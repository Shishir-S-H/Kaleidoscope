# Backend & Frontend — Required Changes

This document lists all actionable items identified for the **backend** (Spring Boot) and **frontend** (Next.js) codebases during the AI services audit. These items are NOT implemented in the AI services repository — they must be addressed by the backend and frontend teams respectively.

---

## Backend Changes (15 items)

| Priority | Item | File(s) | Description |
|----------|------|---------|-------------|
| P0 | Rate limiting on auth endpoints | `SecurityConfig.java`, `pom.xml` | Add Spring Security rate limiter or bucket4j with Redis backend on `/api/auth/login`, `/api/auth/register`, `/api/auth/forgot-password` |
| P0 | Fix email verification token | `UserRegistrationServiceImpl.java` | Replace 10-char UUID substring with `SecureRandom` 32-byte base64 token |
| P0 | Fix MediaAssetTracker race condition | `PostServiceImpl.java:154-164` | Add `@Version` field for optimistic locking or use `SELECT FOR UPDATE` |
| P0 | Add test coverage | `backend/src/test/` | Unit tests for auth flows, post creation, Redis consumers, ES sync; integration tests for full pipeline |
| P1 | Add circuit breakers | All consumers/producers | Add Resilience4j dependency; wrap Redis and ES calls with `@CircuitBreaker` |
| P1 | Add backend DLQ handling | All consumer classes | On repeated failures (>3 redeliveries), move message to a DLQ stream instead of leaving in PEL |
| P1 | Standardize consumer exception handling | `MediaAiInsightsConsumer`, `FaceDetectionConsumer`, etc. | Define consistent policy: rethrow = no XACK (retry), catch+log = XACK (discard) |
| P1 | Split PostServiceImpl | `PostServiceImpl.java` (658+ lines) | Extract into `PostCreationService`, `PostUpdateService`, `PostQueryService` |
| P1 | Add error boundaries | Frontend: all route layouts | Wrap route groups in React error boundaries |
| P2 | Remove commented-out code | `Post.java:93-99,132-135` | Delete commented UserTag blocks, use git history |
| P2 | Extract magic numbers to config | Multiple files | Move batch sizes, timeouts, thresholds to `application.yml` properties |
| P2 | Fix @Transactional annotation | `ElasticsearchStartupSyncService.java` | Remove `readOnly=true` from method that writes to ES, or split read/write |
| P2 | Add custom health indicators | Backend actuator config | Add `HealthIndicator` beans for Redis, Elasticsearch, Cloudinary connectivity |
| P2 | Add Micrometer metrics | Backend async package | Add `@Timed` annotations and custom counters for stream processing and ES queries |
| P3 | Add OpenAPI annotations | All controllers | Add `@Operation`, `@ApiResponse` to undocumented endpoints |

---

## Frontend Changes (10 items)

| Priority | Item | File(s) | Description |
|----------|------|---------|-------------|
| P1 | Remove debug console.log | `EnhancedBodyInput.tsx`, `filterPosts.ts`, multiple controllers | Remove or replace with proper logger |
| P1 | Fix `any` types | `updateUserPreferences.ts:44`, `input.tsx:20` | Replace with `unknown` + type guards or specific error types |
| P1 | Update root metadata | `app/layout.tsx` | Change title from "Create Next App" to "Kaleidoscope", update description |
| P1 | Add React error boundaries | All route layouts in `app/(auth)/layout.tsx`, `app/(unauth)/layout.tsx` | Wrap children in error boundary component with fallback UI |
| P1 | Implement missing TODOs | `MediaUpload.tsx:131,144` | Create `deleteMediaController` and implement server-side Cloudinary deletion |
| P2 | Move tokens to HTTP-only cookies | `src/store/authSlice`, axios interceptor | Stop persisting access token to localStorage via Redux; rely on HTTP-only cookie refresh flow |
| P2 | Standardize error handling | All controllers/services | Pick one pattern (return error objects vs throw) and apply consistently |
| P2 | Add loading/error states | `SearchAndCreate.tsx`, form submissions | Add skeleton loaders, error messages, empty states |
| P3 | Accessibility improvements | Modal components, buttons | Add focus trapping, keyboard navigation, missing aria labels |
| P3 | Add i18n framework | Throughout frontend | Add `next-intl` or similar; extract hardcoded strings |

---

## Notes

- **Priority definitions**: P0 = security/data-integrity (fix before production), P1 = reliability/maintainability, P2 = code quality, P3 = enhancement.
- The AI services repository has already addressed its own actionable items. This document is a handoff for the backend and frontend teams.
- For questions about how changes interact with the AI pipeline (Redis Streams, Elasticsearch, read models), consult the AI services documentation or the team.
