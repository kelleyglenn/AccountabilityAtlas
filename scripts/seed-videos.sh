#!/bin/bash
#
# Seed videos from a JSON file into AccountabilityAtlas via the API.
#
# Usage:
#   ./scripts/seed-videos.sh [--file <path>]
#
# Environment variables:
#   ADMIN_EMAIL     - Admin user email (required)
#   ADMIN_PASSWORD  - Admin user password (required)
#   API_URL         - API base URL (default: http://localhost:8080/api/v1)
#

set -euo pipefail

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Defaults
INPUT_FILE="$ROOT_DIR/seed-data/videos.json"
API_URL="${API_URL:-http://localhost:8080/api/v1}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --file)
      INPUT_FILE="$2"
      shift 2
      ;;
    *)
      error "Unknown option: $1"
      echo "Usage: $0 [--file <path>]"
      exit 1
      ;;
  esac
done

# Validate prerequisites
if ! command -v jq &>/dev/null; then
  error "jq is required but not installed. Install it with: brew install jq (macOS) or apt-get install jq (Linux)"
  exit 1
fi

if [[ ! -f "$INPUT_FILE" ]]; then
  error "Input file not found: $INPUT_FILE"
  exit 1
fi

if [[ -z "${ADMIN_EMAIL:-}" || -z "${ADMIN_PASSWORD:-}" ]]; then
  error "ADMIN_EMAIL and ADMIN_PASSWORD environment variables are required"
  exit 1
fi

# Authenticate
info "Authenticating as $ADMIN_EMAIL..."
AUTH_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$ADMIN_EMAIL\", \"password\": \"$ADMIN_PASSWORD\"}")

HTTP_CODE=$(echo "$AUTH_RESPONSE" | tail -1)
AUTH_BODY=$(echo "$AUTH_RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" != "200" ]]; then
  error "Authentication failed (HTTP $HTTP_CODE): $AUTH_BODY"
  exit 1
fi

ACCESS_TOKEN=$(echo "$AUTH_BODY" | jq -r '.tokens.accessToken')
if [[ -z "$ACCESS_TOKEN" || "$ACCESS_TOKEN" == "null" ]]; then
  error "Failed to extract access token from auth response"
  exit 1
fi
success "Authenticated successfully"

AUTH_HEADER="Authorization: Bearer $ACCESS_TOKEN"

# Counters
TOTAL=$(jq 'length' "$INPUT_FILE")
CREATED=0
SKIPPED=0
FAILED=0

info "Processing $TOTAL videos from $INPUT_FILE..."
echo ""

