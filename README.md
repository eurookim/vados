# Vados 💰

Vados is an AI-powered personal finance assistant built with Streamlit. Log transactions by chatting naturally, track spending against budgets, and get AI-generated insights into your finances.

## Features

- **Log / Chat** — Log transactions (or ask questions about your finances) using natural language, powered by Claude.
- **Dashboard** — At-a-glance view of monthly spending, budget progress, and recent activity.
- **Trends** — Visualize spending trends over time by category (Plotly charts).
- **Transaction History** — Browse, edit, and delete past transactions.
- **Recurring transactions** — Set up recurring transactions that auto-log when due.
- **Budgets** — Set per-category budget targets and track progress against them.
- **Multi-currency support** — USD, EUR, GBP, JPY, KRW, CAD, AUD, INR.
- **Flexible storage** — Uses local SQLite by default, or [Turso](https://turso.tech/) (libSQL over HTTP) when configured.

## Tech Stack

- [Streamlit](https://streamlit.io/) — UI
- [Anthropic API](https://www.anthropic.com/) (Claude) — natural language transaction parsing & insights
- [Plotly](https://plotly.com/python/) — charts
- SQLite / [Turso](https://turso.tech/) — storage

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/eurookim/vados.git
cd vados
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your-api-key-here
```

Optionally, to use a hosted Turso database instead of local SQLite, also set:

```
TURSO_DATABASE_URL=libsql://your-db-url
TURSO_AUTH_TOKEN=your-turso-token
```

When deploying to Streamlit Community Cloud, set these same keys via `.streamlit/secrets.toml` or the app's Secrets settings instead of `.env`.

### 3. Run the app

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

## Project Structure

```
app.py          # Streamlit UI, pages, and layout
ai.py           # Claude integration: chat, transaction parsing, insights
database.py     # Data layer (SQLite or Turso), categories, budgets, recurring transactions
requirements.txt
.streamlit/     # Streamlit theme config
```
