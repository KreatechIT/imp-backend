import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.crmadmin.models import Admin
from apps.frames.models import Frame, FrameAssignment
from apps.koc.models import Submission
from apps.members.models import Member
from apps.notifications.models import Notification
from apps.third_party.models import ThirdPartyConnection
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


def _photo_upload(name="post.jpg"):
    return SimpleUploadedFile(name, io.BytesIO(b"fake-image-bytes").read(), content_type="image/jpeg")


def _real_image_upload(name="bg.png"):
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (10, 200, 10)).save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


class KocSubmissionAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.member = Member.objects.create(user=self.user, full_name="Koc One")

        self.admin_user = UserModel.objects.create(username="notif_admin")
        Admin.objects.create(user=self.admin_user, full_name="Notif Admin")

        self.authenticate()
        self.base_url = f"/koc/{self.member.uuid}/submissions/"

    def test_create_submission(self):
        response = self.client.post(self.base_url, {
            "content_file": _photo_upload(),
            "platform": 1,
            "published_url": "https://instagram.com/reel/abc123",
        }, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Submission.objects.count(), 1)
        submission = Submission.objects.first()
        self.assertEqual(submission.member, self.member)
        self.assertEqual(submission.published_url, "https://instagram.com/reel/abc123")
        self.assertEqual(submission.media_type, 2)
        self.assertEqual(submission.platform, 1)

    def test_create_notifies_admins(self):
        self.client.post(self.base_url, {
            "content_file": _photo_upload(),
            "platform": 1,
            "published_url": "https://instagram.com/reel/abc123",
        }, format="multipart")

        notification = Notification.objects.filter(recipient=self.admin_user).first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.notification_type, 11)

    def test_list_shows_only_own_submissions(self):
        other_user = UserModel.objects.create(username="other_koc")
        other_member = Member.objects.create(user=other_user, full_name="Koc Two")
        Submission.objects.create(
            member=other_member, content_file=_photo_upload(), media_type=2, platform=1,
            published_url="https://instagram.com/reel/other",
        )
        Submission.objects.create(
            member=self.member, content_file=_photo_upload(), media_type=2, platform=1,
            published_url="https://instagram.com/reel/mine",
        )

        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["published_url"], "https://instagram.com/reel/mine")

    def test_no_update_or_delete_endpoint(self):
        submission = Submission.objects.create(
            member=self.member, content_file=_photo_upload(), media_type=2, platform=1,
            published_url="https://instagram.com/reel/mine",
        )
        detail_url = f"{self.base_url}{submission.uuid}/"

        self.assertEqual(self.client.patch(detail_url, {"published_url": "https://x.com"}).status_code, 405)
        self.assertEqual(self.client.put(detail_url, {"published_url": "https://x.com"}).status_code, 405)
        self.assertEqual(self.client.delete(detail_url).status_code, 405)

    def test_requires_published_url_and_file(self):
        response = self.client.post(self.base_url, {}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Submission.objects.count(), 0)


class AdminSubmissionAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin_user = UserModel.objects.create(username="submission_admin")
        Admin.objects.create(user=self.admin_user, full_name="Submission Admin")

        self.member = Member.objects.create(
            user=self.user, full_name="Koc One", phone_number="0123456789",
        )
        self.submission = Submission.objects.create(
            member=self.member, content_file=_photo_upload(), media_type=2, platform=2,
            published_url="https://instagram.com/reel/mine",
        )

    def test_admin_can_list_all_submissions(self):
        self.authenticate(self.admin_user)
        response = self.client.get("/koc/submissions/")
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row["member_uuid"], str(self.member.uuid))
        self.assertEqual(row["member_name"], "Koc One")
        self.assertEqual(row["published_url"], "https://instagram.com/reel/mine")
        self.assertEqual(row["platform"], 2)

    def test_admin_can_filter_by_platform(self):
        self.authenticate(self.admin_user)

        response = self.client.get("/koc/submissions/", {"platform": 1})
        self.assertEqual(response.data["results"], [])

        response = self.client.get("/koc/submissions/", {"platform": 2})
        self.assertEqual(len(response.data["results"]), 1)

    def test_non_admin_forbidden(self):
        self.authenticate(self.user)
        response = self.client.get("/koc/submissions/")
        self.assertEqual(response.status_code, 403)


class MemberKpiAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.member = Member.objects.create(user=self.user, full_name="Koc One")
        self.authenticate()

    def test_member_kpi(self):
        frame = Frame.objects.create(name="PD Frame", frame_type=2)
        FrameAssignment.objects.create(frame=frame, member=self.member)
        Submission.objects.create(
            member=self.member, content_file=_photo_upload(), media_type=2, platform=1,
            published_url="https://instagram.com/reel/mine",
        )
        ThirdPartyConnection.objects.create(
            member=self.member, provider=1, account_id="123",
            access_token_encrypted="x",
        )

        response = self.client.get(f"/koc/{self.member.uuid}/kpi/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["assigned_frames"], 1)
        self.assertEqual(response.data["total_submissions"], 1)
        self.assertEqual(response.data["connected_accounts"], 1)

    def test_kpi_wrong_member_forbidden(self):
        other_user = UserModel.objects.create(username="other_koc")
        other_member = Member.objects.create(user=other_user, full_name="Koc Two")

        response = self.client.get(f"/koc/{other_member.uuid}/kpi/")
        self.assertEqual(response.status_code, 400)


class AdminKpiAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin_user = UserModel.objects.create(username="kpi_admin")
        Admin.objects.create(user=self.admin_user, full_name="Kpi Admin")

        self.member = Member.objects.create(user=self.user, full_name="Koc One")
        frame = Frame.objects.create(name="PD Frame", frame_type=2)
        FrameAssignment.objects.create(frame=frame, member=self.member)
        Submission.objects.create(
            member=self.member, content_file=_photo_upload(), media_type=2, platform=1,
            published_url="https://instagram.com/reel/mine",
        )
        ThirdPartyConnection.objects.create(
            member=self.member, provider=1, account_id="123",
            access_token_encrypted="x",
        )
        self.authenticate(self.admin_user)

    def test_admin_kpi(self):
        response = self.client.get("/koc/dashboard/kpi/", {
            "from_date": "2020-01-01", "to_date": "2030-01-01",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_submissions"], 1)
        self.assertEqual(response.data["submissions_in_range"], 1)
        self.assertEqual(response.data["postdesk_frame_assignments"], 1)
        self.assertEqual(response.data["connected_accounts"], 1)

    def test_admin_kpi_requires_date_range(self):
        response = self.client.get("/koc/dashboard/kpi/")
        self.assertEqual(response.status_code, 400)


class FrameAssignmentNotificationTest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin_user = UserModel.objects.create(username="frame_admin")
        Admin.objects.create(user=self.admin_user, full_name="Frame Admin")
        self.member = Member.objects.create(user=self.user, full_name="Koc One")
        self.authenticate(self.admin_user)

    def test_assigning_frame_notifies_member(self):
        response = self.client.post("/frame/library/", {
            "name": "PD Frame",
            "frame_type": 2,
            "background": _real_image_upload(),
            "members": [str(self.member.uuid)],
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)

        notification = Notification.objects.filter(recipient=self.user).first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.notification_type, 12)
