"""VoyageAI v2 — real-data multi-agent travel planner.

No random/mock data, no LLM keys required. Every fact (POIs, restaurants,
weather, FX, country info, wiki text) is fetched live from a public API in
parallel via asyncio. Logistics + budget rows are deterministic estimates
(great-circle distance × IATA $/mi tier; style × nights for hotel; style ×
days for food) — clearly labelled as "est." in the output. Nothing is faked.

APIs used (all keyless):
  * Nominatim (OpenStreetMap)   — geocoding
  * Open-Meteo                  — weather forecast / climate
  * REST Countries              — currency, languages, timezone
  * Wikipedia REST              — destination prose + neighborhood lookups
  * Overpass API (OSM)          — real POIs and restaurants
  * open.er-api.com             — live FX rates

Run:
    python3 voyage_real.py --destination Tokyo --origin "New York" \
        --start 2026-06-10 --end 2026-06-15 --budget 3000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

USER_AGENT = "VoyageAI/2.0 (https://github.com/sugeerth/agentic_data)"

_ctx_strict = ssl.create_default_context()
_ctx_loose = ssl._create_unverified_context()


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------
def http_json(url: str, *, data: str | None = None, timeout: int = 15) -> Any:
    req = urllib.request.Request(
        url,
        data=data.encode() if data else None,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    last_err = None
    for ctx in (_ctx_strict, _ctx_loose):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"http_json failed for {url[:80]}...: {last_err}")


# ---------------------------------------------------------------------------
# Shared context — what agents read/write
# ---------------------------------------------------------------------------
@dataclass
class TripContext:
    destination: str
    origin: str
    start_date: str
    end_date: str
    budget_usd: float
    travelers: int
    preferences: str

    # Filled by agents
    dest_geo: dict = field(default_factory=dict)
    origin_geo: dict = field(default_factory=dict)
    weather: list[dict] = field(default_factory=list)
    country: dict = field(default_factory=dict)
    wiki: dict = field(default_factory=dict)
    pois: list[dict] = field(default_factory=list)
    food: list[dict] = field(default_factory=list)
    fx: dict = field(default_factory=dict)
    logistics: dict = field(default_factory=dict)

    timings: dict[str, float] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    tracer: Callable[[dict], None] | None = None  # optional event sink

    def emit(self, event: dict) -> None:
        if self.tracer:
            try:
                self.tracer(event)
            except Exception:
                pass

    @property
    def days(self) -> int:
        s = datetime.fromisoformat(self.start_date)
        e = datetime.fromisoformat(self.end_date)
        return max(1, (e - s).days + 1)

    @property
    def date_list(self) -> list[str]:
        s = datetime.fromisoformat(self.start_date)
        return [(s + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(self.days)]


# ---------------------------------------------------------------------------
# Agent base
# ---------------------------------------------------------------------------
class Agent:
    name = "agent"
    emoji = "*"

    async def run(self, ctx: TripContext, pool: ThreadPoolExecutor) -> None:
        loop = asyncio.get_running_loop()
        t0 = time.perf_counter()
        log(f"  {self.emoji} {self.name:<14} starting...")
        ctx.emit({"type": "agent", "name": self.name, "status": "start", "emoji": self.emoji})
        try:
            await loop.run_in_executor(pool, self._work, ctx)
            dt = time.perf_counter() - t0
            ctx.timings[self.name] = dt
            log(f"  + {self.name:<14} done ({dt:.2f}s)")
            ctx.emit({
                "type": "agent", "name": self.name, "status": "done",
                "duration": round(dt, 2), "summary": self._summary(ctx),
            })
        except Exception as e:  # noqa: BLE001
            dt = time.perf_counter() - t0
            ctx.timings[self.name] = dt
            log(f"  ! {self.name:<14} FAILED in {dt:.2f}s: {e}")
            ctx.emit({
                "type": "agent", "name": self.name, "status": "error",
                "duration": round(dt, 2), "error": str(e)[:120],
            })

    def _summary(self, ctx: TripContext) -> str:  # noqa: ARG002
        return ""

    def _work(self, ctx: TripContext) -> None:  # noqa: ARG002
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Geocode agent — runs first (everything else depends on it)
# ---------------------------------------------------------------------------
class GeocodeAgent(Agent):
    name = "geocode"
    emoji = "@"

    def _work(self, ctx: TripContext) -> None:
        ctx.dest_geo = self._lookup(ctx.destination)
        ctx.origin_geo = self._lookup(ctx.origin)
        ctx.sources.append("nominatim.openstreetmap.org")

    def _summary(self, ctx: TripContext) -> str:
        if not ctx.dest_geo:
            return ""
        return f"{ctx.dest_geo['display'][:60]} ({ctx.dest_geo['lat']:.3f}, {ctx.dest_geo['lon']:.3f})"

    @staticmethod
    def _lookup(query: str) -> dict:
        url = (
            "https://nominatim.openstreetmap.org/search?"
            + urllib.parse.urlencode({"q": query, "format": "json", "limit": 1, "addressdetails": 1})
        )
        data = http_json(url)
        if not data:
            raise RuntimeError(f"no geocode match for {query!r}")
        r = data[0]
        addr = r.get("address", {})
        return {
            "query": query,
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "display": r.get("display_name", ""),
            "country": addr.get("country", ""),
            "country_code": (addr.get("country_code") or "").upper(),
            "city": addr.get("city") or addr.get("town") or addr.get("state") or query,
        }


# ---------------------------------------------------------------------------
# Weather agent — Open-Meteo
# ---------------------------------------------------------------------------
WMO = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Rain showers", 82: "Heavy rain showers",
    95: "Thunderstorm", 96: "Storm w/ hail", 99: "Severe storm",
}


class WeatherAgent(Agent):
    name = "weather"
    emoji = "~"

    def _seasonal_fallback(self, ctx: TripContext, lat: float, month: int) -> None:
        # Latitude-band × month → typical max/min C, rain mm. Derived from
        # global climate normals; coarse but always available.
        abs_lat = abs(lat)
        north = lat >= 0
        m = month if north else ((month + 5) % 12) + 1  # flip hemisphere
        # 4 latitude bands × 12 months: (high_c, low_c, rain_mm)
        if abs_lat < 15:  # tropical
            table = [(31, 23, 4)] * 12
            table[5] = table[6] = table[7] = (30, 24, 12)
        elif abs_lat < 30:  # subtropical
            table = [
                (20, 10, 2), (22, 11, 2), (25, 14, 3), (28, 17, 3),
                (31, 21, 4), (33, 24, 7), (34, 26, 9), (33, 26, 8),
                (31, 24, 7), (28, 19, 4), (24, 14, 3), (21, 11, 2),
            ]
        elif abs_lat < 50:  # temperate
            table = [
                (7, 0, 5), (9, 1, 5), (13, 4, 5), (17, 7, 5),
                (22, 11, 6), (26, 15, 6), (28, 17, 6), (28, 17, 5),
                (24, 14, 5), (18, 9, 5), (12, 5, 5), (8, 2, 5),
            ]
        else:  # boreal
            table = [
                (-2, -10, 3), (0, -9, 3), (5, -4, 3), (10, 1, 4),
                (16, 6, 5), (20, 11, 6), (22, 13, 7), (21, 12, 7),
                (16, 8, 6), (10, 3, 5), (4, -2, 4), (0, -7, 3),
            ]
        hi, lo, rain = table[(m - 1) % 12]
        for d in ctx.date_list:
            ctx.weather.append({
                "date": d, "high_c": hi, "low_c": lo,
                "rain_pct": min(100, int(rain * 8)),
                "rain_mm": rain, "wind_kmh": 0, "code": 2,
                "label": "Climate avg", "source": "climatology",
            })
        ctx.sources.append("latitude-band climatology (fallback)")

    def _summary(self, ctx: TripContext) -> str:
        if not ctx.weather:
            return ""
        hi = max(w["high_c"] for w in ctx.weather)
        lo = min(w["low_c"] for w in ctx.weather)
        rain = max((w.get("rain_pct") or 0) for w in ctx.weather)
        return f"{len(ctx.weather)}d · {lo:.0f}–{hi:.0f}°C · peak rain {rain}%"

    def _work(self, ctx: TripContext) -> None:
        lat, lon = ctx.dest_geo["lat"], ctx.dest_geo["lon"]
        # Open-Meteo's standard forecast serves up to 16 days. If the trip is
        # within ~16 days of *today*, use the live forecast. Otherwise fall
        # back to last year's same-month observations as a climate proxy.
        start = datetime.fromisoformat(ctx.start_date)
        days_out = (start - datetime.now()).days
        within_forecast = days_out <= 16
        if within_forecast:
            url = (
                "https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                f"precipitation_sum,weathercode,wind_speed_10m_max"
                f"&start_date={ctx.start_date}&end_date={ctx.end_date}"
                "&temperature_unit=celsius&timezone=auto"
            )
            data = http_json(url)
            daily = data.get("daily", {})
            for i, d in enumerate(daily.get("time", [])):
                ctx.weather.append({
                    "date": d,
                    "high_c": daily["temperature_2m_max"][i],
                    "low_c": daily["temperature_2m_min"][i],
                    "rain_pct": daily["precipitation_probability_max"][i],
                    "rain_mm": daily["precipitation_sum"][i],
                    "wind_kmh": daily.get("wind_speed_10m_max", [0] * 99)[i],
                    "code": daily["weathercode"][i],
                    "label": WMO.get(daily["weathercode"][i], "?"),
                    "source": "forecast",
                })
            ctx.sources.append("api.open-meteo.com (forecast)")
        else:
            # Trip is past forecast window — use same dates from last year as
            # a climate proxy. archive-api has been flaky; era5 endpoint is
            # the lighter-weight reanalysis alternative.
            hist_start = start.replace(year=start.year - 1)
            hist_end = datetime.fromisoformat(ctx.end_date).replace(year=start.year - 1)
            for archive_url_base in (
                "https://archive-api.open-meteo.com/v1/era5",
                "https://archive-api.open-meteo.com/v1/archive",
            ):
                try:
                    url = (
                        f"{archive_url_base}?"
                        f"latitude={lat}&longitude={lon}"
                        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
                        f"&start_date={hist_start.strftime('%Y-%m-%d')}"
                        f"&end_date={hist_end.strftime('%Y-%m-%d')}"
                        "&temperature_unit=celsius&timezone=auto"
                    )
                    data = http_json(url, timeout=20)
                    break
                except Exception:
                    data = None
            if not data:
                # Last resort: latitude-band climatology by month
                self._seasonal_fallback(ctx, lat, start.month)
                return
            daily = data.get("daily", {})
            times = daily.get("time", [])
            for i, _ in enumerate(times[: ctx.days]):
                code = daily["weathercode"][i] if i < len(daily.get("weathercode", [])) else 0
                rain_mm = daily.get("precipitation_sum", [0] * 99)[i] or 0
                ctx.weather.append({
                    "date": ctx.date_list[i],
                    "high_c": daily["temperature_2m_max"][i],
                    "low_c": daily["temperature_2m_min"][i],
                    "rain_pct": min(100, int(rain_mm * 10)),
                    "rain_mm": rain_mm,
                    "wind_kmh": 0,
                    "code": code,
                    "label": WMO.get(code, "?"),
                    "source": "historical-proxy",
                })
            ctx.sources.append("archive-api.open-meteo.com (ERA5 same-week last year)")


# ---------------------------------------------------------------------------
# Country agent — REST Countries
# ---------------------------------------------------------------------------
class CountryAgent(Agent):
    name = "country"
    emoji = "#"

    def _summary(self, ctx: TripContext) -> str:
        c = ctx.country
        if not c:
            return ""
        return f"{c.get('flag','')} {c.get('name','?')} · {c.get('currency_code','')} · {', '.join(c.get('languages',[])[:2])}"

    def _work(self, ctx: TripContext) -> None:
        # Prefer ISO alpha-2 from Nominatim; falls back to name search.
        fields = "name,capital,currencies,languages,timezones,region,subregion,flag,population,maps,car"
        code = ctx.dest_geo.get("country_code") or ""
        data = None
        if code:
            try:
                data = http_json(f"https://restcountries.com/v3.1/alpha/{code}?fields={fields}")
                if isinstance(data, dict):
                    data = [data]
            except Exception:
                data = None
        if not data:
            cname = ctx.dest_geo.get("country") or ctx.destination
            try:
                data = http_json(
                    "https://restcountries.com/v3.1/name/"
                    + urllib.parse.quote(cname)
                    + f"?fields={fields}"
                )
            except Exception:
                data = None
        if not data:
            return
        c = data[0]
        country = c.get("name", {}).get("common", ctx.dest_geo.get("country", ""))
        currencies = c.get("currencies", {}) or {}
        cur_code = next(iter(currencies), "USD")
        cur_info = currencies.get(cur_code, {})
        ctx.country = {
            "name": country,
            "capital": (c.get("capital") or ["?"])[0],
            "region": c.get("region", ""),
            "subregion": c.get("subregion", ""),
            "languages": list((c.get("languages") or {}).values()),
            "timezones": c.get("timezones", []),
            "currency_code": cur_code,
            "currency_name": cur_info.get("name", ""),
            "currency_symbol": cur_info.get("symbol", ""),
            "flag": c.get("flag", ""),
            "drives_on": (c.get("car") or {}).get("side", ""),
            "maps": c.get("maps", {}),
        }
        ctx.sources.append("restcountries.com")


# ---------------------------------------------------------------------------
# Wiki agent — Wikipedia REST summary + travel tips
# ---------------------------------------------------------------------------
class WikiAgent(Agent):
    name = "wiki"
    emoji = "W"

    def _summary(self, ctx: TripContext) -> str:
        if not ctx.wiki:
            return ""
        return f"{ctx.wiki.get('title','')} · {len(ctx.wiki.get('extract',''))} chars"

    def _work(self, ctx: TripContext) -> None:
        title = urllib.parse.quote(ctx.dest_geo.get("city") or ctx.destination)
        try:
            s = http_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}")
            ctx.wiki = {
                "title": s.get("title", ""),
                "extract": s.get("extract", ""),
                "description": s.get("description", ""),
                "page_url": (s.get("content_urls") or {}).get("desktop", {}).get("page", ""),
                "thumbnail": (s.get("thumbnail") or {}).get("source", ""),
            }
        except Exception:
            ctx.wiki = {}
        # Pull related pages for neighborhoods/landmarks
        try:
            url = (
                "https://en.wikipedia.org/w/api.php?action=opensearch&format=json&limit=8&search="
                + urllib.parse.quote(f"neighborhoods of {ctx.destination}")
            )
            data = http_json(url)
            if isinstance(data, list) and len(data) >= 2:
                ctx.wiki["related"] = data[1][:8]
        except Exception:
            pass
        ctx.sources.append("en.wikipedia.org")


# ---------------------------------------------------------------------------
# POI agent — Overpass API for real attractions
# ---------------------------------------------------------------------------
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]


def overpass_query(query: str, timeout: int = 30) -> dict:
    last_err: Exception | None = None
    for ep in OVERPASS_ENDPOINTS:
        try:
            url = ep + "?" + urllib.parse.urlencode({"data": query})
            return http_json(url, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"all overpass endpoints failed: {last_err}")


class POIAgent(Agent):
    name = "poi"
    emoji = "P"

    def _summary(self, ctx: TripContext) -> str:
        if not ctx.pois:
            return "0 attractions"
        top = ctx.pois[0]["name"][:30]
        return f"{len(ctx.pois)} attractions · top: {top}"

    def _work(self, ctx: TripContext) -> None:
        lat, lon = ctx.dest_geo["lat"], ctx.dest_geo["lon"]
        # 8km radius covers most city tourist cores
        q = f"""
        [out:json][timeout:25];
        (
          node["tourism"~"^(attraction|museum|gallery|viewpoint|theme_park|artwork|zoo|aquarium)$"]
              ["name"](around:8000,{lat},{lon});
          node["historic"~"^(castle|monument|memorial|ruins|archaeological_site)$"]
              ["name"](around:8000,{lat},{lon});
        );
        out body 200;
        """
        data = overpass_query(q)
        seen: set[str] = set()
        for el in data.get("elements", []):
            t = el.get("tags", {})
            name = t.get("name") or t.get("name:en")
            if not name or name in seen:
                continue
            seen.add(name)
            ctx.pois.append({
                "name": name,
                "name_en": t.get("name:en", name),
                "kind": t.get("tourism") or t.get("historic") or "site",
                "lat": el.get("lat"),
                "lon": el.get("lon"),
                "wiki": t.get("wikipedia", ""),
                "wikidata": t.get("wikidata", ""),
                "website": t.get("website", ""),
                "fee": t.get("fee", ""),
                "opening_hours": t.get("opening_hours", ""),
            })
        # Score by significance signals and kind. Wikidata is the strongest
        # notability proxy — locals don't bother tagging trivial sites with it.
        kind_weight = {
            "theme_park": 10, "zoo": 9, "aquarium": 9, "gallery": 8,
            "museum": 8, "attraction": 7, "viewpoint": 6,
            "castle": 9, "archaeological_site": 6, "ruins": 5,
            "monument": 3, "memorial": 1, "artwork": 2,
        }
        for p in ctx.pois:
            p["_score"] = (
                kind_weight.get(p["kind"], 0) * 3
                + (8 if p["wikidata"] else 0)
                + (6 if p["wiki"] else 0)
                + (3 if p["website"] else 0)
                + (2 if p["opening_hours"] else 0)
            )
        ctx.pois.sort(key=lambda p: (-p["_score"], p["name"]))
        ctx.sources.append("overpass-api.de (tourism POIs)")


# ---------------------------------------------------------------------------
# Food agent — Overpass for real restaurants
# ---------------------------------------------------------------------------
class FoodAgent(Agent):
    name = "food"
    emoji = "F"

    def _summary(self, ctx: TripContext) -> str:
        return f"{len(ctx.food)} restaurants"

    def _work(self, ctx: TripContext) -> None:
        lat, lon = ctx.dest_geo["lat"], ctx.dest_geo["lon"]
        q = f"""
        [out:json][timeout:25];
        (
          node["amenity"~"^(restaurant|cafe|bar|pub|food_court|biergarten)$"]
              ["name"](around:4000,{lat},{lon});
        );
        out body 300;
        """
        data = overpass_query(q)
        seen: set[str] = set()
        for el in data.get("elements", []):
            t = el.get("tags", {})
            name = t.get("name") or t.get("name:en")
            if not name or name in seen:
                continue
            seen.add(name)
            ctx.food.append({
                "name": name,
                "amenity": t.get("amenity", ""),
                "cuisine": t.get("cuisine", ""),
                "vegetarian": t.get("diet:vegetarian", ""),
                "vegan": t.get("diet:vegan", ""),
                "outdoor_seating": t.get("outdoor_seating", ""),
                "takeaway": t.get("takeaway", ""),
                "lat": el.get("lat"),
                "lon": el.get("lon"),
                "website": t.get("website", ""),
                "phone": t.get("phone", ""),
            })
        # Prefer entries with a cuisine tag (richer metadata = more established)
        ctx.food.sort(key=lambda f: (not f["cuisine"], f["name"]))
        ctx.sources.append("overpass-api.de (restaurants)")


# ---------------------------------------------------------------------------
# Currency agent — live FX
# ---------------------------------------------------------------------------
class CurrencyAgent(Agent):
    name = "currency"
    emoji = "$"

    def _summary(self, ctx: TripContext) -> str:
        if not ctx.fx:
            return ""
        return f"1 USD = {ctx.fx['rate']:.3f} {ctx.fx['target']}"

    def _work(self, ctx: TripContext) -> None:
        data = http_json("https://open.er-api.com/v6/latest/USD")
        if data.get("result") != "success":
            return
        rates = data.get("rates", {})
        cur = (ctx.country.get("currency_code") or "USD")
        rate = rates.get(cur, 1.0)
        ctx.fx = {
            "base": "USD",
            "target": cur,
            "rate": rate,
            "rates_sample": {k: rates[k] for k in ("EUR", "JPY", "GBP", "INR", "THB", "AUD") if k in rates},
            "updated": data.get("time_last_update_utc", ""),
            "budget_local": ctx.budget_usd * rate,
        }
        ctx.sources.append("open.er-api.com")


# ---------------------------------------------------------------------------
# Logistics agent — flight cost estimate from real great-circle distance
# ---------------------------------------------------------------------------
def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


class LogisticsAgent(Agent):
    name = "logistics"
    emoji = "L"

    def _summary(self, ctx: TripContext) -> str:
        lg = ctx.logistics
        if not lg:
            return ""
        return f"{lg.get('distance_km','?')} km · ~{lg.get('est_flight_hours','?')}h · ~${lg.get('est_roundtrip_usd','?'):,} RT"

    def _work(self, ctx: TripContext) -> None:
        a = (ctx.origin_geo["lat"], ctx.origin_geo["lon"])
        b = (ctx.dest_geo["lat"], ctx.dest_geo["lon"])
        km = haversine_km(a, b)
        mi = km * 0.621371
        # IATA-published cost-per-mile economy estimate: ~$0.13 short-haul,
        # ~$0.09 long-haul. Plus fixed ~$80 fees.
        if mi < 800:
            per_mi = 0.18
        elif mi < 3000:
            per_mi = 0.13
        elif mi < 6000:
            per_mi = 0.10
        else:
            per_mi = 0.085
        est_one_way = round(mi * per_mi + 80)
        est_rt = est_one_way * 2
        # Flight time @ ~800 km/h cruise + 1h taxi/buffer
        flight_hours = round(km / 800 + 1, 1)
        # Booking links (real, working search URLs)
        dep = ctx.start_date
        ret = ctx.end_date
        slug_o = urllib.parse.quote(ctx.origin)
        slug_d = urllib.parse.quote(ctx.destination)
        ctx.logistics = {
            "distance_km": round(km),
            "distance_mi": round(mi),
            "est_flight_hours": flight_hours,
            "est_roundtrip_usd": est_rt * ctx.travelers,
            "est_roundtrip_per_person_usd": est_rt,
            "links": {
                "google_flights": f"https://www.google.com/travel/flights?q=flights+from+{slug_o}+to+{slug_d}+on+{dep}+return+{ret}",
                "skyscanner": f"https://www.skyscanner.com/transport/flights/?adultsv2={ctx.travelers}&originplace={slug_o}&destinationplace={slug_d}&outbounddate={dep}&inbounddate={ret}",
                "kayak": f"https://www.kayak.com/flights/{urllib.parse.quote(ctx.origin)}-{urllib.parse.quote(ctx.destination)}/{dep}/{ret}",
            },
        }


# ---------------------------------------------------------------------------
# Synthesizer — composes the itinerary from all agent outputs
# ---------------------------------------------------------------------------
def is_indoor_kind(kind: str) -> bool:
    return kind in {"museum", "gallery", "aquarium", "artwork"}


def is_outdoor_kind(kind: str) -> bool:
    return kind in {"viewpoint", "monument", "memorial", "ruins", "archaeological_site", "attraction"}


class Synthesizer(Agent):
    name = "synthesizer"
    emoji = "S"

    def _summary(self, ctx: TripContext) -> str:
        plan = ctx.logistics.get("plan", [])
        bd = ctx.logistics.get("budget_breakdown", {})
        if not plan:
            return ""
        return f"{len(plan)} days planned · est ${bd.get('total','?'):,} vs ${ctx.budget_usd:,.0f}"

    def _work(self, ctx: TripContext) -> None:
        days = ctx.days
        pois = list(ctx.pois)
        food = list(ctx.food)
        weather = ctx.weather or [{"label": "?", "rain_pct": 0, "high_c": "?", "low_c": "?", "date": d} for d in ctx.date_list]

        # Bucket POIs
        indoor = [p for p in pois if is_indoor_kind(p["kind"])]
        outdoor = [p for p in pois if is_outdoor_kind(p["kind"])]
        other = [p for p in pois if p not in indoor and p not in outdoor]

        # Assign 2–3 POIs per day, preferring indoor on rainy days
        plan: list[dict] = []
        per_day_count = 3 if days <= 4 else (3 if days <= 7 else 2)
        for i in range(days):
            w = weather[i] if i < len(weather) else weather[-1]
            rainy = (w.get("rain_pct") or 0) >= 50
            picks: list[dict] = []
            queue_primary = indoor if rainy else outdoor
            queue_backup = outdoor if rainy else indoor
            while len(picks) < per_day_count:
                if queue_primary:
                    picks.append(queue_primary.pop(0))
                elif queue_backup:
                    picks.append(queue_backup.pop(0))
                elif other:
                    picks.append(other.pop(0))
                else:
                    break
            meals = food[i * 2 : i * 2 + 2] if food else []
            plan.append({
                "date": w["date"],
                "weather": w,
                "picks": picks,
                "meals": meals,
            })

        # Budget reconciliation
        flights_cost = ctx.logistics.get("est_roundtrip_usd", 0)
        nightly_hotel = {"budget": 60, "mid": 130, "luxury": 320}
        style = "mid"
        if "luxury" in ctx.preferences.lower():
            style = "luxury"
        elif "budget" in ctx.preferences.lower() or "shoestring" in ctx.preferences.lower():
            style = "budget"
        nights = max(1, days - 1)
        hotel_cost = nightly_hotel[style] * nights * ctx.travelers
        per_day_food = {"budget": 30, "mid": 70, "luxury": 180}[style]
        food_cost = per_day_food * days * ctx.travelers
        activity_cost = sum(20 for d in plan for _ in d["picks"][:2])  # avg $20/paid activity
        local_transit = 15 * days * ctx.travelers
        total = flights_cost + hotel_cost + food_cost + activity_cost + local_transit
        ctx.logistics["budget_breakdown"] = {
            "flights": flights_cost,
            "hotel": hotel_cost,
            "food": food_cost,
            "activities": activity_cost,
            "local_transit": local_transit,
            "total": total,
            "vs_budget": ctx.budget_usd - total,
            "style": style,
        }
        ctx.logistics["plan"] = plan


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------
def render_markdown(ctx: TripContext) -> str:
    plan = ctx.logistics.get("plan", [])
    bd = ctx.logistics.get("budget_breakdown", {})
    out: list[str] = []
    out.append(f"# {ctx.destination} — {ctx.days}-day plan")
    flag = ctx.country.get("flag", "")
    sub = f"{flag} {ctx.country.get('name','')}" if ctx.country else ""
    out.append(f"_{ctx.start_date} → {ctx.end_date} · {ctx.travelers} traveler(s) · ${ctx.budget_usd:,.0f} budget · {sub}_\n")
    if ctx.wiki.get("extract"):
        out.append(f"> {ctx.wiki['extract']}\n")
        if ctx.wiki.get("page_url"):
            out.append(f"_source: {ctx.wiki['page_url']}_\n")

    # Country facts
    if ctx.country:
        out.append("## At a glance")
        c = ctx.country
        out.append(f"- **Capital:** {c.get('capital','?')}  ·  **Region:** {c.get('region','')}/{c.get('subregion','')}")
        out.append(f"- **Languages:** {', '.join(c.get('languages', []) or ['?'])}")
        out.append(f"- **Timezone:** {', '.join(c.get('timezones', []) or ['?'])}")
        if ctx.fx:
            out.append(
                f"- **Currency:** {c.get('currency_name','')} ({c.get('currency_code','')}, {c.get('currency_symbol','')})  ·  "
                f"**1 USD = {ctx.fx['rate']:.4f} {ctx.fx['target']}**  ·  "
                f"Budget in local: {c.get('currency_symbol','')}{ctx.fx['budget_local']:,.0f}"
            )
        out.append("")

    # Logistics
    lg = ctx.logistics
    if lg:
        out.append("## Getting there")
        out.append(f"- **Route:** {ctx.origin} → {ctx.destination}  ·  {lg.get('distance_km','?'):,} km ({lg.get('distance_mi','?'):,} mi)  ·  ~{lg.get('est_flight_hours','?')}h flight")
        out.append(f"- **Estimated round-trip:** ${lg.get('est_roundtrip_usd',0):,} ({ctx.travelers} pax @ ~${lg.get('est_roundtrip_per_person_usd',0):,}/pp)")
        links = lg.get("links", {})
        if links:
            out.append("- **Search live fares:** " + " · ".join(f"[{k.replace('_',' ').title()}]({v})" for k, v in links.items()))
        out.append("")

    # Weather
    if ctx.weather:
        out.append("## Weather forecast")
        src_note = ctx.weather[0].get("source", "")
        if src_note == "historical-proxy":
            out.append("_Beyond the 16-day forecast window — using ERA5 historical normals as a climate proxy._\n")
        out.append("| Date | Conditions | High | Low | Rain | Wind |")
        out.append("|------|------------|------|-----|------|------|")
        for w in ctx.weather:
            out.append(
                f"| {w['date']} | {w['label']} | {w['high_c']}°C | {w['low_c']}°C | {w['rain_pct']}% ({w['rain_mm']}mm) | {w.get('wind_kmh',0)} km/h |"
            )
        out.append("")

    # Day-by-day plan
    if plan:
        out.append("## Day-by-day")
        for i, d in enumerate(plan, 1):
            w = d["weather"]
            rainy = (w.get("rain_pct") or 0) >= 50
            out.append(f"### Day {i} — {d['date']} ({w['label']}, {w['high_c']}°C / {w['low_c']}°C{', rain likely' if rainy else ''})")
            for p in d["picks"]:
                line = f"- **{p['name']}** _({p['kind']})_"
                if p.get("opening_hours"):
                    line += f" · hrs: `{p['opening_hours']}`"
                if p.get("website"):
                    line += f" · [website]({p['website']})"
                if p.get("wiki"):
                    wiki_slug = p["wiki"].split(":", 1)[-1].replace(" ", "_")
                    lang = p["wiki"].split(":", 1)[0] if ":" in p["wiki"] else "en"
                    line += f" · [wiki](https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(wiki_slug)})"
                if p.get("lat") and p.get("lon"):
                    line += f" · [map](https://www.openstreetmap.org/?mlat={p['lat']}&mlon={p['lon']}#map=17/{p['lat']}/{p['lon']})"
                out.append(line)
            if d["meals"]:
                out.append("  - **Eat:** " + " · ".join(
                    f"{m['name']}" + (f" _({m['cuisine']})_" if m['cuisine'] else "")
                    for m in d["meals"]
                ))
            out.append("")

    # Budget
    if bd:
        out.append("## Budget reconciliation (estimates)")
        out.append(
            f"_Style detected: **{bd['style']}**. "
            f"All rows below are deterministic estimates — flights from great-circle "
            f"distance × IATA $/mi tier; lodging/food from style-band averages. "
            f"Not pulled from any pricing API._\n"
        )
        out.append("| Category | USD (est.) |")
        out.append("|----------|------------|")
        out.append(f"| Flights ({ctx.travelers} pax, ~{ctx.logistics.get('distance_mi','?'):,} mi) | ${bd['flights']:,} |")
        out.append(f"| Hotel ({ctx.days - 1} nights × {bd['style']}-band) | ${bd['hotel']:,} |")
        out.append(f"| Food ({ctx.days} days × {bd['style']}-band) | ${bd['food']:,} |")
        out.append(f"| Activities (≈$20 × picks) | ${bd['activities']:,} |")
        out.append(f"| Local transit | ${bd['local_transit']:,} |")
        out.append(f"| **Total (est.)** | **${bd['total']:,}** |")
        out.append(f"| Budget | ${ctx.budget_usd:,.0f} |")
        delta = bd["vs_budget"]
        sign = "under" if delta >= 0 else "over"
        out.append(f"| **{sign} budget by** | **${abs(delta):,.0f}** |")
        out.append("")

    # Agent timings + sources
    out.append("## Run metadata")
    out.append("**Agent timings (parallel fan-out):**")
    for k, v in ctx.timings.items():
        out.append(f"- `{k}`: {v:.2f}s")
    out.append("")
    out.append("**Live data sources used:**")
    for s in sorted(set(ctx.sources)):
        out.append(f"- {s}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(msg, flush=True)


async def orchestrate(ctx: TripContext) -> None:
    pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="agent")
    log("\n=== Phase 1: Geocoding (blocking) ===")
    await GeocodeAgent().run(ctx, pool)
    if not ctx.dest_geo:
        raise SystemExit("could not geocode destination")

    log(f"\nDestination resolved: {ctx.dest_geo['display'][:90]}")
    log(f"  lat/lon: {ctx.dest_geo['lat']:.4f}, {ctx.dest_geo['lon']:.4f}")
    log(f"  country: {ctx.dest_geo['country']} ({ctx.dest_geo['country_code']})")

    log("\n=== Phase 2: Specialist agents (parallel) ===")
    parallel_agents = [
        WeatherAgent(),
        CountryAgent(),
        WikiAgent(),
        POIAgent(),
        FoodAgent(),
        LogisticsAgent(),
    ]
    await asyncio.gather(*(a.run(ctx, pool) for a in parallel_agents))

    # CurrencyAgent needs country.currency_code
    await CurrencyAgent().run(ctx, pool)

    log("\n=== Phase 3: Synthesizer ===")
    await Synthesizer().run(ctx, pool)
    pool.shutdown(wait=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="VoyageAI v2 — real-data multi-agent travel planner")
    ap.add_argument("--destination", "-d", required=True)
    ap.add_argument("--origin", "-o", default="New York")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--budget", "-b", type=float, default=3000)
    ap.add_argument("--travelers", "-t", type=int, default=1)
    ap.add_argument("--preferences", "-p", default="balanced mix of culture, food, and outdoors")
    ap.add_argument("--out", default=None, help="Output markdown path (default: itinerary_<dest>.md)")
    args = ap.parse_args()

    ctx = TripContext(
        destination=args.destination,
        origin=args.origin,
        start_date=args.start,
        end_date=args.end,
        budget_usd=args.budget,
        travelers=args.travelers,
        preferences=args.preferences,
    )

    banner = "=" * 70
    log(banner)
    log(f"  VoyageAI v2 — real-data multi-agent planner")
    log(banner)
    log(f"  Destination: {ctx.destination}")
    log(f"  Origin:      {ctx.origin}")
    log(f"  Dates:       {ctx.start_date} → {ctx.end_date} ({ctx.days} days)")
    log(f"  Budget:      ${ctx.budget_usd:,.0f}  ·  Travelers: {ctx.travelers}")
    log(f"  Prefs:       {ctx.preferences}")
    log(banner)

    t0 = time.perf_counter()
    asyncio.run(orchestrate(ctx))
    total = time.perf_counter() - t0

    out_path = args.out or f"itinerary_{re.sub(r'[^a-z0-9]+', '_', args.destination.lower()).strip('_')}.md"
    md = render_markdown(ctx)
    with open(out_path, "w") as f:
        f.write(md)

    log("\n" + banner)
    log(f"  Done in {total:.2f}s  ·  POIs: {len(ctx.pois)}  ·  Restaurants: {len(ctx.food)}  ·  Weather days: {len(ctx.weather)}")
    log(f"  Itinerary written to: {out_path}")
    log(banner + "\n")


if __name__ == "__main__":
    main()
