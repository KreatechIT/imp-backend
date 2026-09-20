import requests
from django.conf import settings

AUTHORIZE = "https://www.instagram.com/oauth/authorize"
TOKEN = "https://api.instagram.com/oauth/access_token"  # nosec
GRAPH = "https://graph.instagram.com"

SCOPES = ["instagram_business_basic"]


class InstagramError(Exception):
    pass


def _check(response):
    data = response.json()
    if response.status_code != 200:
        message = data.get("error_message") or data.get("error", {}).get("message")
        raise InstagramError(message or "Instagram rejected the request.")
    return data


def authorize_url(redirect_uri, state):
    params = {
        "client_id": settings.INSTAGRAM_APP_ID,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": ",".join(SCOPES),
    }
    return f"{AUTHORIZE}?{requests.compat.urlencode(params)}"


def connect(code, redirect_uri):
    short_lived = _check(requests.post(
        TOKEN,
        data={
            "client_id": settings.INSTAGRAM_APP_ID,
            "client_secret": settings.INSTAGRAM_APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=15,
    ))

    long_lived = _check(requests.get(
        f"{GRAPH}/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": settings.INSTAGRAM_APP_SECRET,
            "access_token": short_lived["access_token"],
        },
        timeout=15,
    ))

    token = long_lived["access_token"]
    me = _check(requests.get(
        f"{GRAPH}/me",
        params={"fields": "user_id,username", "access_token": token},
        timeout=15,
    ))

    account_id = str(me.get("user_id") or short_lived.get("user_id"))
    return [(account_id, me.get("username", ""), token, long_lived.get("expires_in"))]


def find_media(account_id, permalink, access_token):
    target = permalink.split("?")[0].rstrip("/").lower()
    url = f"{GRAPH}/{account_id}/media"
    params = {
        "fields": "id,media_type,media_url,permalink,thumbnail_url",
        "access_token": access_token,
        "limit": 100,
    }

    while url:
        data = _check(requests.get(url, params=params, timeout=20))
        for item in data.get("data", []):
            if item.get("permalink", "").split("?")[0].rstrip("/").lower() == target:
                return item
        url = data.get("paging", {}).get("next")
        params = None

    return None
