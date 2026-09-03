# IMP Backend — API Documentation

## 1. Environment

| | |
|---|---|
| Base URL | `https://impb.kreatech.org/` |
| Swagger UI | `https://impb.kreatech.org/api-docs/` |
| OpenAPI schema | `https://impb.kreatech.org/schema/` |
| Django admin | `https://impb.kreatech.org/admin/` |
| Media | `https://impb.kreatech.org/media/...` |

## 2. Credentials (staging)

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `8ob1Mm7SlimFN605e3ZQ` |

## 3. Changelog

**Current version: 1.5** — 2026-09-03

| Version | Date | Changes |
|---|---|---|
| 1.5 | 2026-09-03 | **Added**: `GET /front-view/influencer/leaderboard/` and `GET /front-view/influencer/rank/{phone_number}/` (§20a, §20b) — server-side proxies to a third-party influencer-marketing platform (`staging-api.kinggroup44.com`), gated with our own `IsAdmin` instead of exposing the upstream's access_code to clients. |
| 1.4 | 2026-09-03 | **Added**: flat cross-job/cross-org pending applications, `GET /jobs/applications/pending/` and `GET /jobs/applications/pending/{uuid}/` (§16a) — every `status=1` APPLIED member-job across every job/org, paginated, each row carrying its own `job_uuid` and `org_uuid`; alongside the existing job-scoped `/jobs/org/{org_uuid}/job/{job_uuid}/member/` (§16) which is unchanged. Added `org_uuid` field to the `MemberJob` object (§16) — was previously only `org` (name). |
| 1.3 | 2026-09-03 | **Added**: flat cross-org job list, `GET /jobs/list/` and `GET /jobs/list/{uuid}/` (§12a) — lists jobs across every org without requiring the org uuid in the path, alongside the existing org-scoped `/jobs/org/{org_uuid}/job/` (§12) which is unchanged. Also enabled `CORS_ALLOW_ALL_ORIGINS` (env-driven) on staging. |
| 1.2 | 2026-09-03 | Full rewrite against the current codebase — previous doc described a stale route layout (`/jobs/companies/`, `/jobs/postings/`, `/front-view/content/`) that no longer exists. **Org/Job routes renamed**: `/jobs/companies/` → `/jobs/org/`, `/jobs/postings/` → `/jobs/org/{org_uuid}/job/`, requirements/frames nested under it accordingly. **Added**: Frame Library API (`/frame/library/`, `/frame/job/{job_uuid}/`) — create/edit/archive a frame from anywhere, not just from inside its job. **Removed**: `/front-view/content/` (member-facing content aggregator) no longer exists in code; members read banners/guides/terms straight off the same admin routes (all of which only require `IsAuthenticated`, not `IsAdmin`) plus the dedicated `public`/`public/{category}` actions. Documented permission class (`IsAdmin` / `IsMember` / `IsAuthenticated`) per section — this was missing before and matters because several "admin" routes are actually only `IsAuthenticated`, see §0 Known issues. Fixed a bug where creating a frame at `/jobs/org/{org}/job/{job}/frames/` always 500'd. |
| 1.1 | 2026-09-02 | Added CMS dashboard KPI. Submissions: added `pending/` / `approved/` / `rejected/` shortcuts and `from_date` / `to_date` / `search` filters. Removed `GET /members/profile/audit-log/` (login history is no longer exposed via API). (Internally the `admins` Django app was renamed to `crmadmin` — no API path changed.) 85 endpoints. |
| 1.0 | 2026-08-31 | Initial release. Covers auth, admin users, activity log, members, companies, jobs, job requirements, frames, submissions, member job applications, job settings, payouts, earnings statistics, KPI, banners, guides, terms, member profile, bank details, platform accounts, job board, tasks, earnings, missed and app content. 82 endpoints. |

## 0. Known issues (as of 1.2, verified by live testing)

These are real, currently-open bugs, listed so API consumers know what to defend against. Not aspirational — everything else in this document describes actually-verified behavior.

1. **Broken object-level authorization (IDOR) on every `/members/{member_uuid}/...` member-facing route.** `MemberJobViewSet`, `AvailableJobViewSet` (+ `apply`), `MemberTaskViewSet` (tasks/submit/content/result), `MemberFrameViewSet`, `EarningsView`, `MissedView`, `MemberPayoutViewSet` only check `IsAuthenticated` — none verify the JWT's own member matches the `{member_uuid}` in the path. Any logged-in member can currently read or act on another member's tasks, earnings, payouts, job applications and frames by swapping the UUID. Do not treat `{member_uuid}` in the path as a security boundary until this is fixed.
2. **`/front-view/banners/public/`, `/front-view/guides/public/`, `/front-view/terms/public/{category}/` require a valid token**, despite being named/documented as pre-login routes. They inherit `IsAuthenticated` from their viewsets and currently return `401` with no `Authorization` header.
3. **Malformed UUID in a path segment 500s instead of 400/404** on any endpoint whose action does its own manual `.get(uuid=...)` lookup instead of using DRF's built-in object lookup — this is most custom `@action`s and `create`/`update` overrides across the codebase (Frame, Org, Job, JobRequirement, JobMember approve/reject/complete, Submission approve/reject, MemberTask submit/content/result, BankDetail, PlatformAccount, Payout, Banner, Guide, Terms, Admin). Plain `GET` list/retrieve routes are unaffected — DRF's own `get_object()` already 404s cleanly there.
4. **Frame Library (`/frame/library/`) is `IsAuthenticated`, not `IsAdmin`**, despite being described internally as the admin frame library — any logged-in member can currently create, edit or archive entries in the shared frame library.

## 4. Conventions

**Auth header**

```
Authorization: Bearer <access>
```

**Pagination** — every list endpoint unless noted otherwise.

Query: `page` (int, default 1), `page_size` (int, default 20, max 100).

```json
{ "count": 0, "next": null, "previous": null, "results": [] }
```

**Content type** — `application/json`, except endpoints marked *multipart*, which take `multipart/form-data`.

**Errors**

```json
{ "error": "Data submitted is invalid", "details": { "field": ["message"] } }
```

