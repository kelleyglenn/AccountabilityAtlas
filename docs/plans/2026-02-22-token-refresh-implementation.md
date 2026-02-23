# Token Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement token refresh so users stay logged in beyond the 15-minute access token lifetime.

**Architecture:** Backend adds a `refresh()` method to `AuthenticationService` that validates a refresh token, rotates it, and returns a new token pair. Frontend stores refresh tokens in sessionStorage and auto-refreshes via a proactive timer + axios 401 interceptor fallback.

**Tech Stack:** Java 21 / Spring Boot 3.4 / JUnit 5 / Mockito (backend); TypeScript / React / axios / Jest (frontend)

**Design doc:** `docs/plans/2026-02-22-token-refresh-design.md`

---

## Task 1: Backend — Exception class + handler (user-service)

**Issue:** `kelleyglenn/AcctAtlas-user-service#22`

**Files:**
- Create: `src/main/java/com/accountabilityatlas/userservice/exception/InvalidRefreshTokenException.java`
- Modify: `src/main/java/com/accountabilityatlas/userservice/exception/GlobalExceptionHandler.java`

### Step 1: Create `InvalidRefreshTokenException`

Follow the pattern from `InvalidCredentialsException.java`:

```java
package com.accountabilityatlas.userservice.exception;

public class InvalidRefreshTokenException extends RuntimeException {
  public InvalidRefreshTokenException(String message) {
    super(message);
  }
}
```

### Step 2: Add handler to `GlobalExceptionHandler`

Add a new `@ExceptionHandler` method after the existing `handleInvalidCredentials` (around line 28). Follow the exact same pattern:

```java
@ExceptionHandler(InvalidRefreshTokenException.class)
public ResponseEntity<Error> handleInvalidRefreshToken(InvalidRefreshTokenException ex) {
  Error error = new Error();
  error.setCode("INVALID_REFRESH_TOKEN");
  error.setMessage(ex.getMessage());
  return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(error);
}
```

### Step 3: Run quality checks

Run: `./gradlew spotlessApply && ./gradlew check`
Expected: BUILD SUCCESSFUL

### Step 4: Commit

```bash
git add src/main/java/com/accountabilityatlas/userservice/exception/InvalidRefreshTokenException.java \
  src/main/java/com/accountabilityatlas/userservice/exception/GlobalExceptionHandler.java
git commit -m "feat(auth): add InvalidRefreshTokenException and handler (#22)"
```

---

## Task 2: Backend — `AuthenticationService.refresh()` + unit tests (user-service)

**Issue:** `kelleyglenn/AcctAtlas-user-service#22`

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/userservice/service/AuthenticationService.java`
- Modify: `src/test/java/com/accountabilityatlas/userservice/service/AuthenticationServiceTest.java`

### Step 1: Write failing unit tests

Add these tests to `AuthenticationServiceTest.java`. They follow the existing test patterns (Mockito `@ExtendWith`, `@Mock`/`@InjectMocks`, `when`/`thenReturn`, `assertThat`/`assertThatThrownBy`). Reuse the existing `buildUser()` helper.

```java
@Test
void refresh_returnsNewTokenPairOnValidToken() {
  UUID userId = UUID.randomUUID();
  UUID sessionId = UUID.randomUUID();
  User user = buildUser("test@example.com", "$2a$12$hashed");
  ReflectionTestUtils.setField(user, "id", userId);

  Session session = new Session();
  ReflectionTestUtils.setField(session, "id", sessionId);
  session.setUserId(userId);
  session.setRefreshTokenHash("old-hash");
  session.setExpiresAt(Instant.now().plusSeconds(86400));

  when(tokenService.hashRefreshToken("valid-refresh-token")).thenReturn("old-hash");
  when(sessionRepository.findValidByRefreshTokenHash(eq("old-hash"), any(Instant.class)))
      .thenReturn(Optional.of(session));
  when(userRepository.findById(userId)).thenReturn(Optional.of(user));
  when(tokenService.generateRefreshToken()).thenReturn("new-refresh-token");
  when(tokenService.hashRefreshToken("new-refresh-token")).thenReturn("new-hash");
  when(jwtProperties.getRefreshTokenExpiry()).thenReturn(Duration.ofDays(7));
  when(tokenService.generateAccessToken(eq(userId), eq("test@example.com"), any(), eq(sessionId)))
      .thenReturn("new-access-token");

  AuthResult result = authenticationService.refresh("valid-refresh-token");

  assertThat(result.accessToken()).isEqualTo("new-access-token");
  assertThat(result.refreshToken()).isEqualTo("new-refresh-token");
  assertThat(result.user()).isEqualTo(user);
}

