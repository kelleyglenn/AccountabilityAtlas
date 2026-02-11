# user-service Moderation Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the missing endpoints that moderation-service requires for trust tier management and user profile lookups.

**Architecture:** The API spec already defines the endpoints; we need to implement the controller methods and add a service method for trust tier updates.

**Tech Stack:** Java 21, Spring Boot 3.4.x, PostgreSQL

**Related Issue:** Create issue in AcctAtlas-user-service before starting

---

## Current State

### Already Exists
- `User` entity with `trustTier` field (TrustTier enum: NEW, TRUSTED, MODERATOR, ADMIN)
- `UserStats` entity with `submissionCount`, `approvedCount`, `rejectedCount`
- API spec defines `GET /users/{id}` returning `UserPublicProfile`
- API spec defines `PUT /users/{id}/trust-tier` accepting `UpdateTrustTierRequest`
- OpenAPI-generated models: `UserPublicProfile`, `UserPublicStats`, `UpdateTrustTierRequest`

### Missing Implementation
- `UsersController.getUserById()` returns NOT_IMPLEMENTED
- `UsersController.updateUserTrustTier()` not implemented (no method exists)
- `UserService` has no method for updating trust tier

---

## Phase 1: Implement GET /users/{id}

### Task 1: Add UserService.getUserPublicProfile method

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/userservice/service/UserService.java`
- Create: `src/test/java/com/accountabilityatlas/userservice/service/UserServiceTest.java`

**Step 1: Write the failing test**

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {

  @Mock private UserRepository userRepository;
  private UserService userService;

  @BeforeEach
  void setUp() {
    userService = new UserService(userRepository);
  }

  @Test
  void getUserById_existingUser_returnsUser() {
    // Arrange
    UUID id = UUID.randomUUID();
    User user = new User();
    user.setId(id);
    user.setDisplayName("TestUser");
    when(userRepository.findById(id)).thenReturn(Optional.of(user));

    // Act
    User result = userService.getUserById(id);

    // Assert
    assertThat(result.getId()).isEqualTo(id);
  }

  @Test
  void getUserById_nonExistingUser_throwsException() {
    // Arrange
    UUID id = UUID.randomUUID();
    when(userRepository.findById(id)).thenReturn(Optional.empty());

    // Act & Assert
    assertThatThrownBy(() -> userService.getUserById(id))
        .isInstanceOf(UserNotFoundException.class);
  }
}
```

**Step 2: Verify test passes** (getUserById already exists)

**Step 3: Commit**

```bash
git commit -m "test: add UserService unit tests"
```

---

### Task 2: Implement UsersController.getUserById

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/userservice/web/UsersController.java`
- Create: `src/test/java/com/accountabilityatlas/userservice/web/UsersControllerTest.java`

**Step 1: Write controller test**

```java
@WebMvcTest(UsersController.class)
class UsersControllerTest {

  @Autowired private MockMvc mockMvc;
  @MockitoBean private UserService userService;

  @Test
  @WithMockUser
  void getUserById_existingUser_returnsPublicProfile() throws Exception {
    // Arrange
    UUID id = UUID.randomUUID();
    User user = createTestUser(id);
    when(userService.getUserById(id)).thenReturn(user);

    // Act & Assert
    mockMvc.perform(get("/users/{id}", id))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.id").value(id.toString()))
        .andExpect(jsonPath("$.displayName").value("TestUser"))
        .andExpect(jsonPath("$.trustTier").value("NEW"))
        .andExpect(jsonPath("$.stats.submissionCount").value(5))
        .andExpect(jsonPath("$.stats.approvedCount").value(3));
  }

  @Test
  @WithMockUser
  void getUserById_nonExistingUser_returns404() throws Exception {
    // Arrange
    UUID id = UUID.randomUUID();
    when(userService.getUserById(id)).thenThrow(new UserNotFoundException(id));

    // Act & Assert
    mockMvc.perform(get("/users/{id}", id))
        .andExpect(status().isNotFound());
  }

  private User createTestUser(UUID id) {
    User user = new User();
    user.setId(id);
    user.setDisplayName("TestUser");
    user.setTrustTier(TrustTier.NEW);
    UserStats stats = new UserStats();
    stats.setSubmissionCount(5);
    stats.setApprovedCount(3);
    user.setStats(stats);
    return user;
  }
}
```

**Step 2: Implement the controller method**

Replace the NOT_IMPLEMENTED return in `getUserById`:

```java
@Override
public ResponseEntity<UserPublicProfile> getUserById(UUID id) {
  User user = userService.getUserById(id);
  return ResponseEntity.ok(toPublicProfile(user));
}

private UserPublicProfile toPublicProfile(User user) {
  UserPublicProfile profile = new UserPublicProfile();
  profile.setId(user.getId());
  profile.setDisplayName(user.getDisplayName());
  if (user.getAvatarUrl() != null) {
    profile.setAvatarUrl(URI.create(user.getAvatarUrl()));
  }
  profile.setTrustTier(TrustTier.fromValue(user.getTrustTier().name()));
  if (user.getCreatedAt() != null) {
    profile.setCreatedAt(OffsetDateTime.ofInstant(user.getCreatedAt(), ZoneOffset.UTC));
  }

  if (user.getStats() != null) {
    UserPublicStats stats = new UserPublicStats();
    stats.setSubmissionCount(user.getStats().getSubmissionCount());
    stats.setApprovedCount(user.getStats().getApprovedCount());
    profile.setStats(stats);
  }

  return profile;
}
```

**Step 3: Run tests**

```bash
./gradlew test
```

**Step 4: Commit**

```bash
git commit -m "feat: implement GET /users/{id} endpoint"
```

---

## Phase 2: Implement PUT /users/{id}/trust-tier

### Task 3: Add UserService.updateTrustTier method

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/userservice/service/UserService.java`
- Modify: `src/test/java/com/accountabilityatlas/userservice/service/UserServiceTest.java`