| Status | Body |
|---|---|
| 400 | `{"error": ..., "details": ...}` — `Invalid request` / `Data submitted is invalid` / `Data does not exist` / `Data already exists` / `Data archived` |
| 401 | `{"detail": "Authentication credentials were not provided."}` |
| 403 | `{"detail": "You do not have permission to perform this action."}` — wrong role for the endpoint |
| 403 | `{"error": "Incorrect login credentials", "details": {}}` — login endpoints only (deliberate: this project returns 403, not 401, for bad credentials) |
| 404 | `{"detail": "Not found."}` |
| 500 | See §0 Known issues #3 — a malformed (non-UUID) path segment on some routes leaks a stack trace instead of a clean 400. |

**Delete** — no working `DELETE` method anywhere except `/frame/library/{uuid}/`, where `DELETE` is wired to the same soft-delete `archive` logic. Everywhere else, soft delete is `PATCH .../archive/`, which returns the archived object.

**Dates** — `YYYY-MM-DD`. **Datetimes** — ISO 8601 with `+08:00`. **`period_key`** — `YYYY-MM-DD` (daily), `YYYY-Www` (weekly), `YYYY-MM` (monthly).

**Permission classes** — every section below states which of these gates it:

| Class | Meaning |
|---|---|
| `IsAdmin` | valid JWT **and** the user has a linked `Admin` row |
| `IsMember` | valid JWT **and** the user has a linked `Member` row |
| `IsAuthenticated` | any valid JWT, admin or member — **not** role-gated. See §0 #1 and #4 for where this is weaker than it should be. |

## 5. Choices

| Set | Values |
|---|---|
| Admin status | `1` ACTIVE, `2` INACTIVE |
| Member status | `1` ACTIVE, `2` INACTIVE, `3` SUSPENDED |
| Platform | `1` INSTAGRAM, `2` TIKTOK |
| Org (company) status | `1` ACTIVE, `2` INACTIVE |
| Job status | `1` DRAFT, `2` ACTIVE, `3` PAUSED, `4` COMPLETED |
| Job recurrence | `1` DAILY, `2` WEEKLY, `3` MONTHLY |
| Payment period | `1` DAILY, `2` WEEKLY, `3` MONTHLY |
| Content type | `1` REEL, `2` STORY, `3` POST, `4` VIDEO |
| Member job status | `1` APPLIED, `2` ACTIVE, `3` COMPLETED, `4` REJECTED |
| Affiliate link status | `1` PENDING, `2` SUBMITTED, `3` ACTIVE, `4` PAUSED |
| Member task status | `1` PENDING, `2` SUBMITTED, `3` APPROVED, `4` REJECTED, `5` MISSED |
| Task file media type | `1` VIDEO, `2` PHOTO |
| Frame aspect ratio | `1` 9:16, `2` 1:1, `3` 4:5 |
| Frame media type | `1` BOTH, `2` VIDEO, `3` PHOTO |
| Frame status | `1` ACTIVE, `2` INACTIVE |
| Payout status | `1` PENDING, `2` PAID |
| Banner location | `1` HOME BANNER, `2` EVENT BANNER, `3` POST OF THE DAY |
| Guide location | `1` HOME, `2` MISSION TODAY, `3` EARNING, `4` MISSED, `5` RULES, `6` LEADERBOARD, `7` JOB BOARD, `8` AFFILIATE LINKS, `9` PROFILE, `10` BANK DETAILS |
| Terms category | `1` EARNINGS, `2` LEADERBOARD, `3` JOB |
| Bank | `1` Maybank, `2` CIMB Bank, `3` Public Bank, `4` RHB Bank, `5` Hong Leong Bank, `6` Ambank, `7` Bank Islam Malaysia, `8` Bank Rakyat, `9` Affin Bank, `10` Alliance Bank, `11` UOB, `12` HSBC Bank, `13` Standard Chartered Bank, `14` OCBC Bank, `15` Citibank, `16` Agrobank, `17` Bank Muamalat, `18` BSN, `19` Big Pay, `20` Touch N Go, `21` GX Bank |

---

# AUTH

Shared by both roles. No auth required on any endpoint in this section.

### `/login/admin-access-token/` · `/login/member-access-token/`

**POST**

| Field | Type | Required | Notes |
|---|---|---|---|
| `username` | string | yes | |
| `password` | string | yes | |
| `ip_address` | string | no | member endpoint only — recorded on a `LoginAudit` row |
| `device` | string | no | member endpoint only |

**200** — admin: the Admin object + tokens. Member: the full member profile object (see §9 `GET /members/{uuid}/`) + tokens.

```json
{
  "uuid": "ad33c952-...",
  "username": "admin",
  "full_name": "Administrator",
  "status": 1,
  "profile_picture": null,
  "last_login": "2026-08-31T03:23:58+08:00",
  "created": "2026-08-31T03:21:14+08:00",
  "access": "eyJhbGci...",
  "refresh": "eyJhbGci...",
  "role": "ADMIN"
}
```

`role` is `ADMIN` or `MEMBER`. A member posting to the admin endpoint (or the reverse), or a wrong password → **403** `{"error": "Incorrect login credentials", "details": {}}`.

### `/login/refresh-token/`

**POST** — `{ "refresh": "<token>" }` → **200** `{ "access": "...", "refresh": "..." }`

### `/login/verify-token/`

**POST** — `{ "token": "<token>" }` → **200** `{}`

### `/login/logout/`

**POST** — `{ "refresh": "<token>" }` → **200** `{}` (blacklists the refresh token)

---

# ADMIN APIs

Everything below requires an **admin** token (`IsAdmin`) unless the section header says otherwise.

## 6. Admin users — `/admins/users/`

`IsAdmin`.

| Method | Path |
|---|---|
| GET | `/admins/users/` |
| POST | `/admins/users/` |
| GET | `/admins/users/{uuid}/` |
| PUT / PATCH | `/admins/users/{uuid}/` |
| PATCH | `/admins/users/{uuid}/resetpassword/` |
| PATCH | `/admins/users/{uuid}/archive/` |

**GET list query**: `username` (icontains), `status` (int, admin status), `page`, `page_size`.

**POST** *(multipart if `profile_picture`)*

| Field | Type | Required | Notes |
|---|---|---|---|
| `username` | string | yes | unique |
| `full_name` | string | yes | |
| `password` | string | yes | |
| `confirm_password` | string | yes | must equal `password` |
| `status` | int | no | admin status, default `1` |
| `profile_picture` | file | no | image |

**PUT / PATCH** — `full_name`, `status`, `profile_picture`; all optional.

