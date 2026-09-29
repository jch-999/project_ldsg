"""
数据库模块
==========

只用 Python 标准库 sqlite3。
表结构严格按交底书给出的 schema，不改字段名、不增删字段。

为什么每次请求都新开一个连接？
因为 http.server 是多线程的，而 sqlite3 的连接默认不能跨线程使用。
每次请求开一个连接最简单、最不容易出错，对本地小站来说速度完全够。
"""

import sqlite3


# 交底书里的建表语句，原样使用。
SCHEMA = """
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

CREATE INDEX IF NOT EXISTS idx_materials_status_created
    ON materials (status, created_at);
CREATE INDEX IF NOT EXISTS idx_materials_sha256
    ON materials (sha256);
CREATE INDEX IF NOT EXISTS idx_reports_material
    ON reports (material_id, status);
"""


def get_conn(db_path):
    """打开一个数据库连接，并把查询结果设置成能按列名取值。"""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path):
    """建表（如果已经存在就跳过）。程序每次启动都会调用一次。"""
    conn = get_conn(db_path)
    try:
        # WAL 模式让多个线程同时读写时更顺畅（http.server 是多线程的）
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
