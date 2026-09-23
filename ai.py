import json
import os
import re
from datetime import date

from dotenv import load_dotenv

# Load .env BEFORE importing anthropic so the key is in os.environ
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

import anthropic

from database import (
    CATEGORIES,
    SUPPORTED_CURRENCIES,
    get_monthly_summary,
    get_recent_transactions,
    get_budget_targets,
    get_or_create_profile,
    get_default_currency,
    get_upcoming_recurring,
    format_currency,
    resolve_category,
)

MODEL = "claude-sonnet-5"
_client = None


def _get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key and key != "your-api-key-here":
        return key
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return None


def get_client():
    global _client
    if _client is None:
        key = _get_api_key()
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Add your key to .env (local) or Streamlit secrets (cloud)."
            )
        _client = anthropic.Anthropic(api_key=key)
    return _client

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _extract_text(response):
    """Return the concatenated text content of a Messages API response.
    Models with extended thinking enabled prepend non-text blocks (e.g.
    ThinkingBlock), so content[0] is not reliably the text block."""
    return "".join(
        block.text for block in response.content if block.type == "text"
    )


def build_spending_context():
    summary = get_monthly_summary()
    recent = get_recent_transactions(15)
    targets = get_budget_targets()
    profile = get_or_create_profile()
    default_currency = get_default_currency()

    today = date.today()
    month_name = today.strftime("%B %Y")

    lines = [f"=== FINANCIAL CONTEXT FOR {month_name} ==="]
    lines.append(f"Today's date: {today.isoformat()}")
    lines.append(f"Default currency: {default_currency}")
    lines.append(f"Total income this month: {format_currency(summary['total_income'], default_currency)}")
    lines.append(f"Total expenses this month: {format_currency(summary['total_expenses'], default_currency)}")
    lines.append(f"Net balance: {format_currency(summary['net_balance'], default_currency)}")
    lines.append(f"Savings rate: {summary['savings_rate']:.1f}%")

    if summary["by_category"]:
        lines.append("\nSpending by category this month:")
        for cat, amt in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
            budget_str = ""
            if cat in targets:
                pct = amt / targets[cat] * 100
                budget_str = f" (budget: {format_currency(targets[cat], default_currency)}, used: {pct:.0f}%)"
            lines.append(f"  {cat}: {format_currency(amt, default_currency)}{budget_str}")

    if targets:
        lines.append("\nBudget targets:")
        for cat, limit in targets.items():
            spent = summary["by_category"].get(cat, 0)
            lines.append(f"  {cat}: {format_currency(spent, default_currency)} / {format_currency(limit, default_currency)}")

    if recent:
        lines.append("\nMost recent transactions (up to 15):")
        for t in recent:
            sign = "+" if t["type"] == "income" else "-"
            cur = t.get("currency", default_currency)
            lines.append(
                f"  [{t['date']}] {sign}{format_currency(t['amount'], cur)} — {t['category']}: {t['description']}"
            )

    upcoming = get_upcoming_recurring(14)
    if upcoming:
        lines.append("\nUpcoming recurring transactions (next 14 days):")
        for r in upcoming:
            cur = r.get("currency", default_currency)
            lines.append(
                f"  {r['description']}: {format_currency(r['amount'], cur)} ({r['frequency']}, due {r['next_due_date']})"
            )

    if profile.get("goals"):
        lines.append(f"\nUser's financial goals: {profile['goals']}")

    return "\n".join(lines)


