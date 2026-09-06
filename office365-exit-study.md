# Exiting Office 365: study of an open-source alternative stack

## Introduction

A consulting firm of 100 consultants has used the Office 365 suite for about ten years: email and calendar (Exchange/Outlook), file storage and synchronization (OneDrive/SharePoint), collaborative document editing (Word/Excel/PowerPoint Online), video conferencing and corporate chat (Teams), and task management (Planner/To Do).

The firm wants to assess open-source alternatives to this suite, with two main motivations: reducing dependence on a single non-European vendor (data sovereignty, control of licensing costs at scale) and evaluating whether a "best of breed" assembly of open-source building blocks can offer a comparable level of service for its consultants, without sacrificing critical uses (collaborative document co-editing, reliable video conferencing including with external contacts, mobility).

**The firm also has a strong growth ambition.** The application architecture and infrastructure chosen must therefore not be sized for the current 100 consultants alone: they must be able to scale up without major difficulty to several thousand consultants, without the architecture itself being called into question (component swap, rewrite of integrations). This scalability criterion is addressed systematically in the choice of each building block (Chapter 1), in the cross-cutting integration choices (Chapter 2), and directly shapes the infrastructure choices (Chapter 4). Two reference scales are used throughout the document to make sizing concrete: 100 users (current situation) and 2000 users (first step of the targeted growth) — it being understood that the target architecture must allow growth beyond this by adding capacity (horizontal scaling), not by swapping components.

This document capitalizes on the analysis conducted functional block by functional block, then the cross-cutting integration issues between heterogeneous building blocks, before honestly assessing what is structurally lost compared to Office 365 for lack of an alternative, and then addressing deployment infrastructure and long-term operating arrangements.

The document is structured into five chapters:
1. The choice of building blocks by functional block (mail, files, editing, video, chat, tasks, identity)
2. Cross-cutting integration issues between these building blocks
3. What is lost compared to Office 365, for lack of an alternative
4. Infrastructure and deployment arrangements
5. Long-term operations and cross-cutting governance

---

## Chapter 1 — Alternatives by functional block

### 1.1 Email and calendar (replaces Exchange/Outlook)

**Functional need**
Professional email, calendar and invitations, shared contacts, native synchronization on mobile and desktop clients (ActiveSync or equivalent), without depending on the proprietary Exchange protocol.

**Possible alternatives**
- **Grommunio**: near drop-in replacement for Exchange, compatible with MAPI/EWS/ActiveSync, native connectors to Outlook, Thunderbird, Evolution, standard mobile clients.
- **Kolab**, **SOGo**, **Zimbra Collaboration Suite**: older groupware alternatives, compared in detail below.

**Comparison table — Grommunio and the historical groupware alternatives**

| Criterion | Grommunio | Kolab | SOGo | Zimbra Collaboration |
|---|---|---|---|---|
| **License / model** | Open source (Gromox engine), limited admin UI free of charge (paid beyond 5 users) | Open source (GPL), Swiss vendor (Apheleia IT AG) | Open source (GPL v2/LGPL v2), French vendor (Alinto) | **Formerly** open source; since v10 (Daffodil), a **paid license is mandatory** for every edition — the "Open Source Edition" has reached end of life |
| **Project activity** | Very active: frequent releases throughout 2026, public roadmap (EWS, EAS continuously strengthened) | Uncertain activity: last significant packages around 2023-2024, governance that has seen tensions (contested crowdfunding campaign) | Active: version 5.12.10 (August 2026), continuous development at Alinto | Proprietary development continues on the vendor side, but no longer in an open-source logic for the end user |
| **Outlook compatibility (native MAPI/EWS)** | **Native**, without a third-party connector: MAPI/RPC-HTTP and EWS built into the engine | **Absent**: no native MAPI/EWS — Outlook must connect via IMAP or through a third-party CalDAV/CardDAV synchronizer, with no Exchange emulation | **Native via OpenChange**: a separate third-party project that emulates Exchange for Outlook — functional but more complex to deploy and maintain than support built into the engine | Native, but **the Outlook connector is a paid feature** of the Network edition |
| **Mobile synchronization (EAS)** | Native, actively developed (impersonation added in 2026) | Native via Syncroton (dedicated component) | Native, built into the engine since version 2.2.0 | Native, but **classified as a paid feature** ("Zimbra Mobile ActiveSync") in the current licensing model |
| **CalDAV/CardDAV** | Native via grommunio-dav, with GAL publication in CardDAV (2.13) | Native | Native, with extended DAV access (calendars, contacts, and mail) | Native |
| **Documented scalability** | Single appliance up to 2000 users, then a documented multi-server architecture (see below) | Not documented with the same precision in the sources consulted | Horizontal architecture claimed up to several hundred thousand users | Scalable, but large-scale management features (archiving, cross-mailbox search) are also classified as paid |
| **Alignment with the project** | Matches the all-open-source + sovereignty principle | Open source, but the lack of native MAPI/EWS weakens the "drop-in Exchange" promise set as a functional requirement | Open source and scalable, but OpenChange adds an extra component and extra operational complexity compared to native, integrated support | **Effectively ruled out**: the recent shift to a fully paid model directly contradicts this project's cost and software sovereignty motivation |

This table confirms that **Zimbra is no longer a credible alternative for a project motivated by exiting dependence on a single vendor and by controlling licensing costs**: its recent shift to a fully paid license reproduces exactly the problem this project is trying to solve. **Kolab** remains held back by the absence of native Outlook compatibility — a hard point given the functional need stated at the top of this section ("without depending on the proprietary Exchange protocol" does not mean giving up Outlook compatibility for consultants who prefer it). **SOGo** remains Grommunio's most serious competitor: open source, active, scalable, with functional Outlook support — but relying on OpenChange, a separate third-party project to operate in addition to the groupware engine, whereas Grommunio integrates MAPI/EWS natively into a single engine (Gromox). It is this native integration, rather than any inferiority of SOGo on the other criteria, that tips the balance in favor of Grommunio.

**Selection criteria**
- Broad protocol compatibility (ActiveSync for mobile, EWS/MAPI for Outlook compatibility) without forcing a client migration.
- Cost and availability of administration: Grommunio's web admin console is limited/paid beyond a certain user threshold (freemium model on admin, not on the mail engine).
- Sizing and scalability: official documentation indicates that a single Grommunio appliance is designed for a headcount of 1 to 2000 users with appropriate hardware sizing. **Point settled for growth beyond this threshold**: Grommunio documents a genuine multi-server architecture for large-scale environments and hosting providers — "share-nothing" clusters (nodes no longer share direct access to mailbox storage as of version 2025.01.1), high availability via the Linux Corosync/Pacemaker stack, and a multi-tenant architecture with multiple LDAP directories designed for large hosting providers. This is therefore not a hard limit of the component, but a deployment topology change (single appliance → multi-node cluster) to be carried out before the firm's growth reaches this threshold.

**Conclusion — component selected**
**Grommunio**, operated without the web administration interface (CLI/API/configuration files) to avoid the licensing cost beyond 5 users. This choice implies planning in-house for the skills needed to administer mailboxes without a dedicated UI — an operational cost not to be underestimated. On managing the corporate directory (GAL) and its exposure to the various mail clients, see 2.13.

Sizing selected:
- 100 users: ~4-8 GB RAM / 4 cores
- 2000 users: ~16-32 GB RAM / 8+ cores, generous disk storage (mailbox size matters more than the number of connections)
- **Beyond 2000 users**: move out of the single-appliance model and switch to the multi-server architecture documented by Grommunio ("share-nothing" cluster, Corosync/Pacemaker high availability), rather than an ad hoc repartitioning by practice/entity — this is a deployment topology change tooled by the vendor, not an improvisation to design from scratch.

**Additional note — longevity of the EAS and EWS protocols**
Grommunio relies on two distinct protocols created by Microsoft for Exchange: **EAS (Exchange ActiveSync)**, a lightweight XML/HTTP protocol dedicated to mobile sync (mail/calendar/contacts, see 1.1), and **EWS (Exchange Web Services)**, a richer SOAP API used by desktop clients (Outlook, Apple Mail, Thunderbird, see 1.9). In 2026 Microsoft announced changes to both, which should not be confused with each other:
- **EAS**: no protocol retirement, but tightening on the Exchange Online side — blocking protocol versions earlier than 16.1 (March 1, 2026) and retiring *direct* certificate-based authentication in favor of Entra ID (end of 2026).
- **EWS**: a real, complete retirement on the Exchange Online side — progressive deactivation starting October 1, 2026, final shutdown April 1, 2027, in favor of Microsoft Graph.

**Point decisive for this project**: both announcements explicitly concern only **Exchange Online** (the Microsoft 365 cloud service) — Microsoft states with each announcement that there is no change for on-premises Exchange Server. Grommunio is neither one nor the other: it is an independent, open-source implementation of these same documented protocols (MS-ASProtocol, MS-EWS*), which has no obligation to follow Microsoft's retirement schedule for its own service — its June 2026 release in fact shows active EAS development (impersonation added). **Impact on the project: none in the short/medium term**, and an indirect confirmation of the logic behind exiting Office 365: the firm is precisely ceasing to depend on Exchange Online's roadmap. The only point of longer-term vigilance, of a different nature, is that if Microsoft no longer uses EWS/EAS in its own service, third-party client vendors (Apple, Mozilla) have somewhat less incentive to invest in maintaining this support over time — an ecosystem risk to monitor, not a risk of immediate unavailability on the Grommunio side.

---

### 1.2 Instant messaging / corporate chat (replaces Teams-chat)

**Functional need**
Real-time internal chat, discussion rooms, searchable history, end-to-end encryption, mature mobile and desktop clients.

**Possible alternatives**
- **Matrix**: federated protocol, E2EE enabled by default in private rooms, rich client ecosystem.
- **XMPP**: an older, more resource-light protocol, but E2EE depends on the client chosen, and the extension ecosystem (XEP) is more fragmented and more complex to manage in practice — every feature beyond the base (encryption, notifications, multi-device history) depends on an optional extension, which requires checking case by case that each chosen client/server implements the same XEPs, unlike Matrix where these features are built into the protocol's core.

**Selection criteria**
- Alignment with the French state ecosystem: Matrix has been deployed to 400,000 civil servants via Tchap, the French State's messaging application — a strong signal of institutional legitimacy and French-speaking community support.
- Resource footprint: Matrix (Synapse) is heavier than XMPP, because its architecture replicates the conversation history on every participating server, versus simple transmission on the XMPP side.
- UX maturity for non-technical users: better on the Matrix/Element side.

**Conclusion — component selected**
**Matrix**, via the **Synapse** homeserver (see homeserver alternatives below) and the **Element** client. Alignment with Tchap/DINUM is treated as a strategic asset for a consulting firm whose clients potentially include public-sector actors.

Sizing selected (official Element recommendations):
- 100 users: ~2 CPU / 2 GB (Synapse) + 2 CPU / 6 GB (Postgres)
- 2000 users: ~6 CPU / 5.6 GB (Synapse) + 4 CPU / 18 GB (Postgres)
- **Beyond that**: Synapse supports a "workers" mode, which splits the various homeserver functions (federation, sync, message sending) across multiple processes/machines to scale horizontally — this mode should be adopted as the target architecture from the outset for this firm, rather than the monolithic mode, in order to absorb growth without rethinking the Matrix architecture. This is also one of the criteria that weighed in favor of Synapse over Dendrite/Continuwuity (see below), neither of which offers as mature a scalability path.

**Matrix homeserver alternatives (additional note)**
Two alternatives to Synapse were evaluated to reduce resource footprint:
- **Dendrite** (Go, official Element project): significantly lighter memory footprint (256-512 MB), but **in maintenance mode** (only security fixes are applied, no new features), **with no native SSO/OIDC support** and no high availability — incompatible with the Keycloak SSO architecture selected for this project. **Ruled out.**
- **Continuwuity** (Rust, fork of Conduit/Conduwuit): the lightest of the three in terms of resources, but community project governance is still young and unstable (several successive forks). To be re-evaluated only after verifying its current SSO/OIDC support; not selected as is for a client production deployment.

→ **Synapse remains the only mature choice with full SSO support and high availability (workers mode)**, despite its higher resource cost.

---

### 1.3 Video conferencing (replaces Teams-video)

**Functional need**
Video meetings with simultaneous screen and camera sharing, access via a standard telephone line (PSTN) for participants without IP access, automatic transcription, meeting recording, blurred/virtual background, ability to bring in external participants via a simple link.

