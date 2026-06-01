import Database from 'better-sqlite3'
import path from 'path'

const DB_PATH = path.join(__dirname, '../../../cache.db')

let db: Database.Database

export function getDb(): Database.Database {
  if (!db) {
    db = new Database(DB_PATH)
    db.pragma('journal_mode = WAL')
    db.pragma('foreign_keys = ON')
    initSchema(db)
  }
  return db
}

function initSchema(db: Database.Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS commits (
      org      TEXT NOT NULL,
      repo     TEXT NOT NULL,
      sha      TEXT NOT NULL,
      date     TEXT NOT NULL,
      author   TEXT NOT NULL,
      message  TEXT NOT NULL,
      additions INTEGER NOT NULL DEFAULT 0,
      deletions INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY (org, repo, sha)
    );

    CREATE TABLE IF NOT EXISTS commit_files (
      org       TEXT NOT NULL,
      repo      TEXT NOT NULL,
      sha       TEXT NOT NULL,
      filename  TEXT NOT NULL,
      additions INTEGER NOT NULL DEFAULT 0,
      deletions INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_cf_repo   ON commit_files(org, repo);
    CREATE INDEX IF NOT EXISTS idx_cf_sha    ON commit_files(org, repo, sha);
    CREATE INDEX IF NOT EXISTS idx_cf_file   ON commit_files(org, repo, filename);

    CREATE TABLE IF NOT EXISTS code_health_cache (
      org         TEXT NOT NULL,
      repo        TEXT NOT NULL,
      hotspots    TEXT NOT NULL,
      cached_at   TEXT NOT NULL,
      PRIMARY KEY (org, repo)
    );

    CREATE TABLE IF NOT EXISTS scan_state (
      org               TEXT NOT NULL,
      repo              TEXT NOT NULL,
      last_scanned_at   TEXT,
      last_commit_sha   TEXT,
      status            TEXT NOT NULL DEFAULT 'idle',
      scanned_commits   INTEGER NOT NULL DEFAULT 0,
      total_commits     INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY (org, repo)
    );
  `)
}
