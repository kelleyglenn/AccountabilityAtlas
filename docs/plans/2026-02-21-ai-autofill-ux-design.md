# AI Auto-fill UX Improvements

## Context

The AI auto-fill feature (issues #52, #53, #57) is functional but needs UX polish:
- No way to trigger preview with Enter key
- No visible progress indicator during the ~30-40s AI extraction wait
- The success toast doesn't grab enough attention to remind users to review AI suggestions
- Sonnet model is accurate but slow; Haiku may be fast enough

## Changes

### 1. Enter to Preview

Add `onKeyDown` handler to the YouTube URL input. On Enter, call `handlePreview` and `preventDefault` to avoid triggering the outer form submit.

### 2. AI Progress Indicator (3 options for evaluation)

When `isExtracting` is true, show an animated progress indicator below the Auto-fill button. Three options rendered simultaneously for visual comparison:

- **Option A**: Animated bouncing dots with "Analyzing video with AI" text
- **Option B**: Indeterminate progress bar (thin bar with sliding shimmer) and text
- **Option C**: Pulsing text with spinner icon

User picks one; the other two are removed.

### 3. Review Warning Banner

After extraction completes successfully, show a persistent amber banner (no dismiss) in the same area as the progress indicator:

> "AI suggestions applied -- please review all fields before submitting."

Styled consistently with the existing "already submitted" amber warning. New state variable `extractionDone` tracks whether extraction completed successfully.

### 4. Switch to Haiku

Update video-service config to use the faster Haiku model:

| Setting | Before | After |
|---------|--------|-------|
| Model | claude-sonnet-4-6 | claude-haiku-4-5-20251001 |
| Max tokens | 4096 | 4096 |
| Timeout | 60s | 30s |

Files: `application.yml`, `AnthropicProperties.java`, `MetadataExtractionServiceTest.java`

## Branches

- Web-app: `feature/52-ai-autofill` (PR #61)
- Video-service: `feature/52-53-57-llm-extraction` (PR #44)
