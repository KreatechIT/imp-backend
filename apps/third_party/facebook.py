import requests
from django.conf import settings

GRAPH = "https://graph.facebook.com/{}".format(settings.META_GRAPH_API_VERSION)
DIALOG = "https://www.facebook.com/{}/dialog/oauth".format(settings.META_GRAPH_API_VERSION)

SCOPES = ["pages_show_list", "pages_read_engagement"]


class FacebookError(Exception):
    pass


def _get(path, **params):
    response = requests.get(f"{GRAPH}/{path}", params=params, timeout=15)
    data = response.json()
    if response.status_code != 200:
        raise FacebookError(data.get("error", {}).get("message", "Facebook rejected the request."))
    return data


def authorize_url(redirect_uri, state):
    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
    }
    if settings.FACEBOOK_LOGIN_CONFIG_ID:
        params["config_id"] = settings.FACEBOOK_LOGIN_CONFIG_ID
    else:
        params["scope"] = ",".join(SCOPES)
    return f"{DIALOG}?{requests.compat.urlencode(params)}"


def connect(code, redirect_uri):
    user_token = _get(
        "oauth/access_token",
        client_id=settings.META_APP_ID,
        client_secret=settings.META_APP_SECRET,
        redirect_uri=redirect_uri,
        code=code,
    )["access_token"]

    long_lived = _get(
        "oauth/access_token",
        grant_type="fb_exchange_token",
        client_id=settings.META_APP_ID,
        client_secret=settings.META_APP_SECRET,
        fb_exchange_token=user_token,
    )["access_token"]

    pages = _get(
        "me/accounts", fields="id,name,access_token", access_token=long_lived,
    ).get("data", [])
    if not pages:
        raise FacebookError(
            "No Facebook Page found on this account. Reels are read from a Page, "
            "so the account needs one before it can be connected."
        )

    return [
        (page["id"], page.get("name", ""), page["access_token"], None)
        for page in pages
        if page.get("id") and page.get("access_token")
    ]
