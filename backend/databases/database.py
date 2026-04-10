import sqlite3


def get_db():
    conn = sqlite3.connect("mental_companion.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables and run idempotent column migrations. Safe on every startup."""
    conn   = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            name          TEXT,
            password_hash TEXT,
            tier          TEXT DEFAULT 'free',
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS journal_entries (
            id            TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            content       TEXT NOT NULL,
            energy_level  INTEGER,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS entry_tags (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id   TEXT NOT NULL,
            tag        TEXT NOT NULL,
            source     TEXT NOT NULL CHECK(source IN ('user','ai')),
            is_private INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS ai_reflections (
            id              TEXT PRIMARY KEY,
            entry_id        TEXT NOT NULL,
            reflection_text TEXT NOT NULL,
            user_feedback   TEXT CHECK(user_feedback IN ('helpful','not_quite','unhelpful')),
            template_id     TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS detected_patterns (
            id               TEXT PRIMARY KEY,
            user_id          TEXT NOT NULL,
            pattern_type     TEXT NOT NULL,
            pattern_summary  TEXT NOT NULL,
            occurrence_count INTEGER DEFAULT 1,
            last_detected    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS micro_tasks (
            id               TEXT PRIMARY KEY,
            user_id          TEXT NOT NULL,
            task_text        TEXT NOT NULL,
            energy_required  INTEGER,
            status           TEXT DEFAULT 'pending' CHECK(status IN ('pending','done','skipped')),
            created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id              TEXT PRIMARY KEY,
            tone_preference      TEXT DEFAULT 'gentle',
            trigger_words        TEXT DEFAULT '[]',
            user_values          TEXT,
            goals                TEXT,
            goals_for_journaling TEXT,
            reminder_enabled     INTEGER DEFAULT 0,
            reminder_time        TEXT,
            onboarding_complete  INTEGER DEFAULT 0,
            created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Idempotent column additions for existing DBs
    for migration in [
        "ALTER TABLE users ADD COLUMN name TEXT",
        "ALTER TABLE users ADD COLUMN tier TEXT DEFAULT 'free'",
        "ALTER TABLE entry_tags ADD COLUMN is_private INTEGER DEFAULT 0",
        "ALTER TABLE ai_reflections ADD COLUMN template_id TEXT",
    ]:
        try:
            cursor.execute(migration)
        except Exception:
            pass  # column already exists

    conn.commit()
    conn.close()
