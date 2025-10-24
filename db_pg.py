
import os
import json
import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise SystemExit("Missing DATABASE_URL (Neon Postgres) in environment variables")

def db():
    # Autocommit for serverless simplicity
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    conn.autocommit = True
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    # lines
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lines(
        id           BIGSERIAL PRIMARY KEY,
        name         TEXT NOT NULL,
        period_days  INTEGER NOT NULL,
        start_date   DATE NOT NULL,
        legs         INTEGER NOT NULL,
        contrib      BIGINT NOT NULL,
        bid_type     TEXT DEFAULT 'dynamic',
        bid_value    DOUBLE PRECISION DEFAULT 0,
        status       TEXT DEFAULT 'OPEN',
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        base_rate    DOUBLE PRECISION DEFAULT 0,
        cap_rate     DOUBLE PRECISION DEFAULT 100,
        thau_rate    DOUBLE PRECISION DEFAULT 0,
        remind_hour  INTEGER DEFAULT 8,
        remind_min   INTEGER DEFAULT 0,
        last_remind_iso DATE
    );
    """)
    # payments
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments(
        id BIGSERIAL PRIMARY KEY,
        line_id BIGINT NOT NULL REFERENCES lines(id) ON DELETE CASCADE,
        pay_date DATE NOT NULL,
        amount   BIGINT NOT NULL
    );
    """)
    # rounds
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rounds(
        id BIGSERIAL PRIMARY KEY,
        line_id BIGINT NOT NULL REFERENCES lines(id) ON DELETE CASCADE,
        k       INTEGER NOT NULL,
        bid     BIGINT NOT NULL,
        round_date DATE,
        UNIQUE(line_id, k)
    );
    """)
    # configs (key/value JSONB)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS configs(
        key   TEXT PRIMARY KEY,
        value JSONB NOT NULL
    );
    """)
    cur.close()
    conn.close()

def ensure_schema():
    # For now schema is fully created in init_db
    return

def cfg_get(key: str, default=None):
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT value FROM configs WHERE key=%s", (key,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return (row["value"] if row else default)

def cfg_set(key: str, value):
    conn = db()
    cur = conn.cursor()
    cur.execute("INSERT INTO configs(key,value) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
                (key, json.dumps(value, ensure_ascii=False)))
    cur.close(); conn.close()