**Possible alternatives**
- **Visio (DINUM/La Suite numérique)**: the French State's sovereign video conferencing solution, self-hostable, built on **LiveKit** (confirmed: the official `suitenumerique/meet` repository, MIT licensed, is described as *"powered by LiveKit"*, optimized for meetings of more than 100 people). The initial confusion with Jitsi came from another tool in the DINUM ecosystem, **Webconf**, a separate service based on Jitsi — Visio/Meet and Webconf are two different products from La Suite numérique, and only Visio is selected in this document.
- **Element Call**: a video conferencing application native to Matrix, built on the MatrixRTC protocol, using LiveKit as its SFU backend, natively embedded in Element Web/Element X.

**Selection criteria**
- PSTN: confirmed as available on the Visio DINUM side (telephone bridge on the server infrastructure side, independent of the web client); not confirmed on the Element Call side.
- Native integration into the Matrix chat thread: Element Call is natively a Matrix room widget (no integration development needed); Visio DINUM requires a connector for the same thread continuity.
- Advanced features (simultaneous screen sharing + camera, automatic transcription, blurred background): natively available on the Visio DINUM side. On the **Element Call** side, simultaneous screen sharing by multiple participants and background blurring are confirmed as native features; however, **no automatic transcription or native recording feature was identified** for Element Call to date — which makes these, along with PSTN, additional differentiating criteria in favor of Visio DINUM for meetings that need them. These features also rely on layers independent of the display (server-side processing for transcription and the telephone bridge, client-side WebGL/WebAssembly processing for background blur) and therefore remain available on the Visio side even when it is embedded as a widget/iframe in another application, subject to correct configuration of iframe permissions (`allow="camera *; microphone *; display-capture *"` and an `frame-ancestors` open to the domain hosting the widget).
- Meeting recording: available as a beta feature on the Visio DINUM side (video + audio capture of the meeting). The DINUM's public instance applies a 7-day retention period before automatic deletion, but this is very likely an operating policy specific to that instance (a lifecycle rule on its own storage), not a limitation of the software — in self-hosting, this retention is configured by the firm itself (see 2.12, corporate video platform, for the full treatment of this point).

**Conclusion — components selected**
**Both products are kept as complements**, rather than one replacing the other:
- **Visio (DINUM), self-hosted**, for meetings requiring the PSTN telephone bridge, automatic transcription, or recording (features not found on Element Call).
- **Element Call** for ad hoc calls natively integrated into the Matrix chat thread, with no further development.

A dedicated integration project (see Chapter 2) should make it possible to start a Visio DINUM meeting directly from an Element room with thread continuity before/during/after.

---

### 1.4 File synchronization and storage (replaces OneDrive/SharePoint)

**Functional need**
File storage, multi-device synchronization, folder/link sharing, acceptable synchronization performance on large volumes.

**Possible alternatives**
- **Seafile**: dedicated synchronization architecture, reputed to be lightweight and fast.
- **Nextcloud Files**: synchronization based on WebDAV, heavier/less performant than Seafile on this specific point, but a much broader ecosystem of applications and integrations.

**Selection criteria**
- Raw synchronization performance on large volumes: advantage Seafile.
- Ready-to-use integration ecosystem (unified search, notifications, third-party bridges): advantage Nextcloud, but at the cost of a less performant file engine and a PHP stack judged dated for this project.
- Sizing: Seafile is reputed to be light on CPU/RAM; the real sizing factor is the volume of stored data and synchronization frequency, not the number of concurrently active users.

**Conclusion — component selected**
**Seafile**, for its synchronization performance. The lack of an integration ecosystem (unified search, notifications) compared to Nextcloud is treated as a dedicated cross-cutting project (see Chapter 2), rather than sacrificing the performance of the storage component itself.

Sizing selected: a modest server (4-8 cores, 8-16 GB RAM) is sufficient for both 100 and 2000 users; disk storage and synchronization bandwidth are the real sizing factors, not CPU. **Point settled for the growth trajectory beyond 2000 users**: Seafile's clustering/horizontal scaling (several front-end nodes behind a load balancer, sharing a common memory cache) is documented exclusively for the **Pro edition** (proprietary, paid) — no official clustering documentation exists for the Community edition. Concretely: the Community edition remains single-node, scalable only vertically (more CPU/RAM/disk on the same machine), which has a mechanical limit. **This point partly calls into question the goal of staying all-open-source at very large scale**: beyond the threshold where vertical scaling of a single Seafile Community node is no longer sufficient, the only documented path to continue growing is to switch to Seafile Pro (paid license), which must be anticipated in the budget for the growth trajectory rather than discovered once the load wall is hit.

---

### 1.5 Collaborative document editing (replaces Word/Excel/PowerPoint Online)

**Functional need**
Real-time collaborative editing of office documents (word processing, spreadsheet, presentation), compatibility with existing Office formats (ten years of archives to keep), integration with file storage.

**Possible alternatives**
- **OnlyOffice (Community Edition, Document Server)**.
- **Collabora Online (CODE)**: a suite based on the LibreOffice engine, compared in detail below.

**Comparison table — OnlyOffice and Collabora Online**

| Criterion | OnlyOffice (Community/Docs) | Collabora Online (CODE) |
|---|---|---|
| **Engine / native format** | Own engine, native **OOXML** format (.docx/.xlsx/.pptx) — Word/Excel/PowerPoint files are read and written directly, with no conversion step | **LibreOffice** engine, native **ODF** format — every OOXML file goes through a conversion on open and save |
| **Fidelity of Word/Excel/PowerPoint compatibility** | Recognized as the product's strong point, due to the native format shared with Microsoft Office | Good general compatibility, but ODF↔OOXML conversion can introduce formatting discrepancies on complex documents (macros, presentations with embedded media) |
| **Core license** | AGPLv3 | Mozilla Public License 2.0 |
| **Limit of the free edition** | **Lifted since version 9.4** (May 2026): no more cap on concurrent connections on the Community edition (see 1.5 above) | **Permanent and openly acknowledged cap**: the free edition (CODE) remains limited to 10 documents / 20 concurrent connections by design — the vendor explicitly presents it as not intended for production ("not recommended for a production environment"), unlike a cap meant to disappear |
| **Way out of the cap** | None needed: Community Edition ≥ 9.4 can be used in production with no connection limit, with no recurring licensing cost | Requires a paid subscription (Collabora Online / Enterprise) to lift the cap and get support — annual subscription model |
| **Seafile integration** | Official connector documented by OnlyOffice | **Also officially documented**, by Seafile itself (`OFFICE_SERVER_TYPE = 'CollaboraOffice'` setting, WOPI protocol) — this criterion therefore does not differentiate the two solutions, contrary to what one might assume |
| **Architecture / dependencies** | Simplified since version 9.4 (single process, removal of RabbitMQ and external databases) | Architecture claimed to be minimal by the vendor (Linux + WOPI protocol), with no dependency on a message bus or a dedicated database |
| **Vendor / jurisdiction** | Ascensio System SIA, registered in Latvia (EU) — **a point to be nuanced, see note below** | Collabora Productivity Ltd, Cambridge, United Kingdom |

**Conclusion of the comparison**: the point that is genuinely decisive for this project is the **connection cap of the free edition**. OnlyOffice's disappeared in 2026 and the Community edition becomes fully usable in production with no recurring licensing cost. Collabora's (CODE) is **permanent and acknowledged by the vendor itself**: scaling with Collabora requires a paid subscription, which reintroduces exactly the kind of recurring licensing cost this project is trying to eliminate — a point that carries significant weight given the firm's growth ambition (100 → 2000+ users). On format compatibility, the advantage goes to OnlyOffice due to its native format shared with Microsoft Office, which directly matches the stated functional need (ten years of Office archives to keep).

**Euro-Office — the sovereign fork of OnlyOffice, analyzed in detail**

**Context**: on March 27, 2026, a consortium of European players (Nextcloud, IONOS, Proton, XWiki, OpenProject, Eurostack, Open-Xchange, BTactic, Soverin, Abilian) launched **Euro-Office**, a fork of OnlyOffice Document Server. Explicitly stated motivation: Ascensio System SIA, the vendor of OnlyOffice, is registered in Latvia (EU), but according to the consortium a significant part of its development team is said to be based in Russia — a point the vendor itself does not openly deny. This is exactly the type of dependency this project is trying to eliminate (see Introduction), on a par with the Outlook for Mac issue (1.9) or Zimbra's shift to a paid model (table above).

