from typing import Optional
from psycopg2.extras import RealDictCursor
import psycopg2

def create_group(conn_url: str, code: str, name: str, owner_tg_id: int, cycles: int, stake_amount: float):
    with psycopg2.connect(conn_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "insert into hui_group(code,name,owner_tg_id,cycle_total,stake_amount)"
                " values(%s,%s,%s,%s,%s) returning id",
                (code, name, owner_tg_id, cycles, stake_amount)
            )
            gid = cur.fetchone()["id"]
            cur.execute("insert into hui_cycle(group_id, index) values(%s,%s)", (gid, 1))
            return gid

def join_group(conn_url: str, group_code: str, tg_id: int, username: Optional[str], display_name: Optional[str]):
    with psycopg2.connect(conn_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "insert into hui_user(tg_id,tg_username,display_name) values(%s,%s,%s)"
                " on conflict (tg_id) do update set tg_username=excluded.tg_username,"
                " display_name=excluded.display_name returning id",
                (tg_id, username, display_name)
            )
            uid = cur.fetchone()["id"]
            cur.execute("select id from hui_group where code=%s", (group_code,))
            row = cur.fetchone()
            if not row:
                raise ValueError("Group not found")
            gid = row["id"]
            cur.execute(
                "insert into hui_membership(group_id,user_id) values(%s,%s) on conflict do nothing",
                (gid, uid)
            )
            return gid, uid
