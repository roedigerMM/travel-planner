# Travel Planner MVP (Phase 1)

Server-rendered Flask app for discovering travel destinations across multiple origins, with resilient travel-data lookup, AI-assisted preference capture, and AI-based destination enrichment.

## What The App Does

- lets users describe their ideal trip in a small preference chat
- uses OpenAI to turn that input into editable preference tags and a short summary
- runs destination discovery for one or more origins
- stores merged results, per-origin status, and user preferences in SQLite
- uses Anthropic to score candidate destinations against saved preferences
- keeps working in presentation mode with deterministic demo fallback data when the live provider is unreliable

## Current Architecture

- Backend: Flask with app factory and separate UI / API blueprints
- Database: SQLite with SQLAlchemy ORM
- UI: server-rendered Jinja templates with small `fetch()` enhancements
- Travel data: Amadeus integration plus config-driven demo fallback
- AI:
  - OpenAI for preference chat and normalization
  - Anthropic for destination fit scoring and rationale generation

## Main User Flow

1. Open `/`
2. Use the **Preference Assistant** to describe the desired trip
3. Review or remove the generated preference chips
4. Select one or more origins
5. Submit the search
6. Review merged destination candidates and per-origin execution status
7. Click `Enrich with AI` to add fit scores and short rationales

## Setup

1. Create and activate a virtual environment
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`
4. Fill in the provider credentials:
   - `AMADEUS_CLIENT_ID`
   - `AMADEUS_CLIENT_SECRET`
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
5. Recommended for demos:
   - set `TRAVEL_DATA_MODE=auto`
   - this tries live travel data first and falls back to demo data if needed

## Database

Initialize the database:

```bash
flask --app run.py init-db
```

Optional demo seed:

```bash
flask --app run.py seed-demo
```

The demo seed gives you a predictable walkthrough search for presentations.

## Running

Run in PyCharm or via:

```bash
python run.py
```

App URL:

```text
http://127.0.0.1:5000/
```

## Demo Story

For a presentation, the strongest flow is:

1. Open `/`
2. Enter a natural-language preference prompt in the assistant
3. Show the generated tags and summary
4. Add one or two origins
5. Create the search
6. Show the merged candidates and origin-level transparency
7. Trigger `Enrich with AI`
8. Explain the two-provider story:
   - OpenAI shapes user intent into structured preferences
   - Anthropic evaluates how well each destination matches those preferences

If the live travel provider is flaky, `TRAVEL_DATA_MODE=auto` keeps the demo stable by using fallback destination data while still preserving the real integration architecture.

## Tests

Run:

```bash
python -m pytest
```

The tests use a separate temporary SQLite database and should no longer affect your normal local app database.