**What speaks in favor of Euro-Office**
- **A genuine drop-in, not merely a façade**: the code is directly derived from OnlyOffice Document Server and keeps the same REST API — integrators (Nextcloud, ownCloud, and by extension any connector designed for OnlyOffice such as Seafile's) should work with no modification. This is not confirmed by name for Seafile at this stage, but follows directly from the nature of the fork.
- **A fully free model, with no paid edition of its own**: unlike OnlyOffice, which keeps paid Enterprise/Developer editions above the now-unlimited Community Edition, Euro-Office has announced no equivalent commercial offering — funded by direct contributions from the consortium's member companies rather than by license sales.
- **Governance and brand image aligned with the sovereignty logic already maintained in this document.**

**What calls for caution, before any replacement**
- **A very young project**: first stable release dated June 9, 2026, barely three months before this document was written. A member of the Cloudron community sums up the risk well: "*first stable is literally days old, so expect rapid version churn*." This is the same level of caution this document already applies to other very recent features (Grommunio's CardDAV GAL, EAS-4-TbSync) — new is not disqualifying, but it does require validation before production adoption.
- **Unresolved legal dispute**: Ascensio System accuses Euro-Office of having violated the AGPLv3 license's trademark and attribution clauses (section 7) by removing the OnlyOffice logo and mentions from the code. The consortium disputes this. As long as this dispute is unresolved, doubt hangs over the stability of the fork's name, brand, and even its legal status in the medium term — a risk not to be transferred onto a client's infrastructure without being aware of it.
- **Technical architecture possibly less simplified than OnlyOffice ≥ 9.4**: Euro-Office 1.0 appears to be derived from a version of OnlyOffice predating the 9.4 architectural simplification (single process, removal of RabbitMQ/external database, see above) — its documentation still mentions a full Node.js/PostgreSQL/RabbitMQ/Redis/nginx stack. **To be explicitly verified** before any switch: has Euro-Office also inherited the removal of the connection cap, or does it start from the pre-9.4 base that still imposed it?
- **An irony noted by the community itself, worth mentioning for the record without drawing a disqualifying conclusion from it**: the project's repository is hosted on GitHub, a platform owned by Microsoft — an amusing detail given the "sovereign" positioning, but one that does not call into question the sovereignty of the code itself, only that of its development platform.

**Conclusion on this point**: **Euro-Office does not replace OnlyOffice Community ≥ 9.4 as the component selected in this document, at this stage** — the project is too young, an unresolved legal dispute is pending, and its alignment with OnlyOffice 9.4's architectural gains (removal of the connection cap and simplification) is not confirmed. **It is, however, identified as a serious candidate to re-evaluate in a future iteration of this document**, once its maturity, the outcome of the AGPL dispute, and its actual compatibility with the Seafile connector are established — the day these reservations are lifted, it would meet this project's sovereignty motivation better than OnlyOffice, without sacrificing the format compatibility that led to OnlyOffice being chosen over Collabora.

**Selection criteria**
- Word/Excel/PowerPoint format compatibility: a good level of compatibility recognized for OnlyOffice, reinforced by the comparison with Collabora above (shared native format vs. ODF↔OOXML conversion).
- Integration with Seafile: an official Seafile ↔ OnlyOffice Document Server connector exists, allowing online editing directly from storage (not just a viewer) — Collabora has an equally official Seafile integration, so this criterion alone does not distinguish between the two solutions.
- Historical Community Edition licensing limit: a cap of 20 concurrent connections, **removed as of version 9.4** (May 2026), which also simplified the architecture (single process, removal of the RabbitMQ dependency and external databases), reducing resource consumption — a decisive advantage over Collabora CODE's permanent cap (see table above).
- Sizing at real scale: a public benchmark (Enterprise Edition v6.3) puts the maximum guaranteed load at ~1000 concurrent connections on a 4-core / 8 GB RAM / 8 GB swap server. A connection corresponds to a browser tab with a document open for editing (the same document opened by two users counts as two connections); beyond capacity, additional documents open in read-only mode with no error or crash.

**Conclusion — component selected**
**OnlyOffice Community Edition (≥ 9.4)**, integrated with Seafile via the official connector.

For a load scenario of the "100 consultants × 20 documents open in parallel" type (2000 potential connections):
- Order of magnitude for sizing: ~8 cores / 16 GB RAM minimum, with margin, to be validated by a real load test (JMeter) before going into production.
- Plan for active monitoring of the connection count to detect the switch to read-only before users complain.
- Recommended target architecture beyond a certain threshold: a Document Server cluster with a load balancer and Redis session storage, rather than a single instance. **Given the firm's growth ambition, this cluster architecture should be adopted as the target from the initial design**, rather than as a later evolution — moving from a single instance to a horizontal cluster is easier to plan for in the infrastructure (Chapter 4) than to retrofit once the load has become critical.
- Important nuance: the sizing above assumes simultaneous active editing on all open documents; if a significant share of documents are open in the background without active editing, the actual load is lower than the worst case.

---

### 1.6 Task management (replaces Planner/To Do)

**Functional need**
Individual and team task management, shared lists, deadlines.

**Possible alternatives**
- **Vikunja**: lightweight application (Go + database), open API.
- **OpenProject**, **Focalboard**, **Planka**: compared below.

**Comparison table — Vikunja and task management alternatives**

| Criterion | Vikunja | OpenProject | Focalboard | Planka |
|---|---|---|---|---|
| **Positioning** | Lightweight task manager with multiple views (list, Kanban, Gantt, table) | Full project management suite (Gantt, resource planning, cost tracking, audit trails) | Notion/Trello-style boards, from the Mattermost ecosystem | Pure Kanban board, focused on visual simplicity |
| **Age / community** | 7-8 years, ~4,400-5,000 GitHub stars | 13 years, ~15,000 stars — a notably larger community | 6 years, ~26,000 stars — but development activity has slowed (last commit several months apart, versus a few hours for Vikunja) | In development since 2019, ~11,000-12,000 stars |
| **Current maintenance activity** | Very active (commits a few hours apart) | Very active | Slowed in recent months compared to Vikunja | Active |
| **Calendar integration (CalDAV)** | Native | Available but secondary within a broader suite | Not emphasized | Not emphasized |
| **Fit with the stated need** (individual/team task management, shared lists, deadlines — not a full PM tool) | **Matches the scope precisely** | **Overkill**: designed for organizations managing several concurrent projects with audit trails and fine-grained permissions — disproportionate complexity and operating burden relative to a "Planner/To Do" need | Relevant for visual boards, but without the structured deadline tracking or calendar integration expected | Relevant for simple Kanban, but more limited than Vikunja for structured individual task tracking (lists, deadlines, subtasks) |

This comparison confirms the initial choice rather than calling it into question: **OpenProject would be a poor bet** — not because it is worse, but because it solves a broader problem (full project management) than the one posed here (replacing Planner/To Do), at the cost of unnecessary complexity and operating burden. **Focalboard and Planka** remain relevant for pure board/Kanban use, but match less well the explicit need for deadline tracking and calendar integration. Vikunja remains the best-calibrated choice for the exact functional scope requested, with the added advantage of currently more sustained development activity than Focalboard.

**Selection criteria**
- Lightness and ease of deployment.
- Recognized limit: more limited than a true project management tool if needs grow in complexity (task dependencies, advanced Gantt views, etc.) — a scenario in which **OpenProject would again become relevant to re-evaluate**, should the firm's need evolve beyond a simple Planner/To Do replacement toward true cross-cutting project management.

**Conclusion — component selected**
**Vikunja**, for its simplicity-to-functional-coverage ratio, sufficient for the Planner/To Do scope. Sizing: 2-4 cores / 4 GB RAM, sufficient for both 100 and 2000 users unless there is heavy API/automation usage.

---

### 1.7 Authentication and identity (SSO)

**Functional need**
Federated single sign-on across the entire stack, centralized account and access management. In addition, there is a need for **multi-factor authentication (MFA)**, with several channels available depending on context and the desired security level: authenticator app (TOTP, e.g. Google Authenticator/FreeOTP), SMS, one-time password by email, and hardware key (e.g. Yubikey) via the open **WebAuthn/FIDO2** protocol.

**Possible alternatives**
- **Keycloak**: the reference open-source IAM/SSO solution, OIDC/SAML support.
- **Authentik**, **Zitadel**, **WSO2 Identity Server**: compared below.

**Comparison table — Keycloak and IAM/SSO alternatives**

| Criterion | Keycloak | Authentik | Zitadel | WSO2 Identity Server |
|---|---|---|---|---|
| **License** | Apache 2.0, no separate paid edition | MIT (permissive), advanced features under a separate enterprise license | Apache 2.0 until 2025, moved to **AGPLv3** since — implies publishing any modification if the service is exposed over a network | Apache 2.0, with optional commercial subscriptions for support and managed hosting |
| **Protocols covered** | OIDC, SAML, **LDAP** (federation and brokering), the broadest of the three | OIDC, SAML, LDAP, RADIUS, Kerberos — even broader coverage on paper | OIDC/OAuth only — **no LDAP or RADIUS server** | OIDC, SAML, WS-Federation, SCIM — comprehensive on paper, but SAML has historically been treated as secondary compared to Keycloak according to several comparisons |
| **Native "forward-auth" / proxy mode** | Not native — requires a dedicated third-party component for the rare applications with no OIDC support | **Native** ("Authentik Outposts") — allows protecting an application that speaks neither OIDC nor SAML directly, without a separate third-party component | Absent — applications must natively support OIDC/SAML | Absent |
| **Target design** | Broad, multi-protocol identity federation, for heterogeneous environments with legacy applications | Flexible, aimed at self-hosters and small/medium organizations with a mix of applications (including some with no native SSO) | **Multi-tenant B2B SaaS** — an Instance > Organization > Project > Application hierarchy designed to host multiple client organizations, not this project's profile (a single firm) | **CIAM** (management of external *customer* identities) above all, packaged within a broader integration platform (API management, enterprise integrator) — relevant for an organization already using the WSO2 ecosystem, which is not the case here |
| **Integration with the project's IaC approach** | Official, mature Terraform provider — consistent with the IaC approach adopted in Chapter 4 | No official Terraform provider identified | No official Terraform provider identified | **No Terraform provider** — more manual configuration, at odds with the systematic IaC approach adopted in this document |
| **Installation/configuration complexity** | Described as simple in community comparisons | Reputed to be accessible (visual flow editor) | Modern interface, simple OIDC configuration | **Described as complex** in several community comparisons, due to its middleware architecture (WSO2 Carbon), heavier than Keycloak's |
| **Maturity / ecosystem** | The oldest and most widely deployed in enterprises of the three, the most abundant documentation | Very rich integration ecosystem (200+), backed by a vendor company (Authentik Security Inc.) | Younger, but active development (~14,000 GitHub stars mid-2026) | Mature (first versions in 2008), but designed and documented above all for CIAM/API scenarios, not for pure internal identity federation |

**What this comparison reveals most interestingly for this project**: **Authentik's native forward-auth mode** would have been directly relevant to a need initially identified elsewhere in this document — the delegated authentication considered ahead of Lufi (1.8), which did not natively support OIDC. This specific need has since been resolved differently: the comparison conducted in 1.8 led to selecting Gokapi instead of Lufi, precisely because Gokapi natively supports OIDC and therefore no longer needs a separate `oauth2-proxy` component or a forward-auth mode. The point remains useful to note, however: for any future component in the stack that does not natively speak OIDC/SAML, choosing Keycloak will require adding an `oauth2-proxy` component (or equivalent) in `forward_auth` mode, whereas Authentik would have covered this case natively.

**WSO2, on the other hand, does not call anything into question**: it is a mature and genuinely open-source solution (Apache 2.0), but designed and packaged primarily for **CIAM** (managing external customer identities, often coupled with API management) — a different profile from this project's need, which is purely internal identity federation for the firm's consultants. Two concrete points weigh against WSO2 for this specific project: the **absence of an official Terraform provider**, at odds with the systematic IaC approach adopted in Chapter 4, and **installation/configuration reputed to be more complex** than Keycloak's due to its middleware architecture (WSO2 Carbon).

This is not enough, however, to tip the choice toward Authentik either: Keycloak remains better positioned for this project as a whole, for three reasons that outweigh the sole forward-auth point: (1) Keycloak's LDAP federation and SAML brokering are more mature and broader, useful should the firm ever need to federate an existing corporate directory or interact with partners over SAML; (2) it is the most proven solution in heterogeneous enterprise environments, exactly this project's profile (Grommunio, Seafile, Vikunja, OnlyOffice, Matrix/Synapse); (3) Zitadel is structurally ruled out, its multi-tenant B2B model not matching a single-organization deployment, and its recent move to AGPLv3 requiring additional compliance vigilance. **The need initially identified for Lufi (1.8) is ultimately resolved without any forward-auth at all**, thanks to choosing Gokapi over Lufi — but the point deserves to be noted explicitly for any future component with no native OIDC support, rather than discovered after the fact.

**Selection criteria**
- Native OIDC compatibility of each component in the stack: to be verified service by service (Grommunio, Seafile, Vikunja and OnlyOffice support OIDC; Matrix/Synapse as well, via an OIDC provider).
- Sizing driven by the number of connections per second, not by the total number of users.
- **Keycloak's native MFA coverage, channel by channel**:
  - **Authenticator app (TOTP/HOTP)**: natively supported, no development required — configurable directly in standard authentication flows.
  - **Hardware key (Yubikey and equivalents) via WebAuthn/FIDO2**: natively supported by Keycloak, both as a second factor and as a passwordless primary factor (passkey) — this is the open, standardized protocol (W3C/FIDO Alliance) you had in mind, and it covers both dedicated hardware keys and platform authenticators (Touch ID, Windows Hello).
  - **SMS one-time password**: **not natively covered by Keycloak** — requires developing a custom connector (Keycloak Service Provider Interface) linked to an SMS gateway, or a third-party extension.
  - **Email one-time password**: **not natively covered by Keycloak** either, for the same reason — also to be developed via a custom SPI.
- These last two channels (SMS, email) therefore join the list of connectors to be developed identified elsewhere in this document (see Chapter 2), rather than being simple checkboxes in Keycloak's configuration.

**Conclusion — component selected**
**Keycloak**, as the central SSO/IAM for the entire stack, with **TOTP and WebAuthn/FIDO2 enabled natively** from initial deployment (no development required for these two channels). **SMS and email OTP require developing a custom Keycloak SPI** — to be treated as a full development project, not a simple configuration option, and to be prioritized according to the channels actually requested by consultants (the TOTP + WebAuthn pairing already covers a high security level, including phishing resistance for WebAuthn). Sizing: 2-4 cores / 4-8 GB RAM with a dedicated Postgres database, for both scales (100 and 2000 users) in standard office use. Point of vigilance: plan for a highly available Keycloak cluster from the initial target, as SSO becomes a critical single point of failure for all other services — all the more critical along a growth trajectory, since any Keycloak outage would block access to the entire stack for an ever-larger headcount. Keycloak is natively designed for horizontal clustering (several nodes behind a load balancer, distributed cache), which poses no known difficulty in following the firm's growth beyond 2000 users.

---

### 1.8 Making large files available with in-browser encryption

**Functional need**
Occasionally transmit a large file to a recipient (internal or external to the firm) via a simple link, without the size constraints of email attachments, and with a strong confidentiality guarantee — including against the platform administrator itself. This is a distinct need from the structural file sharing covered by Seafile (1.4): here it is a one-off, short-lived drop, designed for external exchange. In addition, there is a need to restrict deposits to authenticated persons, to prevent the instance from being used to anonymously host illicit files.

**Possible alternatives**
- **Lufi** (`ldidry/lufi`): a large-file drop tool with encryption performed entirely in the browser.
- **Gokapi** (`Forceu/Gokapi`): an alternative compared in detail below.
- Commercial services such as WeTransfer — ruled out, contrary to the project's sovereignty logic and without an equivalent end-to-end encryption guarantee.
- A simple Seafile share link — does not provide end-to-end encryption: the Seafile server has clear-text access to the content of the shared file.

**Comparison table — Lufi and Gokapi**

| Criterion | Lufi | Gokapi |
|---|---|---|
| **End-to-end encryption** | **Systematic**: every drop is encrypted client-side, with no option to disable this behavior. Key encoded in the URL anchor fragment (`#`), never sent to the server. | **Optional, at three levels**: level 1 (local files only), level 2 (local + cloud storage, client-side decryption), level 3 = true E2EE (client-side encryption, a compromised server can reveal nothing). Level 3 must be **explicitly chosen at configuration time**, it is not the default behavior. **Warning from the vendor itself: the encryption has not been audited.** |
| **Deposit authentication** | Native, but **LDAP only** — no OIDC/SAML support, incompatible with a direct connection to Keycloak. | **Native OIDC support documented**, with identity providers named explicitly, including Keycloak — a direct connection to the SSO already selected (1.7), with no intermediate component. |
| **User management** | Basic (authentication only) | **Multiple accounts with fine-grained permissions per user and per API key** — each deposit is natively tied to an account, not just tracked after the fact. |
| **Traceability of the depositor** | Not native — requires external correlation between reverse-proxy logs and the file identifier (see former architecture below) | **Native**: each deposited file is directly linked in the database to the authenticated user who deposited it, with no external correlation to build. |
| **Maturity of the E2EE implementation** | Proven at large scale (Framasoft has run it in production under the name Framadrop for several years) | More recent, **not audited according to the vendor**; a known Firefox compatibility bug exists that can truncate files downloaded in E2EE. |
| **Special case of external drops ("File Request")** | N/A (no equivalent mechanism) | A feature allows generating a link for external third parties to drop a file without an account — but **these drops bypass E2EE**, stored without level 3 even if it is otherwise enabled on the server. Not to be used if confidentiality must remain guaranteed for all drops. |
| **License / ecosystem** | AGPL, Perl/Mojolicious, rooted in the French-speaking free-software ecosystem | AGPL-3.0, Go, lightweight (256 MB RAM minimum), active (2.8k GitHub stars) |
| **API/CLI** | Command-line client and scriptable API | Full REST API, dedicated CLI (`gokapi-cli`) |

**What this comparison settles**: the decisive point is Gokapi's **native OIDC authentication**, which directly and simply answers the drop-restriction need stated above — without the detour through LDAP or a separate `oauth2-proxy` component that Lufi would have required (see former, now obsolete, architecture, kept as a historical note at the end of this section). In return, two serious reservations must be made explicit before production deployment: Gokapi's E2EE encryption has **not been audited** (versus a Lufi implementation proven at large scale), and the E2EE option must be **explicitly enabled** (level 3) rather than being the default behavior — a configuration point not to be missed, otherwise the end-to-end confidentiality guarantee would only be apparent.

**Selection criteria**
- The need for strong confidentiality remains covered by Gokapi **provided encryption level 3 is explicitly enabled** — this is not automatic, unlike Lufi, where it is the only possible mode of operation.
- The need to restrict deposits to authenticated persons is better covered natively by Gokapi (direct OIDC to Keycloak) than by Lufi (LDAP only), which would have required either a second LDAP directory or an `oauth2-proxy` connector in `forward_auth` mode in front of the reverse proxy.
- Gokapi's "File Request" feature (deposit by an external third party with no account) should **not** be enabled for this project, or only knowingly: it bypasses E2EE, which would break the confidentiality guarantee for those specific deposits.
- Gokapi's unaudited encryption is a risk to document explicitly with the firm, weighed against the OIDC integration gain — an independent security audit, or failing that active monitoring of the project's security issues, is recommended before a large-scale deployment.
- Keycloak configuration to be followed with particular vigilance: Gokapi's changelog explicitly mentions a correction to its Keycloak documentation after an earlier configuration example allowed unauthorized access — **the up-to-date documentation must be used at deployment time**, not an archived example or an old screenshot.

**Traceability of the deposit**
Unlike the architecture Lufi would have required (correlation between reverse-proxy logs and the file identifier, see the historical note below), Gokapi natively associates every deposited file with the authenticated user account in its own database — traceability requires no external connector or logging to develop. What remains to be defined: the retention period for these internal logs (consistent with legal obligations to retain connection data, LCEN for a service accessible in France), and the reporting/takedown procedure — who, on the firm's side, is authorized to look up the file/depositor association upon a report from a third party or authority, and to trigger deletion of the file.

**Conclusion — component selected**
**Gokapi**, self-hosted, replacing the initially considered Lufi — for the occasional provision of large files requiring enhanced confidentiality, complementing Seafile which remains the structural, long-term file-sharing component (1.4). The choice is justified by native OIDC authentication to Keycloak (1.7), which avoids any intermediate component, and by natively built-in deposit traceability rather than one that has to be reconstructed. **Two conditions must absolutely be met at deployment**: explicitly enable encryption level 3 (E2EE) rather than relying on a less protective default, and do not enable the "File Request" feature if confidentiality must remain guaranteed for all deposits. Gokapi's unaudited encryption remains a point of vigilance to document with the firm, without being disqualifying given the integration gain obtained.

**Historical note — architecture initially envisaged with Lufi (kept for the record)**
Before the comparison above, authentication for the Lufi deposit had been designed via delegated authentication at the reverse-proxy level (Caddy + `oauth2-proxy` in OIDC), since Lufi only natively supports LDAP: `oauth2-proxy` would have been deployed as a dedicated container in Kubernetes (see 4.3), configured as a confidential OIDC client in a Keycloak realm, with a `forward_auth` directive on the deposit routes only (the download and deletion routes remaining ungated to allow external use). Traceability would then have relied on logging on the reverse-proxy side (identity, timestamp, IP) correlated after the fact with the Lufi file identifier — an external correlation that Gokapi makes unnecessary thanks to its native user-account model.

---

### 1.9 Full-featured desktop mail client (complement to grommunio-web)

**Functional need**
Beyond webmail (grommunio-web) and mobile clients (1.1), some consultants want a native full-featured desktop mail client (Windows, Mac, Linux), with full access to mail, calendar and contacts against Grommunio — without depending on a Microsoft account or license to obtain it.

**Possible alternatives**
- **Thunderbird**: an open-source full-featured mail client, already selected elsewhere in this document as the anchor point for the Filelink mechanism for large-file drops (1.8, 2.11). Connects natively to Grommunio over EWS (natively supported by Grommunio without a plugin since version 2023.11.3) or over IMAP/CalDAV/CardDAV for the mail/calendar/contacts base — on the longevity of this protocol on the Grommunio side despite its announced retirement by Microsoft on Exchange Online, see the additional note in 1.1.
- **Apple Mail / Calendar / Contacts (native macOS)**: Grommunio documents native compatibility with the Apple suite via EWS for mail and CalDAV/EWS for calendar, CardDAV for contacts — no third-party client to install on Mac. On exposing the corporate directory (GAL) to this client via CardDAV, see 2.13.
- **Outlook for Mac**: specifically evaluated on request, see below.
- **eM Client**: evaluated as a complement on request, see note below.

**Is Outlook for Mac available without an Office 365 subscription?**
**Yes, but that is not the right decision criterion for this project.**
- **Confirmed availability**: since 2023, the "new Outlook" for Mac is free and no longer requires a Microsoft 365 subscription or Office license to install and use — it is even available directly on the Mac App Store, with a free version (ads shown for free personal accounts such as Gmail/IMAP, no ads for a professional account). Grommunio in fact explicitly documents its compatibility with this client via EWS.
- **The real problem is not the license, it is the "new Outlook's" network architecture**: unlike the old ("legacy") Outlook, which connected directly to the configured mail server, the new Outlook for Mac (like its Windows/iOS/Android equivalents) works as a gateway to the Microsoft cloud for any non-Microsoft account — including an account configured over EWS pointing to a self-hosted Exchange-compatible server such as Grommunio. Concretely: login credentials and a copy of messages/calendar/contacts pass through Microsoft's servers (Azure infrastructure), which themselves connect to the Grommunio server on the user's behalf, before relaying the data to the client. This mechanism is documented by Microsoft itself (the "Sync with Microsoft Cloud"/"Sync your account in Outlook to the Microsoft Cloud" feature) and has been the subject of reports from data-protection authorities in Europe (including the German Federal Commissioner for Data Protection).
- **Direct incompatibility with the project's original motivation**: this mechanism places a copy of the firm's mail content — potentially confidential correspondence with its clients — on the infrastructure of a non-European vendor, exactly the dependency this project is trying to reduce (see Introduction). Choosing Outlook for Mac would mean reintroducing, on the mail client side, the dependency that Grommunio precisely made it possible to eliminate on the server side.
- **The old ("legacy") Outlook, which connects directly without a Microsoft relay, is not a viable alternative either**: its continued availability requires either a Microsoft 365 subscription or a one-time-purchase Office license (2021/2024) tied to a personal Microsoft account or a volume license — thus a Microsoft licensing cost to be maintained precisely to avoid the one this project is trying to remove from the equation. Its end of support has moreover already begun for accounts under a Microsoft 365 subscription, with a complete end of life documented by Microsoft by October 2029 at the latest depending on the licensing channel.

**Additional note — eM Client, a third-party alternative to Outlook**
eM Client is a full-featured mail client competing with Outlook, published by a Czech company (eM Client s.r.o., Prague), with mail (IMAP/POP/EWS), calendar and contacts (CalDAV/CardDAV), tasks, notes and integrated chat. Two points to distinguish from the Outlook for Mac analysis above:
- **Network connection**: unlike the new Outlook, eM Client connects directly to the configured EWS/CalDAV server, with no proprietary cloud relay mechanism — user feedback explicitly describes it as independent of any third-party cloud ecosystem. No indication to the contrary was found. On this specific point, it would therefore be compatible with the project's sovereignty objective, unlike the new Outlook.
- **License**: **proprietary, not open-source** software — free for up to 2 accounts in non-commercial use, paid (~$40/year) beyond that for professional/unlimited use. It is a European company (consistent with the sovereignty logic already maintained for Visio/PeerTube/Tchap), but the code is neither open nor auditable, unlike Thunderbird and the rest of the stack selected in this document.

**eM Client is not selected as a component of the project**: it brings nothing that Thunderbird does not already offer (same connection protocols to Grommunio) while introducing a dependency on a proprietary vendor and a per-user licensing cost beyond two accounts — contrary to the all-open-source principle sought by this project. It remains mentioned here as an individual fallback option should a consultant prefer its ergonomics to Thunderbird's, without the firm making it a deployed standard.

**Selection criteria**
- Direct connection to the Grommunio server with no third-party relay, to remain consistent with the sovereignty objective set out in this document's Introduction.
- Genuine freeness, with no residual dependency on any kind of Microsoft license (neither subscription nor one-time purchase).
- Confirmed EWS compatibility on the Grommunio side for all clients selected.

**Conclusion — component selected**
**Thunderbird** as the reference cross-platform full-featured client (Windows/Mac/Linux), complemented on Mac by the native **Apple Mail/Calendar/Contacts** suite for consultants who prefer system integration over a third-party client — both connecting directly to Grommunio over EWS, with no third-party cloud intermediary. **Outlook for Mac is explicitly ruled out**, not for a licensing-cost reason (its current version is free), but because its network architecture routes mail data through Microsoft's cloud infrastructure even for an account pointing to a self-hosted server — which directly contradicts the data sovereignty objective motivating this entire project.

**Configuration point — disabling Thunderbird's built-in Matrix chat**
Thunderbird natively embeds a Matrix-compatible "Chat" account type, distinct from its mail function. This is not a credible alternative to Element (1.2) for the firm's corporate chat use: **confirmed** by official Mozilla documentation, Thunderbird's Matrix implementation supports neither end-to-end encryption (in an encrypted room, received messages display as raw, unreadable encrypted JSON, with no client-side decryption possible), nor reloading of room history (only messages unread at connection time and new messages appear), nor media (text only). Support for slash commands specific to the Matrix/Element ecosystem is not documented either, which is consistent with an implementation reusing Thunderbird's old generic chat engine rather than a UI designed for Matrix.

Beyond usability, this point touches on perceived security: the stack adopts Matrix with E2EE enabled by default on private rooms (1.2) — a consultant who accidentally enabled Thunderbird's Matrix chat would find themselves facing unreadable encrypted rooms, with no clear indication of why, risking confusion about the actual confidentiality of the exchange. **Recommendation: disable this module in the standard Thunderbird configuration/deployment** (no preconfigured Chat account, and block its creation via `policies.json`/preference lockdown if a centralized deployment is in place), to channel all chat usage toward Element — consistent with the role selected here for Thunderbird, strictly mail/calendar/contacts.

---

## Chapter 2 — Integration between the building blocks

Choosing a "best of breed" stack (each component optimal in its own scope) comes with the trade-off of no native integration between components that were not designed together — unlike an integrated suite such as Office 365 (Microsoft Graph) or DINUM's La Suite numérique, whose components (Tchap, Visio, Docs) are developed by the same team and natively integrated with each other.

This chapter addresses, topic by topic, the cross-cutting integration needs identified.

### 2.1 Unified notification center

**Functional need**
A single entry point aggregating notifications from all services (new Matrix message, Grommunio mail, shared Seafile file, assigned Vikunja task), the way Teams does for the Microsoft ecosystem.

**Possible alternatives**
- **ntfy**: a simple push notification server, pub/sub by topics — lightweight but with no rich notification-center UI.
- **Novu**: a notification infrastructure with a ready-to-use in-app notification center, multi-channel, per-channel preference management.
- **Nextcloud (Dashboard + Notifications API)**: an existing, documented pluggable framework (OCS API), already used by dozens of third-party integrations — but would require porting a PHP stack judged dated just to get an aggregation pattern.
- **Custom microservice** (Go/Node) reusing only the aggregation pattern (parallel fan-out + per-source timeouts), without porting the Nextcloud ecosystem.

**Selection criteria**
- Do not introduce a heavy stack (PHP/monolith) just to get an aggregation pattern reproducible in a few hundred lines.
- Consistency with the rest of the stack, already oriented toward modern, lightweight tools (Vikunja in Go, Matrix alternatives in Rust).
- The hard part, whichever tool is chosen, remains ingestion: no notification manager natively "speaks" Matrix/Grommunio/Seafile/Vikunja — a connector per service is needed to translate each event.

**Conclusion — component selected**
**Novu** for the notification-center UI and multi-channel infrastructure, fed by custom connectors per service (Matrix Application Service webhook, Grommunio webhook/IMAP, Seafile webhook, Vikunja webhook). Developing the connectors is the real project, regardless of the tool chosen.

### 2.2 Unified search

**Functional need**
A single search box allowing a message, mail, file, or task to be found, regardless of the source service.

**Possible alternatives**
- **Pre-computed central index** (e.g. Elasticsearch/Meilisearch): fast at query time, but requires continuously replicating and maintaining each source service's ACLs in the index — under penalty of a permission leak (a user sees a result appear that they do not have access to in the source service).
- **Real-time fan-out**: each search queries the native APIs of every service in parallel (Matrix `/search`, Seafile, Vikunja `search=`, Grommunio via IMAP SEARCH), with the user's Keycloak token relayed to each call — permissions are respected natively since it is the source service that filters.

**Selection criteria**
- Security by design: real-time fan-out avoids the risk of faulty ACL synchronization inherent to a central index.
- Perceived latency: by parallelizing requests, the total response time is bounded by the slowest service (not the sum of each service's response times), provided a per-service timeout is set so that one stuck service does not block the entire search.
- Possible UX improvement: progressive display of results as they arrive (Server-Sent Events/WebSocket) as each service responds, rather than waiting for all services to reply.

**Conclusion — component selected**
**Real-time fan-out**, reusing the same ingestion/connector component as the notification center (development is shared). The option of a pre-computed central index is only re-evaluated if fan-out latency becomes a real usability problem at scale, with ACL synchronization then treated as a dedicated security project in its own right.

### 2.3 Application portal and cross-application navigation menu

**Functional need**
A common banner/menu overlaid on the applications (quick access to the various services, notification bell, search box), without having to rebuild each application.

**Possible alternatives**
- **Iframe-based portal** (e.g. Dashy/Organizr/Homarr) embedding each application within a common frame.
- **HTML injection at the reverse-proxy level** (Nginx `sub_filter`, or a Caddy plugin such as `caddy2-html-injection-plugin`): the proxy rewrites each application's HTML on the fly to insert the banner, with no changes to the applications' code.
- **Static home page of links** (no full application dashboard), for the sole need of links/deep links to native applications.

**Selection criteria**
- The iframe portal raises genuine security concerns for embedding entire applications: the need to loosen `X-Frame-Options`/`frame-ancestors` on every service (widening the clickjacking attack surface), increasing browser restrictions on third-party cookies in an iframe context that can silently break SSO, sometimes degraded browser API behavior (notifications, WebRTC) in an iframe context.
- HTML injection is fragile to version upgrades of each application (the DOM anchor point can move) and requires managing CSP headers, but is more proportionate for a lightweight banner (menu + bell + search) that does not seek to embed each application's full content.
- For the specific case of a single video widget (Visio DINUM) inside a Matrix room, the iframe is on the other hand justified and well scoped: a single targeted widget, not an entire application, with explicit and documented configuration of iframe permissions on the source application side (a case distinct from the global portal).

**Conclusion — component selected**
**HTML injection via the reverse proxy (Caddy + injection plugin)** for the lightweight cross-cutting banner (menu, notification bell, search box), with each application otherwise remaining in native full-screen navigation — no iframe portal embedding the full applications. The iframe remains used occasionally and in a targeted way for the video conferencing widget in Matrix rooms (see 2.4).

### 2.4 Continuity of the text discussion thread before/during/after a video conference

**Functional need**
Have the same text discussion thread accessible before the meeting (planning), during it (exchanges alongside the video), and after it (searchable history) — as Teams allows by associating chat and meeting with the same channel.

**Possible alternatives**
- Rely on Visio DINUM's native built-in chat.
- A Matrix widget embedding Visio DINUM in an Element room (a generic mechanism already historically used to integrate Jitsi into Element).
- **Element Call**, natively integrated into Matrix rooms via the MatrixRTC protocol.

**Selection criteria**
- Visio's (LaSuite Meet) native chat is confined to the meeting session: it does not persist before/after the meeting the way a Teams channel would, and disappears once the meeting ends. **Ruled out** as a continuity solution.
- The Matrix widget mechanism is generic and proven (already used for Jitsi): the Element room remains the sole persistent thread, and the video widget displays alongside it for the duration of the call. Requires verifying that the embedded video application allows the iframe (`frame-ancestors`) — not a blocker here since Visio is self-hosted, so this setting is under direct control.
- Element Call is natively a Matrix room widget, requiring no integration development, but does not cover the PSTN need identified as a requirement (accessibility, participants with no IP access).
- **A precedent already exists**: Tchap (an Element fork developed by the French State, co-funded with Linagora) offers a `/visio` command to start a Visio meeting directly from a room, which constitutes a Matrix ↔ Visio DINUM integration reference already built and published as open source (MIT/AGPL license, `suitenumerique` GitHub repository).

**Conclusion — component selected**
Reuse/adapt the `/visio` integration already developed by Tchap rather than build a Matrix ↔ Visio DINUM connector from scratch. The video backend targeted by this connector is now confirmed (LiveKit, see 1.3), which removes the initial uncertainty. The widget must disable or hide Visio's internal chat to avoid confusion between two simultaneous text threads (one in the widget, one in the Matrix room).

### 2.5 Facilitating the installation of native applications (Mac, iOS, Android)

**Functional need**
Reduce the friction of installing and configuring the multiple native applications (Element, Seafile, Vikunja, Grommunio mail client) on consultants' Mac and mobile devices.

**Possible alternatives**
- **Full MDM with zero-touch enrollment** (Apple Business Manager + Android Enterprise, driven by a solution such as myMDM, Appaloosa or Headwind MDM): automatic, preconfigured push of applications as soon as the device is unboxed/provisioned.
- **Apple configuration profiles with no MDM server** (`.mobileconfig` file generated via Apple Configurator): preconfiguration of an account or setting, distributed by a simple link/QR code, with no server infrastructure.
- **Preconfigured application deep links** (e.g. `element://https://matrix.example.com` link for Element) combined with QR codes, together with a static onboarding page.

**Selection criteria**
- Full MDM is disproportionate for a consulting firm whose workstations are not necessarily all under full IT control (partial BYOD), and introduces a residual dependency on Apple Business Manager regardless of the MDM vendor chosen (Apple's zero-touch enrollment necessarily remains controlled by Apple).
- `.mobileconfig` profiles and deep links cover most of the initial installation friction with no server infrastructure to operate and no subscription.
- MDM retains real value if a fleet-management need arises (remote wipe, inventory, compliance) — but that is not the need initially stated (facilitating installation), which does not justify this investment.

**Conclusion — component selected**
A lightweight approach, with no MDM server:
1. A static onboarding page (HTML, behind Caddy) listing each application with an App Store/Play Store link and a preconfigured deep-link QR code.
2. An optional `.mobileconfig` file to preconfigure the Grommunio mail account (ActiveSync) on Mac/iPhone.
3. No MDM infrastructure until a remote fleet-management need is identified.

### 2.6 Absence of a dedicated chat within OnlyOffice

**Functional need**
Avoid duplicating a chat specific to OnlyOffice alongside the corporate Matrix chat, so as not to fragment document-related exchanges across two different tools.

**Possible alternatives**
- Disable OnlyOffice Document Server's internal chat module and redirect document-related exchanges to a dedicated Matrix room (one room per document or per Seafile workspace).
- Automatically generate a link to the associated Matrix room from the OnlyOffice toolbar.

**Selection criteria**
- **Confirmed**: OnlyOffice exposes a native, documented configuration setting to disable chat specifically, independently of comments — `document.permissions.chat: false` in the editor's configuration file, distinct from `document.permissions.comment` (which can remain enabled). This is therefore not an integration to develop, but a simple setting to configure for each opened document.
- Still to be built: automatically generating a link to the corresponding Matrix room in the OnlyOffice toolbar (a small display connector, not a modification of OnlyOffice's core).

**Conclusion — component selected**
**Disabling OnlyOffice chat via `document.permissions.chat: false`**, applied by default whenever a document is opened from Seafile, complemented by a link to the Matrix room associated with the document or workspace (a display connector to be developed, see 2.11).

### 2.7 `@user` mentions in document comments

**Functional need**
Being able to mention a colleague in a document comment (OnlyOffice) and trigger a notification to that person, as Office 365 allows in Word/Excel by @-mentioning a colleague via mail or Teams notification.

**Possible alternatives**
- Hook OnlyOffice's native mention event into the unified notification center (Novu, see 2.1).

**Selection criteria**
- **Confirmed**: OnlyOffice exposes a dedicated, documented mentions API. The `onRequestUsers` event provides the list of users proposed when typing the `+`/`@` sign in a comment; the `onRequestSendNotify` event fires when a comment mentioning someone is submitted, and passes the integrating backend the message, the list of mentioned emails, and an action link pointing directly to the comment's location in the document. It is up to the integrating application's backend (not OnlyOffice) to actually send the notification — exactly the entry point needed to feed the unified notification center.

**Conclusion — component selected**
**Implementing the `onRequestSendNotify` handler** in the Seafile↔OnlyOffice integration backend, to forward every mention to the unified notification center (Novu, 2.1) with the action link natively provided by the API — this connector joins the list of connectors to be developed in 2.1, without separate treatment.

### 2.8 Unified presence between Element, Grommunio and Visio

**Functional need**
Display a consistent presence status (online/away/in a meeting) across Element, Grommunio and Visio, rather than three independent and potentially contradictory statuses — for example, a consultant shown as "available" in Element while they are in a meeting on Visio.

**Possible alternatives**
- Do nothing: keep three independent presence indicators, each native to its own tool.
- Build a presence aggregator that queries each source and republishes a consolidated status on a common surface (the application-portal banner, see 2.3), rather than trying to inject this status into each application's native indicator.

**Selection criteria**
- Each component has its own notion of presence, with disjoint protocols: **Matrix** exposes a native presence API (`m.presence`, online/unavailable/offline states), queryable live both client-side and server-side. **Grommunio/EWS** does not publish presence as such, but allows deriving an "in a meeting" state from the calendar via the `GetUserAvailability` operation — similar to what the Cisco Unified Presence integration historically did by subscribing to the Exchange calendar over EWS to derive an availability status. **Visio** (LiveKit) only has a notion of presence during an active call (list of participants connected to a room), with no "available/away" state outside a call.
- Injecting an aggregated status directly into each application's native indicator (making "in a meeting" appear inside Element itself, for example) would require modifying the native display of each client — out of reach without forking the applications themselves.
- Displaying the consolidated status on a neutral surface already designed for this purpose (the application-portal banner, 2.3) is significantly more realistic: the data is aggregated on the connector side and displayed in one place only, with no changes to the source applications' code.

**Conclusion — component selected**
A **presence aggregator developed as an additional connector**, on the same pattern as the notification center (2.1) and unified search (2.2): Matrix presence queried live, Grommunio calendar availability derived via `GetUserAvailability` (EWS), Visio call status queried via the LiveKit API/webhooks — consolidated status displayed in the application-portal banner (2.3), rather than injected into each application's native indicators, which each remain on their own logic. Connector to be developed, added to the list of integration projects (2.11).

---

### 2.9 "Create a video call" button from a Grommunio calendar invitation

**Functional need**
A button in the Grommunio meeting editor to automatically insert a Visio meeting link, on the Teams/Outlook integration model, rather than manually creating the meeting on Visio and then copying the link into the invitation.

**Possible alternatives**
- **Reusable personal link**: Visio natively documents that generated meeting links can be reused indefinitely — the same link can be pasted once into a signature or a Grommunio invitation template, with no button and no development.
- **Full integration button**: a connector that calls a room-creation API on the Visio/La Suite Meet side to generate a meeting on the fly and insert the link directly into the invitation body when it is created.

**Selection criteria**
- The reusable personal link covers a good part of the need with no development at all, but remains manual: each organizer must know and paste their own link, with no automation or button in the editor.
- The full integration button assumes an extension point on the grommunio-web side (not natively documented as extensible for this specific case) or a companion module on the client side (Outlook Add-in, heavier, see 1.9). On the Visio/Meet side, the project's architecture (Django REST Framework, open-source `suitenumerique/meet` repository) suggests that a room-creation API exists internally, but it is not publicly documented at this stage — the product still being under active development. **This point is to be confirmed directly with the DINUM teams before costing any development.**

**And what about Thunderbird and mobile calendars?**
- **The reusable link works identically, with no client distinction**: since it is just plain text pasted into an event's location or description field, its insertion does not depend on any particular protocol (EWS, CalDAV or EAS) — it works equally well in Thunderbird, Apple Calendar, or a mobile's native EAS calendar, with no development and no distinction between clients. This is precisely the advantage of this fallback solution: it is universal by design.
- **The full integration button, on the other hand, must be examined client by client**:
  - **Thunderbird**: technically achievable, and with a **solid, active precedent rather than mere hypothesis**. Two existing add-ons illustrate two very different levels of maturity for this same pattern (video call + Thunderbird calendar):
    - *Jitsi Meet Event Generator*: a cautionary example rather than a model to follow — the button is only available in the mail compose window, not in the event editor (an explicit user request went unaddressed in the reviews), and the generated `.ics` file contains a malformed UID that breaks compatibility with CalDAV calendars — exactly the protocol used here with Grommunio.
    - **`NC Connector for Thunderbird`**: a much more convincing precedent. This add-on, actively maintained (public GitHub repository, releases continuing through 2026), **creates and updates a Nextcloud Talk room directly from Thunderbird's calendar event editor** — a genuine calendar integration, not just mail — and synchronizes changes or deletion of the room when the event changes. It even has an Outlook counterpart ("NC Connector ecosystem"). This is a more relevant point of comparison than the earlier Jitsi/Google Meet/Zoom precedents, because **Nextcloud Talk is, like Visio, a self-hosted, open-source video conferencing tool** — architecturally close to what this project would seek to build, rather than an integration with a third-party commercial service.
    - A remaining point of vigilance: NC Connector relies, as considered above, on Thunderbird's experimental calendar API ("Calendar experiment," not finalized in the software's core) — but its active, continuous development over several years shows that this risk is manageable over time with dedicated maintenance, not a deal-breaker.
  - **Mobile (native iOS/Android calendars over EAS, or a mobile mail client)**: **no realistic path identified, and the reason is more fundamental than a simple lack of an extension point**. Thunderbird for Android is not a mobile version of the same desktop application: it is a legacy of the K-9 Mail codebase (Kotlin, native Android), currently being reworked, which does not support the desktop WebExtension ecosystem at all. Concretely, none of the add-ons mentioned above (NC Connector, Jitsi, Google Meet, Zoom) exist, nor can they exist, on Thunderbird mobile — this is not a temporary limitation to monitor, but a difference in software architecture. The reusable link therefore remains the only option on mobile, definitively.

**Conclusion — component selected**
**A two-speed solution, with a scope clarified by client**: immediately, roll out the **reusable personal Visio link** — a universal solution, valid with no distinction across grommunio-web, Outlook, Thunderbird, Apple Calendar, and mobile calendars, with no development at all. The **full integration button** remains a project to be scoped more precisely, realistic on **grommunio-web** and **Outlook** (Add-in) in the short term, and on **Thunderbird** — where the `NC Connector for Thunderbird` precedent (Nextcloud Talk/calendar integration, actively maintained) demonstrates the concrete feasibility of an equivalent integration for Visio, provided the experimental calendar API is used and maintained knowingly. **Structurally out of reach on mobile**, since Thunderbird for Android does not share the desktop's WebExtension architecture. The whole is conditioned on the availability and documentation of a room-creation API on the Visio side — to be verified with the DINUM before costing. Added to the list of integration projects (2.11).

---

### 2.10 Direct link to a Seafile/OnlyOffice document from a Vikunja task

**Functional need**
Associate a Seafile/OnlyOffice document with a Vikunja task without duplicating the file as an attachment, to avoid divergence between the version of the document in Seafile and the one attached to the task.

**Possible alternatives**
- **Link pasted into the task description**: manually paste the (stable) internal Seafile document URL into the Vikunja description, which supports rich text/Markdown and therefore renders the link clickable — zero development.
- **Dedicated connector**: use Vikunja's REST APIs (task endpoints, HMAC-signed webhooks) and Seafile's to offer a "link a Seafile document" action directly in the task UI, with, for example, a preview or a dedicated attachment type rather than a free-text field.

**Selection criteria**
- Vikunja exposes a full REST API (tasks, attachments, webhooks) widely used by the community for this type of automation — a dedicated connector remains achievable if the need goes beyond a simple link.
- A simple link pasted into the description already covers the primary stated objective (avoiding file duplication as an attachment) with no development at all: the file stays in Seafile, the task only references a link to it.
- Developing a dedicated connector only adds real value if the need goes beyond a simple link (document preview within the task, automatic status update if the document is modified) — a need not expressed at this stage.
- Consistency with the restriction already adopted in 2.8 (Chapter 1.4) on unauthenticated Seafile share links: the pasted link points to the authenticated document in Seafile, not to a public share link — no contradiction with this policy.

**Conclusion — component selected**
**Adopted with no development**: a Seafile link pasted into the Markdown description of the Vikunja task. A **dedicated connector** (Vikunja + Seafile API) is only to be considered if a need for a more advanced preview or synchronization emerges in practice — not selected as a priority project at this stage, but kept in mind should the need evolve.

---

### 2.11 Other integration topics to be scoped

Topics identified but not yet examined in detail, to be addressed following the same framework (need / alternatives / criteria / conclusion) in a future iteration:

**Automatic deposit of large files to Gokapi from mail**
Need: when a consultant tries to attach a large file to an email (Grommunio webmail or a full-featured client), offer to automatically deposit it on Gokapi (1.8) and insert the generated link in place of the attachment, after explicit user confirmation — rather than letting the send fail or working around the limit through other, uncontrolled means.
- **Grommunio-web**: this point remains to be scoped — it depends on the availability of an extension point (plugin) in grommunio-web's architecture to intercept an attachment upload above a size threshold and offer the Gokapi deposit before sending. Gokapi's REST API makes this server-side integration easier (API-key authentication tied to the sender's OIDC account).
- **Full-featured clients**: Thunderbird natively has a mechanism dedicated to exactly this need, **Filelink** — beyond a configurable size threshold (5 MB by default), Thunderbird automatically offers to send the attachment via a Filelink provider rather than as a classic attachment, this mechanism being open to third-party extensions (Filelink providers already exist for Dropbox, Box, WebDAV, or Send instances). A Filelink module dedicated to Gokapi is therefore to be developed following a pattern already proven by the Thunderbird community, not an integration to invent — Gokapi's REST API and CLI (`gokapi-cli`) provide the necessary entry points. For Outlook, in the absence of an equivalent natively extensible mechanism, the integration would require a companion module (Office Add-in) — heavier development, to be costed separately if Outlook needs to be supported at the same level as Thunderbird.

**Banning unauthenticated Seafile share links**
Need: prevent the generation of Seafile share links accessible with no authentication, so that any unauthenticated external sharing goes exclusively through Gokapi (1.8) — consistent with and complementary to the previous point. **Confirmed**: Seafile exposes a documented server setting, `SHARE_LINK_LOGIN_REQUIRED = True`, which forces login to view any file/folder share link. In addition, the `can_generate_share_link` permission can be disabled by role (`seahub_settings.py`) to purely and simply prevent the generation of share links by the users concerned, rather than only restricting their viewing. Both settings can be combined depending on the desired level of rigor (preventing generation vs. requiring authentication to view).

### 2.12 Corporate video platform (storage and provision of recordings and transcriptions)

**Functional need**
Have an equivalent to Microsoft Stream/Videos: a centralized space where meeting recordings and their transcriptions are kept durably, indexed, and made available to consultants (search by title/date/participants, streaming playback, viewing-rights management), rather than letting each recording disappear or sit around as an isolated file.

This need is directly linked to the finding made in 1.3: the public Visio (DINUM) instance only keeps recordings for 7 days before automatic deletion. **In self-hosting, this limit does not apply to the firm** (see selection criteria below) — but the need for durable storage and indexed availability remains, once the time constraint is lifted.

**Possible alternatives**
- **Store recordings as plain files in Seafile**, in a folder dedicated to each meeting/project.
- **PeerTube**: an open-source, federated (ActivityPub protocol) video publishing and streaming platform, already used by DINUM itself for publishing videos within the LaSuite/DINUM ecosystem (tube.numerique.gouv.fr).
- Proprietary solutions such as Panopto/Kaltura — not selected at this stage, contrary to the project's sovereignty logic.

**Selection criteria**
- Simple Seafile storage meets the retention need, but not the need for a video platform as such: no streaming player suited to video (just a file download), no indexing by meeting metadata, no content search.
- PeerTube provides precisely what plain file storage lacks: a streaming video player, organization by channels/playlists (for example one channel per team or per meeting type), and per-video visibility management (private, internal, unlisted).
- Consistency with the DINUM ecosystem already leveraged for Visio/Tchap: PeerTube is not an isolated choice, it is the tool the French State already uses for the same kind of need in the same software ecosystem.
- PeerTube's federated (ActivityPub) format is not a stated need here, but is not a drawback either: federation is optional and can remain disabled for strictly internal use.

**The 7-day limit is not a constraint of the Visio software, but an operating policy specific to the DINUM instance.** Technically, the recording is produced by **LiveKit Egress** (the component that captures a room's audio/video stream), which writes the file to **S3-compatible storage** (a bucket) — this is the officially documented and proven output for LiveKit, on a par with Google Cloud Storage or Azure. The 7-day deletion observed on the public instance is very likely a lifecycle rule set on DINUM's bucket (or an equivalent application-side cleanup on DINUM's side), not a limit fixed in Visio's code — to be confirmed concretely at installation (the project's own documentation states that advanced features such as recording still lack detailed documentation), but the S3 + lifecycle-rule pattern on the infrastructure side is the near-universal mechanism for this type of purge.

**The S3 bucket is not a cloud dependency, but one more self-hosted component.** LiveKit Egress supports a direct-to-local-disk write mode with no storage configuration, but that disk belongs to the Egress pod itself, ephemeral and not shared with other services by default. Having PeerTube read this file would then require a network volume shared between Kubernetes pods (NFS or equivalent), more fragile to operate at scale than the officially supported path. **Self-hosted MinIO** (S3 API-compatible, running in the same Kubernetes cluster as the rest of the stack) is therefore selected as the Egress destination rather than a filesystem share between pods — this is not a third-party cloud component, just one more object-storage piece of software to host, on a par with Seafile or Keycloak. Retention on this self-hosted bucket is configured by the firm itself (a generous lifecycle rule, or none at all) rather than something imposed on it.

- Still to be built: the receiving webhook that subscribes to the MinIO bucket's `ObjectCreated` notifications to trigger the deposit to PeerTube (upload via its API, associating meeting metadata — title, date, participants — with the video). With no time constraint (retention now under control), this deposit can be handled as a periodic task (daily batch) rather than as a critical real-time reaction — simpler to operate, with no risk even in the event of a temporary connector outage.

**Conclusion — component selected**
**PeerTube**, as the corporate video platform for durably keeping and making available meeting recordings and their transcriptions, fed upstream by **self-hosted MinIO** (S3-compatible destination for LiveKit Egress, whose retention rule is set by the firm itself, with no dependency on a limit imposed by a third party) and a deposit connector to PeerTube that can run as a periodic task rather than urgent real time. Seafile is not selected for this specific use (lack of a streaming player and indexing), but remains relevant for storing regular documents and files (1.4).

---

### 2.13 Corporate directory (GAL) accessible from all selected mail clients

**Functional need**
Have a corporate directory (Global Address List) that can be browsed and queried from any mail client selected in this document — not just Outlook — for recipient autocomplete while typing and searching for colleagues by name, as Exchange/Office 365's GAL natively allows.

**Finding**
Grommunio natively manages the GAL (see 1.1): a directory automatically populated from the users/domains configured on the server side, with fine-grained admin control (a "Hide from GAL" checkbox per user to exclude service mailboxes and technical resources), distribution-list resolution with nested groups, support for internationalized domains (IDN). This foundation is, however, not exposed the same way depending on the client protocol:
- **MAPI/EWS/EAS clients** (Outlook, see 1.9): native, full access to the GAL, with no additional configuration — this is inherent to Grommunio's protocol compatibility with Exchange.
- **CardDAV clients** (Thunderbird, Apple Mail/Contacts, see 1.9): historically, only the user's *personal* contact book was exposed by `grommunio-dav` over CardDAV — the GAL was absent from it, leaving users of these clients without colleague autocomplete.

**Possible alternatives**
- Accept this limitation and direct Thunderbird/Apple Mail users to grommunio-web for any directory search — a usage degradation accepted by default.
- **Enable publication of the GAL over CardDAV**, a native feature added by Grommunio in its 2026.06.1 release: `grommunio-dav` can now publish the GAL as a read-only CardDAV address book, via the `GAL_ENABLED` configuration parameter (disabled by default), with a configurable cache duration (`GAL_CACHE_TTL`).

**Selection criteria**
- A native, recent feature of the component already selected (no connector to develop, unlike the other topics in this chapter): a simple server setting to enable.
- Consistency with the usual principle of a GAL: read-only publication, users being unable to modify or enrich the corporate directory from their client.
- The `GAL_CACHE_TTL` setting must be sized to balance directory freshness (consultants joining/leaving) against load on the DAV server, with a default TTL on the order of an hour posing no known difficulty for standard office use.

**Conclusion — component selected**
**Enabling `GAL_ENABLED` in the `grommunio-dav` configuration from initial deployment**, so that Thunderbird and Apple Mail/Contacts (1.9) natively have the read-only corporate directory, on a par with Outlook via MAPI/EWS — with no connector to develop, unlike the other integration projects in this chapter. Point of vigilance: since this feature is very recent (June 2026), its maturity and behavior in real-world use (cache freshness, performance on a directory with several thousand entries at the targeted growth scale) still need to be validated in acceptance testing before broad rollout.

**Additional point — expanding distribution lists (the "+" next to a list)**
On Outlook/Exchange, clicking the small "+" to the right of a distribution list in the recipient field "explodes" the list and displays all its members individually. This behavior relies on the EWS `ExpandDL` operation.
- **On the EWS side (Outlook for Mac, eM Client, see 1.9)**: **confirmed functional**. `ExpandDL` is among the operations explicitly implemented by Gromox, in the same June 2026 EWS-strengthening wave that also brought room search and the full meeting workflow (see 2.14).
- **On the CardDAV side (Thunderbird)**: **not available, and this is not a Grommunio limitation.** The CardDAV equivalent of `ExpandDL` is the vCard 4.0 representation of a group (`KIND:group` + `MEMBER` properties, RFC 6350). However, Thunderbird itself does not implement this mechanism — it is an open, documented feature request filed with Mozilla, still unresolved to this day. Thunderbird's native "Expand list" right-click (since version 91) only works on lists in its legacy local/personal address book, not on a group received via CardDAV. Even if Grommunio's CardDAV GAL published its distribution lists in `KIND:group` format, Thunderbird would not know how to interpret them as expandable lists.

This point reinforces the finding already made earlier in this section: the gap between Outlook/EWS and Thunderbird/CardDAV on the GAL is not limited to whether the directory is present or not, but extends to features built on top of it (here, list expansion) — to be documented in communications to consultants, on a par with room booking (2.14).

---

### 2.14 Meeting room booking depending on the client (Outlook vs. Thunderbird/mobile)

**Functional need**
Book a meeting room (or another shared resource, such as a vehicle or a projector) directly from the calendar's meeting editor, with a search of available rooms and automatic confirmation based on their availability — as Outlook/Exchange's "Room Finder" allows.

**Finding**
Grommunio natively manages room booking: the administrator creates the room as a shared user account (a "room resource"), and in the meeting editor, the user adds it as a participant and then marks it "Set as Resource" — the room then automatically accepts or declines the meeting depending on its availability. This mechanism is natively exposed in **grommunio-web** and in **Outlook** (MAPI/EWS) — room search and the full meeting workflow (invitations, cancellations, replies) over EWS were, moreover, specifically strengthened by Grommunio's June 2026 release (see 2.13).

**What does not carry over on CalDAV (Thunderbird) and mobile clients**
- **Thunderbird**: it is possible to add the room's mail address as a meeting participant and see its free/busy slot displayed — a generic CalDAV availability mechanism, identical for any participant. However, **there is no selector to browse/search available rooms** (no Room Finder equivalent), and **the automatic accept/decline workflow is not guaranteed to work identically** when an invitation is sent from a CalDAV client rather than MAPI/EWS — Grommunio's documentation only describes this mechanism in the context of grommunio-web, with no explicit mention of its behavior for an invitation initiated over CalDAV.
- **Mobile (EAS)**: mobile synchronization goes through `grommunio-sync`, documented by Grommunio itself as a reduced subset of functionality compared to MAPI/EWS. No confirmation was found that room search and booking work along this path — to be verified at installation rather than assumed to work.

**This limitation is not a software version lag, but a structural limit of the CalDAV standard**: the CalDAV/iTIP protocol defines neither a browsable room directory nor an auto-acceptance workflow by a resource — these are proprietary extensions built by Microsoft on top of MAPI/EWS. No generic CalDAV client has any reason to have implemented them, since they are not part of the protocol it speaks; the same finding is observed on other CalDAV groupware servers (SOGo, Nextcloud) independently of Grommunio. A newer version of Thunderbird will therefore change nothing on this point as long as the CalDAV protocol itself does not evolve.

**Alternative — connecting Thunderbird over EAS rather than CalDAV, via the `TbSync` + `EAS-4-TbSync` add-on**
This third-party add-on adds the full EAS protocol (up to version 16.1) to Thunderbird, as an alternative to native CalDAV. Its most recent series of releases (v5.3.x, the latest dated August 28, 2026) closes a long-standing gap: the meeting workflow now works end-to-end (accepting/declining/rescheduling an invitation reaches the server, the organizer sees the reply), a participant's **availability (free/busy) is displayed on invitation**, and the **GAL becomes a searchable address book** rather than a blind addition. For adding a room, this should therefore provide a noticeably better experience than pure CalDAV: availability displayed natively, as a mobile EAS client would.

Two reservations remain, however, before adopting this path:
- The release notes mention no dedicated "browse available rooms" selector nor an explicit auto-acceptance mechanism by the room (the equivalent of "Set as Resource") — only generic participant availability, including for a room if its address is known.
- This add-on's end-to-end test suite is explicitly run against **Microsoft 365 and Kopano/Z-Push** — not against Grommunio. Since EAS is a documented, shared protocol, compatibility should follow to the extent that `grommunio-sync` implements it correctly, but this is neither tested nor certified by the add-on's maintainers for Grommunio specifically.
- It is an actively developed third-party add-on, not an official Thunderbird component — to be evaluated from a maintenance and longevity standpoint before production adoption, on a par with this document's other external dependencies.

**Selection criteria**
- Accept the limitation as a structural loss for Thunderbird/mobile users in the default CalDAV configuration, directing them to grommunio-web for any room booking — consistent with the principle already stated in 1.9 ("not every client exposes every feature, grommunio-web remains the full functional reference").
- Or test `TbSync` + `EAS-4-TbSync` as an alternative configuration for Thunderbird users with a frequent need for room visibility, bearing in mind that it is an uncertified third-party add-on on Grommunio and that the actual search/booking feature is not confirmed, only availability is.
- Document this limitation in the project's communications, to avoid it being discovered in production by a consultant looking for the Room Finder in Thunderbird without finding it.

**Conclusion — component selected**
**No connector to develop**: room booking remains a complete feature on the **grommunio-web** and **Outlook** side. On the **Thunderbird** side, two configurations coexist: native CalDAV (availability visibility only, with no search or auto-acceptance) or **EAS via `TbSync` + `EAS-4-TbSync`** (better availability visibility, complete meeting workflow, but still with no room selector and no confirmed auto-acceptance, and on a path not officially tested against Grommunio). On the **mobile (native EAS)** side, a similar situation, not confirmed at this stage. **To be verified concretely in acceptance testing** before choosing a default configuration and communicating a final limitation to consultants: the actual behavior of adding a room over CalDAV, with `EAS-4-TbSync`, and on mobile.

---

## Chapter 3 — What is lost compared to Office 365, for lack of an alternative

Some losses compared to Office 365 are a deliberate choice (sovereignty and cost against integrated application comfort, see the trade-offs in Chapter 1). Others are not a choice: they are structural impossibilities, for lack of an existing alternative or because they depend on a mechanism that belongs to Microsoft alone. This chapter isolates this second category of losses, so that the decision to exit Office 365 is made with full knowledge of the facts.

### 3.1 Interoperability with clients' Teams

**The concrete finding**: a consulting firm continuously exchanges with clients who, for their part, remain on Microsoft 365/Teams. The question raised is direct — will each consultant need a Teams account at each client in order to communicate with them, or is there a lighter-weight option?

**What is not a problem: one-off meetings**
Joining a Teams meeting organized by a client requires no account: anyone can join a Teams meeting as a guest from a browser, simply by giving their name, with no account creation and no app installation. This is strictly symmetric to what Visio already allows for participants external to your own stack. **No loss here.**

**What is a problem: persistent chat and presence with a client**
Two distinct mechanisms exist on the Microsoft side for this need, and neither is fully satisfactory without depending on Microsoft:

1. **External access (Teams-to-Teams federation)**: allows chatting, calling and scheduling meetings with users of another Microsoft 365 organization, without adding them as guests — but this mechanism only works **between two Teams tenants**. Since the end of interoperability with consumer Skype (May 2025), external federation only works Teams-to-Teams. **A firm that exits Office 365 and no longer operates a Teams tenant therefore loses access to this mechanism**: it is impossible to have Matrix and Teams talk to each other natively through this channel, for lack of a Teams tenant on the firm's side to federate with.
2. **Guest access**: the client adds each consultant as a guest in its own Microsoft 365 tenant, which creates a guest account in its directory (Entra ID). This account **does not consume a Teams/Microsoft 365 license** on either the client's or the firm's side — the consultant can sign in with a free personal Microsoft account, a Google account, or a simple one-time code. This is therefore not a Microsoft 365 subscription to purchase, but **a structural constraint remains**: each consultant must be invited individually, tenant by tenant, with no bridge to Matrix whatsoever — the exchange takes place entirely inside the client's Teams, invisible to the notification center and the unified search built in Chapter 2. A consultant working with 5 different clients potentially accumulates 5 separate guest identities, across 5 separate Teams interfaces.

**Conclusion — an accepted loss, with no complete alternative**
There is no mature, officially supported bridge between Matrix and Teams equivalent to Teams-Teams federation. Community bridges (Matrix-Teams bridges) exist but rely on APIs not guaranteed by Microsoft over time, and are not selected for structural professional use. **The only viable option remains guest invitation into the client's tenant, at no licensing cost, but with no way to unify it with the rest of the firm's stack.** This point must be explicitly built into the project's communications: exiting Office 365 does not remove the need, for each consultant, to manage one identity per client that remains on Teams.

### 3.2 Built-in artificial intelligence (Copilot)

No native equivalent to Copilot exists within Word/Excel/Outlook/Teams to summarize, generate, rewrite or analyze data from within the interface. External AI tools (including Claude) can be connected at the periphery of the stack (content generation, writing assistance), but "in-click" integration, within each application itself, does not natively exist in the components selected in Chapter 1.

### 3.3 Native cross-application data graph

At Microsoft 365, Teams/Outlook/SharePoint/OneDrive share a common data graph (Microsoft Graph): unified search, an attachment that automatically becomes a SharePoint link, presence shared everywhere. The stack selected here remains, despite the integration projects in Chapter 2 (notification center, unified search), a federation of independent tools whose integration remains shallower than a true common data graph — the connectors developed link events, not a shared database.

### 3.4 Maturity and unification of mobile applications

The mobile apps (Element, Grommunio, Seafile, Vikunja) are functional but individually less polished than Outlook/Teams mobile, and remain separate applications on the user side rather than a unified experience — despite the installation-facilitation efforts addressed in 2.5.

### 3.5 Packaged compliance and governance features

DLP (Data Loss Prevention), eDiscovery, advanced retention policies, industrialized regulatory compliance (litigation hold in particular), centralized cross-service auditing: these features exist at Microsoft in a packaged, ready-to-use form. In the stack selected here, the equivalent will have to be rebuilt component by component (Matrix message retention, Seafile retention policies, Grommunio archiving) or accepted at a more artisanal level of compliance, for lack of an equivalent cross-cutting compliance suite.

### 3.6 Single accountability and support

With Office 365, there is a single vendor, a single SLA, a single point of contact in the event of an incident. With the stack selected here, responsibility is split across several vendors and open-source communities: in the event of a bug or an incident affecting several components at once, it is the firm (or its operating provider, see Chapter 5) that owns cross-service integration and diagnosis, with no single point of contact to hold contractually accountable across the whole chain.

---

## Chapter 4 — Infrastructure and deployment arrangements

### 4.1 General principle

The entire stack must be fully redeployable from scratch (a new environment, rebuilding after a major incident, duplication for a new client) from a source code repository describing the entire infrastructure and configuration — an approach known as infrastructure as code (IaC).

Given the firm's growth ambition, this IaC description must be parameterized for capacity (number of replicas, resources allocated per component) rather than fixed for a given headcount: scaling from 100 to several thousand consultants must translate into a simple variation of these parameters and adding nodes to the cluster, never into a rewrite of the infrastructure definition itself.

### 4.2 Virtualization layer and hosting choice

**Decision adopted: infrastructure operated in-house (or in colocation), virtualized with Proxmox VE — no managed cloud.**

Two options had been considered:
- **Hosting with a managed cloud/Kubernetes provider** (e.g. a sovereign offering such as OVHcloud, Scaleway): the virtualization layer is handled by the provider, invisible to the firm — the simplest solution to operate, but one that reintroduces a form of dependency on a third party for hosting, at odds with the sovereignty logic that has motivated this entire project since its Introduction (reducing dependence on a single non-European vendor) and with the choice already made to self-host Visio.
- **In-house-operated infrastructure, on physical hardware owned or leased in a bare-metal/colocation setup**: requires a hypervisor layer to virtualize the physical servers before deploying Kubernetes on them.

**The second option is adopted.** It is consistent with the full end-to-end control this project targets (the firm then controls the physical location of the data end-to-end, not just the software), and with the choices already made for Grommunio and Visio, which presuppose in-house hosting. The trade-off accepted: the operating burden of the physical infrastructure (hardware, network, datacenter/colocation) rests with the firm or its operating provider (Chapter 5), rather than with a cloud provider — consistent with the rest of the stack, where responsibility is already accepted as split across several components (see 3.6).

**Proxmox VE** is selected as the hypervisor layer: open source, proven for serious self-hosting, with a mature Terraform/OpenTofu provider (`bpg/proxmox`) allowing the virtual machines hosting the Kubernetes nodes to be defined in a fully declarative way — consistent with the IaC approach in Chapter 4.1. Proxmox also allows high availability at the hypervisor level (a multi-node physical Proxmox cluster, live VM migration), which complements the high availability already planned at the application level (Synapse in workers mode, Keycloak cluster, OnlyOffice Document Server cluster).

**Recommendation**: **Proxmox VE** is included in the IaC repository as the target virtualization layer, with the Kubernetes cluster deployed on the VMs it provisions — rather than installing Kubernetes directly on the physical servers ("bare metal"), which would deprive the firm of the VM migration/resizing flexibility and the additional node-to-node isolation that virtualization provides.

### 4.3 Containerization of the building blocks

Most components of the stack (Matrix/Synapse, Element Call, Visio DINUM, MinIO, Seafile, OnlyOffice Document Server, Vikunja, Keycloak, Gokapi, the notification center, the unified search service, PeerTube, Caddy) is packaged as containers (Docker), which allows:
- a reproducible, versioned definition of each service (image, environment variables, volumes);
- identical deployment regardless of the target environment (development workstation, acceptance environment, production);
- clear isolation between components, consistent with the "best of breed" approach adopted in this document;
- native orchestration in Kubernetes (see 4.4), each of these components being natively designed cloud-native (stateless or clusterable services).

**Deliberate exception: Grommunio as a VM appliance, not a container.** Grommunio does offer an official container package (`grommunio/gromox-container`), but its own documentation presents it as a solution for special needs not covered by the standard appliance, not as the recommended primary deployment mode — the documented defaults are explicitly described as not production-ready, and the "core" container bundles many services (nginx, Postfix, the gromox daemons, Redis, PHP-FPM) under a single supervisord process, without the decomposition into microservices that would naturally orchestrate in Kubernetes. The **appliance** (full VM, ISO/OVA) remains the most mature and best-tested deployment mode according to Grommunio itself. Grommunio is therefore deployed as a **VM appliance directly on Proxmox** (see 4.2), rather than containerized in Kubernetes like the rest of the stack — a consistent choice for a critical, stateful service (mailboxes), which incidentally benefits from the hypervisor-level high availability (Proxmox cluster, live migration) already planned for other reasons.

### 4.4 Orchestration

Given the firm's growth ambition (several thousand consultants targeted), the orchestrator selected from the initial design must be the one that allows horizontal scaling with no later architecture change, for all containerized components identified in 4.3:

- **Docker Compose** remains relevant only for a small-scale development/test environment (Chapter 4.6), but is not selected as the production target: it does not natively provide the horizontal scaling or high availability required by the components identified as critical in this respect (Synapse in workers mode, clustered OnlyOffice Document Server, clustered Keycloak).
- **Kubernetes** (with per-component Helm manifests) is selected as the production target from the initial 100-user deployment, precisely so that scaling to 2000 and then several thousand consultants translates into adding capacity (nodes, replicas) rather than an orchestrator migration mid-growth — a change of orchestration architecture would be a far greater risk and cost than the initial overcapacity of a Kubernetes cluster sized generously from the start. Kubernetes nodes are Proxmox VMs (see 4.2). Grommunio, outside the Kubernetes scope (4.3), remains a separate Proxmox VM, provisioned and configured by the same IaC repository (see 4.5).

**Alternative considered and ruled out — Coolify**
Coolify (a self-hosted PaaS, MIT, git-push deployment, one-click service catalog) was evaluated as a possible orchestration path. **Ruled out for the production target**, for three reasons:
- Its multi-server mode relies on **Docker Swarm**, not Kubernetes — an architectural limit acknowledged by the vendor itself, to the point that a complete rewrite (v5) is underway specifically to move past this ceiling, with no announced release date. Adopting Coolify today would mean reintroducing exactly the risk that choosing Kubernetes from the outset is meant to avoid: an orchestrator change mid-growth.
- Runs as root by default, and was the subject of 11 critical CVEs (command injection, root key exposure) in early 2026 — the burden of fixing them rests entirely on the self-hosting operator.
- Would introduce a second deployment paradigm alongside the IaC approach already adopted (Terraform/OpenTofu + Ansible + Kubernetes/Helm), rather than a consistent complement.

Coolify retains marginal, optional interest as a **convenience layer for the development/test environment** (4.6, already scoped on small-scale Docker Compose) — a web interface rather than the command line for developers iterating on that tier — but must in no way approach the Kubernetes production target.

The target hosting provider remains open (in-house datacenter/colocation, to be selected according to the usual criteria: proximity, certification, cost), but the principle of in-house infrastructure on Proxmox, rather than a managed cloud, is now settled (see 4.2).

### 4.5 Provisioning and configuration

- **Provisioning of the underlying infrastructure** (Proxmox VMs — including the Grommunio appliance VM — or cloud resources, network, storage) described by an infrastructure-as-code tool (Terraform or OpenTofu), versioned in the same repository as the rest of the stack.
- **Application configuration** of each component (Keycloak realms and clients, Matrix domains, service accounts, integration connectors) automated via playbooks (Ansible) or declarative manifests, rather than manually documented steps.
- **Secrets management** (passwords, API keys, certificates) externalized into a dedicated vault (e.g. Vault or a managed equivalent), never in plain text in the code repository.

### 4.6 Environments

Plan for at least three environments, strictly identical in their IaC definition, differing only in size and data:
- **Development/test**: reduced scale, synthetic data.
- **Acceptance (staging)**: intermediate scale, used in particular for validating version upgrades (see Chapter 5).
- **Production**.

### 4.7 Backup and restore

Every component holding persistent data (Grommunio mailboxes, Synapse history, Seafile files, OnlyOffice documents, Vikunja tasks, Keycloak realms) must be covered by a documented backup strategy tested through regular restores — the "start from scratch" capability targeted by the IaC approach only covers rebuilding the infrastructure and configuration, not recovering the data itself. In the in-house Proxmox hosting scenario (4.2), VM-level backups (Proxmox Backup Server snapshots) complement, without replacing, the application-level backups specific to each component.

---

## Chapter 5 — Long-term operations and cross-cutting governance

### 4.1 Objective

Beyond the initial deployment, the stack must be steered over time in a way that is cross-cutting across all components: vulnerability monitoring, monitoring of new available versions, and tooled validation of these new versions before they go into production.

### 4.2 Vulnerability (CVE) monitoring

- Setting up an automated, regular scan of each component's containerized images (e.g. Trivy or Grype) to detect known vulnerabilities affecting embedded dependencies.
- Subscribing to each component's official security feeds (security mailing lists or RSS/GitHub Security Advisories feeds for Grommunio, Synapse/Element, Seafile, OnlyOffice, Vikunja, Keycloak, Caddy) to be alerted independently of the automated scan cycle.
- Centralizing alerts raised (scan + vendor monitoring) into a single dashboard, with a severity level and an affected component per alert.

### 4.3 Monitoring of newly available versions

- Automated tracking of each component's new releases (a Renovate- or Dependabot-type mechanism applied to container images and IaC repository dependencies), rather than a periodic manual check.
- Every new version detected (security fix or new feature) triggers the process described below, rather than being applied directly to production.

### 4.4 Automatic triggering of an acceptance environment

When a new version of a component is detected:
1. An ephemeral acceptance environment is automatically created from the IaC definition (Chapter 4), with the new version of the affected component and the current versions of all other components.
2. This environment is populated with a representative test dataset (not real production data).
3. A continuous integration/deployment (CI/CD) pipeline orchestrates this entire cycle with no manual intervention up to the results-validation step.

### 4.5 Replaying test scenarios

- Maintaining a library of automated test scenarios covering the critical uses identified in this document: sending/receiving mail (Grommunio), creating and synchronizing a file (Seafile), co-editing a document (OnlyOffice), sending a message and starting a video call from a room (Matrix/Element/Visio), creating and notifying a task (Vikunja), end-to-end SSO authentication (Keycloak) across each of the preceding components.
- These scenarios are replayed automatically on the ephemeral acceptance environment for every new version detected, before any promotion to production.
- A results report (pass/fail per scenario) governs the decision to promote the new version to production — manual or automated depending on the criticality of the component concerned.

### 4.6 Cross-cutting governance

- A single dashboard consolidating: open vulnerabilities per component, current versions vs. available versions per component, results of the latest acceptance runs, health status (technical monitoring) of each component in production.
- This cross-cutting governance is distinct from the user-facing notification center (Chapter 2): it is aimed at the operations team, not at the consultants who are end users of the stack.

---

*Working document — to be completed and refined over future sessions. Points still open at this stage: unified presence — aggregation connector to be developed (2.8); video-call button from Grommunio — a fallback solution (reusable link) adopted for the time being, full integration button conditioned on the availability of a room-creation API on the Visio side, to be confirmed with DINUM (2.9); final selection of the hosting/datacenter provider (4.2); to be confirmed in practice: the actual adoption level of Thunderbird/Apple Mail among consultants used to Outlook, once Outlook for Mac is explicitly ruled out for sovereignty reasons (1.9); to be validated in acceptance testing: maturity of the CardDAV GAL (`GAL_ENABLED`, a June 2026 feature) on a directory at the targeted growth scale (2.13); to be validated in acceptance testing: actual behavior of the room-booking workflow initiated from Thunderbird or a mobile device over EAS, before communicating a final limitation to consultants (2.14); **to be re-evaluated in a future iteration: Euro-Office (sovereign fork of OnlyOffice Document Server) as a replacement candidate for OnlyOffice, once its maturity, the outcome of its AGPL dispute with Ascensio System, and its actual compatibility with the Seafile connector are confirmed (1.5)**; **before putting Gokapi into production: confirm through an independent audit or active monitoring the robustness of its E2EE implementation (unaudited according to the vendor itself), and verify that the Keycloak/OIDC documentation used for configuration is up to date (an earlier configuration example allowed unauthorized access in the past) (1.8)**; the connectors identified in this document remain to be developed (notification center 2.1, unified search 2.2, Visio↔Matrix widget 2.4, unified presence aggregator 2.8, PeerTube webhook 2.12, OnlyOffice mentions handler 2.7, Thunderbird Filelink module for Gokapi 2.11, Keycloak SPI for SMS and email OTP 1.7); an internal reporting/takedown procedure to be documented for Gokapi, including access rights to the file/depositor association natively kept by the tool (1.8).*