SYSTEM_PROMPT = """You are Vados, an AI-powered personal finance assistant. You handle two types of user messages through a single conversation:

1. TRANSACTION LOGGING: If the user's message describes spending, earning, or transferring money (contains amounts, action verbs like "spent", "paid", "bought", "earned", "got paid", etc.), parse it as a transaction.

2. FINANCIAL Q&A: If the user asks a question about their finances, spending patterns, budget, or asks for advice, answer using the financial context provided below.

3. AMBIGUOUS: If you cannot tell whether the message is a transaction or a question, ask: "Did you want to log that as a transaction, or are you asking about your spending?"

IMPORTANT: A transaction message MUST include an amount. If the message mentions spending/earning/an item but gives no number (e.g. "coffee", "restaurant", "thinking about groceries"), do NOT guess or invent an amount — treat it as AMBIGUOUS and ask for the amount instead.

FOR TRANSACTIONS:
When you identify a transaction, respond with ONLY a JSON block in this exact format (no other text):
```json
{
  "intent": "transaction",
  "transactions": [
    {
      "type": "income" or "expense",
      "amount": <number, positive, no currency symbol>,
      "category": "<one of: {categories}>",
      "description": "<short clean label>",
      "date": "<YYYY-MM-DD, default to today if not specified>",
      "currency": "<3-letter currency code, default to user's default currency if not specified>"
    }
  ],
  "confirmation_message": "<friendly message summarizing what you parsed, asking the user to confirm>"
}
```

If the user mentions multiple transactions in one message, include all of them in the transactions array.

IMPORTANT date handling: Today's date is provided in the context. Resolve relative dates like "yesterday", "last Friday", "two days ago" into absolute YYYY-MM-DD dates.

IMPORTANT category rules:
- Use ONLY these categories: {categories}
- For income transactions, always use category "Income" and type "income"
- Pick the single best-fit category

IMPORTANT currency rules:
- The user's default currency is provided in the context. Use it unless the user specifies otherwise.
- Supported currencies: {currencies}
- If the user mentions a currency symbol or code (e.g. "50 euros", "£30", "¥5000"), use the appropriate currency code.

FOR Q&A:
Answer naturally and conversationally. Ground your answers in the financial data provided below. Reference specific numbers. If the user asks about something not in the data, say so honestly.

FOR CORRECTIONS:
If the user says something like "change that to entertainment" or "that should be X category", respond with:
```json
{
  "intent": "correction",
  "category": "<new category>",
  "description": "<new description if mentioned, otherwise null>",
  "confirmation_message": "<confirmation of the change>"
}
```

FINANCIAL CONTEXT:
{context}
""".replace("{categories}", ", ".join(CATEGORIES)).replace("{currencies}", ", ".join(SUPPORTED_CURRENCIES))


def chat(user_message, conversation_history, pending_transaction=None):
    context = build_spending_context()
    system = SYSTEM_PROMPT.replace("{context}", context)

    messages = list(conversation_history)
    messages.append({"role": "user", "content": user_message})

    if pending_transaction:
        system += (
            f"\n\nPENDING TRANSACTION AWAITING CONFIRMATION:\n"
            f"{json.dumps(pending_transaction)}\n"
            f"If the user confirms (yes, yep, sure, correct, looks good, etc.), respond with:\n"
            f"```json\n{{\"intent\": \"confirmed\"}}\n```\n"
            f"If the user says no, cancel, or wants to discard, respond with:\n"
            f"```json\n{{\"intent\": \"cancelled\"}}\n```\n"
            f"If the user wants changes, handle the correction."
        )

    response = get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=messages,
    )

    return _extract_text(response)


def parse_ai_response(response_text):
    # Try fenced JSON block first
    json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try entire response as JSON
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    # Non-greedy fallback: match the first balanced-looking JSON object
    json_match = re.search(r"\{.*?\}", response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def is_valid_date(date_str):
    if not DATE_REGEX.match(date_str):
        return False
    try:
        parts = date_str.split("-")
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        date(year, month, day)
        return True
    except (ValueError, IndexError):
        return False


def validate_transaction(txn):
    if txn.get("type") not in ("income", "expense"):
        return False, "Invalid transaction type"
    if not isinstance(txn.get("amount"), (int, float)) or txn["amount"] <= 0:
        return False, "Invalid amount"
    cat = resolve_category(txn.get("category", ""))
    if cat is None:
        return False, f"Unknown category: {txn.get('category')}"
    txn["category"] = cat
    if not txn.get("description"):
        return False, "Missing description"
    if not txn.get("date"):
        txn["date"] = date.today().isoformat()
    elif not is_valid_date(txn["date"]):
        txn["date"] = date.today().isoformat()
    # Default currency to user's default if not specified or invalid
    if not txn.get("currency") or txn["currency"] not in SUPPORTED_CURRENCIES:
        txn["currency"] = get_default_currency()
    return True, None


def generate_insight():
    context = build_spending_context()
    system = f"""You are Vados, an AI finance assistant. Based on the user's financial data below, generate ONE short, specific, actionable insight about their spending this month. Be direct and reference real numbers. Keep it to 1-2 sentences max.

{context}"""

    response = get_client().messages.create(
        model=MODEL,
        max_tokens=200,
        system=system,
        messages=[{"role": "user", "content": "Give me one key financial insight for this month."}],
    )
    return _extract_text(response)


def parse_onboarding_history(user_message):
    context = build_spending_context()
    system = f"""You are Vados. The user is providing historical spending data during onboarding. Parse ALL transactions mentioned into structured data.

Respond with ONLY a JSON block:
```json
{{
  "transactions": [
    {{
      "type": "income" or "expense",
      "amount": <number>,
      "category": "<{'|'.join(CATEGORIES)}>",
      "description": "<short label>",
      "date": "<YYYY-MM-DD, use first of last month if not specified>",
      "currency": "<3-letter code, one of {', '.join(SUPPORTED_CURRENCIES)}; the user's default currency if not specified>"
    }}
  ]
}}
```

Today's date: {date.today().isoformat()}

{context}"""

    response = get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return parse_ai_response(_extract_text(response))
