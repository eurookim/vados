import calendar
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

import requests

DB_PATH = os.path.join(os.path.dirname(__file__), "vados.db")

CATEGORIES = [
    "Food", "Transport", "Entertainment", "Shopping",
    "Subscriptions", "Health", "Housing", "Education",
    "Personal", "Income"
]

EXPENSE_CATEGORIES = [c for c in CATEGORIES if c != "Income"]

SUPPORTED_CURRENCIES = {
    "USD": "$", "EUR": "\u20ac", "GBP": "\u00a3", "JPY": "\u00a5",
    "KRW": "\u20a9", "CAD": "C$", "AUD": "A$", "INR": "\u20b9",
}

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


@contextmanager
def _sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _turso_rows(sql, params):
    results = _turso_execute([{"sql": sql, "args": list(params) if params else []}])
    return results[0]["rows"] if results else []


def _execute(sql, params=None):
    """Execute a single write statement."""
    if _use_turso():
        _turso_rows(sql, params)
        return
    with _sqlite() as conn:
        conn.execute(sql, params or ())
        conn.commit()


def _fetchall(sql, params=None):
    """Execute a query and return all rows as list of dicts."""
    if _use_turso():
        return _turso_rows(sql, params)
    with _sqlite() as conn:
        return [dict(r) for r in conn.execute(sql, params or ()).fetchall()]


def _fetchone(sql, params=None):
    """Execute a query and return one row as dict or None."""
    if _use_turso():
        rows = _turso_rows(sql, params)
        return rows[0] if rows else None
    with _sqlite() as conn:
        row = conn.execute(sql, params or ()).fetchone()
        return dict(row) if row else None


def _execute_many(statements):
    """Execute multiple statements in one call."""
    if _use_turso():
        _turso_execute(statements)
        return
    with _sqlite() as conn:
        for stmt in statements:
            conn.execute(stmt["sql"], stmt.get("args", []))
        conn.commit()


# ============================================================
# PUBLIC API
# ============================================================

def _safe_add_column(table, column, col_def):
    """Add a column if it doesn't already exist. Works for both SQLite and Turso."""
    rows = _fetchall(f"PRAGMA table_info({table})")
    existing = {r.get("name") for r in rows}
    if column not in existing:
        _execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")


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
        {"sql": """CREATE TABLE IF NOT EXISTS recurring_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            frequency TEXT NOT NULL CHECK(frequency IN ('weekly', 'biweekly', 'monthly')),
            next_due_date TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""},
    ])
    # Migrate existing tables with new columns
    _safe_add_column("transactions", "currency", "TEXT NOT NULL DEFAULT 'USD'")
    _safe_add_column("user_profile", "default_currency", "TEXT NOT NULL DEFAULT 'USD'")


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


def add_transaction(date_str, txn_type, amount, category, description, source="manual", currency="USD"):
    _execute(
        "INSERT INTO transactions (date, type, amount, category, description, source, currency) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (date_str, txn_type, abs(amount), _require_category(category), description, source, currency),
    )


def update_transaction(txn_id, category=None, description=None, amount=None):
    stmts = []
    if category is not None:
        stmts.append({"sql": "UPDATE transactions SET category = ? WHERE id = ?", "args": [_require_category(category), txn_id]})
    if description is not None:
        stmts.append({"sql": "UPDATE transactions SET description = ? WHERE id = ?", "args": [description, txn_id]})
    if amount is not None:
        stmts.append({"sql": "UPDATE transactions SET amount = ? WHERE id = ?", "args": [abs(amount), txn_id]})
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


def _require_category(category):
    resolved = resolve_category(category)
    if resolved is None:
        raise ValueError(f"Unknown category: {category}")
    return resolved


def get_last_transaction():
    return _fetchone("SELECT * FROM transactions ORDER BY id DESC LIMIT 1")


# ============================================================
# CURRENCY
# ============================================================

def get_default_currency():
    row = _fetchone("SELECT default_currency FROM user_profile WHERE id = 1")
    return row["default_currency"] if row else "USD"


def set_default_currency(currency):
    _execute("UPDATE user_profile SET default_currency = ? WHERE id = 1", (currency,))


def format_currency(amount, currency="USD"):
    symbol = SUPPORTED_CURRENCIES.get(currency, currency + " ")
    if currency == "JPY" or currency == "KRW":
        return f"{symbol}{amount:,.0f}"
    return f"{symbol}{amount:,.2f}"


# ============================================================
# RECURRING TRANSACTIONS
# ============================================================

def add_recurring_transaction(txn_type, amount, category, description, frequency, next_due_date, currency="USD"):
    _execute(
        "INSERT INTO recurring_transactions (type, amount, category, description, currency, frequency, next_due_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (txn_type, abs(amount), _require_category(category), description, currency, frequency, next_due_date),
    )


def get_recurring_transactions(active_only=True):
    if active_only:
        return _fetchall("SELECT * FROM recurring_transactions WHERE active = 1 ORDER BY next_due_date")
    return _fetchall("SELECT * FROM recurring_transactions ORDER BY next_due_date")


def update_recurring_transaction(rec_id, **kwargs):
    stmts = []
    allowed = {"amount", "category", "description", "frequency", "next_due_date", "active", "currency"}
    for key, val in kwargs.items():
        if key not in allowed:
            continue
        if key == "category":
            val = resolve_category(val)
            if val is None:
                continue
        stmts.append({"sql": f"UPDATE recurring_transactions SET {key} = ? WHERE id = ?", "args": [val, rec_id]})
    if stmts:
        _execute_many(stmts)


def delete_recurring_transaction(rec_id):
    _execute("DELETE FROM recurring_transactions WHERE id = ?", (rec_id,))


def _advance_date(date_str, frequency):
    """Calculate the next due date based on frequency."""
    d = date.fromisoformat(date_str)
    if frequency == "weekly":
        return (d + timedelta(days=7)).isoformat()
    elif frequency == "biweekly":
        return (d + timedelta(days=14)).isoformat()
    else:  # monthly
        year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
        day = min(d.day, calendar.monthrange(year, month)[1])
        return date(year, month, day).isoformat()


def process_due_recurring_transactions():
    """Auto-log any recurring transactions that are due. Returns count of logged transactions."""
    due = _fetchall(
        "SELECT * FROM recurring_transactions WHERE active = 1 AND next_due_date <= ?",
        (date.today().isoformat(),),
    )
    count = 0
    for rec in due:
        add_transaction(
            rec["next_due_date"], rec["type"], rec["amount"],
            rec["category"], rec["description"],
            source="recurring", currency=rec.get("currency", "USD"),
        )
        new_date = _advance_date(rec["next_due_date"], rec["frequency"])
        _execute(
            "UPDATE recurring_transactions SET next_due_date = ? WHERE id = ?",
            (new_date, rec["id"]),
        )
        count += 1
    return count


def get_upcoming_recurring(days=30):
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    return _fetchall(
        "SELECT * FROM recurring_transactions WHERE active = 1 AND next_due_date <= ? ORDER BY next_due_date",
        (cutoff,),
    )


# ============================================================
# TRENDS
# ============================================================

def get_monthly_summaries(months=6):
    today = date.today()
    results = []
    for i in range(months):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        results.append({"year": y, "month": m, **get_monthly_summary(y, m)})
    return list(reversed(results))
