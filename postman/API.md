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

**Current version: 1.0** — 2026-08-31

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-08-31 | Initial release. Covers auth, admin users, activity log, members, companies, jobs, job requirements, frames, submissions, member job applications, job settings, payouts, earnings statistics, KPI, banners, guides, terms, member profile, bank details, platform accounts, job board, tasks, earnings, missed and app content. 82 endpoints. |

## 4. Conventions

**Auth header**

```
Authorization: Bearer <access>
```

**Pagination** — every list endpoint.

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
| 403 | `{"error": "Incorrect login credentials", "details": {}}` — login endpoints only |
| 404 | `{"detail": "Not found."}` |

**Delete** — no `DELETE` method anywhere. Soft delete is `PATCH .../archive/`, which returns the archived object.

**Dates** — `YYYY-MM-DD`. **Datetimes** — ISO 8601 with `+08:00`. **`period_key`** — `YYYY-MM-DD` (daily), `YYYY-Www` (weekly), `YYYY-MM` (monthly).

## 5. Choices

| Set | Values |
|---|---|
| Admin status | `1` ACTIVE, `2` INACTIVE |
| Member status | `1` ACTIVE, `2` INACTIVE, `3` SUSPENDED |
| Platform | `1` INSTAGRAM, `2` TIKTOK |
| Company status | `1` ACTIVE, `2` INACTIVE |
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

Shared by both roles.

### `/login/admin-access-token/` · `/login/member-access-token/`

**POST** — no auth.

| Field | Type | Required | Notes |
|---|---|---|---|
| `username` | string | yes | |
| `password` | string | yes | |
| `ip_address` | string | no | member endpoint only |
| `device` | string | no | member endpoint only |

**200** — admin: the Admin object + tokens. Member: the Member profile object + tokens.

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

`role` is `ADMIN` or `MEMBER`. A member posting to the admin endpoint (or the reverse) → **403** `{"error": "Incorrect login credentials", "details": {}}`.

### `/login/refresh-token/`

**POST** — `{ "refresh": "<token>" }` → **200** `{ "access": "...", "refresh": "..." }`

### `/login/verify-token/`

**POST** — `{ "token": "<token>" }` → **200** `{}`

### `/login/logout/`

**POST** — `{ "refresh": "<token>" }` → **200** `{}` (blacklists the refresh token)

---

# ADMIN APIs

Everything below requires an **admin** token unless noted.

## 6. Admin users — `/admins/users/`

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

| Method | Path |
|---|---|
| GET | `/admins/activity-log/` |
| GET | `/admins/activity-log/{uuid}/` |

**Query**: `username` (icontains), `page`, `page_size`.

```json
{ "uuid": "uuid", "datetime": "datetime", "admin": "username", "activity": "string" }
```

## 8. Members — `/members/`

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

## 9. Member bank details (read-only) — `/members/{member_uuid}/bank-details/`

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

## 10. Companies — `/jobs/companies/`

| Method | Path |
|---|---|
| GET | `/jobs/companies/` |
| POST | `/jobs/companies/` |
| GET | `/jobs/companies/{uuid}/` |
| PUT / PATCH | `/jobs/companies/{uuid}/` |
| PATCH | `/jobs/companies/{uuid}/archive/` |

**Query**: `name` (icontains), `status` (int, company status), `page`, `page_size`.

**POST / PUT / PATCH** *(multipart if `logo`)*

| Field | Type | Required (POST) | Notes |
|---|---|---|---|
| `name` | string | yes | unique |
| `status` | int | no | company status, default `1` |
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

## 11. Jobs — `/jobs/postings/`

| Method | Path |
|---|---|
| GET | `/jobs/postings/` |
| POST | `/jobs/postings/` |
| GET | `/jobs/postings/{uuid}/` |
| PUT / PATCH | `/jobs/postings/{uuid}/` |
| PATCH | `/jobs/postings/{uuid}/archive/` |

**Query**: `company_uuid`, `status` (int, job status), `title` (icontains), `page`, `page_size`.

**POST**

| Field | Type | Required | Notes |
|---|---|---|---|
| `company_uuid` | uuid | yes | must be an unarchived company |
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

**PUT / PATCH** — same scalar fields, all optional. `requirements` is **not** accepted here; use the requirements endpoints.

