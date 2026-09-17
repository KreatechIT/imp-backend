from .models import ThirdPartyConnection
from .providers.meta import MetaAPIError, download_media_file, find_media_by_permalink, get_media


def get_active_connection(member, provider):
    return ThirdPartyConnection.objects.filter(
        member=member, provider=provider, archived=None,
    ).first()


def resolve_media(connection, media_id=None, source_url=None):
    access_token = connection.get_access_token()

    if not media_id and source_url:
        match = find_media_by_permalink(connection.account_id, source_url, access_token)
        if match is None:
            raise MetaAPIError("Could not find that link among this account's posts.")
        media_id = match["id"]

    return get_media(media_id, access_token)


def download_media(media_url):
    return download_media_file(media_url)
