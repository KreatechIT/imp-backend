from contextlib import contextmanager

from apps.crmadmin.models import Admin
from apps.front_view.models import DummyInfluencer, InfluencerSnapshot, InfluencerSyncRun
from apps.front_view.views import mask_name, mask_phone
from apps.members.models import Member
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel

REAL_URL = "/front-view/influencer/leaderboard/"
PUBLIC_URL = "/front-view/leaderboard/"
DUMMY_URL = "/front-view/leaderboard-dummies/"


def real_row(rank, name, amount):
    return {
        "rank": rank,
        "member_uuid": f"00000000-0000-0000-0000-{rank:012d}",
        "full_name": name,
        "phone_number": f"01{rank:08d}",
        "reg_count": 1,
        "cvs_count": 1,
        "deposit_amount": amount,
    }


@contextmanager
def synced(rows):
    """Store rows as the newest successful sync."""
    run = InfluencerSyncRun.objects.create(slot=1, status=1, row_count=len(rows))
    InfluencerSnapshot.objects.bulk_create([
        InfluencerSnapshot(run=run, **row) for row in rows
    ])
    yield


class LeaderboardBaseTest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.member = Member.objects.create(user=self.user, full_name="Koc One")
        self.admin_user = UserModel.objects.create(username="board_admin")
        Admin.objects.create(user=self.admin_user, full_name="Board Admin")

    def as_admin(self):
        self.authenticate(self.admin_user)

    def as_member(self):
        self.authenticate(self.user)


class RealLeaderboardTest(LeaderboardBaseTest):
    def test_admin_gets_real_ranking_without_dummies(self):
        DummyInfluencer.objects.create(full_name="Dummy", deposit_amount=9999)
        self.as_admin()
        with synced([real_row(1, "Real One", "500.00")]):
            response = self.client.get(REAL_URL)
        assert response.status_code == 200
        assert [r["full_name"] for r in response.json()] == ["Real One"]

    def test_requires_authentication(self):
        with synced([]):
            assert self.client.get(REAL_URL).status_code == 401


class DummyInfluencerCrudTest(LeaderboardBaseTest):
    def payload(self, **extra):
        data = {
            "full_name": "Aiman",
            "phone_number": "0123456789",
            "deposit_amount": "1200.50",
            "reg_count": 8,
            "cvs_count": 5,
        }
        data.update(extra)
        return data

    def create(self, **extra):
        return self.client.post(DUMMY_URL, data=self.payload(**extra), format="json")

    def test_admin_can_create(self):
        self.as_admin()
        response = self.create()
        assert response.status_code == 201, response.content
        data = response.json()
        assert data["full_name"] == "Aiman"
        assert data["deposit_amount"] == "1200.50"
        assert DummyInfluencer.objects.count() == 1

    def test_create_requires_name_and_amount(self):
        self.as_admin()
        response = self.client.post(DUMMY_URL, data={}, format="json")
        assert response.status_code == 400
        body = response.content.decode()
        assert "full_name" in body and "deposit_amount" in body

    def test_create_rejects_negative_amount(self):
        self.as_admin()
        assert self.create(deposit_amount="-1").status_code == 400

    def test_list_is_sorted_by_amount_and_hides_archived(self):
        self.as_admin()
        small = self.create(full_name="Small", deposit_amount="10").json()
        self.create(full_name="Big", deposit_amount="900")
        self.client.patch(f"{DUMMY_URL}{small['uuid']}/archive/")

        rows = self.client.get(DUMMY_URL).json()["results"]
        assert [r["full_name"] for r in rows] == ["Big"]

    def test_update_changes_only_sent_fields(self):
        self.as_admin()
        uuid = self.create().json()["uuid"]
        response = self.client.patch(
            f"{DUMMY_URL}{uuid}/", data={"deposit_amount": "2000"}, format="json",
        )
        assert response.status_code == 200, response.content
        dummy = DummyInfluencer.objects.get(uuid=uuid)
        assert str(dummy.deposit_amount) == "2000.00"
        assert dummy.full_name == "Aiman"
        assert dummy.reg_count == 8

    def test_archive_then_update_is_rejected(self):
        self.as_admin()
        uuid = self.create().json()["uuid"]
        assert self.client.patch(f"{DUMMY_URL}{uuid}/archive/").status_code == 200
        assert DummyInfluencer.objects.get(uuid=uuid).archived is not None
        response = self.client.patch(
            f"{DUMMY_URL}{uuid}/", data={"full_name": "X"}, format="json",
        )
        assert response.status_code == 400

    def test_archive_twice_is_rejected(self):
        self.as_admin()
        uuid = self.create().json()["uuid"]
        self.client.patch(f"{DUMMY_URL}{uuid}/archive/")
        assert self.client.patch(f"{DUMMY_URL}{uuid}/archive/").status_code == 400

    def test_unknown_uuid_is_missing(self):
        self.as_admin()
        response = self.client.patch(
            f"{DUMMY_URL}00000000-0000-0000-0000-000000000000/archive/",
        )
        assert response.status_code == 400

    def test_requires_authentication(self):
        assert self.client.get(DUMMY_URL).status_code == 401
        assert self.create().status_code == 401


