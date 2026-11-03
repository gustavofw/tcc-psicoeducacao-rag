-- Busca por palavra sem diferenciar acento ("triade" = "tríade")
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
  AS $$ SELECT public.unaccent('public.unaccent', $1) $$;
DROP INDEX IF EXISTS chunks_busca_gin;
ALTER TABLE chunks DROP COLUMN IF EXISTS busca;
ALTER TABLE chunks ADD COLUMN busca tsvector
  GENERATED ALWAYS AS (to_tsvector('portuguese', f_unaccent(conteudo))) STORED;
CREATE INDEX chunks_busca_gin ON chunks USING gin (busca);
SELECT count(*) AS com_triade FROM chunks
  WHERE busca @@ plainto_tsquery('portuguese', f_unaccent('triade cognitiva'));
