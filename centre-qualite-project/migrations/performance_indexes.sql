-- NELYIO V60.3 - index de performance PostgreSQL
-- Non destructif et idempotent. A executer manuellement sur la base Nelyio
-- APRES sauvegarde et de preference hors pic d'activite.
-- Ce script ne supprime aucun index/table et n'active aucune extension.

-- Preuve code/HAR : Recherche d'appels et Support bornent d'abord chaque jour
-- par (import_id, start). Les index historiques commençaient par first_agent
-- ou campaign et ne couvrent pas ce cas général.
CREATE INDEX IF NOT EXISTS supervision_calls_import_time
    ON supervision.phone_calls(import_id, start);

-- Recherche exacte d'indice, déjà présente dans le schéma SQLite historique
-- mais absente du jeu d'index PostgreSQL explicite.
CREATE INDEX IF NOT EXISTS supervision_calls_indice
    ON supervision.phone_calls(indice);

-- Support/Recherche/Priorités : latest_agent_names() utilise DISTINCT ON(agent)
-- ORDER BY agent, import_id DESC, id DESC. C’est le même index déjà présent
-- dans le schéma SQLite historique, mais absent des index PostgreSQL explicites.
CREATE INDEX IF NOT EXISTS supervision_activity_agent_latest
    ON supervision.activities(agent, import_id DESC, id DESC);


-- V60.4: nom/roster borne au dernier import actif. L'ordre exact évite un tri
-- même quand l'import du jour contient plusieurs dizaines de milliers d'activités.
CREATE INDEX IF NOT EXISTS supervision_activity_import_agent_latest
    ON supervision.activities(import_id, agent, id DESC);

-- V60.4: Journal Détails. Le chemin par défaut est SIMPLIFY2/export et filtre
-- par import actif + plage temporelle avant ORDER BY start DESC,id DESC.
-- Les index séparés source_time/import_time/page_order existaient déjà mais
-- PostgreSQL devait encore combiner/trier de très gros ensembles.
CREATE INDEX IF NOT EXISTS details_detail_event_source_import_page
    ON details.detail_events(event_source, source_import_id, start DESC, id DESC);

-- ANI/numéro : le filtre est une recherche de sous-chaîne sur les chiffres
-- normalisés. Un B-tree ne peut pas accélérer LIKE '%...%'. Si pg_trgm est
-- DEJA installé, créer un GIN sur l'expression réellement utilisée. Le script
-- n'installe volontairement pas l'extension.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname='pg_trgm') THEN
    -- Recherche ANI par défaut de l'interface Recherche d'appels.
    EXECUTE $idx$
      CREATE INDEX IF NOT EXISTS supervision_calls_ani_digits_trgm
      ON supervision.phone_calls USING gin
      ((regexp_replace(COALESCE(ani,''),'[^0-9]','','g')) gin_trgm_ops)
    $idx$;
    -- Recherche "tous les champs téléphone" quand elle est explicitement demandée.
    EXECUTE $idx$
      CREATE INDEX IF NOT EXISTS supervision_calls_phone_any_trgm
      ON supervision.phone_calls USING gin
      ((regexp_replace(COALESCE(ani,'')||'|'||COALESCE(dnis,'')||'|'||COALESCE(outtel,'')||'|'||COALESCE(outdialed,''),'[^0-9|]','','g')) gin_trgm_ops)
    $idx$;
  END IF;
END $$;

-- Mettre à jour les statistiques du planificateur après création d'index.
ANALYZE supervision.phone_calls;
ANALYZE supervision.activities;
ANALYZE details.detail_events;
ANALYZE details.detail_event_agents;
