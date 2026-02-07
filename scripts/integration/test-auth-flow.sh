#!/bin/bash
#
# Test the full authentication flow through the API gateway:
# 1. Register a new user
# 2. Login and capture the access token
# 3. Call /users/me with the token
#
# Prerequisites:
#   - docker-compose --profile backend is running
#   - jq is installed (for JSON parsing)
#
# Usage:
#   ./scripts/tests/test-auth-flow.sh [email]
#

set -e

BASE_URL="${BASE_URL:-http://localhost:8080/api/v1}"
EMAIL="${1:-test-$(date +%s)@example.com}"
PASSWORD="SecurePass123"
DISPLAY_NAME="TestUser"

echo "=== Auth Flow Test ==="
echo "Base URL: $BASE_URL"
echo "Email: $EMAIL"
echo ""

# Check for jq
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed."
    echo "Install with: choco install jq (Windows) or apt install jq (Linux)"
    exit 1
fi

# Step 1: Register
echo "--- Step 1: Register ---"
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"displayName\":\"$DISPLAY_NAME\"}")

echo "Response:"
echo "$REGISTER_RESPONSE" | jq .

# Check for error
if echo "$REGISTER_RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    echo ""
    echo "Registration failed. If email already exists, trying login..."
else
    echo ""
    echo "Registration successful!"
fi
echo ""

# Step 2: Login
echo "--- Step 2: Login ---"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

echo "Response:"
echo "$LOGIN_RESPONSE" | jq .

# Extract access token
ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.tokens.accessToken')

if [ "$ACCESS_TOKEN" = "null" ] || [ -z "$ACCESS_TOKEN" ]; then
    echo ""
    echo "Error: Failed to get access token from login response"
    exit 1
fi

echo ""
echo "Access token obtained: ${ACCESS_TOKEN:0:50}..."
echo ""

# Step 3: Get current user
echo "--- Step 3: Get Current User (/users/me) ---"
ME_RESPONSE=$(curl -s "$BASE_URL/users/me" \
    -H "Authorization: Bearer $ACCESS_TOKEN")

echo "Response:"
echo "$ME_RESPONSE" | jq .

echo ""
echo "=== Test Complete ==="
