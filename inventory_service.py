import re
import json
import db_compat as sqlite3
from inventory_followup import enrich_config

def site_case(collector_expr, ip_expr, gateway_expr="''"):
    return f"classify_site({collector_expr}, {ip_expr}, {gateway_expr})"

def dashboard_transitions_sql(limit=10):
    """SQL used by the Dashboard for PCs seen on both local and remote sites.

    PostgreSQL only allows a SELECT alias in ORDER BY as a bare name; wrapping
    that alias in CAST()/datetime() makes it resolve as a physical input
    column. Order by the aggregate expression itself so the query is portable.
    """
    history_site = site_case("collecteur", "adresse_ip", "passerelle")
    return f"""
        SELECT ordinateur,GROUP_CONCAT(DISTINCT site) sites,COUNT(DISTINCT site) nb_sites,MAX(date_evenement) derniere_vue
        FROM (SELECT ordinateur,date_evenement,{history_site} AS site FROM diagnostic WHERE ordinateur IS NOT NULL)
        WHERE site IN ('SUR SITE','TELETRAVAIL')
        GROUP BY ordinateur HAVING COUNT(DISTINCT site)>1
        ORDER BY MAX(date_evenement) DESC LIMIT {int(limit)}
    """


def pc_users_sql():
    """Per-PC user history, ordered by the aggregate rather than its alias."""
    return """
        SELECT utilisateur,COUNT(*) passages,MIN(date_evenement) premiere_vue,MAX(date_evenement) derniere_vue
        FROM diagnostic WHERE ordinateur=? GROUP BY utilisateur ORDER BY MAX(date_evenement) DESC
    """


