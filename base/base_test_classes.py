from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from base.models import UserModel


class BaseAPITestCase(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create(
            username="john_doe",
        )

    def authenticate(self, user=None):
        self.token = AccessToken.for_user(user or self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
