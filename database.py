import os
import sqlite3
from datetime import date

try:
    import libsql_experimental as libsql
    HAS_LIBSQL = True
except ImportError:
    HAS_LIBSQL = False

DB_PATH = os.path.join(os.path.dirname(__file__), "vados.db")

CATEGORIES = [
    "Food", "Transport", "Entertainment", "Shopping",
    "Subscriptions", "Health", "Housing", "Education",
    "Personal", "Income"
]

EXPENSE_CATEGORIES = [c for c in CATEGORIES if c != "Income"]

CATEGORY_SYNONYMS = {
    "dining": "Food",
    "restaurants": "Food",
    "groceries": "Food",
    "gym": "Health",
    "rent": "Housing",
    "utilities": "Housing",
    "uber": "Transport",
    "lyft": "Transport",
    "gas": "Transport",
    "clothes": "Shopping",
    "gifts": "Personal",
    "tuition": "Education",
    "salary": "Income",
}


def _get_turso_config():
    """Check for Turso credentials in env vars or Streamlit secrets."""
    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    if url and token:
        return url, token
    try:
        import streamlit as st
        url = st.secrets.get("TURSO_DATABASE_URL")
        token = st.secrets.get("TURSO_AUTH_TOKEN")
        if url and token:
            return url, token
    except Exception:
        pass
    return None, None


def get_connection():
    url, token = _get_turso_config()
    if url and token and HAS_LIBSQL:
        conn = libsql.connect("vados.db", sync_url=url, auth_token=token)
        conn.sync()
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


def _dict_row(row, description):
    """Convert a row tuple to a dict using cursor description."""
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        return dict(row)
    return {description[i][0]: row[i] for i in range(len(description))}


def _execute_and_commit(sql, params=None):
    conn = get_connection()
    try:
        if params:
            conn.execute(sql, params)
        else:
            conn.execute(sql)
        conn.commit()
        _try_sync(conn)
    finally:
        conn.close()


def _fetchall(sql, params=None):
    conn = get_connection()
    try:
        cur = conn.execute(sql, params) if params else conn.execute(sql)
        rows = cur.fetchall()
        desc = cur.description
        return [_dict_row(r, desc) for r in rows]
    finally:
        conn.close()


def _fetchone(sql, params=None):
    conn = get_connection()
    try:
        cur = conn.execute(sql, params) if params else conn.execute(sql)
        row = cur.fetchone()
        if row is None:
            return None
        return _dict_row(row, cur.description)
    finally:
        conn.close()


def _try_sync(conn):
    """Sync to Turso remote if using libsql."""
    if hasattr(conn, "sync"):
        try:
            conn.sync()
        except Exception:
            pass


def init_db():
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                goals TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_insight_at TEXT,
                onboarding_complete INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS budget_targets (
                category TEXT PRIMARY KEY,
                monthly_limit REAL NOT NULL
            )
        """)
        conn.commit()
        _try_sync(conn)
    finally:
        conn.close()


def get_or_create_profile():
    row = _fetchone("SELECT * FROM user_profile WHERE id = 1")
    if not row:
        _execute_and_commit(
            "INSERT INTO user_profile (id, goals, onboarding_complete) VALUES (1, '', 0)"
        )
        row = _fetchone("SELECT * FROM user_profile WHERE id = 1")
    return row


def update_profile(goals=None, onboarding_complete=None, last_insight_at=None):
    conn = get_connection()
    try:
        if goals is not None:
            conn.execute("UPDATE user_profile SET goals = ? WHERE id = 1", (goals,))
        if onboarding_complete is not None:
            conn.execute(
                "UPDATE user_profile SET onboarding_complete = ? WHERE id = 1",
                (onboarding_complete,),
            )
        if last_insight_at is not None:
            conn.execute(
                "UPDATE user_profile SET last_insight_at = ? WHERE id = 1",
                (last_insight_at,),
            )
        conn.commit()
        _try_sync(conn)
    finally:
        conn.close()


def add_transaction(date_str, txn_type, amount, category, description, source="manual"):
    resolved = resolve_category(category)
    if resolved is None:
        raise ValueError(f"Unknown category: {category}")
    _execute_and_commit(
        "INSERT INTO transactions (date, type, amount, category, description, source) VALUES (?, ?, ?, ?, ?, ?)",
        (date_str, txn_type, abs(amount), resolved, description, source),
    )


def update_transaction(txn_id, category=None, description=None):
    conn = get_connection()
    try:
        if category is not None:
            resolved = resolve_category(category)
            if resolved is None:
                raise ValueError(f"Unknown category: {category}")
            conn.execute(
                "UPDATE transactions SET category = ? WHERE id = ?", (resolved, txn_id)
            )
        if description is not None:
            conn.execute(
                "UPDATE transactions SET description = ? WHERE id = ?",
                (description, txn_id),
            )
        conn.commit()
        _try_sync(conn)
    finally:
        conn.close()


def delete_transaction(txn_id):
    _execute_and_commit("DELETE FROM transactions WHERE id = ?", (txn_id,))


def get_all_transactions():
    return _fetchall("SELECT * FROM transactions ORDER BY date DESC, id DESC")


def get_monthly_transactions(year=None, month=None):
    if year is None or month is None:
        today = date.today()
        year, month = today.year, today.month
    start = f"{year}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{month + 1:02d}-01"
    return _fetchall(
        "SELECT * FROM transactions WHERE date >= ? AND date < ? ORDER BY date DESC, id DESC",
        (start, end),
    )


def get_recent_transactions(limit=15):
    return _fetchall(
        "SELECT * FROM transactions ORDER BY date DESC, id DESC LIMIT ?", (limit,)
    )


def get_monthly_summary(year=None, month=None):
    txns = get_monthly_transactions(year, month)
    total_income = sum(t["amount"] for t in txns if t["type"] == "income")
    total_expenses = sum(t["amount"] for t in txns if t["type"] == "expense")
    net = total_income - total_expenses

    by_category = {}
    for t in txns:
        if t["type"] == "expense":
            by_category[t["category"]] = by_category.get(t["category"], 0) + t["amount"]

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_balance": net,
        "savings_rate": (net / total_income * 100) if total_income > 0 else 0,
        "by_category": by_category,
    }


def set_budget_target(category, monthly_limit):
    _execute_and_commit(
        "INSERT OR REPLACE INTO budget_targets (category, monthly_limit) VALUES (?, ?)",
        (category, monthly_limit),
    )


def remove_budget_target(category):
    _execute_and_commit("DELETE FROM budget_targets WHERE category = ?", (category,))


def get_budget_targets():
    rows = _fetchall("SELECT * FROM budget_targets")
    return {r["category"]: r["monthly_limit"] for r in rows}


def resolve_category(category):
    if not category:
        return None
    if category in CATEGORIES:
        return category
    lower = category.lower().strip()
    for cat in CATEGORIES:
        if cat.lower() == lower:
            return cat
    if lower in CATEGORY_SYNONYMS:
        return CATEGORY_SYNONYMS[lower]
    return None


def get_last_transaction():
    return _fetchone("SELECT * FROM transactions ORDER BY id DESC LIMIT 1")
