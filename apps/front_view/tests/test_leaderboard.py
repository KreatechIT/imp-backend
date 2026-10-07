from unittest.mock import MagicMock, patch

import requests

from apps.crmadmin.models import Admin
from apps.front_view.models import DummyInfluencer
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


def upstream(rows, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = rows
    return patch("apps.front_view.views.requests.get", return_value=response)


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
        with upstream([real_row(1, "Real One", "500.00")]):
            response = self.client.get(REAL_URL)
        assert response.status_code == 200
        assert [r["full_name"] for r in response.json()] == ["Real One"]

    def test_requires_authentication(self):
        with upstream([]):
            assert self.client.get(REAL_URL).status_code == 401

    def test_upstream_failure_returns_502(self):
        self.as_admin()
        with upstream([], status_code=500):
            assert self.client.get(REAL_URL).status_code == 502
        with patch(
            "apps.front_view.views.requests.get",
            side_effect=requests.ConnectionError,
        ):
            assert self.client.get(REAL_URL).status_code == 502


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
        with upstream(rows):
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
            "Dummy Top", "Real High", "Dummy Mid", "Real Low",
        ]
        assert [r["rank"] for r in rows] == [1, 2, 3, 4]

    def test_rows_have_the_same_shape_and_do_not_reveal_dummies(self):
        DummyInfluencer.objects.create(
            full_name="Dummy", phone_number="0111", deposit_amount="50",
            reg_count=3, cvs_count=2,
        )
        rows = self.get([real_row(1, "Real", "10.00")]).json()
        dummy_row = next(r for r in rows if r["full_name"] == "Dummy")
        real = next(r for r in rows if r["full_name"] == "Real")
        assert set(dummy_row) == set(real)
        assert dummy_row["deposit_amount"] == "50.00"
        assert dummy_row["phone_number"] == "0111"
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
            "Dummy 4", "Dummy 3", "Dummy 2", "Dummy 1", "Dummy 0",
        ]
        assert rows[-1]["full_name"] == "Real 15"

    def test_archived_dummies_are_excluded(self):
        dummy = DummyInfluencer.objects.create(full_name="Gone", deposit_amount="999")
        dummy.archive()
        rows = self.get([real_row(1, "Real", "10.00")]).json()
        assert [r["full_name"] for r in rows] == ["Real"]

    def test_works_with_no_real_rows(self):
        DummyInfluencer.objects.create(full_name="Solo", deposit_amount="5")
        rows = self.get([]).json()
        assert [(r["rank"], r["full_name"]) for r in rows] == [(1, "Solo")]

    def test_upstream_failure_returns_502(self):
        self.as_member()
        with upstream([], status_code=503):
            assert self.client.get(PUBLIC_URL).status_code == 502

    def test_requires_authentication(self):
        assert self.client.get(PUBLIC_URL).status_code == 401

    def test_admin_can_read_too(self):
        self.as_admin()
        with upstream([real_row(1, "Real", "10.00")]):
            assert self.client.get(PUBLIC_URL).status_code == 200
