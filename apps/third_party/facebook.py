import re

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


def _resolve_link(permalink):
    url = permalink
    body = ""
    if "/share/" in url or "pfbid" in url:
        try:
            response = requests.get(
                url, allow_redirects=True, timeout=25,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            url = response.url
            body = response.text
        except requests.RequestException:
            pass

    ids = re.findall(r"/(?:reel|videos|video|posts|photos)/(\d+)", url)
    ids += re.findall(r"[?&](?:v|story_fbid|fbid)=(\d+)", url)

    if body and not ids:
        for pattern in (
            r'"post_id":"(\d+)"',
            r'"top_level_post_id":"(\d+)"',
            r'"story_fbid":"(\d+)"',
        ):
            ids += re.findall(pattern, body)
        if not ids:
            ids += re.findall(r"(\d{15,17})", body)[:5]

    return url.split("?")[0].rstrip("/").lower(), set(ids)


def find_media(page_id, permalink, access_token):
    target, target_ids = _resolve_link(permalink)

    for edge in ("video_reels", "videos"):
        url = f"{GRAPH}/{page_id}/{edge}"
        params = {
            "fields": "id,permalink_url,source,description",
            "access_token": access_token,
            "limit": 100,
        }

        while url:
            response = requests.get(url, params=params, timeout=20)
            data = response.json()
            if response.status_code != 200:
                raise FacebookError(
                    data.get("error", {}).get("message", "Facebook rejected the request."),
                )

            for item in data.get("data", []):
                link = item.get("permalink_url", "")
                if link.startswith("/"):
                    link = f"https://www.facebook.com{link}"
                normalised = link.split("?")[0].rstrip("/").lower()
                item_ids = set(re.findall(r"/(?:reel|videos|video|posts)/(\d+)", normalised))
                item_ids.add(str(item.get("id", "")))

                if normalised == target or (target_ids and target_ids & item_ids):
                    return {
                        "id": item["id"],
                        "media_type": "VIDEO",
                        "media_url": item.get("source"),
                        "permalink": link,
                    }

            url = data.get("paging", {}).get("next")
            params = None

    return _find_photo_post(page_id, target, target_ids, access_token)


def _find_photo_post(page_id, target, target_ids, access_token):
    url = f"{GRAPH}/{page_id}/posts"
    params = {
        "fields": "id,permalink_url,full_picture,attachments{type,media,target}",
        "access_token": access_token,
        "limit": 100,
    }

    while url:
        response = requests.get(url, params=params, timeout=20)
        data = response.json()
        if response.status_code != 200:
            raise FacebookError(
                data.get("error", {}).get("message", "Facebook rejected the request."),
            )

        for item in data.get("data", []):
            link = item.get("permalink_url", "")
            if link.startswith("/"):
                link = f"https://www.facebook.com{link}"
            normalised = link.split("?")[0].rstrip("/").lower()

            item_ids = set(re.findall(r"/(?:posts|photos)/(\d+)", normalised))
            post_id = str(item.get("id", ""))
            item_ids.add(post_id)
            if "_" in post_id:
                item_ids.add(post_id.split("_")[1])

            if normalised == target or (target_ids and target_ids & item_ids):
                attachment = (item.get("attachments", {}).get("data") or [{}])[0]
                media_url = (
                    attachment.get("media", {}).get("image", {}).get("src")
                    or item.get("full_picture")
                )
                if not media_url:
                    continue
                return {
                    "id": post_id,
                    "media_type": "IMAGE",
                    "media_url": media_url,
                    "permalink": link,
                }

        url = data.get("paging", {}).get("next")
        params = None

    return None
