# Transaction parser eval harness

Evaluates the natural-language transaction parser pipeline used by the app:
`ai.chat()` -> `ai.parse_ai_response()` -> `ai.validate_transaction()`.

## Running it

```bash
python evals/run_eval.py
```

Options:

- `--cases evals/cases.jsonl` — path to the test cases (default shown).
- `--out evals/results.json` — where to write full results (default shown).
- `--no-cache` — bypass the response cache and re-call the API for every case.

Requires `ANTHROPIC_API_KEY` in `.env`, same as the app.

## How it works

- **50 hand-written cases** in `cases.jsonl` (one JSON object per line), grouped into:
  simple expenses/income, relative dates, multiple transactions per message,
  non-default currencies (symbols and words), debatable category edge cases,
  ambiguous messages (should trigger a clarifying question, not a parse), and
  pure Q&A messages (should produce no transaction at all).
- **Pinned date**: `ai.date` is monkeypatched to a fixed `2025-01-15` for the
  run, so relative-date cases ("yesterday", "last Friday") are stable
  regardless of when the eval is run. `ai.py` itself is never modified.
- **No real DB access**: `ai.build_spending_context()` and
  `ai.get_default_currency()` are monkeypatched to fixed values, so the eval
  never touches `vados.db` or Turso.
- **Caching**: each case's API response is cached to `evals/.cache/<hash>.json`,
  keyed by a hash of the pinned date + model + utterance. Reruns are free
  unless you pass `--no-cache`. The cache directory is gitignored.
## Issues found while building this (now fixed in `ai.py`)

These were originally reported rather than fixed silently; the user asked
for them to be fixed, so all three landed in `ai.py`:

1. **Stale `MODEL` constant.** `claude-sonnet-4-20250514` 404'd against the
   current `ANTHROPIC_API_KEY` (retired snapshot). Updated to `claude-sonnet-5`.
2. **`response.content[0].text` assumed the first content block was always
   text.** `claude-sonnet-5` has extended thinking on by default, which
   prepends a `ThinkingBlock` with no `.text` attribute — every call site
   (`chat()`, `generate_insight()`, `parse_onboarding_history()`) crashed.
   Added `_extract_text(response)`, which filters `response.content` to
   `type == "text"` blocks, and switched all three call sites to it.
3. **Missing-amount transactions were sometimes hallucinated.** Given just
   `"coffee"` (no amount), the model invented a $5.00 transaction instead of
   asking for the amount. Added an explicit rule to `SYSTEM_PROMPT`: a
   transaction message must include an amount, or it's AMBIGUOUS.

## Scoring

- **Intent accuracy**: whether the case correctly produced a transaction vs.
  not. Note "ambiguous" and "qa" cases collapse into the same observable
  bucket for this metric — the system prompt has both respond with plain
  text (no JSON), so there's no way to tell them apart from the response
  alone. This is a limitation of the current prompt design, not the harness.
- **Per-field accuracy**: `type`, `amount`, `category`, `date`, `currency`,
  computed only over transaction cases, aligned by position within each
  case's transaction list.
- **Category mismatches**: every case where the category didn't match is
  listed individually in the summary and in `results.json`, since category is
  inherently subjective for several of the test cases (flagged with a
  `note` field in `cases.jsonl`). Treat these as "review", not "fail".

## Results

Results are written to `evals/results.json` (per-case detail + summary) and a
summary table is printed to stdout. Paste the table below into the main
README after a run.

Run: 2025-01-15 (pinned eval date) · model: `claude-sonnet-5` · 50 cases, 0 errors
· after fixing the stale `MODEL`, the `content[0].text` crash, and the
missing-amount hallucination (see above)

**Intent classification accuracy: 50/50 (100.0%)**

| Field | Correct | Total | Accuracy |
|---|---|---|---|
| type | 47 | 47 | 100.0% |
| amount | 47 | 47 | 100.0% |
| category | 45 | 47 | 95.7% |
| date | 47 | 47 | 100.0% |
| currency | 47 | 47 | 100.0% |

**Per-group intent accuracy**

| Group | Cases | Correct | Accuracy |
|---|---|---|---|
| simple | 10 | 10 | 100.0% |
| relative_dates | 8 | 8 | 100.0% |
| multiple | 6 | 6 | 100.0% |
| currency | 8 | 8 | 100.0% |
| category_edge | 8 | 8 | 100.0% |
| ambiguous | 5 | 5 | 100.0% |
| qa | 5 | 5 | 100.0% |

**Category mismatches (2, review — category is inherently subjective for these, both flagged as debatable up front, not counted as harness failures)**

- `category_01`: "bought a couple books at the bookstore for 40" → expected `Shopping`, got `Education`
- `category_06`: "bought a birthday gift for a coworker for 25" → expected `Personal`, got `Shopping`
