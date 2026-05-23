"""VoyageAI v2 — animated web frontend with D3 visualisations and Leaflet map.

Wraps voyage_real.orchestrate behind a stdlib HTTP server. The browser opens
/stream as an EventSource:

  1. Each agent card pulses while running, then turns green with a one-line
     live summary when done.
  2. Once the synthesizer fires, the SSE 'done' event carries the full JSON
     payload, and the frontend builds:
       - hero card with the destination's Wikipedia image as the background
       - radial D3 SVG of agent timings (proportional arcs)
       - D3 line+bar chart of the live weather forecast
       - D3 donut of the deterministic budget estimate
       - D3 world map with an animated great-circle arc from origin to dest
       - Leaflet map showing every real POI + restaurant returned by Overpass
       - day-by-day card list with weather chips, real POIs, real restaurants

No mock data, no LLM, no API keys.

Run:   python3 voyage_web.py [--port 8765]
Open:  http://localhost:8765/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import queue
import sys
import threading
import time
import traceback
import urllib.parse
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voyage_real as vr  # noqa: E402


AGENTS = [
    {"name": "geocode",     "emoji": "📍", "label": "Geocode",      "blurb": "Nominatim · OSM",       "phase": 1},
    {"name": "weather",     "emoji": "🌤️",  "label": "Weather",     "blurb": "Open-Meteo",            "phase": 2},
    {"name": "country",     "emoji": "🌐",  "label": "Country",     "blurb": "REST Countries",        "phase": 2},
    {"name": "wiki",        "emoji": "📖",  "label": "Wiki",        "blurb": "Wikipedia REST",        "phase": 2},
    {"name": "poi",         "emoji": "🗿",  "label": "Attractions", "blurb": "Overpass · OSM",        "phase": 2},
    {"name": "food",        "emoji": "🍜",  "label": "Restaurants", "blurb": "Overpass · OSM",        "phase": 2},
    {"name": "logistics",   "emoji": "✈️",   "label": "Logistics",  "blurb": "Great-circle + tier",   "phase": 2},
    {"name": "currency",    "emoji": "💱",  "label": "Currency",    "blurb": "open.er-api.com",       "phase": 3},
    {"name": "synthesizer", "emoji": "🧭",  "label": "Synthesizer", "blurb": "Day-by-day planner",    "phase": 4},
]


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>VoyageAI v2 — live multi-agent travel planner</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="https://d3js.org/topojson.v3.min.js"></script>
<script src="https://d3js.org/d3-geo.v3.min.js"></script>
<style>
:root{
  --primary:#667eea; --primary-dark:#5a67d8; --secondary:#764ba2; --accent:#f093fb;
  --bg:#0a0a1e; --bg-light:#15153a; --bg-card:#1a1a3d;
  --text:#e2e8f0; --text-light:#a0aec0; --text-bright:#fff;
  --border:rgba(102,126,234,.22);
  --good:#48bb78; --warn:#ecc94b; --bad:#f56565; --info:#7cd1ff;
  --gradient:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
  --gradient-accent:linear-gradient(135deg,#f093fb 0%,#f5576c 100%);
  --radius:16px;
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;overflow-x:hidden;min-height:100vh}
.bg-gradient{position:fixed;inset:0;z-index:-2;background:
  radial-gradient(ellipse at 20% 20%,rgba(102,126,234,.18) 0%,transparent 60%),
  radial-gradient(ellipse at 80% 30%,rgba(118,75,162,.18) 0%,transparent 60%),
  radial-gradient(ellipse at 50% 90%,rgba(240,147,251,.12) 0%,transparent 60%);}
.bg-stars{position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.4}
.container{max-width:1280px;margin:0 auto;padding:0 1.6rem}
header{padding:2.5rem 0 .8rem;display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;flex-wrap:wrap}
.brand{font-size:2.1rem;font-weight:900;letter-spacing:-.02em;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.brand-sub{color:var(--text-light);font-weight:500;font-size:1rem;margin-left:.4rem}
.hero-badge{display:inline-flex;align-items:center;gap:.5rem;background:rgba(102,126,234,.15);border:1px solid var(--border);border-radius:30px;padding:.35rem 1rem;font-size:.78rem;color:var(--info);font-weight:500}
.hero-badge .dot{width:7px;height:7px;border-radius:50%;background:var(--good);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(72,187,120,.6)}50%{opacity:.55;box-shadow:0 0 0 10px rgba(72,187,120,0)}}
.tagline{color:var(--text-light);max-width:720px;font-size:.95rem;margin-top:.6rem}

.card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:1.4rem;box-shadow:0 4px 30px rgba(0,0,0,.25);position:relative;overflow:hidden}
.card h3.section{font-size:.78rem;color:var(--text-light);text-transform:uppercase;letter-spacing:.12em;font-weight:700;margin-bottom:.9rem;display:flex;align-items:center;gap:.5rem}
.card h3.section::before{content:'';width:5px;height:5px;border-radius:50%;background:var(--accent)}

/* Form */
form{display:grid;grid-template-columns:repeat(12,1fr);gap:.85rem}
label{font-size:.7rem;color:var(--text-light);text-transform:uppercase;letter-spacing:.08em;font-weight:600;display:block;margin-bottom:.3rem}
input{width:100%;padding:.62rem .82rem;background:rgba(0,0,0,.32);color:var(--text-bright);border:1px solid var(--border);border-radius:10px;font:inherit;font-size:.94rem;transition:border-color .2s,box-shadow .2s}
input:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px rgba(102,126,234,.2)}
.col-dest{grid-column:span 4}.col-orig{grid-column:span 4}
.col-start{grid-column:span 2}.col-end{grid-column:span 2}
.col-tr{grid-column:span 2}.col-bud{grid-column:span 2}
.col-pref{grid-column:span 8}.col-submit{grid-column:span 12;display:flex;gap:.9rem;align-items:center;flex-wrap:wrap}
@media(max-width:760px){.col-dest,.col-orig,.col-pref{grid-column:span 12}.col-start,.col-end,.col-tr,.col-bud{grid-column:span 6}}
button.primary{background:var(--gradient);color:white;border:0;padding:.8rem 1.5rem;border-radius:10px;font-weight:700;font-size:.94rem;cursor:pointer;transition:transform .15s,filter .15s,box-shadow .2s;font-family:inherit;box-shadow:0 4px 20px rgba(102,126,234,.3)}
button.primary:hover{transform:translateY(-1px);filter:brightness(1.08);box-shadow:0 8px 28px rgba(102,126,234,.45)}
button.primary:active{transform:translateY(0)}
button.primary:disabled{opacity:.55;cursor:wait}
.samples{color:var(--text-light);font-size:.85rem;display:flex;gap:.55rem;flex-wrap:wrap}
.samples a{color:var(--accent);text-decoration:none;padding:.3rem .75rem;background:rgba(240,147,251,.08);border:1px solid rgba(240,147,251,.22);border-radius:999px;transition:all .15s;font-weight:500;font-size:.84rem}
.samples a:hover{background:rgba(240,147,251,.18);transform:translateY(-1px);border-color:rgba(240,147,251,.4)}

/* Status pills */
.status-row{display:flex;gap:.7rem;flex-wrap:wrap;margin-top:1rem;align-items:center}
.pill{display:inline-flex;align-items:center;gap:.4rem;padding:.3rem .75rem;border-radius:999px;background:rgba(102,126,234,.12);border:1px solid var(--border);font-size:.8rem;color:var(--text);font-weight:500;font-family:'JetBrains Mono',monospace}
.pill.live::before{content:'';width:7px;height:7px;border-radius:50%;background:var(--good);animation:pulse 1.4s infinite}
.pill.done{background:rgba(72,187,120,.12);border-color:rgba(72,187,120,.3);color:#9ae6b4}

/* Agent radial flow */
.flow-wrap{display:grid;grid-template-columns:380px 1fr;gap:1.2rem;margin-top:1.2rem;align-items:start}
@media(max-width:900px){.flow-wrap{grid-template-columns:1fr}}
#agentDiagram{width:100%;height:380px;display:block}
.agent-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:.7rem}
.agent{background:rgba(0,0,0,.28);border:1px solid var(--border);border-radius:12px;padding:.75rem .9rem;position:relative;overflow:hidden;transition:all .35s cubic-bezier(.4,0,.2,1);opacity:.5}
.agent::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:#3a3a5a;transition:background .3s}
.agent.running{opacity:1;border-color:rgba(102,126,234,.5);box-shadow:0 0 0 1px rgba(102,126,234,.3),0 6px 22px rgba(102,126,234,.22)}
.agent.running::before{background:var(--primary);box-shadow:0 0 12px var(--primary)}
.agent.running .ico{animation:spin 1.4s linear infinite}
.agent.done{opacity:1;border-color:rgba(72,187,120,.35)}
.agent.done::before{background:var(--good)}
.agent.error{opacity:1;border-color:rgba(245,101,101,.45)}
.agent.error::before{background:var(--bad)}
@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
.agent .top{display:flex;align-items:center;gap:.55rem}
.agent .ico{font-size:1.25rem;width:32px;height:32px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.04);border-radius:8px;flex-shrink:0}
.agent .name{font-weight:700;color:var(--text-bright);font-size:.88rem;line-height:1.1}
.agent .blurb{color:var(--text-light);font-size:.66rem;text-transform:uppercase;letter-spacing:.06em;margin-top:.05rem}
.agent .summary{margin-top:.55rem;font-size:.74rem;color:var(--text-light);min-height:.9rem;font-family:'JetBrains Mono',monospace;line-height:1.35;word-break:break-word}
.agent .dur{position:absolute;top:.55rem;right:.7rem;font-size:.66rem;color:var(--text-light);font-family:'JetBrains Mono',monospace;background:rgba(0,0,0,.4);padding:.08rem .35rem;border-radius:5px;opacity:0;transition:opacity .3s}
.agent.done .dur,.agent.error .dur{opacity:1}
.agent.done .dur{color:#9ae6b4}

/* Hero */
#hero{position:relative;margin-top:1.6rem;border-radius:var(--radius);overflow:hidden;min-height:280px;display:none;animation:fadeIn .6s ease}
#hero.active{display:block}
#heroImg{position:absolute;inset:0;background-size:cover;background-position:center;filter:brightness(.5) saturate(1.1);transition:filter .6s}
#hero::after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(10,10,30,.2) 0%,rgba(10,10,30,.85) 100%)}
.hero-content{position:relative;z-index:2;padding:2rem 2.2rem;display:flex;flex-direction:column;justify-content:flex-end;min-height:280px}
.hero-content h2{font-size:clamp(1.8rem,4vw,2.8rem);font-weight:900;letter-spacing:-.02em;color:white;margin-bottom:.4rem;line-height:1.05;text-shadow:0 2px 20px rgba(0,0,0,.6)}
.hero-meta{display:flex;gap:1rem;flex-wrap:wrap;color:rgba(255,255,255,.92);font-size:.95rem;font-weight:500}
.hero-meta span{background:rgba(0,0,0,.35);padding:.3rem .8rem;border-radius:999px;backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.1)}
.hero-extract{margin-top:1rem;color:rgba(255,255,255,.78);max-width:760px;font-size:.92rem;line-height:1.55}
.hero-extract a{color:var(--accent);text-decoration:none}

/* Visual grid */
.viz-grid{display:grid;grid-template-columns:repeat(12,1fr);gap:1.2rem;margin-top:1.2rem}
.viz-grid > .card{display:none}
.viz-grid.active > .card{display:block;animation:fadeIn .55s ease both}
@keyframes fadeIn{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
.span4{grid-column:span 4}.span6{grid-column:span 6}.span8{grid-column:span 8}.span12{grid-column:span 12}
@media(max-width:980px){.span4,.span6,.span8{grid-column:span 12}}

/* Globe */
#globeWrap{position:relative;height:300px}
#globeSvg{width:100%;height:100%}
.globe-sphere{fill:#0c0f24;stroke:rgba(102,126,234,.35);stroke-width:.8}
.globe-graticule{fill:none;stroke:rgba(102,126,234,.16);stroke-width:.5}
.globe-land{fill:rgba(118,75,162,.35);stroke:rgba(255,255,255,.07);stroke-width:.4;transition:fill .3s}
.globe-arc{fill:none;stroke:url(#arcGrad);stroke-width:2.5;stroke-linecap:round;filter:drop-shadow(0 0 5px rgba(240,147,251,.6))}
.globe-city{fill:var(--accent);filter:drop-shadow(0 0 8px var(--accent))}
.globe-city.origin{fill:var(--info);filter:drop-shadow(0 0 8px var(--info))}
.globe-label{fill:white;font:600 11px 'Inter';text-shadow:0 0 4px rgba(0,0,0,.8);pointer-events:none}
.globe-route-label{position:absolute;top:.7rem;right:.7rem;color:var(--text-light);font-size:.78rem;font-family:'JetBrains Mono',monospace;background:rgba(0,0,0,.4);padding:.25rem .55rem;border-radius:8px;backdrop-filter:blur(6px)}

/* Weather chart */
#weatherSvg{width:100%;height:200px}
.wx-rain{fill:rgba(124,209,255,.35)}
.wx-rain-hover{fill:rgba(124,209,255,.7)}
.wx-high{stroke:#f56565;stroke-width:2.2;fill:none}
.wx-low{stroke:#7cd1ff;stroke-width:2.2;fill:none;stroke-dasharray:3,3}
.wx-area{fill:url(#wxArea);opacity:.4}
.wx-dot{fill:#fff;stroke:#f56565;stroke-width:2}
.wx-dot-low{fill:#fff;stroke:#7cd1ff;stroke-width:2}
.wx-label{fill:var(--text-light);font:11px 'JetBrains Mono';text-anchor:middle}
.wx-axis text{fill:var(--text-light);font:10px 'JetBrains Mono'}
.wx-axis line, .wx-axis path{stroke:rgba(255,255,255,.1)}
.wx-tooltip{position:absolute;background:rgba(0,0,0,.92);border:1px solid var(--border);padding:.55rem .8rem;border-radius:8px;font-size:.78rem;pointer-events:none;opacity:0;transition:opacity .15s;z-index:10;font-family:'JetBrains Mono',monospace;max-width:200px}

/* Budget donut */
#budgetSvg{width:100%;height:240px}
.donut-arc{stroke:var(--bg-card);stroke-width:2;transition:transform .2s,opacity .2s;cursor:pointer;transform-origin:center}
.donut-arc:hover{transform:scale(1.04);opacity:.92}
.donut-center{text-anchor:middle;dominant-baseline:central}
.donut-center .big{fill:white;font:800 22px 'Inter'}
.donut-center .small{fill:var(--text-light);font:500 10px 'Inter';text-transform:uppercase;letter-spacing:.1em}
.legend{display:grid;grid-template-columns:1fr 1fr;gap:.4rem;margin-top:1rem;font-size:.8rem}
.legend-item{display:flex;align-items:center;gap:.5rem;color:var(--text-light)}
.legend-swatch{width:11px;height:11px;border-radius:3px;flex-shrink:0}
.legend-amt{margin-left:auto;color:white;font-family:'JetBrains Mono',monospace;font-size:.75rem}

/* Leaflet map */
#poiMap{height:480px;width:100%;border-radius:12px;background:#0c0f24}
.leaflet-container{background:#0c0f24!important;font:inherit!important}
.leaflet-popup-content-wrapper{background:rgba(20,20,50,.96)!important;color:var(--text)!important;border:1px solid var(--border);border-radius:10px;box-shadow:0 6px 22px rgba(0,0,0,.4)}
.leaflet-popup-tip{background:rgba(20,20,50,.96)!important}
.leaflet-popup-content{margin:.6rem .8rem!important;font-size:.85rem!important}
.leaflet-popup-content a{color:var(--accent)}
.leaflet-control-attribution{background:rgba(0,0,0,.5)!important;color:var(--text-light)!important;font-size:9px!important}
.leaflet-control-attribution a{color:var(--info)!important}
.poi-marker{border-radius:50%;border:2px solid white;box-shadow:0 0 0 1px rgba(0,0,0,.4),0 0 10px rgba(0,0,0,.4)}
.map-filters{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.8rem;font-size:.78rem}
.map-filter{padding:.28rem .7rem;border-radius:999px;background:rgba(0,0,0,.28);border:1px solid var(--border);cursor:pointer;color:var(--text-light);transition:all .15s;user-select:none;font-weight:500}
.map-filter.active{background:rgba(102,126,234,.25);border-color:var(--primary);color:white}
.map-filter:hover{transform:translateY(-1px)}
.map-counts{margin-left:auto;color:var(--text-light);font-family:'JetBrains Mono',monospace;font-size:.78rem;display:flex;align-items:center;gap:.4rem}

/* Day cards */
#daysWrap{display:grid;grid-template-columns:1fr;gap:.8rem;margin-top:1rem}
.day-card{background:rgba(0,0,0,.25);border:1px solid var(--border);border-radius:14px;padding:1.1rem 1.3rem;animation:fadeIn .5s ease both;transition:all .25s}
.day-card:hover{border-color:rgba(102,126,234,.5);transform:translateX(3px)}
.day-head{display:flex;align-items:center;gap:1rem;margin-bottom:.8rem;flex-wrap:wrap}
.day-num{background:var(--gradient);color:white;font-weight:800;width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:.85rem;flex-shrink:0}
.day-date{font-weight:700;color:var(--text-bright);font-size:1rem}
.day-wx{display:inline-flex;align-items:center;gap:.4rem;background:rgba(102,126,234,.1);border:1px solid var(--border);padding:.2rem .65rem;border-radius:999px;font-size:.76rem;color:var(--text-light);font-family:'JetBrains Mono',monospace}
.day-wx.rainy{background:rgba(124,209,255,.12);border-color:rgba(124,209,255,.3);color:#bee0fd}
.day-pois{display:grid;grid-template-columns:1fr;gap:.5rem;padding-left:50px}
.day-poi{display:flex;align-items:flex-start;gap:.7rem;padding:.55rem .7rem;background:rgba(255,255,255,.02);border-radius:8px;border:1px solid transparent;transition:all .2s;cursor:pointer}
.day-poi:hover{background:rgba(102,126,234,.08);border-color:rgba(102,126,234,.2);transform:translateX(2px)}
.day-poi .pico{font-size:1.05rem;width:30px;flex-shrink:0;text-align:center}
.day-poi .pmid{flex:1;min-width:0}
.day-poi .ptitle{color:white;font-weight:600;font-size:.9rem;line-height:1.25}
.day-poi .pmeta{color:var(--text-light);font-size:.74rem;font-family:'JetBrains Mono',monospace;margin-top:.15rem}
.day-poi .plinks{display:flex;gap:.5rem;flex-wrap:wrap}
.day-poi .plinks a{color:var(--accent);text-decoration:none;font-size:.74rem;background:rgba(240,147,251,.08);padding:.15rem .45rem;border-radius:5px;border:1px solid rgba(240,147,251,.2);transition:background .15s}
.day-poi .plinks a:hover{background:rgba(240,147,251,.2)}
.day-meals{padding-left:50px;margin-top:.6rem;color:var(--text-light);font-size:.82rem}
.day-meals strong{color:#9ae6b4}

/* Sources strip */
.sources-strip{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:1rem;padding-top:1rem;border-top:1px solid var(--border)}
.source-chip{font-size:.7rem;color:var(--text-light);background:rgba(0,0,0,.3);padding:.2rem .55rem;border-radius:5px;font-family:'JetBrains Mono',monospace;border:1px solid var(--border)}

footer{padding:2rem 0;text-align:center;color:var(--text-light);font-size:.82rem;margin-top:2rem}
footer a{color:var(--accent);text-decoration:none}
.fact-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:.7rem;margin-top:.4rem}
.fact{background:rgba(0,0,0,.25);border:1px solid var(--border);border-radius:10px;padding:.7rem .85rem}
.fact .k{color:var(--text-light);font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.2rem;font-weight:600}
.fact .v{color:white;font-weight:600;font-size:.92rem;font-family:'JetBrains Mono',monospace}
.flag-big{font-size:1.6rem;margin-right:.4rem;vertical-align:middle}
</style>
</head>
<body>
<div class="bg-gradient"></div>
<canvas class="bg-stars" id="stars"></canvas>
<div class="container">

<header>
  <div>
    <div class="brand">VoyageAI v2<span class="brand-sub">— live multi-agent planner</span></div>
    <div class="tagline">9 agents, parallel asyncio fan-out, real data from 6 keyless public APIs. Watch them fire below.</div>
  </div>
  <div class="hero-badge"><span class="dot"></span> all live data · zero LLM keys</div>
</header>

<div class="card">
  <h3 class="section">Plan a trip</h3>
  <form id="planForm">
    <div class="col-dest"><label>Destination</label><input name="destination" value="Tokyo" required></div>
    <div class="col-orig"><label>Origin</label><input name="origin" value="San Francisco"></div>
    <div class="col-start"><label>Start</label><input name="start" type="date" value="__S1__" required></div>
    <div class="col-end"><label>End</label><input name="end" type="date" value="__E1__" required></div>
    <div class="col-tr"><label>Travelers</label><input name="travelers" type="number" min="1" max="20" value="2"></div>
    <div class="col-bud"><label>Budget USD</label><input name="budget" type="number" min="100" step="100" value="3500"></div>
    <div class="col-pref"><label>Preferences</label><input name="preferences" value="balanced mix of culture, food, and outdoors"></div>
    <div class="col-submit">
      <button class="primary" id="planBtn" type="submit">Plan trip →</button>
      <div class="samples">
        <a href="#" data-q="Tokyo|San Francisco|__S1__|__E1__|3500|2|balanced mix of culture food and outdoors">Tokyo 6d</a>
        <a href="#" data-q="Lisbon|New York|__S1__|__E2__|2200|2|budget-friendly food-focused walking">Lisbon 7d</a>
        <a href="#" data-q="Barcelona|London|__S1__|__E1__|2800|2|tapas architecture beach">Barcelona 6d</a>
        <a href="#" data-q="Mexico City|Chicago|__S1__|__E3__|1500|1|street food museums">CDMX 5d</a>
        <a href="#" data-q="Reykjavik|New York|__S1__|__E1__|2500|2|northern lights nature">Reykjavik 6d</a>
        <a href="#" data-q="Marrakech|Paris|__S1__|__E2__|1800|2|souks food">Marrakech 7d</a>
      </div>
    </div>
  </form>

  <div class="status-row" id="statusRow" style="display:none">
    <span class="pill live" id="pillStatus">Agents firing…</span>
    <span class="pill" id="pillTime">0.00s</span>
    <span class="pill" id="pillDone">0 / __NAGENTS__ done</span>
  </div>

  <div class="flow-wrap" id="flowWrap" style="display:none">
    <svg id="agentDiagram" viewBox="0 0 380 380"></svg>
    <div class="agent-list" id="agentList"></div>
  </div>
</div>

<div id="hero">
  <div id="heroImg"></div>
  <div class="hero-content">
    <h2 id="heroTitle">—</h2>
    <div class="hero-meta" id="heroMeta"></div>
    <div class="hero-extract" id="heroExtract"></div>
  </div>
</div>

<div class="viz-grid" id="vizGrid">

  <div class="card span6">
    <h3 class="section">Country snapshot</h3>
    <div id="countryFacts" class="fact-grid"></div>
  </div>

  <div class="card span6">
    <h3 class="section">Origin → destination</h3>
    <div id="globeWrap">
      <svg id="globeSvg"></svg>
      <div class="globe-route-label" id="routeLabel"></div>
    </div>
  </div>

  <div class="card span8">
    <h3 class="section">Live weather forecast (Open-Meteo)</h3>
    <svg id="weatherSvg"></svg>
    <div class="wx-tooltip" id="wxTooltip"></div>
  </div>

  <div class="card span4">
    <h3 class="section">Estimated budget breakdown</h3>
    <svg id="budgetSvg"></svg>
    <div class="legend" id="budgetLegend"></div>
  </div>

  <div class="card span12">
    <h3 class="section">Real POIs &amp; restaurants from OpenStreetMap (Overpass)</h3>
    <div id="poiMap"></div>
    <div class="map-filters" id="mapFilters">
      <span class="map-filter active" data-cat="all">All</span>
      <span class="map-filter" data-cat="poi">Attractions</span>
      <span class="map-filter" data-cat="museum">Museums &amp; galleries</span>
      <span class="map-filter" data-cat="viewpoint">Viewpoints</span>
      <span class="map-filter" data-cat="historic">Historic</span>
      <span class="map-filter" data-cat="food">Restaurants</span>
      <span class="map-counts" id="mapCounts"></span>
    </div>
  </div>

  <div class="card span12">
    <h3 class="section">Day-by-day plan (weather-aware)</h3>
    <div id="daysWrap"></div>
    <div class="sources-strip" id="sourcesStrip"></div>
  </div>

</div>
</div>

<footer>
  Built atop <a href="https://github.com/sugeerth/agentic_data">sugeerth/agentic_data</a> · every fact on this page came from a live public API call · zero mock data
</footer>

<script>
// ---- starfield ----
(function(){const c=document.getElementById('stars'),x=c.getContext('2d');function resize(){c.width=innerWidth;c.height=innerHeight;}resize();addEventListener('resize',resize);const N=80,stars=Array.from({length:N},()=>({x:Math.random()*c.width,y:Math.random()*c.height,r:Math.random()*1.2+.3,a:Math.random(),da:(Math.random()-.5)*.012}));function tick(){x.clearRect(0,0,c.width,c.height);for(const s of stars){s.a+=s.da;if(s.a<.1||s.a>.9)s.da=-s.da;x.fillStyle='rgba(255,255,255,'+s.a.toFixed(3)+')';x.beginPath();x.arc(s.x,s.y,s.r,0,7);x.fill();}requestAnimationFrame(tick);}tick();})();

const AGENTS = __AGENTS_JSON__;
const flowWrap = document.getElementById('flowWrap');
const agentList = document.getElementById('agentList');
const diagram = d3.select('#agentDiagram');
const statusRow = document.getElementById('statusRow');
const pillStatus = document.getElementById('pillStatus');
const pillTime = document.getElementById('pillTime');
const pillDone = document.getElementById('pillDone');
const planBtn = document.getElementById('planBtn');
const vizGrid = document.getElementById('vizGrid');
const hero = document.getElementById('hero');
const tooltip = document.getElementById('wxTooltip');

// ---- agent cards ----
function renderAgentList(){
  agentList.innerHTML = '';
  AGENTS.forEach(a=>{
    const el = document.createElement('div');
    el.className = 'agent pending';
    el.id = 'agent-' + a.name;
    el.innerHTML = `<div class="dur" id="dur-${a.name}"></div>
      <div class="top"><div class="ico">${a.emoji}</div>
        <div><div class="name">${a.label}</div><div class="blurb">${a.blurb}</div></div></div>
      <div class="summary" id="summary-${a.name}">queued</div>`;
    agentList.appendChild(el);
  });
}

// ---- radial diagram (supervisor center, agents around ring) ----
function renderRadial(){
  const W=380,H=380,R=130;
  diagram.selectAll('*').remove();
  const g = diagram.append('g').attr('transform',`translate(${W/2},${H/2})`);
  // defs
  const defs = diagram.append('defs');
  const rg = defs.append('radialGradient').attr('id','centerGrad');
  rg.append('stop').attr('offset','0%').attr('stop-color','#f093fb');
  rg.append('stop').attr('offset','100%').attr('stop-color','#5a67d8');

  // outer ring
  g.append('circle').attr('r',R+20).attr('fill','none').attr('stroke','rgba(102,126,234,.12)').attr('stroke-dasharray','2,4');
  g.append('circle').attr('r',R-30).attr('fill','none').attr('stroke','rgba(102,126,234,.08)');

  // connection lines (drawn first so they're under nodes)
  const N = AGENTS.length;
  AGENTS.forEach((a,i)=>{
    const ang = (i / N) * Math.PI * 2 - Math.PI/2;
    const x = Math.cos(ang) * R, y = Math.sin(ang) * R;
    g.append('line').attr('class','radial-line').attr('id','line-'+a.name)
      .attr('x1',0).attr('y1',0).attr('x2',x).attr('y2',y)
      .attr('stroke','rgba(102,126,234,.18)').attr('stroke-width',1).attr('stroke-dasharray','3,3');
  });
  // center supervisor
  g.append('circle').attr('r',32).attr('fill','url(#centerGrad)').attr('filter','drop-shadow(0 0 14px rgba(118,75,162,.55))');
  g.append('text').attr('text-anchor','middle').attr('dy','.36em').attr('fill','#fff').style('font','700 11px Inter').text('Supervisor');

  // agent nodes
  AGENTS.forEach((a,i)=>{
    const ang = (i / N) * Math.PI * 2 - Math.PI/2;
    const x = Math.cos(ang) * R, y = Math.sin(ang) * R;
    const ng = g.append('g').attr('id','rnode-'+a.name).attr('transform',`translate(${x},${y})`).attr('class','radial-node');
    ng.append('circle').attr('class','rnode-pulse').attr('r',26).attr('fill','rgba(102,126,234,.12)').attr('stroke','rgba(102,126,234,.4)').attr('stroke-width',1).style('opacity',.5);
    ng.append('circle').attr('class','rnode-core').attr('r',18).attr('fill','rgba(15,15,40,.95)').attr('stroke','rgba(102,126,234,.5)').attr('stroke-width',1.5);
    ng.append('text').attr('text-anchor','middle').attr('dy','.36em').style('font','16px sans-serif').text(a.emoji);
    // labels outside
    const lx = Math.cos(ang) * (R+38), ly = Math.sin(ang) * (R+38);
    ng.append('text').attr('x',lx-x).attr('y',ly-y).attr('text-anchor','middle').attr('dy','.36em').attr('fill','#a0aec0').style('font','600 9.5px Inter').style('text-transform','uppercase').style('letter-spacing','.06em').text(a.label);
  });
}

function setAgent(name, status, payload){
  // list card
  const el = document.getElementById('agent-'+name);
  if(el){
    el.classList.remove('pending','running','done','error');
    el.classList.add(status);
    const sum = document.getElementById('summary-'+name);
    const dur = document.getElementById('dur-'+name);
    if(status==='running') sum.textContent='running…';
    if(status==='done'){ sum.textContent = payload.summary||'done'; dur.textContent=payload.duration.toFixed(2)+'s'; }
    if(status==='error'){ sum.textContent = payload.error||'error'; dur.textContent=payload.duration.toFixed(2)+'s'; }
  }
  // radial node
  const core = diagram.select('#rnode-'+name+' .rnode-core');
  const pulse = diagram.select('#rnode-'+name+' .rnode-pulse');
  const line = diagram.select('#line-'+name);
  if(status==='running'){
    core.transition().duration(300).attr('fill','rgba(102,126,234,.7)').attr('stroke','#fff').attr('r',22);
    pulse.transition().duration(300).style('opacity',.9).attr('r',32);
    pulse.append('animate').attr('attributeName','r').attr('from',26).attr('to',38).attr('dur','1.3s').attr('repeatCount','indefinite');
    line.transition().duration(300).attr('stroke','rgba(102,126,234,.7)').attr('stroke-width',2).attr('stroke-dasharray','none');
  } else if(status==='done'){
    core.transition().duration(300).attr('fill','rgba(72,187,120,.85)').attr('stroke','#9ae6b4').attr('r',18);
    pulse.transition().duration(300).style('opacity',.4).attr('r',26);
    pulse.selectAll('animate').remove();
    line.transition().duration(300).attr('stroke','rgba(72,187,120,.45)').attr('stroke-width',1.5).attr('stroke-dasharray','none');
  } else if(status==='error'){
    core.transition().duration(300).attr('fill','rgba(245,101,101,.75)').attr('stroke','#feb2b2');
    line.transition().duration(300).attr('stroke','rgba(245,101,101,.5)');
  }
}

// ---- timer ----
let startTime=0,timerId=null,doneCount=0;
function startTimer(){startTime=performance.now();timerId=setInterval(()=>{pillTime.textContent=((performance.now()-startTime)/1000).toFixed(2)+'s';},80);}
function stopTimer(){clearInterval(timerId);}

function reset(){
  renderAgentList();
  renderRadial();
  flowWrap.style.display='grid';
  statusRow.style.display='flex';
  vizGrid.classList.remove('active');
  vizGrid.querySelectorAll('.card').forEach(c=>{ if(c.id !== 'flowWrap') return; });
  hero.classList.remove('active');
  pillStatus.className='pill live';
  pillStatus.textContent='Agents firing…';
  pillDone.classList.remove('done');
  pillDone.textContent = `0 / ${AGENTS.length} done`;
  doneCount=0;
  document.getElementById('daysWrap').innerHTML='';
  if(window._poiMap){window._poiMap.remove();window._poiMap=null;}
}

// ---- main runner ----
function run(params){
  reset();
  startTimer();
  planBtn.disabled=true;
  const q = new URLSearchParams(params).toString();
  const es = new EventSource('/stream?'+q);
  es.addEventListener('agent', ev=>{
    const d = JSON.parse(ev.data);
    if(d.status==='start') setAgent(d.name,'running',d);
    else if(d.status==='done'){setAgent(d.name,'done',d); doneCount++; pillDone.textContent=`${doneCount} / ${AGENTS.length} done`;}
    else if(d.status==='error'){setAgent(d.name,'error',d); doneCount++; pillDone.textContent=`${doneCount} / ${AGENTS.length} done`;}
  });
  es.addEventListener('done', ev=>{
    stopTimer(); planBtn.disabled=false;
    pillStatus.className='pill done'; pillStatus.textContent='✓ Plan ready';
    pillDone.classList.add('done');
    const data = JSON.parse(ev.data);
    renderAll(data);
    es.close();
  });
  es.addEventListener('error', ev=>{ stopTimer(); planBtn.disabled=false; es.close(); });
}

// ---- rendering of full result ----
function renderAll(data){
  renderHero(data);
  renderCountry(data);
  renderGlobe(data);
  renderWeather(data);
  renderBudget(data);
  renderMap(data);
  renderDays(data);
  renderSources(data);
  vizGrid.classList.add('active');
  hero.scrollIntoView({behavior:'smooth',block:'start'});
}

function renderHero(d){
  const wiki = d.wiki || {};
  const img = wiki.image || '';
  document.getElementById('heroImg').style.backgroundImage = img ? `url(${img})` : 'linear-gradient(135deg,#667eea 0%,#764ba2 100%)';
  document.getElementById('heroTitle').textContent = `${d.destination} · ${d.days}-day plan`;
  const meta = document.getElementById('heroMeta');
  const flag = d.country?.flag||'';
  meta.innerHTML = `
    <span>${d.start} → ${d.end}</span>
    <span>${d.travelers} traveler(s)</span>
    <span>$${Number(d.budget_usd).toLocaleString()} budget</span>
    ${flag?`<span>${flag} ${escapeHtml(d.country?.name||'')}</span>`:''}
  `;
  const ext = document.getElementById('heroExtract');
  if(wiki.extract){
    const url = wiki.page_url ? ` <a href="${wiki.page_url}" target="_blank">source ↗</a>` : '';
    ext.innerHTML = escapeHtml(wiki.extract.slice(0,360)) + (wiki.extract.length>360?'…':'') + url;
  } else ext.innerHTML = '';
  hero.classList.add('active');
}

function renderCountry(d){
  const c = d.country||{}, fx = d.fx||{}, lg = d.logistics||{};
  const facts = [
    ['Capital', c.capital || '—'],
    ['Region', `${c.region||''} / ${c.subregion||''}`],
    ['Languages', (c.languages||[]).join(', ')||'—'],
    ['Timezone', (c.timezones||[]).join(', ')||'—'],
    ['Currency', `${c.currency_name||''} (${c.currency_symbol||''}${c.currency_code||''})`],
    ['FX live', fx.rate ? `1 USD = ${fx.rate.toFixed(4)} ${fx.target}` : '—'],
    ['Budget local', fx.budget_local ? `${c.currency_symbol||''}${Math.round(fx.budget_local).toLocaleString()}` : '—'],
    ['Distance', lg.distance_km ? `${lg.distance_km.toLocaleString()} km · ~${lg.est_flight_hours}h` : '—'],
  ];
  const fg = document.getElementById('countryFacts');
  fg.innerHTML = facts.map(([k,v])=>`<div class="fact"><div class="k">${k}</div><div class="v">${escapeHtml(String(v))}</div></div>`).join('');
}

// ---- D3 globe with great-circle arc ----
let worldCache = null;
async function loadWorld(){
  if(worldCache) return worldCache;
  const res = await fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json');
  worldCache = await res.json();
  return worldCache;
}
async function renderGlobe(d){
  const svg = d3.select('#globeSvg');
  svg.selectAll('*').remove();
  const rect = svg.node().getBoundingClientRect();
  const w=rect.width||600, h=rect.height||300;
  const oLat = d.origin_geo?.lat, oLon = d.origin_geo?.lon;
  const dLat = d.dest_geo?.lat, dLon = d.dest_geo?.lon;
  if(typeof oLat !== 'number' || typeof dLat !== 'number') return;
  const midLat = (oLat+dLat)/2, midLon = (oLon+dLon)/2;
  const projection = d3.geoOrthographic()
    .scale(Math.min(w,h)/2.3)
    .translate([w/2,h/2])
    .rotate([-midLon, -midLat]);
  const path = d3.geoPath().projection(projection);

  const defs = svg.append('defs');
  const lg = defs.append('linearGradient').attr('id','arcGrad').attr('x1','0%').attr('x2','100%');
  lg.append('stop').attr('offset','0%').attr('stop-color','#7cd1ff');
  lg.append('stop').attr('offset','100%').attr('stop-color','#f093fb');

  svg.append('path').attr('class','globe-sphere').attr('d', path({type:'Sphere'}));
  const graticule = d3.geoGraticule10();
  svg.append('path').attr('class','globe-graticule').attr('d', path(graticule));

  try {
    const world = await loadWorld();
    const land = topojson.feature(world, world.objects.countries);
    svg.append('path').attr('class','globe-land').attr('d', path(land));
  } catch(e){}

  // great-circle arc
  const arc = {type:'LineString', coordinates:[[oLon,oLat],[dLon,dLat]]};
  const arcPath = svg.append('path').attr('class','globe-arc').attr('d', path(arc));
  const len = arcPath.node().getTotalLength();
  arcPath.attr('stroke-dasharray', len+' '+len).attr('stroke-dashoffset', len)
    .transition().duration(1600).ease(d3.easeCubicInOut).attr('stroke-dashoffset', 0);

  // city dots
  function addCity(lat,lon,cls,label){
    const p = projection([lon,lat]); if(!p) return;
    svg.append('circle').attr('class','globe-city '+cls).attr('cx',p[0]).attr('cy',p[1]).attr('r',0)
      .transition().delay(900).duration(500).attr('r',5);
    svg.append('text').attr('class','globe-label').attr('x',p[0]+8).attr('y',p[1]-6).text(label)
      .style('opacity',0).transition().delay(1300).duration(400).style('opacity',1);
  }
  addCity(oLat,oLon,'origin', d.origin);
  addCity(dLat,dLon,'', d.destination);

  document.getElementById('routeLabel').textContent =
    `${d.logistics?.distance_km?.toLocaleString()||'?'} km · ~${d.logistics?.est_flight_hours||'?'}h flight`;
}

// ---- weather chart ----
function renderWeather(d){
  const svg = d3.select('#weatherSvg');
  svg.selectAll('*').remove();
  const rect = svg.node().getBoundingClientRect();
  const W = rect.width||700, H = 200;
  const margin = {top:18,right:24,bottom:30,left:36};
  const data = d.weather||[];
  if(!data.length){ svg.append('text').attr('x',W/2).attr('y',H/2).attr('class','wx-label').text('no weather data'); return; }

  const x = d3.scaleBand().domain(data.map(w=>w.date)).range([margin.left, W-margin.right]).padding(0.3);
  const yT = d3.scaleLinear().domain([d3.min(data,w=>w.low_c)-2, d3.max(data,w=>w.high_c)+2]).range([H-margin.bottom, margin.top]);
  const yR = d3.scaleLinear().domain([0, 100]).range([H-margin.bottom, margin.top]);

  // gradient area
  const defs = svg.append('defs');
  const lg = defs.append('linearGradient').attr('id','wxArea').attr('x1','0').attr('x2','0').attr('y1','0').attr('y2','1');
  lg.append('stop').attr('offset','0%').attr('stop-color','#f56565').attr('stop-opacity',.5);
  lg.append('stop').attr('offset','100%').attr('stop-color','#7cd1ff').attr('stop-opacity',.1);

  // rain bars (using rain_pct against yR axis)
  svg.append('g').selectAll('rect').data(data).join('rect')
    .attr('class','wx-rain')
    .attr('x', w=>x(w.date)).attr('width', x.bandwidth())
    .attr('y', w=>yR(w.rain_pct||0)).attr('height', w=>H-margin.bottom-yR(w.rain_pct||0))
    .on('mouseenter', function(e,w){
      d3.select(this).classed('wx-rain-hover', true);
      tooltip.style.opacity = 1;
      tooltip.innerHTML = `<strong>${w.date}</strong><br>${w.label}<br>${w.high_c}°C / ${w.low_c}°C<br>rain ${w.rain_pct||0}% (${w.rain_mm||0}mm)`;
    })
    .on('mousemove', function(e){
      tooltip.style.left = (e.pageX+12)+'px';
      tooltip.style.top = (e.pageY-12)+'px';
    })
    .on('mouseleave', function(){
      d3.select(this).classed('wx-rain-hover', false);
      tooltip.style.opacity = 0;
    });

  // area under high
  const areaGen = d3.area().curve(d3.curveCatmullRom)
    .x(w=>x(w.date)+x.bandwidth()/2).y0(yT.range()[0]).y1(w=>yT(w.high_c));
  svg.append('path').datum(data).attr('class','wx-area').attr('d', areaGen);

  // lines
  const lineHigh = d3.line().curve(d3.curveCatmullRom).x(w=>x(w.date)+x.bandwidth()/2).y(w=>yT(w.high_c));
  const lineLow = d3.line().curve(d3.curveCatmullRom).x(w=>x(w.date)+x.bandwidth()/2).y(w=>yT(w.low_c));
  const hp = svg.append('path').datum(data).attr('class','wx-high').attr('d', lineHigh);
  const lp = svg.append('path').datum(data).attr('class','wx-low').attr('d', lineLow);
  [hp,lp].forEach(p=>{
    const len = p.node().getTotalLength();
    p.attr('stroke-dasharray', len+' '+len).attr('stroke-dashoffset', len)
      .transition().duration(900).ease(d3.easeCubicOut).attr('stroke-dashoffset',0);
  });

  // dots
  svg.append('g').selectAll('circle.h').data(data).join('circle').attr('class','wx-dot')
    .attr('cx', w=>x(w.date)+x.bandwidth()/2).attr('cy', w=>yT(w.high_c)).attr('r',0)
    .transition().delay(600).duration(400).attr('r',3.5);
  svg.append('g').selectAll('circle.l').data(data).join('circle').attr('class','wx-dot-low')
    .attr('cx', w=>x(w.date)+x.bandwidth()/2).attr('cy', w=>yT(w.low_c)).attr('r',0)
    .transition().delay(800).duration(400).attr('r',3);

  // axes
  const xa = d3.axisBottom(x).tickFormat(d=>d.slice(5));
  svg.append('g').attr('class','wx-axis').attr('transform',`translate(0,${H-margin.bottom})`).call(xa);
  svg.append('g').attr('class','wx-axis').attr('transform',`translate(${margin.left},0)`).call(d3.axisLeft(yT).ticks(4).tickFormat(d=>d+'°'));

  // legend
  svg.append('text').attr('x',margin.left).attr('y',12).attr('fill','#f56565').style('font','11px JetBrains Mono').text('● high');
  svg.append('text').attr('x',margin.left+60).attr('y',12).attr('fill','#7cd1ff').style('font','11px JetBrains Mono').text('● low');
  svg.append('text').attr('x',margin.left+115).attr('y',12).attr('fill','rgba(124,209,255,.6)').style('font','11px JetBrains Mono').text('▮ rain %');
}

// ---- budget donut ----
function renderBudget(d){
  const bd = d.logistics?.budget_breakdown||{};
  const svg = d3.select('#budgetSvg');
  svg.selectAll('*').remove();
  const W = svg.node().getBoundingClientRect().width||300, H=240;
  const r = Math.min(W,H)/2 - 12;
  const g = svg.append('g').attr('transform',`translate(${W/2},${H/2})`);
  const data = [
    {k:'Flights',c:'#7cd1ff',v:bd.flights||0},
    {k:'Hotel',c:'#667eea',v:bd.hotel||0},
    {k:'Food',c:'#f093fb',v:bd.food||0},
    {k:'Activities',c:'#48bb78',v:bd.activities||0},
    {k:'Transit',c:'#ecc94b',v:bd.local_transit||0},
  ].filter(x=>x.v>0);
  const total = d3.sum(data,x=>x.v);
  if(!total){ g.append('text').attr('class','donut-center').append('tspan').attr('class','small').text('no data'); return; }
  const arc = d3.arc().innerRadius(r*.62).outerRadius(r);
  const pie = d3.pie().value(x=>x.v).sort(null).padAngle(.025);
  const arcs = g.selectAll('path').data(pie(data)).join('path')
    .attr('class','donut-arc').attr('fill',pd=>pd.data.c)
    .attr('d', arc)
    .each(function(pd){ this._current = {startAngle:pd.startAngle, endAngle:pd.startAngle}; })
    .transition().duration(900).ease(d3.easeCubicOut)
    .attrTween('d', function(pd){
      const i = d3.interpolate(this._current, pd);
      this._current = i(1);
      return t => arc(i(t));
    });
  const center = g.append('text').attr('class','donut-center');
  center.append('tspan').attr('class','big').text('$'+total.toLocaleString());
  center.append('tspan').attr('class','small').attr('x',0).attr('dy','1.6em').text('Total (est.)');
  const vsBudget = (d.budget_usd||0) - total;
  center.append('tspan').attr('class','small').attr('x',0).attr('dy','1.4em')
    .attr('fill', vsBudget>=0 ? '#9ae6b4' : '#feb2b2')
    .text((vsBudget>=0?'$':'-$') + Math.abs(vsBudget).toLocaleString() + (vsBudget>=0?' under':' over'));

  const legend = document.getElementById('budgetLegend');
  legend.innerHTML = data.map(x=>`
    <div class="legend-item"><span class="legend-swatch" style="background:${x.c}"></span>
    <span>${x.k}</span><span class="legend-amt">$${x.v.toLocaleString()}</span></div>
  `).join('');
}

// ---- Leaflet POI map ----
function poiCategory(p){
  if(['museum','gallery','aquarium','artwork','zoo','theme_park'].includes(p.kind)) return 'museum';
  if(['castle','monument','memorial','ruins','archaeological_site'].includes(p.kind)) return 'historic';
  if(p.kind === 'viewpoint') return 'viewpoint';
  return 'poi';
}
const CAT_COLOR = { museum:'#f093fb', historic:'#ecc94b', viewpoint:'#7cd1ff', poi:'#667eea', food:'#48bb78' };
const CAT_EMOJI = { museum:'🏛️', historic:'🏰', viewpoint:'🌄', poi:'📍', food:'🍴' };

function renderMap(d){
  const center = [d.dest_geo?.lat||0, d.dest_geo?.lon||0];
  if(window._poiMap){ window._poiMap.remove(); }
  const map = L.map('poiMap', {zoomControl:true, attributionControl:true}).setView(center, 13);
  window._poiMap = map;
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap · CARTO',
    maxZoom: 19, subdomains: 'abcd'
  }).addTo(map);

  const groups = {};
  function addGroup(name){ const lg = L.layerGroup().addTo(map); groups[name]=lg; return lg; }
  ['museum','historic','viewpoint','poi','food'].forEach(addGroup);

  const counts = {museum:0,historic:0,viewpoint:0,poi:0,food:0};
  (d.pois||[]).forEach(p=>{
    if(!p.lat||!p.lon) return;
    const cat = poiCategory(p);
    counts[cat]++;
    const icon = L.divIcon({
      className:'',
      html:`<div class="poi-marker" style="background:${CAT_COLOR[cat]};width:11px;height:11px"></div>`,
      iconSize:[14,14], iconAnchor:[7,7]
    });
    const m = L.marker([p.lat,p.lon],{icon}).addTo(groups[cat]);
    const wiki = p.wiki ? `<br><a href="https://${p.wiki.split(':')[0]||'en'}.wikipedia.org/wiki/${encodeURIComponent((p.wiki.split(':')[1]||'').replace(/ /g,'_'))}" target="_blank">wikipedia ↗</a>` : '';
    const site = p.website ? `<br><a href="${p.website}" target="_blank">website ↗</a>` : '';
    const hours = p.opening_hours ? `<br><code>${escapeHtml(p.opening_hours)}</code>` : '';
    m.bindPopup(`<strong>${CAT_EMOJI[cat]} ${escapeHtml(p.name)}</strong><br><em>${p.kind}</em>${hours}${site}${wiki}`);
  });
  (d.food||[]).forEach(f=>{
    if(!f.lat||!f.lon) return;
    counts.food++;
    const icon = L.divIcon({
      className:'',
      html:`<div class="poi-marker" style="background:${CAT_COLOR.food};width:8px;height:8px;border-width:1px"></div>`,
      iconSize:[10,10], iconAnchor:[5,5]
    });
    const m = L.marker([f.lat,f.lon],{icon}).addTo(groups.food);
    const cuisine = f.cuisine ? `<br>cuisine: <code>${escapeHtml(f.cuisine)}</code>` : '';
    m.bindPopup(`<strong>🍴 ${escapeHtml(f.name)}</strong><br><em>${f.amenity}</em>${cuisine}`);
  });

  // filter chips
  document.querySelectorAll('.map-filter').forEach(btn=>{
    btn.onclick = ()=>{
      document.querySelectorAll('.map-filter').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      const cat = btn.dataset.cat;
      Object.entries(groups).forEach(([k,lg])=>{
        if(cat==='all' || cat===k) map.addLayer(lg);
        else map.removeLayer(lg);
      });
    };
  });
  // counts label
  document.getElementById('mapCounts').innerHTML =
    `${Object.values(counts).reduce((a,b)=>a+b,0)} markers · ` +
    Object.entries(counts).map(([k,n])=>`<span style="color:${CAT_COLOR[k]}">●</span> ${n} ${k}`).join(' · ');
}

// ---- day-by-day cards ----
function poiEmoji(kind){
  return ({museum:'🏛️',gallery:'🎨',aquarium:'🐠',theme_park:'🎢',zoo:'🦁',viewpoint:'🌄',castle:'🏰',monument:'🗿',memorial:'🕊️',ruins:'🏛',archaeological_site:'🏺',attraction:'📍',artwork:'🖼️'})[kind]||'📍';
}
function renderDays(d){
  const plan = d.logistics?.plan || [];
  const wrap = document.getElementById('daysWrap');
  wrap.innerHTML = '';
  plan.forEach((day, i)=>{
    const w = day.weather||{};
    const rainy = (w.rain_pct||0) >= 50;
    const wxCls = rainy ? 'day-wx rainy' : 'day-wx';
    const poisHtml = (day.picks||[]).map(p=>{
      const wikiUrl = p.wiki ? `https://${(p.wiki.split(':')[0]||'en')}.wikipedia.org/wiki/${encodeURIComponent((p.wiki.split(':')[1]||'').replace(/ /g,'_'))}` : '';
      const mapUrl = (p.lat && p.lon) ? `https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lon}#map=17/${p.lat}/${p.lon}` : '';
      const links = [
        p.website ? `<a href="${p.website}" target="_blank">website</a>` : '',
        wikiUrl ? `<a href="${wikiUrl}" target="_blank">wiki</a>` : '',
        mapUrl ? `<a href="${mapUrl}" target="_blank">map</a>` : '',
      ].filter(Boolean).join('');
      const meta = [
        p.kind,
        p.opening_hours ? `hrs: ${p.opening_hours.slice(0,40)}` : ''
      ].filter(Boolean).join(' · ');
      return `<div class="day-poi" onclick="if(window._poiMap){window._poiMap.flyTo([${p.lat},${p.lon}], 16, {duration:.8});}">
        <div class="pico">${poiEmoji(p.kind)}</div>
        <div class="pmid">
          <div class="ptitle">${escapeHtml(p.name)}</div>
          <div class="pmeta">${escapeHtml(meta)}</div>
        </div>
        <div class="plinks">${links}</div>
      </div>`;
    }).join('');
    const meals = (day.meals||[]).map(m =>
      `<span>${escapeHtml(m.name)}${m.cuisine?` <em style="color:#9ae6b4">(${escapeHtml(m.cuisine)})</em>`:''}</span>`
    ).join(' · ');
    const card = document.createElement('div');
    card.className = 'day-card';
    card.style.animationDelay = (i*0.08)+'s';
    card.innerHTML = `
      <div class="day-head">
        <div class="day-num">D${i+1}</div>
        <div class="day-date">${w.date||''}</div>
        <div class="${wxCls}">${w.label||'?'} · ${w.high_c}°C / ${w.low_c}°C · rain ${w.rain_pct||0}%</div>
      </div>
      <div class="day-pois">${poisHtml || '<div style="color:var(--text-light)">No POIs assigned.</div>'}</div>
      ${meals ? `<div class="day-meals"><strong>Eat:</strong> ${meals}</div>` : ''}
    `;
    wrap.appendChild(card);
  });
}

function renderSources(d){
  const ss = document.getElementById('sourcesStrip');
  const srcs = d.sources || [];
  ss.innerHTML = '<span style="color:var(--text-light);font-size:.74rem;margin-right:.4rem">live sources →</span>' + srcs.map(s=>`<span class="source-chip">${escapeHtml(s)}</span>`).join('');
}

function escapeHtml(s){ return (s||'').toString().replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }

document.getElementById('planForm').addEventListener('submit', e=>{
  e.preventDefault();
  const fd = new FormData(e.target);
  run(Object.fromEntries(fd));
});
document.querySelectorAll('.samples a').forEach(a=>{
  a.addEventListener('click', e=>{
    e.preventDefault();
    const [d,o,s,en,b,t,p] = a.dataset.q.split('|');
    const f = document.getElementById('planForm');
    f.destination.value=d; f.origin.value=o; f.start.value=s; f.end.value=en;
    f.budget.value=b; f.travelers.value=t; f.preferences.value=p;
    run({destination:d,origin:o,start:s,end:en,budget:b,travelers:t,preferences:p});
  });
});

// auto-fire Tokyo on first load
window.addEventListener('load', ()=>{
  setTimeout(()=>{ document.querySelector('.samples a').click(); }, 400);
});
</script>
</body></html>"""