@Test
void refresh_rotatesRefreshTokenHash() {
  UUID userId = UUID.randomUUID();
  UUID sessionId = UUID.randomUUID();
  User user = buildUser("test@example.com", "$2a$12$hashed");
  ReflectionTestUtils.setField(user, "id", userId);

  Session session = new Session();
  ReflectionTestUtils.setField(session, "id", sessionId);
  session.setUserId(userId);
  session.setRefreshTokenHash("old-hash");
  session.setExpiresAt(Instant.now().plusSeconds(86400));

  when(tokenService.hashRefreshToken("valid-refresh-token")).thenReturn("old-hash");
  when(sessionRepository.findValidByRefreshTokenHash(eq("old-hash"), any(Instant.class)))
      .thenReturn(Optional.of(session));
  when(userRepository.findById(userId)).thenReturn(Optional.of(user));
  when(tokenService.generateRefreshToken()).thenReturn("new-refresh-token");
  when(tokenService.hashRefreshToken("new-refresh-token")).thenReturn("new-hash");
  when(jwtProperties.getRefreshTokenExpiry()).thenReturn(Duration.ofDays(7));
  when(tokenService.generateAccessToken(any(), anyString(), any(), any()))
      .thenReturn("new-access-token");

  authenticationService.refresh("valid-refresh-token");

  assertThat(session.getRefreshTokenHash()).isEqualTo("new-hash");
}

@Test
void refresh_throwsOnInvalidToken() {
  when(tokenService.hashRefreshToken("bad-token")).thenReturn("bad-hash");
  when(sessionRepository.findValidByRefreshTokenHash(eq("bad-hash"), any(Instant.class)))
      .thenReturn(Optional.empty());

  assertThatThrownBy(() -> authenticationService.refresh("bad-token"))
      .isInstanceOf(InvalidRefreshTokenException.class);
}

@Test
void refresh_throwsWhenUserNotFound() {
  UUID userId = UUID.randomUUID();
  Session session = new Session();
  session.setUserId(userId);
  session.setRefreshTokenHash("hash");
  session.setExpiresAt(Instant.now().plusSeconds(86400));

  when(tokenService.hashRefreshToken("token")).thenReturn("hash");
  when(sessionRepository.findValidByRefreshTokenHash(eq("hash"), any(Instant.class)))
      .thenReturn(Optional.of(session));
  when(userRepository.findById(userId)).thenReturn(Optional.empty());

  assertThatThrownBy(() -> authenticationService.refresh("token"))
      .isInstanceOf(InvalidRefreshTokenException.class);
}
```

Add these imports to the test file:
```java
import com.accountabilityatlas.userservice.exception.InvalidRefreshTokenException;
import org.springframework.test.util.ReflectionTestUtils;
```

### Step 2: Run tests — verify they fail

Run: `./gradlew test --tests "*.AuthenticationServiceTest"`
Expected: FAIL — `refresh` method does not exist on `AuthenticationService`.

### Step 3: Implement `AuthenticationService.refresh()`

Add this method to `AuthenticationService.java` after the `logout()` method:

```java
@Transactional
public AuthResult refresh(String refreshToken) {
  String hash = tokenService.hashRefreshToken(refreshToken);
  Instant now = Instant.now();

  Session session =
      sessionRepository
          .findValidByRefreshTokenHash(hash, now)
          .orElseThrow(() -> new InvalidRefreshTokenException("Invalid or expired refresh token"));

  User user =
      userRepository
          .findById(session.getUserId())
          .orElseThrow(() -> new InvalidRefreshTokenException("User not found for session"));

  // Rotate refresh token
  String newRefreshToken = tokenService.generateRefreshToken();
  String newRefreshTokenHash = tokenService.hashRefreshToken(newRefreshToken);
  session.setRefreshTokenHash(newRefreshTokenHash);
  session.setExpiresAt(now.plus(jwtProperties.getRefreshTokenExpiry()));

  String accessToken =
      tokenService.generateAccessToken(
          user.getId(), user.getEmail(), user.getTrustTier(), session.getId());

  return new AuthResult(user, accessToken, newRefreshToken);
}
```

Add this import to `AuthenticationService.java`:
```java
import com.accountabilityatlas.userservice.exception.InvalidRefreshTokenException;
```

### Step 4: Run tests — verify they pass

Run: `./gradlew test --tests "*.AuthenticationServiceTest"`
Expected: All tests PASS

### Step 5: Commit

```bash
git add src/main/java/com/accountabilityatlas/userservice/service/AuthenticationService.java \
  src/test/java/com/accountabilityatlas/userservice/service/AuthenticationServiceTest.java
