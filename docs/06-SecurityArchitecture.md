# Security Architecture

## Security Principles

1. **Defense in Depth**: Multiple layers of security controls
2. **Least Privilege**: Minimum necessary access at every layer
3. **Zero Trust**: Verify every request, assume breach
4. **Secure by Default**: Security controls enabled without configuration

---

## Authentication

### Authentication Flow

```
┌──────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Client  │────▶│ API Gateway │────▶│ User Service │────▶│  PostgreSQL │
└──────────┘     └─────────────┘     └──────────────┘     └─────────────┘
     │                 │                    │
     │                 │                    ▼
     │                 │           ┌──────────────┐
     │                 │           │    Redis     │
     │                 │           │  (Sessions)  │
     │                 │           └──────────────┘
     │                 │
     │    JWT Token    │
     ◀─────────────────┘
```

### JWT Token Structure

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "user-uuid",
    "email": "user@example.com",
    "trustTier": "TRUSTED",
    "sessionId": "session-uuid",
    "iat": 1704067200,
    "exp": 1704068100
  }
}
```

### Token Lifecycle

| Token Type | Lifetime | Storage | Refresh |
|------------|----------|---------|---------|
| Access Token | 15 minutes | Client memory | Via refresh token |
| Refresh Token | 7 days | HTTP-only cookie | Rotation on use |
| Password Reset | 1 hour | Not stored (hash in DB) | One-time use |

### Password Requirements

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- Password checked against common breach databases (HaveIBeenPwned API)
- BCrypt hashing with cost factor 12

### OAuth 2.0 Integration

| Provider | Scopes | Data Retrieved |
|----------|--------|----------------|
| Google | `openid email profile` | Email, name, avatar |
| Apple | `name email` | Email, name |

OAuth flow uses PKCE (Proof Key for Code Exchange) for additional security.

---

## Authorization

### Role-Based Access Control (RBAC)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                             PERMISSION MATRIX                                 │
├───────────────────┬───────┬──────────┬──────────┬────────────┬───────────────┤
│ Action            │ Guest │ New      │ Trusted  │ Moderator  │ Admin         │
├───────────────────┼───────┼──────────┼──────────┼────────────┼───────────────┤
│ View videos       │ ✓     │ ✓        │ ✓        │ ✓          │ ✓             │
│ View map          │ ✓     │ ✓        │ ✓        │ ✓          │ ✓             │
│ Search            │ ✓     │ ✓        │ ✓        │ ✓          │ ✓             │
│ Submit video *    │ ✗     │ ✓        │ ✓        │ ✓          │ ✓             │
│ Edit own video    │ ✗     │ ✓        │ ✓        │ ✓          │ ✓             │
│ Delete own video  │ ✗     │ ✓        │ ✓        │ ✓          │ ✓             │
│ Report content    │ ✗     │ ✓        │ ✓        │ ✓          │ ✓             │
│ View mod queue    │ ✗     │ ✗        │ ✗        │ ✓          │ ✓             │
│ Approve/reject    │ ✗     │ ✗        │ ✗        │ ✓          │ ✓             │
│ Edit any video    │ ✗     │ ✗        │ ✗        │ ✓          │ ✓             │
│ Delete any video  │ ✗     │ ✗        │ ✗        │ ✓          │ ✓             │
│ Manage users      │ ✗     │ ✗        │ ✗        │ ✗          │ ✓             │
│ Promote to mod    │ ✗     │ ✗        │ ✗        │ ✗          │ ✓             │
│ System config     │ ✗     │ ✗        │ ✗        │ ✗          │ ✓             │
└───────────────────┴───────┴──────────┴──────────┴────────────┴───────────────┘

* New user submissions require moderation approval. Trusted users publish directly.
```

### Trust Tiers

| Tier | Requirements | Privileges |
|------|--------------|------------|
| NEW | Default for new users | Submissions require moderation |
| TRUSTED | 10+ approved, 30+ days, no recent rejections | Direct publishing |
| MODERATOR | Manual promotion by admin | Content moderation |
| ADMIN | Manual designation | Full system access |

