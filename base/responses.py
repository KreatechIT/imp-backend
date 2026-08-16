from uuid import UUID
from typing import Optional

from rest_framework import status
from rest_framework.response import Response


class SuccessResponse:
    def __init__(self, data=None):
        self.data = data

    def get_response(self):
        return Response(
            data=self.data,
            status=status.HTTP_200_OK
        )


class CreatedSuccessResponse:
    def __init__(self, data=None):
        self.data = data

    def get_response(self):
        return Response(
            data=self.data,
            status=status.HTTP_201_CREATED
        )


class NoDataSuccessResponse:
    def get_response(self):
        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class BadRequestError:
    def __init__(self, error_message="Invalid request", details=None):
        self.error_message = error_message
        self.details = details if details else {}

    def get_response(self):
        return Response(
            {
                "error": self.error_message,
                "details": self.details
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class InvalidDataError:
    def __init__(self, error_message="Data submitted is invalid", details=None):
        self.error_message = error_message
        self.details = details if details else {}

    def get_response(self):
        return Response(
            {
                "error": self.error_message,
                "details": self.details
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class ExistingDataError:
    def __init__(
        self,
        error_message: str = "Data already exists",
        item_key: Optional[str] = None,
        item_id=None,
    ):
        self.error_message = error_message
        item = item_key if item_key is not None else "Item"
        self.details = (
            f"{item}: {item_id} already exists"
            if item_id is not None else f"{item} key already exists"
        )

    def get_response(self):
        return Response(
            {
                "error": self.error_message,
                "details": self.details
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class MissingItemError:
    def __init__(
        self,
        error_message: str = "Data does not exist",
        item_key: Optional[str] = None,
        item_id: Optional[UUID] = None,
    ):
        self.error_message = error_message
        item = item_key if item_key is not None else "Item"
        self.details = (
            f"{item}: {item_id} does not exist"
            if item_id is not None else f"{item} key does not exist"
        )

    def get_response(self):
        return Response(
            {
                "error": self.error_message,
                "details": self.details
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class ItemAlreadyArchivedError:
    def __init__(
        self,
        error_message: str = "Data archived",
        item_key: Optional[str] = None,
        item_id=None,
    ):
        self.error_message = error_message
        item = item_key if item_key is not None else "Item"
        self.details = (
            f"{item}: {item_id} already archived"
            if item_id is not None else f"{item} archived"
        )

    def get_response(self):
        return Response(
            {
                "error": self.error_message,
                "details": self.details
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class NotExistingError:
    def get_response(self):
        return Response(
            {
                "detail": "Not found."
            },
            status=status.HTTP_404_NOT_FOUND
        )


class PermissionDeniedError:
    def __init__(self, error_message="Permission denied", details=None):
        self.error_message = error_message
        self.details = details if details else {}

    def get_response(self):
        return Response(
            {
                "error": self.error_message,
                "details": self.details
            },
            status=status.HTTP_403_FORBIDDEN
        )


class ThirdPartyError:
    def __init__(self, error_message: str = "Unable to contact third party"):
        self.error_message = error_message

    def get_response(self):
        return Response(
            {
                "error": self.error_message,
            },
            status=status.HTTP_502_BAD_GATEWAY
        )
