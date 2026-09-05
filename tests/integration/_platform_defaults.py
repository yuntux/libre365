"""
Fichier généré par scripts/sync_platform.py à partir de platform.yaml.
Ne PAS éditer à la main : les valeurs par défaut de tests/integration/conftest.py
doivent rester alignées avec les ports par défaut de docker-compose (étude 4.6) —
c'est précisément ce que ce fichier garantit en étant généré depuis la même
source que docker-compose/.env.example.
"""

DEFAULT_PORTS = {
    "CADDY_HTTPS_PORT": 10443,
    "CADDY_HTTP_PORT": 10080,
    "ELEMENT_PORT": 8081,
    "GOKAPI_PORT": 53842,
    "GROMMUNIO_DEV_HTTP_PORT": 8443,
    "KEYCLOAK_PORT": 8080,
    "MINIO_API_PORT": 9000,
    "MINIO_CONSOLE_PORT": 9001,
    "NOTIFICATION_HUB_PORT": 4001,
    "NOVU_MOCK_PORT": 13000,
    "ONLYOFFICE_MENTIONS_PORT": 4004,
    "ONLYOFFICE_PORT": 8083,
    "PEERTUBE_INGEST_PORT": 4005,
    "PEERTUBE_PORT": 9002,
    "POSTGRES_KEYCLOAK_PORT": 5433,
    "POSTGRES_ONLYOFFICE_PORT": 5435,
    "POSTGRES_SYNAPSE_PORT": 5434,
    "PRESENCE_AGGREGATOR_PORT": 4003,
    "SEAFILE_PORT": 8082,
    "SYNAPSE_CLIENT_PORT": 8008,
    "SYNAPSE_FEDERATION_PORT": 8448,
    "UNIFIED_SEARCH_PORT": 4002,
    "VIKUNJA_PORT": 3456,
}
