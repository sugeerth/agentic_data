# VoyageAI v2 — real-data multi-agent (additive)

This branch **adds** two new files to the repo without modifying any existing
code, agents, tools, or docs. The original v1 system (LangGraph supervisor,
Streamlit `app.py`, evaluation harness, GitHub Pages) is unchanged.

## What's new

| File | Purpose |
|------|---------|
| `voyage_real.py` | Single-file multi-agent planner — 9 specialist agents fan out via asyncio, every fact pulled live from a keyless public API |
| `voyage_web.py`  | Stdlib HTTP server wrapping `voyage_real`, streams agent progress over SSE to an animated browser UI |

## What does NOT exist in v2 by design

* No mock data, no `random.uniform()`, no hardcoded city dictionaries
* No LLM API key required (no Anthropic / Groq / Google / OpenAI calls)
* No new dependencies beyond stdlib + the existing `markdown` package

## Live data sources

| Agent | API | Returns |
|-------|-----|---------|
| `geocode` | nominatim.openstreetmap.org | lat/lon, country, ISO code |
| `weather` | api.open-meteo.com | 16-day forecast (daily high/low/rain/wind/wmo) |
| `country` | restcountries.com | capital, languages, currency, timezone, flag |
| `wiki` | en.wikipedia.org REST | summary extract, page URL |
| `poi` | overpass-api.de | tourism + historic nodes within 8 km of city center |
| `food` | overpass-api.de | restaurants/cafes/bars within 4 km, with cuisine tags |
| `currency` | open.er-api.com | live USD → local rate |
| `logistics` | (computed) | great-circle distance + flight time + fare-search links |
| `synthesizer` | (computed) | day-by-day plan, weather-aware POI assignment, budget |

## Estimates (clearly labelled)

`logistics` and the budget reconciliation are **deterministic estimates**:

* Flight: `distance_mi × per-mi tier ($0.085–$0.18 depending on haul) + $80`
* Hotel: `nights × style-band nightly ($60 / $130 / $320)`
* Food: `days × style-band daily ($30 / $70 / $180)`

They are marked "est." in every UI surface. Nothing here is randomized.

## Run it

```bash
pip install markdown   # only new requirement
python3 voyage_real.py --destination Tokyo --origin "San Francisco" \
        --start 2026-05-28 --end 2026-06-02 --budget 3500 --travelers 2

# Or the animated web UI with live agent stream
python3 voyage_web.py --port 8765
open http://localhost:8765/
```

End-to-end run time: ~3–5 s for any city on earth.