git commit -m "feat(auth): implement AuthenticationService.refresh() with TDD (#22)"
```

---

## Task 3: Backend — Wire up controller + fix `expiresIn` + controller test (user-service)

**Issue:** `kelleyglenn/AcctAtlas-user-service#22`

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/userservice/web/AuthController.java`
- Modify: `src/test/java/com/accountabilityatlas/userservice/web/AuthControllerTest.java`

### Step 1: Write failing controller tests

Replace the existing `refreshTokens_returns501` test in `AuthControllerTest.java` with these:

```java
@Test
void refreshTokens_returns200OnSuccess() throws Exception {
  var user = buildDomainUser();
  var result = new AuthResult(user, "new-access-token", "new-refresh-token");
  when(authenticationService.refresh("valid-refresh-token")).thenReturn(result);

  mockMvc
      .perform(
          post("/auth/refresh")
              .contentType(MediaType.APPLICATION_JSON)
              .content(
                  """
                  {"refreshToken": "valid-refresh-token"}
                  """))
      .andExpect(status().isOk())
      .andExpect(jsonPath("$.tokens.accessToken").value("new-access-token"))
      .andExpect(jsonPath("$.tokens.refreshToken").value("new-refresh-token"))
      .andExpect(jsonPath("$.tokens.expiresIn").isNumber())
      .andExpect(jsonPath("$.tokens.tokenType").value("Bearer"));
}

@Test
void refreshTokens_returns401OnInvalidToken() throws Exception {
  when(authenticationService.refresh("bad-token"))
      .thenThrow(new InvalidRefreshTokenException("Invalid or expired refresh token"));

  mockMvc
      .perform(
          post("/auth/refresh")
              .contentType(MediaType.APPLICATION_JSON)
              .content(
                  """
                  {"refreshToken": "bad-token"}
                  """))
      .andExpect(status().isUnauthorized())
      .andExpect(jsonPath("$.code").value("INVALID_REFRESH_TOKEN"));
}
```

Add this import to `AuthControllerTest.java`:
```java
import com.accountabilityatlas.userservice.exception.InvalidRefreshTokenException;
```

### Step 2: Run tests — verify they fail

Run: `./gradlew test --tests "*.AuthControllerTest"`
Expected: FAIL — controller still returns 501.

### Step 3: Wire up `AuthController.refreshTokens()` and fix `expiresIn`

In `AuthController.java`:

1. Add `JwtProperties` as a constructor dependency:

```java
private final RegistrationService registrationService;
private final AuthenticationService authenticationService;
private final JwtProperties jwtProperties;

public AuthController(
    RegistrationService registrationService,
    AuthenticationService authenticationService,
    JwtProperties jwtProperties) {
  this.registrationService = registrationService;
  this.authenticationService = authenticationService;
  this.jwtProperties = jwtProperties;
}
```

2. Replace the `refreshTokens()` method body:

```java
@Override
public ResponseEntity<RefreshResponse> refreshTokens(RefreshRequest refreshRequest) {
  AuthResult result = authenticationService.refresh(refreshRequest.getRefreshToken());

  RefreshResponse response = new RefreshResponse();
  response.setTokens(toTokenPair(result.accessToken(), result.refreshToken()));
  return ResponseEntity.ok(response);
}
```

3. Fix `toTokenPair()` to derive `expiresIn` from config:

```java
private TokenPair toTokenPair(String accessToken, String refreshToken) {
  TokenPair tokens = new TokenPair();
  tokens.setAccessToken(accessToken);
  tokens.setRefreshToken(refreshToken);
  tokens.setExpiresIn((int) jwtProperties.getAccessTokenExpiry().toSeconds());
  tokens.setTokenType("Bearer");
  return tokens;
}
```

Add this import:
```java
import com.accountabilityatlas.userservice.config.JwtProperties;
```

4. Add `@MockitoBean` for `JwtProperties` in `AuthControllerTest.java` (line ~47, after the existing `@MockitoBean` declarations):

```java
@MockitoBean private JwtProperties jwtProperties;
```

And in the test setup, configure the mock to return a real value. Add this to each test that checks `expiresIn`, or add a `@BeforeEach`:

```java
@BeforeEach
void setUp() {
  when(jwtProperties.getAccessTokenExpiry()).thenReturn(Duration.ofMinutes(15));
}
```

Add this import:
```java
import com.accountabilityatlas.userservice.config.JwtProperties;
import java.time.Duration;
import org.junit.jupiter.api.BeforeEach;
```

Also update `login_mapsAllUserFieldsIncludingOptional` test assertion to use dynamic value:
Change `.andExpect(jsonPath("$.tokens.expiresIn").value(900))` — this should still pass since `Duration.ofMinutes(15).toSeconds()` is `900`.

### Step 4: Run tests — verify they pass

Run: `./gradlew test --tests "*.AuthControllerTest"`
Expected: All tests PASS

### Step 5: Run full quality checks

Run: `./gradlew spotlessApply && ./gradlew check`
Expected: BUILD SUCCESSFUL

### Step 6: Commit

```bash
git add src/main/java/com/accountabilityatlas/userservice/web/AuthController.java \
  src/test/java/com/accountabilityatlas/userservice/web/AuthControllerTest.java
