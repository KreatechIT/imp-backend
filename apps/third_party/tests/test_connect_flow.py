from unittest import mock

from django.core import signing

from apps.members.models import Member
from apps.third_party.models import ThirdPartyConnection
from base.base_test_classes import BaseAPITestCase

SALT = "third-party-oauth-state"


class ConnectFlowTest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.member = Member.objects.create(user=self.user, full_name="Koc One")
        self.authenticate(self.user)
        self.base = f"/members/{self.member.uuid}/socialmedia"

    def _state(self, provider=2):
        return signing.dumps(
            {"member_uuid": str(self.member.uuid), "provider": provider}, salt=SALT)

    def test_start_facebook_returns_authorize_url(self):
        r = self.client.post(f"{self.base}/start/", {"provider": 2}, format="json")
        self.assertEqual(r.status_code, 200)
        url = r.data["authorize_url"]
        self.assertIn("facebook.com", url)
        self.assertIn("config_id=", url)
        self.assertIn("%2Fkoc%2Foauth%2Fcallback", url)

    def test_start_instagram_returns_instagram_url(self):
        r = self.client.post(f"{self.base}/start/", {"provider": 1}, format="json")
        self.assertIn("instagram.com/oauth/authorize", r.data["authorize_url"])
        self.assertIn("instagram_business_basic", r.data["authorize_url"])

    def test_start_rejects_bad_provider(self):
        r = self.client.post(f"{self.base}/start/", {"provider": 9}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_exchange_success_saves_and_returns_connected(self):
        with mock.patch("apps.third_party.facebook.connect",
                        return_value=[("PAGE1", "My Page", "TOKEN", None)]):
            r = self.client.post(f"{self.base}/exchange/",
                                 {"code": "abc", "state": self._state()}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "connected")
        self.assertEqual(r.data["account_label"], "My Page")
        c = ThirdPartyConnection.objects.get(member=self.member, provider=2)
        self.assertEqual(c.get_access_token(), "TOKEN")
        self.assertNotIn("TOKEN", c.access_token_encrypted)

    def test_exchange_meta_failure_is_200_with_failed_status(self):
        from apps.third_party.facebook import FacebookError
        with mock.patch("apps.third_party.facebook.connect",
                        side_effect=FacebookError("No Facebook Page found.")):
            r = self.client.post(f"{self.base}/exchange/",
                                 {"code": "abc", "state": self._state()}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "failed")
        self.assertIn("No Facebook Page", r.data["message"])
        self.assertEqual(ThirdPartyConnection.objects.count(), 0)

    def test_exchange_forged_state_is_200_failed(self):
        r = self.client.post(f"{self.base}/exchange/",
                             {"code": "abc", "state": "forged"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "failed")
        self.assertEqual(ThirdPartyConnection.objects.count(), 0)

    def test_exchange_state_from_another_member_rejected(self):
        other = Member.objects.create(
            user=type(self.user).objects.create(username="other"), full_name="Other")
        state = signing.dumps(
            {"member_uuid": str(other.uuid), "provider": 2}, salt=SALT)
        r = self.client.post(f"{self.base}/exchange/",
                             {"code": "abc", "state": state}, format="json")
        self.assertEqual(r.data["status"], "failed")
        self.assertEqual(ThirdPartyConnection.objects.count(), 0)

    def test_instagram_exchange_stores_expiry(self):
        with mock.patch("apps.third_party.instagram.connect",
                        return_value=[("IG1", "kocuser", "IGTOKEN", 5184000)]):
            r = self.client.post(f"{self.base}/exchange/",
                                 {"code": "abc", "state": self._state(1)}, format="json")
        self.assertEqual(r.data["status"], "connected")
        c = ThirdPartyConnection.objects.get(provider=1)
        self.assertIsNotNone(c.token_expires_at)
        self.assertFalse(c.is_expired)

    def test_list_and_disconnect(self):
        c = ThirdPartyConnection.objects.create(
            member=self.member, provider=2, account_id="P",
            account_label="My Page", access_token_encrypted="x")
        r = self.client.get(f"{self.base}/")
        self.assertEqual(len(r.data["results"]), 1)
        self.assertEqual(r.data["results"][0]["account_label"], "My Page")

        r = self.client.patch(f"{self.base}/{c.uuid}/disconnect/")
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        self.assertIsNotNone(c.archived)

    def test_another_member_cannot_use_my_uuid(self):
        other_user = type(self.user).objects.create(username="intruder")
        Member.objects.create(user=other_user, full_name="Intruder")
        self.authenticate(other_user)
        r = self.client.get(f"{self.base}/")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(ThirdPartyConnection.objects.count(), 0)

    def test_exchange_saves_every_page_granted(self):
        with mock.patch("apps.third_party.facebook.connect", return_value=[
            ("P1", "Page One", "T1", None),
            ("P2", "Page Two", "T2", None),
        ]):
            r = self.client.post(f"{self.base}/exchange/",
                                 {"code": "abc", "state": self._state()}, format="json")
        self.assertEqual(r.data["status"], "connected")
        self.assertEqual(len(r.data["accounts"]), 2)
        self.assertEqual(ThirdPartyConnection.objects.count(), 2)
        self.assertEqual(
            {c.account_id for c in ThirdPartyConnection.objects.all()}, {"P1", "P2"})
        self.assertEqual(
            ThirdPartyConnection.objects.get(account_id="P2").get_access_token(), "T2")

    def test_reconnecting_same_page_updates_not_duplicates(self):
        for token in ("T1", "T2"):
            with mock.patch("apps.third_party.facebook.connect",
                            return_value=[("P1", "Page One", token, None)]):
                self.client.post(f"{self.base}/exchange/",
                                 {"code": "abc", "state": self._state()}, format="json")
        self.assertEqual(ThirdPartyConnection.objects.count(), 1)
        self.assertEqual(
            ThirdPartyConnection.objects.first().get_access_token(), "T2")
