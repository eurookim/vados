"""Evaluation harness for the natural-language transaction parser (ai.chat +
ai.parse_ai_response + ai.validate_transaction).

Usage:
    python evals/run_eval.py [--no-cache] [--cases evals/cases.jsonl] [--out evals/results.json]

See evals/README.md for details.
"""
import argparse
import copy
import hashlib
import json
import math
import os
import sys
from datetime import date as real_date, datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CACHE_DIR = os.path.join(SCRIPT_DIR, ".cache")

sys.path.insert(0, PROJECT_ROOT)

import ai  # noqa: E402

# ----------------------------------------------------------------------
# Determinism: pin "today" and stub out anything that hits the real DB.
# ----------------------------------------------------------------------

PINNED_TODAY = real_date(2025, 1, 15)  # Wednesday


class _FakeDate(real_date):
    @classmethod
    def today(cls):
        return PINNED_TODAY


FIXED_RAG_CONTEXT = """=== FINANCIAL CONTEXT FOR January 2025 ===
Today's date: 2025-01-15
Default currency: USD
Total income this month: $3,200.00
Total expenses this month: $845.30
Net balance: $2,354.70
Savings rate: 73.6%

Spending by category this month:
  Food: $210.50
  Shopping: $180.00
  Housing: $150.00
  Transport: $85.00
  Entertainment: $60.00
  Health: $59.80
  Subscriptions: $45.00
  Education: $30.00
  Personal: $25.00

Budget targets:
  Food: $300.00 / $300.00
  Entertainment: $60.00 / $100.00

Most recent transactions (up to 15):
  [2025-01-14] -$45.00 — Shopping: New shoes
  [2025-01-13] -$60.00 — Entertainment: Movie night
  [2025-01-10] -$150.00 — Housing: Rent
  [2025-01-08] +$3200.00 — Income: Paycheck
  [2025-01-05] -$30.00 — Education: Online course

Upcoming recurring transactions (next 14 days):
  Gym membership: $15.00 (monthly, due 2025-01-20)

User's financial goals: Save 20% of income each month
"""


def _stub_build_rag_context():
    return FIXED_RAG_CONTEXT


def _stub_get_default_currency():
    return "USD"


def apply_stubs():
    ai.date = _FakeDate
    ai.build_rag_context = _stub_build_rag_context
    ai.get_default_currency = _stub_get_default_currency


# ----------------------------------------------------------------------
# Caching
# ----------------------------------------------------------------------

def cache_key(utterance):
    payload = f"{PINNED_TODAY.isoformat()}|{ai.MODEL}|{utterance}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_chat(utterance, use_cache=True):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = cache_key(utterance)
    path = os.path.join(CACHE_DIR, f"{key}.json")

    if use_cache and os.path.exists(path):
        with open(path) as f:
            return json.load(f)["response_text"], True

    response_text = ai.chat(utterance, conversation_history=[], pending_transaction=None)

    with open(path, "w") as f:
        json.dump({"utterance": utterance, "response_text": response_text}, f, indent=2)

    return response_text, False


# ----------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------

TXN_FIELDS = ["type", "amount", "category", "date", "currency"]


def classify_actual_intent(parsed):
    if not parsed:
        return "non_transaction"
    intent = parsed.get("intent")
    if intent == "transaction" and parsed.get("transactions"):
        return "transaction"
    if intent == "correction":
        return "correction"
    if intent in ("confirmed", "cancelled"):
        return "other"
    return "non_transaction"


def normalize_expected_intent(expected_intent):
    if expected_intent == "transaction":
        return "transaction"
    # "ambiguous" and "qa" both surface as plain text (no JSON block) per
    # the system prompt, so they collapse to the same observable bucket.
    return "non_transaction"


def fields_match(field, expected_val, actual_val):
    if actual_val is None:
        return False
    if field == "amount":
        try:
            return math.isclose(float(expected_val), float(actual_val), rel_tol=1e-6, abs_tol=1e-6)
        except (TypeError, ValueError):
            return False
    if field == "currency" or field == "category" or field == "type":
        return str(expected_val) == str(actual_val)
    if field == "date":
        return str(expected_val) == str(actual_val)
    return expected_val == actual_val


def run_case(case, use_cache):
    input_text = case["input"]
    expected = case["expected"]

    result = {
        "id": case["id"],
        "group": case["group"],
        "input": input_text,
        "note": case.get("note"),
        "error": None,
        "from_cache": False,
    }

    try:
        response_text, from_cache = cached_chat(input_text, use_cache=use_cache)
    except Exception as e:  # noqa: BLE001
        result["error"] = f"chat() raised: {e}"
        result["actual_intent"] = "error"
        result["expected_intent"] = normalize_expected_intent(expected["intent"])
        result["intent_correct"] = False
        result["transaction_field_results"] = []
        return result

    result["from_cache"] = from_cache
    result["raw_response"] = response_text

    parsed = ai.parse_ai_response(response_text)
    actual_intent = classify_actual_intent(parsed)
    expected_intent_norm = normalize_expected_intent(expected["intent"])

    result["actual_intent"] = actual_intent
    result["expected_intent"] = expected_intent_norm
    result["intent_correct"] = (actual_intent == expected_intent_norm)

    txn_field_results = []

    if expected["intent"] == "transaction":
        expected_txns = expected.get("transactions", [])
        actual_txns_raw = parsed.get("transactions", []) if (parsed and actual_intent == "transaction") else []

        # Validate each actual transaction the same way the app does.
        validated_txns = []
        for txn in actual_txns_raw:
            txn = copy.deepcopy(txn)
            ok, err = ai.validate_transaction(txn)
            validated_txns.append(txn if ok else None)

        for i, exp_txn in enumerate(expected_txns):
            act_txn = validated_txns[i] if i < len(validated_txns) else None
            per_field = {}
            for field in TXN_FIELDS:
                exp_val = exp_txn.get(field)
                act_val = act_txn.get(field) if act_txn else None
                per_field[field] = {
                    "expected": exp_val,
                    "actual": act_val,
                    "correct": fields_match(field, exp_val, act_val),
                }
            txn_field_results.append(per_field)

        if len(validated_txns) > len(expected_txns):
            result["extra_transactions"] = validated_txns[len(expected_txns):]

    result["transaction_field_results"] = txn_field_results
    return result


