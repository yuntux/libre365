import { GrommunioAvailability } from "../types";

const EWS_URL = process.env.GROMMUNIO_EWS_URL ?? "https://mail.example.org/EWS/Exchange.asmx";

/**
 * Derive l'etat "en reunion" depuis le calendrier via `GetUserAvailability` (EWS),
 * cf. etude 2.8 ligne 499 : Grommunio/EWS ne publie pas de presence a proprement
 * parler, mais permet cette derivation calendaire -- a l'image de l'ancienne
 * integration Cisco Unified Presence <-> Exchange.
 *
 * `GetUserAvailability` est une operation SOAP (namespace
 * http://schemas.microsoft.com/exchange/services/2006/messages), pas REST/JSON --
 * d'ou l'enveloppe XML construite a la main ci-dessous plutot qu'un simple fetch JSON.
 * Le parsing de la reponse est simplifie (extraction du premier `<BusyType>` par regex)
 * plutot qu'un vrai parseur XML/SOAP, la structure de l'appel etant le point a fournir ici.
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
    // Simplification assumee : un vrai client SOAP parserait le XML proprement
    // (ex. `fast-xml-parser`) plutot que cette extraction textuelle.
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
