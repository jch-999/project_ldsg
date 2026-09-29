CREATE TABLE IF NOT EXISTS materials (
    id                 TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    description        TEXT,
    course_code        TEXT,
    course_name        TEXT,
    category           TEXT,
    semester           TEXT,
    tags               TEXT,
    file_key           TEXT NOT NULL,
    file_name          TEXT NOT NULL,
    original_name      TEXT,
    file_size          INTEGER,
    mime_type          TEXT,
    sha256             TEXT,
    uploader_note      TEXT,
    upload_credential  TEXT,
    status             TEXT NOT NULL DEFAULT 'pending',
    review_note        TEXT,
    reviewed_at        TEXT,
    reviewer           TEXT,
    downloads          INTEGER NOT NULL DEFAULT 0,
    views              INTEGER NOT NULL DEFAULT 0,
    ip_hmac            TEXT,
    intercept_flag     TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS material_sources (
    material_id  TEXT,
    provider     TEXT,
    object_key   TEXT,
    size         INTEGER,
    sha256       TEXT,
    priority     INTEGER
);

CREATE TABLE IF NOT EXISTS credentials (
    credential     TEXT PRIMARY KEY,
    approved_count INTEGER NOT NULL DEFAULT 0,
    level          INTEGER NOT NULL DEFAULT 0,
    first_seen     TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    id           TEXT PRIMARY KEY,
    material_id  TEXT NOT NULL,
    reason       TEXT,
    detail       TEXT,
    ip_hmac      TEXT,
    status       TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS upload_events (
    ip_hmac     TEXT,
    credential  TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           TEXT PRIMARY KEY,
    material_id  TEXT,
    action       TEXT,
    reason       TEXT,
    actor        TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intercept_log (
    id           TEXT PRIMARY KEY,
    action       TEXT NOT NULL,
    rule         TEXT,
    filename     TEXT,
    course_code  TEXT,
    byte_size    INTEGER,
    sha256       TEXT,
    ip_hmac      TEXT,
    credential   TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_materials_status_created
    ON materials (status, created_at);
CREATE INDEX IF NOT EXISTS idx_materials_sha256
    ON materials (sha256);
CREATE INDEX IF NOT EXISTS idx_reports_material
    ON reports (material_id, status);
CREATE INDEX IF NOT EXISTS idx_intercept_created
    ON intercept_log(created_at);