**PATCH resetpassword** — `password` (string, required), `confirm_password` (string, required, must match).

**PATCH archive** — no body. Archives the admin and their user account.

**Response object**

```json
{
  "uuid": "uuid",
  "username": "string",
  "full_name": "string",
  "status": 1,
  "profile_picture": "url|null",
  "last_login": "datetime|null",
  "created": "datetime"
}
```

## 7. Activity log — `/admins/activity-log/`

`IsAdmin`. Read-only.

| Method | Path |
|---|---|
| GET | `/admins/activity-log/` |
| GET | `/admins/activity-log/{uuid}/` |

**Query**: `username` (icontains), `page`, `page_size`.

```json
{ "uuid": "uuid", "datetime": "datetime", "admin": "username", "activity": "string" }
```

## 8. Dashboard KPI — `/admins/dashboard/kpi/`

`IsAdmin`. The 4 tiles on the CMS dashboard.

| Method | Path |
|---|---|
| GET | `/admins/dashboard/kpi/` |

**Query**

| Param | Type | Required | Notes |
|---|---|---|---|
| `from_date` | date | yes | `YYYY-MM-DD` |
| `to_date` | date | yes | `YYYY-MM-DD`, must be ≥ `from_date` |

`total_influencers`, `active_campaigns` and `pending_submissions` are a live snapshot — **not** scoped to the date range. `approved_submissions` is the only tile scoped to `[from_date, to_date]`: submissions reviewed and approved in that window.

```json
{
  "total_influencers": 0,
  "active_campaigns": 0,
  "pending_submissions": 0,
  "approved_submissions": 0
}
```

## 9. Members — `/members/`

`IsAdmin`.

| Method | Path |
|---|---|
| GET | `/members/` |
| POST | `/members/` |
| GET | `/members/{uuid}/` |
| PUT / PATCH | `/members/{uuid}/` |
| PATCH | `/members/{uuid}/change-password/` |
| PATCH | `/members/{uuid}/archive/` |

**GET list query**: `search` (name / username / phone / email / bank account no. / account holder), `username`, `status` (int, member status), `from_date` + `to_date` (both required together, filters on `created`), `page`, `page_size`.

**POST** *(multipart if `profile_picture`)*

| Field | Type | Required | Notes |
|---|---|---|---|
| `username` | string | yes | unique |
| `password` | string | yes | |
| `confirm_password` | string | yes | must equal `password` |
| `full_name` | string | no | |
| `phone_number` | string | no | max 20, unique |
| `email` | email | no | unique |
| `date_of_birth` | date | no | |
| `status` | int | no | member status, default `1` |
| `joined` | date | no | |
| `profile_picture` | file | no | image |

**PUT / PATCH** — same fields minus `username` / `password` / `confirm_password`; all optional.

**PATCH change-password** — `password` (string, required). No current-password check; this is the admin reset.

**PATCH archive** — no body.

**Response object (list, create, update)**

```json
{
  "uuid": "uuid",
  "username": "string",
  "full_name": "string|null",
  "phone_number": "string|null",
  "email": "string|null",
  "date_of_birth": "date|null",
  "profile_picture": "url|null",
  "status": 1,
  "joined": "date|null",
  "last_login": "datetime|null",
  "created": "datetime"
}
```

**GET `/members/{uuid}/`** returns the same plus:

```json
{
  "bank_details": [
    { "uuid": "uuid", "bank": 2, "account_holder_name": "string",
      "account_number": "string", "is_primary": true }
  ],
  "platform_accounts": [
    { "uuid": "uuid", "platform": 2, "handle": "string",
      "profile_url": "url|null", "is_verified": false, "last_synced": "datetime|null" }
  ]
}
```

## 10. Member bank details (read-only, admin view) — `/members/{member_uuid}/bank-details/`

`IsAdmin`.

| Method | Path |
|---|---|
| GET | `/members/{member_uuid}/bank-details/` |
| GET | `/members/{member_uuid}/bank-details/{uuid}/` |

```json
{
  "uuid": "uuid", "bank": 2, "account_holder_name": "string",
  "account_number": "string", "is_primary": true,
  "member": "full name", "member_uuid": "uuid", "username": "string",
  "created": "datetime", "modified": "datetime"
}
```

## 10a. Member login audit (read-only, admin view) — `/members/{member_uuid}/audit_login/`

`IsAdmin`.

| Method | Path |
|---|---|
| GET | `/members/{member_uuid}/audit_login/` |
| GET | `/members/{member_uuid}/audit_login/{uuid}/` |

```json
{ "uuid": "uuid", "datetime": "datetime", "ip_address": "string|null", "device": "string|null" }
```

## 11. Orgs — `/jobs/org/`

`IsAdmin`. (Path segment is `org`, not `companies` — the underlying model is still called `Company` internally, but every URL and JSON field uses "org".)

| Method | Path |
|---|---|
| GET | `/jobs/org/` |
| POST | `/jobs/org/` |
| GET | `/jobs/org/{org_uuid}/` |
| PUT / PATCH | `/jobs/org/{org_uuid}/` |
| PATCH | `/jobs/org/{org_uuid}/archive/` |

**Query**: `name` (icontains), `status` (int, org status), `page`, `page_size`.

**POST / PUT / PATCH** *(multipart if `logo`)*

| Field | Type | Required (POST) | Notes |
|---|---|---|---|
| `name` | string | yes | unique |
| `status` | int | no | org status, default `1` |
| `telegram_link` | url | no | max 500 |
| `logo` | file | no | image |

All fields optional on PUT / PATCH.

```json
{
  "uuid": "uuid", "name": "string", "logo": "url|null",
  "telegram_link": "url|null", "status": 1,
  "total_jobs": 0, "created": "datetime"
}
```

## 12. Jobs — `/jobs/org/{org_uuid}/job/`

`IsAdmin`. Every job hangs off one org, so the org uuid is in the path, not the body.

| Method | Path |
|---|---|
| GET | `/jobs/org/{org_uuid}/job/` |
| POST | `/jobs/org/{org_uuid}/job/` |
| GET | `/jobs/org/{org_uuid}/job/{uuid}/` |
| PUT / PATCH | `/jobs/org/{org_uuid}/job/{uuid}/` |
| PATCH | `/jobs/org/{org_uuid}/job/{uuid}/archive/` |

**Query**: `status` (int, job status), `title` (icontains), `page`, `page_size`.

