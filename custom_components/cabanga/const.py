"""Constantes pour l'intégration Cabanga."""
from datetime import timedelta

DOMAIN = "cabanga"

# Endpoints Keycloak (authentification)
TOKEN_URL = "https://login.scolares.be/auth/realms/horizon/protocol/openid-connect/token"
CLIENT_ID = "cabanga-frontend"

# Endpoints API Cabanga
API_BASE_URL = "https://api.scolares.be/cabanga/api"

# Configuration
CONF_REFRESH_TOKEN = "refresh_token"
CONF_STUDENTS = "students"  # liste de {"school_id": ..., "id": ..., "name": ...}

# Options
DEFAULT_SCAN_INTERVAL = timedelta(hours=3)

# Fenêtre de récupération du journal / devoirs (jours avant / après aujourd'hui)
DIARY_DAYS_BEFORE = 7
DIARY_DAYS_AFTER = 14
