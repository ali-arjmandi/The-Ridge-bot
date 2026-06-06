import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reservations.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                username  TEXT    NOT NULL,
                location  TEXT    NOT NULL,
                date      TEXT    NOT NULL,
                start_h   INTEGER NOT NULL,
                end_h     INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_res_loc_date
            ON reservations (location, date)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)


# ── read ──────────────────────────────────────────────────────────────────────

def get_booked_hours(location: str, date: str) -> list[tuple[int, int]]:
    """Return list of (start_h, end_h) already booked for location+date."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT start_h, end_h FROM reservations WHERE location=? AND date=?",
            (location, date),
        ).fetchall()
    return [(r["start_h"], r["end_h"]) for r in rows]


def get_user_reservations(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM reservations
               WHERE user_id=? AND date >= date('now','localtime')
               ORDER BY date, start_h""",
            (user_id,),
        ).fetchall()


def get_all_upcoming() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM reservations
               WHERE date >= date('now','localtime')
               ORDER BY date, start_h""",
        ).fetchall()


def get_reservation_by_id(res_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM reservations WHERE id=?", (res_id,)
        ).fetchone()


# ── write ─────────────────────────────────────────────────────────────────────

def create_reservation(
    user_id: int, username: str, location: str, date: str, start_h: int, end_h: int
) -> int:
    """Insert and return new reservation id. Raises ValueError on overlap."""
    booked = get_booked_hours(location, date)
    for s, e in booked:
        if start_h < e and end_h > s:
            raise ValueError("overlap")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO reservations (user_id,username,location,date,start_h,end_h) VALUES (?,?,?,?,?,?)",
            (user_id, username, location, date, start_h, end_h),
        )
    return cur.lastrowid


def get_config(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set_config(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def delete_reservation(res_id: int, user_id: int) -> bool:
    """Delete only if it belongs to user_id. Returns True on success."""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM reservations WHERE id=? AND user_id=?",
            (res_id, user_id),
        )
    return cur.rowcount == 1
