import requests
from django.conf import settings


class MetaAPIError(Exception):
    def __init__(self, message, payload=None):
        super().__init__(message)
        self.payload = payload or {}


def graph_api_base() -> str:
    return f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}"


def authorize_base() -> str:
    return f"https://www.facebook.com/{settings.META_GRAPH_API_VERSION}/dialog/oauth"


def build_authorize_url(redirect_uri: str, state: str, scopes: list[str]) -> str:
    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": ",".join(scopes),
    }
    query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return f"{authorize_base()}?{query}"


def exchange_code_for_token(code: str, redirect_uri: str) -> dict:
    resp = requests.get(
        f"{graph_api_base()}/oauth/access_token",
        params={
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=15,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        raise MetaAPIError("Meta rejected the authorization code.", data)
    return data


def exchange_for_long_lived_token(short_lived_token: str) -> dict:
    resp = requests.get(
        f"{graph_api_base()}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "fb_exchange_token": short_lived_token,
        },
        timeout=15,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        raise MetaAPIError("Meta rejected the token exchange.", data)
    return data


def get_me(access_token: str, fields: str = "id,name") -> dict:
    resp = requests.get(
        f"{graph_api_base()}/me",
        params={"fields": fields, "access_token": access_token},
        timeout=15,
    )
    data = resp.json()
    if resp.status_code != 200:
        raise MetaAPIError("Could not read the connected account.", data)
    return data


def get_media(media_id: str, access_token: str) -> dict:
    resp = requests.get(
        f"{graph_api_base()}/{media_id}",
        params={
            "fields": "id,media_type,media_url,permalink,thumbnail_url,timestamp",
            "access_token": access_token,
        },
        timeout=15,
    )
    data = resp.json()
    if resp.status_code != 200:
        raise MetaAPIError("Could not fetch that media from Meta.", data)
    return data


def find_media_by_permalink(account_id: str, permalink: str, access_token: str) -> dict | None:
    normalized = permalink.rstrip("/").lower()
    resp = requests.get(
        f"{graph_api_base()}/{account_id}/media",
        params={
            "fields": "id,permalink",
            "access_token": access_token,
            "limit": 50,
        },
        timeout=15,
    )
    data = resp.json()
    if resp.status_code != 200:
        raise MetaAPIError("Could not read this account's media from Meta.", data)

    for item in data.get("data", []):
        if item.get("permalink", "").rstrip("/").lower() == normalized:
            return item
    return None


def download_media_file(media_url: str):
    resp = requests.get(media_url, stream=True, timeout=60)
    if resp.status_code != 200:
        raise MetaAPIError("Could not download the media file from Meta.")
    return resp
