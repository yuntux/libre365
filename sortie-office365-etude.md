# Sortie d'Office 365 : étude d'une stack alternative libre

## Introduction

Un cabinet de conseil de 100 consultants utilise la suite Office 365 depuis une dizaine d'années : messagerie et agenda (Exchange/Outlook), stockage et synchronisation de fichiers (OneDrive/SharePoint), édition collaborative de documents (Word/Excel/PowerPoint Online), visioconférence et tchat d'entreprise (Teams), gestion de tâches (Planner/To Do).

Le cabinet souhaite expertiser les alternatives libres à cette suite, avec deux motivations principales : réduire la dépendance à un éditeur unique non européen (souveraineté des données, maîtrise des coûts de licence à l'échelle) et évaluer si un assemblage de briques open source « best of breed » peut offrir un niveau de service comparable pour ses consultants, sans sacrifier les usages critiques (co-édition documentaire, visioconférence fiable y compris avec des interlocuteurs externes, mobilité).

**Le cabinet porte par ailleurs une forte ambition de croissance.** L'architecture applicative et l'infrastructure retenues ne doivent donc pas être dimensionnées pour les 100 consultants actuels seuls : elles doivent pouvoir monter en charge sans difficulté majeure jusqu'à plusieurs milliers de consultants, sans remise en cause de l'architecture elle-même (changement de brique, réécriture des intégrations). Ce critère de scalabilité est traité systématiquement dans le choix de chaque brique (chapitre 1), dans les choix d'intégration transverses (chapitre 2) et structure directement les choix d'infrastructure (chapitre 4). Deux échelles de référence sont utilisées tout au long du document pour objectiver le dimensionnement : 100 utilisateurs (situation actuelle) et 2000 utilisateurs (première marche de la croissance visée) — étant entendu que l'architecture cible doit permettre d'aller au-delà par ajout de capacité (scaling horizontal), pas par changement de brique.

Ce document capitalise l'analyse menée bloc fonctionnel par bloc fonctionnel, puis les problématiques transverses d'intégration entre briques hétérogènes, avant d'objectiver honnêtement ce qui est structurellement perdu par rapport à Office 365 faute d'alternative, puis d'aborder l'infrastructure de déploiement et les modalités d'exploitation dans la durée.

Le document est structuré en cinq chapitres :
1. Le choix des briques par bloc fonctionnel (mail, fichiers, édition, visio, tchat, tâches, identité)
2. Les problématiques d'intégration transverses entre ces briques
3. Ce que l'on perd par rapport à Office 365, faute d'alternative
4. L'infrastructure et les modalités de déploiement
5. L'exploitation et le pilotage transverse dans la durée

---

## Chapitre 1 — Alternatives par bloc fonctionnel

### 1.1 Messagerie et agenda (remplace Exchange/Outlook)

**Besoin fonctionnel**
Messagerie électronique professionnelle, calendrier et invitations, contacts partagés, synchronisation native sur les clients mobiles et desktop (ActiveSync ou équivalent), sans dépendre du protocole propriétaire Exchange.

**Alternatives possibles**
- **Grommunio** : remplacement quasi drop-in d'Exchange, compatible MAPI/EWS/ActiveSync, connecteurs natifs vers Outlook, Thunderbird, Evolution, clients mobiles standards.
- **Kolab**, **SOGo**, **Zimbra Collaboration Suite** : alternatives groupware plus anciennes, comparées en détail ci-dessous.

**Tableau comparatif — Grommunio et les alternatives groupware historiques**

| Critère | Grommunio | Kolab | SOGo | Zimbra Collaboration |
|---|---|---|---|---|
| **Licence / modèle** | Open source (moteur Gromox), admin UI limitée gratuitement (payante au-delà de 5 utilisateurs) | Open source (GPL), éditeur suisse (Apheleia IT AG) | Open source (GPL v2/LGPL v2), éditeur français (Alinto) | **Anciennement** open source ; depuis la v10 (Daffodil), **licence payante obligatoire** pour toute édition — l'« Open Source Edition » a atteint sa fin de vie |
| **Activité du projet** | Très active : releases fréquentes tout au long de 2026, roadmap publique (EWS, EAS renforcés en continu) | Activité incertaine : derniers paquets significatifs autour de 2023-2024, gouvernance ayant connu des tensions (campagne de financement participatif contestée) | Active : version 5.12.4 (octobre 2025), développement continu chez Alinto | Développement propriétaire poursuivi côté éditeur, mais plus dans une logique open source pour l'utilisateur final |
| **Compatibilité Outlook (natif MAPI/EWS)** | **Native**, sans connecteur tiers : MAPI/RPC-HTTP et EWS intégrés au moteur | **Absente** : pas de MAPI/EWS natif — Outlook doit se connecter en IMAP ou via un synchroniseur CalDAV/CardDAV tiers, sans émulation Exchange | **Native via OpenChange** : un projet tiers séparé qui émule Exchange pour Outlook — fonctionnel mais plus complexe à déployer et maintenir qu'un support intégré au moteur | Native, mais **le connecteur Outlook est une fonctionnalité payante** de l'édition Network |
| **Synchronisation mobile (EAS)** | Native, développée activement (impersonation ajoutée en 2026) | Native via Syncroton (composant dédié) | Native, intégrée au moteur depuis la version 2.2.0 | Native, mais **classée fonctionnalité payante** (« Zimbra Mobile ActiveSync ») dans le modèle de licence actuel |
| **CalDAV/CardDAV** | Natif via grommunio-dav, avec publication du GAL en CardDAV (2.13) | Natif | Natif, avec accès DAV étendu (calendriers, contacts, et mails) | Natif |
| **Scalabilité documentée** | Appliance unique jusqu'à 2000 utilisateurs, puis architecture multi-serveurs documentée (cf. ci-dessous) | Non documentée avec la même précision dans les sources consultées | Architecture horizontale revendiquée jusqu'à plusieurs centaines de milliers d'utilisateurs | Scalable, mais les fonctionnalités de gestion à grande échelle (archivage, recherche cross-mailbox) sont aussi classées payantes |
| **Alignement avec le projet** | Correspond au principe tout-open-source + souveraineté | Open source, mais absence de MAPI/EWS natif fragilise la promesse « drop-in Exchange » posée comme besoin fonctionnel | Open source et scalable, mais OpenChange ajoute une brique et une complexité opérationnelle supplémentaires par rapport à un support natif intégré | **Écarté de fait** : la bascule vers un modèle intégralement payant contredit directement la motivation de coût et de souveraineté logicielle de ce projet |

Ce tableau confirme que **Zimbra n'est plus une alternative crédible pour un projet motivé par la sortie d'une dépendance à un éditeur unique et par la maîtrise des coûts de licence** : sa bascule récente vers une licence payante intégrale reproduit exactement le problème que ce projet cherche à résoudre. **Kolab** reste freiné par l'absence de compatibilité Outlook native — un point dur au regard du besoin fonctionnel posé en tête de cette section (« sans dépendre du protocole propriétaire Exchange » ne veut pas dire renoncer à la compatibilité Outlook pour les consultants qui le préfèrent). **SOGo** reste le concurrent le plus sérieux de Grommunio : open source, actif, scalable, avec un support Outlook fonctionnel — mais reposant sur OpenChange, un projet tiers distinct à opérer en plus du moteur groupware, alors que Grommunio intègre MAPI/EWS nativement dans un seul moteur (Gromox). C'est cette intégration native, plutôt qu'une infériorité de SOGo sur les autres critères, qui penche en faveur de Grommunio.

**Critères de choix**
- Compatibilité protocolaire large (ActiveSync pour mobile, EWS/MAPI pour compatibilité Outlook) sans forcer une migration de client.
- Coût et disponibilité de l'administration : la console d'administration web de Grommunio est limitée/payante au-delà d'un certain seuil d'utilisateurs (modèle freemium sur l'admin, pas sur le moteur mail).
- Dimensionnement et scalabilité : la documentation officielle indique qu'une seule appliance Grommunio est prévue pour un effectif de 1 à 2000 utilisateurs avec un dimensionnement matériel adapté. **Point tranché pour la croissance au-delà de ce seuil** : Grommunio documente une véritable architecture multi-serveurs pour les environnements de grande échelle et les hébergeurs — clusters « share-nothing » (les nœuds ne partagent plus d'accès direct au stockage des mailbox depuis la version 2025.01.1), haute disponibilité via la pile Linux Corosync/Pacemaker, et une architecture multi-tenant à LDAP multiples pensée pour les hébergeurs de grande taille. Ce n'est donc pas une limite dure de la brique, mais un changement de topologie de déploiement (appliance unique → cluster multi-nœuds) à opérer avant que la croissance du cabinet n'atteigne ce seuil.

**Conclusion — brique retenue**
**Grommunio**, piloté sans l'interface d'administration web (CLI/API/fichiers de configuration) pour éviter le coût de licence au-delà de 5 utilisateurs. Ce choix implique de prévoir en interne la compétence nécessaire pour administrer les mailbox sans IHM dédiée — coût opérationnel à ne pas sous-estimer. Sur la gestion de l'annuaire d'entreprise (GAL) et son exposition aux différents clients mail, voir 2.13.

Dimensionnement retenu :
- 100 utilisateurs : ~4-8 Go RAM / 4 cœurs
- 2000 utilisateurs : ~16-32 Go RAM / 8+ cœurs, stockage disque généreux (la taille des mailbox pèse plus que le nombre de connexions)
- **Au-delà de 2000 utilisateurs** : sortir du modèle appliance unique et basculer vers l'architecture multi-serveurs documentée par Grommunio (cluster « share-nothing », haute disponibilité Corosync/Pacemaker), plutôt qu'un repartitionnement artisanal par practice/entité — c'est un changement de topologie de déploiement outillé par l'éditeur, pas une improvisation à concevoir depuis zéro.

**Note complémentaire — pérennité des protocoles EAS et EWS**
Grommunio s'appuie sur deux protocoles distincts créés par Microsoft pour Exchange : **EAS (Exchange ActiveSync)**, protocole léger XML/HTTP dédié à la synchro mobile (mail/agenda/contacts, cf. 1.1), et **EWS (Exchange Web Services)**, API SOAP plus riche utilisée par les clients desktop (Outlook, Apple Mail, Thunderbird, cf. 1.9). Microsoft a annoncé en 2026 des évolutions sur les deux, à ne pas confondre :
- **EAS** : pas de retrait du protocole, mais un durcissement côté Exchange Online — blocage des versions de protocole antérieures à 16.1 (1er mars 2026) et retrait de l'authentification par certificat *directe* au profit d'Entra ID (fin 2026).
- **EWS** : retrait réel et complet côté Exchange Online — désactivation progressive à partir du 1er octobre 2026, arrêt définitif le 1er avril 2027, au profit de Microsoft Graph.

**Point déterminant pour ce projet** : ces deux annonces ne concernent explicitement que **Exchange Online** (le service cloud Microsoft 365) — Microsoft précise à chaque annonce l'absence de changement pour Exchange Server on-premises. Grommunio n'est ni l'un ni l'autre : c'est une implémentation indépendante et open source de ces mêmes protocoles documentés (MS-ASProtocol, MS-EWS*), qui n'a aucune obligation de suivre le calendrier de retrait de Microsoft sur son propre service — sa release de juin 2026 montre au contraire un développement actif d'EAS (ajout de l'impersonation). **Impact sur le projet : nul à court/moyen terme**, et une confirmation indirecte de la logique de sortie d'Office 365 : le cabinet cesse précisément de dépendre de la feuille de route d'Exchange Online. Seul point de vigilance à plus long terme, de nature différente : si Microsoft n'utilise plus EWS/EAS dans son propre service, les éditeurs de clients tiers (Apple, Mozilla) ont un peu moins d'incitation à investir dans le maintien de ce support sur la durée — un risque d'écosystème à surveiller, pas un risque de disponibilité immédiate côté Grommunio.

---

### 1.2 Messagerie instantanée / tchat d'entreprise (remplace Teams-chat)

**Besoin fonctionnel**
Tchat interne temps réel, salons de discussion, historique consultable, chiffrement de bout en bout, clients mobiles et desktop matures.

**Alternatives possibles**
- **Matrix** : protocole fédéré, E2EE activé par défaut dans les rooms privées, écosystème client riche.
- **XMPP** : protocole plus ancien et plus léger en ressources, mais E2EE dépendant du choix du client, et écosystème d'extensions (XEP) plus fragmenté et plus complexe à gérer en pratique — chaque fonctionnalité au-delà du socle (chiffrement, notifications, historique multi-appareils) dépend d'une extension optionnelle, ce qui impose de vérifier au cas par cas que chaque client/serveur retenu implémente bien les mêmes XEP, contrairement à Matrix où ces fonctionnalités sont intégrées au socle du protocole.

**Critères de choix**
- Alignement avec l'écosystème étatique français : Matrix a été déployé pour 400 000 fonctionnaires via Tchap, l'application de messagerie de l'État — signal fort de légitimité institutionnelle et de support communautaire francophone.
- Empreinte ressources : Matrix (Synapse) est plus gourmand que XMPP, car son architecture réplique l'historique de conversation sur chaque serveur participant, contre une transmission simple côté XMPP.
- Maturité UX pour utilisateurs non techniques : meilleure côté Matrix/Element.

**Conclusion — brique retenue**
**Matrix**, via le homeserver **Synapse** (voir alternatives de homeserver ci-dessous) et le client **Element**. Alignement avec Tchap/DINUM retenu comme un atout stratégique pour un cabinet de conseil dont les clients incluent potentiellement des acteurs publics.

Dimensionnement retenu (recommandations officielles Element) :
- 100 utilisateurs : ~2 CPU / 2 Go (Synapse) + 2 CPU / 6 Go (Postgres)
- 2000 utilisateurs : ~6 CPU / 5,6 Go (Synapse) + 4 CPU / 18 Go (Postgres)
- **Au-delà** : Synapse supporte un mode « workers », qui sépare les différentes fonctions du homeserver (fédération, synchronisation, envoi de messages) sur plusieurs processus/machines pour scaler horizontalement — c'est ce mode qui doit être retenu comme cible d'architecture dès le départ pour ce cabinet, plutôt que le mode monolithique, afin d'absorber la croissance sans repenser l'architecture Matrix. C'est aussi l'un des critères qui a pesé en faveur de Synapse contre Dendrite/Continuwuity (cf. ci-dessous), aucun des deux ne proposant une voie de scalabilité aussi mature.

**Alternatives de homeserver Matrix (note complémentaire)**
Deux alternatives à Synapse ont été évaluées pour réduire l'empreinte ressources :
- **Dendrite** (Go, projet officiel Element) : empreinte mémoire nettement plus légère (256-512 Mo), mais **en mode maintenance** (seuls des correctifs de sécurité sont appliqués, plus de nouvelles fonctionnalités), **sans support SSO/OIDC natif** et sans haute disponibilité — incompatible avec l'architecture SSO Keycloak retenue pour ce projet. **Écarté.**
- **Continuwuity** (Rust, fork de Conduit/Conduwuit) : le plus léger des trois en ressources, mais gouvernance de projet communautaire encore jeune et instable (plusieurs forks successifs). À réévaluer uniquement après vérification de son support SSO/OIDC à jour, pas retenu en l'état pour une mise en production cliente.

→ **Synapse reste le seul choix mature avec support SSO complet et haute disponibilité (mode workers)**, malgré son coût ressources plus élevé.

---

### 1.3 Visioconférence (remplace Teams-visio)

**Besoin fonctionnel**
Réunions vidéo avec partage d'écran et caméra simultanés, accès par ligne téléphonique classique (RTC/PSTN) pour les participants sans accès IP, transcription automatique, enregistrement de la réunion, arrière-plan flouté/virtuel, capacité à recevoir des participants externes via un simple lien.

**Alternatives possibles**
- **Visio (DINUM/LaSuite numérique)** : solution de visioconférence souveraine de l'État français, hébergeable en auto-hébergement, construite sur **LiveKit** (confirmé : le dépôt officiel `suitenumerique/meet`, licence MIT, est décrit comme *"powered by LiveKit"*, optimisé pour des réunions de plus de 100 personnes). La confusion initiale avec Jitsi provenait d'un autre outil de l'écosystème DINUM, **Webconf**, un service distinct basé sur Jitsi — Visio/Meet et Webconf sont deux produits différents de La Suite numérique, seul Visio étant retenu dans ce document.
- **Element Call** : application de visioconférence native à Matrix, construite sur le protocole MatrixRTC, utilisant LiveKit comme backend SFU, embarquée nativement dans Element Web/Element X.

