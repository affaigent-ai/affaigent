BEGIN;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS identities (
  identity_key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('work','private','shared')),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO identities (identity_key, display_name, kind)
VALUES
  ('dennis_work', 'Dennis Work', 'work'),
  ('linsey_work', 'Linsey Work', 'work'),
  ('shared_private', 'Shared Private', 'shared')
ON CONFLICT (identity_key) DO UPDATE
SET
  display_name = EXCLUDED.display_name,
  kind = EXCLUDED.kind;

CREATE TABLE IF NOT EXISTS connectors (
  connector_id BIGSERIAL PRIMARY KEY,
  connector_key TEXT NOT NULL UNIQUE,
  identity_key TEXT NOT NULL REFERENCES identities(identity_key) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  account_label TEXT NOT NULL,
  scope_kind TEXT NOT NULL CHECK (scope_kind IN ('work','private','shared')),
  status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','active','disabled','error')),
  secret_ref TEXT,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_connectors_identity_key ON connectors (identity_key);
CREATE INDEX IF NOT EXISTS idx_connectors_provider ON connectors (provider);
CREATE INDEX IF NOT EXISTS idx_connectors_status ON connectors (status);
CREATE INDEX IF NOT EXISTS idx_connectors_config_gin ON connectors USING GIN (config);

DROP TRIGGER IF EXISTS trg_connectors_updated_at ON connectors;
CREATE TRIGGER trg_connectors_updated_at
BEFORE UPDATE ON connectors
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS memory_entries (
  memory_id TEXT PRIMARY KEY,
  identity_key TEXT NOT NULL REFERENCES identities(identity_key) ON DELETE RESTRICT,
  connector_id BIGINT REFERENCES connectors(connector_id) ON DELETE SET NULL,
  memory_type TEXT NOT NULL CHECK (
    memory_type IN (
      'profile',
      'preference',
      'task_context',
      'fact',
      'entity_note',
      'document_note',
      'policy',
      'conversation_note',
      'system_note'
    )
  ),
  title TEXT,
  content TEXT NOT NULL,
  summary TEXT,
  source_kind TEXT NOT NULL CHECK (
    source_kind IN (
      'manual',
      'conversation',
      'gmail',
      'calendar',
      'drive',
      'docs',
      'sheets',
      'browser',
      'system'
    )
  ),
  source_ref TEXT,
  source_event_at TIMESTAMPTZ,
  importance SMALLINT NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
  sensitivity TEXT NOT NULL DEFAULT 'normal' CHECK (sensitivity IN ('low','normal','high')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded','archived','deleted')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_accessed_at TIMESTAMPTZ,
  archived_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_memory_entries_identity_key ON memory_entries (identity_key);
CREATE INDEX IF NOT EXISTS idx_memory_entries_connector_id ON memory_entries (connector_id);
CREATE INDEX IF NOT EXISTS idx_memory_entries_memory_type ON memory_entries (memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_entries_source_kind ON memory_entries (source_kind);
CREATE INDEX IF NOT EXISTS idx_memory_entries_status ON memory_entries (status);
CREATE INDEX IF NOT EXISTS idx_memory_entries_source_event_at ON memory_entries (source_event_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_entries_created_at ON memory_entries (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_entries_metadata_gin ON memory_entries USING GIN (metadata);

DROP TRIGGER IF EXISTS trg_memory_entries_updated_at ON memory_entries;
CREATE TRIGGER trg_memory_entries_updated_at
BEFORE UPDATE ON memory_entries
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS memory_chunks (
  chunk_id TEXT PRIMARY KEY,
  memory_id TEXT NOT NULL REFERENCES memory_entries(memory_id) ON DELETE CASCADE,
  identity_key TEXT NOT NULL REFERENCES identities(identity_key) ON DELETE RESTRICT,
  connector_id BIGINT REFERENCES connectors(connector_id) ON DELETE SET NULL,
  chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
  chunk_text TEXT NOT NULL,
  embedding_status TEXT NOT NULL DEFAULT 'pending' CHECK (embedding_status IN ('pending','embedded','error')),
  qdrant_point_id TEXT UNIQUE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (memory_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_memory_chunks_memory_id ON memory_chunks (memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_identity_key ON memory_chunks (identity_key);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_connector_id ON memory_chunks (connector_id);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_embedding_status ON memory_chunks (embedding_status);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_created_at ON memory_chunks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_metadata_gin ON memory_chunks USING GIN (metadata);

DROP TRIGGER IF EXISTS trg_memory_chunks_updated_at ON memory_chunks;
CREATE TRIGGER trg_memory_chunks_updated_at
BEFORE UPDATE ON memory_chunks
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS memory_links (
  from_memory_id TEXT NOT NULL REFERENCES memory_entries(memory_id) ON DELETE CASCADE,
  to_memory_id TEXT NOT NULL REFERENCES memory_entries(memory_id) ON DELETE CASCADE,
  relation_type TEXT NOT NULL CHECK (
    relation_type IN (
      'relates_to',
      'supersedes',
      'derived_from',
      'same_subject',
      'depends_on'
    )
  ),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (from_memory_id, to_memory_id, relation_type),
  CHECK (from_memory_id <> to_memory_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_links_to_memory_id ON memory_links (to_memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_links_relation_type ON memory_links (relation_type);
CREATE INDEX IF NOT EXISTS idx_memory_links_metadata_gin ON memory_links USING GIN (metadata);

COMMIT;