**POST**

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | yes | |
| `description` | string | no | |
| `recurrence` | int | no | job recurrence, default `1` |
| `payment_amount` | decimal(12,2) | yes | ≥ 0 |
| `payment_period` | int | no | payment period, default `3` |
| `deduction_per_miss` | decimal(12,2) | no | ≥ 0; falls back to job settings when null |
| `start_date` | datetime | yes | |
| `end_date` | datetime | no | must be ≥ `start_date` |
| `status` | int | no | job status, default `1` |
| `requirements` | array | no | list of `{platform, content_type, quantity}` |

`requirements[]`: `platform` (int, required), `content_type` (int, required), `quantity` (int, ≥ 1, default `1`).

**PUT / PATCH** — same scalar fields, all optional. `requirements` is **not** accepted here; use the requirements endpoint (§13).

```json
{
  "uuid": "uuid",
  "org": "string", "org_uuid": "uuid", "org_logo": "url|null",
  "title": "string", "description": "string|null",
  "recurrence": 1, "payment_amount": "0.00", "payment_period": 3,
  "deduction_per_miss": "0.00|null",
  "start_date": "datetime", "end_date": "datetime|null",
  "status": 2, "is_live": true,
  "requirements": [
    { "uuid": "uuid", "platform": 1, "content_type": 1, "quantity": 1 }
  ],
  "created": "datetime"
}
```

`is_live` = status `2` **and** not archived **and** now is between `start_date` and `end_date`. Verified by live testing against a real job.

## 12a. Job list, all orgs — `/jobs/list/`

`IsAdmin`. Read-only. Same `Job` object and fields as §12, but flat — lists jobs across every org instead of requiring the org uuid in the path. Use this when you just need a job's `uuid` (and its `org_uuid`) without resolving the org first; use §12 when you're already scoped to one org.

| Method | Path |
|---|---|
| GET | `/jobs/list/` |
| GET | `/jobs/list/{uuid}/` |

**Query**: `org_uuid` (uuid, filter to one org), `status` (int, job status), `title` (icontains), `page`, `page_size`.

Response object identical to §12.

## 13. Job requirements — `/jobs/org/{org_uuid}/job/{job_uuid}/requirement/`

`IsAdmin`.

| Method | Path |
|---|---|
| GET | `/jobs/org/{org_uuid}/job/{job_uuid}/requirement/` |
| POST | `/jobs/org/{org_uuid}/job/{job_uuid}/requirement/` |
| GET | `/jobs/org/{org_uuid}/job/{job_uuid}/requirement/{uuid}/` |
| PUT / PATCH | `/jobs/org/{org_uuid}/job/{job_uuid}/requirement/{uuid}/` |
| PATCH | `/jobs/org/{org_uuid}/job/{job_uuid}/requirement/{uuid}/archive/` |

| Field | Type | Required (POST) | Notes |
|---|---|---|---|
| `platform` | int | yes | platform |
| `content_type` | int | yes | content type |
| `quantity` | int | no | ≥ 1, default `1` |

`platform` + `content_type` is unique per unarchived job → duplicate returns **400** `Data already exists`. Verified by live testing.

```json
{ "uuid": "uuid", "platform": 1, "content_type": 1, "quantity": 1 }
```

## 14. Frames on a job — `/jobs/org/{org_uuid}/job/{job_uuid}/frames/`

