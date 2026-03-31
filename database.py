import os
import sqlite3
from datetime import date

import requests

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


# ============================================================
# CONNECTION LAYER — Turso HTTP API or local SQLite
# ============================================================

def _get_turso_config():
    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    if url and token:
        return url.replace("libsql://", "https://"), token
    try:
        import streamlit as st
        url = st.secrets.get("TURSO_DATABASE_URL", "")
        token = st.secrets.get("TURSO_AUTH_TOKEN", "")
        if url and token:
            return url.replace("libsql://", "https://"), token
    except Exception:
        pass
    return None, None


def _use_turso():
    url, token = _get_turso_config()
    return url is not None and token is not None


def _turso_execute(statements):
    """Execute a list of SQL statements via Turso HTTP pipeline API.
    Each statement is a dict: {"sql": "...", "args": [...]}
    Returns list of results, each with 'cols' and 'rows'.
    """
    url, token = _get_turso_config()
    reqs = []
    for stmt in statements:
        args = []
        for a in stmt.get("args", []):
            if a is None:
                args.append({"type": "null"})
            elif isinstance(a, int):
                args.append({"type": "integer", "value": str(a)})
            elif isinstance(a, float):
                args.append({"type": "float", "value": a})
            elif isinstance(a, str):
                args.append({"type": "text", "value": a})
            else:
                args.append({"type": "text", "value": str(a)})
        reqs.append({
            "type": "execute",
            "stmt": {"sql": stmt["sql"], "args": args}
        })
    reqs.append({"type": "close"})

    resp = requests.post(
        f"{url}/v2/pipeline",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"requests": reqs},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for r in data.get("results", []):
        if r.get("type") == "ok" and r.get("response", {}).get("type") == "execute":
            result = r["response"]["result"]
            cols = [c["name"] for c in result.get("cols", [])]
            rows = []
            for raw_row in result.get("rows", []):
                row = {}
                for i, cell in enumerate(raw_row):
                    val = cell.get("value")
                    if cell.get("type") == "integer" and val is not None:
                        val = int(val)
                    elif cell.get("type") == "float" and val is not None:
                        val = float(val)
                    elif cell.get("type") == "null":
                        val = None
                    row[cols[i]] = val
                rows.append(row)
            results.append({"cols": cols, "rows": rows, "last_insert_rowid": result.get("last_insert_rowid")})
        elif r.get("type") == "error":
            raise RuntimeError(f"Turso error: {r.get('error', {}).get('message', 'unknown')}")
    return results


def _execute(sql, params=None):
    """Execute a single write statement."""
    if _use_turso():
        _turso_execute([{"sql": sql, "args": list(params) if params else []}])
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(sql, params or ())
            conn.commit()
        finally:
            conn.close()


def _fetchall(sql, params=None):
    """Execute a query and return all rows as list of dicts."""
    if _use_turso():
        results = _turso_execute([{"sql": sql, "args": list(params) if params else []}])
        return results[0]["rows"] if results else []
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params or ()).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def _fetchone(sql, params=None):
    """Execute a query and return one row as dict or None."""
    if _use_turso():
        results = _turso_execute([{"sql": sql, "args": list(params) if params else []}])
        rows = results[0]["rows"] if results else []
        return rows[0] if rows else None
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(sql, params or ()).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def _execute_many(statements):
    """Execute multiple statements in one call."""
    if _use_turso():
        _turso_execute(statements)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            for stmt in statements:
                conn.execute(stmt["sql"], stmt.get("args", []))
            conn.commit()
        finally:
            conn.close()


# ============================================================
# PUBLIC API
# ============================================================

def init_db():
    _execute_many([
        {"sql": """CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""},
        {"sql": """CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            goals TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_insight_at TEXT,
            onboarding_complete INTEGER NOT NULL DEFAULT 0
        )"""},
        {"sql": """CREATE TABLE IF NOT EXISTS budget_targets (
            category TEXT PRIMARY KEY,
            monthly_limit REAL NOT NULL
        )"""},
    ])


def get_or_create_profile():
    row = _fetchone("SELECT * FROM user_profile WHERE id = 1")
    if not row:
        _execute(
            "INSERT INTO user_profile (id, goals, onboarding_complete) VALUES (1, '', 0)"
        )
        row = _fetchone("SELECT * FROM user_profile WHERE id = 1")
    return row


def update_profile(goals=None, onboarding_complete=None, last_insight_at=None):
    stmts = []
    if goals is not None:
        stmts.append({"sql": "UPDATE user_profile SET goals = ? WHERE id = 1", "args": [goals]})
    if onboarding_complete is not None:
        stmts.append({"sql": "UPDATE user_profile SET onboarding_complete = ? WHERE id = 1", "args": [onboarding_complete]})
    if last_insight_at is not None:
        stmts.append({"sql": "UPDATE user_profile SET last_insight_at = ? WHERE id = 1", "args": [last_insight_at]})
    if stmts:
        _execute_many(stmts)


def add_transaction(date_str, txn_type, amount, category, description, source="manual"):
    resolved = resolve_category(category)
    if resolved is None:
        raise ValueError(f"Unknown category: {category}")
    _execute(
        "INSERT INTO transactions (date, type, amount, category, description, source) VALUES (?, ?, ?, ?, ?, ?)",
        (date_str, txn_type, abs(amount), resolved, description, source),
    )


def update_transaction(txn_id, category=None, description=None):
    stmts = []
    if category is not None:
        resolved = resolve_category(category)
        if resolved is None:
            raise ValueError(f"Unknown category: {category}")
        stmts.append({"sql": "UPDATE transactions SET category = ? WHERE id = ?", "args": [resolved, txn_id]})
    if description is not None:
        stmts.append({"sql": "UPDATE transactions SET description = ? WHERE id = ?", "args": [description, txn_id]})
    if stmts:
        _execute_many(stmts)


def delete_transaction(txn_id):
    _execute("DELETE FROM transactions WHERE id = ?", (txn_id,))


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
    _execute(
        "INSERT OR REPLACE INTO budget_targets (category, monthly_limit) VALUES (?, ?)",
        (category, monthly_limit),
    )


def remove_budget_target(category):
    _execute("DELETE FROM budget_targets WHERE category = ?", (category,))


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