```json
{
  "uuid": "uuid",
  "company": "string", "company_uuid": "uuid", "company_logo": "url|null",
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

`is_live` = status `2` **and** not archived **and** now is between `start_date` and `end_date`.

## 12. Job requirements — `/jobs/postings/{job_uuid}/requirements/`

| Method | Path |
|---|---|
| GET | `/jobs/postings/{job_uuid}/requirements/` |
| POST | `/jobs/postings/{job_uuid}/requirements/` |
| GET | `/jobs/postings/{job_uuid}/requirements/{uuid}/` |
| PUT / PATCH | `/jobs/postings/{job_uuid}/requirements/{uuid}/` |
| PATCH | `/jobs/postings/{job_uuid}/requirements/{uuid}/archive/` |

| Field | Type | Required (POST) | Notes |
|---|---|---|---|
| `platform` | int | yes | platform |
| `content_type` | int | yes | content type |
| `quantity` | int | no | ≥ 1, default `1` |

`platform` + `content_type` is unique per unarchived job → duplicate returns **400** `Data already exists`.

```json
{ "uuid": "uuid", "platform": 1, "content_type": 1, "quantity": 1 }
```

## 13. Frames — `/jobs/postings/{job_uuid}/frames/`

| Method | Path |
|---|---|
| GET | `/jobs/postings/{job_uuid}/frames/` |
| POST | `/jobs/postings/{job_uuid}/frames/` |
| GET | `/jobs/postings/{job_uuid}/frames/{uuid}/` |
| PUT / PATCH | `/jobs/postings/{job_uuid}/frames/{uuid}/` |
| PATCH | `/jobs/postings/{job_uuid}/frames/{uuid}/archive/` |

**Query**: `media_type` (int — matches that type **and** `1` BOTH), `status` (int, frame status), `page`, `page_size`.

**POST / PUT / PATCH** — *multipart*

| Field | Type | Required (POST) | Notes |
|---|---|---|---|
| `name` | string | yes | |
| `image` | file | yes | PNG with an alpha channel; size-validated |
| `aspect_ratio` | int | no | frame aspect ratio, default `1` |
| `media_type` | int | no | frame media type, default `1` |
| `ordering` | int | no | ≥ 0, default `0` |
| `status` | int | no | frame status, default `1` |

All optional on PUT / PATCH. A non-transparent image returns **400**.

```json
{
  "uuid": "uuid", "job_uuid": "uuid", "job_title": "string", "company": "string",
  "name": "string", "image": "url",
  "aspect_ratio": 1, "media_type": 1, "ordering": 0,
  "status": 1, "is_live": true,
  "created": "datetime", "modified": "datetime"
}
```

## 14. Submissions — `/jobs/submissions/`

| Method | Path |
|---|---|
| GET | `/jobs/submissions/` |
| GET | `/jobs/submissions/{uuid}/` |
| PATCH | `/jobs/submissions/{uuid}/approve/` |
| PATCH | `/jobs/submissions/{uuid}/reject/` |

**Query**

| Param | Notes |
|---|---|
| `status` | `1` pending (not submitted, period still open) · `2` awaiting review · `3` approved · `4` rejected · `5` missed (not submitted, period closed). Omitted → every submitted task. |
| `job_uuid` | |
| `member_uuid` | |
| `period_key` | exact |
| `page`, `page_size` | |

**PATCH approve** — no body. **400** if not submitted, or already reviewed.

**PATCH reject** — `reject_reason` (string, required). Same 400 rules.

**Response object** (also the task object used by every member task endpoint)

```json
{
  "uuid": "uuid",
  "member": "full name", "member_uuid": "uuid",
  "company": "string", "job_title": "string", "member_job_uuid": "uuid",
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

## 15. Member job applications — `/members/{member_uuid}/jobs/`

GET is open to any authenticated user; the write actions are **admin only** (a member calling them gets **400** `Can only be triggered by admins`).

| Method | Path |
|---|---|
| GET | `/members/{member_uuid}/jobs/` |
| GET | `/members/{member_uuid}/jobs/{uuid}/` |
| PATCH | `/members/{member_uuid}/jobs/{uuid}/` |
| PATCH | `/members/{member_uuid}/jobs/{uuid}/approve/` |
| PATCH | `/members/{member_uuid}/jobs/{uuid}/reject/` |
| PATCH | `/members/{member_uuid}/jobs/{uuid}/complete/` |

**Query**: `status` (int, member job status), `page`, `page_size`.

**PATCH** *(body)*

| Field | Type | Required | Notes |
|---|---|---|---|
| `status` | int | no | member job status |
| `affiliate_link` | url | no | max 500 |
| `affiliate_link_status` | int | no | affiliate link status |

**PATCH approve** — `affiliate_link` (url, optional). Sets `status = 2`, `joined = today`; if a link is given, also `affiliate_link_status = 3`.

**PATCH reject** — no body. Sets `status = 4`.

**PATCH complete** — no body. Sets `status = 3`, `completed = today`.

```json
{
  "uuid": "uuid",
  "member": "full name", "member_uuid": "uuid", "username": "string",
  "company": "string", "company_logo": "url|null",
  "job_uuid": "uuid", "job_title": "string",
  "payment_amount": "0.00", "payment_period": 3, "recurrence": 1,
  "status": 2, "affiliate_link": "url|null", "affiliate_link_status": 1,
  "has_frames": true,
  "joined": "date|null", "completed": "date|null", "created": "datetime"
}
```

## 16. Job settings — `/jobs/settings/`

Singleton. Created on first GET.

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

## 17. Payouts — `/earnings/payouts/`

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

## 18. Earnings statistics — `/earnings/statistics/`

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

## 19. Earnings KPI — `/earnings/kpi/`

**GET** — no params. Current month, all members.

```json
{
  "member_count": 0, "earning_member_count": 0, "missed_member_count": 0,
  "base_pay": "0.00", "posted_count": 0, "missed_count": 0,
  "deduction": "0.00", "total": "0.00"
}
```

## 20. Banners — `/front-view/banners/`

| Method | Path |
|---|---|
| GET | `/front-view/banners/` |
| POST | `/front-view/banners/` |
| GET | `/front-view/banners/{uuid}/` |
| PUT / PATCH | `/front-view/banners/{uuid}/` |
| PATCH | `/front-view/banners/{uuid}/archive/` |

**Query**: `location` (int, banner location), `page`, `page_size`.

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

## 21. Guides — `/front-view/guides/`

| Method | Path |
|---|---|
| GET | `/front-view/guides/` |
| POST | `/front-view/guides/` |
| GET | `/front-view/guides/{uuid}/` |
| PUT / PATCH | `/front-view/guides/{uuid}/` |
| PATCH | `/front-view/guides/{uuid}/archive/` |

**Query**: `location` (int, guide location), `page`, `page_size`.

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

## 22. Terms & conditions — `/front-view/terms/`

| Method | Path |
|---|---|
| GET | `/front-view/terms/` |
| POST | `/front-view/terms/` |
| GET | `/front-view/terms/{uuid}/` |
| PUT / PATCH | `/front-view/terms/{uuid}/` |

No archive action.

| Field | Type | Required | Notes |
|---|---|---|---|
| `category` | int | yes (POST only) | terms category, unique |
| `content` | html | yes | sanitised server-side |

PUT / PATCH accept `content` only.

```json
{ "uuid": "uuid", "category": 1, "content": "<p>html</p>", "modified": "datetime" }
```

---

# MEMBER APIs

Requires a **member** token, except where marked. `{member_uuid}` is the logged-in member's own `uuid` (returned by the login response).

## 23. Profile — `/members/profile/`

| Method | Path |
|---|---|
| GET | `/members/profile/` |
| PATCH | `/members/profile/` |

**PATCH** *(multipart if `profile_picture`)* — `full_name` (string, optional), `profile_picture` (file, optional).

Response is the full member profile — see §8 `GET /members/{uuid}/`.

## 24. Change password — `/members/profile/change-password/`

**PATCH**

| Field | Type | Required |
|---|---|---|
| `current_password` | string | yes |
| `password` | string | yes |
| `confirm_password` | string | yes — must equal `password` |

**200** `{ "message": "Password updated" }` · **400** `Current password is incorrect`.

## 25. Login history — `/members/profile/audit-log/`

**GET** — paginated.

```json
{ "uuid": "uuid", "datetime": "datetime",
  "ip_address": "string|null", "device": "string|null" }
```

## 26. Own bank details — `/members/profile/bank-details/`

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

```json
{ "uuid": "uuid", "bank": 2, "account_holder_name": "string",
  "account_number": "string", "is_primary": true }
```

## 27. Platform accounts — `/members/profile/platform-accounts/`

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

| Method | Path |
|---|---|
| GET | `/members/{member_uuid}/available-jobs/` |
| GET | `/members/{member_uuid}/available-jobs/{uuid}/` |
| POST | `/members/{member_uuid}/available-jobs/{uuid}/apply/` |

Lists jobs with `status = 2` (ACTIVE) and not archived.

**POST apply** — no body. **201** with the new member-job object (§15), `status = 1` APPLIED.
**400** `Job is not open for applications` if the job is not live; **400** `Already applied to this job` on a repeat.

Response is the job object (§11) plus:

```json
{ "is_applied": false }
```

## 29. My jobs — `/members/{member_uuid}/jobs/`

**GET** only for members — see §15 for the object and the `status` query param. The PATCH actions on this path are admin-only.

## 30. Frames for a job — `/members/{member_uuid}/jobs/{job_uuid}/frames/`

| Method | Path |
|---|---|
| GET | `/members/{member_uuid}/jobs/{job_uuid}/frames/` |
| GET | `/members/{member_uuid}/jobs/{job_uuid}/frames/{uuid}/` |

Returns only frames with `status = 1` on a job the member holds with `status = 2` ACTIVE. A job the member is not on returns an empty list.

**Query**: `media_type` (int — matches that type **and** `1` BOTH), `aspect_ratio` (int), `page`, `page_size`.

Object as in §13.

## 31. Tasks — `/members/{member_uuid}/tasks/`

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

Every one of these returns the task object — see §14.

`status` is derived, not stored: reviewed → `3`/`4`; submitted → `2`; `period_end` in the past → `5` MISSED; otherwise `1` PENDING.

## 32. Earnings — `/members/{member_uuid}/earnings/`

**GET** — current month, no params. The period still in progress is excluded from `posted_count`, `missed_count` and `deduction`; it is only counted once `period_end` has passed.

```json
{
  "period_key": "2026-08", "from_date": "date", "to_date": "date",
  "base_pay": "0.00", "missed_count": 0, "posted_count": 0,
  "deduction": "0.00", "total": "0.00",
  "jobs": [
    {
      "member_job_uuid": "uuid", "company": "string", "job_title": "string",
      "payment_amount": "0.00", "payment_period": 3, "cycles": 1,
      "base_pay": "0.00", "missed_count": 0, "posted_count": 0,
      "deduction": "0.00", "total": "0.00"
    }
  ]
}
```

## 33. Missed — `/members/{member_uuid}/missed/`

**GET** — current month, no params. Excludes the period still in progress.

```json
{
  "period_key": "2026-08", "from_date": "date", "to_date": "date",
  "missed_count": 0, "deduction": "0.00",
  "days": [
    { "member_job_uuid": "uuid", "company": "string", "job_title": "string",
      "period_key": "2026-08-14", "period_start": "date", "period_end": "date",
      "deduction": "0.00" }
  ]
}
```

## 34. My payouts — `/members/{member_uuid}/payouts/`

| Method | Path |
|---|---|
| GET | `/members/{member_uuid}/payouts/` |
| GET | `/members/{member_uuid}/payouts/{uuid}/` |

Read-only. Object as in §17.

## 35. App content — `/front-view/content/`

Members only. The live, member-facing read of banners / guides / terms.

| Method | Path | Query |
|---|---|---|
| GET | `/front-view/content/` | `location` (int, banner location), `page`, `page_size` |
| GET | `/front-view/content/{uuid}/` | |
| GET | `/front-view/content/guides/` | `location` (int, guide location) |
| GET | `/front-view/content/terms/` | `category` (int, terms category) |

`/content/` returns only banners whose `active_from` / `active_until` window contains now — paginated, object as in §20.

`guides/` and `terms/` return **bare arrays**, not paginated — objects as in §21 and §22.
