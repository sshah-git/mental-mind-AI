CREATE TABLE users (
    id TEXT PRIMARY KEY,              -- UUID
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,               -- or NULL if magic-link auth
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE journal_entries (
    id TEXT PRIMARY KEY,               -- UUID
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,             -- the raw journal text
    energy_level INTEGER,              -- optional: 1–5
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE entry_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL,
    tag TEXT NOT NULL,                 -- e.g. "anxiety", "overwhelm"
    source TEXT NOT NULL CHECK(source IN ('user', 'ai')),

   FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE
);

CREATE TABLE ai_reflections (
    id TEXT PRIMARY KEY,               -- UUID
    entry_id TEXT NOT NULL,
    reflection_text TEXT NOT NULL,
    user_feedback TEXT CHECK (
        user_feedback IN ('helpful', 'not_quite', 'unhelpful')
    ),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

   FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE
);

CREATE TABLE detected_patterns (
    id TEXT PRIMARY KEY,               -- UUID
    user_id TEXT NOT NULL,
    pattern_type TEXT NOT NULL,        -- e.g. "low_energy", "self_criticism"
    pattern_summary TEXT NOT NULL,     -- human-readable insight
    occurrence_count INTEGER DEFAULT 1,
    last_detected DATETIME DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- will be used later for tasks added by users
CREATE TABLE micro_tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    task_text TEXT NOT NULL,
    energy_required INTEGER,
    status TEXT CHECK(status IN ('pending', 'done', 'skipped')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