def summarize(results):
    intent_correct = sum(1 for r in results if r.get("intent_correct"))
    intent_total = len(results)

    field_correct = {f: 0 for f in TXN_FIELDS}
    field_total = {f: 0 for f in TXN_FIELDS}

    group_stats = {}
    category_mismatches = []

    for r in results:
        g = r["group"]
        gs = group_stats.setdefault(g, {"cases": 0, "intent_correct": 0})
        gs["cases"] += 1
        if r.get("intent_correct"):
            gs["intent_correct"] += 1

        for txn_result in r.get("transaction_field_results", []):
            for field in TXN_FIELDS:
                field_total[field] += 1
                if txn_result[field]["correct"]:
                    field_correct[field] += 1
            cat = txn_result.get("category")
            if cat and not cat["correct"]:
                category_mismatches.append({
                    "id": r["id"],
                    "input": r["input"],
                    "note": r.get("note"),
                    "expected": cat["expected"],
                    "actual": cat["actual"],
                })

    field_accuracy = {
        f: {
            "correct": field_correct[f],
            "total": field_total[f],
            "pct": (field_correct[f] / field_total[f] * 100) if field_total[f] else None,
        }
        for f in TXN_FIELDS
    }

    group_accuracy = {
        g: {
            "cases": s["cases"],
            "intent_correct": s["intent_correct"],
            "pct": s["intent_correct"] / s["cases"] * 100 if s["cases"] else None,
        }
        for g, s in group_stats.items()
    }

    return {
        "intent_accuracy": {
            "correct": intent_correct,
            "total": intent_total,
            "pct": (intent_correct / intent_total * 100) if intent_total else None,
        },
        "field_accuracy": field_accuracy,
        "group_accuracy": group_accuracy,
        "category_mismatches": category_mismatches,
    }


def print_summary(summary, num_cases, num_errors):
    print()
    print("=" * 60)
    print("EVAL SUMMARY")
    print("=" * 60)
    print(f"Cases run: {num_cases}  (errors: {num_errors})")
    print()

    ia = summary["intent_accuracy"]
    print(f"Intent classification accuracy: {ia['correct']}/{ia['total']} ({ia['pct']:.1f}%)")
    print()

    print("Per-field accuracy (transaction cases only):")
    print(f"{'field':<12}{'correct':>10}{'total':>8}{'pct':>8}")
    for field, stats in summary["field_accuracy"].items():
        pct = f"{stats['pct']:.1f}%" if stats["pct"] is not None else "n/a"
        print(f"{field:<12}{stats['correct']:>10}{stats['total']:>8}{pct:>8}")
    print()

    print("Per-group intent accuracy:")
    print(f"{'group':<16}{'cases':>8}{'correct':>10}{'pct':>8}")
    for group, stats in sorted(summary["group_accuracy"].items()):
        pct = f"{stats['pct']:.1f}%" if stats["pct"] is not None else "n/a"
        print(f"{group:<16}{stats['cases']:>8}{stats['intent_correct']:>10}{pct:>8}")
    print()

    mismatches = summary["category_mismatches"]
    print(f"Category mismatches ({len(mismatches)}) — review these, category is subjective:")
    for m in mismatches:
        note = f"  [{m['note']}]" if m.get("note") else ""
        print(f"  {m['id']}: \"{m['input']}\" -> expected {m['expected']!r}, got {m['actual']!r}{note}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Run the transaction-parser eval suite.")
    parser.add_argument("--cases", default=os.path.join(SCRIPT_DIR, "cases.jsonl"))
    parser.add_argument("--out", default=os.path.join(SCRIPT_DIR, "results.json"))
    parser.add_argument("--no-cache", action="store_true", help="Ignore cache, re-call the API for every case.")
    args = parser.parse_args()

    apply_stubs()

    cases = []
    with open(args.cases) as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    use_cache = not args.no_cache
    results = []
    num_errors = 0
    for case in cases:
        print(f"Running {case['id']}...", file=sys.stderr)
        r = run_case(case, use_cache=use_cache)
        if r.get("error"):
            num_errors += 1
        results.append(r)

    summary = summarize(results)

    output = {
        "run_at": datetime.now().isoformat(),
        "pinned_today": PINNED_TODAY.isoformat(),
        "model": ai.MODEL,
        "num_cases": len(results),
        "num_errors": num_errors,
        "summary": summary,
        "cases": results,
    }

    with open(args.out, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print_summary(summary, len(results), num_errors)
    print(f"\nFull results written to {args.out}")


if __name__ == "__main__":
    main()
