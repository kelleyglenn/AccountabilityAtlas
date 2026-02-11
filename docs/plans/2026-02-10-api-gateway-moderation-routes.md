# api-gateway Moderation Service Routes

> **Quick Config Change** - No implementation plan needed, just a configuration update.

**Goal:** Add routes for moderation-service endpoints to api-gateway.

**Estimated effort:** 5 minutes

---

## Current Routes

```yaml
routes:
  - id: user-service-auth
    uri: ${USER_SERVICE_URL:http://localhost:8081}
    predicates:
      - Path=/api/v1/auth/**
    filters:
      - RewritePath=/api/v1/(?<segment>.*), /${segment}
  - id: user-service-users
    uri: ${USER_SERVICE_URL:http://localhost:8081}
    predicates:
      - Path=/api/v1/users/**
    filters:
      - RewritePath=/api/v1/(?<segment>.*), /${segment}
```

---

## Routes to Add

Add to `AcctAtlas-api-gateway/src/main/resources/application.yml`:

```yaml
        - id: moderation-service
          uri: ${MODERATION_SERVICE_URL:http://localhost:8085}
          predicates:
            - Path=/api/v1/moderation/**
          filters:
            - RewritePath=/api/v1/(?<segment>.*), /${segment}
```

---

## Full Updated Routes Section

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: user-service-auth
          uri: ${USER_SERVICE_URL:http://localhost:8081}
          predicates:
            - Path=/api/v1/auth/**
          filters:
            - RewritePath=/api/v1/(?<segment>.*), /${segment}
        - id: user-service-users
          uri: ${USER_SERVICE_URL:http://localhost:8081}
          predicates:
            - Path=/api/v1/users/**
          filters:
            - RewritePath=/api/v1/(?<segment>.*), /${segment}
        - id: moderation-service
          uri: ${MODERATION_SERVICE_URL:http://localhost:8085}
          predicates:
            - Path=/api/v1/moderation/**
          filters:
            - RewritePath=/api/v1/(?<segment>.*), /${segment}
```

---

## Environment Variables

For Docker/production, add:

| Variable | Default | Description |
|----------|---------|-------------|
| MODERATION_SERVICE_URL | http://localhost:8085 | moderation-service base URL |

---

## Testing

After adding the route:

```bash
# Start moderation-service
cd AcctAtlas-moderation-service && ./gradlew bootRun

# Start api-gateway
cd AcctAtlas-api-gateway && ./gradlew bootRun

# Test route (should proxy to moderation-service)
curl http://localhost:8080/api/v1/moderation/queue \
  -H "Authorization: Bearer <token>"
```

---

## Commit

```bash
cd AcctAtlas-api-gateway
git add src/main/resources/application.yml
git commit -m "feat: add moderation-service routes"
```
