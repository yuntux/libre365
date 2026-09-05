"""Shared data shapes for the onlyoffice-mentions connector."""

from __future__ import annotations

from typing import Optional, TypedDict


class DirectoryUser(TypedDict, total=False):
    """Directory user (Keycloak Admin API), minimal shape used here."""

    id: str
    username: str
    email: str
    firstName: Optional[str]
    lastName: Optional[str]


class OnlyOfficeUserEntry(TypedDict):
    """Shape expected by OnlyOffice Document Server in response to `onRequestUsers`."""

    id: str
    name: str
    email: str


class OnlyOfficeDocument(TypedDict, total=False):
    title: Optional[str]
    fileType: Optional[str]


class OnRequestSendNotifyPayload(TypedDict, total=False):
    """
    Payload sent by OnlyOffice to `onRequestSendNotify` (study 2.7 line 484):
    comment message, mentioned emails, action link to the exact position
    of the comment in the document.
    """

    actionLink: Optional[str]
    message: Optional[str]
    emails: Optional[list]
    document: Optional[OnlyOfficeDocument]
    fileId: Optional[str]


class NotificationHubPayload(TypedDict, total=False):
    actionLink: Optional[str]
    comment: Optional[str]
    document: Optional[OnlyOfficeDocument]
    emails: list
    fileId: Optional[str]
    timestamp: str
