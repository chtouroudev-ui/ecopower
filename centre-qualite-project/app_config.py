from pathlib import Path

BASE = Path(__file__).resolve().parent
APP_DB = BASE / "TECHIN_Stock_Manager.db"
STATIC = BASE / "static"
LEGACY_DIAG_DB = BASE / "diagnostic.db"
LEGACY_STOCK_DB = BASE / "stock.db"
LEGACY_AUTH_DB = BASE / "auth.db"
ADMIN_PASSWORD_FILE = BASE / "INITIAL_ADMIN.txt"
SESSION_COOKIE = "techin_session"
SESSION_MAX_HOURS = 8
SESSION_IDLE_MINUTES = 30
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_MINUTES = 10
MAX_JSON_BYTES = 1_048_576
PBKDF2_ROUNDS = 450_000
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
FALLBACK_PORTS = list(range(5050, 5101))

ADMIN_STATUS = {"EN_SERVICE", "STOCK", "REPARATION", "REFORME", "PERDU"}
ROLES = {"admin", "technician", "viewer"}
ROLE_LEVEL = {"viewer": 10, "technician": 20, "admin": 30}

ACCESS_MODULES = {
    "collection": {"label": "Live Nelyio", "description": "Lecture : Supervision Live. Modification : configuration et pilotage du collecteur local", "write": True},
    "dashboard": {"label": "Tableau de bord", "description": "Vue d'ensemble du parc", "write": False},
    "inventory": {"label": "Gestion du parc", "description": "Parc, fiches PC, affectations et modifications", "write": True},
    "consumables": {"label": "Consommables", "description": "Stock consommables, entrées/sorties et traçabilité", "write": True},
    "support": {"label": "Support technique Nelyio", "description": "Statistiques, incidents, notes et imports Support", "write": True},
    "analytics": {"label": "Analyse & tendances Nelyio", "description": "Comparer périodes, tendances, récurrences, distributions et incidents simultanés", "write": False},
    "details": {"label": "Détails des logs Nelyio", "description": "Consulter les journaux détaillés par jour, groupe, agent et client", "write": False},
    "calls": {"label": "Recherche d'appels Nelyio", "description": "Recherche ANI/indice et imports d'appels", "write": True},
    "ani": {"label": "Voir ANI complet", "description": "Afficher et rechercher le numéro appelant complet dans les vues historiques et Live", "write": False},
    "config": {"label": "Configuration", "description": "Base, import diagnostic, réseau et HTTPS", "write": True},
    "classification": {"label": "Règles de tri", "description": "Réseau, annuaire agents, groupes et exclusions", "write": True},
    "policies": {"label": "Policies Nelyio", "description": "Règles métier transversales appliquées aux analyses techniques", "write": True},
    "declarations": {"label": "Déclarations", "description": "Autorisations, interventions, réunions et autres périodes déclarées par les responsables", "write": True},
    "quality": {"label": "Analytiques · Qualité", "description": "Pilotage qualité, appels suspects et analyses agents/files", "write": True},
    "users": {"label": "Utilisateurs & accès", "description": "Comptes, groupes de sécurité et permissions", "write": True},
    "security": {"label": "Sécurité & audit", "description": "Journaux de connexion et événements sensibles", "write": False},
}
ACCESS_INTERFACES = {
    "dashboard": {"label": "Vue d'ensemble", "section": "Parc", "module": "dashboard", "write": False},
    "inventory": {"label": "Ordinateurs", "section": "Parc", "module": "inventory", "write": True},
    "consumables": {"label": "Consommables", "section": "Parc", "module": "consumables", "write": True},
    "inventory_add": {"label": "Ajouter un ordinateur", "section": "Parc", "module": "inventory", "write": True, "write_only": True},

    "live_supervision": {"label": "Centre Qualité Live", "section": "Live", "module": "collection", "write": False},
    "live_campaigns": {"label": "Campagnes à surveiller", "section": "Live", "module": "collection", "write": False},
    "live_incidents": {"label": "Incidents / Alertes", "section": "Live", "module": "collection", "write": True},
    "live_search": {"label": "Recherche d'appels Live", "section": "Live", "module": "calls", "write": False},

    "support": {"label": "Diagnostic technique", "section": "Support", "module": "support", "write": True},
    "disconnect_details": {"label": "Détails des coupures", "section": "Support", "module": "details", "write": False},
    "calls": {"label": "Recherche d'appels", "section": "Support", "module": "calls", "write": True},
    "details": {"label": "Journal détaillé", "section": "Support", "module": "details", "write": False},
    "analytics": {"label": "Tendances techniques", "section": "Support", "module": "analytics", "write": False},
    "reports": {"label": "Rapports", "section": "Support", "module": "support", "write": False},
    "declarations": {"label": "Déclarations", "section": "Support", "module": "declarations", "write": True},

    "analytics_home": {"label": "Synthèse Analytiques", "section": "Analytiques", "module": "quality", "write": False},
    "quality_pilotage": {"label": "Analyse détaillée", "section": "Analytiques", "module": "quality", "write": True},
    "quality_activity": {"label": "Qualité agents", "section": "Analytiques", "module": "quality", "write": False},
    "quality_overview": {"label": "Qualité de service", "section": "Analytiques", "module": "quality", "write": False},
    "quality_distributions": {"label": "Distributions", "section": "Analytiques", "module": "quality", "write": False},
    "suspicious_calls": {"label": "Appels suspects", "section": "Analytiques", "module": "quality", "write": False},
    "classification_groups": {"label": "Groupes et équipes", "section": "Analytiques", "module": "classification", "write": True},
    "quality_agents": {"label": "Priorités des agents", "section": "Analytiques", "module": "quality", "write": True},
    "quality_bases": {"label": "Priorités des files", "section": "Analytiques", "module": "quality", "write": True},

    "collection_admin": {"label": "Collecteur Live", "section": "Administration", "module": "collection", "write": True},
    "live_quality_admin": {"label": "Signalisation Qualité Live", "section": "Administration", "module": "config", "write": True},
    "production_health": {"label": "Santé de production", "section": "Administration", "module": "config", "write": False},
    "config": {"label": "Paramètres de l'application", "section": "Administration", "module": "config", "write": True},
    "classification": {"label": "Règles de classement", "section": "Administration", "module": "classification", "write": True},
    "support_priority": {"label": "Niveaux d'alerte", "section": "Administration", "module": "classification", "write": True},
    "policies": {"label": "Règles d'analyse", "section": "Administration", "module": "policies", "write": True},
    "users": {"label": "Utilisateurs et droits", "section": "Administration", "module": "users", "write": True},
    "security": {"label": "Sécurité et audit", "section": "Administration", "module": "security", "write": False},
}

ACCESS_NONE = 0
ACCESS_READ = 1
ACCESS_WRITE = 2
EDIT_FIELDS = [
    "asset_tag", "statut", "affectation", "emplacement_attendu", "notes",
    "manual_utilisateur", "manual_ip", "manual_mac", "manual_sn_pc",
    "manual_sn_carte_mere", "manual_domaine", "manual_fabricant",
    "manual_modele", "manual_windows", "manual_version_windows"
]
DIAG_FIELDS = [
    "event_uuid", "date_evenement", "action", "utilisateur", "ordinateur",
    "adresse_ip", "passerelle", "adresse_mac", "sn_pc", "sn_carte_mere",
    "domaine", "fabricant", "modele", "windows", "version_windows",
    "collecteur", "version_script", "date_import"
]
SITE_VALUES = {"SUR SITE", "TELETRAVAIL", "INCONNU"}
