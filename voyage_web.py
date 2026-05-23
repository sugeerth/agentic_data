"""VoyageAI v2 — animated web frontend with live SSE agent stream.

Wraps voyage_real.orchestrate behind a tiny stdlib HTTP server. The browser
opens /stream as an EventSource and watches all 8 agents fire in real time:
each card lights up when its agent starts, then turns green with a one-line
summary when done. After the synthesizer completes, the itinerary fades in.

Run:   python3 voyage_web.py [--port 8765]
Open:  http://localhost:8765/
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import queue
import sys
import threading
import time
import traceback
import os
import urllib.parse
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import markdown as md

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voyage_real as vr  # noqa: E402


AGENTS = [
    {"name": "geocode",     "emoji": "📍", "label": "Geocode",     "blurb": "Nominatim OSM",     "phase": 1},
    {"name": "weather",     "emoji": "🌤️",  "label": "Weather",    "blurb": "Open-Meteo",         "phase": 2},
    {"name": "country",     "emoji": "🌐",  "label": "Country",    "blurb": "REST Countries",     "phase": 2},
    {"name": "wiki",        "emoji": "📖",  "label": "Wiki",       "blurb": "Wikipedia REST",     "phase": 2},
    {"name": "poi",         "emoji": "🗿",  "label": "Attractions","blurb": "Overpass · OSM",     "phase": 2},
    {"name": "food",        "emoji": "🍜",  "label": "Restaurants","blurb": "Overpass · OSM",     "phase": 2},
    {"name": "logistics",   "emoji": "✈️",   "label": "Logistics", "blurb": "Haversine + IATA $/mi", "phase": 2},
    {"name": "currency",    "emoji": "💱",  "label": "Currency",   "blurb": "open.er-api.com",    "phase": 3},
    {"name": "synthesizer", "emoji": "🧭",  "label": "Synthesizer","blurb": "Day-by-day planner", "phase": 4},
]


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>VoyageAI v2 — live multi-agent travel planner</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{
  --primary:#667eea; --primary-dark:#5a67d8; --secondary:#764ba2; --accent:#f093fb;
  --bg:#0f0f23; --bg-light:#1a1a3e; --bg-card:#1e1e42;
  --text:#e2e8f0; --text-light:#a0aec0; --text-bright:#fff;
  --border:rgba(102,126,234,.2);
  --good:#48bb78; --warn:#ecc94b; --bad:#f56565;
  --gradient:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
  --gradient-accent:linear-gradient(135deg,#f093fb 0%,#f5576c 100%);
  --radius:16px;
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;overflow-x:hidden;min-height:100vh}
.bg-gradient{position:fixed;inset:0;z-index:-1;background:
  radial-gradient(ellipse at 20% 50%,rgba(102,126,234,.15) 0%,transparent 50%),
  radial-gradient(ellipse at 80% 20%,rgba(118,75,162,.15) 0%,transparent 50%),
  radial-gradient(ellipse at 50% 80%,rgba(240,147,251,.08) 0%,transparent 50%);}
.container{max-width:1200px;margin:0 auto;padding:0 2rem}
header{padding:2.5rem 0 1rem}
.brand{font-size:2rem;font-weight:900;letter-spacing:-.02em;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;display:inline-block}
.brand-sub{color:var(--text-light);font-weight:500;margin-left:.5rem}
.hero-badge{display:inline-flex;align-items:center;gap:.5rem;background:rgba(102,126,234,.15);border:1px solid var(--border);border-radius:30px;padding:.35rem 1rem;font-size:.8rem;color:var(--primary);font-weight:500;margin:.5rem 0 1rem;}
.hero-badge .dot{width:7px;height:7px;border-radius:50%;background:var(--good);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(72,187,120,.6)}50%{opacity:.55;box-shadow:0 0 0 8px rgba(72,187,120,0)}}
.tagline{font-size:1rem;color:var(--text-light);max-width:720px}

/* Form */
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:1.6rem;box-shadow:0 4px 30px rgba(0,0,0,.2)}
form{display:grid;grid-template-columns:repeat(12,1fr);gap:.9rem;margin-top:1.2rem}
label{font-size:.72rem;color:var(--text-light);text-transform:uppercase;letter-spacing:.08em;font-weight:600;display:block;margin-bottom:.3rem}
input{width:100%;padding:.65rem .85rem;background:rgba(0,0,0,.3);color:var(--text-bright);border:1px solid var(--border);border-radius:10px;font:inherit;font-size:.95rem;transition:border-color .2s,box-shadow .2s}
input:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px rgba(102,126,234,.18)}
.col-dest{grid-column:span 4}.col-orig{grid-column:span 4}
.col-start{grid-column:span 2}.col-end{grid-column:span 2}
.col-tr{grid-column:span 2}.col-bud{grid-column:span 2}
.col-pref{grid-column:span 8}.col-submit{grid-column:span 12;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
@media(max-width:760px){.col-dest,.col-orig,.col-pref{grid-column:span 12}.col-start,.col-end,.col-tr,.col-bud{grid-column:span 6}}
button.primary{background:var(--gradient);color:white;border:0;padding:.85rem 1.6rem;border-radius:10px;font-weight:700;font-size:.95rem;cursor:pointer;transition:transform .15s,filter .15s;font-family:inherit}
button.primary:hover{transform:translateY(-1px);filter:brightness(1.08)}
button.primary:active{transform:translateY(0)}
button.primary:disabled{opacity:.55;cursor:wait}
.samples{color:var(--text-light);font-size:.85rem;display:flex;gap:.7rem;flex-wrap:wrap}
.samples a{color:var(--accent);text-decoration:none;padding:.3rem .7rem;background:rgba(240,147,251,.08);border:1px solid rgba(240,147,251,.2);border-radius:999px;transition:all .15s}
.samples a:hover{background:rgba(240,147,251,.18);transform:translateY(-1px)}

/* Live status row */
.status-row{display:flex;gap:.8rem;flex-wrap:wrap;margin-top:1.2rem;align-items:center}
.pill{display:inline-flex;align-items:center;gap:.4rem;padding:.35rem .8rem;border-radius:999px;background:rgba(102,126,234,.12);border:1px solid var(--border);font-size:.82rem;color:var(--text);font-weight:500}
.pill.live::before{content:'';width:7px;height:7px;border-radius:50%;background:var(--good);animation:pulse 1.4s infinite}
.pill.done{background:rgba(72,187,120,.12);border-color:rgba(72,187,120,.3);color:#9ae6b4}

/* Agent flow */
.flow{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.9rem;margin-top:1.3rem}
.agent{background:rgba(0,0,0,.25);border:1px solid var(--border);border-radius:14px;padding:1rem 1.1rem;position:relative;overflow:hidden;transition:all .3s cubic-bezier(.4,0,.2,1);opacity:.55}
.agent::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:#3a3a5a;transition:background .3s}
.agent.pending::before{background:#3a3a5a}
.agent.running{opacity:1;border-color:rgba(102,126,234,.45);box-shadow:0 0 0 1px rgba(102,126,234,.25),0 4px 20px rgba(102,126,234,.18)}
.agent.running::before{background:var(--primary);box-shadow:0 0 12px var(--primary)}
.agent.running .ico{animation:spin 1.4s linear infinite}
.agent.done{opacity:1;border-color:rgba(72,187,120,.35)}
.agent.done::before{background:var(--good)}
.agent.error{opacity:1;border-color:rgba(245,101,101,.45)}
.agent.error::before{background:var(--bad)}
@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
.agent .top{display:flex;align-items:center;gap:.65rem}
.agent .ico{font-size:1.5rem;width:38px;height:38px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.04);border-radius:10px;flex-shrink:0}
.agent .name{font-weight:700;color:var(--text-bright);font-size:.95rem}
.agent .blurb{color:var(--text-light);font-size:.72rem;text-transform:uppercase;letter-spacing:.06em}
.agent .summary{margin-top:.7rem;font-size:.8rem;color:var(--text-light);min-height:1.1rem;font-family:'JetBrains Mono',monospace;line-height:1.4;word-break:break-word}
.agent .dur{position:absolute;top:.7rem;right:.9rem;font-size:.7rem;color:var(--text-light);font-family:'JetBrains Mono',monospace;background:rgba(0,0,0,.3);padding:.1rem .4rem;border-radius:6px;opacity:0;transition:opacity .3s}
.agent.done .dur,.agent.error .dur{opacity:1}
.agent.done .dur{color:#9ae6b4}
.agent.error .dur{color:#feb2b2}
.agent .check{position:absolute;bottom:.7rem;right:.9rem;font-size:1.1rem;opacity:0;transform:scale(.4);transition:all .35s cubic-bezier(.34,1.56,.64,1)}
.agent.done .check{opacity:1;transform:scale(1)}

.phase-label{grid-column:1/-1;color:var(--text-light);font-size:.72rem;text-transform:uppercase;letter-spacing:.12em;font-weight:600;margin-top:.5rem}
.phase-label:first-child{margin-top:0}

/* Itinerary */
.itinerary{margin-top:1.6rem;animation:fadeSlideUp .6s ease}
@keyframes fadeSlideUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.itin-header{background:var(--gradient);border-radius:16px 16px 0 0;padding:1.8rem 2rem;color:white}
.itin-header h2{font-size:1.7rem;font-weight:800;margin-bottom:.2rem}
.itin-header .meta{opacity:.9;font-size:.9rem;display:flex;gap:1.2rem;flex-wrap:wrap}
.itin-body{background:var(--bg-card);border:1px solid var(--border);border-top:none;border-radius:0 0 16px 16px;padding:0;overflow:hidden}
.itin-body h2{font-size:1rem;color:var(--text-light);text-transform:uppercase;letter-spacing:.1em;padding:1.4rem 2rem .8rem;border-bottom:1px solid var(--border)}
.itin-body h3{font-size:1.05rem;color:var(--text-bright);padding:1.3rem 2rem .5rem;font-weight:700;animation:fadeSlideUp .5s ease both}
.itin-body p,.itin-body ul,.itin-body ol{padding:.4rem 2rem;color:var(--text);font-size:.92rem}
.itin-body blockquote{margin:1rem 2rem;padding:.8rem 1.2rem;border-left:3px solid var(--accent);background:rgba(240,147,251,.06);border-radius:0 10px 10px 0;color:#d6c1de;font-style:italic;font-size:.92rem}
.itin-body ul{list-style:none;padding-left:2rem;padding-right:2rem}
.itin-body ul li{padding:.35rem 0;color:var(--text);font-size:.92rem;animation:fadeSlideUp .4s ease both}
.itin-body ul li::before{content:'▸ ';color:var(--primary);font-weight:700}
.itin-body strong{color:var(--text-bright);font-weight:700}
.itin-body a{color:var(--accent);text-decoration:none;font-size:.85rem;padding:0 .15rem}
.itin-body a:hover{text-decoration:underline}
.itin-body code{font-family:'JetBrains Mono',monospace;background:rgba(0,0,0,.3);padding:1px 6px;border-radius:5px;font-size:.78rem;color:#c3e88d}
.itin-body em{color:var(--text-light)}
.itin-body table{border-collapse:collapse;width:calc(100% - 4rem);margin:.6rem 2rem;font-size:.85rem}
.itin-body th,.itin-body td{border:1px solid var(--border);padding:.5rem .8rem;text-align:left}
.itin-body th{background:rgba(0,0,0,.25);color:var(--text-light);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em}
.itin-body tr:hover td{background:rgba(102,126,234,.05)}
.itin-body hr{display:none}
.itin-body p:last-child,.itin-body ul:last-child{padding-bottom:1.4rem}

footer{padding:2rem;text-align:center;color:var(--text-light);font-size:.82rem;margin-top:2rem}
footer a{color:var(--accent);text-decoration:none}
</style>
</head>
<body>
<div class="bg-gradient"></div>
<div class="container">
  <header>
    <div class="brand">VoyageAI v2<span class="brand-sub">— real-data multi-agent planner</span></div>
    <div class="hero-badge"><span class="dot"></span> 8 agents · async fan-out · zero LLM keys · all live data</div>
    <p class="tagline">Live sources: Nominatim · Overpass · Open-Meteo · REST Countries · Wikipedia · open.er-api.com. Watch them fire in parallel below.</p>
  </header>

  <div class="card">
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
          <a href="#" data-q="Tokyo|San Francisco|__S1__|__E1__|3500|2|balanced mix of culture, food, and outdoors">Tokyo 6d</a>
          <a href="#" data-q="Lisbon|New York|__S1__|__E2__|2200|2|budget-friendly food-focused walking">Lisbon 7d</a>
          <a href="#" data-q="Barcelona|London|__S1__|__E1__|2800|2|tapas architecture beach">Barcelona 6d</a>
          <a href="#" data-q="Mexico City|Chicago|__S1__|__E3__|1500|1|street food museums">CDMX 5d</a>
        </div>
      </div>
    </form>
    <div class="status-row" id="statusRow" style="display:none">
      <span class="pill live" id="pillStatus">Agents firing…</span>
      <span class="pill" id="pillTime">0.00s</span>
      <span class="pill" id="pillDone">0 / __NAGENTS__ done</span>
    </div>
    <div class="flow" id="flow"></div>
  </div>

  <div id="itineraryHost"></div>
</div>
<footer>
  Built as an upgrade of <a href="https://github.com/sugeerth/agentic_data">sugeerth/agentic_data</a> ·
  every data point on this page came from a live public API call, no LLM, no API keys.
</footer>

<script>
const AGENTS = __AGENTS_JSON__;
const flow = document.getElementById('flow');
const statusRow = document.getElementById('statusRow');
const pillStatus = document.getElementById('pillStatus');
const pillTime = document.getElementById('pillTime');
const pillDone = document.getElementById('pillDone');
const itineraryHost = document.getElementById('itineraryHost');
const form = document.getElementById('planForm');
const planBtn = document.getElementById('planBtn');

let phaseRendered = new Set();
function renderFlow(){
  flow.innerHTML = '';
  let lastPhase = null;
  const phaseNames = {1:'Phase 1 · Geocoding (blocks)', 2:'Phase 2 · Specialists (parallel)', 3:'Phase 3 · Dependent', 4:'Phase 4 · Synthesizer'};
  for(const a of AGENTS){
    if(a.phase !== lastPhase){
      const ph = document.createElement('div');
      ph.className = 'phase-label';
      ph.textContent = phaseNames[a.phase] || `Phase ${a.phase}`;
      flow.appendChild(ph);
      lastPhase = a.phase;
    }
    const el = document.createElement('div');
    el.className = 'agent pending';
    el.id = 'agent-' + a.name;
    el.innerHTML = `
      <div class="dur" id="dur-${a.name}"></div>
      <div class="top">
        <div class="ico">${a.emoji}</div>
        <div>
          <div class="name">${a.label}</div>
          <div class="blurb">${a.blurb}</div>
        </div>
      </div>
      <div class="summary" id="summary-${a.name}">queued</div>
      <div class="check">✓</div>`;
    flow.appendChild(el);
  }
}
renderFlow();

function setAgent(name, status, payload){
  const el = document.getElementById('agent-'+name);
  if(!el) return;
  el.classList.remove('pending','running','done','error');
  el.classList.add(status);
  const sum = document.getElementById('summary-'+name);
  const dur = document.getElementById('dur-'+name);
  if(status==='running'){ sum.textContent = 'running…'; }
  if(status==='done'){
    sum.textContent = payload.summary || 'done';
    dur.textContent = payload.duration.toFixed(2)+'s';
  }
  if(status==='error'){
    sum.textContent = payload.error || 'error';
    dur.textContent = payload.duration.toFixed(2)+'s';
  }
}

let startTime = 0, timerId = null, doneCount = 0;
function startTimer(){ startTime = performance.now(); timerId = setInterval(()=>{
  pillTime.textContent = ((performance.now()-startTime)/1000).toFixed(2)+'s';
},100); }
function stopTimer(){ clearInterval(timerId); }

function reset(){
  renderFlow();
  itineraryHost.innerHTML = '';
  statusRow.style.display = 'flex';
  pillStatus.className = 'pill live';
  pillStatus.textContent = 'Agents firing…';
  pillDone.classList.remove('done');
  pillDone.textContent = `0 / ${AGENTS.length} done`;
  doneCount = 0;
}

function run(params){
  reset();
  startTimer();
  planBtn.disabled = true;
  const q = new URLSearchParams(params).toString();
  const es = new EventSource('/stream?' + q);
  es.addEventListener('agent', ev=>{
    const data = JSON.parse(ev.data);
    if(data.status==='start') setAgent(data.name,'running',data);
    else if(data.status==='done'){ setAgent(data.name,'done',data); doneCount++; pillDone.textContent = `${doneCount} / ${AGENTS.length} done`; }
    else if(data.status==='error'){ setAgent(data.name,'error',data); doneCount++; pillDone.textContent = `${doneCount} / ${AGENTS.length} done`; }
  });
  es.addEventListener('done', ev=>{
    stopTimer(); planBtn.disabled = false;
    pillStatus.className = 'pill done';
    pillStatus.textContent = '✓ Plan ready';
    pillDone.classList.add('done');
    const data = JSON.parse(ev.data);
    itineraryHost.innerHTML = `
      <div class="itinerary">
        <div class="itin-header">
          <h2>${escapeHtml(data.destination)} — ${data.days}-day plan</h2>
          <div class="meta">
            <span>${data.start} → ${data.end}</span>
            <span>${data.travelers} traveler(s)</span>
            <span>$${Number(data.budget).toLocaleString()} budget</span>
            ${data.flag?`<span>${data.flag} ${escapeHtml(data.country||'')}</span>`:''}
          </div>
        </div>
        <div class="itin-body">${data.html}</div>
      </div>`;
    es.close();
    // Stagger reveal of the days
    const headers = itineraryHost.querySelectorAll('.itin-body h3');
    headers.forEach((h,i)=>{ h.style.animationDelay = (i*0.06)+'s'; });
    const lis = itineraryHost.querySelectorAll('.itin-body ul li');
    lis.forEach((li,i)=>{ li.style.animationDelay = (Math.min(i,30)*0.025)+'s'; });
    itineraryHost.scrollIntoView({behavior:'smooth',block:'start'});
  });
  es.addEventListener('error', ev=>{
    stopTimer(); planBtn.disabled = false;
    pillStatus.className = 'pill';
    pillStatus.textContent = 'connection ended';
    es.close();
  });
}

function escapeHtml(s){ return (s||'').replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }

form.addEventListener('submit', e=>{
  e.preventDefault();
  const fd = new FormData(form);
  run(Object.fromEntries(fd));
});

document.querySelectorAll('.samples a').forEach(a=>{
  a.addEventListener('click', e=>{
    e.preventDefault();
    const [d,o,s,en,b,t,p] = a.dataset.q.split('|');
    form.destination.value=d; form.origin.value=o; form.start.value=s; form.end.value=en;
    form.budget.value=b; form.travelers.value=t; form.preferences.value=p;
    run({destination:d,origin:o,start:s,end:en,budget:b,travelers:t,preferences:p});
  });
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
                markdown_text = vr.render_markdown(ctx)
                # Strip the H1 + first line of meta — we render those in the
                # gradient header. Drop the "Run metadata" trailer too.
                stripped = strip_redundant(markdown_text)
                result["html"] = md.markdown(stripped, extensions=["tables"])
                result["destination"] = ctx.destination
                result["start"] = ctx.start_date
                result["end"] = ctx.end_date
                result["days"] = ctx.days
                result["travelers"] = ctx.travelers
                result["budget"] = ctx.budget_usd
                result["country"] = ctx.country.get("name", "")
                result["flag"] = ctx.country.get("flag", "")
            except Exception as e:  # noqa: BLE001
                result["error"] = str(e)
                result["trace"] = traceback.format_exc()
            finally:
                q.put({"type": "done"})

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        try:
            # heartbeat to keep proxies happy
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
                    payload = {**result}
                    if "error" in payload:
                        self.wfile.write(sse_event("error", payload))
                    else:
                        self.wfile.write(sse_event("done", payload))
                    self.wfile.flush()
                    return
                if ev.get("type") == "agent":
                    self.wfile.write(sse_event("agent", ev))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def strip_redundant(markdown_text: str) -> str:
    """Remove the H1 + meta + run-metadata trailer that we render separately."""
    lines = markdown_text.splitlines()
    out: list[str] = []
    skipped_header = False
    skip_until_end = False
    for ln in lines:
        if not skipped_header:
            if ln.startswith("# "):
                continue
            if ln.startswith("_") and ln.endswith("_"):
                skipped_header = True
                continue
            if ln.strip() == "":
                continue
        if ln.startswith("## Run metadata"):
            skip_until_end = True
        if skip_until_end:
            continue
        out.append(ln)
    return "\n".join(out)


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