def current_sql(where="", order="ordinateur ASC"):
    site = site_case("d.collecteur", "d.adresse_ip", "d.passerelle")
    reason = f"classify_reason(d.collecteur, d.adresse_ip, d.passerelle)"
    effective_user = "COALESCE(NULLIF(m.manual_utilisateur,''),d.utilisateur,'')"
    if sqlite3.postgres_enabled():
        # PostgreSQL: use native date arithmetic. This avoids SQLite-only
        # julianday()/MAX(x,y) scalar semantics in the Dashboard/Inventory SQL.
        age_days = "GREATEST(0, (CURRENT_DATE - CAST(d.date_evenement AS date)))"
        date_is_today = "CAST(d.date_evenement AS date)=CURRENT_DATE"
    else:
        age_days = "MAX(0,CAST(julianday(date('now','localtime'))-julianday(date(d.date_evenement)) AS INTEGER))"
        date_is_today = "date(d.date_evenement)=date('now','localtime')"
    if sqlite3.postgres_enabled():
        latest_cte = """
    d AS (
        SELECT DISTINCT ON (d0.ordinateur) d0.*
        FROM diagnostic d0
        WHERE d0.ordinateur IS NOT NULL AND TRIM(d0.ordinateur) <> ''
        ORDER BY d0.ordinateur, d0.date_evenement DESC, d0.id DESC
    )"""
    else:
        latest_cte = """
    ranked AS (
        SELECT d0.*, ROW_NUMBER() OVER (
            PARTITION BY d0.ordinateur ORDER BY datetime(d0.date_evenement) DESC, d0.id DESC
        ) rn
        FROM diagnostic d0
        WHERE d0.ordinateur IS NOT NULL AND TRIM(d0.ordinateur) <> ''
    ), d AS (
        SELECT * FROM ranked WHERE rn=1
    )"""
    return f"""
    WITH {latest_cte}, names AS (
        SELECT ordinateur FROM d
        UNION
        SELECT ordinateur FROM asset_management
    ), c AS (
        SELECT
            n.ordinateur,
            d.id,d.event_uuid,d.date_evenement,d.action,
            {effective_user} AS utilisateur,
            COALESCE(NULLIF(TRIM(COALESCE(ud.first_name,'') || ' ' || COALESCE(ud.last_name,'')),''),{effective_user}) AS utilisateur_affiche,
            COALESCE(ud.first_name,'') AS utilisateur_prenom,
            COALESCE(ud.last_name,'') AS utilisateur_nom,
            COALESCE(NULLIF(m.manual_ip,''),d.adresse_ip,'') AS adresse_ip,
            COALESCE(d.passerelle,'') AS passerelle,
            COALESCE(NULLIF(m.manual_mac,''),d.adresse_mac,'') AS adresse_mac,
            COALESCE(NULLIF(m.manual_sn_pc,''),d.sn_pc,'') AS sn_pc,
            COALESCE(NULLIF(m.manual_sn_carte_mere,''),d.sn_carte_mere,'') AS sn_carte_mere,
            COALESCE(NULLIF(m.manual_domaine,''),d.domaine,'') AS domaine,
            COALESCE(NULLIF(m.manual_fabricant,''),d.fabricant,'') AS fabricant,
            COALESCE(NULLIF(m.manual_modele,''),d.modele,'') AS modele,
            COALESCE(NULLIF(m.manual_windows,''),d.windows,'') AS windows,
            COALESCE(NULLIF(m.manual_version_windows,''),d.version_windows,'') AS version_windows,
            COALESCE(d.collecteur,'') AS collecteur,
            COALESCE(d.version_script,'') AS version_script,
            COALESCE(m.statut,'EN_SERVICE') AS statut,
            COALESCE(m.asset_tag,'') AS asset_tag,
            COALESCE(m.affectation,'') AS affectation,
            COALESCE(m.emplacement_attendu,'') AS emplacement_attendu,
            COALESCE(m.notes,'') AS notes,
            COALESCE(m.manual_utilisateur,'') AS manual_utilisateur,
            COALESCE(m.manual_ip,'') AS manual_ip,
            COALESCE(m.manual_mac,'') AS manual_mac,
            COALESCE(m.manual_sn_pc,'') AS manual_sn_pc,
            COALESCE(m.manual_sn_carte_mere,'') AS manual_sn_carte_mere,
            COALESCE(m.manual_domaine,'') AS manual_domaine,
            COALESCE(m.manual_fabricant,'') AS manual_fabricant,
            COALESCE(m.manual_modele,'') AS manual_modele,
            COALESCE(m.manual_windows,'') AS manual_windows,
            COALESCE(m.manual_version_windows,'') AS manual_version_windows,
            COALESCE(m.created_manually,0) AS created_manually,
            COALESCE(m.created_by,'') AS created_by,
            COALESCE(m.updated_by,'') AS updated_by,
            m.updated_at,
            CASE WHEN d.id IS NULL THEN 0 ELSE 1 END AS has_diagnostic,
            {site} AS site_actuel,
            {reason} AS site_reason,
            COALESCE(g.id,0) AS groupe_id,
            COALESCE(g.name,'') AS groupe_utilisateur,
            CASE
                WHEN d.date_evenement IS NULL OR TRIM(d.date_evenement)='' THEN NULL
                ELSE {age_days}
            END AS jours_depuis_vue,
            COALESCE(followup_status(COALESCE(m.statut,'EN_SERVICE'),
                CASE WHEN d.date_evenement IS NULL OR TRIM(d.date_evenement)='' THEN NULL
                     ELSE {age_days} END,
                (SELECT value FROM settings WHERE key='inventory_followup_policy_v2')),
            CASE
                WHEN COALESCE((SELECT value FROM settings WHERE key='inventory_followup_override_stock'),'1')='1' AND COALESCE(m.statut,'EN_SERVICE')='STOCK' THEN 'STOCK'
                WHEN COALESCE((SELECT value FROM settings WHERE key='inventory_followup_override_repair'),'1')='1' AND COALESCE(m.statut,'EN_SERVICE')='REPARATION' THEN 'REPARATION'
                WHEN COALESCE((SELECT value FROM settings WHERE key='inventory_followup_override_lost'),'1')='1' AND COALESCE(m.statut,'EN_SERVICE')='PERDU' THEN 'KO'
                WHEN COALESCE((SELECT value FROM settings WHERE key='inventory_followup_override_retired'),'1')='1' AND COALESCE(m.statut,'EN_SERVICE')='REFORME' THEN 'REFORME'
                WHEN d.date_evenement IS NULL OR TRIM(d.date_evenement)='' THEN 'CRITIQUE'
                WHEN {date_is_today} THEN 'EN_SERVICE'
                WHEN {age_days} > CAST(COALESCE((SELECT value FROM settings WHERE key='inventory_followup_late_days'),'20') AS INTEGER) THEN 'CRITIQUE'
                WHEN {age_days} > CAST(COALESCE((SELECT value FROM settings WHERE key='inventory_followup_warning_days'),'7') AS INTEGER) THEN 'RETARD_7J'
                ELSE 'PAS_A_JOUR'
            END) AS suivi_statut,
            CASE WHEN COALESCE(m.emplacement_attendu,'')<>'' AND m.emplacement_attendu<>({site}) THEN 1 ELSE 0 END AS emplacement_ecart,
            CASE WHEN m.ordinateur IS NOT NULL AND (
                COALESCE(m.manual_utilisateur,'')<>'' OR COALESCE(m.manual_ip,'')<>'' OR COALESCE(m.manual_mac,'')<>'' OR
                COALESCE(m.manual_sn_pc,'')<>'' OR COALESCE(m.manual_sn_carte_mere,'')<>'' OR COALESCE(m.manual_domaine,'')<>'' OR
                COALESCE(m.manual_fabricant,'')<>'' OR COALESCE(m.manual_modele,'')<>'' OR COALESCE(m.manual_windows,'')<>'' OR
                COALESCE(m.manual_version_windows,'')<>''
            ) THEN 1 ELSE 0 END AS has_manual_override
        FROM names n
        LEFT JOIN d ON d.ordinateur=n.ordinateur
        LEFT JOIN asset_management m ON m.ordinateur=n.ordinateur
        LEFT JOIN user_group_members gm ON gm.user_key=user_key({effective_user})
        LEFT JOIN user_groups g ON g.id=gm.group_id
        LEFT JOIN user_directory ud ON ud.user_key=user_key({effective_user})
    )
    SELECT * FROM c
    {where}
    ORDER BY {order}
    """

