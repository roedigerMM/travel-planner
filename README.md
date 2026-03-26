# Travel Planner MVP (Phase 1)

Server-rendered Flask app for discovering travel destinations across multiple origins, with Amadeus-backed lookup, demo fallback data, and AI enrichment through OpenAI and Anthropic.

## Features

- Server-rendered discovery form with progressive origin autocomplete
- Multi-origin search execution with per-origin status transparency
- Real Amadeus integration plus deterministic demo fallback data
- Merged destination results stored in SQLite
- AI enrichment with fit scores and rationales on the results page
- Separate UI and JSON API blueprints

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`.
4. Fill in Amadeus, OpenAI, and Anthropic keys.
5. Set `TRAVEL_DATA_MODE=auto` for presentation-safe behavior.

## Database

Initialize the database:

```bash
flask --app run.py init-db
```

Optional demo seed:

```bash
flask --app run.py seed-demo
```

## Running

Run in PyCharm or via:

```bash
python run.py
```

App URL:

```text
http://127.0.0.1:5000/
```

## Demo Flow

1. Open `/`
2. Search airports or cities and create a search
3. Review merged results and per-origin status
4. Click `Enrich with AI` on the results page

## Tests

Run:

```bash
pytest
```