# Process each video entry
for i in $(seq 0 $((TOTAL - 1))); do
  ENTRY=$(jq ".[$i]" "$INPUT_FILE")
  TITLE=$(echo "$ENTRY" | jq -r '.title')
  YOUTUBE_URL=$(echo "$ENTRY" | jq -r '.youtubeUrl')

  echo -n "[$((i + 1))/$TOTAL] $TITLE... "

  # Create location if present
  LOCATION_ID=""
  HAS_LOCATION=$(echo "$ENTRY" | jq 'has("location") and .location != null')

  if [[ "$HAS_LOCATION" == "true" ]]; then
    LAT=$(echo "$ENTRY" | jq '.location.latitude')
    LNG=$(echo "$ENTRY" | jq '.location.longitude')
    LOC_NAME=$(echo "$ENTRY" | jq -r '.location.name // empty')
    LOC_CITY=$(echo "$ENTRY" | jq -r '.location.city // empty')
    LOC_STATE=$(echo "$ENTRY" | jq -r '.location.state // empty')

    # If no lat/lng, try geocoding from name/city/state
    if [[ "$LAT" == "null" || "$LNG" == "null" ]]; then
      ADDRESS_PARTS=""
      [[ -n "$LOC_NAME" ]] && ADDRESS_PARTS="$LOC_NAME"
      [[ -n "$LOC_CITY" ]] && ADDRESS_PARTS="${ADDRESS_PARTS:+$ADDRESS_PARTS, }$LOC_CITY"
      [[ -n "$LOC_STATE" ]] && ADDRESS_PARTS="${ADDRESS_PARTS:+$ADDRESS_PARTS, }$LOC_STATE"

      if [[ -n "$ADDRESS_PARTS" ]]; then
        ENCODED_ADDRESS=$(echo "$ADDRESS_PARTS" | python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read().strip()))" 2>/dev/null || echo "$ADDRESS_PARTS")
        GEOCODE_RESPONSE=$(curl -s -w "\n%{http_code}" \
          "$API_URL/locations/geocode?address=$ENCODED_ADDRESS" \
          -H "$AUTH_HEADER")
        GEO_CODE=$(echo "$GEOCODE_RESPONSE" | tail -1)
        GEO_BODY=$(echo "$GEOCODE_RESPONSE" | sed '$d')

        if [[ "$GEO_CODE" == "200" ]]; then
          LAT=$(echo "$GEO_BODY" | jq '.latitude')
          LNG=$(echo "$GEO_BODY" | jq '.longitude')
        fi
      fi
    fi

    # Only create location if we have coordinates
    if [[ "$LAT" != "null" && "$LNG" != "null" ]]; then
      DISPLAY_NAME="${LOC_NAME:-${LOC_CITY:-Unknown}}"
      LOC_BODY=$(jq -n \
        --arg displayName "$DISPLAY_NAME" \
        --argjson lat "$LAT" \
        --argjson lng "$LNG" \
        --arg city "${LOC_CITY:-}" \
        --arg state "${LOC_STATE:-}" \
        '{
          coordinates: { latitude: $lat, longitude: $lng },
          displayName: $displayName,
          city: (if $city != "" then $city else null end),
          state: (if $state != "" then $state else null end)
        }')

      LOC_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/locations" \
        -H "Content-Type: application/json" \
        -H "$AUTH_HEADER" \
        -d "$LOC_BODY")
      LOC_CODE=$(echo "$LOC_RESPONSE" | tail -1)
      LOC_BODY_RESP=$(echo "$LOC_RESPONSE" | sed '$d')

      if [[ "$LOC_CODE" == "201" ]]; then
        LOCATION_ID=$(echo "$LOC_BODY_RESP" | jq -r '.id')
      fi
    fi
  fi

  # Build video creation request
  AMENDMENTS=$(echo "$ENTRY" | jq -c '.amendments // []')
  PARTICIPANTS=$(echo "$ENTRY" | jq -c '.participants // []')
  VIDEO_DATE=$(echo "$ENTRY" | jq -r '.videoDate // empty')

  VIDEO_BODY=$(jq -n \
    --arg youtubeUrl "$YOUTUBE_URL" \
    --argjson amendments "$AMENDMENTS" \
    --argjson participants "$PARTICIPANTS" \
    --arg videoDate "${VIDEO_DATE:-}" \
    --arg locationId "${LOCATION_ID:-}" \
    '{
      youtubeUrl: $youtubeUrl,
      amendments: $amendments,
      participants: $participants
    }
    + (if $videoDate != "" then { videoDate: $videoDate } else {} end)
    + (if $locationId != "" then { locationId: $locationId } else {} end)')

  # Create video
  VIDEO_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/videos" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d "$VIDEO_BODY")
  VIDEO_CODE=$(echo "$VIDEO_RESPONSE" | tail -1)

  case "$VIDEO_CODE" in
    201)
      echo -e "${GREEN}created${NC}"
      CREATED=$((CREATED + 1))
      ;;
    409)
      echo -e "${YELLOW}already exists (skipped)${NC}"
      SKIPPED=$((SKIPPED + 1))
      ;;
    *)
      VIDEO_BODY_RESP=$(echo "$VIDEO_RESPONSE" | sed '$d')
      echo -e "${RED}failed (HTTP $VIDEO_CODE)${NC}"
      warn "  Response: $VIDEO_BODY_RESP"
      FAILED=$((FAILED + 1))
      ;;
  esac
done

# Summary
echo ""
echo "============================================"
echo "  Seed Summary"
echo "============================================"
echo "  Total:   $TOTAL"
echo -e "  Created: ${GREEN}$CREATED${NC}"
echo -e "  Skipped: ${YELLOW}$SKIPPED${NC}"
echo -e "  Failed:  ${RED}$FAILED${NC}"
echo "============================================"

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi
