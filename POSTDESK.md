# PostDesk — Backend Implementation Notes

Branch: `postdesk`

PostDesk is a second product built into the existing IMP (Influencer Management Portal) codebase. It gives **KOC** users a workflow for taking a video, compositing it with an admin-configured frame, downloading it, publishing it manually to Facebook/Instagram, and reporting the published link back.

Requirements source: `[Influencer Management Portal (IMP)] Project Details (1).xlsx`.
The authoritative sheet is **"PostDesk Requirement"** (7 rows). `PostDesk Requirement 1` and `PostDesk Requirement2` are earlier drafts that contain some detail the final sheet drops (frame versioning, bulk upload, MP4 fallback, reporting).

---

## 1. Roles: KOC vs Influencer

KOC is **not** a separate model. Both KOC and Influencer/KOL are `Member` rows, distinguished by a `Member.role` FK.

```python
class Role(TimeStampedModel):          # apps/members/models.py
    name     = CharField(100, unique=True)
    status   = IntegerField(choices=ROLE_STATUS_CHOICES, default=1)
    archived = DateTimeField(null=True)
```

There is deliberately **no permission model**. The spec only requires a fixed role → module mapping ("KOC accesses assigned KOC modules only"), not per-user configurable permissions. Admin is flat full-access — the spec states *"Admin has full management access."*

Seed the two roles:

```bash
python manage.py seedroles     # creates "influencer" and "koc" (lowercase, idempotent)
```

### Endpoints

| Method | Path | Notes |
|---|---|---|
| `GET` | `/members/roles/` | Read-only list, admin only |
| `POST` | `/members/` | Accepts optional `role_uuid` |
| `PATCH` | `/members/{uuid}/` | Accepts optional `role_uuid` |

`PATCH` only touches the role when `role_uuid` is present in the payload — sending other fields alone leaves the role untouched. Sending `"role_uuid": null` clears it.

### Login response

`POST /login/member-access-token/` returns **`member_role`** (`"influencer"` / `"koc"` / `null`) alongside the pre-existing `role` field (`"MEMBER"` / `"ADMIN"`).

> ⚠️ The two keys are easy to confuse. `role` is the **identity type** and already existed; `member_role` is the **KOC/Influencer role** we added. It's named that way because `login/views.py` hardcodes `data["role"] = "MEMBER"` after spreading the serializer, which would have clobbered a field named `role`.

The frontend routes on `member_role`.

---

## 2. User Groups

```python
class UserGroup(TimeStampedModel):     # apps/members/models.py
    name     = CharField(100, unique=True)
    members  = M2M(Member, related_name="user_groups")
    status   = IntegerField(choices=USER_GROUP_STATUS_CHOICES, default=1)
    archived = DateTimeField(null=True)
```

There is **no `role` field on the group**, by decision — "one group holds one role only" is enforced in the frontend, not the backend. A direct API call can still mix roles; add a serializer check if that ever matters.

### Endpoints

| Method | Path | Returns |
|---|---|---|
| `GET` | `/members/group/` | Flat list — `uuid`, `name`, `status`, `total_members`, `created`. Filters: `name`, `status` |
| `GET` | `/members/group/{uuid}/` | Detail — flat fields **plus** nested `members` (`uuid`, `username`, `full_name`, `phone_number`, `date_of_birth`, `member_role`) |
| `POST` | `/members/group/` | `name`, `status`, `members` (list of member uuids) |
| `PUT` / `PATCH` | `/members/group/{uuid}/` | Partial. Sending `members` **replaces** the whole list; omitting it leaves membership untouched |
| `PATCH` | `/members/group/{uuid}/archive/` | Soft delete |

Unknown member uuids return `400` naming the offending uuid rather than silently dropping them.

`total_members` is a queryset annotation and nested members come from a filtered `Prefetch` — both live in the viewset, not the serializer.

---

## 3. Frames — restructured

### The problem

`Frame.job` was a **mandatory** FK. A frame could not exist without a job, which made the model unusable for PostDesk (KOC frames have no job). This is the trap the restructure fixes — and the rule going forward: **never make the context mandatory.**

### The change

`Frame` is now **context-free**. All linkage moved to `FrameAssignment`.

```python
class Frame(TimeStampedModel):         # apps/frames/models.py
    frame_type   = IntegerField(choices=FRAME_TYPE_CHOICES, default=1)  # 1=JOB, 2=POSTDESK
    name         = CharField(150)
    background   = ImageField(null=True)     # layer 1, image only
    image        = ImageField(null=True)     # the overlay — image or GIF, transparent
    aspect_ratio, media_type, ordering, status, archived
    # job FK REMOVED

class FrameAssignment(TimeStampedModel):
    frame      = FK(Frame, related_name="assignments")
    job        = FK(Job, null=True)          # IMP
    member     = FK(Member, null=True)       # individual KOC
    user_group = FK(UserGroup, null=True)    # KOC group
    status, archived
```

`frame_type` is the explicit discriminator between the two products. Before it existed the type was *inferred* from what a frame was assigned to, which left a frame with no assignments ambiguous and allowed a frame to appear in both products' lists. It is set on create and cannot be changed afterwards.

**Constraint — `frame_assignment_single_target`:** each row must have exactly one of `job` / `member` / `user_group`. A row with none (points at nothing) or two (ambiguous) is rejected by Postgres.

Assigning one frame to multiple groups *and* multiple individuals is fine — that's several rows, each with a single target.

### `Frame.job` is now a property

To avoid rewriting every serializer, `Frame` exposes a `job` property resolving through its assignments:

```python
@property
def job(self):
    assignment = next(
        (a for a in self.assignments.all() if a.job_id and a.archived is None),
        None,
    )
    return assignment.job if assignment else None
```

It relies on `prefetch_related("assignments__job__company")` in the viewset querysets — without that prefetch it becomes an N+1.

> ⚠️ It returns `None` for PostDesk frames, so serializer fields reading it use `SerializerMethodField` with a null guard. A plain `source="job.uuid"` raises `AttributeError` on `None`.

### Render authorization

`POST /frame/{uuid}/render/` previously looked up the frame with no scoping at all:

```python
frame = models.Frame.objects.filter(uuid=frame_uuid, archived=None).first()
```

Any authenticated member could render onto **any** frame by uuid — bypassing the careful scoping in `MemberFrameViewSet`. This predates this branch, but putting both products in one table made it worse: an IMP member could reach PostDesk frames.

It now resolves entitlement before allowing the render:
- **Job frame** — the member must hold that job with an active `MemberJob` (`status=2`, not archived)
- **PostDesk frame** — assigned to them individually, or via a group they belong to

> ⚠️ This fixed a real hole, and it broke five existing render tests whose setup created a member and a job frame **without** a `MemberJob` linking them — an impossible real-world state that only passed because nothing was checking. Their setup was corrected rather than the check loosened.

### Multiple frames per KOC — intentional

There is **no** unique-active-frame-per-member constraint. A KOC can hold several frames (individually assigned plus any from their groups) and picks one per video — matching how the existing IMP frame editor already works (it renders an "Available Frames" grid).

The spec's *"only one active Frame can apply to one KOC"* was softened by its own wording — *"**Normally**, only one..."* — and a hard constraint would reject the real case of a KOC assigned Frame X individually and Frame Y via a group.

Resolution is a simple union, with no precedence rule and nothing ever deleted:

```
frames_for(koc) = individual assignments ∪ assignments of every group they belong to
```

### Endpoints

Writes go through **one** endpoint for both frame types, discriminated by `frame_type`. Reads are split, because the admin has two different screens.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/frame/library/` | Create — job **or** PostDesk frame |
| `PATCH` | `/frame/library/{uuid}/` | Edit — either type |
| `PATCH` | `/frame/library/{uuid}/archive/` | Archive — either type |
| `GET` | `/frame/library/` | **Job frames only.** Filters: `job_uuid`, `media_type`, `status` |
| `GET` | `/frame/postdesk/` | **PostDesk frames only**, with assignments. Filters: `name`, `status` |
| `GET` | `/frame/postdesk/{uuid}/` | PostDesk detail |

`/jobs/org/{org}/job/{job}/frames/` is unchanged and still works.

**Create a job frame** (exactly as before):
```json
{ "name": "...", "job_uuid": "<uuid>", "image": <file> }
```

**Create a PostDesk frame:**
```json
{ "name": "Spring Neon", "frame_type": 2,
  "background": <file>, "image": <file>,
  "members": ["<uuid>"], "user_groups": ["<uuid>"] }
```

At least one of `background` / `image` is required for PostDesk frames — either or both.

**Cross-type fields are rejected, not ignored:**

| Sent | Response |
|---|---|
| `members` / `user_groups` / `background` on a job frame | `{"members": ["Not allowed for job frames."]}` |
| `job_uuid` on a PostDesk frame | `{"job_uuid": ["Not allowed for PostDesk frames."]}` |
| PostDesk with neither image | `{"background": ["Provide a background, an overlay frame, or both."]}` |
| Job frame with no `job_uuid` / no `image` | `{"...": ["Required for job frames."]}` |

`PATCH` validates against the frame's **stored** type, so member assignments can't be added to a job frame after creation. `frame_type` itself cannot be changed after creation — it's ignored on update.

**PostDesk response shape** (`GET /frame/postdesk/{uuid}/`):
```json
{
  "uuid": "...", "frame_type": 2,
  "job_uuid": null, "job_title": null, "org": null,
  "name": "Spring Neon",
  "background": "http://host/media/frame/....png",
  "image": "http://host/media/frame/....png",
  "aspect_ratio": 1, "media_type": 1, "ordering": 0,
  "status": 1, "is_live": true,
  "created": "...", "modified": "...",
  "total_assigned": 2,
  "members": [{ "uuid": "...", "username": "...", "full_name": "..." }],
  "user_groups": [{ "uuid": "...", "name": "..." }]
}
```

Image fields are returned as **absolute URLs**.

> ⚠️ `total_assigned` counts assignment **rows**, not people. A frame assigned to 1 member and 1 group reports `2`, regardless of how many members that group holds. If the UI needs a headcount, that's a different calculation.

Sending `members` / `user_groups` on `PATCH` **replaces** the whole set. Omitting them leaves assignments untouched.

### Query changes

- `job__*` → `assignments__job__*`
- `select_related("job__company")` → `prefetch_related("assignments__job__company")` — `assignments` is a *reverse* relation, `select_related` cannot traverse it
- `.distinct()` added where reverse joins can duplicate rows
- `Job.frames` → `Job.frame_assignments` (`apps/jobs/serializers_get.py`)

All existing URLs, request payloads and response fields are unchanged. **The frontend needs no changes.**

---

## 4. Audit Log

Generic, in `base/models.py` next to `UserModel` (matching where `cp360-backend-skeleton` puts its equivalent).

```python
class AuditLog(TimeStampedModel):
    actor  = FK(AUTH_USER_MODEL, null=True)   # works for Admin, Member or KOC
    action = CharField(100)                   # free string — no choices
    status = CharField(50, null=True)         # spec's "Status/Result"
    target_content_type / target_object_id / target   # GenericForeignKey — any model
    detail = TextField(null=True)             # free-form
    # created (from TimeStampedModel) = date/time
```

`action` and `status` are deliberately unrestricted so new action types need no migration.

Per the spec, it must record: source reel link submitted, retrieval success/failure, processing completed/failed, video downloaded, temp video deleted, published link submitted/updated — and must survive the video file being deleted.

**Querying:**

```python
AuditLog.objects.filter(action="video_downloaded")     # by action
AuditLog.objects.filter(actor=koc_user)                # what this KOC did

