/*
 * Mock leger de l'API Novu pour l'environnement docker-compose dev/test.
 *
 * Pourquoi un mock plutot que la vraie stack Novu (etude 2.1) :
 * l'infrastructure Novu de reference assemble novu/api + novu/worker +
 * novu/ws + novu/web + MongoDB + Redis (et optionnellement un service de
 * mail) - lourd pour un environnement de test rapide en CI et redondant
 * avec le vrai objectif ici, qui est de tester les CONNECTEURS
 * (notification-hub, onlyoffice-mentions, presence-aggregator...) plutot
 * que Novu lui-meme. Ce mock expose donc uniquement la surface minimale que
 * ces connecteurs appellent en pratique : un endpoint de sante et un
 * endpoint d'ingestion d'evenement (equivalent simplifie de
 * POST /v1/events/trigger de l'API Novu), qui journalise et acquitte.
 *
 * Pour un test d'integration bout-en-bout AVEC le vrai Novu (recette,
 * etude 4.4/5.5), remplacer ce service par le docker-compose officiel Novu
 * documente sur https://docs.novu.co/self-hosting - non duplique ici pour
 * eviter la derive de configuration entre deux definitions de la stack.
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