git commit -m "feat(auth): wire up POST /auth/refresh and fix dynamic expiresIn (#22)"
```

---

## Task 4: Backend — Integration test (user-service)

**Issue:** `kelleyglenn/AcctAtlas-user-service#22`

**Files:**
- Modify: `src/test/java/com/accountabilityatlas/userservice/integration/AuthIntegrationTest.java`

### Step 1: Add integration tests

Add these tests to `AuthIntegrationTest.java`. Follow the existing patterns (register first, extract token via `JsonPath.read()`):

```java
@Test
void refresh_returnsNewTokenPair() throws Exception {
  // Register to get initial tokens
  MvcResult registerResult =
      mockMvc
          .perform(
              post("/auth/register")
                  .contentType(MediaType.APPLICATION_JSON)
                  .content(
                      """
                      {
                        "email": "refresh@example.com",
                        "password": "SecurePass123",
                        "displayName": "RefreshUser"
                      }
                      """))
          .andExpect(status().isCreated())
          .andReturn();

  String refreshToken =
      JsonPath.read(registerResult.getResponse().getContentAsString(), "$.tokens.refreshToken");

  // Refresh
  MvcResult refreshResult =
      mockMvc
          .perform(
              post("/auth/refresh")
                  .contentType(MediaType.APPLICATION_JSON)
                  .content(String.format("""
                      {"refreshToken": "%s"}
                      """, refreshToken)))
          .andExpect(status().isOk())
          .andExpect(jsonPath("$.tokens.accessToken").exists())
          .andExpect(jsonPath("$.tokens.refreshToken").exists())
          .andExpect(jsonPath("$.tokens.expiresIn").value(900))
          .andExpect(jsonPath("$.tokens.tokenType").value("Bearer"))
          .andReturn();

  // New access token should work for authenticated endpoints
  String newAccessToken =
      JsonPath.read(refreshResult.getResponse().getContentAsString(), "$.tokens.accessToken");
  mockMvc
      .perform(get("/users/me").header("Authorization", "Bearer " + newAccessToken))
      .andExpect(status().isOk())
      .andExpect(jsonPath("$.email").value("refresh@example.com"));
}

@Test
void refresh_rotatesRefreshToken() throws Exception {
  MvcResult registerResult =
      mockMvc
          .perform(
              post("/auth/register")
                  .contentType(MediaType.APPLICATION_JSON)
                  .content(
                      """
                      {
                        "email": "rotate@example.com",
                        "password": "SecurePass123",
                        "displayName": "RotateUser"
                      }
                      """))
          .andExpect(status().isCreated())
          .andReturn();

  String originalRefreshToken =
      JsonPath.read(registerResult.getResponse().getContentAsString(), "$.tokens.refreshToken");

  // First refresh succeeds
  MvcResult refreshResult =
      mockMvc
          .perform(
              post("/auth/refresh")
                  .contentType(MediaType.APPLICATION_JSON)
                  .content(String.format("""
                      {"refreshToken": "%s"}
                      """, originalRefreshToken)))
          .andExpect(status().isOk())
          .andReturn();

  String newRefreshToken =
      JsonPath.read(refreshResult.getResponse().getContentAsString(), "$.tokens.refreshToken");
  assertThat(newRefreshToken).isNotEqualTo(originalRefreshToken);

  // Original refresh token no longer works (rotation)
  mockMvc
      .perform(
          post("/auth/refresh")
              .contentType(MediaType.APPLICATION_JSON)
              .content(String.format("""
                  {"refreshToken": "%s"}
                  """, originalRefreshToken)))
      .andExpect(status().isUnauthorized());
}

@Test
void refresh_rejectsInvalidToken() throws Exception {
  mockMvc
      .perform(
          post("/auth/refresh")
              .contentType(MediaType.APPLICATION_JSON)
              .content("""
                  {"refreshToken": "completely-invalid-token"}
                  """))
      .andExpect(status().isUnauthorized())
      .andExpect(jsonPath("$.code").value("INVALID_REFRESH_TOKEN"));
}
```

