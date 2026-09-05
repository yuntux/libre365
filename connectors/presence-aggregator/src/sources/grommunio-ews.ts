import { GrommunioAvailability } from "../types";

const EWS_URL = process.env.GROMMUNIO_EWS_URL ?? "https://mail.example.org/EWS/Exchange.asmx";

/**
 * Derives the "in meeting" state from the calendar via `GetUserAvailability` (EWS),
 * see study 2.8 line 499: Grommunio/EWS does not publish presence as such,
 * but allows this calendar-based derivation -- similar to the old
 * Cisco Unified Presence <-> Exchange integration.
 *
 * `GetUserAvailability` is a SOAP operation (namespace
 * http://schemas.microsoft.com/exchange/services/2006/messages), not REST/JSON --
 * hence the hand-built XML envelope below rather than a simple JSON fetch.
 * Response parsing is simplified (extracting the first `<BusyType>` via regex)
 * rather than a real XML/SOAP parser, since the structure of the call is the point
 * to provide here.
 */
export async function getGrommunioAvailability(
  userEmail: string,
  fetchImpl: typeof fetch = fetch
): Promise<GrommunioAvailability | null> {
  const soapEnvelope = buildGetUserAvailabilityRequest(userEmail);

  try {
    const response = await fetchImpl(EWS_URL, {
      method: "POST",
      headers: {
        "Content-Type": "text/xml; charset=utf-8",
        SOAPAction: '"http://schemas.microsoft.com/exchange/services/2006/messages/GetUserAvailability"',
      },
      body: soapEnvelope,
    });

    if (!response.ok) {
      return null;
    }

    const xml = await response.text();
    // Deliberate simplification: a real SOAP client would parse the XML properly
    // (e.g. `fast-xml-parser`) rather than this text-based extraction.
    const busyTypeMatch = xml.match(/<BusyType>(\w+)<\/BusyType>/);
    const busyType = busyTypeMatch?.[1];

    return { inMeetingNow: busyType === "Busy" || busyType === "OOF" };
  } catch {
    return null;
  }
}

function buildGetUserAvailabilityRequest(userEmail: string): string {
  const now = new Date();
  const in30min = new Date(now.getTime() + 30 * 60 * 1000);
  return `<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
  xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
  <soap:Body>
    <m:GetUserAvailabilityRequest>
      <t:MailboxDataArray>
        <t:MailboxData>
          <t:Email><t:Address>${userEmail}</t:Address></t:Email>
          <t:AttendeeType>Required</t:AttendeeType>
        </t:MailboxData>
      </t:MailboxDataArray>
      <t:FreeBusyViewOptions>
        <t:TimeWindow>
          <t:StartTime>${now.toISOString()}</t:StartTime>
          <t:EndTime>${in30min.toISOString()}</t:EndTime>
        </t:TimeWindow>
        <t:RequestedView>FreeBusy</t:RequestedView>
      </t:FreeBusyViewOptions>
    </m:GetUserAvailabilityRequest>
  </soap:Body>
</soap:Envelope>`;
}
