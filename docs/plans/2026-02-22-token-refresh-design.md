# Token Refresh Design

## Problem

Access tokens expire after 15 minutes with no renewal mechanism. The user is silently logged out on their next API call after expiry, which is disruptive for a demo.

## Scope

- **user-service #22**: Implement `POST /auth/refresh` endpoint
- **web-app #3**: Store refresh token + auto-refresh logic
- **web-app #4**: Deferred (keep sessionStorage, no HTTP-only cookies for now)

## Backend: `POST /auth/refresh` (user-service)

### New method: `AuthenticationService.refresh(String refreshToken)`

1. Hash incoming refresh token via `TokenService.hashRefreshToken()`
2. Look up session via `SessionRepository.findValidByRefreshTokenHash(hash, now)`
3. If not found, throw exception mapping to 401
4. Load user via `UserRepository.findById(session.getUserId())`
5. **Rotate refresh token**: generate new token, hash it, update session's `refreshTokenHash` and reset `expiresAt`
6. Generate new access token
7. Return `AuthResult(user, newAccessToken, newRefreshToken)`

### Controller wiring: `AuthController.refreshTokens()`

- Call `authenticationService.refresh(request.getRefreshToken())`
- Map result to `RefreshResponse` with `TokenPair`
- Return 200 on success, 401 on invalid/expired/revoked token

### `expiresIn` fix

Currently hardcoded to `900` in `toTokenPair()`. Derive from `JwtProperties.getAccessTokenExpiry()` instead.

### Error codes

| Condition | HTTP | Error code |
|-----------|------|------------|
| Invalid/missing refresh token | 401 | `INVALID_REFRESH_TOKEN` |
| Expired session | 401 | `SESSION_EXPIRED` |
| Revoked session / token reuse | 401 | `TOKEN_REUSED` |

On token reuse detection, also revoke the session (security measure for stolen tokens).

## Frontend: Token Storage & Refresh Logic (web-app)

### `auth.ts` - New API call

```typescript
export async function refreshTokens(refreshToken: string): Promise<RefreshResponse> {
  const response = await apiClient.post<RefreshResponse>("/auth/refresh", { refreshToken });
  return response.data;
}
```

### `client.ts` - Axios 401 interceptor with request queue

Response interceptor catches 401 errors:
- First 401 triggers a refresh call; concurrent 401s queue and wait
- On success: retry all queued requests with new token
- On failure: clear auth state, redirect to login
- Skip retry for `/auth/refresh` itself (prevent infinite loop via `_retry` flag)

Functions `refreshTokens()` and `clearAuth()` are registered by `AuthProvider` via setter functions (same pattern as existing `setAccessToken`).

### `AuthProvider.tsx` - Store refresh token + proactive timer

**On login/register:**
- Store both `accessToken` and `refreshToken` in sessionStorage
- Schedule refresh at ~80% of `expiresIn` (12 minutes for 15-minute tokens)

**Proactive timer:**
- `setTimeout` fires at 80% of token lifetime
- Calls `/auth/refresh`, stores new tokens, reschedules on success
- Clears auth on failure (user lands on login naturally)

**On mount (page refresh):**
- Restore both tokens from sessionStorage
- If access token is near expiry (within 20% of lifetime), refresh immediately
- Otherwise schedule at normal 80% mark

**On logout:**
- Clear both tokens from sessionStorage
- Cancel the refresh timer

## Edge Cases

- **Refresh endpoint returns 401**: Interceptor does NOT retry `/auth/refresh` calls. Falls through to `clearAuth()`.
- **Concurrent requests during refresh**: Queue ensures only one refresh call in flight.
- **Timer drift / tab sleeping**: 401 interceptor catches late timers as fallback.
- **Page refresh**: Tokens restored from sessionStorage; timer rescheduled.

## Not in scope (YAGNI)

- "Remember me" checkbox
- Cross-tab token synchronization
- Sliding window / activity-based extension
- HTTP-only cookie storage (deferred)

## Testing

### Backend (user-service)

- **Unit tests** for `AuthenticationService.refresh()`: valid token, expired session, revoked session, token reuse detection
- **`@WebMvcTest`** for `AuthController`: endpoint contract (200/401)
- **Integration test** (`@SpringBootTest` + TestContainers): login -> refresh -> verify new tokens work -> verify old refresh token invalidated

### Frontend (web-app)

- **Unit tests for interceptor**: 401 -> refresh -> retry; concurrent 401 queue behavior
- **Unit tests for AuthProvider**: login stores both tokens; timer fires refresh; failed refresh clears auth

### Integration tests (AcctAtlas-integration-tests)

- **API test**: login -> refresh -> verify new tokens work
- **E2E test**: login -> verify session persists beyond access token lifetime