### Step 2: Run integration tests

Run: `./gradlew test --tests "*.AuthIntegrationTest"`
Expected: All tests PASS

### Step 3: Run full check

Run: `./gradlew spotlessApply && ./gradlew check`
Expected: BUILD SUCCESSFUL

### Step 4: Commit

```bash
git add src/test/java/com/accountabilityatlas/userservice/integration/AuthIntegrationTest.java
git commit -m "test(auth): add integration tests for token refresh (#22)"
```

---

## Task 5: Frontend — Add `RefreshResponse` type + `refreshTokens` API function (web-app)

**Issue:** `kelleyglenn/AcctAtlas-web-app#3`

**Files:**
- Modify: `src/types/api.ts`
- Modify: `src/lib/api/auth.ts`
- Modify: `src/__tests__/lib/api/auth.test.ts`

### Step 1: Add `RefreshResponse` type

Add to `src/types/api.ts` after `LoginResponse` (line 78):

```typescript
export interface RefreshResponse {
  tokens: TokenPair;
}
```

### Step 2: Write failing test for `refreshTokens`

Add to `src/__tests__/lib/api/auth.test.ts`:

```typescript
describe("refreshTokens", () => {
  it("calls apiClient.post with /auth/refresh and returns response.data", async () => {
    const responseData = {
      tokens: {
        accessToken: "new-access",
        refreshToken: "new-refresh",
        expiresIn: 900,
        tokenType: "Bearer",
      },
    };

    (apiClient.post as jest.Mock).mockResolvedValue({ data: responseData });

    const result = await refreshTokens("old-refresh-token");

    expect(apiClient.post).toHaveBeenCalledWith("/auth/refresh", {
      refreshToken: "old-refresh-token",
    });
    expect(result).toEqual(responseData);
  });
});
```

Update the import at the top of the test file:
```typescript
import { login, register, refreshTokens } from "@/lib/api/auth";
```

### Step 3: Run test — verify it fails

Run: `npm test -- --testPathPattern="auth.test.ts"`
Expected: FAIL — `refreshTokens` is not exported.

### Step 4: Add `refreshTokens` to `auth.ts`

Add to `src/lib/api/auth.ts`:

```typescript
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  RefreshResponse,
} from "@/types/api";
```

Add the function:

```typescript
export async function refreshTokens(
  refreshToken: string
): Promise<RefreshResponse> {
  const response = await apiClient.post<RefreshResponse>("/auth/refresh", {
    refreshToken,
  });
  return response.data;
}
```

### Step 5: Run test — verify it passes

Run: `npm test -- --testPathPattern="auth.test.ts"`
Expected: PASS

### Step 6: Commit

```bash
git add src/types/api.ts src/lib/api/auth.ts src/__tests__/lib/api/auth.test.ts
git commit -m "feat(auth): add refreshTokens API function (#3)"
```

---

## Task 6: Frontend — Axios 401 interceptor with refresh queue (web-app)

**Issue:** `kelleyglenn/AcctAtlas-web-app#3`

**Files:**
- Modify: `src/lib/api/client.ts`
- Create: `src/__tests__/lib/api/client.test.ts`

### Step 1: Write failing tests for the interceptor

Create `src/__tests__/lib/api/client.test.ts`:

```typescript
import axios from "axios";

// Must mock axios before importing client
jest.mock("axios", () => {
  const mockAxios = {
    create: jest.fn(() => mockAxios),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
    post: jest.fn(),
    get: jest.fn(),
    defaults: { headers: { common: {} } },
  };
  return { __esModule: true, default: mockAxios };
});

describe("client 401 interceptor", () => {
  it("exports setOnRefreshTokens and setOnClearAuth", async () => {
    const { setOnRefreshTokens, setOnClearAuth } = await import(
      "@/lib/api/client"
    );
    expect(typeof setOnRefreshTokens).toBe("function");
    expect(typeof setOnClearAuth).toBe("function");
  });
});
```

