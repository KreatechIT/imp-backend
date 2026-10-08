from datetime import datetime
from unittest.mock import MagicMock, patch

import requests
from celery.exceptions import Retry
from django.utils import timezone

from apps.crmadmin.models import Admin
from apps.front_view import influencer_sync, tasks
from apps.front_view.models import InfluencerSnapshot, InfluencerSyncRun
from apps.members.models import Member
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel
from core.celery import app as celery_app

RUNS_URL = "/front-view/influencer/sync-runs/"


def third_party(results, not_found=(), status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {"results": results, "not_found": list(not_found)}
    if status_code != 200:
        response.raise_for_status.side_effect = requests.HTTPError("boom")
    return patch("apps.front_view.influencer_sync.requests.post", return_value=response)


def result_row(rank, phone, amount="10.00"):
    return {
        "rank": rank,
        "member_uuid": f"00000000-0000-0000-0000-{rank:012d}",
        "full_name": f"Name {rank}",
        "phone_number": phone,
        "reg_count": 2,
        "cvs_count": 1,
        "deposit_amount": amount,
    }


class SyncBase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        Member.objects.create(user=self.user, full_name="One", phone_number="0111")
        other = UserModel.objects.create(username="two")
        Member.objects.create(user=other, full_name="Two", phone_number="0222")
        gone = UserModel.objects.create(username="gone")
        Member.objects.create(
            user=gone, full_name="Gone", phone_number="0333", archived=timezone.now(),
        )
        no_phone = UserModel.objects.create(username="nophone")
        Member.objects.create(user=no_phone, full_name="No Phone")


class RunSyncTest(SyncBase):
    def test_sends_live_member_phones_and_stores_the_ranking(self):
        with third_party(
            [result_row(1, "0222", "50.00"), result_row(2, "0111")], not_found=["x"],
        ) as post:
            stored = influencer_sync.run_sync(2, attempt=1)

        sent = post.call_args.kwargs["json"]
        assert sorted(sent["phone_numbers"]) == ["0111", "0222"]
        assert post.call_args.args[0].endswith("/third-party/influencer-leaderboard/")
        assert stored == 2
        run = InfluencerSyncRun.objects.get()
        assert run.status == 1
        assert run.slot == 2
        assert run.row_count == 2 and run.not_found == ["x"]
        assert [r.phone_number for r in run.rows.all()] == ["0222", "0111"]

    def test_old_runs_are_kept_and_the_newest_success_is_current(self):
        with third_party([result_row(1, "0111", "10.00")]):
            influencer_sync.run_sync(1, 1)
        with third_party([result_row(1, "0222", "20.00")]):
            influencer_sync.run_sync(2, 1)
        assert InfluencerSyncRun.objects.count() == 2
        assert InfluencerSnapshot.objects.count() == 2
        assert influencer_sync.latest_run().rows.get().phone_number == "0222"

    def test_a_failed_run_never_replaces_the_current_board(self):
        with third_party([result_row(1, "0111")]):
            influencer_sync.run_sync(1, 1)
        influencer_sync.record_failure(1, 1, requests.ConnectionError("down"))
        failed = InfluencerSyncRun.objects.get(status=2)
        assert "down" in failed.error
        assert influencer_sync.latest_run().rows.get().phone_number == "0111"

    def test_nothing_to_send_makes_no_call(self):
        Member.objects.all().delete()
        with third_party([]) as post:
            assert influencer_sync.run_sync(1, 1) == 0
        post.assert_not_called()
        assert InfluencerSyncRun.objects.count() == 0


class TaskRetryTest(SyncBase):
    def test_first_failure_is_logged_and_retried_once_after_the_slot_delay(self):
        for slot, delay in (
            (1, 3600),
            (2, 1800),
        ):
            with third_party([], status_code=500):
                with patch.object(
                    tasks.sync_influencer_leaderboard, "retry", side_effect=Retry(),
                ) as retry:
                    try:
                        tasks.sync_influencer_leaderboard.run(slot)
                    except Retry:
                        pass
            assert retry.call_args.kwargs["countdown"] == delay

        runs = InfluencerSyncRun.objects.all()
        assert runs.count() == 2
        assert all(r.status == 2 and r.attempt == 1 for r in runs)

    def test_only_one_retry_is_allowed(self):
        assert tasks.sync_influencer_leaderboard.max_retries == 1

    def test_second_attempt_can_succeed(self):
        with third_party([result_row(1, "0111")]):
            tasks.sync_influencer_leaderboard.apply(args=(1,), retries=1)
        run = InfluencerSyncRun.objects.get()
        assert run.attempt == 2 and run.status == 1


class ScheduleTest(BaseAPITestCase):
    def test_runs_at_the_agreed_kuala_lumpur_times(self):
        schedule = celery_app.conf.beat_schedule
        night = schedule["sync-influencer-leaderboard-1"]
        day = schedule["sync-influencer-leaderboard-2"]
        assert (night["schedule"].hour, night["schedule"].minute) == ({2}, {0})
        assert (day["schedule"].hour, day["schedule"].minute) == ({11}, {58})
        assert night["args"] == (1,)
        assert day["args"] == (2,)
        assert celery_app.conf.timezone == "Asia/Kuala_Lumpur"


class SyncRunHistoryApiTest(SyncBase):
    def setUp(self):
        super().setUp()
        admin_user = UserModel.objects.create(username="hist_admin")
        Admin.objects.create(user=admin_user, full_name="Hist Admin")
        self.admin_user = admin_user

        self.old = InfluencerSyncRun.objects.create(slot=1, status=1, row_count=1)
        InfluencerSnapshot.objects.create(
            run=self.old, rank=1, member_uuid="u1", phone_number="0111", deposit_amount="5",
        )
        self.new = InfluencerSyncRun.objects.create(slot=2, status=2, error="down")
        InfluencerSyncRun.objects.filter(pk=self.old.pk).update(
            created=timezone.make_aware(datetime(2026, 9, 1, 2, 0)),
        )
        InfluencerSyncRun.objects.filter(pk=self.new.pk).update(
            created=timezone.make_aware(datetime(2026, 9, 2, 11, 58)),
        )

    def test_lists_newest_first(self):
        self.authenticate(self.admin_user)
        rows = self.client.get(RUNS_URL).json()["results"]
        assert [r["uuid"] for r in rows] == [str(self.new.uuid), str(self.old.uuid)]
        assert rows[0]["status_display"] == "FAILED" and rows[0]["error"] == "down"

    def test_filters_by_date_and_datetime(self):
        self.authenticate(self.admin_user)

        def uuids(query):
            return [r["uuid"] for r in self.client.get(f"{RUNS_URL}?{query}").json()["results"]]

        assert uuids("date_from=2026-09-02") == [str(self.new.uuid)]
        assert uuids("date_to=2026-09-01") == [str(self.old.uuid)]
        assert uuids("date_from=2026-09-01&date_to=2026-09-02") == [
            str(self.new.uuid), str(self.old.uuid),
        ]
        assert uuids("date_from=2026-09-01T03:00:00") == [str(self.new.uuid)]
        assert uuids("status=1") == [str(self.old.uuid)]
        assert uuids("slot=2") == [str(self.new.uuid)]

    def test_bad_date_is_rejected(self):
        self.authenticate(self.admin_user)
        assert self.client.get(f"{RUNS_URL}?date_from=yesterday").status_code == 400

    def test_detail_shows_that_runs_ranking(self):
        self.authenticate(self.admin_user)
        data = self.client.get(f"{RUNS_URL}{self.old.uuid}/").json()
        assert [r["phone_number"] for r in data["rows"]] == ["0111"]
        assert data["rows"][0]["deposit_amount"] == "5.00"

    def test_admin_only(self):
        assert self.client.get(RUNS_URL).status_code == 401
        self.authenticate(self.user)
        assert self.client.get(RUNS_URL).status_code == 403
