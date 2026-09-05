/*
 * Lightweight mock of the Novu API for the docker-compose dev/test
 * environment.
 *
 * Why a mock rather than the real Novu stack (study 2.1):
 * the reference Novu infrastructure assembles novu/api + novu/worker +
 * novu/ws + novu/web + MongoDB + Redis (and optionally a mail service) -
 * heavy for a fast test environment in CI, and redundant with the real
 * goal here, which is to test the CONNECTORS (notification-hub,
 * onlyoffice-mentions, presence-aggregator...) rather than Novu itself.
 * This mock therefore only exposes the minimal surface that these
 * connectors actually call: a health endpoint and an event ingestion
 * endpoint (a simplified equivalent of Novu's API
 * POST /v1/events/trigger), which logs and acknowledges.
 *
 * For an end-to-end integration test WITH the real Novu (staging,
 * study 4.4/5.5), replace this service with the official Novu
 * docker-compose documented at https://docs.novu.co/self-hosting - not
 * duplicated here to avoid configuration drift between two definitions of
 * the stack.
 */
const http = require("http");

const PORT = process.env.PORT || 3000;
const events = [];

const server = http.createServer((req, res) => {
  let body = "";
  req.on("data", (chunk) => (body += chunk));
  req.on("end", () => {
    if (req.url === "/v1/health-check" || req.url === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "ok", mock: true }));
      return;
    }
    if (req.method === "POST" && req.url === "/v1/events/trigger") {
      let payload = {};
      try {
        payload = JSON.parse(body || "{}");
      } catch (e) {
        // ignore malformed payloads in the mock
      }
      events.push(payload);
      console.log("[novu-mock] event received:", JSON.stringify(payload));
      res.writeHead(201, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ acknowledged: true, status: "processed" }));
      return;
    }
    if (req.method === "GET" && req.url === "/v1/events") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ data: events }));
      return;
    }
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "not found (novu-mock)" }));
  });
});

server.listen(PORT, () => {
  console.log(`[novu-mock] listening on :${PORT}`);
});