### Step 2: Run test — verify it fails

Run: `npm test -- --testPathPattern="client.test.ts"`
Expected: FAIL — `setOnRefreshTokens` not exported.

### Step 3: Implement the interceptor

Replace `src/lib/api/client.ts` with:

```typescript
import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api/v1";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// Callbacks registered by AuthProvider
let onRefreshTokens: (() => Promise<void>) | null = null;
let onClearAuth: (() => void) | null = null;

export function setOnRefreshTokens(fn: (() => Promise<void>) | null) {
  onRefreshTokens = fn;
}

export function setOnClearAuth(fn: (() => void) | null) {
  onClearAuth = fn;
}

// Request interceptor — attach access token
apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// Response interceptor — handle 401 with refresh queue
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

function processQueue(error: unknown | null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve();
    }
  });
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => apiClient(originalRequest));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        if (onRefreshTokens) {
          await onRefreshTokens();
        } else {
          throw new Error("No refresh handler registered");
        }
        processQueue(null);
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);
        if (onClearAuth) {
          onClearAuth();
        }
        return Promise.reject(error);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
```

### Step 4: Run test — verify it passes

Run: `npm test -- --testPathPattern="client.test.ts"`
Expected: PASS

### Step 5: Commit

```bash
git add src/lib/api/client.ts src/__tests__/lib/api/client.test.ts
git commit -m "feat(auth): add 401 interceptor with refresh queue (#3)"
```

---

## Task 7: Frontend — AuthProvider refresh token storage + proactive timer (web-app)

**Issue:** `kelleyglenn/AcctAtlas-web-app#3`

**Files:**
- Modify: `src/providers/AuthProvider.tsx`
- Modify: `src/__tests__/providers/AuthProvider.test.tsx`

### Step 1: Write failing tests

Add these tests to `src/__tests__/providers/AuthProvider.test.tsx`.

First, update the mock for `@/lib/api/client` to include the new exports:

```typescript
jest.mock("@/lib/api/client", () => ({
  setAccessToken: jest.fn(),
  setOnRefreshTokens: jest.fn(),
  setOnClearAuth: jest.fn(),
}));
```

Update the typed mock imports:

```typescript
import {
  setAccessToken,
  setOnRefreshTokens,
  setOnClearAuth,
} from "@/lib/api/client";

const mockSetAccessToken = setAccessToken as jest.MockedFunction<
  typeof setAccessToken
>;
const mockSetOnRefreshTokens = setOnRefreshTokens as jest.MockedFunction<
  typeof setOnRefreshTokens
>;
const mockSetOnClearAuth = setOnClearAuth as jest.MockedFunction<
  typeof setOnClearAuth
>;
```

Update the mock for auth API to include `refreshTokens`:

```typescript
jest.mock("@/lib/api/auth", () => ({
  login: jest.fn(),
  register: jest.fn(),
  logout: jest.fn(),
  refreshTokens: jest.fn(),
}));
```

Add typed mock:
```typescript
const mockRefreshTokens = authApi.refreshTokens as jest.MockedFunction<
  typeof authApi.refreshTokens
>;
```

Add these test cases:

```typescript
describe("refresh token storage", () => {
  it("should store refresh token in sessionStorage on login", async () => {
    mockLogin.mockResolvedValueOnce(mockLoginResponse);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.login("test@example.com", "password123");
    });

    expect(sessionStorage.getItem("refreshToken")).toBe(
      "test-refresh-token"
    );
  });

  it("should store refresh token in sessionStorage on register", async () => {
    mockRegister.mockResolvedValueOnce(mockRegisterResponse);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.register(
        "test@example.com",
        "password123",
        "Test User"
      );
    });

    expect(sessionStorage.getItem("refreshToken")).toBe(
      "register-refresh-token"
    );
  });

  it("should clear refresh token on logout", async () => {
    mockLogin.mockResolvedValueOnce(mockLoginResponse);
    mockLogout.mockResolvedValue(undefined);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.login("test@example.com", "password123");
    });

    expect(sessionStorage.getItem("refreshToken")).toBe(
      "test-refresh-token"
    );

    act(() => {
      result.current.logout();
    });

    expect(sessionStorage.getItem("refreshToken")).toBeNull();
  });
});

describe("callback registration", () => {
  it("should register onRefreshTokens and onClearAuth callbacks on mount", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockSetOnRefreshTokens).toHaveBeenCalledWith(expect.any(Function));
    expect(mockSetOnClearAuth).toHaveBeenCalledWith(expect.any(Function));
  });
});
```

