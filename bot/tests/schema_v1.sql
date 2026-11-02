-- Схема базы версии 1 (как в первом выпуске бота) — для проверки миграции.
CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts      INTEGER NOT NULL,
    created_at      TEXT    NOT NULL,
    tg_id           INTEGER NOT NULL,
    username        TEXT,
    name            TEXT    NOT NULL,
    contact         TEXT    NOT NULL,
    comment         TEXT,
    calc            TEXT,
    consent_at      TEXT    NOT NULL,
    consent_version TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'new',
    status_ts       INTEGER
);
CREATE INDEX IF NOT EXISTS leads_ts ON leads(created_ts);
CREATE INDEX IF NOT EXISTS leads_tg ON leads(tg_id);

CREATE TABLE IF NOT EXISTS shipments (
    lead_id       INTEGER PRIMARY KEY REFERENCES leads(id) ON DELETE CASCADE,
    items         TEXT NOT NULL,
    address       TEXT NOT NULL,
    when_text     TEXT NOT NULL,
    phone         TEXT NOT NULL,
    created_by    INTEGER,
    created_name  TEXT,
    created_ts    INTEGER NOT NULL,
    accepted_by   INTEGER,
    accepted_name TEXT,
    accepted_ts   INTEGER,
    shipped_by    INTEGER,
    shipped_name  TEXT,
    shipped_ts    INTEGER,
    cancelled_ts  INTEGER
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts  INTEGER NOT NULL,
    created_at  TEXT    NOT NULL,
    tg_id       INTEGER NOT NULL,          -- клиент
    username    TEXT,
    name        TEXT,
    direction   TEXT    NOT NULL,          -- 'in' от клиента, 'out' ответ магазина
    kind        TEXT    NOT NULL DEFAULT 'text',
    text        TEXT,
    admin_id    INTEGER,                   -- кто из команды ответил (для 'out')
    admin_name  TEXT
);
CREATE INDEX IF NOT EXISTS messages_ts ON messages(created_ts);
CREATE INDEX IF NOT EXISTS messages_tg ON messages(tg_id);

-- сообщение в чате сотрудника → клиент, которому уйдёт ответ на него
CREATE TABLE IF NOT EXISTS relay (
    admin_chat_id    INTEGER NOT NULL,
    admin_message_id INTEGER NOT NULL,
    tg_id            INTEGER NOT NULL,
    lead_id          INTEGER,
    created_ts       INTEGER NOT NULL,
    PRIMARY KEY (admin_chat_id, admin_message_id)
);
CREATE INDEX IF NOT EXISTS relay_tg ON relay(tg_id);

CREATE TABLE IF NOT EXISTS team (
    tg_id     INTEGER PRIMARY KEY,
    username  TEXT,
    name      TEXT,
    role      TEXT NOT NULL,               -- 'manager' | 'shipping'
    notify    TEXT NOT NULL,               -- 'all' | 'orders'
    added_at  TEXT NOT NULL,
    added_by  INTEGER
);

CREATE TABLE IF NOT EXISTS invites (
    code_hash  TEXT PRIMARY KEY,
    role       TEXT    NOT NULL,
    created_ts INTEGER NOT NULL,
    expires_ts INTEGER NOT NULL,
    created_by INTEGER,
    used_by    INTEGER,
    used_ts    INTEGER
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
