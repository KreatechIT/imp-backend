from django.conf import settings
from django.urls import reverse

STATE_SALT = "third-party-oauth-state"
STATE_MAX_AGE_SECONDS = 600

PROVIDER_SCOPES = {
    1: ["instagram_business_basic", "pages_show_list"],
    2: ["pages_show_list", "pages_read_engagement"],
}


def callback_redirect_uri(request):
    return request.build_absolute_uri(reverse("third_party:oauth-callback"))


def build_result_redirect(result: str) -> str:
    frontend_base = settings.FRONTEND_BASE_URL.rstrip("/")
    path = settings.THIRD_PARTY_CONNECT_RESULT_PATH
    return f"{frontend_base}{path}?third_party_connect={result}"