class PublicLeaderboardTest(LeaderboardBaseTest):
    def get(self, rows):
        self.as_member()
        with synced(rows):
            return self.client.get(PUBLIC_URL)

    def test_merges_real_and_dummy_sorted_by_deposit(self):
        DummyInfluencer.objects.create(full_name="Dummy Mid", deposit_amount="300")
        DummyInfluencer.objects.create(full_name="Dummy Top", deposit_amount="900")
        response = self.get([
            real_row(1, "Real High", "600.00"),
            real_row(2, "Real Low", "100.00"),
        ])
        assert response.status_code == 200
        rows = response.json()
        assert [r["full_name"] for r in rows] == [
            mask_name(n) for n in ("Dummy Top", "Real High", "Dummy Mid", "Real Low")
        ]
        assert [r["rank"] for r in rows] == [1, 2, 3, 4]

    def test_rows_have_the_same_shape_and_do_not_reveal_dummies(self):
        DummyInfluencer.objects.create(
            full_name="Dummy", phone_number="0111222333", deposit_amount="50",
            reg_count=3, cvs_count=2,
        )
        rows = self.get([real_row(1, "Real", "10.00")]).json()
        dummy_row = next(r for r in rows if r["full_name"] == mask_name("Dummy"))
        real = next(r for r in rows if r["full_name"] == mask_name("Real"))
        assert set(dummy_row) == set(real)
        assert dummy_row["deposit_amount"] == "50.00"
        assert dummy_row["phone_number"] == "******2333"
        assert dummy_row["reg_count"] == 3 and dummy_row["cvs_count"] == 2

    def test_only_top_twenty_are_returned_and_reranked(self):
        real = [real_row(i, f"Real {i}", f"{1000 - i}.00") for i in range(1, 21)]
        for i in range(5):
            DummyInfluencer.objects.create(
                full_name=f"Dummy {i}", deposit_amount=2000 + i,
            )
        rows = self.get(real).json()
        assert len(rows) == 20
        assert [r["rank"] for r in rows] == list(range(1, 21))
        assert [r["full_name"] for r in rows[:5]] == [
            mask_name(f"Dummy {i}") for i in (4, 3, 2, 1, 0)
        ]
        assert rows[-1]["full_name"] == mask_name("Real 15")

    def test_archived_dummies_are_excluded(self):
        dummy = DummyInfluencer.objects.create(full_name="Gone", deposit_amount="999")
        dummy.archive()
        rows = self.get([real_row(1, "Real", "10.00")]).json()
        assert [r["full_name"] for r in rows] == [mask_name("Real")]

    def test_works_with_no_real_rows(self):
        DummyInfluencer.objects.create(full_name="Solo", deposit_amount="5")
        rows = self.get([]).json()
        assert [(r["rank"], r["full_name"]) for r in rows] == [(1, mask_name("Solo"))]

    def test_names_and_phones_are_masked_for_real_and_dummy_rows(self):
        DummyInfluencer.objects.create(
            full_name="Hafiz Rahman", phone_number="0111234567", deposit_amount="900",
        )
        rows = self.get([real_row(1, "Aiman Hakim", "500.00")]).json()
        assert [(r["full_name"], r["phone_number"]) for r in rows] == [
            ("H**********n", "******4567"),
            ("A*********m", "******0001"),
        ]
        assert "Hafiz" not in str(rows) and "Aiman" not in str(rows)
        assert "0111234567" not in str(rows)

    def test_admin_views_are_not_masked(self):
        DummyInfluencer.objects.create(
            full_name="Hafiz Rahman", phone_number="0111234567", deposit_amount="900",
        )
        self.as_admin()
        dummy = self.client.get(DUMMY_URL).json()["results"][0]
        assert dummy["full_name"] == "Hafiz Rahman"
        assert dummy["phone_number"] == "0111234567"
        with synced([real_row(1, "Aiman Hakim", "500.00")]):
            real = self.client.get(REAL_URL).json()[0]
        assert real["full_name"] == "Aiman Hakim"
        assert real["phone_number"] == "0100000001"

    def test_before_the_first_sync_only_dummies_show(self):
        DummyInfluencer.objects.create(full_name="Solo", deposit_amount="5")
        self.as_member()
        rows = self.client.get(PUBLIC_URL).json()
        assert [r["full_name"] for r in rows] == [mask_name("Solo")]

    def test_requires_authentication(self):
        assert self.client.get(PUBLIC_URL).status_code == 401

    def test_admin_can_read_too(self):
        self.as_admin()
        with synced([real_row(1, "Real", "10.00")]):
            assert self.client.get(PUBLIC_URL).status_code == 200