**Critères de choix**
- RTC/PSTN : fonctionnalité confirmée disponible côté Visio DINUM (pont téléphonique côté infrastructure serveur, indépendant du client web) ; non confirmée côté Element Call.
- Intégration native au fil de discussion Matrix : Element Call est nativement un widget de room Matrix (pas de développement d'intégration nécessaire) ; Visio DINUM nécessite un connecteur pour la même continuité de fil textuel.
- Fonctionnalités avancées (partage d'écran + caméra simultané, transcription auto, arrière-plan flouté) : disponibles nativement côté Visio DINUM. Côté **Element Call**, le partage d'écran simultané par plusieurs participants et le floutage d'arrière-plan sont confirmés comme fonctionnalités natives ; en revanche, **aucune fonctionnalité de transcription automatique ni d'enregistrement natif n'a été identifiée** pour Element Call à ce jour — ce qui en fait, avec le RTC/PSTN, des critères de différenciation supplémentaires en faveur de Visio DINUM pour les réunions qui en ont besoin. Ces fonctionnalités reposent par ailleurs sur des couches indépendantes de l'affichage (traitement serveur pour la transcription et le pont téléphonique, traitement client-side WebGL/WebAssembly pour le flou d'arrière-plan) et restent donc disponibles côté Visio même si celui-ci est intégré en widget/iframe dans une autre application, sous réserve de configuration correcte des permissions d'iframe (`allow="camera *; microphone *; display-capture *"` et `frame-ancestors` ouvert vers le domaine hébergeant le widget).
- Enregistrement de réunion : fonctionnalité disponible en bêta côté Visio DINUM (capture vidéo + audio de la réunion). L'instance publique de la DINUM applique une rétention de 7 jours avant suppression automatique, mais il s'agit très probablement d'une politique d'exploitation propre à cette instance (règle de cycle de vie sur son propre stockage), pas d'une limite du logiciel — en auto-hébergement, cette rétention est configurée par le cabinet lui-même (voir 2.12, plateforme vidéo d'entreprise, pour le traitement complet de ce point).

**Conclusion — brique retenue**
**Les deux produits sont conservés en complémentarité**, plutôt qu'un remplacement de l'un par l'autre :
- **Visio (DINUM), auto-hébergé**, pour les réunions nécessitant le pont téléphonique RTC/PSTN, la transcription automatique ou l'enregistrement (fonctionnalités non retrouvées côté Element Call).
- **Element Call** pour les appels ad hoc intégrés nativement au fil de discussion Matrix, sans développement complémentaire.

Un chantier d'intégration spécifique (voir chapitre 2) doit permettre de démarrer une réunion Visio DINUM directement depuis une room Element avec continuité du fil textuel avant/pendant/après.

---

### 1.4 Synchronisation et stockage de fichiers (remplace OneDrive/SharePoint)

**Besoin fonctionnel**
Stockage de fichiers, synchronisation multi-appareils, partage de dossiers/liens, performance de synchronisation acceptable sur de gros volumes.

**Alternatives possibles**
- **Seafile** : architecture de synchronisation dédiée, réputée légère et performante.
- **Nextcloud Files** : synchronisation reposant sur WebDAV, plus lourde/moins performante que Seafile sur ce point précis, mais écosystème d'applications et d'intégrations beaucoup plus large.

**Critères de choix**
- Performance pure de synchronisation sur gros volumes : avantage Seafile.
- Écosystème d'intégrations prêtes à l'emploi (recherche unifiée, notifications, bridges tiers) : avantage Nextcloud, mais au prix d'un moteur de fichiers moins performant et d'une stack PHP jugée datée pour ce projet.
- Dimensionnement : Seafile est réputé léger côté CPU/RAM ; le facteur dimensionnant réel est le volume de données stockées et la fréquence de synchronisation, pas le nombre d'utilisateurs actifs simultanés.

**Conclusion — brique retenue**
**Seafile**, pour la performance de synchronisation. Le manque d'écosystème d'intégration (recherche unifiée, notifications) par rapport à Nextcloud est traité comme un chantier transverse dédié (voir chapitre 2), plutôt que de sacrifier la performance de la brique de stockage elle-même.

Dimensionnement retenu : serveur modeste (4-8 cœurs, 8-16 Go RAM) suffisant pour 100 comme 2000 utilisateurs ; le stockage disque et la bande passante de synchronisation sont les vrais facteurs de dimensionnement, pas le CPU. **Point tranché pour la trajectoire de croissance au-delà de 2000 utilisateurs** : le clustering/scaling horizontal de Seafile (plusieurs nœuds frontaux derrière un load balancer, partageant un cache mémoire commun) est documenté exclusivement pour l'**édition Pro** (propriétaire, payante) — aucune documentation officielle de clustering n'existe pour l'édition Community. Concrètement : l'édition Community reste mono-nœud, scalable uniquement verticalement (plus de CPU/RAM/disque sur la même machine), ce qui a une limite mécanique. **Ce point remet en cause partiellement l'objectif de rester en tout-open-source à très grande échelle** : au-delà du seuil où le scaling vertical d'un nœud Seafile Community ne suffit plus, la seule voie documentée pour poursuivre la croissance est de basculer vers Seafile Pro (licence payante), ce qui doit être anticipé budgétairement dans la trajectoire de croissance plutôt que découvert au moment où le mur de charge est atteint.

---

### 1.5 Édition collaborative de documents (remplace Word/Excel/PowerPoint Online)

**Besoin fonctionnel**
Édition collaborative en temps réel de documents bureautiques (traitement de texte, tableur, présentation), compatibilité avec les formats Office existants (dix ans d'archives à conserver), intégration avec le stockage de fichiers.

**Alternatives possibles**
- **OnlyOffice (Community Edition, Document Server)**.
- **Collabora Online (CODE)** : suite basée sur le moteur LibreOffice, comparée en détail ci-dessous.

**Tableau comparatif — OnlyOffice et Collabora Online**

| Critère | OnlyOffice (Community/Docs) | Collabora Online (CODE) |
|---|---|---|
| **Moteur / format natif** | Moteur propre, format natif **OOXML** (.docx/.xlsx/.pptx) — les fichiers Word/Excel/PowerPoint sont lus et écrits directement, sans étape de conversion | Moteur **LibreOffice**, format natif **ODF** — tout fichier OOXML passe par une conversion à l'ouverture et à l'enregistrement |
| **Fidélité de compatibilité Word/Excel/PowerPoint** | Reconnue comme le point fort du produit, du fait du format natif partagé avec Microsoft Office | Bonne compatibilité générale, mais la conversion ODF↔OOXML peut introduire des écarts de mise en forme sur des documents complexes (macros, présentations avec médias embarqués) |
| **Licence du cœur** | AGPLv3 | Mozilla Public License 2.0 |
| **Limite de l'édition gratuite** | **Levée depuis la version 9.4** (mai 2026) : plus de plafond de connexions simultanées sur l'édition Community (cf. 1.5 ci-dessus) | **Plafond permanent et assumé** : l'édition gratuite (CODE) reste limitée à 10 documents / 20 connexions simultanées par conception — l'éditeur la présente explicitement comme non destinée à la production (« not recommended for a production environment »), au contraire d'un plafond appelé à disparaître |
| **Voie de sortie du plafond** | Aucune nécessaire : la Community Edition ≥ 9.4 est utilisable en production sans limite de connexions, sans coût de licence récurrent | Nécessite un abonnement payant (Collabora Online / Enterprise) pour lever le plafond et obtenir un support — modèle par abonnement annuel |
| **Intégration Seafile** | Connecteur officiel documenté par OnlyOffice | **Également documentée officiellement**, par Seafile lui-même (paramètre `OFFICE_SERVER_TYPE = 'CollaboraOffice'`, protocole WOPI) — ce critère ne différencie donc pas les deux solutions, contrairement à ce qu'on pourrait supposer |
| **Architecture / dépendances** | Simplifiée depuis la version 9.4 (processus unique, suppression de RabbitMQ et des bases de données externes) | Architecture réputée minimale par l'éditeur (Linux + protocole WOPI), sans dépendance à un bus de message ou une base de données dédiée |
| **Éditeur / juridiction** | Ascensio System SIA, enregistrée en Lettonie (UE) — **point à nuancer, cf. note ci-dessous** | Collabora Productivity Ltd, Cambridge, Royaume-Uni |

**Conclusion du comparatif** : le point réellement décisif pour ce projet est le **plafond de connexions de l'édition gratuite**. Celui d'OnlyOffice a disparu en 2026 et l'édition Community devient pleinement utilisable en production sans coût de licence récurrent. Celui de Collabora (CODE) est **permanent et assumé par l'éditeur lui-même** : passer à l'échelle avec Collabora impose un abonnement payant, ce qui réintroduit exactement le type de coût de licence récurrent que ce projet cherche à éliminer — un point qui pèse lourd compte tenu de l'ambition de croissance du cabinet (100 → 2000+ utilisateurs). Sur la compatibilité des formats, l'avantage va à OnlyOffice de par son format natif partagé avec Microsoft Office, ce qui correspond directement au besoin fonctionnel énoncé (dix ans d'archives Office à conserver).

**Euro-Office — le fork souverain d'OnlyOffice, analysé en détail**

**Contexte** : le 27 mars 2026, un consortium d'acteurs européens (Nextcloud, IONOS, Proton, XWiki, OpenProject, Eurostack, Open-Xchange, BTactic, Soverin, Abilian) a lancé **Euro-Office**, un fork d'OnlyOffice Document Server. Motivation explicitement affichée : Ascensio System SIA, l'éditeur d'OnlyOffice, est enregistrée en Lettonie (UE), mais une partie significative de son équipe de développement serait basée en Russie selon le consortium — un point que l'éditeur lui-même ne dément pas ouvertement. C'est exactement le type de dépendance que ce projet cherche à éliminer (cf. introduction), au même titre que la question Outlook pour Mac (1.9) ou la bascule payante de Zimbra (tableau ci-dessus).

**Ce qui joue en faveur d'Euro-Office**
- **Drop-in réel, pas une simple façade** : le code est directement dérivé d'OnlyOffice Document Server et conserve la même API REST — les intégrateurs (Nextcloud, ownCloud, et par extension tout connecteur pensé pour OnlyOffice comme celui de Seafile) devraient fonctionner sans modification. Ce n'est pas confirmé nommément pour Seafile à ce stade, mais découle directement de la nature du fork.
- **Modèle intégralement gratuit, sans édition payante propre au projet** : contrairement à OnlyOffice qui conserve des éditions Enterprise/Developer payantes au-dessus de la Community Edition désormais illimitée, Euro-Office n'a annoncé aucune offre commerciale équivalente — financé par les contributions directes des entreprises du consortium plutôt que par la vente de licences.
- **Gouvernance et image de marque alignées avec la logique de souveraineté déjà tenue dans ce document.**

**Ce qui appelle à la prudence, avant tout remplacement**
- **Projet très jeune** : première version stable datée du 9 juin 2026, soit à peine trois mois avant la rédaction de ce document. Un contributeur de la communauté Cloudron résume bien le risque : « *first stable is literally days old, so expect rapid version churn* ». C'est le même niveau de prudence que ce document applique déjà à d'autres fonctionnalités très récentes (GAL CardDAV de Grommunio, EAS-4-TbSync) — nouveau n'est pas disqualifiant, mais impose une validation avant adoption en production.
- **Litige juridique non tranché** : Ascensio System accuse Euro-Office d'avoir violé les clauses de marque et d'attribution de la licence AGPLv3 (section 7) en retirant le logo et les mentions OnlyOffice du code. Le consortium conteste. Tant que ce litige n'est pas résolu, un doute plane sur la stabilité du nom, de la marque, voire du statut légal du fork à moyen terme — un risque à ne pas transférer sur l'infrastructure d'un client sans en avoir conscience.
- **Architecture technique possiblement moins simplifiée qu'OnlyOffice ≥ 9.4** : Euro-Office 1.0 semble dérivé d'une version d'OnlyOffice antérieure à la simplification architecturale de la version 9.4 (processus unique, suppression de RabbitMQ/base de données externe, cf. ci-dessus) — sa documentation mentionne encore une pile Node.js/PostgreSQL/RabbitMQ/Redis/nginx complète. **À vérifier explicitement** avant toute bascule : Euro-Office a-t-il également hérité de la suppression du plafond de connexions, ou repart-il de la base pré-9.4 qui l'imposait encore ?
- **Ironie relevée par la communauté elle-même, à noter pour mémoire sans en tirer de conclusion disqualifiante** : le dépôt du projet est hébergé sur GitHub, plateforme détenue par Microsoft — un détail cocasse au regard du positionnement « souverain », mais qui ne remet pas en cause la souveraineté du code lui-même, seulement celle de sa plateforme de développement.

**Conclusion sur ce point** : **Euro-Office ne remplace pas OnlyOffice Community ≥ 9.4 comme brique retenue dans ce document, à ce stade** — le projet est trop jeune, sur un litige juridique non tranché, et son alignement avec les gains architecturaux d'OnlyOffice 9.4 (suppression du plafond de connexions et simplification) n'est pas confirmé. **Il est en revanche identifié comme un candidat sérieux à ré-évaluer dans une prochaine itération de ce document**, une fois sa maturité, l'issue du litige AGPL, et sa compatibilité effective avec le connecteur Seafile établies — le jour où ces réserves seront levées, il répondrait mieux que OnlyOffice à la motivation de souveraineté posée dès l'introduction, sans sacrifier la compatibilité de formats qui a fait retenir OnlyOffice face à Collabora.

**Critères de choix**
- Compatibilité de formats Word/Excel/PowerPoint : bon niveau de compatibilité reconnu pour OnlyOffice, renforcé par la comparaison avec Collabora ci-dessus (format natif partagé vs conversion ODF↔OOXML).
- Intégration avec Seafile : connecteur officiel Seafile ↔ OnlyOffice Document Server existant, permettant l'édition en ligne directement depuis le stockage (pas seulement un visualiseur) — Collabora dispose d'une intégration Seafile tout aussi officielle, ce critère ne départage donc pas les deux solutions à lui seul.
- Limite historique de licence Community Edition : plafond de 20 connexions simultanées, **supprimé à partir de la version 9.4** (mai 2026), qui a par ailleurs simplifié l'architecture (processus unique, suppression des dépendances RabbitMQ et bases de données externes), réduisant la consommation de ressources — un avantage décisif par rapport au plafond permanent de Collabora CODE (cf. tableau ci-dessus).
- Dimensionnement à l'échelle réelle : un benchmark public (Enterprise Edition v6.3) situe la charge maximale garantie à ~1000 connexions simultanées sur un serveur 4 cœurs / 8 Go RAM / 8 Go swap. Une connexion correspond à un onglet navigateur avec un document ouvert pour édition (un même document ouvert par deux utilisateurs compte pour deux connexions) ; au-delà de la capacité, les documents supplémentaires s'ouvrent en lecture seule sans erreur ni plantage.

**Conclusion — brique retenue**
**OnlyOffice Community Edition (≥ 9.4)**, intégré à Seafile via le connecteur officiel.

Pour un scénario de charge de type « 100 consultants × 20 documents ouverts en parallèle » (2000 connexions potentielles) :
- Ordre de grandeur de dimensionnement : ~8 cœurs / 16 Go RAM minimum, avec marge, à valider par un test de charge réel (JMeter) avant mise en production.
- Prévoir un monitoring actif du nombre de connexions pour détecter la bascule en lecture seule avant que les utilisateurs ne s'en plaignent.
- Architecture cible recommandée au-delà d'un certain seuil : cluster Document Server avec load balancer et stockage de session Redis, plutôt qu'une instance unique. **Compte tenu de l'ambition de croissance du cabinet, cette architecture en cluster doit être retenue comme cible dès la conception initiale**, plutôt que comme une évolution ultérieure — le passage d'une instance unique à un cluster horizontal étant plus simple à anticiper dans l'infrastructure (chapitre 4) qu'à rétrofitter une fois la charge devenue critique.
- Nuance importante : le dimensionnement ci-dessus part du principe d'une édition active simultanée sur tous les documents ouverts ; si une part significative des documents sont ouverts en arrière-plan sans édition active, la charge réelle est inférieure au pire cas.

---

### 1.6 Gestion de tâches (remplace Planner/To Do)

**Besoin fonctionnel**
Gestion de tâches individuelles et d'équipe, listes partagées, échéances.

**Alternatives possibles**
- **Vikunja** : application légère (Go + base de données), API ouverte.
- **OpenProject**, **Focalboard**, **Planka** : comparés ci-dessous.

**Tableau comparatif — Vikunja et les alternatives de gestion de tâches**

| Critère | Vikunja | OpenProject | Focalboard | Planka |
|---|---|---|---|---|
| **Positionnement** | Gestionnaire de tâches léger avec vues multiples (liste, Kanban, Gantt, table) | Suite de gestion de projet complète (Gantt, planification de ressources, suivi de coûts, pistes d'audit) | Tableaux façon Notion/Trello, issu de l'écosystème Mattermost | Tableau Kanban pur, orienté simplicité visuelle |
| **Ancienneté / communauté** | 7-8 ans, ~4 400-5 000 étoiles GitHub | 13 ans, ~15 000 étoiles — communauté nettement plus large | 6 ans, ~26 000 étoiles — mais activité de développement ralentie (dernier commit à plusieurs mois d'écart contre quelques heures pour Vikunja) | En développement depuis 2019, ~11 000-12 000 étoiles |
| **Activité de maintenance actuelle** | Très active (commits à quelques heures d'intervalle) | Très active | Ralentie ces derniers mois par rapport à Vikunja | Active |
| **Intégration calendrier (CalDAV)** | Native | Disponible mais secondaire dans une suite plus large | Non mise en avant | Non mise en avant |
| **Adéquation au besoin exprimé** (gestion de tâches individuelles/équipe, listes partagées, échéances — pas un outil de PM complet) | **Correspond précisément au périmètre** | **Surdimensionné** : conçu pour des organisations gérant plusieurs projets concurrents avec pistes d'audit et permissions fines — complexité et charge d'exploitation disproportionnées par rapport au besoin « Planner/To Do » | Pertinent pour des tableaux visuels, mais sans le suivi d'échéances structuré ni l'intégration calendrier attendue | Pertinent pour du Kanban simple, mais plus limité que Vikunja sur le suivi de tâches individuelles structurées (listes, échéances, sous-tâches) |

Ce comparatif confirme le choix initial plutôt que de le remettre en cause : **OpenProject serait un mauvais calcul** — non pas parce qu'il est moins bon, mais parce qu'il résout un problème plus large (gestion de projet complète) que celui posé ici (remplacer Planner/To Do), au prix d'une complexité et d'une charge d'exploitation inutiles. **Focalboard et Planka** restent pertinents pour un usage tableau/Kanban pur, mais correspondent moins bien au besoin explicite de suivi d'échéances et d'intégration calendrier. Vikunja reste le choix le mieux calibré pour le périmètre fonctionnel exact demandé, avec l'avantage supplémentaire d'une activité de développement actuellement plus soutenue que Focalboard.

**Critères de choix**
- Légèreté et simplicité de déploiement.
- Limite reconnue : plus limité qu'un vrai outil de gestion de projet si les besoins montent en complexité (dépendances de tâches, vues Gantt avancées, etc.) — un scénario où **OpenProject redeviendrait pertinent à réévaluer**, si le besoin du cabinet évolue au-delà d'un simple remplacement Planner/To Do vers une vraie gestion de projet transverse.

**Conclusion — brique retenue**
**Vikunja**, pour son rapport simplicité/couverture fonctionnelle suffisant au périmètre Planner/To Do. Dimensionnement : 2-4 cœurs / 4 Go RAM, suffisant pour 100 comme 2000 utilisateurs sauf usage massif d'API/automatisations.

---

### 1.7 Authentification et identité (SSO)

**Besoin fonctionnel**
Authentification unique fédérée sur l'ensemble des briques de la stack, gestion centralisée des comptes et des accès. À cela s'ajoute un besoin d'**authentification à plusieurs facteurs (MFA)**, avec plusieurs canaux disponibles selon le contexte et le niveau de sécurité recherché : application d'authentification (TOTP, type Google Authenticator/FreeOTP), SMS, OTP par mail, et clé matérielle (type Yubikey) via le protocole ouvert **WebAuthn/FIDO2**.

**Alternatives possibles**
- **Keycloak** : solution IAM/SSO open source de référence, support OIDC/SAML.
- **Authentik**, **Zitadel**, **WSO2 Identity Server** : comparés ci-dessous.

**Tableau comparatif — Keycloak et les alternatives IAM/SSO**

| Critère | Keycloak | Authentik | Zitadel | WSO2 Identity Server |
|---|---|---|---|---|
| **Licence** | Apache 2.0, sans édition payante séparée | MIT (permissive), fonctionnalités avancées sous licence entreprise distincte | Apache 2.0 jusqu'en 2025, passé sous **AGPLv3** depuis — implique de publier toute modification si le service est exposé en réseau | Apache 2.0, avec abonnements commerciaux optionnels pour le support et l'hébergement managé |
| **Protocoles couverts** | OIDC, SAML, **LDAP** (fédération et brokering), le plus large des trois | OIDC, SAML, LDAP, RADIUS, Kerberos — couverture encore plus large sur le papier | OIDC/OAuth uniquement — **pas de serveur LDAP ni RADIUS** | OIDC, SAML, WS-Federation, SCIM — complet sur le papier, mais SAML historiquement traité comme secondaire par rapport à Keycloak selon plusieurs comparatifs |
| **Mode « forward-auth » / proxy natif** | Non natif — nécessite un composant tiers dédié pour les rares applications sans support OIDC | **Natif** (« Authentik Outposts ») — permet de protéger une application qui ne parle ni OIDC ni SAML directement, sans composant tiers séparé | Absent — les applications doivent nativement supporter OIDC/SAML | Absent |
| **Conception cible** | Fédération d'identité large, multi-protocoles, pour des environnements hétérogènes avec applications legacy | Flexible, orienté self-hosters et petites/moyennes structures avec un mélange d'applications (dont certaines sans SSO natif) | **Multi-tenant B2B SaaS** — hiérarchie Instance > Organisation > Projet > Application pensée pour héberger plusieurs organisations clientes, pas le profil de ce projet (un seul cabinet) | **CIAM** (gestion d'identité *clients* externes) avant tout, packagé au sein d'une plateforme d'intégration plus large (API management, enterprise integrator) — pertinent pour une organisation déjà cliente de l'écosystème WSO2, pas le cas ici |
| **Intégration avec l'approche IaC du projet** | Provider Terraform officiel et mature — cohérent avec l'approche IaC retenue au chapitre 4 | Pas de provider Terraform officiel identifié | Pas de provider Terraform officiel identifié | **Pas de provider Terraform** — configuration plus manuelle, à contre-courant de l'approche IaC systématique retenue dans ce document |
| **Complexité d'installation/configuration** | Qualifiée de simple dans les comparatifs communautaires | Réputée accessible (éditeur de flux visuel) | Interface moderne, configuration OIDC simple | **Qualifiée de complexe** dans plusieurs comparatifs communautaires, du fait de son architecture middleware (WSO2 Carbon) plus lourde que celle de Keycloak |
| **Maturité / écosystème** | Le plus ancien et le plus déployé en entreprise des trois, documentation la plus abondante | Écosystème d'intégrations très riche (200+), société éditrice (Authentik Security Inc.) derrière le projet | Plus jeune, mais développement actif (~14 000 étoiles GitHub mi-2026) | Mature (premières versions en 2008), mais conçu et documenté avant tout pour des scénarios CIAM/API, pas pour une fédération d'identité interne pure |

**Ce que ce comparatif révèle de plus intéressant pour ce projet** : le **mode forward-auth natif d'Authentik** aurait été directement pertinent pour un besoin initialement identifié ailleurs dans ce document — l'authentification déléguée envisagée devant Lufi (1.8), qui ne supportait pas nativement OIDC. Ce besoin précis a depuis été résolu autrement : la comparaison menée en 1.8 a conduit à retenir Gokapi à la place de Lufi, précisément parce que Gokapi supporte OIDC nativement et n'a donc plus besoin d'un composant `oauth2-proxy` séparé ni d'un mode forward-auth. Le point reste néanmoins utile à noter : pour toute future brique de la stack qui ne parlerait pas nativement OIDC/SAML, le choix de Keycloak imposera d'ajouter un composant `oauth2-proxy` (ou équivalent) en `forward_auth`, alors qu'Authentik aurait couvert ce cas nativement.

**WSO2, à l'inverse, ne remet rien en cause** : c'est une solution mature et réellement open source (Apache 2.0), mais conçue et packagée avant tout pour du **CIAM** (gestion d'identité de clients externes, souvent couplée à de la gestion d'API) — un profil différent du besoin de ce projet, qui est une fédération d'identité purement interne pour les consultants du cabinet. Deux points concrets pèsent contre WSO2 pour ce projet précis : l'**absence de provider Terraform officiel**, à contre-courant de l'approche IaC systématique retenue au chapitre 4, et une **installation/configuration réputée plus complexe** que celle de Keycloak du fait de son architecture middleware (WSO2 Carbon).

Cela ne suffit cependant pas à faire basculer le choix vers Authentik non plus : Keycloak reste mieux positionné pour ce projet dans son ensemble, pour trois raisons qui pèsent plus lourd que le seul point forward-auth : (1) la fédération LDAP et le brokering SAML de Keycloak sont plus matures et plus larges, utiles si le cabinet doit un jour fédérer un annuaire d'entreprise existant ou interagir avec des partenaires en SAML ; (2) c'est la solution la plus éprouvée en environnement d'entreprise hétérogène, exactement le profil de ce projet (Grommunio, Seafile, Vikunja, OnlyOffice, Matrix/Synapse) ; (3) Zitadel est structurellement écarté, son modèle multi-tenant B2B ne correspondant pas à un déploiement mono-organisation, et son passage récent à l'AGPLv3 imposant une vigilance de conformité supplémentaire. **Le besoin initialement identifié pour Lufi (1.8) est finalement résolu sans forward-auth du tout**, grâce au choix de Gokapi plutôt que de Lufi — mais le point mérite d'être noté explicitement pour toute future brique sans support OIDC natif, plutôt que découvert a posteriori.

**Critères de choix**
- Compatibilité OIDC native de chaque brique de la stack : à vérifier service par service (Grommunio, Seafile, Vikunja et OnlyOffice supportent OIDC ; Matrix/Synapse également via provider OIDC).
- Dimensionnement piloté par le nombre de connexions par seconde, pas par le nombre total d'utilisateurs.
- **Couverture MFA native de Keycloak, canal par canal** :
  - **Application d'authentification (TOTP/HOTP)** : nativement supporté, sans développement — configurable directement dans les flux d'authentification standards.
  - **Clé matérielle (Yubikey et équivalents) via WebAuthn/FIDO2** : nativement supporté par Keycloak, à la fois comme second facteur et comme facteur principal sans mot de passe (passkey) — c'est le protocole ouvert et standardisé (W3C/FIDO Alliance) que vous aviez en tête, et il couvre aussi bien les clés matérielles dédiées que les authentificateurs de plateforme (Touch ID, Windows Hello).
  - **OTP par SMS** : **non couvert nativement par Keycloak** — nécessite le développement d'un connecteur custom (Service Provider Interface Keycloak) relié à une passerelle SMS, ou une extension tierce.
  - **OTP par mail** : **non couvert nativement par Keycloak** non plus, pour la même raison — également à développer via SPI custom.
- Ces deux derniers canaux (SMS, mail) rejoignent donc la liste des connecteurs à développer identifiés ailleurs dans ce document (cf. chapitre 2), plutôt que d'être de simples cases à cocher dans la configuration de Keycloak.

**Conclusion — brique retenue**
**Keycloak**, en SSO/IAM central pour l'ensemble de la stack, avec **TOTP et WebAuthn/FIDO2 activés nativement** dès le déploiement initial (aucun développement requis pour ces deux canaux). L'**OTP par SMS et par mail nécessite le développement d'un SPI Keycloak custom** — à traiter comme un chantier de développement à part entière, pas comme une simple option de configuration, et à prioriser selon les canaux réellement demandés par les consultants (le couple TOTP + WebAuthn couvre déjà un niveau de sécurité élevé, y compris phishing-résistant pour WebAuthn). Dimensionnement : 2-4 cœurs / 4-8 Go RAM avec base Postgres dédiée, pour les deux échelles (100 et 2000 utilisateurs) en usage bureautique classique. Point de vigilance : prévoir un cluster Keycloak en haute disponibilité dès la cible initiale, le SSO devenant un point individuel de défaillance critique pour l'ensemble des autres services — d'autant plus critique dans une trajectoire de croissance, puisque toute panne de Keycloak bloquerait l'accès à l'ensemble de la stack pour un effectif toujours plus grand. Keycloak est nativement conçu pour du clustering horizontal (plusieurs nœuds derrière un load balancer, cache distribué), ce qui ne pose pas de difficulté connue pour suivre la croissance du cabinet au-delà de 2000 utilisateurs.

---

### 1.8 Mise à disposition de gros fichiers avec chiffrement dans le navigateur

**Besoin fonctionnel**
Transmettre ponctuellement un fichier volumineux à un destinataire (interne ou externe au cabinet) via un simple lien, sans les contraintes de taille des pièces jointes mail, et avec une garantie de confidentialité forte — y compris vis-à-vis de l'administrateur de la plateforme elle-même. C'est un besoin distinct du partage de fichiers structurel couvert par Seafile (1.4) : ici, il s'agit d'un dépôt ponctuel à durée de vie courte, pensé pour l'échange externe. À cela s'ajoute un besoin de restreindre le dépôt aux personnes authentifiées, pour éviter que l'instance ne serve à héberger des fichiers illicites de façon anonyme.

**Alternatives possibles**
- **Lufi** (`ldidry/lufi`) : outil de dépôt de fichiers volumineux avec chiffrement entièrement réalisé côté navigateur.
- **Gokapi** (`Forceu/Gokapi`) : alternative comparée en détail ci-dessous.
- Services commerciaux type WeTransfer — écartés, contraires à la logique de souveraineté du projet et sans garantie de chiffrement de bout en bout équivalente.
- Un simple lien de partage Seafile — ne fournit pas de chiffrement de bout en bout : le serveur Seafile a accès en clair au contenu du fichier partagé.

**Tableau comparatif — Lufi et Gokapi**

| Critère | Lufi | Gokapi |
|---|---|---|
| **Chiffrement de bout en bout** | **Systématique** : tous les dépôts sont chiffrés côté navigateur, sans option pour désactiver ce comportement. Clé encodée dans le fragment d'ancre de l'URL (`#`), jamais transmise au serveur. | **Optionnel, à trois niveaux** : niveau 1 (fichiers locaux uniquement), niveau 2 (local + stockage cloud, déchiffrement client-side), niveau 3 = véritable E2EE (chiffrement client-side, le serveur compromis ne peut rien révéler). Le niveau 3 doit être **choisi explicitement à la configuration**, ce n'est pas le comportement par défaut. **Avertissement de l'éditeur lui-même : le chiffrement n'a pas été audité.** |
| **Authentification du dépôt** | Native, mais **uniquement via LDAP** — pas de support OIDC/SAML, incompatible avec un branchement direct sur Keycloak. | **Support OIDC natif documenté**, avec des identités providers cités nommément dont Keycloak — branchement direct sur le SSO déjà retenu (1.7), sans composant intermédiaire. |
| **Gestion des utilisateurs** | Basique (authentification uniquement) | **Comptes multiples avec permissions fines par utilisateur et par clé API** — chaque dépôt est nativement associé à un compte, pas seulement tracé a posteriori. |
| **Traçabilité du déposant** | Non native — nécessite une corrélation externe entre les logs du reverse proxy et l'identifiant de fichier (cf. ancienne architecture ci-dessous) | **Native** : chaque fichier déposé est directement rattaché en base à l'utilisateur authentifié qui l'a déposé, sans corrélation externe à construire. |
| **Maturité de l'implémentation E2EE** | Éprouvée à grande échelle (Framasoft l'exploite en production sous le nom Framadrop depuis plusieurs années) | Plus récente, **non auditée selon l'éditeur** ; un bug de compatibilité connu existe avec Firefox pouvant tronquer les fichiers téléchargés en E2EE. |
| **Cas particulier des dépôts externes (« File Request »)** | N/A (pas de mécanisme équivalent) | Une fonctionnalité permet de générer un lien pour que des tiers externes déposent un fichier sans compte — mais **ces dépôts contournent le chiffrement E2EE**, stockés sans le niveau 3, même si celui-ci est activé par ailleurs sur le serveur. À ne pas utiliser si la confidentialité doit rester garantie pour tous les dépôts. |
| **Licence / écosystème** | AGPL, Perl/Mojolicious, ancré dans l'écosystème du logiciel libre francophone | AGPL-3.0, Go, léger (256 Mo RAM minimum), actif (2,8k étoiles GitHub) |
| **API/CLI** | Client en ligne de commande et API scriptable | REST API complète, CLI dédié (`gokapi-cli`) |

**Ce que ce comparatif tranche** : le point décisif est l'**authentification native OIDC de Gokapi**, qui répond directement et simplement au besoin de restriction du dépôt posé plus haut — sans le détour par LDAP ou par un composant `oauth2-proxy` séparé qu'aurait exigé Lufi (cf. ancienne architecture, désormais obsolète, conservée en note historique en fin de section). En contrepartie, deux réserves sérieuses doivent être objectivées avant la mise en production : le chiffrement E2EE de Gokapi n'est **pas audité** (contre une implémentation Lufi éprouvée à grande échelle), et l'option E2EE doit être **activée explicitement** (niveau 3) plutôt que d'être le comportement par défaut — un point de configuration à ne pas manquer, faute de quoi la garantie de confidentialité de bout en bout ne serait qu'apparente.

**Critères de choix**
- Le besoin de confidentialité forte reste couvert par Gokapi **à condition d'activer explicitement le niveau de chiffrement 3** — ce n'est pas automatique, contrairement à Lufi où c'est le seul mode de fonctionnement possible.
- Le besoin de restriction du dépôt aux personnes authentifiées est mieux couvert nativement par Gokapi (OIDC direct vers Keycloak) que par Lufi (LDAP uniquement), qui aurait nécessité soit un second annuaire LDAP, soit un connecteur `oauth2-proxy` en `forward_auth` devant le reverse proxy.
- La fonctionnalité « File Request » de Gokapi (dépôt par un tiers externe sans compte) ne doit **pas** être activée pour ce projet, ou seulement en connaissance de cause : elle contourne le chiffrement E2EE, ce qui romprait la garantie de confidentialité pour ces dépôts précis.
- Le chiffrement non audité de Gokapi est un risque à documenter explicitement auprès du cabinet, en le mettant en balance avec le gain d'intégration OIDC — un audit de sécurité indépendant, ou à défaut une veille active sur les issues de sécurité du projet, est recommandé avant un déploiement à grande échelle.
- Configuration Keycloak à suivre avec vigilance particulière : le changelog de Gokapi mentionne explicitement une correction de sa documentation Keycloak après qu'un exemple de configuration antérieur permettait un accès non autorisé — **utiliser impérativement la documentation à jour au moment du déploiement**, pas un exemple archivé ou une capture d'écran ancienne.

**Traçabilité du dépôt**
Contrairement à l'architecture qu'aurait nécessitée Lufi (corrélation entre les logs du reverse proxy et l'identifiant de fichier, cf. note historique ci-dessous), Gokapi associe nativement chaque fichier déposé au compte utilisateur authentifié dans sa propre base de données — la traçabilité ne nécessite pas de connecteur ni de journalisation externe à développer. Restent à définir : la durée de rétention de ces journaux internes (cohérente avec les obligations légales de conservation des données de connexion, LCEN pour un service accessible en France), et la procédure de signalement/retrait — qui, côté cabinet, est habilité à consulter l'association fichier/déposant sur signalement d'un tiers ou d'une autorité, et à déclencher la suppression du fichier.

**Conclusion — brique retenue**
**Gokapi**, auto-hébergé, en remplacement de Lufi initialement envisagé — pour la mise à disposition ponctuelle de fichiers volumineux nécessitant une confidentialité renforcée, en complément de Seafile qui reste la brique de partage de fichiers structurel et durable (1.4). Le choix se justifie par l'authentification OIDC native vers Keycloak (1.7), qui évite tout composant intermédiaire, et par une traçabilité du dépôt intégrée nativement plutôt que reconstruite. **Deux conditions doivent impérativement être respectées au déploiement** : activer explicitement le niveau de chiffrement 3 (E2EE) plutôt que de se fier à un défaut moins protecteur, et ne pas activer la fonctionnalité « File Request » si la confidentialité doit rester garantie pour tous les dépôts. Le chiffrement non audité de Gokapi reste un point de vigilance à documenter auprès du cabinet, sans être disqualifiant au vu du gain d'intégration obtenu.

**Note historique — architecture initialement envisagée avec Lufi (conservée pour mémoire)**
Avant la comparaison ci-dessus, l'authentification du dépôt avec Lufi avait été conçue via une authentification déléguée au niveau du reverse proxy (Caddy + `oauth2-proxy` en OIDC), Lufi ne supportant que LDAP nativement : `oauth2-proxy` aurait été déployé comme conteneur dédié dans Kubernetes (cf. 4.3), configuré comme client OIDC confidentiel dans un realm Keycloak, avec une directive `forward_auth` sur les routes de dépôt uniquement (les routes de téléchargement et de suppression restant non gatées pour permettre l'usage externe). La traçabilité aurait alors reposé sur une journalisation côté reverse proxy (identité, horodatage, IP) corrélée a posteriori avec l'identifiant de fichier Lufi — une corrélation externe que Gokapi rend inutile grâce à son modèle de comptes utilisateurs natif.

---

### 1.9 Client mail lourd sur poste de travail (complément à grommunio-web)

**Besoin fonctionnel**
Au-delà du webmail (grommunio-web) et des clients mobiles (1.1), une partie des consultants souhaite un client mail lourd natif sur poste de travail (Windows, Mac, Linux), avec accès complet à la messagerie, au calendrier et aux contacts contre Grommunio — sans dépendre d'un compte ou d'une licence Microsoft pour l'obtenir.

**Alternatives possibles**
- **Thunderbird** : client mail lourd open source, déjà retenu ailleurs dans ce document comme point d'ancrage du mécanisme Filelink pour le dépôt de gros fichiers (1.8, 2.11). Se connecte nativement à Grommunio en EWS (pris en charge par Grommunio en natif et sans plugin depuis la version 2023.11.3) ou en IMAP/CalDAV/CardDAV pour le socle mail/calendrier/contacts — sur la pérennité de ce protocole côté Grommunio malgré son retrait annoncé par Microsoft sur Exchange Online, voir la note complémentaire en 1.1.
- **Apple Mail / Calendrier / Contacts (natifs macOS)** : Grommunio documente une compatibilité native avec la suite Apple via EWS pour le mail et CalDAV/EWS pour le calendrier, CardDAV pour les contacts — sans client tiers à installer sur Mac. Sur l'exposition de l'annuaire d'entreprise (GAL) à ce client via CardDAV, voir 2.13.
- **Outlook pour Mac** : évalué spécifiquement à la demande, cf. ci-dessous.
- **eM Client** : évalué en complément à la demande, cf. note ci-dessous.

**Outlook pour Mac est-il disponible sans abonnement Office 365 ?**
**Oui, mais ce n'est pas le bon critère de décision pour ce projet.**
- **Disponibilité confirmée** : depuis 2023, le « nouveau Outlook » pour Mac est gratuit et ne nécessite plus d'abonnement Microsoft 365 ni de licence Office pour être installé et utilisé — il est même disponible directement sur le Mac App Store, avec une version gratuite (publicités affichées pour les comptes personnels gratuits type Gmail/IMAP, sans publicité pour un compte professionnel). Grommunio documente d'ailleurs explicitement sa compatibilité avec ce client via EWS.
- **Le problème réel n'est pas la licence, c'est l'architecture réseau du « nouveau Outlook »** : contrairement à l'ancien Outlook (« legacy »), qui se connectait directement au serveur mail configuré, le nouveau Outlook pour Mac (comme ses équivalents Windows/iOS/Android) fonctionne comme une passerelle vers le cloud Microsoft pour tout compte non-Microsoft — y compris un compte configuré en EWS pointant vers un serveur Exchange-compatible auto-hébergé comme Grommunio. Concrètement : les identifiants de connexion et une copie des messages/calendrier/contacts transitent par les serveurs Microsoft (infrastructure Azure), qui se connectent eux-mêmes au serveur Grommunio pour le compte de l'utilisateur, avant de relayer les données au client. Ce mécanisme est documenté par Microsoft lui-même (fonctionnalité « Sync with Microsoft Cloud »/« Sync your account in Outlook to the Microsoft Cloud ») et a fait l'objet de signalements de la part d'autorités de protection des données en Europe (dont le Commissaire fédéral allemand à la protection des données).
- **Incompatibilité directe avec la motivation initiale du projet** : ce mécanisme place une copie du contenu de messagerie du cabinet — potentiellement des correspondances confidentielles avec ses clients — sur l'infrastructure d'un éditeur non européen, exactement la dépendance que ce projet cherche à réduire (cf. introduction). Retenir Outlook pour Mac reviendrait à réintroduire, côté client mail, la dépendance que Grommunio a précisément permis d'éliminer côté serveur.
- **L'ancien Outlook (« legacy »), qui se connecte directement sans relais Microsoft, n'est pas une alternative viable non plus** : sa disponibilité continue nécessite soit un abonnement Microsoft 365, soit une licence Office achetée en une fois (2021/2024) liée à un compte Microsoft personnel ou à une licence en volume — donc un coût de licence Microsoft à maintenir précisément pour éviter celui que ce projet cherche à sortir de l'équation. Sa fin de support est en outre déjà amorcée pour les comptes sous abonnement Microsoft 365, avec une fin de vie complète documentée par Microsoft au plus tard en octobre 2029 selon le canal de licence.

**Note complémentaire — eM Client, une alternative tierce à Outlook**
eM Client est un client mail lourd concurrent d'Outlook, édité par une société tchèque (eM Client s.r.o., Prague), avec mail (IMAP/POP/EWS), calendrier et contacts (CalDAV/CardDAV), tâches, notes et tchat intégré. Deux points à distinguer de l'analyse Outlook pour Mac ci-dessus :
- **Connexion réseau** : contrairement au nouveau Outlook, eM Client se connecte directement au serveur EWS/CalDAV configuré, sans mécanisme de relais cloud propriétaire — les retours d'utilisateurs le décrivent explicitement comme indépendant d'un écosystème cloud tiers. Aucune indication contraire trouvée. Sur ce point précis, il serait donc compatible avec l'objectif de souveraineté du projet, à la différence du nouveau Outlook.
- **Licence** : logiciel **propriétaire, non open source** — gratuit jusqu'à 2 comptes en usage non commercial, payant (~40 $/an) au-delà pour un usage professionnel/illimité. C'est une entreprise européenne (cohérent avec la logique de souveraineté déjà tenue pour Visio/PeerTube/Tchap), mais le code n'est ni ouvert ni auditable, contrairement à Thunderbird et au reste de la stack retenue dans ce document.

**eM Client n'est pas retenu comme brique du projet** : il n'apporte rien que Thunderbird n'offre déjà (mêmes protocoles de connexion à Grommunio) tout en introduisant une dépendance à un éditeur propriétaire et un coût de licence par utilisateur au-delà de deux comptes — contraire au principe du tout-open-source recherché par ce projet. Il reste mentionné ici comme option de repli individuelle si un consultant préfère son ergonomie à celle de Thunderbird, sans que le cabinet en fasse un standard déployé.

**Critères de choix**
- Connexion directe au serveur Grommunio sans relais tiers, pour rester cohérent avec l'objectif de souveraineté posé dès l'introduction de ce document.
- Gratuité réelle, sans dépendance résiduelle à une licence Microsoft d'aucune sorte (ni abonnement, ni achat unique).
- Compatibilité EWS confirmée côté Grommunio pour l'ensemble des clients retenus.

**Conclusion — brique retenue**
**Thunderbird** comme client lourd multiplateforme de référence (Windows/Mac/Linux), complété sur Mac par la suite native **Apple Mail/Calendrier/Contacts** pour les consultants qui préfèrent l'intégration système plutôt qu'un client tiers — les deux se connectant directement à Grommunio en EWS, sans intermédiaire cloud tiers. **Outlook pour Mac est explicitement écarté**, non pour un motif de coût de licence (sa version actuelle est gratuite), mais parce que son architecture réseau route les données de messagerie via l'infrastructure cloud de Microsoft même pour un compte pointant vers un serveur auto-hébergé — ce qui contredit directement l'objectif de souveraineté des données motivant l'ensemble de ce projet.

**Point de configuration — désactiver le chat Matrix intégré à Thunderbird**
Thunderbird embarque nativement un compte de type « Chat » compatible Matrix, distinct de sa fonction mail. Ce n'est pas une alternative crédible à Element (1.2) pour l'usage tchat d'entreprise du cabinet : **confirmé** par la documentation officielle Mozilla, l'implémentation Matrix de Thunderbird ne supporte ni le chiffrement de bout en bout (dans un salon chiffré, les messages reçus s'affichent sous forme de JSON chiffré brut, illisible, sans déchiffrement possible côté client), ni le rechargement de l'historique des salons (seuls les messages non lus à la connexion et les nouveaux messages apparaissent), ni les médias (texte uniquement). La prise en charge des commandes slash spécifiques à l'écosystème Matrix/Element n'est pas documentée non plus, ce qui est cohérent avec une implémentation réutilisant l'ancien moteur de chat générique de Thunderbird plutôt qu'une UI pensée pour Matrix.

Au-delà du confort d'usage, ce point touche à la sécurité perçue : la stack retient Matrix avec E2EE activé par défaut sur les rooms privées (1.2) — un consultant qui activerait par mégarde le chat Matrix dans Thunderbird se retrouverait face à des salons chiffrés illisibles, sans indication claire de la raison, avec un risque de confusion sur la confidentialité réelle de l'échange. **Recommandation : désactiver ce module dans la configuration/déploiement standard de Thunderbird** (absence de compte Chat préconfiguré, et blocage de sa création via `policies.json`/verrouillage de préférence si un déploiement centralisé est en place), afin de canaliser tout l'usage tchat vers Element — cohérent avec le rôle de Thunderbird retenu ici, strictement mail/agenda/contacts.

---

## Chapitre 2 — Intégration entre les briques

Le choix d'une stack « best of breed » (chaque brique optimale sur son périmètre) a pour contrepartie l'absence d'intégration native entre briques qui n'ont pas été conçues ensemble — contrairement à une suite intégrée comme Office 365 (Microsoft Graph) ou à LaSuite numérique de la DINUM, dont les briques (Tchap, Visio, Docs) sont développées par la même équipe et intégrées nativement entre elles.

Ce chapitre traite, sujet par sujet, les besoins d'intégration transverses identifiés.

### 2.1 Centre de notifications unifié

**Besoin fonctionnel**
Un point d'entrée unique agrégeant les notifications de tous les services (nouveau message Matrix, mail Grommunio, fichier partagé Seafile, tâche assignée Vikunja), comme le fait Teams pour l'écosystème Microsoft.

**Alternatives possibles**
- **ntfy** : serveur de notification push simple, pub/sub par topics — léger mais sans UI riche de centre de notif.
- **Novu** : infrastructure de notification avec centre de notif in-app prêt à l'emploi, multi-canal, gestion des préférences par canal.
- **Nextcloud (Dashboard + Notifications API)** : framework pluggable existant et documenté (API OCS), déjà utilisé par des dizaines d'intégrations tierces — mais nécessiterait de porter une stack PHP jugée datée pour ne récupérer qu'un pattern d'agrégation.
- **Micro-service custom** (Go/Node) réutilisant uniquement le pattern d'agrégation (fan-out parallèle + timeouts par source), sans porter l'écosystème Nextcloud.

**Critères de choix**
- Ne pas introduire une stack lourde (PHP/monolithe) pour ne récupérer qu'un pattern d'agrégation reproductible en quelques centaines de lignes.
- Cohérence avec le reste de la stack, déjà orientée vers des outils modernes et légers (Vikunja en Go, alternatives Matrix en Rust).
- Le point dur reste, quel que soit l'outil choisi, l'ingestion : aucun gestionnaire de notification ne « parle » nativement Matrix/Grommunio/Seafile/Vikunja — un connecteur par service est nécessaire pour traduire chaque événement.

**Conclusion — brique retenue**
**Novu** pour l'UI de centre de notif et l'infrastructure multi-canal, alimenté par des connecteurs custom par service (webhook Matrix Application Service, webhook/IMAP Grommunio, webhook Seafile, webhook Vikunja). Le développement des connecteurs constitue le vrai chantier, indépendamment de l'outil retenu.

### 2.2 Recherche unifiée

**Besoin fonctionnel**
Une seule zone de recherche permettant de retrouver un message, un mail, un fichier ou une tâche, quel que soit le service source.

**Alternatives possibles**
- **Index central pré-calculé** (type Elasticsearch/Meilisearch) : rapide à l'usage, mais nécessite de répliquer et maintenir en continu les ACL de chaque service source dans l'index — sous peine de fuite de permissions (un utilisateur voit apparaître un résultat auquel il n'a pas accès dans le service source).
- **Fan-out en temps réel** : chaque recherche interroge en parallèle les APIs natives de chaque service (Matrix `/search`, Seafile, Vikunja `search=`, Grommunio via IMAP SEARCH), avec le token Keycloak de l'utilisateur relayé à chaque appel — les permissions sont respectées nativement puisque c'est le service source qui filtre.

**Critères de choix**
- Sécurité par construction : le fan-out temps réel évite le risque de synchronisation d'ACL défaillante propre à l'index central.
- Latence perçue : en parallélisant les requêtes, le temps de réponse total est borné par le service le plus lent (et non par la somme des temps de chaque service), à condition de fixer un timeout par service pour éviter qu'un service en carafe bloque toute la recherche.
- Amélioration possible de l'UX : affichage progressif des résultats au fil de l'eau (Server-Sent Events/WebSocket) à mesure que chaque service répond, plutôt que d'attendre la réponse de tous les services.

**Conclusion — brique retenue**
**Fan-out en temps réel**, réutilisant la même brique d'ingestion/connecteurs que le centre de notifications (mutualisation du développement). L'option d'un index central pré-calculé n'est réévaluée que si la latence du fan-out devient un vrai problème d'usage à l'échelle, avec la synchronisation des ACL alors traitée comme un chantier de sécurité dédié à part entière.

### 2.3 Portail applicatif et menu de navigation entre applications

**Besoin fonctionnel**
Un bandeau/menu commun superposé aux applications (accès rapide aux différents services, cloche de notification, zone de recherche), sans avoir à reconstruire chaque application.

**Alternatives possibles**
- **Portail avec iframes** (type Dashy/Organizr/Homarr) embarquant chaque application dans un cadre commun.
- **Injection HTML côté reverse proxy** (Nginx `sub_filter`, ou plugin Caddy tel que `caddy2-html-injection-plugin`) : le proxy réécrit le HTML de chaque application à la volée pour y insérer le bandeau, sans toucher au code des applications.
- **Page d'accueil statique de liens** (sans dashboard applicatif complet), pour le seul besoin de liens/deep links vers les applications natives.

**Critères de choix**
- Le portail iframe pose de vrais problèmes de sécurité pour embarquer des applications entières : nécessité de desserrer `X-Frame-Options`/`frame-ancestors` sur chaque service (élargissement de la surface d'attaque clickjacking), restrictions croissantes des navigateurs sur les cookies tiers en contexte iframe pouvant casser le SSO silencieusement, comportement parfois dégradé des API navigateur (notifications, WebRTC) en contexte iframe.
- L'injection HTML est fragile aux montées de version de chaque application (le point d'ancrage DOM peut bouger) et nécessite de gérer les en-têtes CSP, mais reste plus proportionnée pour un bandeau léger (menu + cloche + recherche) qui ne cherche pas à embarquer le contenu complet de chaque application.
- Pour le cas précis d'un widget vidéo unique (Visio DINUM) à l'intérieur d'une room Matrix, l'iframe est en revanche justifiée et cadrée : un seul widget ciblé, pas une application entière, avec configuration explicite et documentée des permissions d'iframe côté application source (cas distinct du portail global).

**Conclusion — brique retenue**
**Injection HTML via reverse proxy (Caddy + plugin d'injection)** pour le bandeau léger transverse (menu, cloche de notification, zone de recherche), chaque application restant par ailleurs en navigation plein écran native — pas de portail iframe embarquant les applications complètes. L'iframe reste utilisée ponctuellement et de façon ciblée pour le widget de visioconférence dans les rooms Matrix (cf. 2.4).

### 2.4 Continuité du fil de discussion textuel avant/pendant/après une visioconférence

**Besoin fonctionnel**
Disposer d'un même fil de discussion textuel accessible avant la réunion (planification), pendant (échanges en parallèle de la vidéo) et après (historique consultable) — comme le permet Teams en associant chat et réunion au même canal.

**Alternatives possibles**
- Compter sur le tchat natif intégré à Visio DINUM.
- Widget Matrix embarquant Visio DINUM dans une room Element (mécanisme générique déjà utilisé historiquement pour intégrer Jitsi dans Element).
- **Element Call**, nativement intégré aux rooms Matrix via le protocole MatrixRTC.

**Critères de choix**
- Le tchat natif de Visio (LaSuite Meet) est cloisonné à la session de réunion : il ne persiste pas avant/après la réunion comme le ferait un canal Teams, et disparaît une fois la réunion terminée. **Écarté** comme solution de continuité.
- Le mécanisme de widget Matrix est générique et éprouvé (déjà utilisé pour Jitsi) : la room Element reste le seul fil persistant, et le widget vidéo s'affiche en complément pendant la durée de l'appel. Nécessite de vérifier que l'application vidéo embarquée autorise l'iframe (`frame-ancestors`) — non bloquant ici puisque Visio est auto-hébergé, donc ce réglage est sous contrôle direct.
- Element Call est nativement un widget de room Matrix, sans développement d'intégration nécessaire, mais ne couvre pas le besoin RTC/PSTN identifié comme un impératif (accessibilité, participants sans accès IP).
- **Un précédent existe déjà** : Tchap (fork d'Element développé par l'État, co-financé avec Linagora) propose une commande `/visio` pour lancer une réunion Visio directement depuis une room, ce qui constitue une référence d'intégration Matrix ↔ Visio DINUM déjà construite et publiée en open source (licence MIT/AGPL, dépôt GitHub `suitenumerique`).

**Conclusion — brique retenue**
Reprendre/adapter l'intégration `/visio` déjà développée par Tchap plutôt que de construire un connecteur Matrix ↔ Visio DINUM à partir de zéro. Le backend vidéo ciblé par ce connecteur est désormais confirmé (LiveKit, cf. 1.3), ce qui lève l'incertitude initiale. Le widget doit désactiver ou masquer le tchat interne de Visio pour éviter la confusion entre deux fils textuels simultanés (un dans le widget, un dans la room Matrix).

### 2.5 Facilitation de l'installation des applications natives (Mac, iOS, Android)

**Besoin fonctionnel**
Réduire la friction d'installation et de configuration des multiples applications natives (Element, Seafile, Vikunja, client mail Grommunio) sur les postes Mac et mobiles des consultants.

**Alternatives possibles**
- **MDM complet avec enrôlement zero-touch** (Apple Business Manager + Android Enterprise, piloté par une solution comme myMDM, Appaloosa ou Headwind MDM) : poussée automatique et pré-configurée des applications dès le déballage/la mise en service de l'appareil.
- **Profils de configuration Apple sans serveur MDM** (fichier `.mobileconfig` généré via Apple Configurator) : pré-configuration d'un compte ou d'un réglage, distribué par simple lien/QR code, sans infrastructure serveur.
- **Deep links applicatifs pré-configurés** (ex. lien `element://https://matrix.example.com` pour Element) associés à des QR codes, combinés à une page d'onboarding statique.

**Critères de choix**
- Le MDM complet est disproportionné pour un cabinet de conseil dont les postes ne sont pas nécessairement tous sous contrôle total IT (BYOD partiel), et introduit une dépendance résiduelle à Apple Business Manager quel que soit l'éditeur MDM choisi (l'enrôlement zero-touch Apple reste obligatoirement contrôlé par Apple).
- Les profils `.mobileconfig` et les deep links couvrent l'essentiel de la friction d'installation initiale sans aucune infrastructure serveur à opérer ni abonnement.
- Le MDM garde un intérêt réel si un besoin de gestion de flotte apparaît (effacement à distance, inventaire, conformité) — mais ce n'est pas le besoin exprimé initialement (faciliter l'installation), qui ne justifie pas cet investissement.

**Conclusion — brique retenue**
Approche légère, sans serveur MDM :
1. Page d'onboarding statique (HTML, derrière Caddy) listant chaque application avec lien App Store/Play Store et QR code de deep link pré-configuré.
2. Fichier `.mobileconfig` optionnel pour préconfigurer le compte mail Grommunio (ActiveSync) sur Mac/iPhone.
3. Aucune infrastructure MDM tant qu'un besoin de gestion de flotte à distance n'est pas identifié.

### 2.6 Absence de tchat dédié dans OnlyOffice

**Besoin fonctionnel**
Éviter la duplication d'un tchat propre à OnlyOffice en parallèle du tchat d'entreprise Matrix, pour ne pas fragmenter les échanges liés à un document entre deux outils différents.

**Alternatives possibles**
- Désactiver le module de tchat interne d'OnlyOffice Document Server et rediriger les échanges liés à un document vers une room Matrix dédiée (une room par document ou par espace de travail Seafile).
- Générer automatiquement un lien vers la room Matrix associée depuis la barre d'outils OnlyOffice.

**Critères de choix**
- **Confirmé** : OnlyOffice expose un paramètre de configuration natif et documenté pour désactiver précisément le tchat, indépendamment des commentaires — `document.permissions.chat: false` dans le fichier de configuration de l'éditeur, distinct de `document.permissions.comment` (qui peut rester activé). Ce n'est donc pas une intégration à développer, mais un simple paramètre à positionner à la configuration de chaque document ouvert.
- Reste à construire : la génération automatique d'un lien vers la room Matrix correspondante dans la barre d'outils OnlyOffice (petit connecteur d'affichage, pas une modification du cœur d'OnlyOffice).

**Conclusion — brique retenue**
**Désactivation du tchat OnlyOffice via `document.permissions.chat: false`**, appliquée par défaut à l'ouverture de tout document depuis Seafile, en complément d'un lien vers la room Matrix associée au document ou à l'espace de travail (connecteur d'affichage à développer, cf. 2.11).

### 2.7 Mentions `@utilisateur` dans les commentaires des documents

**Besoin fonctionnel**
Pouvoir mentionner un collègue dans un commentaire de document (OnlyOffice) et déclencher une notification vers cette personne, comme le permet Office 365 dans Word/Excel en @-mentionnant un collègue par mail ou notification Teams.

**Alternatives possibles**
- Brancher l'événement natif de mention d'OnlyOffice sur le centre de notifications unifié (Novu, cf. 2.1).

**Critères de choix**
- **Confirmé** : OnlyOffice expose une API de mentions dédiée et documentée. L'événement `onRequestUsers` fournit la liste des utilisateurs proposés lors de la frappe du signe `+`/`@` dans un commentaire ; l'événement `onRequestSendNotify` se déclenche lorsqu'un commentaire mentionnant quelqu'un est soumis, et transmet au backend intégrateur le message, la liste des emails mentionnés et un lien d'action pointant directement vers la position du commentaire dans le document. C'est au backend applicatif (pas à OnlyOffice) qu'il revient d'envoyer effectivement la notification — exactement le point d'entrée nécessaire pour alimenter le centre de notifications unifié.

**Conclusion — brique retenue**
**Implémentation du handler `onRequestSendNotify`** dans le backend d'intégration Seafile↔OnlyOffice, pour transmettre chaque mention au centre de notifications unifié (Novu, 2.1) avec le lien d'action fourni nativement par l'API — ce connecteur rejoint la liste de ceux à développer en 2.1, sans traitement séparé.

### 2.8 Présence unifiée entre Element, Grommunio et Visio

**Besoin fonctionnel**
Afficher un statut de présence cohérent (en ligne/absent/en réunion) entre Element, Grommunio et Visio, plutôt que trois statuts indépendants et potentiellement contradictoires — par exemple un consultant affiché « disponible » dans Element alors qu'il est en réunion sur Visio.

**Alternatives possibles**
- Ne rien faire : conserver trois indicateurs de présence indépendants, chacun natif à son outil.
- Construire un agrégateur de présence qui consulte chaque source et republie un statut consolidé dans une surface commune (le bandeau du portail applicatif, cf. 2.3), plutôt que de tenter d'injecter ce statut dans l'indicateur natif de chaque application.

**Critères de choix**
- Chaque brique a sa propre notion de présence, avec des protocoles disjoints : **Matrix** expose une API de présence native (`m.presence`, états online/unavailable/offline), consultable en direct côté client comme côté serveur. **Grommunio/EWS** ne publie pas de présence à proprement parler, mais permet de dériver un état « en réunion » depuis le calendrier via l'opération `GetUserAvailability` — à l'image de ce que faisait historiquement l'intégration Cisco Unified Presence en s'abonnant au calendrier Exchange par EWS pour en dériver un statut de disponibilité. **Visio** (LiveKit) n'a de notion de présence que pendant un appel actif (liste des participants connectés à une room), sans état « disponible/absent » en dehors d'un appel.
- Injecter un statut agrégé directement dans l'indicateur natif de chaque application (faire apparaître « en réunion » dans Element lui-même, par exemple) nécessiterait de modifier l'affichage natif de chaque client — hors de portée sans forker les applications elles-mêmes.
- Afficher le statut consolidé dans une surface neutre déjà prévue à cet effet (le bandeau du portail applicatif, 2.3) est nettement plus réaliste : la donnée est agrégée côté connecteur et affichée à un seul endroit, sans toucher au code des applications sources.

**Conclusion — brique retenue**
**Agrégateur de présence développé comme connecteur supplémentaire**, sur le même schéma que le centre de notifications (2.1) et la recherche unifiée (2.2) : présence Matrix consultée en direct, disponibilité calendaire Grommunio dérivée par `GetUserAvailability` (EWS), état d'appel Visio consulté via l'API/les webhooks LiveKit — statut consolidé affiché dans le bandeau du portail applicatif (2.3), plutôt qu'injecté dans les indicateurs natifs de chaque application, qui restent chacun sur sa propre logique. Connecteur à développer, ajouté à la liste des chantiers d'intégration (2.11).

---

### 2.9 Bouton « créer une visio » depuis une invitation de calendrier Grommunio

**Besoin fonctionnel**
Un bouton dans l'éditeur de réunion Grommunio pour insérer automatiquement un lien de réunion Visio, sur le modèle de l'intégration Teams/Outlook, plutôt que de créer manuellement la réunion sur Visio puis de recopier le lien dans l'invitation.

**Alternatives possibles**
- **Lien personnel réutilisable** : Visio documente nativement le fait que les liens de réunion générés peuvent être réutilisés à l'infini — un même lien peut être collé une fois dans une signature ou un modèle d'invitation Grommunio, sans bouton ni développement.
- **Bouton d'intégration complet** : un connecteur qui appelle une API de création de room côté Visio/La Suite Meet pour générer une réunion à la volée et insérer le lien directement dans le corps de l'invitation au moment de sa création.

**Critères de choix**
- Le lien personnel réutilisable couvre une bonne partie du besoin sans aucun développement, mais reste manuel : chaque organisateur doit connaître et coller son propre lien, sans automatisation ni bouton dans l'éditeur.
- Le bouton d'intégration complet suppose un point d'extension côté grommunio-web (non documenté nativement comme extensible pour ce cas précis) ou un module complémentaire côté client (Outlook Add-in, plus lourd, cf. 1.9). Côté Visio/Meet, l'architecture du projet (Django REST Framework, dépôt open source `suitenumerique/meet`) laisse penser qu'une API de création de room existe en interne, mais elle n'est pas documentée publiquement à ce stade — le produit étant encore en développement actif. **Ce point est à confirmer directement auprès des équipes DINUM avant de chiffrer un développement.**

**Et sur Thunderbird et les agendas mobiles ?**
- **Le lien réutilisable fonctionne à l'identique, sans distinction de client** : comme il s'agit d'un simple texte collé dans le champ emplacement ou la description d'un événement, son insertion ne dépend d'aucun protocole particulier (EWS, CalDAV ou EAS) — elle fonctionne aussi bien dans Thunderbird, Apple Calendrier, ou l'agenda natif d'un mobile en EAS, sans aucun développement ni distinction entre clients. C'est précisément l'intérêt de cette solution de repli : elle est universelle par construction.
- **Le bouton d'intégration complet est en revanche à examiner client par client** :
  - **Thunderbird** : techniquement réalisable, et avec un **précédent solide et actif plutôt qu'une simple hypothèse**. Deux add-ons existants illustrent deux niveaux de maturité très différents sur ce même pattern (visio + calendrier Thunderbird) :
    - *Jitsi Meet Event Generator* : mise en garde plutôt que modèle à suivre — le bouton n'est disponible que dans la fenêtre de composition d'un mail, pas dans l'éditeur d'événement (demande explicite d'utilisateurs restée sans suite dans les avis), et le fichier `.ics` généré contient un UID mal formé qui casse la compatibilité avec les calendriers CalDAV — exactement le protocole utilisé ici avec Grommunio.
    - **`NC Connector for Thunderbird`** : un précédent nettement plus convaincant. Cet add-on, activement maintenu (dépôt GitHub public, releases continues jusqu'en 2026), **crée et met à jour un salon Nextcloud Talk directement depuis l'éditeur d'événement du calendrier Thunderbird** — véritable intégration calendrier, pas seulement mail — et synchronise les modifications ou la suppression du salon lorsque l'événement change. Il dispose même d'un pendant Outlook (« NC Connector ecosystem »). C'est un point de comparaison plus pertinent que les précédents Jitsi/Google Meet/Zoom, car **Nextcloud Talk est, comme Visio, un outil de visioconférence auto-hébergé et open source** — architecturalement proche de ce que ce projet chercherait à construire, plutôt qu'une intégration à un service tiers commercial.
    - Point de vigilance qui demeure : NC Connector s'appuie, comme envisagé plus haut, sur l'API expérimentale de calendrier de Thunderbird (« Calendar experiment », non finalisée dans le cœur du logiciel) — mais son développement actif et continu sur plusieurs années démontre que ce risque est gérable dans la durée avec une maintenance dédiée, pas rédhibitoire.
  - **Mobile (agendas natifs iOS/Android en EAS, ou client mail mobile)** : **aucune voie réaliste identifiée, et la raison est plus fondamentale qu'un simple manque de point d'extension**. Thunderbird pour Android n'est pas une déclinaison mobile de la même application desktop : c'est un héritage du code de K-9 Mail (Kotlin, natif Android), en cours de refonte, qui ne supporte pas du tout l'écosystème WebExtension desktop. Concrètement, aucun des add-ons cités ci-dessus (NC Connector, Jitsi, Google Meet, Zoom) n'existe ni ne peut exister sur Thunderbird mobile — ce n'est pas une limite temporaire à surveiller, mais une différence d'architecture logicielle. Le lien réutilisable reste donc la seule option sur mobile, de façon définitive.

**Conclusion — brique retenue**
**Solution à deux vitesses, avec un périmètre clarifié par client** : dans l'immédiat, généraliser l'usage du **lien personnel réutilisable Visio** — solution universelle, valable sans distinction sur grommunio-web, Outlook, Thunderbird, Apple Calendrier et les agendas mobiles, sans aucun développement. Le **bouton d'intégration complet** reste un chantier à instruire plus finement, réaliste sur **grommunio-web** et **Outlook** (Add-in) à court terme, et sur **Thunderbird** — où le précédent `NC Connector for Thunderbird` (intégration Nextcloud Talk/calendrier, activement maintenue) démontre la faisabilité concrète d'une intégration équivalente pour Visio, moyennant l'usage assumé et maintenu de l'API expérimentale de calendrier. **Structurellement hors de portée sur mobile**, Thunderbird pour Android ne partageant pas l'architecture WebExtension du desktop. L'ensemble reste conditionné à la disponibilité et à la documentation d'une API de création de room côté Visio — à vérifier auprès de la DINUM avant chiffrage. Ajouté à la liste des chantiers d'intégration (2.11).

---

### 2.10 Lien direct vers un document Seafile/OnlyOffice depuis une tâche Vikunja

**Besoin fonctionnel**
Associer un document Seafile/OnlyOffice à une tâche Vikunja sans dupliquer le fichier en pièce jointe, pour éviter la divergence entre la version du document dans Seafile et celle attachée à la tâche.

**Alternatives possibles**
- **Lien collé dans la description de la tâche** : coller manuellement l'URL interne (stable) du document Seafile dans la description Vikunja, qui supporte le texte enrichi/Markdown et rend donc le lien cliquable — zéro développement.
- **Connecteur dédié** : utiliser les API REST de Vikunja (endpoints tâches, webhooks signés HMAC) et de Seafile pour proposer une action « lier un document Seafile » directement dans l'UI de la tâche, avec par exemple un aperçu ou un type de pièce jointe dédié plutôt qu'un champ texte libre.

**Critères de choix**
- Vikunja expose une API REST complète (tâches, pièces jointes, webhooks) largement utilisée par la communauté pour ce type d'automatisation — un connecteur reste réalisable si le besoin dépasse le simple lien.
- Un simple lien collé dans la description couvre déjà l'objectif premier énoncé (éviter la duplication de fichiers en pièce jointe) sans aucun développement : le fichier reste dans Seafile, la tâche ne référence qu'un lien vers celui-ci.
- Le développement d'un connecteur dédié n'apporte une vraie valeur ajoutée que si le besoin va au-delà du simple lien (aperçu du document dans la tâche, mise à jour automatique d'un statut si le document est modifié) — besoin non exprimé à ce stade.
- Cohérence avec la restriction déjà retenue en 2.8 (chapitre 1.4) des liens de partage Seafile non authentifiés : le lien collé pointe vers le document authentifié dans Seafile, pas vers un lien de partage public — pas de contradiction avec cette politique.

**Conclusion — brique retenue**
**Retenu sans développement** : lien Seafile collé dans la description Markdown de la tâche Vikunja. Un **connecteur dédié** (API Vikunja + Seafile) n'est à envisager que si un besoin d'aperçu ou de synchronisation plus poussé émerge à l'usage — non retenu comme chantier prioritaire à ce stade, mais gardé en tête si le besoin évolue.

---

### 2.11 Autres sujets d'intégration à instruire

Sujets identifiés mais non encore creusés en détail, à traiter selon le même canevas (besoin / alternatives / critères / conclusion) lors d'une prochaine itération :

**Dépôt automatique de gros fichiers vers Gokapi depuis le mail**
Besoin : lorsqu'un consultant tente de joindre un fichier volumineux à un mail (webmail Grommunio ou client lourd), proposer de le déposer automatiquement sur Gokapi (1.8) et d'insérer le lien généré à la place de la pièce jointe, après confirmation explicite de l'utilisateur — plutôt que de laisser échouer l'envoi ou de contourner la limite par d'autres moyens non maîtrisés.
- **Grommunio-web** : ce point reste à instruire — dépend de la disponibilité d'un point d'extension (plugin) dans l'architecture de grommunio-web pour intercepter un dépôt de pièce jointe au-delà d'un seuil de taille et proposer le dépôt Gokapi avant envoi. L'API REST de Gokapi facilite cette intégration côté serveur (authentification par clé API à associer au compte OIDC de l'expéditeur).
- **Clients lourds** : Thunderbird dispose nativement d'un mécanisme dédié à ce besoin précis, le **Filelink** — au-delà d'un seuil de taille configurable (5 Mo par défaut), Thunderbird propose automatiquement d'envoyer la pièce jointe via un fournisseur Filelink plutôt qu'en pièce jointe classique, ce mécanisme étant ouvert à des extensions tierces (des fournisseurs Filelink existent déjà pour Dropbox, Box, WebDAV, ou des instances de Send). Un module Filelink dédié à Gokapi est donc à développer selon un patron déjà éprouvé par la communauté Thunderbird, pas une intégration à inventer — l'API REST et le CLI (`gokapi-cli`) de Gokapi fournissent les points d'entrée nécessaires. Pour Outlook, en l'absence d'un mécanisme équivalent nativement extensible, l'intégration demanderait un module complémentaire (Office Add-in) — développement plus lourd, à chiffrer séparément si Outlook doit être supporté au même niveau que Thunderbird.

**Interdiction des liens de partage Seafile non authentifiés**
Besoin : empêcher la génération de liens de partage Seafile accessibles sans authentification, pour que tout partage externe non authentifié passe exclusivement par Gokapi (1.8) — cohérent et complémentaire du point précédent. **Confirmé** : Seafile expose un paramètre serveur documenté, `SHARE_LINK_LOGIN_REQUIRED = True`, qui force la connexion pour consulter tout lien de partage de fichier/dossier. En complément, la permission `can_generate_share_link` peut être désactivée par rôle (`seahub_settings.py`) pour empêcher purement et simplement la génération de liens de partage par les utilisateurs concernés, plutôt que de seulement restreindre leur consultation. Les deux réglages sont cumulables selon le niveau de rigueur souhaité (empêcher la génération vs. exiger une authentification à la consultation).

### 2.12 Plateforme vidéo d'entreprise (stockage et mise à disposition des enregistrements et transcriptions)

**Besoin fonctionnel**
Disposer d'un équivalent à Microsoft Stream/Videos : un espace centralisé où les enregistrements de réunion et leurs transcriptions sont conservés durablement, indexés, et mis à disposition des consultants (recherche par titre/date/participants, lecture en streaming, gestion des droits de visionnage), plutôt que de laisser chaque enregistrement disparaître ou traîner en fichier isolé.

Ce besoin est directement lié au constat fait en 1.3 : l'instance publique de Visio (DINUM) ne conserve les enregistrements que 7 jours avant suppression automatique. **En auto-hébergement, cette limite ne s'impose pas au cabinet** (voir critères de choix ci-dessous) — mais le besoin de conservation durable et de mise à disposition indexée reste entier, une fois la contrainte de délai levée.

**Alternatives possibles**
- **Stocker les enregistrements comme de simples fichiers dans Seafile**, dans un dossier dédié par réunion/projet.
- **PeerTube** : plateforme de publication et de streaming vidéo open source, fédérée (protocole ActivityPub), déjà utilisée par la DINUM elle-même pour la publication de vidéos dans l'écosystème LaSuite/DINUM (tube.numerique.gouv.fr).
- Solutions propriétaires de type Panopto/Kaltura — non retenues à ce stade, contraires à la logique de souveraineté du projet.

**Critères de choix**
- Un simple stockage Seafile répond au besoin de conservation, mais pas au besoin de plateforme vidéo à proprement parler : pas de lecteur de streaming adapté à la vidéo (juste un téléchargement de fichier), pas d'indexation par métadonnées de réunion, pas de recherche dans le contenu.
- PeerTube apporte précisément ce qui manque à un simple stockage de fichiers : un lecteur vidéo en streaming, une organisation par chaînes/playlists (par exemple une chaîne par équipe ou par type de réunion), et une gestion de la visibilité par vidéo (privée, interne, non répertoriée).
- Cohérence avec l'écosystème DINUM déjà mobilisé pour Visio/Tchap : PeerTube n'est pas un choix isolé, c'est l'outil que l'État français utilise déjà pour le même type de besoin dans le même écosystème logiciel.
- Le format fédéré (ActivityPub) de PeerTube n'est pas un besoin exprimé ici mais n'est pas non plus un handicap : la fédération est optionnelle et peut rester désactivée pour un usage interne strict.

**La limite de 7 jours n'est pas une contrainte du logiciel Visio, mais une politique d'exploitation propre à l'instance de la DINUM.** Techniquement, l'enregistrement est produit par **LiveKit Egress** (le composant qui capture le flux audio/vidéo d'une room), qui écrit le fichier vers un **stockage compatible S3** (bucket) — c'est la sortie officiellement documentée et éprouvée par LiveKit, au même titre que Google Cloud Storage ou Azure. La suppression au bout de 7 jours observée sur l'instance publique est très probablement une règle de cycle de vie posée sur le bucket de la DINUM (ou un nettoyage applicatif équivalent côté DINUM), pas une limite figée dans le code de Visio — à confirmer concrètement à l'installation (la documentation du projet indique elle-même que les fonctionnalités avancées comme l'enregistrement manquent encore de documentation détaillée), mais le schéma S3 + règle de cycle de vie côté infrastructure est le mécanisme quasi systématique pour ce type de purge.

**Le bucket S3 n'est pas une dépendance cloud, mais un composant auto-hébergé de plus.** LiveKit Egress supporte un mode d'écriture directe sur disque local sans configuration de stockage, mais ce disque est celui du pod Egress lui-même, éphémère et non partagé avec les autres services par défaut. Faire lire ce fichier par PeerTube nécessiterait alors un volume réseau partagé entre pods Kubernetes (NFS ou équivalent), plus fragile à opérer à l'échelle que le chemin officiellement supporté. **MinIO auto-hébergé** (compatible API S3, tournant dans le même cluster Kubernetes que le reste de la stack) est donc retenu comme destination d'Egress plutôt qu'un partage de filesystem entre pods — ce n'est pas une brique cloud tierce, juste un logiciel de stockage objet supplémentaire à héberger, au même titre que Seafile ou Keycloak. La rétention sur ce bucket auto-hébergé est configurée par le cabinet lui-même (règle de cycle de vie généreuse, ou son absence pure et simple) plutôt que subie.

- Reste à construire : le webhook receveur qui s'abonne aux notifications `ObjectCreated` du bucket MinIO pour déclencher le dépôt vers PeerTube (upload via son API, association des métadonnées de réunion — titre, date, participants — à la vidéo). Sans contrainte de délai (rétention désormais maîtrisée), ce dépôt peut se faire en tâche périodique (batch quotidien) plutôt qu'en réaction temps réel critique — plus simple à opérer, sans risque même en cas de panne temporaire du connecteur.

**Conclusion — brique retenue**
**PeerTube**, comme plateforme vidéo d'entreprise pour la conservation et la mise à disposition durable des enregistrements de réunion et de leurs transcriptions, alimentée en amont par **MinIO auto-hébergé** (destination S3-compatible de LiveKit Egress, dont la règle de rétention est fixée par le cabinet lui-même, sans dépendre d'une limite imposée par un tiers) et un connecteur de dépôt vers PeerTube pouvant fonctionner en tâche périodique plutôt qu'en urgence temps réel. Seafile n'est pas retenu pour cet usage précis (absence de lecteur de streaming et d'indexation), mais reste pertinent pour le stockage des documents et fichiers classiques (1.4).

---

### 2.13 Annuaire d'entreprise (GAL) accessible depuis tous les clients mail retenus

**Besoin fonctionnel**
Disposer d'un annuaire d'entreprise (Global Address List) consultable et interrogeable depuis n'importe quel client mail retenu dans ce document — pas seulement Outlook — pour l'autocomplétion des destinataires à la frappe et la recherche de collègues par nom, comme le permet nativement le GAL d'Exchange/Office 365.

**Constat**
Grommunio gère nativement le GAL (cf. 1.1) : annuaire alimenté automatiquement depuis les utilisateurs/domaines configurés côté serveur, avec gestion fine par admin (case « Hide from GAL » par utilisateur pour exclure boîtes de service et ressources techniques), résolution des listes de distribution avec groupes imbriqués, support des domaines internationalisés (IDN). Ce socle n'est cependant pas exposé de la même façon selon le protocole client :
- **Clients MAPI/EWS/EAS** (Outlook, cf. 1.9) : accès natif et complet au GAL, sans configuration supplémentaire — c'est inhérent à la compatibilité protocolaire de Grommunio avec Exchange.
- **Clients CardDAV** (Thunderbird, Apple Mail/Contacts, cf. 1.9) : historiquement, seul le carnet de contacts *personnel* de l'utilisateur était exposé par `grommunio-dav` en CardDAV — le GAL en était absent, laissant les utilisateurs de ces clients sans autocomplétion des collègues.

**Alternatives possibles**
- Se contenter de cette limite et orienter les utilisateurs Thunderbird/Apple Mail vers grommunio-web pour toute recherche dans l'annuaire — dégradation d'usage acceptée par défaut.
- **Activer la publication du GAL en CardDAV**, fonctionnalité native ajoutée par Grommunio dans sa release 2026.06.1 : `grommunio-dav` peut désormais publier le GAL comme carnet d'adresses CardDAV en lecture seule, via le paramètre `GAL_ENABLED` de sa configuration (désactivé par défaut), avec une durée de cache configurable (`GAL_CACHE_TTL`).

**Critères de choix**
- Fonctionnalité native et récente de la brique déjà retenue (pas de connecteur à développer, à la différence des autres sujets de ce chapitre) : simple paramètre serveur à activer.
- Cohérence avec le principe habituel d'un GAL : publication en lecture seule, les utilisateurs ne pouvant ni modifier ni enrichir l'annuaire d'entreprise depuis leur client.
- Le réglage `GAL_CACHE_TTL` doit être dimensionné pour équilibrer fraîcheur de l'annuaire (arrivées/départs de consultants) et charge sur le serveur DAV, sans qu'un TTL par défaut de l'ordre de l'heure pose de difficulté connue pour un usage bureautique classique.

**Conclusion — brique retenue**
**Activation de `GAL_ENABLED` dans la configuration de `grommunio-dav` dès le déploiement initial**, pour que Thunderbird et Apple Mail/Contacts (1.9) disposent nativement de l'annuaire d'entreprise en lecture seule, au même titre qu'Outlook via MAPI/EWS — sans connecteur à développer, contrairement aux autres chantiers d'intégration de ce chapitre. Point de vigilance : cette fonctionnalité étant très récente (juin 2026), sa maturité et son comportement en usage réel (fraîcheur du cache, performance sur un annuaire de plusieurs milliers d'entrées à l'échelle de croissance visée) restent à valider en recette avant généralisation.

**Point complémentaire — expansion des listes de diffusion (le « + » à côté d'une liste)**
Sur Outlook/Exchange, cliquer sur le petit « + » à droite d'une liste de diffusion dans le champ destinataire « explose » la liste et affiche individuellement tous ses membres. Ce comportement repose sur l'opération EWS `ExpandDL`.
- **Côté EWS (Outlook pour Mac, eM Client, cf. 1.9)** : **confirmé fonctionnel**. `ExpandDL` fait partie des opérations explicitement implémentées par Gromox, dans la même vague de renforcement EWS de juin 2026 qui a aussi apporté la recherche de salles et le workflow complet de réunion (cf. 2.14).
- **Côté CardDAV (Thunderbird)** : **non disponible, et ce n'est pas une limite de Grommunio.** L'équivalent CardDAV de `ExpandDL` est la représentation vCard 4.0 d'un groupe (`KIND:group` + propriétés `MEMBER`, RFC 6350). Or Thunderbird lui-même n'implémente pas ce mécanisme — c'est une demande de fonctionnalité ouverte et documentée auprès de Mozilla, toujours non résolue à ce jour. Le clic droit « Expand list » natif de Thunderbird (depuis la version 91) ne fonctionne que sur les listes de son carnet d'adresses local/personnel historique, pas sur un groupe reçu via CardDAV. Même si le GAL CardDAV de Grommunio publiait ses listes de diffusion au format `KIND:group`, Thunderbird ne saurait pas les interpréter comme des listes explosables.

Ce point renforce le constat déjà posé plus haut dans cette section : l'écart entre Outlook/EWS et Thunderbird/CardDAV sur le GAL ne se limite pas à la présence ou non de l'annuaire, mais s'étend aux fonctionnalités construites dessus (ici, l'expansion des listes) — à documenter dans la communication aux consultants au même titre que la réservation de salles (2.14).

---

### 2.14 Réservation de salles de réunion selon le client (Outlook vs. Thunderbird/mobile)

**Besoin fonctionnel**
Réserver une salle de réunion (ou une autre ressource partagée, type véhicule ou vidéoprojecteur) directement depuis l'éditeur de réunion du calendrier, avec recherche des salles disponibles et confirmation automatique selon leur disponibilité — comme le permet le « Room Finder » d'Outlook/Exchange.

**Constat**
Grommunio gère nativement la réservation de salles : l'administrateur crée la salle comme compte utilisateur partagé (« room resource »), et dans l'éditeur de réunion, l'utilisateur l'ajoute comme participant puis la marque « Set as Resource » — la salle accepte ou refuse alors automatiquement la réunion selon sa disponibilité. Ce mécanisme est nativement exposé dans **grommunio-web** et dans **Outlook** (MAPI/EWS) — la recherche de salles et le workflow complet de réunion (invitations, annulations, réponses) sur EWS ont d'ailleurs été spécifiquement renforcés par la release Grommunio de juin 2026 (cf. 2.13).

**Ce qui ne suit pas sur les clients CalDAV (Thunderbird) et mobile**
- **Thunderbird** : possibilité d'ajouter l'adresse mail de la salle comme participant à une réunion et de voir s'afficher son créneau libre/occupé — mécanisme générique de disponibilité CalDAV, identique pour n'importe quel participant. En revanche, **pas de sélecteur pour parcourir/rechercher les salles disponibles** (pas d'équivalent au Room Finder), et **le workflow d'acceptation/refus automatique n'est pas garanti fonctionner de façon identique** lorsqu'une invitation est envoyée depuis un client CalDAV plutôt que MAPI/EWS — la documentation Grommunio ne décrit ce mécanisme que dans le contexte de grommunio-web, sans mention explicite de son comportement pour une invitation initiée en CalDAV.
- **Mobile (EAS)** : la synchronisation mobile passe par `grommunio-sync`, documenté par Grommunio lui-même comme un sous-ensemble de fonctionnalités réduit par rapport à MAPI/EWS. Aucune confirmation trouvée que la recherche et la réservation de salle fonctionnent sur ce chemin — à vérifier à l'installation plutôt qu'à supposer acquis.

**Cette limite n'est pas un retard de version logicielle, mais une limite structurelle du standard CalDAV** : le protocole CalDAV/iTIP ne définit ni annuaire de salles consultable ni workflow d'auto-acceptation par une ressource — ce sont des extensions propriétaires construites par Microsoft au-dessus de MAPI/EWS. Aucun client CalDAV générique n'a de raison de les avoir implémentées puisqu'elles ne font pas partie du protocole qu'il parle ; le même constat s'observe sur d'autres serveurs groupware CalDAV (SOGo, Nextcloud) indépendamment de Grommunio. Une version plus récente de Thunderbird ne changera donc rien à ce point tant que le protocole CalDAV lui-même n'évolue pas.

**Alternative — brancher Thunderbird sur EAS plutôt que CalDAV, via l'add-on `TbSync` + `EAS-4-TbSync`**
Cet add-on tiers ajoute à Thunderbird le protocole EAS complet (jusqu'à la version 16.1), en alternative au CalDAV natif. Sa série de releases la plus récente (v5.3.x, dont la dernière date du 28 août 2026) ferme un manque de longue date : le workflow de réunion fonctionne désormais de bout en bout (accepter/décliner/reporter une invitation remonte au serveur, l'organisateur voit la réponse), la **disponibilité (libre/occupé) d'un participant s'affiche à l'invitation**, et le **GAL devient un carnet d'adresses consultable en recherche** plutôt qu'un ajout à l'aveugle. Pour l'ajout d'une salle, cela devrait donc apporter une expérience sensiblement meilleure qu'en CalDAV pur : disponibilité affichée nativement, comme le ferait un client EAS mobile.

Deux réserves cependant, avant de retenir cette voie :
- Les notes de version ne mentionnent aucun sélecteur dédié « parcourir les salles disponibles » ni de mécanisme explicite d'auto-acceptation par la salle (l'équivalent du « Set as Resource ») — seulement la disponibilité générique des participants, salle comprise si son adresse est connue.
- La suite de tests de bout en bout de cet add-on est explicitement exécutée contre **Microsoft 365 et Kopano/Z-Push** — pas contre Grommunio. EAS étant un protocole documenté et partagé, la compatibilité devrait suivre dans la mesure où `grommunio-sync` l'implémente correctement, mais ce n'est ni testé ni certifié par les mainteneurs de l'add-on pour Grommunio spécifiquement.
- C'est un add-on tiers en développement actif, pas un composant officiel de Thunderbird — à évaluer sous l'angle maintenance et pérennité avant adoption en production, au même titre que les autres dépendances externes de ce document.

**Critères de choix**
- Accepter la limite comme une perte structurelle assumée pour les utilisateurs Thunderbird/mobile en configuration CalDAV par défaut, en les orientant vers grommunio-web pour toute réservation de salle — cohérent avec le principe déjà posé en 1.9 (« tous les clients n'exposent pas toutes les fonctionnalités, grommunio-web reste la référence fonctionnelle complète »).
- Ou tester `TbSync` + `EAS-4-TbSync` comme configuration alternative pour les utilisateurs Thunderbird qui ont un besoin fréquent de visibilité sur les salles, en gardant à l'esprit qu'il s'agit d'un add-on tiers non certifié sur Grommunio et que la fonctionnalité de recherche/réservation à proprement parler n'est pas confirmée, seule la disponibilité l'est.
- Documenter cette limite dans la communication du projet, pour éviter la découverte en production par un consultant qui chercherait le Room Finder dans Thunderbird sans le trouver.

**Conclusion — brique retenue**
**Aucun connecteur à développer** : la réservation de salle reste une fonctionnalité complète côté **grommunio-web** et **Outlook**. Côté **Thunderbird**, deux configurations coexistent : CalDAV natif (visibilité de disponibilité seule, sans recherche ni auto-acceptation) ou **EAS via `TbSync` + `EAS-4-TbSync`** (meilleure visibilité de disponibilité, workflow de réunion complet, mais toujours sans sélecteur de salles ni auto-acceptation confirmée, et sur un chemin non testé officiellement contre Grommunio). Côté **mobile (EAS natif)**, situation similaire, non confirmée à ce stade. **À vérifier concrètement en recette** avant de choisir une configuration par défaut et de communiquer une limite définitive aux consultants : comportement réel de l'ajout d'une salle en CalDAV, avec `EAS-4-TbSync`, et sur mobile.

---

## Chapitre 3 — Ce que l'on perd par rapport à Office 365, faute d'alternative

Certaines pertes par rapport à Office 365 sont un choix assumé (souveraineté et coût contre confort applicatif intégré, cf. arbitrages du chapitre 1). D'autres ne sont pas un choix : ce sont des impossibilités structurelles, faute d'alternative existante ou faute de dépendre d'un mécanisme qui n'appartient qu'à Microsoft. Ce chapitre isole ces secondes pertes, pour que la décision de sortie d'Office 365 se prenne en connaissance de cause.

### 3.1 Interopérabilité avec les Teams des clients

**Le constat concret** : un cabinet de conseil échange en continu avec des clients qui, eux, restent sur Microsoft 365/Teams. La question posée est directe — faudra-t-il faire créer un compte Teams à chaque consultant chez chaque client pour pouvoir échanger avec eux, ou existe-t-il un moyen plus léger ?

**Ce qui ne pose pas de problème : les réunions ponctuelles**
Rejoindre une réunion Teams organisée par un client ne nécessite aucun compte : n'importe qui peut rejoindre une réunion Teams en tant qu'invité depuis un navigateur, en indiquant simplement son nom, sans créer de compte ni installer l'application. C'est strictement symétrique à ce que Visio permet déjà pour les participants externes à votre propre stack. **Aucune perte ici.**

**Ce qui pose problème : le chat et la présence persistants avec un client**
Deux mécanismes distincts existent côté Microsoft pour ce besoin, et aucun des deux n'est pleinement satisfaisant sans dépendre de Microsoft :

1. **L'accès externe (fédération Teams-to-Teams)** : permet de discuter, appeler et planifier des réunions avec des utilisateurs d'une autre organisation Microsoft 365, sans les ajouter comme invités — mais ce mécanisme ne fonctionne qu'**entre deux tenants Teams**. Depuis la fin de l'interopérabilité avec Skype consommateur (mai 2025), la fédération externe ne fonctionne plus qu'en Teams-à-Teams. **Un cabinet qui sort d'Office 365 et n'opère plus de tenant Teams perd donc l'accès à ce mécanisme** : impossible de faire dialoguer nativement Matrix et Teams par ce biais, faute de tenant Teams à fédérer côté cabinet.
2. **L'accès invité (guest access)** : le client ajoute chaque consultant comme invité dans son propre tenant Microsoft 365, ce qui crée un compte invité dans son annuaire (Entra ID). Ce compte **ne consomme pas de licence Teams/Microsoft 365** côté client ni côté cabinet — le consultant peut se connecter avec un compte Microsoft personnel gratuit, un compte Google, ou un simple code à usage unique. Ce n'est donc pas un abonnement Microsoft 365 à acheter, mais **une contrainte structurelle demeure** : chaque consultant doit être invité individuellement, tenant client par tenant client, sans aucune passerelle avec Matrix — l'échange se déroule entièrement à l'intérieur du Teams du client, invisible du centre de notifications et de la recherche unifiée bâtis en chapitre 2. Un consultant travaillant avec 5 clients différents accumule potentiellement 5 identités invitées distinctes, dans 5 interfaces Teams distinctes.

**Conclusion — perte assumée, sans alternative complète**
Il n'existe pas de pont mûr et officiellement supporté entre Matrix et Teams équivalent à la fédération Teams-Teams. Des ponts communautaires (bridges Matrix-Teams) existent mais reposent sur des API non garanties dans la durée par Microsoft, et ne sont pas retenus pour un usage professionnel structurant. **La seule option viable reste l'invitation en tant qu'invité dans le tenant du client, sans coût de licence, mais sans unification possible avec le reste de la stack du cabinet.** Ce point est à intégrer explicitement dans la communication du projet : la sortie d'Office 365 ne supprime pas le besoin, pour chaque consultant, de gérer une identité par client resté sur Teams.

### 3.2 Intelligence artificielle intégrée (Copilot)

Aucun équivalent natif à Copilot n'existe dans Word/Excel/Outlook/Teams pour résumer, générer, réécrire ou analyser des données depuis l'interface. Des outils IA externes (dont Claude) peuvent être branchés en périphérie de la stack (génération de contenu, assistance à la rédaction), mais l'intégration « dans le clic », au sein même de chaque application, n'existe pas nativement dans les briques retenues au chapitre 1.

### 3.3 Graphe de données inter-applicatif natif

Chez Microsoft 365, Teams/Outlook/SharePoint/OneDrive partagent un même graphe de données (Microsoft Graph) : recherche unifiée, pièce jointe qui devient automatiquement un lien SharePoint, présence partagée partout. La stack retenue reste, malgré les chantiers d'intégration du chapitre 2 (centre de notifications, recherche unifiée), une fédération d'outils indépendants dont l'intégration reste plus superficielle qu'un vrai graphe de données commun — les connecteurs développés relient des événements, pas une base de données partagée.

### 3.4 Maturité et unification des applications mobiles

Les apps mobiles (Element, Grommunio, Seafile, Vikunja) sont fonctionnelles mais individuellement moins abouties que Outlook/Teams mobile en finition, et restent des applications distinctes côté utilisateur plutôt qu'une expérience unifiée — malgré les efforts de facilitation d'installation traités en 2.5.

### 3.5 Fonctions de conformité et gouvernance packagées

DLP (Data Loss Prevention), eDiscovery, retention policies avancées, conformité réglementaire industrialisée (litigation hold notamment), audit centralisé cross-services : ces fonctions existent chez Microsoft de façon packagée et prête à l'emploi. Dans la stack retenue, l'équivalent devra être reconstruit brique par brique (rétention de messages Matrix, politiques de conservation Seafile, archivage Grommunio) ou accepté avec un niveau de conformité plus artisanal, faute de suite de conformité transverse équivalente.

### 3.6 Responsabilité et support uniques

Avec Office 365, un seul fournisseur, un seul SLA, un seul point de contact en cas d'incident. Avec la stack retenue, la responsabilité est éclatée entre plusieurs éditeurs et communautés open source : en cas de bug ou d'incident touchant plusieurs briques à la fois, c'est le cabinet (ou son prestataire d'exploitation, cf. chapitre 5) qui porte l'intégration et le diagnostic cross-services, sans interlocuteur unique à engager contractuellement sur l'ensemble de la chaîne.

---

## Chapitre 4 — Infrastructure et modalités de déploiement

### 4.1 Principe général

L'ensemble de la stack doit pouvoir être redéployé intégralement à partir de zéro (nouvel environnement, reconstruction après incident majeur, duplication pour un nouveau client) à partir d'un dépôt de code source décrivant l'intégralité de l'infrastructure et de la configuration — approche dite d'infrastructure as code (IaC).

Compte tenu de l'ambition de croissance du cabinet, cette description IaC doit être paramétrée en capacité (nombre de réplicas, ressources allouées par brique) plutôt que figée pour un effectif donné : monter en charge de 100 à plusieurs milliers de consultants doit se traduire par une simple variation de ces paramètres et un ajout de nœuds au cluster, jamais par une réécriture de la définition d'infrastructure elle-même.

### 4.2 Couche de virtualisation et choix d'hébergement

**Décision retenue : infrastructure opérée en propre (ou en colocation), virtualisée avec Proxmox VE — pas de cloud managé.**

Deux options avaient été envisagées :
- **Hébergement chez un fournisseur cloud/Kubernetes managé** (ex. offre souveraine type OVHcloud, Scaleway) : la couche de virtualisation est prise en charge par le fournisseur, invisible pour le cabinet — solution la plus simple à opérer, mais qui réintroduit une forme de dépendance à un tiers pour l'hébergement, à contre-courant de la logique de souveraineté qui motive l'ensemble de ce projet dès son introduction (réduire la dépendance à un éditeur unique non européen) et du choix déjà fait d'auto-héberger Visio.
- **Infrastructure opérée en propre, sur du matériel physique détenu ou loué en baremetal/colocation** : demande une couche d'hyperviseur pour virtualiser les serveurs physiques avant d'y déployer Kubernetes.

**Le second choix est retenu.** Il est cohérent avec la maîtrise complète de la chaîne visée par le projet (le cabinet contrôle alors la localisation physique des données de bout en bout, pas seulement le logiciel), et avec les choix déjà pris pour Grommunio et Visio, qui présupposent un hébergement en propre. Le compromis assumé : la charge d'exploitation de l'infrastructure physique (matériel, réseau, datacenter/colocation) repose sur le cabinet ou son prestataire d'exploitation (chapitre 5), plutôt que sur un fournisseur cloud — cohérent avec le reste de la stack, où la responsabilité est déjà assumée comme éclatée entre plusieurs briques (cf. 3.6).

**Proxmox VE** est retenu comme couche d'hyperviseur : open source, éprouvé pour de l'auto-hébergement sérieux, doté d'un provider Terraform/OpenTofu mature (`bpg/proxmox`) permettant de définir les machines virtuelles hébergeant les nœuds Kubernetes de façon entièrement déclarative — cohérent avec l'approche IaC du chapitre 4.1. Proxmox permet également la haute disponibilité au niveau de l'hyperviseur (cluster Proxmox à plusieurs nœuds physiques, migration à chaud des VM), ce qui vient compléter la haute disponibilité déjà prévue au niveau applicatif (Synapse en mode workers, cluster Keycloak, cluster OnlyOffice Document Server).

**Recommandation** : **Proxmox VE** est intégré au dépôt IaC comme couche de virtualisation cible, avec le cluster Kubernetes déployé sur les VM qu'il provisionne — plutôt que d'installer Kubernetes directement sur les serveurs physiques (« bare metal »), ce qui priverait le cabinet de la flexibilité de migration/redimensionnement des VM et de l'isolation supplémentaire entre nœuds que permet la virtualisation.

### 4.3 Conteneurisation des briques

La majorité des briques de la stack (Matrix/Synapse, Element Call, Visio DINUM, MinIO, Seafile, OnlyOffice Document Server, Vikunja, Keycloak, Gokapi, le centre de notifications, le service de recherche unifiée, PeerTube, Caddy) est packagée sous forme de conteneur (Docker), ce qui permet :
- une définition reproductible et versionnée de chaque service (image, variables d'environnement, volumes) ;
- un déploiement identique quel que soit l'environnement cible (poste de développement, environnement de recette, production) ;
- une isolation claire entre les briques, cohérente avec l'approche « best of breed » retenue dans ce document ;
- une orchestration native dans Kubernetes (cf. 4.4), chacune de ces briques étant nativement pensée cloud-native (services sans état ou clusterisables).

**Exception assumée : Grommunio en VM appliance, pas en conteneur.** Grommunio propose bien un packaging conteneur officiel (`grommunio/gromox-container`), mais sa propre documentation le présente comme une solution pour des besoins spéciaux non couverts par l'appliance standard, pas comme le mode de déploiement principal recommandé — les defaults documentés sont explicitement qualifiés de non prêts pour la production, et le conteneur « core » bundle de nombreux services (nginx, Postfix, les daemons gromox, Redis, PHP-FPM) sous un seul processus supervisord, sans la décomposition en microservices qui s'orchestre naturellement dans Kubernetes. L'**appliance** (VM complète, ISO/OVA) reste le mode de déploiement le plus mature et le plus testé selon Grommunio lui-même. Grommunio est donc déployé comme **VM appliance directement sur Proxmox** (cf. 4.2), plutôt que conteneurisé dans Kubernetes comme le reste de la stack — un choix cohérent pour un service critique et à état (mailbox), qui bénéficie au passage de la haute disponibilité au niveau hyperviseur (cluster Proxmox, migration à chaud) déjà prévue pour d'autres raisons.

### 4.4 Orchestration

Compte tenu de l'ambition de croissance du cabinet (plusieurs milliers de consultants visés), l'orchestrateur retenu dès la conception initiale doit être celui qui permet le scaling horizontal sans changement d'architecture ultérieur, pour l'ensemble des briques conteneurisées identifiées en 4.3 :

- **Docker Compose** reste pertinent uniquement pour un environnement de développement/test à échelle réduite (chapitre 4.6), mais n'est pas retenu comme cible de production : il ne permet pas nativement le scaling horizontal ni la haute disponibilité requis par les briques identifiées comme critiques à cet égard (Synapse en mode workers, OnlyOffice Document Server en cluster, Keycloak en cluster).
- **Kubernetes** (avec des manifestes Helm par brique) est retenu comme cible de production dès le déploiement initial à 100 utilisateurs, précisément pour que la montée en charge vers 2000 puis plusieurs milliers de consultants se traduise par un ajout de capacité (nœuds, réplicas) plutôt que par une migration d'orchestrateur en cours de croissance — un changement d'architecture d'orchestration serait un risque et un coût bien supérieurs à la surcapacité initiale d'un cluster Kubernetes dimensionné large dès le départ. Les nœuds Kubernetes sont des VM Proxmox (cf. 4.2). Grommunio, hors périmètre Kubernetes (4.3), reste une VM Proxmox distincte, provisionnée et configurée par le même dépôt IaC (cf. 4.5).

**Alternative envisagée et écartée — Coolify**
Coolify (PaaS auto-hébergée, MIT, déploiement par git-push, catalogue de services en un clic) a été évaluée comme piste possible d'orchestration. **Écartée pour la cible de production**, pour trois raisons :
- Son mode multi-serveur repose sur **Docker Swarm**, pas Kubernetes — une limite architecturale assumée par l'éditeur lui-même, au point qu'une réécriture complète (v5) est en cours spécifiquement pour dépasser ce plafond, sans date de sortie annoncée. Adopter Coolify aujourd'hui reviendrait à réintroduire le risque qu'un choix de Kubernetes dès l'origine cherche précisément à éviter : un changement d'orchestrateur en cours de croissance.
- Fonctionne en root par défaut, et a fait l'objet de 11 CVE critiques (injection de commande, exposition de clé root) début 2026 — la charge de correction repose entièrement sur l'opérateur auto-hébergé.
- Introduirait un second paradigme de déploiement en parallèle de l'approche IaC déjà retenue (Terraform/OpenTofu + Ansible + Kubernetes/Helm), plutôt qu'un complément cohérent.

Coolify garde un intérêt marginal et optionnel comme **surcouche de confort pour l'environnement de développement/test** (4.6, déjà scopé sur Docker Compose à échelle réduite) — une interface web plutôt que la ligne de commande pour les développeurs qui itèrent sur ce tier — mais ne doit en aucun cas s'approcher de la cible de production Kubernetes.

Le fournisseur d'hébergement cible reste ouvert (datacenter/colocation en propre, à sélectionner selon les critères habituels : proximité, certification, coût), mais le principe d'une infrastructure en propre sur Proxmox, plutôt qu'un cloud managé, est désormais acté (cf. 4.2).

### 4.5 Provisionnement et configuration

- **Provisionnement de l'infrastructure sous-jacente** (VM Proxmox — dont la VM appliance Grommunio — ou ressources cloud, réseau, stockage) décrit par un outil d'infrastructure as code (Terraform ou OpenTofu), versionné dans le même dépôt que le reste de la stack.
- **Configuration applicative** de chaque brique (réalms et clients Keycloak, domaines Matrix, comptes de service, connecteurs d'intégration) automatisée via des playbooks (Ansible) ou des manifestes déclaratifs, plutôt que des étapes manuelles documentées.
- **Gestion des secrets** (mots de passe, clés API, certificats) externalisée dans un coffre-fort dédié (ex. Vault ou équivalent géré), jamais en clair dans le dépôt de code.

### 4.6 Environnements

Prévoir au minimum trois environnements strictement identiques dans leur définition IaC, ne différant que par leur taille et leurs données :
- **Développement/test** : échelle réduite, données synthétiques.
- **Recette** : échelle intermédiaire, utilisée notamment pour la validation des montées de version (voir chapitre 5).
- **Production**.

### 4.7 Sauvegarde et restauration

Chaque brique disposant de données persistantes (mailbox Grommunion, historique Synapse, fichiers Seafile, documents OnlyOffice, tâches Vikunja, réalms Keycloak) doit faire l'objet d'une stratégie de sauvegarde documentée et testée par des restaurations régulières — la capacité de « repartir de zéro » visée par l'approche IaC ne couvre que la reconstruction de l'infrastructure et de la configuration, pas la récupération des données elles-mêmes. Dans le scénario d'hébergement en propre sur Proxmox (4.2), les sauvegardes au niveau VM (snapshots Proxmox Backup Server) viennent compléter, sans les remplacer, les sauvegardes applicatives propres à chaque brique.

---

## Chapitre 5 — Exploitation et pilotage transverse

### 4.1 Objectif

Au-delà du déploiement initial, la stack doit être pilotée dans la durée de façon transverse à l'ensemble des briques : suivi des vulnérabilités, suivi des nouvelles versions disponibles, et validation outillée de ces nouvelles versions avant mise en production.

### 4.2 Veille sur les vulnérabilités (CVE)

- Mise en place d'un scan automatisé et régulier des images conteneurisées de chaque brique (type Trivy ou Grype) pour détecter les vulnérabilités connues affectant les dépendances embarquées.
- Abonnement aux flux de sécurité officiels de chaque brique (listes de diffusion sécurité ou flux RSS/GitHub Security Advisories de Grommunio, Synapse/Element, Seafile, OnlyOffice, Vikunja, Keycloak, Caddy) pour être alerté indépendamment du cycle de scan automatisé.
- Centralisation des alertes remontées (scan + veille éditeurs) vers un tableau de bord unique, avec une criticité et une brique concernée par alerte.

### 4.3 Veille sur les nouvelles versions disponibles

- Suivi automatisé des nouvelles releases de chaque brique (mécanisme de type Renovate ou Dependabot appliqué aux images de conteneurs et aux dépendances du dépôt IaC), plutôt qu'une vérification manuelle périodique.
- Chaque nouvelle version détectée (correctif de sécurité ou nouvelle fonctionnalité) déclenche la suite du processus décrit ci-dessous, plutôt que d'être appliquée directement en production.

### 4.4 Déclenchement automatique d'un environnement de recette

Lorsqu'une nouvelle version d'une brique est détectée :
1. Un environnement de recette éphémère est créé automatiquement à partir de la définition IaC (chapitre 4), avec la nouvelle version de la brique concernée et les versions courantes de toutes les autres briques.
2. Cet environnement est alimenté par un jeu de données de test représentatif (pas les données réelles de production).
3. Un pipeline d'intégration/déploiement continu (CI/CD) orchestre l'ensemble de ce cycle sans intervention manuelle jusqu'à l'étape de validation des résultats.

### 4.5 Rejeu des scénarios de test

- Maintien d'une bibliothèque de scénarios de test automatisés couvrant les usages critiques identifiés dans ce document : envoi/réception mail (Grommunio), création et synchronisation de fichier (Seafile), co-édition d'un document (OnlyOffice), envoi de message et démarrage d'une visio depuis une room (Matrix/Element/Visio), création et notification d'une tâche (Vikunja), authentification SSO bout en bout (Keycloak) sur chacune des briques précédentes.
- Ces scénarios sont rejoués automatiquement sur l'environnement de recette éphémère à chaque nouvelle version détectée, avant toute promotion en production.
- Un rapport de résultats (succès/échec par scénario) conditionne la décision de promotion de la nouvelle version vers la production — manuelle ou automatisée selon la criticité de la brique concernée.

### 4.6 Pilotage transverse

- Tableau de bord unique consolidant : état des vulnérabilités ouvertes par brique, versions courantes vs. versions disponibles par brique, résultats des derniers passages en recette, état de santé (supervision technique) de chaque brique en production.
- Ce pilotage transverse est distinct du centre de notifications utilisateur (chapitre 2) : il s'adresse à l'équipe d'exploitation, pas aux consultants utilisateurs finaux de la stack.

---

*Document de travail — à compléter et préciser au fil des prochaines sessions. Points encore ouverts à ce stade : présence unifiée — connecteur d'agrégation à développer (2.8) ; bouton visio depuis Grommunio — solution de repli (lien réutilisable) retenue dans l'immédiat, bouton d'intégration complet conditionné à la disponibilité d'une API de création de room côté Visio, à confirmer auprès de la DINUM (2.9) ; sélection définitive du fournisseur d'hébergement/datacenter (4.2) ; à confirmer à l'usage : niveau d'adoption réel de Thunderbird/Apple Mail par les consultants habitués à Outlook, une fois Outlook pour Mac explicitement écarté pour motif de souveraineté (1.9) ; à valider en recette : maturité du GAL en CardDAV (`GAL_ENABLED`, fonctionnalité de juin 2026) sur un annuaire à l'échelle de croissance visée (2.13) ; à valider en recette : comportement réel du workflow de réservation de salle initié depuis Thunderbird ou un mobile en EAS, avant de communiquer une limite définitive aux consultants (2.14) ; **à ré-évaluer dans une prochaine itération : Euro-Office (fork souverain d'OnlyOffice Document Server) comme candidat de remplacement à OnlyOffice, une fois sa maturité, l'issue de son litige AGPL avec Ascensio System, et sa compatibilité effective avec le connecteur Seafile confirmées (1.5)** ; **avant mise en production de Gokapi : confirmer par un audit indépendant ou une veille active la robustesse de son implémentation E2EE (non auditée selon l'éditeur lui-même), et vérifier que la documentation Keycloak/OIDC utilisée pour la configuration est bien à jour (un exemple de configuration antérieur a permis un accès non autorisé par le passé) (1.8)** ; les connecteurs identifiés dans ce document restent à développer (centre de notifications 2.1, recherche unifiée 2.2, widget Visio↔Matrix 2.4, agrégateur de présence unifiée 2.8, webhook PeerTube 2.12, handler de mentions OnlyOffice 2.7, module Filelink Thunderbird pour Gokapi 2.11, SPI Keycloak pour OTP SMS et mail 1.7) ; procédure interne de signalement/retrait à documenter pour Gokapi, incluant les habilitations d'accès à l'association fichier/déposant conservée nativement par l'outil (1.8).*