### Resource Ownership

Users can only modify resources they own:
- Edit/delete their own video submissions
- Manage their own profile
- View their own submission history

Moderators and Admins can override ownership restrictions.

---

## API Security

### Rate Limiting

| Tier | Submissions/Day | Searches/Min | API Calls/Min |
|------|-----------------|--------------|---------------|
| Anonymous | 0 | 10 | 30 |
| NEW | 5 | 30 | 60 |
| TRUSTED | 50 | 60 | 120 |
| MODERATOR | Unlimited | 120 | 300 |
| ADMIN | Unlimited | Unlimited | Unlimited |

Rate limiting implemented at API Gateway using Redis token bucket algorithm.

### Input Validation

All inputs validated at multiple layers:

1. **API Gateway**: Request size limits, content-type validation
2. **Controller Layer**: DTO validation with Jakarta Bean Validation
3. **Service Layer**: Business rule validation
4. **Database Layer**: Constraint validation

### Content Security

| Threat | Mitigation |
|--------|------------|
| XSS | HTML sanitization, CSP headers, output encoding |
| SQL Injection | Parameterized queries (JPA/Hibernate) |
| CSRF | SameSite cookies, CSRF tokens for mutations |
| SSRF | URL allowlist for YouTube/Google domains only |
| Path Traversal | Input sanitization, no file system access |

### YouTube URL Validation

Only accept URLs matching:
- `youtube.com/watch?v={id}`
- `youtu.be/{id}`
- `youtube.com/embed/{id}`

Validate video exists via YouTube Data API before accepting.

---

## Infrastructure Security

> **Note**: The network architecture, security groups, and WAF rules below describe the **Phase 3-4 target state**. Phase 1 uses a simplified setup (EC2 in a public subnet with nginx rate limiting). Phase 2 introduces ALB and private subnets. See [07-InfrastructureArchitecture.md](07-InfrastructureArchitecture.md) for the current phase and migration path.

### Network Architecture (Phase 3-4)