`IsAuthenticated` (not `IsAdmin` — any logged-in user, admin or member, can read/write here; see §0 #1 for why that matters combined with the member-facing routes).

| Method | Path |
|---|---|
| GET | `/jobs/org/{org_uuid}/job/{job_uuid}/frames/` |
| POST | `/jobs/org/{org_uuid}/job/{job_uuid}/frames/` |
| GET | `/jobs/org/{org_uuid}/job/{job_uuid}/frames/{uuid}/` |
| PUT / PATCH | `/jobs/org/{org_uuid}/job/{job_uuid}/frames/{uuid}/` |
| PATCH | `/jobs/org/{org_uuid}/job/{job_uuid}/frames/{uuid}/archive/` |

**Query**: `media_type` (int — matches that type **and** `1` BOTH), `status` (int, frame status), `page`, `page_size`.

**POST / PUT / PATCH** — *multipart*

| Field | Type | Required (POST) | Notes |
|---|---|---|---|
| `name` | string | yes | |
| `job_uuid` | uuid | yes on POST | must match the `{job_uuid}` already in the URL — the job comes from the path, this field is accepted but not otherwise used to look anything up on this route (it exists because the same request serializer is shared with the Frame Library API, §14a) |
| `image` | file | yes | PNG with an alpha channel; size-validated |
| `aspect_ratio` | int | no | frame aspect ratio, default `1` |
| `media_type` | int | no | frame media type, default `1` |
| `ordering` | int | no | ≥ 0, default `0` |
| `status` | int | no | frame status, default `1` |

All optional on PUT / PATCH (`job_uuid` included — if given on PUT/PATCH, it does not move the frame to another job on this route, unlike the Library API's PATCH). A non-transparent image returns **400**.

```json
{
  "uuid": "uuid", "job_uuid": "uuid", "job_title": "string", "org": "string",
  "name": "string", "image": "url",
  "aspect_ratio": 1, "media_type": 1, "ordering": 0,
  "status": 1, "is_live": true,
  "created": "datetime", "modified": "datetime"
}
```

**Fixed in 1.2**: POST to this route previously always returned **500** (`Frame() got unexpected keyword arguments: 'job_uuid'`) because `job_uuid` was passed straight into `Frame.objects.create()` without being removed first. Verified working (**201**) after the fix.

## 14a. Frame library (all jobs) — `/frame/library/`

`IsAuthenticated` — see §0 #4; this is currently reachable by members too, not just admins.

Same `Frame` model and object shape as §14, but not nested under a job path — you address a frame by its own uuid, and tell the API which job it belongs to via `job_uuid` in the body instead of the URL.

| Method | Path |
|---|---|
| GET | `/frame/library/` |
| POST | `/frame/library/` |
| GET | `/frame/library/{uuid}/` |
| PUT / PATCH | `/frame/library/{uuid}/` |
| DELETE | `/frame/library/{uuid}/` — soft delete, same as `archive` below |
| PATCH | `/frame/library/{uuid}/archive/` |

**Query**: `job_uuid` (uuid, filter to one job), `media_type` (int — matches that type **and** `1` BOTH), `status` (int, frame status), `page`, `page_size`.

**POST** *(multipart)*

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | |
| `job_uuid` | uuid | yes | must be an unarchived job; **404** `Job Id` if not found |
| `image` | file | yes | PNG with an alpha channel; size-validated |
| `aspect_ratio` | int | no | frame aspect ratio, default `1` |
| `media_type` | int | no | frame media type, default `1` |
| `ordering` | int | no | ≥ 0, default `0` |
| `status` | int | no | frame status, default `1` |

**PUT / PATCH** *(multipart)* — same fields, all optional. If `job_uuid` is given, the frame is moved to that job (must also be an unarchived job, else **404**).

```json
{
  "uuid": "uuid", "job_uuid": "uuid", "job_title": "string", "org": "string",
  "name": "string", "image": "url",
  "aspect_ratio": 1, "media_type": 1, "ordering": 0,
  "status": 1, "is_live": true,
  "created": "datetime", "modified": "datetime"
}
```

## 14b. Frames for one job (read-only) — `/frame/job/{job_uuid}/`

`IsAuthenticated`. Genuinely read-only — `POST` correctly returns **405**, unlike §14/§14a.

| Method | Path |
|---|---|
| GET | `/frame/job/{job_uuid}/` |
| GET | `/frame/job/{job_uuid}/{uuid}/` |

**Query**: `media_type` (int), `status` (int), `page`, `page_size`. Object as in §14.

## 15. Submissions — `/jobs/job/{job_uuid}/submission/`

`IsAdmin`.

| Method | Path |
|---|---|
| GET | `/jobs/job/{job_uuid}/submission/` |
| GET | `/jobs/job/{job_uuid}/submission/pending/` |
| GET | `/jobs/job/{job_uuid}/submission/approved/` |
| GET | `/jobs/job/{job_uuid}/submission/rejected/` |
| GET | `/jobs/job/{job_uuid}/submission/{uuid}/` |
| PATCH | `/jobs/job/{job_uuid}/submission/{uuid}/approve/` |
| PATCH | `/jobs/job/{job_uuid}/submission/{uuid}/reject/` |

`pending/`, `approved/`, `rejected/` are `/submission/` pre-filtered to `status = 2` / `3` / `4` respectively — every query param below still applies on them, `status` is just ignored there (fixed by the path).

**Query**

| Param | Notes |
|---|---|
| `status` | `1` pending (not submitted, period still open) · `2` awaiting review · `3` approved · `4` rejected · `5` missed (not submitted, period closed). Omitted → every submitted task. Ignored on `/pending/`, `/approved/`, `/rejected/`. |
| `member_uuid` | |
| `period_key` | exact |
| `from_date` / `to_date` | filters on `submitted_at`'s date; either may be given alone |
| `search` | fuzzy match on influencer full name, username, phone number |
| `page`, `page_size` | |

**PATCH approve** — no body. **400** if not submitted, or already reviewed.

**PATCH reject** — `reject_reason` (string, required). Same 400 rules.

**Response object** (also the task object used by every member task endpoint)

```json
{
  "uuid": "uuid",
  "member": "full name", "member_uuid": "uuid",
  "org": "string", "job_title": "string", "member_job_uuid": "uuid",
  "platform": 1, "content_type": 1, "quantity": 1,
  "period_key": "2026-08-31", "period_start": "date", "period_end": "date",
  "status": 2,
  "proof_link": "url|null", "proof_file": "url|null", "note": "string|null",
  "submitted_at": "datetime|null",
  "reviewed_at": "datetime|null", "is_approved": true, "reject_reason": "string|null",
  "files": [
    { "uuid": "uuid", "file": "url", "media_type": 1,
      "original_name": "string|null", "size": 0, "created": "datetime" }
  ],
  "views": 0, "likes": 0, "comments": 0, "shares": 0,
  "metrics_screenshot": "url|null", "metrics_submitted_at": "datetime|null",
  "has_result": false
}
```

## 16. Member job applications, admin side — `/jobs/org/{org_uuid}/job/{job_uuid}/member/`

`IsAdmin`. Who applied to this job, and the decision on each application.

| Method | Path |
|---|---|
| GET | `/jobs/org/{org_uuid}/job/{job_uuid}/member/` |
| GET | `/jobs/org/{org_uuid}/job/{job_uuid}/member/{uuid}/` |
| PATCH | `/jobs/org/{org_uuid}/job/{job_uuid}/member/{uuid}/` |
| PATCH | `/jobs/org/{org_uuid}/job/{job_uuid}/member/{uuid}/approve/` |
| PATCH | `/jobs/org/{org_uuid}/job/{job_uuid}/member/{uuid}/reject/` |
| PATCH | `/jobs/org/{org_uuid}/job/{job_uuid}/member/{uuid}/complete/` |

**Query**: `status` (int, member job status), `search` (name / username / phone), `page`, `page_size`.

**PATCH** *(body)* — the escape hatch: sets any field directly, no state guard.

| Field | Type | Required | Notes |
|---|---|---|---|
| `status` | int | no | member job status |
| `affiliate_link` | url | no | max 500 |
| `affiliate_link_status` | int | no | affiliate link status |

**PATCH approve** — `affiliate_link` (url, optional). **400** if already reviewed. Sets `status = 2`, `joined = today`; if a link is given, also `affiliate_link_status = 3`.

**PATCH reject** — no body. **400** if already reviewed. Sets `status = 4`.

**PATCH complete** — no body. **400** unless currently active (`status = 2`). Sets `status = 3`, `completed = today`.

```json
{
  "uuid": "uuid",
  "member": "full name", "member_uuid": "uuid", "username": "string",
  "org": "string", "org_uuid": "uuid", "org_logo": "url|null",
  "job_uuid": "uuid", "job_title": "string",
  "payment_amount": "0.00", "payment_period": 3, "recurrence": 1,
  "status": 2, "affiliate_link": "url|null", "affiliate_link_status": 1,
  "has_frames": true,
  "joined": "date|null", "completed": "date|null", "created": "datetime"
}
```

`has_frames` = the job has at least one active, unarchived frame. Verified by live testing (flips `true` the moment a frame is created on the job). `org_uuid` added in 1.4.

## 16a. Pending applications, all jobs — `/jobs/applications/pending/`

`IsAdmin`. Read-only. Same `MemberJob` object as §16, but flat — every application still in `status = 1` APPLIED, across every job and org, instead of one job at a time. Each row carries its own `job_uuid` and `org_uuid`. Use this when you just need the pending queue everywhere; use §16 when you're already scoped to one job.

| Method | Path |
|---|---|
| GET | `/jobs/applications/pending/` |
| GET | `/jobs/applications/pending/{uuid}/` |

**Query**: `org_uuid` (uuid, filter to one org), `job_uuid` (uuid, filter to one job), `search` (name / username / phone), `page`, `page_size`.

Response object identical to §16 (always `status: 1` here).

## 17. Job settings — `/jobs/settings/`

`IsAdmin`. Singleton, created on first GET.

| Method | Path |
|---|---|
| GET | `/jobs/settings/` |
| PATCH | `/jobs/settings/` |

| Field | Type | Required | Notes |
|---|---|---|---|
| `default_deduction_per_miss` | decimal(12,2) | no | ≥ 0 |
| `default_payment_period` | int | no | payment period |
| `submission_grace_hours` | int | no | ≥ 0; hours past a period's midnight a member may still submit |
| `requires_review` | bool | no | |
| `maintenance_mode` | bool | no | |

```json
{
  "uuid": "uuid",
  "default_deduction_per_miss": "0.00",
  "default_payment_period": 3,
  "submission_grace_hours": 0,
  "requires_review": true,
  "maintenance_mode": false
}
```

## 18. Payouts — `/earnings/payouts/`

`IsAdmin`. Note: despite being a `ReadOnlyModelViewSet`, `create`/`update` are real, reachable methods here — DRF wires routes by method presence, not base class, so POST/PUT/PATCH all work. Confirmed by live testing (POST → **201**, persisted).

| Method | Path |
|---|---|
| GET | `/earnings/payouts/` |
| POST | `/earnings/payouts/` |
| GET | `/earnings/payouts/{uuid}/` |
| PUT / PATCH | `/earnings/payouts/{uuid}/` |
| PATCH | `/earnings/payouts/{uuid}/mark-paid/` |
| PATCH | `/earnings/payouts/{uuid}/archive/` |

**Query**: `member_uuid`, `period_key`, `status` (`1` pending, `2` paid), `page`, `page_size`.

**POST**

| Field | Type | Required | Notes |
|---|---|---|---|
| `member_uuid` | uuid | yes | |
| `period_key` | string | yes | `YYYY-MM` |
| `amount` | decimal(12,2) | yes | ≥ 0 |
| `note` | string | no | |

One payout per member per `period_key` → duplicate returns **400** `Data already exists`.

**PUT / PATCH** — `amount`, `note`; both optional.

**PATCH mark-paid** — no body. **400** if already paid.

```json
{
  "uuid": "uuid", "member": "full name", "member_uuid": "uuid",
  "period_key": "2026-08", "amount": "0.00", "note": "string|null",
  "status": 1, "paid_at": "datetime|null", "created": "datetime"
}
```

## 19. Earnings statistics — `/earnings/statistics/`

`IsAdmin`.

**GET**

| Param | Type | Notes |
|---|---|---|
| `month` | string | `YYYY-MM`, default current month |
| `search` | string | name / username |
| `status` | int | member status |
| `sort` | string | `total`, `-total`, `missed`, `-missed`, `deduction`, `-deduction`, `name` |
| `min_total` | decimal | |
| `max_total` | decimal | |
| `page`, `page_size` | int | |

```json
{
  "summary": {
    "period_key": "2026-08", "from_date": "date", "to_date": "date",
    "member_count": 0, "earning_member_count": 0, "missed_member_count": 0,
    "base_pay": "0.00", "posted_count": 0, "missed_count": 0,
    "deduction": "0.00", "total": "0.00"
  },
  "count": 0, "next": null, "previous": null,
  "results": [
    {
      "member_uuid": "uuid", "full_name": "string", "username": "string",
      "phone_number": "string|null", "email": "string|null", "status": 1,
      "job_count": 0, "base_pay": "0.00", "posted_count": 0,
      "missed_count": 0, "deduction": "0.00", "total": "0.00"
    }
  ]
}
```

All aggregate math (base pay, deduction, total, per-member and summed) was verified by live testing against hand-computed expected values and matched exactly.

## 20. Earnings KPI — `/earnings/kpi/`

`IsAdmin`. No params. Current month, all members.

```json
{
  "member_count": 0, "earning_member_count": 0, "missed_member_count": 0,
  "base_pay": "0.00", "posted_count": 0, "missed_count": 0,
  "deduction": "0.00", "total": "0.00"
}
```

## 20a. Influencer leaderboard (third-party proxy) — `/front-view/influencer/leaderboard/`

`IsAdmin`. Server-side proxy to an external influencer-marketing platform's leaderboard API (`staging-api.kinggroup44.com`). The upstream endpoint is gated only by an `access_code` in its URL; this proxy keeps that code server-side (`INFLUENCER_API_BASE_URL` / `INFLUENCER_API_ACCESS_CODE` env vars) and gates our own callers with `IsAdmin` instead.

| Method | Path |
|---|---|
| GET | `/front-view/influencer/leaderboard/` |

No params. Returns the upstream response verbatim — top members ranked by total deposit amount for the current calendar month, with each member's referral stats (registrations and conversions of people they referred, same month). **Not paginated** — a bare array.

```json
[
  {
    "rank": 1,
    "member_uuid": "uuid",
    "full_name": "string",
    "phone_number": "string",
    "reg_count": 0,
    "cvs_count": 0,
    "deposit_amount": "0.00"
  }
]
```

`reg_count` — people this member referred who registered this month. `cvs_count` — of those, how many converted (made ≥1 deposit). `deposit_amount` — this member's own total deposit this month.

**502** `{"error": "Unable to contact third party"}` if the upstream is unreachable or errors.

## 20b. Influencer rank (third-party proxy) — `/front-view/influencer/rank/{phone_number}/`

`IsAdmin`. Same upstream platform as §20a, filtered to one member by phone number.

| Method | Path |
|---|---|
| GET | `/front-view/influencer/rank/{phone_number}/` |

```json
{
  "member_uuid": "uuid",
  "full_name": "string",
  "phone_number": "string",
  "rank": 1,
  "reg_count": 0,
  "cvs_count": 0,
  "deposit_amount": "0.00",
  "next_rank": 2,
  "next_rank_amount": "0.00"
}
```

`rank` — `null` if the member made no deposit this month (unranked). `next_rank` / `next_rank_amount` — the rank and deposit total directly above this member, i.e. what they need to beat to move up; both `null` if already rank 1, or if unranked.

**400** if the upstream returns 404 for an unknown phone number. **502** if the upstream is unreachable or errors.

## 21. Banners — `/front-view/banners/`

`IsAuthenticated` for everything except `public/`, which is documented as open but currently also requires auth — see §0 #2.

| Method | Path |
|---|---|
| GET | `/front-view/banners/` |
| GET | `/front-view/banners/public/` |
| POST | `/front-view/banners/` |
| GET | `/front-view/banners/{uuid}/` |
| PUT / PATCH | `/front-view/banners/{uuid}/` |
| PATCH | `/front-view/banners/{uuid}/archive/` |

**Query (list)**: `location` (int, banner location), `page`, `page_size`.

**`public/`** — live banners (`active_from`/`active_until` window contains now, unarchived) — bare array, **not paginated**. Same `location` query param.

**POST / PUT / PATCH** *(multipart if `image`)*

| Field | Type | Required (POST) | Notes |
|---|---|---|---|
| `name` | string | yes | |
| `image` | file | no | |
| `link` | url | no | |
| `location` | int | no | banner location, default `1` |
| `active_from` | datetime | no | |
| `active_until` | datetime | no | must be ≥ `active_from` |
| `ordering` | int | no | ≥ 0, default `0` |

```json
{
  "uuid": "uuid", "name": "string", "image": "url|null", "link": "url|null",
  "location": 1, "active_from": "datetime|null", "active_until": "datetime|null",
  "ordering": 0, "is_live": true, "created": "datetime"
}
```

## 22. Guides — `/front-view/guides/`

`IsAuthenticated` for everything, including `public/` — see §0 #2 (naming implies open access, code disagrees).

| Method | Path |
|---|---|
| GET | `/front-view/guides/` |
| GET | `/front-view/guides/public/` |
| POST | `/front-view/guides/` |
| GET | `/front-view/guides/{uuid}/` |
| PUT / PATCH | `/front-view/guides/{uuid}/` |
| PATCH | `/front-view/guides/{uuid}/archive/` |

**Query (list)**: `location` (int, guide location), `page`, `page_size`.

**`public/`** — bare array, **not paginated**. Same `location` query param.

| Field | Type | Required (POST) | Notes |
|---|---|---|---|
| `location` | int | yes | guide location |
| `title` | string | no | |
| `content` | html | yes | sanitised server-side |
| `ordering` | int | no | ≥ 0, default `0` |

```json
{ "uuid": "uuid", "location": 1, "title": "string|null",
  "content": "<p>html</p>", "ordering": 0, "modified": "datetime" }
```

## 23. Terms & conditions — `/front-view/terms/`

`IsAuthenticated` for the CRUD routes. The single-category public read is a separate view — see §0 #2, it currently also requires auth despite the docstring's stated intent.

| Method | Path |
|---|---|
| GET | `/front-view/terms/` |
| POST | `/front-view/terms/` |
| GET | `/front-view/terms/{uuid}/` |
| PUT / PATCH | `/front-view/terms/{uuid}/` |
| GET | `/front-view/terms/public/{category}/` |

No archive action on this model.

| Field | Type | Required | Notes |
|---|---|---|---|
| `category` | int | yes (POST only) | terms category, unique |
| `content` | html | yes | sanitised server-side |

PUT / PATCH accept `content` only.

```json
{ "uuid": "uuid", "category": 1, "content": "<p>html</p>", "modified": "datetime" }
```

**GET `public/{category}/`** — never 404s; a category with no row yet returns `{"content": ""}`. Otherwise:

```json
{ "content": "<p>html</p>" }
```

---

# MEMBER APIs

Requires a **member** token, except where marked. `{member_uuid}` is the logged-in member's own `uuid` (returned by the login response) — **but see §0 #1: the routes below do not currently verify that the token's own member matches this path segment.**

## 24. Profile — `/members/profile/`

`IsMember`.

| Method | Path |
|---|---|
| GET | `/members/profile/` |
| PATCH | `/members/profile/` |

**PATCH** *(multipart if `profile_picture`)* — `full_name` (string, optional), `profile_picture` (file, optional).

Response is the full member profile — see §9 `GET /members/{uuid}/`.

## 25. Change password — `/members/profile/change-password/`

`IsMember`.

**PATCH**

| Field | Type | Required |
|---|---|---|
| `current_password` | string | yes |
| `password` | string | yes |
| `confirm_password` | string | yes — must equal `password` |

**200** `{ "message": "Password updated" }` · **400** `Current password is incorrect`.

## 26. Own bank details — `/members/profile/bank-details/`

`IsMember`.

| Method | Path |
|---|---|
| GET | `/members/profile/bank-details/` |
| POST | `/members/profile/bank-details/` |
| GET | `/members/profile/bank-details/{uuid}/` |
| PUT / PATCH | `/members/profile/bank-details/{uuid}/` |
| PATCH | `/members/profile/bank-details/{uuid}/archive/` |

| Field | Type | Required (POST) | Notes |
|---|---|---|---|
| `bank` | int | yes | bank |
| `account_holder_name` | string | yes | |
| `account_number` | string | yes | |
| `is_primary` | bool | no | default `true`; setting it clears the flag on the member's other accounts |

Verified by live testing: setting a second account as primary correctly un-sets the flag on the first.

```json
{ "uuid": "uuid", "bank": 2, "account_holder_name": "string",
  "account_number": "string", "is_primary": true }
```

## 27. Platform accounts — `/members/profile/platform-accounts/`

`IsMember`.

| Method | Path |
|---|---|
| GET | `/members/profile/platform-accounts/` |
| POST | `/members/profile/platform-accounts/` |
| GET | `/members/profile/platform-accounts/{uuid}/` |
| PUT / PATCH | `/members/profile/platform-accounts/{uuid}/` |
| PATCH | `/members/profile/platform-accounts/{uuid}/archive/` |

| Field | Type | Required (POST) | Notes |
|---|---|---|---|
| `platform` | int | yes | platform; one account per platform per member |
| `handle` | string | yes | |
| `profile_url` | url | no | |

Duplicate platform → **400** `Data already exists`.

```json
{ "uuid": "uuid", "platform": 2, "handle": "string",
  "profile_url": "url|null", "is_verified": false, "last_synced": "datetime|null" }
```

## 28. Job board — `/members/{member_uuid}/available-jobs/`

`IsAuthenticated` — see §0 #1.

| Method | Path |
|---|---|
| GET | `/members/{member_uuid}/available-jobs/` |
| GET | `/members/{member_uuid}/available-jobs/{uuid}/` |
| POST | `/members/{member_uuid}/available-jobs/{uuid}/apply/` |

Lists jobs with `status = 2` (ACTIVE) and not archived, within their `start_date`/`end_date` window.

**POST apply** — no body. **201** with the new member-job object (§16), `status = 1` APPLIED.
**400** `Job is not open for applications` if the job is not live; **400** `Already applied to this job` on a repeat.

Response is the job object (§12) plus:

```json
{ "is_applied": false }
```

## 29. My jobs — `/members/{member_uuid}/jobs/`

`IsAuthenticated` — see §0 #1. **GET** only — this route is read-only for everyone; the write actions on a member's job application live under §16 and are `IsAdmin`.

Object and `status` query param as in §16.

## 30. Frames for a job — `/members/{member_uuid}/jobs/{job_uuid}/frames/`

`IsAuthenticated` — see §0 #1.

| Method | Path |
|---|---|
| GET | `/members/{member_uuid}/jobs/{job_uuid}/frames/` |
| GET | `/members/{member_uuid}/jobs/{job_uuid}/frames/{uuid}/` |

Returns only frames with `status = 1` on a job the member holds with `status = 2` ACTIVE. A job the member is not on returns an empty list.

**Query**: `media_type` (int — matches that type **and** `1` BOTH), `aspect_ratio` (int), `page`, `page_size`.

Object as in §14.

## 31. Tasks — `/members/{member_uuid}/tasks/`

`IsAuthenticated` — see §0 #1.

| Method | Path |
|---|---|
| GET | `/members/{member_uuid}/tasks/` |
| GET | `/members/{member_uuid}/tasks/today/` |
| GET | `/members/{member_uuid}/tasks/{uuid}/` |
| POST / PATCH | `/members/{member_uuid}/tasks/{uuid}/submit/` |
| POST | `/members/{member_uuid}/tasks/{uuid}/content/` |
| PATCH | `/members/{member_uuid}/tasks/{uuid}/content/{file_uuid}/` |
| POST / PATCH | `/members/{member_uuid}/tasks/{uuid}/result/` |

**GET list query**: `member_job_uuid`, `period_key`, `page`, `page_size`.

**GET today** — creates today's task rows for every active member-job if they don't exist yet, then returns them. **Not paginated** — a bare array.

**submit** *(multipart if `proof_file`)*

| Field | Type | Required | Notes |
|---|---|---|---|
| `proof_link` | url | conditional | one of `proof_link` / `proof_file` is required |
| `proof_file` | file | conditional | |
| `note` | string | no | |

**400** `Task has already been submitted` · **400** `Submission window has closed` (past `period_end` midnight + `submission_grace_hours`).

**content** *(multipart)* — the finished deliverables, separate from the proof screenshot.

| Field | Type | Required | Notes |
|---|---|---|---|
| `files` | file[] | yes | 1–20 files; `media_type` is derived from the extension |

**PATCH content/{file_uuid}/** — no body. Archives one uploaded file.

**result** — post performance. Display only; does not affect earnings.

| Field | Type | Required | Notes |
|---|---|---|---|
| `views` | int | no | ≥ 0 |
| `likes` | int | no | ≥ 0 |
| `comments` | int | no | ≥ 0 |
| `shares` | int | no | ≥ 0 |
| `metrics_screenshot` | file | no | |

At least one field is required. **400** `Submit the task before reporting its result` if the task hasn't been submitted. No deadline on this endpoint.

Every one of these returns the task object — see §15.

`status` is derived, not stored: reviewed → `3`/`4`; submitted → `2`; `period_end` in the past → `5` MISSED; otherwise `1` PENDING.

## 32. Earnings — `/members/{member_uuid}/earnings/`

`IsAuthenticated` — see §0 #1.

**GET** — current month, no params. The period still in progress is excluded from `posted_count`, `missed_count` and `deduction`; it is only counted once `period_end` has passed. Verified by live testing: base pay, cycle counting, missed/posted counts and deduction math all matched hand-computed expected values exactly.

```json
{
  "period_key": "2026-08", "from_date": "date", "to_date": "date",
  "base_pay": "0.00", "missed_count": 0, "posted_count": 0,
  "deduction": "0.00", "total": "0.00",
  "jobs": [
    {
      "member_job_uuid": "uuid", "org": "string", "job_title": "string",
      "payment_amount": "0.00", "payment_period": 3, "cycles": 1,
      "base_pay": "0.00", "missed_count": 0, "posted_count": 0,
      "deduction": "0.00", "total": "0.00"
    }
  ]
}
```

## 33. Missed — `/members/{member_uuid}/missed/`

`IsAuthenticated` — see §0 #1.

**GET** — current month, no params. Excludes the period still in progress.

```json
{
  "period_key": "2026-08", "from_date": "date", "to_date": "date",
  "missed_count": 0, "deduction": "0.00",
  "days": [
    { "member_job_uuid": "uuid", "org": "string", "job_title": "string",
      "period_key": "2026-08-14", "period_start": "date", "period_end": "date",
      "deduction": "0.00" }
  ]
}
```

## 34. My payouts — `/members/{member_uuid}/payouts/`

`IsAuthenticated` — see §0 #1. Read-only.

| Method | Path |
|---|---|
| GET | `/members/{member_uuid}/payouts/` |
| GET | `/members/{member_uuid}/payouts/{uuid}/` |

Object as in §18.

---

## Removed since 1.1

- `GET /front-view/content/`, `GET /front-view/content/{uuid}/`, `GET /front-view/content/guides/`, `GET /front-view/content/terms/` — this member-facing content-aggregator view no longer exists in the codebase. Members currently read banners/guides/terms directly off the admin routes in §21–23, all of which are `IsAuthenticated` (not `IsAdmin`), plus the `public`/`public/{category}` actions described there (which, per §0 #2, currently still require a token despite the intent).