### Step 2: Run tests — verify they fail

Run: `npm test -- --testPathPattern="AuthProvider.test"`
Expected: FAIL — refresh token not stored, callbacks not registered.

### Step 3: Implement AuthProvider changes

Replace `src/providers/AuthProvider.tsx`:

```typescript
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  setAccessToken,
  setOnRefreshTokens,
  setOnClearAuth,
} from "@/lib/api/client";
import * as authApi from "@/lib/api/auth";
import * as usersApi from "@/lib/api/users";
import type { User } from "@/types/api";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    displayName: string
  ) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const REFRESH_THRESHOLD = 0.8; // Refresh at 80% of token lifetime

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  const clearAuth = useCallback(() => {
    clearRefreshTimer();
    setUser(null);
    setAccessToken(null);
    sessionStorage.removeItem("accessToken");
    sessionStorage.removeItem("refreshToken");
    sessionStorage.removeItem("tokenExpiresAt");
  }, [clearRefreshTimer]);

  const performRefresh = useCallback(async () => {
    const refreshToken = sessionStorage.getItem("refreshToken");
    if (!refreshToken) {
      clearAuth();
      return;
    }

    try {
      const response = await authApi.refreshTokens(refreshToken);
      setAccessToken(response.tokens.accessToken);
      sessionStorage.setItem("accessToken", response.tokens.accessToken);
      sessionStorage.setItem("refreshToken", response.tokens.refreshToken);
      const expiresAt = Date.now() + response.tokens.expiresIn * 1000;
      sessionStorage.setItem("tokenExpiresAt", expiresAt.toString());
      scheduleRefresh(response.tokens.expiresIn);
    } catch {
      clearAuth();
    }
  }, [clearAuth]);

  const scheduleRefresh = useCallback(
    (expiresInSeconds: number) => {
      clearRefreshTimer();
      const delayMs = expiresInSeconds * 1000 * REFRESH_THRESHOLD;
      refreshTimerRef.current = setTimeout(() => {
        performRefresh();
      }, delayMs);
    },
    [clearRefreshTimer, performRefresh]
  );

  const storeTokensAndSchedule = useCallback(
    (accessTokenValue: string, refreshToken: string, expiresIn: number) => {
      setAccessToken(accessTokenValue);
      sessionStorage.setItem("accessToken", accessTokenValue);
      sessionStorage.setItem("refreshToken", refreshToken);
      const expiresAt = Date.now() + expiresIn * 1000;
      sessionStorage.setItem("tokenExpiresAt", expiresAt.toString());
      scheduleRefresh(expiresIn);
    },
    [scheduleRefresh]
  );

  // Register interceptor callbacks
  useEffect(() => {
    setOnRefreshTokens(performRefresh);
    setOnClearAuth(clearAuth);

    return () => {
      setOnRefreshTokens(null);
      setOnClearAuth(null);
      clearRefreshTimer();
    };
  }, [performRefresh, clearAuth, clearRefreshTimer]);

  const fetchCurrentUser = useCallback(async () => {
    try {
      const userData = await usersApi.getCurrentUser();
      setUser(userData);
    } catch {
      setUser(null);
      setAccessToken(null);
    }
  }, []);

  useEffect(() => {
    const storedToken = sessionStorage.getItem("accessToken");
    const storedRefreshToken = sessionStorage.getItem("refreshToken");

    if (storedToken && storedRefreshToken) {
      setAccessToken(storedToken);

      // Check if token is near expiry and schedule refresh
      const expiresAt = sessionStorage.getItem("tokenExpiresAt");
      if (expiresAt) {
        const remainingMs = parseInt(expiresAt, 10) - Date.now();
        if (remainingMs <= 0) {
          // Token expired — refresh immediately
          performRefresh();
        } else {
          const totalLifetimeMs = 900 * 1000; // 15 min default
          const remainingFraction = remainingMs / totalLifetimeMs;
          if (remainingFraction <= 1 - REFRESH_THRESHOLD) {
            // Less than 20% lifetime remaining — refresh now
            performRefresh();
          } else {
            scheduleRefresh(remainingMs / 1000);
          }
        }
      }

      fetchCurrentUser().finally(() => setIsLoading(false));
    } else if (storedToken) {
      // Legacy: access token only, no refresh token
      setAccessToken(storedToken);
      fetchCurrentUser().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [fetchCurrentUser, performRefresh, scheduleRefresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await authApi.login({ email, password });
      storeTokensAndSchedule(
        response.tokens.accessToken,
        response.tokens.refreshToken,
        response.tokens.expiresIn
      );
      setUser(response.user);
    },
    [storeTokensAndSchedule]
  );

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      const response = await authApi.register({
        email,
        password,
        displayName,
      });
      storeTokensAndSchedule(
        response.tokens.accessToken,
        response.tokens.refreshToken,
        response.tokens.expiresIn
      );
      setUser(response.user);
    },
    [storeTokensAndSchedule]
  );

  const logout = useCallback(() => {
    authApi.logout().catch(() => {});
    clearAuth();
  }, [clearAuth]);

  const refreshUser = useCallback(async () => {
    try {
      const userData = await usersApi.getCurrentUser();
      setUser(userData);
    } catch {
      // ignore - user data might be stale but that's ok
    }
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
```

