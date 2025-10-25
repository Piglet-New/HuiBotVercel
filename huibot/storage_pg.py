import os, psycopg2

class _DB:
    def url(self):
        return os.getenv("DATABASE_URL","")

db = _DB()

def run_sql_file(conn_url: str, path: str):
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    with psycopg2.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