ct = ContentType.objects.get_for_model(video)          # what happened to this video
AuditLog.objects.filter(target_content_type=ct, target_object_id=str(video.pk))
```

> ⚠️ `filter(target=obj)` does **not** work — Django cannot reverse-query a `GenericForeignKey`. Always go through the two columns.

No `AuditLog.objects.create(...)` calls are wired up yet — the model exists, the video pipeline it logs against does not.

---

## 5. Deployment

### Migrations added

| App | Migration |
|---|---|
| `base` | `0003_auditlog` |
| `members` | `0002_role_member_role_...`, `0003_usergroup` |
| `frames` | `0005_frame_background_frameassignment`, `0006_remove_frame_job`, `0007_alter_frame_image`, `0008_frame_frame_type_and_more` |

### ⚠️ Ordering is critical

`frames/0006` **drops the `Frame.job` column**. The backfill reads that column, so it must run *between* 0005 and 0006:

```bash
python manage.py migrate frames 0005        # adds background + FrameAssignment table
python manage.py backfillframeassignments   # copies job links into assignment rows
python manage.py migrate                    # applies 0006 + everything else
python manage.py seedroles                  # creates "influencer" and "koc"
```

- Run it **before 0005** → `FrameAssignment` table doesn't exist
- Run it **after 0006** → `Frame.job` is gone; the command raises `FieldError` and the links are unrecoverable

**Back up the database first.** 0006 is destructive and depends on a manual step wedged between two migrations.

If the target environment has no frames, skip the backfill — but don't run it after 0006, it will error.

`backfillframeassignments` is one-shot by nature: once 0006 lands it can never run again. Delete it in a follow-up so nobody hits that error later and wonders what broke.

---

## 6. Conventions used

- Management commands live in **`core/management/commands/`**, never per-app
- **No data migrations.** Migration files carry schema only; backfills are management commands, run deliberately and idempotently
- Serializers serialize. Querysets, annotations and prefetching live in the viewset
- Soft delete (`archive()` / `is_archived`) throughout — not hard deletes
- Response helpers from `base/responses.py`, permissions from `core/permissions.py`

---

## 7. Test status

```bash
python -m pytest apps/frames/tests/    # 56 passed
python -m pytest                       # 13 failed, 75 passed
```

`apps/frames/tests/test_user_journey.py` walks both products as a real user: admin creates a KOC with the `koc` role → puts them in a group → creates a frame assigned to that group → KOC logs in (checking `member_role`) → renders → downloads → file is deleted. Plus the equivalent IMP journey, and a check that a KOC gets `403` on every admin module.

`apps/frames/tests/test_frame_api.py` covers the frame API end to end — 38 tests across job frames, PostDesk frames, cross-type validation, absolute media URLs, permissions, and member access scoping. It was mutation-checked: disabling the serializer validation fails exactly the 6 validation tests, so the suite is not vacuous.

The 13 failures are **pre-existing and unrelated** — `apps/members/tests/test_apis.py` references a `display_name` field that does not exist on `Member` (it's `full_name`). That test file was already stale before this branch; it is unchanged here. The count is identical before and after the frame restructure.

Verified manually beyond the suite:
- A member on Job A sees only Job A's frames and an empty list for Job B — the authorization scoping survived the restructure
- Admin frame create / list / library-filter / archive all work; create produces exactly one assignment row
- User group CRUD including partial patch semantics and unknown-uuid rejection
- Login returns both `role` and `member_role`

> Note: `POST /jobs/org/{org}/job/{job}/frames/` requires `job_uuid` **in the body** even though the viewset takes the job from the URL path. Pre-existing quirk, not introduced here.

---

## 8. Not built yet

| Spec row | Item |
|---|---|
| 3 | Reel URL retrieval, MP4 upload fallback, caption text + colour |
| 4 | 4-layer composite (background → video → overlay → caption), download-then-delete |
| 5 | Published reel link submission (platform, timestamp, must outlive the video file) |
| 6 | KOC dashboard and admin review dashboard |
| 7 | Wiring `AuditLog.objects.create(...)` into the pipeline |

### Known gaps to resolve before building the pipeline

- **`drawtext` needs a font file on the server and ffmpeg built with `--enable-libfreetype`.** There is no text rendering in `apps/frames/tasks.py` today. Verify on the target server early — this typically only fails at deploy time.
- **Background compositing.** `tasks.py` currently pads with `color=black` when content doesn't fill the canvas. That pad is where the background layer belongs. Compositing also needs a third ffmpeg input beneath the content, and must handle a missing background *or* missing overlay, since both are nullable.
- **Frontend**: the editor at `/more/frame-editor/` already has crop, trim, live frame preview, and render→poll→download→mark-downloaded (which is what "delete after download" needs). Missing: caption UI, background layer in the preview stage, reel-URL import, published-link screen — and its job coupling (`task_uuid` / `member_job_uuid` / `job_uuid` threaded through every page) has to be cut.
- **`PLATFORM_CHOICES`** (`apps/members/choices.py`) has only Instagram and TikTok — **Facebook is missing** and the spec requires it.
- **No KOC-facing endpoint for assigned frames.** `/frame/postdesk/` is admin-only, and the member frame endpoints are all job-scoped (`/members/{uuid}/jobs/{job}/frames/`). A KOC can render onto a frame they're entitled to, but has no way to *discover* which frames those are. The KOC editor needs something like `/members/{uuid}/frames/` returning the union of individual + group assignments.
- **`Member.status`** has no `PENDING` state, but the spec requires accounts to start Pending and activate on first successful login.