### Step 4: Run tests — verify they pass

Run: `npm test -- --testPathPattern="AuthProvider.test"`
Expected: PASS

### Step 5: Run all frontend tests

Run: `npm test`
Expected: All tests PASS

### Step 6: Run prettier

Run: `npx prettier --write .`

### Step 7: Commit

```bash
git add src/providers/AuthProvider.tsx src/__tests__/providers/AuthProvider.test.tsx
git commit -m "feat(auth): add refresh token storage and proactive timer (#3)"
```

---

## Task 8: Deploy and run integration tests

**Dependencies:** Tasks 1-4 (user-service) and Tasks 5-7 (web-app) must be complete.

### Step 1: Deploy affected services

Run from the top-level repo:
```bash
./scripts/deploy.sh user-service web-app
```
Expected: Both services rebuild, deploy, and pass health checks.

### Step 2: Un-skip integration tests

In `AcctAtlas-integration-tests/api/tests/user-service.spec.ts`, change the three `test.skip(` calls in the "Token Refresh" describe block (lines 160, 194, 206) to `test(` (removing `test.skip`).

### Step 3: Run integration tests

```bash
cd AcctAtlas-integration-tests
npm run test:all
```
Expected: All tests PASS, including the three newly un-skipped token refresh tests.

### Step 4: Commit integration test changes

```bash
cd AcctAtlas-integration-tests
git add api/tests/user-service.spec.ts
git commit -m "test(auth): enable token refresh integration tests"
```

---

## Task 9: Create PRs

Create PRs in this order. Do NOT create the integration-tests PR until the service PRs are merged.

### Step 1: user-service PR

```bash
cd AcctAtlas-user-service
git push -u origin <branch-name>
gh pr create --title "feat(auth): implement token refresh endpoint" --body "$(cat <<'EOF'
## Summary
- Implements `POST /auth/refresh` endpoint (was returning 501)
- Adds `AuthenticationService.refresh()` with token rotation
- Adds `InvalidRefreshTokenException` with proper 401 error codes
- Fixes `expiresIn` to derive from config instead of hardcoded 900

Closes #22

## Test plan
- [ ] Unit tests for `AuthenticationService.refresh()` (valid, invalid, rotation)
- [ ] Controller tests for 200/401 responses
- [ ] Integration test: register → refresh → verify new tokens → verify old token invalidated
- [ ] `./gradlew check` passes

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### Step 2: web-app PR

```bash
cd AcctAtlas-web-app
git push -u origin <branch-name>
gh pr create --title "feat(auth): add token refresh handling" --body "$(cat <<'EOF'
## Summary
- Stores refresh token in sessionStorage alongside access token
- Adds proactive refresh timer (fires at 80% of token lifetime)
- Adds axios 401 interceptor with request queue as fallback
- Adds `refreshTokens()` API function
- Silent redirect to login on refresh failure

Closes #3

## Test plan
- [ ] Unit tests for `refreshTokens` API function
- [ ] Unit tests for 401 interceptor exports
- [ ] Unit tests for AuthProvider: stores refresh token, registers callbacks, clears on logout
- [ ] `npm test` passes
- [ ] Manual test: login → wait 15+ min → verify still logged in

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### Step 3: integration-tests PR (after service PRs are merged)

```bash
cd AcctAtlas-integration-tests
git push -u origin <branch-name>
gh pr create --title "test(auth): enable token refresh integration tests" --body "$(cat <<'EOF'
## Summary
- Un-skips the three token refresh tests that were waiting on user-service #22
- Tests: valid refresh, invalid token rejection, token reuse detection

## Test plan
- [ ] `npm run test:all` passes

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
