CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY, tenant TEXT NOT NULL, department TEXT NOT NULL,
  admin INTEGER NOT NULL DEFAULT 0, actor_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships (
  group_id TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(user_id),
  PRIMARY KEY (group_id, user_id)
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, tenant TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
  visibility TEXT NOT NULL, group_id TEXT, owner TEXT NOT NULL REFERENCES users(user_id),
  version INTEGER NOT NULL, source_version TEXT NOT NULL, synced_version TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0, acl_known INTEGER NOT NULL DEFAULT 1,
  source_path TEXT
);
CREATE TABLE IF NOT EXISTS grants (
  document_id TEXT NOT NULL REFERENCES documents(id), user_id TEXT NOT NULL REFERENCES users(user_id),
  PRIMARY KEY(document_id, user_id)
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id),
  question TEXT NOT NULL, refs TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audits (
  id TEXT PRIMARY KEY, correlation_id TEXT NOT NULL, actor_hash TEXT NOT NULL,
  actor_type TEXT NOT NULL, action TEXT NOT NULL, outcome TEXT NOT NULL,
  policy_version TEXT NOT NULL, source_version TEXT, created_at TEXT NOT NULL
);
INSERT INTO schema_migrations(version) SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version=1);
