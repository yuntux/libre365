"""Derives the "in meeting" state from the calendar via `GetUserAvailability` (EWS),
see study 2.8 line 499: Grommunio/EWS does not publish presence as such,
but allows this calendar-based derivation -- similar to the old
Cisco Unified Presence <-> Exchange integration.

`GetUserAvailability` is a SOAP operation (namespace
http://schemas.microsoft.com/exchange/services/2006/messages), not REST/JSON --
hence the hand-built XML envelope below rather than a simple JSON POST body.
Response parsing is simplified (extracting the first `<BusyType>` via regex)
rather than a real XML/SOAP parser, since the structure of the call is the point
to provide here -- exactly as in the original TypeScript stub
(`src/sources/grommunio-ews.ts`), which this module ports.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.types import GrommunioAvailability

EWS_URL = os.environ.get(
    "GROMMUNIO_EWS_URL", "https://mail.example.org/EWS/Exchange.asmx"
)

_BUSY_TYPE_RE = re.compile(r"<BusyType>(\w+)</BusyType>")


def _iso(dt: datetime) -> str:
    # Mirrors JS `Date.toISOString()`: milliseconds, trailing "Z".
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{dt.microsecond // 1000:03d}Z"
    )


def _build_get_user_availability_request(user_email: str) -> str:
    now = datetime.now(timezone.utc)
    in_30min = now + timedelta(minutes=30)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
  xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
  <soap:Body>
    <m:GetUserAvailabilityRequest>
      <t:MailboxDataArray>
        <t:MailboxData>
          <t:Email><t:Address>{user_email}</t:Address></t:Email>
          <t:AttendeeType>Required</t:AttendeeType>
        </t:MailboxData>
      </t:MailboxDataArray>
      <t:FreeBusyViewOptions>
        <t:TimeWindow>
          <t:StartTime>{_iso(now)}</t:StartTime>
          <t:EndTime>{_iso(in_30min)}</t:EndTime>
        </t:TimeWindow>
        <t:RequestedView>FreeBusy</t:RequestedView>
      </t:FreeBusyViewOptions>
    </m:GetUserAvailabilityRequest>
  </soap:Body>
</soap:Envelope>"""


async def get_grommunio_availability(
    user_email: str, client: Optional[httpx.AsyncClient] = None
) -> Optional[GrommunioAvailability]:
    soap_envelope = _build_get_user_availability_request(user_email)
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": '"http://schemas.microsoft.com/exchange/services/2006/messages/GetUserAvailability"',
    }

    async def _do_request(c: httpx.AsyncClient) -> Optional[GrommunioAvailability]:
        try:
            response = await c.post(EWS_URL, content=soap_envelope, headers=headers)
            if response.status_code >= 400:
                return None
            xml = response.text
            match = _BUSY_TYPE_RE.search(xml)
            busy_type = match.group(1) if match else None
            return GrommunioAvailability(
                in_meeting_now=busy_type in ("Busy", "OOF")
            )
        except httpx.HTTPError:
            return None

    if client is not None:
        return await _do_request(client)

    async with httpx.AsyncClient() as owned_client:
        return await _do_request(owned_client)