def rows_to_dict(rows):
    return [dict(r) for r in rows]

def clean_pc_name(value):
    value = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9._-]{1,64}", value):
        return None
    return value

def clean_username(value):
    value = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,40}", value):
        return None
    return value


DEFAULT_FOLLOWUP_LABELS = {
    "EN_SERVICE": "À jour", "PAS_A_JOUR": "Pas à jour", "RETARD_7J": "Retard",
    "CRITIQUE": "Critique", "STOCK": "En stock", "REPARATION": "Réparation",
    "KO": "KO / perdu", "REFORME": "Réformé",
}

def followup_config(con):
    rows = {r[0]: r[1] for r in con.execute("SELECT key,value FROM settings WHERE key LIKE 'inventory_followup_%'").fetchall()}
    try:
        warning = max(1, min(3650, int(rows.get("inventory_followup_warning_days", "7"))))
    except Exception:
        warning = 7
    try:
        late = max(warning + 1, min(3650, int(rows.get("inventory_followup_late_days", "20"))))
    except Exception:
        late = 20
    labels = dict(DEFAULT_FOLLOWUP_LABELS)
    try:
        incoming = json.loads(rows.get("inventory_followup_labels", "{}") or "{}")
        if isinstance(incoming, dict):
            for key in labels:
                value = str(incoming.get(key, "") or "").strip()
                if value:
                    labels[key] = value[:60]
    except Exception:
        pass
    return enrich_config({
        "warning_days": warning, "late_days": late, "labels": labels,
        "override_stock": rows.get("inventory_followup_override_stock", "1") == "1",
        "override_repair": rows.get("inventory_followup_override_repair", "1") == "1",
        "override_lost": rows.get("inventory_followup_override_lost", "1") == "1",
        "override_retired": rows.get("inventory_followup_override_retired", "1") == "1",
    }, rows)