**Step 1: Write the failing test**

```java
@Test
void updateTrustTier_validTier_updatesTier() {
  // Arrange
  UUID id = UUID.randomUUID();
  User user = new User();
  user.setId(id);
  user.setTrustTier(TrustTier.NEW);
  when(userRepository.findById(id)).thenReturn(Optional.of(user));
  when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

  // Act
  User result = userService.updateTrustTier(id, TrustTier.TRUSTED, "AUTO_PROMOTION");

  // Assert
  assertThat(result.getTrustTier()).isEqualTo(TrustTier.TRUSTED);
  verify(userRepository).save(user);
}

@Test
void updateTrustTier_userNotFound_throwsException() {
  // Arrange
  UUID id = UUID.randomUUID();
  when(userRepository.findById(id)).thenReturn(Optional.empty());

  // Act & Assert
  assertThatThrownBy(() -> userService.updateTrustTier(id, TrustTier.TRUSTED, "reason"))
      .isInstanceOf(UserNotFoundException.class);
}
```

**Step 2: Implement the service method**

```java
@Transactional
public User updateTrustTier(UUID id, TrustTier newTier, String reason) {
  User user = getUserById(id);
  TrustTier oldTier = user.getTrustTier();
  user.setTrustTier(newTier);
  User saved = userRepository.save(user);

  // TODO: Publish UserTrustTierChanged event (Phase 2 - SQS integration)
  log.info("Updated user {} trust tier: {} -> {} (reason: {})", id, oldTier, newTier, reason);

  return saved;
}
```

**Step 3: Run tests and commit**

```bash
./gradlew test
git commit -m "feat: add UserService.updateTrustTier method"
```

---

### Task 4: Implement UsersController.updateUserTrustTier

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/userservice/web/UsersController.java`
- Modify: `src/test/java/com/accountabilityatlas/userservice/web/UsersControllerTest.java`
- Modify: `src/main/java/com/accountabilityatlas/userservice/config/SecurityConfig.java`

**Step 1: Add security configuration for admin-only endpoint**

The endpoint should only be accessible by ADMIN users. Update SecurityConfig:

```java
.requestMatchers(HttpMethod.PUT, "/users/*/trust-tier")
.hasRole("ADMIN")
```

**Step 2: Write controller test**

```java
@Test
@WithMockUser(roles = "ADMIN")
void updateTrustTier_asAdmin_updatesTier() throws Exception {
  // Arrange
  UUID id = UUID.randomUUID();
  User user = createTestUser(id);
  user.setTrustTier(TrustTier.TRUSTED);
  when(userService.updateTrustTier(eq(id), eq(TrustTier.TRUSTED), anyString()))
      .thenReturn(user);

  // Act & Assert
  mockMvc.perform(put("/users/{id}/trust-tier", id)
          .contentType(MediaType.APPLICATION_JSON)
          .content("""
              {"trustTier": "TRUSTED", "reason": "AUTO_PROMOTION"}
              """))
      .andExpect(status().isOk())
      .andExpect(jsonPath("$.trustTier").value("TRUSTED"));
}

@Test
@WithMockUser(roles = "MODERATOR")
void updateTrustTier_asModerator_returns403() throws Exception {
  // Arrange
  UUID id = UUID.randomUUID();

  // Act & Assert
  mockMvc.perform(put("/users/{id}/trust-tier", id)
          .contentType(MediaType.APPLICATION_JSON)
          .content("""
              {"trustTier": "TRUSTED", "reason": "test"}
              """))
      .andExpect(status().isForbidden());
}
```

**Step 3: Implement the controller method**

Add to UsersController (need to add the method since OpenAPI generates interface):

```java
@Override
public ResponseEntity<User> updateUserTrustTier(UUID id, UpdateTrustTierRequest request) {
  TrustTier newTier = TrustTier.valueOf(request.getTrustTier().getValue());
  User user = userService.updateTrustTier(id, newTier, request.getReason());
  return ResponseEntity.ok(toApiUser(user));
}
```

**Step 4: Run tests and commit**

```bash
./gradlew test
git commit -m "feat: implement PUT /users/{id}/trust-tier endpoint (admin only)"
```

---

## Phase 3: Event Publishing (Optional - for SQS integration later)

### Task 5: Create UserTrustTierChangedEvent

This task is optional and can be deferred until SQS integration in Phase 2.

**Files:**
- Create: `src/main/java/com/accountabilityatlas/userservice/event/UserTrustTierChangedEvent.java`
- Create: `src/main/java/com/accountabilityatlas/userservice/event/UserEventPublisher.java`

Event structure:
```java
public record UserTrustTierChangedEvent(
    UUID userId,
    String oldTier,
    String newTier,
    String reason,
    Instant timestamp
) {}
```

---

## Summary

| Task | Description | Complexity |
|------|-------------|------------|
| 1 | Add UserService tests | Low |
| 2 | Implement GET /users/{id} | Medium |
| 3 | Add UserService.updateTrustTier | Low |
| 4 | Implement PUT /users/{id}/trust-tier | Medium |
| 5 | Event publishing (optional) | Low |

**Estimated effort:** 2-3 hours

---

## Testing Checklist

- [ ] GET /users/{id} returns UserPublicProfile with stats
- [ ] GET /users/{id} returns 404 for non-existent user
- [ ] PUT /users/{id}/trust-tier updates trust tier (admin only)
- [ ] PUT /users/{id}/trust-tier returns 403 for non-admin
- [ ] All existing tests still pass
