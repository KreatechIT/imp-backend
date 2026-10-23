from datetime import datetime, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.crmadmin import models as admin_models
from apps.jobs import models
from apps.members.models import Member
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


class JobDaysAPITest(BaseAPITestCase):
    """A job laid out day by day: each day's tasks beside the story's result."""

    def setUp(self):
        super().setUp()
        admin_models.Admin.objects.create(user=self.user, full_name="Base Admin")

        member_user = UserModel.objects.create(username="member_days")
        self.member = Member.objects.create(user=member_user, full_name="Member Days")

        today = timezone.localdate()
        self.first_day = today - timedelta(days=3)
        midnight = timezone.make_aware(
            datetime(self.first_day.year, self.first_day.month, self.first_day.day)
        )
        self.job = models.Job.objects.create(
            company=models.Company.objects.create(name="KGAME99"),
            title="Daily Job",
            start_date=midnight,
        )
        self.story = models.JobRequirement.objects.create(
            job=self.job, platform=1, content_type=2, quantity=1,
        )
        self.reel = models.JobRequirement.objects.create(
            job=self.job, platform=1, content_type=1, quantity=1,
        )
        self.member_job = models.MemberJob.objects.create(
            member=self.member, job=self.job, status=2, joined=self.first_day,
        )

        def make(requirement, day, **extra):
            return models.MemberTask.objects.create(
                member_job=self.member_job, requirement=requirement,
                period_key=day.isoformat(), period_start=day, period_end=day,
                **extra,
            )

        # day 1: story + reel submitted, story result in
        self.day1_story = make(
            self.story, self.first_day, submitted_at=timezone.now(),
            proof_link="https://instagram.com/p/1",
        )
        self.day1_story.submit_result(
            metrics_views=120, metrics_screenshot=SimpleUploadedFile("s.jpg", b"x"),
        )
        make(self.reel, self.first_day, submitted_at=timezone.now())
        # day 2: story submitted, result still to do; reel never opened
        self.day2_story = make(
            self.story, self.first_day + timedelta(days=1), submitted_at=timezone.now(),
        )

    def get_days(self, url):
        response = self.client.get(url)
        assert response.status_code == 200
        return response.json()

    def test_member_sees_every_day_numbered_from_the_job_start(self):
        self.authenticate(self.member.user)
        data = self.get_days(f"/members/{self.member.uuid}/jobs/{self.member_job.uuid}/days/")

        assert data["org"] == "KGAME99"
        days = data["days"]
        assert [d["number"] for d in days] == [1, 2, 3, 4]
        assert [d["is_today"] for d in days] == [False, False, False, True]

    def test_each_day_carries_its_tasks_and_the_story_result(self):
        self.authenticate(self.member.user)
        days = self.get_days(
            f"/members/{self.member.uuid}/jobs/{self.member_job.uuid}/days/"
        )["days"]

        day1, day2, day3, today = days
        assert [(t["content_type"], t["status"]) for t in day1["tasks"]] == [(1, 2), (2, 2)]
        assert day1["result"]["has_result"] is True
        assert day1["result"]["metrics_views"] == 120
        assert day1["result"]["metrics_screenshot"]

        assert day2["result"]["can_submit"] is True
        assert day2["result"]["has_result"] is False
        # reel was never opened on day 2: shown as missed, not left out
        assert [(t["content_type"], t["status"], t["uuid"]) for t in day2["tasks"]][0] == (1, 5, None)

        # a missed day cannot take a result; today's tasks are still open
        assert day3["result"]["can_submit"] is False
        assert [t["status"] for t in today["tasks"]] == [1, 1]

    def test_days_before_the_member_joined_are_left_out(self):
        self.member_job.update(joined=self.first_day + timedelta(days=2))
        self.authenticate(self.member.user)
        days = self.get_days(
            f"/members/{self.member.uuid}/jobs/{self.member_job.uuid}/days/"
        )["days"]
        assert [d["number"] for d in days] == [3, 4]

    def test_job_without_a_story_has_no_result_part(self):
        self.story.update(archived=timezone.now())
        self.authenticate(self.member.user)
        days = self.get_days(
            f"/members/{self.member.uuid}/jobs/{self.member_job.uuid}/days/"
        )["days"]
        assert all(d["result"] is None for d in days)

    def test_other_members_cannot_read_the_days(self):
        other = UserModel.objects.create(username="someone_else")
        Member.objects.create(user=other, full_name="Someone Else")
        self.authenticate(other)
        response = self.client.get(
            f"/members/{self.member.uuid}/jobs/{self.member_job.uuid}/days/"
        )
        # the project reports a missing/hidden item as 400, same as everywhere
        assert response.status_code == 400

    def test_admin_sees_the_same_days(self):
        self.authenticate()
        data = self.get_days(
            f"/jobs/job/{self.job.uuid}/result/member/{self.member.uuid}/days/"
        )
        assert [d["number"] for d in data["days"]] == [1, 2, 3, 4]
        assert data["days"][0]["tasks"][1]["proof_link"] == "https://instagram.com/p/1"
        assert data["days"][0]["result"]["has_result"] is True

    def test_admin_endpoint_needs_admin(self):
        self.authenticate(self.member.user)
        response = self.client.get(
            f"/jobs/job/{self.job.uuid}/result/member/{self.member.uuid}/days/"
        )
        assert response.status_code == 403