class MyRankTest(LeaderboardBaseTest):
    ME_URL = "/front-view/leaderboard/me/"

    def setUp(self):
        super().setUp()
        self.member.update(phone_number="0100000002")

    def test_gives_own_rank_and_gap_on_the_merged_board(self):
        DummyInfluencer.objects.create(full_name="Dummy", deposit_amount="900")
        self.as_member()
        with synced([
            real_row(1, "Real High", "600.00"),
            real_row(2, "Koc One", "100.00"),
        ]):
            data = self.client.get(self.ME_URL).json()
        assert data["rank"] == 3
        assert data["deposit_amount"] == "100.00"
        assert data["next_rank"] == 2
        assert data["next_rank_amount"] == "600.00"
        assert data["full_name"] == "Koc One"
        assert data["phone_number"] == "0100000002"
        assert data["in_top_board"] is True
        assert data["synced_at"] is not None

    def test_rank_one_has_no_next_rank(self):
        self.as_member()
        with synced([real_row(2, "Koc One", "100.00")]):
            data = self.client.get(self.ME_URL).json()
        assert data["rank"] == 1
        assert data["next_rank"] is None and data["next_rank_amount"] is None

    def test_member_missing_from_the_sync_is_unranked(self):
        self.as_member()
        with synced([real_row(1, "Someone", "50.00")]):
            data = self.client.get(self.ME_URL).json()
        assert data["rank"] is None
        assert data["deposit_amount"] == "0.00"
        assert data["in_top_board"] is False

    def test_outside_top_twenty_is_flagged(self):
        rows = [real_row(i, f"R{i}", f"{1000 - i}.00") for i in range(1, 22)]
        self.member.update(phone_number="0100000021")
        self.as_member()
        with synced(rows):
            data = self.client.get(self.ME_URL).json()
        assert data["rank"] == 21
        assert data["in_top_board"] is False

    def test_admin_cannot_use_member_endpoint(self):
        self.as_admin()
        assert self.client.get(self.ME_URL).status_code == 403

    def test_requires_authentication(self):
        assert self.client.get(self.ME_URL).status_code == 401


class RankByPhoneTest(LeaderboardBaseTest):
    def test_admin_looks_up_a_phone(self):
        self.as_admin()
        with synced([real_row(1, "A", "500.00"), real_row(2, "B", "200.00")]):
            data = self.client.get("/front-view/influencer/rank/0100000002/").json()
            missing = self.client.get("/front-view/influencer/rank/0999/")
        assert data["rank"] == 2 and data["next_rank_amount"] == "500.00"
        assert missing.status_code == 400

    def test_members_cannot_look_up_other_phones(self):
        self.as_member()
        assert self.client.get("/front-view/influencer/rank/0100000002/").status_code == 403


class MaskingHelpersTest(BaseAPITestCase):
    def test_mask_name(self):
        assert mask_name("Aiman") == "A***n"
        assert mask_name("Aiman Hakim") == "A*********m"
        assert mask_name("Li") == "L*"
        assert mask_name("A") == "A*"
        assert mask_name("  Siti  ") == "S**i"
        assert mask_name("") == ""
        assert mask_name(None) == ""

    def test_mask_phone(self):
        assert mask_phone("0123456789") == "******6789"
        assert mask_phone("+60123456789") == "********6789"
        assert mask_phone("12345") == "*2345"
        assert mask_phone("1234") == "****"
        assert mask_phone("12") == "**"
        assert mask_phone("") == ""
        assert mask_phone(None) == ""
