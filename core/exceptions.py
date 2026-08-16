import traceback

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        return response

    view = context.get("view", None)
    view_name = view.__class__.__name__ if view else None

    if settings.DEBUG:
        error_message = {
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "view": view_name,
        }
    else:
        error_message = {"detail": "Internal server error"}

    return Response(error_message, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