```
┌─────────────────────────────────────────────────────────────────┐
│                           INTERNET                               │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                        ┌─────▼─────┐
                        │    WAF    │
                        │ (AWS WAF) │
                        └─────┬─────┘
                              │
                        ┌─────▼─────┐
                        │    ALB    │
                        │  (HTTPS)  │
                        └─────┬─────┘
                              │
┌─────────────────────────────┼───────────────────────────────────┐
│                     VPC (10.0.0.0/16)                            │
│  ┌──────────────────────────┼─────────────────────────────────┐ │
│  │           PUBLIC SUBNETS (10.0.1.0/24, 10.0.2.0/24)        │ │
│  │                          │                                  │ │
│  │                    ┌─────▼─────┐                           │ │
│  │                    │    NAT    │                           │ │
│  │                    │  Gateway  │                           │ │
│  │                    └─────┬─────┘                           │ │
│  └──────────────────────────┼─────────────────────────────────┘ │
│                              │                                   │
│  ┌──────────────────────────┼─────────────────────────────────┐ │
│  │          PRIVATE SUBNETS (10.0.10.0/24, 10.0.11.0/24)      │ │
│  │                          │                                  │ │
│  │     ┌────────────────────┼────────────────────┐            │ │
│  │     ▼                    ▼                    ▼            │ │
│  │ ┌────────┐         ┌──────────┐         ┌──────────┐       │ │
│  │ │  ECS   │         │   ECS    │         │   ECS    │       │ │
│  │ │Services│         │ Services │         │ Services │       │ │
│  │ └────────┘         └──────────┘         └──────────┘       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌──────────────────────────┼─────────────────────────────────┐ │
│  │          DATA SUBNETS (10.0.20.0/24, 10.0.21.0/24)         │ │
│  │                          │                                  │ │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐             │ │
│  │  │PostgreSQL│    │  Redis   │    │OpenSearch│             │ │
│  │  │   RDS    │    │ElastiCache    │  Domain  │             │ │
│  │  └──────────┘    └──────────┘    └──────────┘             │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Security Groups (Phase 3-4)

| Component | Inbound | Outbound |
|-----------|---------|----------|
| ALB | 443 from Internet | All to ECS |
| ECS Services | 8080-8086 from ALB | All to VPC |
| PostgreSQL | 5432 from ECS SG | None |
| Redis | 6379 from ECS SG | None |
| OpenSearch | 443 from ECS SG | None |

### AWS WAF Rules (Phase 3+)

1. **Rate Limiting**: Block IPs exceeding 2000 requests/5 minutes
2. **SQL Injection**: AWS managed SQLi rule set
3. **XSS Protection**: AWS managed XSS rule set
4. **Known Bad Inputs**: AWS managed Known Bad Inputs rule set
5. **Geo Blocking**: Optional, if required

---

## Secrets Management

### AWS Secrets Manager

| Secret | Rotation | Usage |
|--------|----------|-------|
| `db/postgres/master` | 30 days | RDS master credentials |
| `db/postgres/app` | 30 days | Application DB user |
| `jwt/signing-key` | 90 days | JWT RS256 private key |
| `oauth/google` | Manual | Google OAuth credentials |
| `oauth/apple` | Manual | Apple OAuth credentials |
| `youtube/api-key` | Manual | YouTube Data API key |
| `email/ses` | N/A | SES uses IAM roles |

### Key Rotation

- JWT signing keys support rotation with `kid` header
- Old keys valid for 24 hours after rotation
- Applications reload keys every 5 minutes from Secrets Manager

---

## Logging and Audit

### Security Events Logged

| Event | Log Level | Contains |
|-------|-----------|----------|
| Login success | INFO | User ID, IP, device |
| Login failure | WARN | Email (masked), IP, reason |
| Password reset request | INFO | User ID (if exists) |
| Permission denied | WARN | User ID, resource, action |
| Rate limit exceeded | WARN | User/IP, endpoint |
| JWT validation failure | WARN | Reason, token fragment |
| Moderation action | INFO | Moderator ID, content ID, action |
| Trust tier change | INFO | User ID, old tier, new tier, changed by |

### Log Retention

| Log Type | Retention | Storage |
|----------|-----------|---------|
| Application logs | 30 days | CloudWatch Logs |
| Security events | 1 year | CloudWatch Logs + S3 |
| WAF logs | 90 days | S3 |
| Audit trail | 2 years | PostgreSQL + S3 export |

### Alerting

Alerting channels scale with deployment phase. Phases 1-2 use email-based CloudWatch alarms. Phase 3+ adds SMS for critical alerts. PagerDuty and Slack are recommended when the team and user base grow significantly (see [07-InfrastructureArchitecture.md](07-InfrastructureArchitecture.md#monitoring-and-observability)).

| Alert | Threshold | Phase 1-2 Channel | Phase 3+ Channel |
|-------|-----------|-------------------|-------------------|
| Failed logins spike | > 100/minute | Email | PagerDuty |
| Rate limit triggers spike | > 500/minute | Email | Slack |
| WAF blocks spike | > 1000/hour | N/A (no WAF) | Slack |
| Authentication errors | > 10/minute | Email | Slack |
| Database auth failures | Any | Email | PagerDuty |

---

## Incident Response

### Security Incident Playbooks

1. **Account Compromise**
   - Revoke all sessions for user
   - Force password reset
   - Notify user via backup email/SMS
   - Review recent activity

2. **API Key Exposure**
   - Rotate exposed key immediately
   - Audit usage during exposure window
   - Update all service configurations

3. **Data Breach**
   - Isolate affected systems
   - Engage incident response team
   - Preserve evidence
   - Notify affected users (if applicable)
   - Report to authorities (if required)

### Contact

- Security email: security@accountabilityatlas.com
- Bug bounty: (future consideration)