def safe_dates():
    now = datetime.now()
    return (
        (now + timedelta(days=5)).strftime("%Y-%m-%d"),
        (now + timedelta(days=10)).strftime("%Y-%m-%d"),
        (now + timedelta(days=11)).strftime("%Y-%m-%d"),
        (now + timedelta(days=9)).strftime("%Y-%m-%d"),
    )


def home_html():
    s1, e1, e2, e3 = safe_dates()
    p = PAGE
    p = p.replace("__AGENTS_JSON__", json.dumps(AGENTS))
    p = p.replace("__NAGENTS__", str(len(AGENTS)))
    p = p.replace("__S1__", s1).replace("__E1__", e1).replace("__E2__", e2).replace("__E3__", e3)
    return p


def sse_event(name: str, payload: dict) -> bytes:
    body = json.dumps(payload, default=str)
    return f"event: {name}\ndata: {body}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: N802
        print("  http  " + fmt % args, flush=True)

    def _write(self, status: int, body: str, content_type: str = "text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        if parsed.path == "/":
            self._write(200, home_html())
            return
        if parsed.path == "/health":
            self._write(200, json.dumps({"ok": True}), "application/json")
            return
        if parsed.path == "/stream":
            self._stream(params)
            return
        self._write(404, "not found", "text/plain")

    def _stream(self, params: dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        q: queue.Queue = queue.Queue()

        def tracer(event: dict) -> None:
            q.put(event)

        result: dict = {}

        def worker():
            try:
                ctx = vr.TripContext(
                    destination=params.get("destination", "Tokyo").strip(),
                    origin=params.get("origin", "New York").strip() or "New York",
                    start_date=params.get("start", "").strip(),
                    end_date=params.get("end", "").strip(),
                    budget_usd=float(params.get("budget") or 3000),
                    travelers=int(params.get("travelers") or 1),
                    preferences=params.get("preferences", "").strip() or "balanced",
                    tracer=tracer,
                )
                asyncio.run(vr.orchestrate(ctx))
                result.update(ctx.to_payload())
            except Exception as e:  # noqa: BLE001
                result["error"] = str(e)
                result["trace"] = traceback.format_exc()
            finally:
                q.put({"type": "done"})

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    ev = q.get(timeout=30)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                if ev.get("type") == "done":
                    if "error" in result:
                        self.wfile.write(sse_event("error", result))
                    else:
                        self.wfile.write(sse_event("done", result))
                    self.wfile.flush()
                    return
                if ev.get("type") == "agent":
                    self.wfile.write(sse_event("agent", ev))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"VoyageAI v2 web server on http://{args.host}:{args.port}/", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
