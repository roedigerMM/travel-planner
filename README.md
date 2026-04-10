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
- Travel data:
  - pluggable provider interface
  - Amadeus provider
  - RapidAPI Skyscanner provider spike
  - config-driven demo fallback
- AI:
  - OpenAI for preference chat and normalization
  - Anthropic for destination fit scoring and rationale generation

## Travel Provider Status

- `amadeus`
  - legacy provider
  - still supported by the app
- `rapidapi_skyscanner`
  - current spike provider
  - location search uses `searchAirport`
  - destination discovery uses `searchFlightEverywhere`
  - monthly price resolution uses `getCheapestOneway`
  - candidates are now primarily city-based, not strictly airport-IATA-based

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
   - for `TRAVEL_DATA_PROVIDER=amadeus`:
     - `AMADEUS_CLIENT_ID`
     - `AMADEUS_CLIENT_SECRET`
   - for `TRAVEL_DATA_PROVIDER=rapidapi_skyscanner`:
     - `RAPIDAPI_KEY`
     - optionally adjust:
       - `RAPIDAPI_SKYSCANNER_HOST`
       - `RAPIDAPI_MARKET`
       - `RAPIDAPI_LOCALE`
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
5. Choose the travel provider:
   - `TRAVEL_DATA_PROVIDER=amadeus`
   - or `TRAVEL_DATA_PROVIDER=rapidapi_skyscanner`
6. Recommended for demos:
   - set `TRAVEL_DATA_MODE=auto`
   - this tries live travel data first and falls back to demo data if needed

Example for the RapidAPI spike:

```bash
TRAVEL_DATA_PROVIDER=rapidapi_skyscanner
RAPIDAPI_KEY=...
RAPIDAPI_SKYSCANNER_HOST=skyscanner-flights-travel-api.p.rapidapi.com
RAPIDAPI_MARKET=DE
RAPIDAPI_LOCALE=de-DE
TRAVEL_DATA_MODE=auto
```

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

Important after pulling schema changes:

- this project does not yet use formal DB migrations
- if the local schema changes, rebuild your local database:

```bash
rm -f instance/app.sqlite
./.venv/bin/flask --app run.py init-db
./.venv/bin/flask --app run.py seed-demo
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

## Known Limitations

- The RapidAPI Skyscanner spike is city-oriented:
  - destination candidates may use provider city codes such as `LISB` or `ROME`
  - not every candidate maps cleanly to a 3-letter airport IATA code
- RapidAPI free-plan quotas can interrupt live testing:
  - when limits are exceeded, `TRAVEL_DATA_MODE=auto` falls back to demo data
  - if no matching demo suggestions exist, the API can still return `502`
- `getCheapestOneway` required an extra client-side month filter:
  - the endpoint may return entries outside the requested month
  - the app now filters those entries before choosing the cheapest day
- Some RapidAPI parameters behave inconsistently:
  - for example, `market=DE` was not always accepted on `getCheapestOneway` during testing
  - the spike therefore uses the most stable subset of parameters discovered in live testing

## Tests

Run:

```bash
./.venv/bin/python -m pytest
```

The tests use a separate temporary SQLite database and should no longer affect your normal local app database.
