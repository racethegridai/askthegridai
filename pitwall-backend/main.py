"""
PitWall AI — FastAPI backend
Fetches live race data from OpenF1 API, enriched with FastF1 session metadata.
Serves a /api/state REST endpoint and a /events SSE stream.
"""

import asyncio
import csv
import hashlib
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import anthropic
import fastf1
import feedparser
import httpx
import stripe
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# ── Questions log ────────────────────────────────────
_QUESTIONS_LOG = Path(__file__).parent / "questions_log.csv"
_LOG_HEADERS   = ["timestamp", "question", "length", "session_id"]
# Lock is initialised in _lifespan() so it's created inside the running event loop.
_log_lock: asyncio.Lock | None = None

def _ensure_log_headers() -> None:
    """Create questions_log.csv with headers if it doesn't exist yet."""
    if not _QUESTIONS_LOG.exists():
        with open(_QUESTIONS_LOG, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(_LOG_HEADERS)

async def _log_question(question: str, session_id: str) -> None:
    """Append one row to questions_log.csv (non-blocking, serialised by lock)."""
    if _log_lock is None:
        return   # lock not yet initialised (startup edge case)
    ts  = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = [ts, question, len(question), session_id]
    async with _log_lock:
        try:
            _ensure_log_headers()
            with open(_QUESTIONS_LOG, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(row)
        except Exception as exc:
            log.warning("[LOG] Failed to write question: %s", exc)

# ── Load .env (search from backend dir upward) ───────
load_dotenv(Path(__file__).parent / ".env")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
load_dotenv(Path(__file__).parent.parent / ".env", override=False)  # fallback to project root

# ── Logging ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pitwall")

# ── FastF1 cache ─────────────────────────────────────
_cache_dir = Path(__file__).parent / "f1_cache"
_cache_dir.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(_cache_dir))

# ── Constants ────────────────────────────────────────

OPENF1 = "https://api.openf1.org/v1"
POLL_INTERVAL_LIVE     = 15   # seconds — full refresh during a live session
POLL_INTERVAL_IDLE     = 60   # seconds — full refresh when no live session
POLL_CRITICAL_LIVE     = 5    # seconds — flag/pit check during live session
POLL_CRITICAL_IDLE     = 20   # seconds — flag/pit check when idle
OPENF1_TIMEOUT         = 3.0  # seconds — fail fast; cached data serves immediately
BACKOFF_BASE = 10.0           # initial backoff on 429 (seconds)
BACKOFF_MAX  = 120.0          # cap backoff at 2 minutes

# Demo mode removed April 2026

# ── AI model constants ───────────────────────────────
# User-facing chat uses Sonnet (set directly on each endpoint — do not change).
HAIKU_MODEL = "claude-haiku-4-5"  # background summarization tasks only

# ── IP rate limiter ──────────────────────────────────
_RATE_WINDOW   = 3600  # seconds (1 hour sliding window)
_RATE_MAX      = 50    # max AI requests per IP per hour
_rate_data: dict[str, list[float]] = {}
_rate_lock     = asyncio.Lock()

# Keep legacy names so nothing else in the file breaks
POLL_INTERVAL_REGULAR  = POLL_INTERVAL_LIVE
POLL_INTERVAL_CRITICAL = POLL_CRITICAL_LIVE

COMPOUND_SHORT: dict[str, str] = {
    "SOFT": "S", "MEDIUM": "M", "HARD": "H",
    "INTERMEDIATE": "I", "WET": "W",
    "HYPERSOFT": "S", "ULTRASOFT": "S", "SUPERSOFT": "S",
    "UNKNOWN": "?",
}

# Laps per circuit (fallback when API doesn't provide it)
CIRCUIT_LAPS: dict[str, int] = {
    "Bahrain": 57, "Sakhir": 57,
    "Jeddah": 50,
    "Melbourne": 58, "Albert Park": 58,
    "Suzuka": 53,
    "Shanghai": 56,
    "Miami": 57,
    "Imola": 63,
    "Monaco": 78,
    "Montréal": 70, "Montreal": 70,
    "Barcelona": 66,
    "Spielberg": 71, "Red Bull Ring": 71,
    "Silverstone": 52,
    "Budapest": 70,
    "Spa": 44, "Spa-Francorchamps": 44,
    "Zandvoort": 72,
    "Monza": 53,
    "Baku": 51,
    "Singapore": 62,
    "Austin": 56,
    "Mexico City": 71,
    "São Paulo": 71, "Sao Paulo": 71, "Interlagos": 71,
    "Las Vegas": 50,
    "Lusail": 57, "Qatar": 57,
    "Abu Dhabi": 58, "Yas Marina": 58,
}

# ── Shared state ─────────────────────────────────────

_state: dict[str, Any] = {}
_lock = asyncio.Lock()
_subscribers: list[asyncio.Queue] = []

# ── Championship standings cache ──────────────────────
_standings_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}

# ── News cache ────────────────────────────────────────
_NEWS_CACHE_TTL = 3600  # 1 hour
_NEWS_FEEDS = [
    "https://www.motorsport.com/rss/f1/news/",
]
_news_cache: dict[str, Any] = {"items": [], "refreshed_at": None}
_news_lock  = asyncio.Lock()

# ── Reddit + Google Trends caches ─────────────────────
cached_reddit: list[dict] = []
cached_trends: list[dict] = []

# ── News insights cache (keyed by article URL) ────────
_insights_cache: dict[str, dict] = {}
_insights_lock  = asyncio.Lock()

FALLBACK_STANDINGS = [
    {"position": 1,  "driver": "Antonelli",   "first_name": "Andrea Kimi", "team": "Mercedes",      "points": 72,  "wins": 2},
    {"position": 2,  "driver": "Norris",       "first_name": "Lando",       "team": "McLaren",        "points": 68,  "wins": 2},
    {"position": 3,  "driver": "Piastri",      "first_name": "Oscar",       "team": "McLaren",        "points": 61,  "wins": 1},
    {"position": 4,  "driver": "Russell",      "first_name": "George",      "team": "Mercedes",       "points": 54,  "wins": 1},
    {"position": 5,  "driver": "Leclerc",      "first_name": "Charles",     "team": "Ferrari",        "points": 48,  "wins": 1},
    {"position": 6,  "driver": "Hamilton",     "first_name": "Lewis",       "team": "Ferrari",        "points": 41,  "wins": 1},
    {"position": 7,  "driver": "Verstappen",   "first_name": "Max",         "team": "Red Bull",       "points": 35,  "wins": 0},
    {"position": 8,  "driver": "Hadjar",       "first_name": "Isack",       "team": "Red Bull",       "points": 28,  "wins": 0},
    {"position": 9,  "driver": "Sainz",        "first_name": "Carlos",      "team": "Williams",       "points": 22,  "wins": 0},
    {"position": 10, "driver": "Albon",        "first_name": "Alexander",   "team": "Williams",       "points": 18,  "wins": 0},
    {"position": 11, "driver": "Hulkenberg",   "first_name": "Nico",        "team": "Audi",           "points": 14,  "wins": 0},
    {"position": 12, "driver": "Bortoleto",    "first_name": "Gabriel",     "team": "Audi",           "points": 10,  "wins": 0},
    {"position": 13, "driver": "Alonso",       "first_name": "Fernando",    "team": "Aston Martin",   "points": 8,   "wins": 0},
    {"position": 14, "driver": "Lindblad",     "first_name": "Arvid",       "team": "Racing Bulls",   "points": 2,   "wins": 0},
    {"position": 15, "driver": "Lawson",       "first_name": "Liam",        "team": "Racing Bulls",   "points": 2,   "wins": 0},
    {"position": 16, "driver": "Stroll",       "first_name": "Lance",       "team": "Aston Martin",   "points": 1,   "wins": 0},
    {"position": 17, "driver": "Colapinto",    "first_name": "Franco",      "team": "Alpine",         "points": 0,   "wins": 0},
    {"position": 18, "driver": "Perez",        "first_name": "Sergio",      "team": "Cadillac",       "points": 0,   "wins": 0},
    {"position": 19, "driver": "Bottas",       "first_name": "Valtteri",    "team": "Cadillac",       "points": 0,   "wins": 0},
    {"position": 20, "driver": "Bearman",      "first_name": "Oliver",      "team": "Haas",           "points": 0,   "wins": 0},
    {"position": 21, "driver": "Ocon",         "first_name": "Esteban",     "team": "Haas",           "points": 0,   "wins": 0},
    {"position": 22, "driver": "Doohan",       "first_name": "Jack",        "team": "Alpine",         "points": 0,   "wins": 0},
]

# ── OpenF1 cache TTLs (seconds per endpoint) ─────────
CACHE_TTL: dict[str, float] = {
    "/position":     10.0,   # race positions
    "/intervals":    10.0,   # gaps between cars
    "/team_radio":    5.0,   # team radio clips
    "/race_control": 15.0,   # race incidents / flags
    "/pit":          15.0,   # pit stops
    "/sessions":     30.0,   # session metadata
    "/drivers":      30.0,   # driver roster
    "/stints":       30.0,   # tyre stints
    "/laps":         30.0,   # lap data
}
CACHE_TTL_DEFAULT = 10.0

# ── Per-path backoff state ────────────────────────────
# Maps endpoint path -> (retry_after_monotonic, current_delay_seconds)
_backoff: dict[str, tuple[float, float]] = {}

# ── OpenF1 response cache ─────────────────────────────
# Maps cache_key -> {"data": list, "mono": float, "cached_at": str}
# "mono" is time.monotonic() timestamp of last successful fetch.
_cache: dict[str, dict] = {}
# One asyncio.Lock per cache key — collapses concurrent requests into one
# OpenF1 call (stampede prevention).
_cache_locks: dict[str, asyncio.Lock] = {}


def _cache_key(path: str, params: dict | None) -> str:
    """Stable cache key from endpoint path + sorted query params."""
    if not params:
        return path
    return path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))


def _get_cache_lock(key: str) -> asyncio.Lock:
    if key not in _cache_locks:
        _cache_locks[key] = asyncio.Lock()
    return _cache_locks[key]


def _blank_state() -> dict[str, Any]:
    return {
        "session_key": None,
        "session_name": "Waiting for session data…",
        "circuit": "—",
        "session_type": "—",
        "year": datetime.now(timezone.utc).year,
        "is_live": False,       # session is currently happening
        "is_race": False,       # session type is Race or Sprint
        "lap": 0,
        "total_laps": 0,
        "lap_pct": 0.0,
        "status": "none",       # none | yellow | double_yellow | sc | vsc | red
        "status_message": "",
        "drivers": [],
        "incidents": [],
        "radio": [],
        "pit_stops": [],
        "last_updated": "",
    }


# ── OpenF1 helpers ────────────────────────────────────

async def _of1(client: httpx.AsyncClient, path: str, params: dict | None = None) -> list:
    """
    Fetch from OpenF1 REST API with TTL caching and stampede prevention.

    - Returns cached data immediately if it is still within the TTL window.
    - Uses a per-key asyncio.Lock so that N simultaneous callers collapse into
      exactly ONE outbound OpenF1 request; all callers receive the same result.
    - On 429 or any network error, returns the last known-good cached data so
      the UI never shows empty sections.
    """
    key      = _cache_key(path, params)
    ttl      = CACHE_TTL.get(path, CACHE_TTL_DEFAULT)
    now_mono = time.monotonic()

    # Fast path: serve from cache without acquiring any lock.
    cached = _cache.get(key)
    if cached and (now_mono - cached["mono"]) < ttl:
        return cached["data"]

    # Slow path: acquire the per-key lock (stampede protection).
    lock = _get_cache_lock(key)
    async with lock:
        # Re-check inside the lock; another coroutine may have fetched while
        # we were waiting.
        now_mono = time.monotonic()
        cached   = _cache.get(key)
        if cached and (now_mono - cached["mono"]) < ttl:
            return cached["data"]

        # Check backoff (rate-limit penalty still active).
        if path in _backoff:
            retry_after, _ = _backoff[path]
            if now_mono < retry_after:
                cached_data = _cache.get(key, {}).get("data", [])
                log.debug("OpenF1 %s — in backoff, returning cached (%d records)", path, len(cached_data))
                return cached_data

        of1_key = os.getenv("OPENF1_API_KEY", "")
        headers = {"Authorization": f"Bearer {of1_key}"} if of1_key else {}
        try:
            r = await client.get(
                f"{OPENF1}{path}",
                params=params or {},
                headers=headers,
                timeout=OPENF1_TIMEOUT,
            )
            if r.status_code == 401:
                log.warning("OpenF1 %s 401 — API key required during live session. Set OPENF1_API_KEY env var.", path)
                return _cache.get(key, {}).get("data", [])
            if r.status_code == 429:
                new_delay = min(_backoff[path][1] * 2, BACKOFF_MAX) if path in _backoff else BACKOFF_BASE
                _backoff[path] = (now_mono + new_delay, new_delay)
                log.warning("OpenF1 %s 429 — backing off %.0fs (serving cached)", path, new_delay)
                return _cache.get(key, {}).get("data", [])

            r.raise_for_status()
            _backoff.pop(path, None)   # successful response — reset penalty

            data   = r.json()
            result = data if isinstance(data, list) else [data]
            _cache[key] = {
                "data":      result,
                "mono":      now_mono,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
            return result

        except httpx.HTTPStatusError as exc:
            log.warning("OpenF1 %s failed: %s", path, exc)
            return _cache.get(key, {}).get("data", [])
        except Exception as exc:
            log.warning("OpenF1 %s failed: %s", path, exc)
            return _cache.get(key, {}).get("data", [])


def _latest_per_driver(records: list[dict], sort_key: str) -> dict[int, dict]:
    """
    Collapse a stream of records into one record per driver_number,
    keeping whichever has the lexicographically greatest sort_key value.
    """
    best: dict[int, dict] = {}
    for rec in records:
        dn = rec.get("driver_number")
        if dn is None:
            continue
        existing = best.get(dn)
        if existing is None or (rec.get(sort_key) or "") > (existing.get(sort_key) or ""):
            best[dn] = rec
    return best


def _format_gap(raw, position: int) -> str:
    if position == 1 or raw is None or raw == 0 or raw == 0.0:
        return "LEADER"
    if isinstance(raw, (int, float)):
        if raw > 90:
            return "+1 LAP"          # rough heuristic for lapped cars
        return f"+{raw:.3f}"
    s = str(raw).strip()
    return s if s.startswith("+") else f"+{s}"


def _build_incidents(rc_raw: list[dict]) -> list[dict]:
    incidents = []
    for rc in reversed(rc_raw):
        flag = (rc.get("flag") or "").upper()
        msg  = rc.get("message", "") or ""
        if flag and flag not in ("CLEAR", "GREEN") and rc.get("scope") != "Sector":
            incidents.append({"lap": rc.get("lap_number"), "flag": flag, "msg": msg, "date": rc.get("date", "")})
        elif any(kw in msg.upper() for kw in ("RETIRED", "STOP", "MEDICAL", "PIT ENTRY CLOSED")):
            incidents.append({"lap": rc.get("lap_number"), "flag": flag or "INFO", "msg": msg, "date": rc.get("date", "")})
        if len(incidents) >= 6:
            break
    return incidents


def _detect_flag(rc_records: list[dict]) -> tuple[str, str]:
    """
    Walk race control records newest-first; return (status, message).
    Stops when it hits a track-wide flag or CLEAR.
    """
    # Filter to track-scope or no-scope flag events; skip sector-level events
    track_events = [
        r for r in rc_records
        if r.get("category") == "Flag"
        and r.get("scope") in ("Track", None, "")
        and r.get("flag")
    ]
    if not track_events:
        return "none", ""

    # Most recent track-level flag
    latest = track_events[-1]
    flag = (latest.get("flag") or "").upper()
    msg  = latest.get("message", "") or ""

    if flag == "RED":
        return "red", msg or "Red Flag — Race Suspended"
    if "SAFETY CAR" in flag:
        return "sc", msg or "Safety Car Deployed"
    if "VIRTUAL" in flag:
        return "vsc", msg or "Virtual Safety Car Deployed"
    if flag == "DOUBLE YELLOW":
        return "double_yellow", msg or "Double Yellow Flag"
    if flag == "YELLOW":
        return "yellow", msg or "Yellow Flag"
    if flag == "CLEAR" or flag == "GREEN":
        return "none", ""

    return "none", ""


# ── Data refresh ──────────────────────────────────────

async def _refresh() -> dict[str, Any]:
    s = _blank_state()

    async with httpx.AsyncClient(follow_redirects=True) as client:

        # ── Session ───────────────────────────────────
        sessions = await _of1(client, "/sessions", {"session_key": "latest"})
        if not sessions:
            log.warning("No session data from OpenF1")
            return s

        sess = sessions[-1]
        session_key = sess["session_key"]
        session_type = sess.get("session_type", "")
        location = sess.get("location", "")
        circuit  = sess.get("circuit_short_name", location)
        year     = sess.get("year", datetime.now(timezone.utc).year)

        s["session_key"]  = session_key
        s["session_name"] = f"{year} {location} — {sess.get('session_name', session_type)}"
        s["circuit"]      = circuit
        s["session_type"] = sess.get("session_name", session_type)
        s["year"]         = year
        s["is_race"]      = session_type in ("Race", "Sprint")

        # Determine if session is currently live
        now = datetime.now(timezone.utc)
        try:
            date_start = datetime.fromisoformat(str(sess["date_start"]).replace("Z", "+00:00"))
            date_end_raw = sess.get("date_end")
            if date_end_raw:
                date_end = datetime.fromisoformat(str(date_end_raw).replace("Z", "+00:00"))
                s["is_live"] = date_start <= now <= date_end
            else:
                # date_end is None → session started but hasn't ended yet → LIVE
                s["is_live"] = date_start <= now
        except Exception as exc:
            log.warning("[REFRESH] is_live parse failed: %s", exc)
            s["is_live"] = False

        # ── Parallel fetches ──────────────────────────
        (
            drivers_raw,
            positions_raw,
            intervals_raw,
            stints_raw,
            rc_raw,
            radio_raw,
            pits_raw,
        ) = await asyncio.gather(
            _of1(client, "/drivers",      {"session_key": session_key}),
            _of1(client, "/position",     {"session_key": session_key}),
            _of1(client, "/intervals",    {"session_key": session_key}),
            _of1(client, "/stints",       {"session_key": session_key}),
            _of1(client, "/race_control", {"session_key": session_key}),
            _of1(client, "/team_radio",   {"session_key": session_key}),
            _of1(client, "/pit",          {"session_key": session_key}),
        )

        # For current lap, fetch just one driver's laps (fast, ~50 records)
        laps_raw = await _of1(
            client, "/laps",
            {"session_key": session_key, "driver_number": drivers_raw[0]["driver_number"]}
        ) if drivers_raw else []

        # ── Driver metadata ───────────────────────────
        driver_meta: dict[int, dict] = {}
        for d in drivers_raw:
            dn = d.get("driver_number")
            if dn is not None:
                driver_meta[dn] = d

        # ── Current lap ───────────────────────────────
        if laps_raw:
            lap_nums = [r["lap_number"] for r in laps_raw if r.get("lap_number")]
            s["lap"] = max(lap_nums) if lap_nums else 0
        else:
            # Fallback: infer from completed stints
            ended = [r["lap_end"] for r in stints_raw if r.get("lap_end")]
            s["lap"] = max(ended) if ended else 0

        # ── Total laps ────────────────────────────────
        total = 0
        for key, laps in CIRCUIT_LAPS.items():
            if key.lower() in circuit.lower():
                total = laps
                break
        if not total:
            # Try from FastF1 schedule (non-blocking executor call)
            try:
                loop = asyncio.get_event_loop()
                def _ff1_total():
                    ev = fastf1.get_event(year, location)
                    return int(getattr(ev, "RoundNumber", 0))  # not ideal but triggers cache
                await loop.run_in_executor(None, _ff1_total)
            except Exception:
                pass
        s["total_laps"] = total
        if total and s["lap"]:
            s["lap_pct"] = round((s["lap"] / total) * 100, 1)

        # ── Flag / session status ─────────────────────
        s["status"], s["status_message"] = _detect_flag(rc_raw)

        # ── Race incidents (last 6 significant events) ─
        s["incidents"] = _build_incidents(rc_raw)

        # ── Team Radio (most recent 3 clips) ──────────
        radio_entries = []
        for r in reversed(radio_raw):
            dn   = r.get("driver_number")
            meta = driver_meta.get(dn, {})
            radio_entries.append({
                "driver":  meta.get("name_acronym", str(dn)),
                "team":    meta.get("team_name", ""),
                "url":     r.get("recording_url", ""),
                "date":    r.get("date", ""),
            })
            if len(radio_entries) >= 3:
                break
        s["radio"] = radio_entries

        # ── Positions ─────────────────────────────────
        latest_pos  = _latest_per_driver(positions_raw,  "date")
        latest_int  = _latest_per_driver(intervals_raw,  "date")
        latest_stint = _latest_per_driver(stints_raw,    "stint_number")

        # All stints per driver for strategy display
        stints_by_driver: dict[int, list] = {}
        for st in stints_raw:
            dn = st.get("driver_number")
            if dn is not None:
                stints_by_driver.setdefault(dn, []).append(st)
        for dn in stints_by_driver:
            stints_by_driver[dn].sort(key=lambda x: x.get("stint_number", 0))

        # ── Build driver list ─────────────────────────
        drivers_out: list[dict] = []
        current_lap = s["lap"]

        sorted_pos = sorted(
            latest_pos.items(),
            key=lambda kv: kv[1].get("position", 99),
        )

        for dn, pos_rec in sorted_pos:
            pos  = pos_rec.get("position", 99)
            meta = driver_meta.get(dn, {})

            # Name formatting
            first = meta.get("first_name", "")
            last  = meta.get("last_name", "")
            if first and last:
                name = f"{first[0]}. {last}"
            else:
                name = meta.get("broadcast_name", str(dn))

            # Team colour — OpenF1 omits the #
            raw_colour = meta.get("team_colour", "888888") or "888888"
            colour = f"#{raw_colour}" if not raw_colour.startswith("#") else raw_colour

            # Gap
            int_rec = latest_int.get(dn, {})
            gap_str = _format_gap(int_rec.get("gap_to_leader"), pos)

            # Current tyre stint
            stint = latest_stint.get(dn, {})
            compound_raw = (stint.get("compound") or "UNKNOWN").upper()
            compound = COMPOUND_SHORT.get(compound_raw, "?")
            lap_start_of_stint = stint.get("lap_start") or 0
            stint_laps = max(0, current_lap - lap_start_of_stint) if lap_start_of_stint else 0

            # Full strategy (all stints for this driver)
            strategy: list[dict] = []
            for st in stints_by_driver.get(dn, []):
                c     = COMPOUND_SHORT.get((st.get("compound") or "UNKNOWN").upper(), "?")
                lsrt  = st.get("lap_start") or 0
                lend  = st.get("lap_end")    # None if stint still active
                laps  = (lend - lsrt) if lend else max(0, current_lap - lsrt)
                strategy.append({"compound": c, "laps": laps, "active": lend is None})

            drivers_out.append({
                "pos":      pos,
                "number":   dn,
                "code":     meta.get("name_acronym", str(dn)),
                "name":     name,
                "team":     meta.get("team_name", ""),
                "colour":   colour,
                "tyre":     compound,
                "stintLap": stint_laps,
                "gap":      gap_str,
                "strategy": strategy,
            })

        s["drivers"] = drivers_out

        # ── Pit stops ─────────────────────────────────
        # latest_pit_per_driver gives us the most recent pit record per driver.
        # pit_duration is None while the car is still in the pit lane.
        latest_pit = _latest_per_driver(pits_raw, "date")
        pit_stops_out: list[dict] = []
        for dn, pit_rec in latest_pit.items():
            meta = driver_meta.get(dn, {})
            first = meta.get("first_name", "")
            last  = meta.get("last_name", "")
            if first and last:
                pit_name = f"{first[0]}. {last}"
            else:
                pit_name = meta.get("broadcast_name", str(dn))
            raw_colour = meta.get("team_colour", "888888") or "888888"
            pit_colour = f"#{raw_colour}" if not raw_colour.startswith("#") else raw_colour
            pit_stops_out.append({
                "driver_number": dn,
                "code":     meta.get("name_acronym", str(dn)),
                "name":     pit_name,
                "team":     meta.get("team_name", ""),
                "colour":   pit_colour,
                "lap":      pit_rec.get("lap_number"),
                "date":     pit_rec.get("date", ""),
                "duration": pit_rec.get("pit_duration"),
            })
        s["pit_stops"] = pit_stops_out

        s["last_updated"] = datetime.now(timezone.utc).isoformat()

    return s


# ── Background poller ─────────────────────────────────

async def _poller():
    global _state
    while True:
        try:
            is_live = _state.get("is_live", False)
            # Also poll fast if session_key is set (session exists, may be live)
            session_active = bool(_state.get("session_key"))
            interval = POLL_INTERVAL_LIVE if (is_live or session_active) else POLL_INTERVAL_IDLE
            log.info("Fetching race data (session_key=latest, live=%s, next=%ds)…", is_live, interval)
            new_state = await _refresh()
            async with _lock:
                _state = new_state

            _broadcast(json.dumps(_state))

            log.info(
                "Updated: %s, Lap %s/%s, %d drivers, status=%s",
                new_state.get("session_name"),
                new_state.get("lap"),
                new_state.get("total_laps"),
                len(new_state.get("drivers", [])),
                new_state.get("status"),
            )
        except Exception:
            log.exception("Poller iteration failed")
            interval = POLL_INTERVAL_IDLE  # back off on error

        await asyncio.sleep(interval)


def _broadcast(payload: str) -> None:
    """Push a JSON payload to all SSE subscribers, dropping stale queues."""
    dead: list[asyncio.Queue] = []
    for q in list(_subscribers):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass


async def _poll_critical():
    """Fetch race_control and pit at a faster cadence during live sessions only."""
    global _state
    while True:
        is_live = _state.get("is_live", False)
        interval = POLL_CRITICAL_LIVE if is_live else POLL_CRITICAL_IDLE
        await asyncio.sleep(interval)
        session_key = _state.get("session_key")
        if not session_key:
            continue
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                rc_raw, pits_raw = await asyncio.gather(
                    _of1(client, "/race_control", {"session_key": session_key}),
                    _of1(client, "/pit",          {"session_key": session_key}),
                )
            changed = False
            if rc_raw:
                status, msg = _detect_flag(rc_raw)
                incidents = _build_incidents(rc_raw)
                async with _lock:
                    _state["status"] = status
                    _state["status_message"] = msg
                    _state["incidents"] = incidents
                changed = True

            if pits_raw:
                # Rebuild pit_stops from fresh data
                dm: dict[int, dict] = {}
                for d in _state.get("drivers", []):
                    dm[d["number"]] = d

                latest_pit = _latest_per_driver(pits_raw, "date")
                pit_stops_out: list[dict] = []
                for dn, pit_rec in latest_pit.items():
                    drv = dm.get(dn, {})
                    pit_stops_out.append({
                        "driver_number": dn,
                        "code":     drv.get("code", str(dn)),
                        "name":     drv.get("name", str(dn)),
                        "team":     drv.get("team", ""),
                        "colour":   drv.get("colour", "#888888"),
                        "lap":      pit_rec.get("lap_number"),
                        "date":     pit_rec.get("date", ""),
                        "duration": pit_rec.get("pit_duration"),
                    })
                async with _lock:
                    _state["pit_stops"] = pit_stops_out
                changed = True

            if changed:
                _broadcast(json.dumps(_state))
        except Exception:
            log.exception("Critical poller failed")


# ── RSS news helpers ──────────────────────────────────

def _time_ago(dt: datetime) -> str:
    """Return a human-readable relative time string."""
    diff_s = (datetime.now(timezone.utc) - dt).total_seconds()
    if diff_s < 120:
        return "just now"
    if diff_s < 3600:
        return f"{int(diff_s / 60)}m ago"
    if diff_s < 86400:
        return f"{int(diff_s / 3600)}h ago"
    return f"{int(diff_s / 86400)}d ago"


async def _summarise_story(client: anthropic.AsyncAnthropic, title: str, description: str) -> str:
    """Summarise one news story with Haiku. Falls back to raw description on error."""
    snippet = (description or "").strip()[:800]
    prompt = (
        f"Headline: {title}. Description: {snippet}.\n\n"
        "You are an F1 expert explaining news to a casual fan. Using the headline as your primary source, "
        "write a cohesive, 2-sentence summary.\n\n"
        "Do not output an ellipsis (...). "
        "Ensure the final sentence ends with a proper period. "
        "The resulting text must be at least 40 words long."
    )
    try:
        resp = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        log.warning("[NEWS] Summarisation failed: %s", exc)
        return snippet[:300]


async def fetch_f1_news() -> list[dict]:
    """
    Fetch from _NEWS_FEEDS, keep stories from the last 24 h, summarise with Haiku.
    Returns a list of dicts ready for /api/news.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    raw: list[dict] = []

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as http:
        for url in _NEWS_FEEDS:
            try:
                r = await http.get(url)
                r.raise_for_status()
                feed = feedparser.parse(r.text)
                # Determine source badge from feed URL
                if "formula1.com" in url:
                    badge = "F1 Official"
                elif "motorsport.com" in url:
                    badge = "Motorsport"
                else:
                    badge = "FIA"

                for entry in feed.entries[:5]:
                    pub: datetime | None = None
                    if getattr(entry, "published_parsed", None):
                        try:
                            pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        except Exception:
                            pass
                    # Skip stories older than 24 h (only when we have a valid date)
                    if pub and pub < cutoff:
                        continue

                    # Extract image URL from media:content or enclosures
                    image_url = ""
                    media_content = getattr(entry, "media_content", None)
                    if media_content and isinstance(media_content, list) and len(media_content) > 0:
                        image_url = media_content[0].get("url", "")
                    if not image_url:
                        enclosures = getattr(entry, "enclosures", None)
                        if enclosures and isinstance(enclosures, list) and len(enclosures) > 0:
                            enc = enclosures[0]
                            if isinstance(enc, dict):
                                t = enc.get("type", "")
                                if t.startswith("image"):
                                    image_url = enc.get("href", enc.get("url", ""))

                    raw.append({
                        "title":        (entry.get("title") or "").strip(),
                        "description":  (entry.get("summary") or entry.get("description") or "").strip(),
                        "link":         entry.get("link", ""),
                        "pub":          pub,
                        "image":        image_url,
                        "source_badge": badge,
                    })
            except Exception as exc:
                log.warning("[NEWS] Feed fetch failed (%s): %s", url, exc)

    if not raw:
        return []

    # Deduplicate by normalised title
    seen: set[str] = set()
    unique: list[dict] = []
    for item in raw:
        key = item["title"].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    # Newest first, cap at 10
    unique.sort(
        key=lambda x: x["pub"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    unique = unique[:10]

    # Parallel AI summaries
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key:
        ai_client = anthropic.AsyncAnthropic(api_key=api_key)
        summaries = await asyncio.gather(
            *[_summarise_story(ai_client, it["title"], it["description"]) for it in unique],
            return_exceptions=True,
        )
    else:
        summaries = [it["description"][:300] for it in unique]

    result = []
    for item, summary in zip(unique, summaries):
        if isinstance(summary, Exception):
            summary = item["description"][:300]
        result.append({
            "title":        item["title"],
            "summary":      summary,
            "time_ago":     _time_ago(item["pub"]) if item["pub"] else "recently",
            "source":       item["link"],
            "image":        item.get("image", ""),
            "source_badge": item.get("source_badge", ""),
        })
    return result


_REDDIT_FALLBACK: list[dict] = [
    {"title": "Miami GP preview — what to watch this weekend", "score": 2400, "url": "https://reddit.com/r/formula1", "num_comments": 340, "created": 0},
    {"title": "Antonelli championship lead analysis", "score": 1800, "url": "https://reddit.com/r/formula1", "num_comments": 210, "created": 0},
    {"title": "Italian tax investigation explained", "score": 3200, "url": "https://reddit.com/r/formula1", "num_comments": 450, "created": 0},
]

# ── UPDATE EVERY THURSDAY before a race weekend ───────
_TRENDS_FALLBACK: list[dict] = [
    {"title": "Miami GP 2026",             "source": "F1 Trending"},
    {"title": "Antonelli championship",    "source": "F1 Trending"},
    {"title": "F1 Italy investigation",    "source": "F1 Trending"},
    {"title": "Hamilton Ferrari Miami",    "source": "F1 Trending"},
    {"title": "Verstappen engine upgrade", "source": "F1 Trending"},
]


# ── General response cache for /api/chat ─────────────
_RESPONSE_CACHE_TTL = 4 * 3600  # 4 hours in seconds
response_cache: dict[str, dict] = {}


def _rc_key(message: str) -> str:
    """MD5 hash of the lowercased, stripped user message."""
    return hashlib.md5(message.lower().strip().encode()).hexdigest()


def _purge_response_cache() -> None:
    """Remove entries older than _RESPONSE_CACHE_TTL."""
    cutoff = time.time() - _RESPONSE_CACHE_TTL
    stale = [k for k, v in response_cache.items() if v["ts"] < cutoff]
    for k in stale:
        del response_cache[k]
    if stale:
        log.debug("[CACHE] Purged %d stale entries", len(stale))


def _get_rc(key: str) -> str | None:
    entry = response_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _RESPONSE_CACHE_TTL:
        return entry["reply"]
    if entry:
        del response_cache[key]
    return None


def _set_rc(key: str, reply: str) -> None:
    response_cache[key] = {"reply": reply, "ts": time.time()}


# ── Question cache (System 1) ─────────────────────────

_question_cache: dict[str, dict] = {}
_CACHE_TTL = 3600  # 1 hour

_STATIC_QUESTIONS = [
    'what is drs', 'what is an undercut', 'what is a safety car',
    'what is parc ferme', 'what is box box', 'what is vsc',
    'what is the fastest lap', 'how does qualifying work',
    'how do points work', 'what is a formation lap',
    'what is a pit stop', 'who is antonelli', 'who is hamilton',
    'who is verstappen', 'what is active aero',
    'explain drs', 'explain the safety car',
]


def _is_cacheable(question: str) -> bool:
    q = question.lower().strip()
    return any(sq in q for sq in _STATIC_QUESTIONS)


def _cache_key(question: str, style: str, model: str = "") -> str:
    combined = f"{question.lower().strip()}_{style}_{model}"
    return hashlib.md5(combined.encode()).hexdigest()


def _get_cached(question: str, style: str, model: str = "") -> str | None:
    key = _cache_key(question, style, model)
    entry = _question_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["response"]
    if entry:
        del _question_cache[key]
    return None


def _set_cached(question: str, style: str, response: str, model: str = "") -> None:
    key = _cache_key(question, style, model)
    _question_cache[key] = {"response": response, "ts": time.time()}


# ── Model routing (System 2) ──────────────────────────

_SIMPLE_PATTERNS = [
    'who is', 'what is', 'how many', 'what does', 'when did',
    'who won', 'how old', 'what team', 'where is',
    'what position', 'how do points',
]
_COMPLEX_PATTERNS = [
    'explain', 'why does', 'how does', 'compare', 'predict',
    'strategy', 'impact', 'affect', 'difference', 'should',
    'would', 'could', 'analyse', 'breakdown', 'detail',
]


def _model_for_question(question: str) -> str:
    q = question.lower()
    if any(p in q for p in _COMPLEX_PATTERNS):
        return "claude-sonnet-4-20250514"
    if any(p in q for p in _SIMPLE_PATTERNS):
        return "claude-haiku-4-5-20251001"
    return "claude-sonnet-4-20250514"


async def fetch_reddit_trending():
    global cached_reddit
    url = "https://www.reddit.com/r/formula1/hot.json?limit=10"
    headers = {"User-Agent": "AskTheGridAI:v1.0 (by /u/askthegridai)"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"Reddit returned {r.status_code} — using fallback")
            cached_reddit = _REDDIT_FALLBACK
            return
        data = r.json()
        posts = []
        for post in data['data']['children']:
            p = post['data']
            if not p.get('stickied'):
                posts.append({
                    'title': p['title'],
                    'score': p['score'],
                    'url': 'https://reddit.com' + p['permalink'],
                    'num_comments': p['num_comments'],
                    'created': p['created_utc'],
                })
        cached_reddit = posts[:8] if posts else _REDDIT_FALLBACK
    except Exception as e:
        print(f"Reddit fetch failed: {e} — using fallback")
        cached_reddit = _REDDIT_FALLBACK


async def fetch_google_trends():
    global cached_trends
    # Google Trends RSS blocks server IPs reliably — use curated fallback list.
    # Update _TRENDS_FALLBACK manually every Thursday before each race weekend.
    cached_trends = _TRENDS_FALLBACK


async def _news_poller():
    """Background task: refresh news + reddit + trends cache every _NEWS_CACHE_TTL seconds."""
    while True:
        try:
            log.info("[NEWS] Refreshing RSS news cache…")
            items = await fetch_f1_news()
            async with _news_lock:
                _news_cache["items"] = items
                _news_cache["refreshed_at"] = datetime.now(timezone.utc).isoformat()
            log.info("[NEWS] Cached %d items", len(items))
        except Exception as exc:
            log.warning("[NEWS] Poller error: %s", exc)
        try:
            await fetch_reddit_trending()
            log.info("[NEWS] Cached %d Reddit posts", len(cached_reddit))
        except Exception as exc:
            log.warning("[NEWS] Reddit poller error: %s", exc)
        try:
            await fetch_google_trends()
            log.info("[NEWS] Cached %d trend terms", len(cached_trends))
        except Exception as exc:
            log.warning("[NEWS] Trends poller error: %s", exc)
        await asyncio.sleep(_NEWS_CACHE_TTL)


# ── App lifespan ──────────────────────────────────────

@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _state, _log_lock, _WAITLIST_LOCK, _VISITS_LOCK
    _log_lock      = asyncio.Lock()
    _WAITLIST_LOCK = asyncio.Lock()
    _VISITS_LOCK   = asyncio.Lock()
    _state = _blank_state()
    # Kick an immediate refresh so data is ready before first SSE client connects
    try:
        _state = await _refresh()
        log.info("[STARTUP] Initial refresh complete: %s, live=%s", _state.get("session_name"), _state.get("is_live"))
    except Exception as exc:
        log.warning("[STARTUP] Initial refresh failed: %s", exc)
    task_regular  = asyncio.create_task(_poller())
    task_critical = asyncio.create_task(_poll_critical())
    task_news     = asyncio.create_task(_news_poller())
    yield
    task_regular.cancel()
    task_critical.cancel()
    task_news.cancel()
    for task in (task_regular, task_critical, task_news):
        try:
            await task
        except asyncio.CancelledError:
            pass


# ── FastAPI app ───────────────────────────────────────

app = FastAPI(title="PitWall AI", version="1.0.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Serve the frontend HTML ───────────────────────────
_html_file   = Path(__file__).parent / "pitwall-ai.html"
_VISITS_LOG  = Path(os.environ.get("DATA_DIR", ".")) / "visits_log.csv"
_VISITS_LOCK: asyncio.Lock | None = None   # initialised in _lifespan

async def _log_visit(request: Request) -> None:
    if _VISITS_LOCK is None:
        return
    ip  = _get_client_ip(request)
    ua  = request.headers.get("user-agent", "")[:200]
    ref = request.headers.get("referer", "")[:200]
    ts  = datetime.now(timezone.utc).isoformat(timespec="seconds")
    async with _VISITS_LOCK:
        try:
            if not _VISITS_LOG.exists():
                with open(_VISITS_LOG, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(["timestamp", "ip", "user_agent", "referrer"])
            with open(_VISITS_LOG, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([ts, ip, ua, ref])
        except Exception as exc:
            log.debug("[VISITS] Write failed: %s", exc)

@app.get("/")
async def serve_frontend(request: Request):
    from fastapi.responses import FileResponse
    asyncio.create_task(_log_visit(request))
    return FileResponse(_html_file, media_type="text/html")


@app.get("/api/visit-stats")
async def visit_stats(key: str = ""):
    """Owner-only: visit analytics from visits_log.csv."""
    if key != "atgaiimamw2026":
        raise HTTPException(status_code=403, detail="Forbidden")
    if not _VISITS_LOG.exists():
        return {"total": 0, "today": 0, "unique_ips": 0, "recent": []}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows: list[dict] = []
    try:
        with open(_VISITS_LOG, "r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
    except Exception as exc:
        log.warning("[VISITS] Read failed: %s", exc)
        return {"total": 0, "today": 0, "unique_ips": 0, "recent": []}
    total      = len(rows)
    today_cnt  = sum(1 for r in rows if r.get("timestamp", "").startswith(today))
    unique_ips = len({r.get("ip", "") for r in rows if r.get("ip")})
    recent = [
        {"timestamp": r.get("timestamp", ""), "ip": r.get("ip", ""), "referrer": r.get("referrer", "")}
        for r in rows[-10:][::-1]
    ]
    return {"total": total, "today": today_cnt, "unique_ips": unique_ips, "recent": recent}


@app.get("/atg-logo.svg")
async def serve_logo():
    from fastapi.responses import FileResponse
    return FileResponse(Path(__file__).parent / "atg-logo.svg", media_type="image/svg+xml")


@app.get("/api/health")
async def health():
    key_set = bool(os.getenv("ANTHROPIC_API_KEY"))
    return {"ok": True, "last_updated": _state.get("last_updated"), "api_key_set": key_set}


@app.get("/api/state")
async def get_state():
    async with _lock:
        return _state


# ── IP rate-limit helpers ─────────────────────────────

def _get_client_ip(request: Request) -> str:
    """Return the real client IP, honouring Railway's X-Forwarded-For header."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _enforce_rate_limit(request: Request) -> None:
    """Sliding-window rate limiter: max _RATE_MAX requests per IP per _RATE_WINDOW seconds."""
    ip = _get_client_ip(request)
    now = time.time()
    async with _rate_lock:
        timestamps = _rate_data.get(ip, [])
        # Drop entries older than the window
        timestamps = [t for t in timestamps if now - t < _RATE_WINDOW]
        if len(timestamps) >= _RATE_MAX:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait before asking more questions.",
            )
        timestamps.append(now)
        _rate_data[ip] = timestamps


# ── Chat proxy ────────────────────────────────────────

_FORMATTING_INSTRUCTIONS = """FORMATTING RULES — ALWAYS FOLLOW:

Structure every response like this:

PART 1 — THE SHORT VERSION:
One or two sentences maximum. Bold the single most important term using **term** syntax. This is what someone needs if they only read one thing.
Example: The FIA just changed how battery energy deploys on straights. This directly affects **Verstappen** more than anyone else on the grid.

PART 2 — THE DETAIL:
Two to three short paragraphs maximum. Each paragraph is three sentences max. Bold key terms the first time they appear like **undercut**, **safety car**, **active aero**. Never write walls of text. One idea per paragraph.

PART 3 — FOLLOW UP QUESTIONS:
Always end every response with exactly three suggested follow-up questions on a single line in this exact format:
FOLLOWUPS: First question here? | Second question here? | Third question here?

The word FOLLOWUPS: must appear at the start of that line. Questions separated by | pipe character.

Additional rules:
Never use - for bullet points.
Never use ## for headers.
Write in flowing conversational paragraphs only.
If you need to list things write them naturally in a sentence."""


_WEB_SEARCH_INSTRUCTIONS = """WEB SEARCH INSTRUCTIONS:
When answering questions about current F1 news or events:
1. Search for the topic first
2. Read the full content of the top 2-3 results, not just headlines
3. Synthesize everything you read into one clear explanation
4. Always explain in the user's selected style
5. Never just repeat headlines
6. Connect the story to the championship and what it means for upcoming races
7. End with what to watch for next"""


_CRITICAL_CONTEXT = """CRITICAL CONTEXT — READ FIRST:
Today's date is April 2026.
The 2026 F1 season is currently underway with 4 races completed.
This is NOT 2024 or 2025.

Lewis Hamilton is NOW at Ferrari.
He LEFT Mercedes after 2024.
He signed with Ferrari for 2026.
This already happened.

Kimi Antonelli replaced Hamilton at Mercedes for 2026 and is currently leading the championship.

When anyone asks about Hamilton at Ferrari treat this as current fact not future speculation.
When anyone asks about Antonelli at Mercedes treat this as current fact not future speculation.

Never say 'Hamilton might move to Ferrari' or 'if Hamilton joins Ferrari'.
He is already there. It already happened.

Never reference 2024 season results as the most recent season.
The most recent completed races are from the 2026 season."""


class ChatRequest(BaseModel):
    system:   str
    messages: list[dict]
    driver:   str | None = None   # set when user is on a driver profile page
    model:    str | None = None   # 'haiku' → force Haiku; None → auto-route
    context:  str | None = None   # semantic context for model routing


_HAIKU_CONTEXTS = {
    "news_summary", "news_insight", "fan_topics", "article_summary",
    "rule_explanation", "incident_explanation", "trivia", "driver_profile",
}
_SONNET_CONTEXTS = {
    "live_race", "race_strategy", "championship", "homepage_insight",
}


def _select_model(req: "ChatRequest") -> str:
    """
    Model routing priority:
      1. Explicit req.model field ('haiku' / 'sonnet') → use that
      2. Semantic context → _HAIKU_CONTEXTS or _SONNET_CONTEXTS
      3. Message length < 80 chars → Haiku
      4. Message length > 120 chars → Sonnet
      5. Fall back to _model_for_question() pattern matching
    """
    _H = "claude-haiku-4-5-20251001"
    _S = "claude-sonnet-4-20250514"

    # Explicit override
    if req.model == "haiku":
        return _H
    if req.model in ("sonnet", "claude-sonnet-4-6"):
        return _S

    # Context-based routing
    ctx = (req.context or "").lower()
    if ctx in _HAIKU_CONTEXTS:
        return _H
    if ctx in _SONNET_CONTEXTS:
        return _S

    # Message length
    last_msg = ""
    for m in reversed(req.messages):
        if m.get("role") == "user":
            last_msg = m.get("content", "")
            break
    msg_len = len(last_msg)

    if msg_len < 80:
        return _H
    if msg_len > 120:
        return _S

    return _model_for_question(last_msg)


def _build_dynamic_context() -> str:
    """
    Build a live data block from all backend caches — injected fresh into
    every chat request so the AI always has current standings, news, and
    session state without the frontend needing to include it.
    """
    sections: list[str] = []

    # Championship standings
    standings_data = _standings_cache.get("data")
    if standings_data and standings_data.get("standings"):
        lines = []
        for d in standings_data["standings"][:10]:
            name = f"{d.get('first_name', '')} {d.get('driver', '')}".strip()
            lines.append(
                f"P{d['position']} {name} — {d['team']} — {d['points']}pts"
                + (f" ({d['wins']}W)" if d.get("wins") else "")
            )
        sections.append("LIVE CHAMPIONSHIP STANDINGS:\n" + "\n".join(lines))

    # Latest news headlines
    news_items = _news_cache.get("items", [])
    if news_items:
        headlines = [f"- {item['title']}" for item in news_items[:5]]
        sections.append("LATEST F1 NEWS:\n" + "\n".join(headlines))

    # Reddit trending — excluded from public AI context (owner-only)

    # Google Trends
    if cached_trends:
        terms = ", ".join(t['title'] for t in cached_trends)
        sections.append("TRENDING F1 SEARCHES TODAY:\n" + terms)

    # Current session — trimmed to ~200 chars to keep prompts lean
    state = _state
    if state.get("session_key"):
        lap    = state.get("lap", 0)
        total  = state.get("total_laps", "?")
        name   = state.get("session_name", "unknown")
        status = state.get("status", "none")
        top5   = state.get("drivers", [])[:5]
        top5_str = ", ".join(
            f"P{d['pos']} {d.get('code','?')}" for d in top5
        ) if top5 else "—"
        live_summary = f"{name} Lap {lap}/{total} | {top5_str} | Status:{status}"
        sections.append(f"RACE: {live_summary[:200]}")
        radio = state.get("radio", [])
        if radio:
            last = radio[-1]
            msg  = last.get("msg", last.get("message", ""))[:80]
            sections.append(f"LAST RADIO: {last.get('driver','?')}: {msg}")

    # Weather for next race (if cached)
    wd = _weather_cache.get("data")
    if wd and wd.get("forecast"):
        fc = wd["forecast"]
        race_day = fc[-1] if len(fc) >= 1 else fc[0]
        sections.append(
            f"RACE WEATHER ({wd.get('location','?')}): "
            f"{race_day['condition']}, {race_day['rain_chance']}% rain chance, "
            f"max {race_day['max_temp']}°C, wind {race_day['wind_kmh']} km/h"
        )

    if not sections:
        return ""
    updated = (state.get("last_updated") or "")[:19] or "now"
    return (
        f"[LIVE APP DATA — refreshed {updated} UTC]\n\n"
        + "\n\n".join(sections)
    )


def _build_driver_context(driver_name: str) -> str:
    """
    Return a focused stats block for a specific driver, read from the
    live standings cache.  Empty string if the driver is not found.
    """
    standings_data = _standings_cache.get("data")
    if not standings_data:
        return ""
    for d in standings_data.get("standings", []):
        full_name = f"{d.get('first_name', '')} {d.get('driver', '')}".strip()
        if (
            driver_name.lower() in full_name.lower()
            or driver_name.lower() in d.get("driver", "").lower()
        ):
            return (
                f"DRIVER PROFILE — {full_name}:\n"
                f"Championship position: P{d['position']}\n"
                f"Points: {d['points']}\n"
                f"Team: {d['team']}\n"
                f"Wins this season: {d.get('wins', 0)}\n"
            )
    return ""


# Keywords whose presence in a user message signals that live race data is needed.
# Anything not in this list goes straight to Claude with no cache lookup.
_LIVE_KEYWORDS: frozenset[str] = frozenset([
    # positions / timing
    "position", "positions", "p1", "p2", "p3", "p4", "p5",
    "gap", "gaps", "interval", "intervals", "leading", "leader",
    "top 5", "top five", "top 3", "top three",
    # lap / race progress
    "what lap", "which lap", "current lap", "lap count",
    "how many laps",
    # pit / strategy
    "pit stop", "pit stops", "pitted", "pitting", "pit wall",
    "strategy", "undercut", "overcut", "tyre change", "tire change",
    # live events
    "just happened", "just now", "right now", "happening now",
    "live", "current race", "current positions",
    "what just", "who just",
    # flags / incidents
    "safety car", "red flag", "yellow flag", "vsc", "sc deployed",
    "race control", "incident", "retired", "dnf",
    # radio
    "team radio", "radio message",
])


def _needs_live_context(messages: list[dict]) -> bool:
    """
    Return True only when the latest user message is asking about live
    race data (positions, gaps, pit stops, flags, radio).
    General F1 knowledge questions (rules, history, driver careers,
    "what is DRS") return False and skip the cache lookup entirely.
    """
    text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            text = (m.get("content") or "").lower()
            break
    return any(kw in text for kw in _LIVE_KEYWORDS)


def _build_race_context(state: dict) -> str:
    """
    Compact race snapshot injected into system prompts.
    Only called when _needs_live_context() returns True.
    Reads exclusively from the in-memory cache — never triggers a fresh
    OpenF1 fetch.
    """
    if not state.get("session_key"):
        return ""
    top5 = state.get("drivers", [])[:5]
    top5_str = ", ".join(
        f"P{d['pos']} {d['code']} tyre:{d.get('tyre','?')} "
        f"+{d.get('stintLap', 0)}L gap:{d.get('gap', '?')}"
        for d in top5
    ) if top5 else "no driver data"
    incidents = "; ".join(
        f"Lap {i.get('lap', '?')}: {i.get('msg', '')}"
        for i in (state.get("incidents") or [])[:3]
    ) or "none"
    updated = (state.get("last_updated") or "")[:19] or "unknown"
    return (
        f"\n\n[SERVER RACE DATA — cached {updated} UTC]\n"
        f"Session: {state.get('session_name', '—')} | "
        f"Lap: {state.get('lap', 0)}/{state.get('total_laps', '?')} | "
        f"Status: {state.get('status', 'none')}\n"
        f"Top 5: {top5_str}\n"
        f"Incidents: {incidents}"
    )


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    """Non-streaming chat used by background features (radio translation, strategy)."""
    await _enforce_rate_limit(request)
    print(f"[ENDPOINT] /api/chat called", flush=True)

    # Purge stale cache entries on every request (cheap — dict iteration)
    _purge_response_cache()

    # Build cache key from the last user message
    last_user_msg = ""
    for m in reversed(req.messages):
        if m.get("role") == "user":
            last_user_msg = m.get("content", "")
            break
    cache_key = _rc_key(last_user_msg) if last_user_msg else ""

    if cache_key:
        cached_reply = _get_rc(cache_key)
        if cached_reply:
            print(f"[CACHE HIT]  key={cache_key[:8]}… msg={last_user_msg[:60]!r}", flush=True)
            return JSONResponse({"reply": cached_reply}, headers={"X-Cache": "HIT"})
        print(f"[CACHE MISS] key={cache_key[:8]}… msg={last_user_msg[:60]!r}", flush=True)
        # Log only real user questions that will hit the API (not owner/system)
        if last_user_msg and not last_user_msg.startswith("ATGAI"):
            session_id = _get_client_ip(request)
            asyncio.create_task(_log_question(last_user_msg, session_id))

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not found. Add it to pitwall-backend/.env"
        )

    client = anthropic.AsyncAnthropic(api_key=api_key)

    _chat_model = _select_model(req)
    # Shorter questions need fewer tokens — cap at 300 for speed, 400 globally
    _max_tok = 300 if len(last_user_msg) < 60 else 400

    async def _call_anthropic() -> str:
        response = await client.messages.create(
            model=_chat_model,
            max_tokens=_max_tok,
            system=_CRITICAL_CONTEXT + "\n\n" + req.system,
            messages=req.messages,
        )
        return response.content[0].text

    # Exponential backoff — up to 3 attempts
    reply = None
    last_exc: Exception | None = None
    for _attempt in range(3):
        try:
            reply = await _call_anthropic()
            break
        except anthropic.AuthenticationError:
            raise HTTPException(status_code=401, detail="Invalid Anthropic API key in .env")
        except (anthropic.RateLimitError, anthropic.APIStatusError) as exc:
            is_429 = isinstance(exc, anthropic.RateLimitError) or getattr(exc, "status_code", 0) == 429
            if is_429 and _attempt < 2:
                wait = (2 ** _attempt) * 1.5
                log.warning("[CHAT] 429 — attempt %d, waiting %.1fs", _attempt + 1, wait)
                await asyncio.sleep(wait)
                last_exc = exc
            else:
                last_exc = exc
                break
        except Exception as exc:
            log.warning("[CHAT] Unexpected error: %s", exc)
            return {"reply": "Something went wrong. Please try again in a moment."}

    if reply is None:
        log.warning("[CHAT] All retries exhausted: %s", last_exc)
        return {"reply": "The AI is getting lots of questions right now — try again in a few seconds!"}

    if cache_key and reply:
        _set_rc(cache_key, reply)
    return JSONResponse({"reply": reply}, headers={"X-Cache": "MISS"})


@app.post("/api/chat-stream")
async def chat_stream(req: ChatRequest, request: Request):
    """
    Streaming chat endpoint (Fix 1 + Fix 2).
    Emits SSE tokens so the UI can render text word-by-word.
    Injects the server's cached _state into the system prompt so no fresh
    OpenF1 fetch is needed per question.
    """
    await _enforce_rate_limit(request)
    t0 = time.time()
    print(f"[ENDPOINT] /api/chat-stream called", flush=True)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not found. Add it to pitwall-backend/.env"
        )

    # ── Extract question + choose model ──────────────────
    question = (req.messages[-1].get("content", "") if req.messages else "")
    model = _select_model(req)

    # ── System 1: question cache (static F1 facts only) ──
    if _is_cacheable(question):
        cached_reply = _get_cached(question, req.system, model)
        if cached_reply:
            print(f"[STREAM] Cache hit for: {question[:60]}", flush=True)
            async def stream_cached():
                yield f"data: {json.dumps({'token': cached_reply})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(
                stream_cached(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control":     "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection":        "keep-alive",
                    "X-Model-Used":      "cache",
                },
            )

    print(f"[STREAM] Model={model} question={question[:60]!r}", flush=True)

    # Block 0 — critical context: date + season facts (never cached, always first).
    # Block 1 — formatting rules (no markdown).
    # Block 2 — web search instructions.
    # Block 3 — static (prompt-cached): mode/style instructions from frontend.
    # Block 4 — dynamic (never cached): live standings + news + session + radio.
    # Block 5 — optional: driver profile stats when user is on a driver page.
    # Block 6 — optional: race-specific snapshot when message asks for live data.
    system_blocks: list[dict] = [
        {"type": "text", "text": _CRITICAL_CONTEXT},
        {"type": "text", "text": _FORMATTING_INSTRUCTIONS},
        {"type": "text", "text": _WEB_SEARCH_INSTRUCTIONS},
        {
            "type": "text",
            "text": req.system,
            "cache_control": {"type": "ephemeral"},
        },
    ]

    dynamic_ctx = _build_dynamic_context()
    if dynamic_ctx:
        system_blocks.append({"type": "text", "text": dynamic_ctx})

    if req.driver:
        driver_ctx = _build_driver_context(req.driver)
        if driver_ctx:
            system_blocks.append({"type": "text", "text": driver_ctx})

    if _needs_live_context(req.messages):
        async with _lock:
            state_snap = dict(_state)
        race_ctx = _build_race_context(state_snap)
        if race_ctx:
            system_blocks.append({"type": "text", "text": race_ctx})

    print(f"[STREAM] Context built: {time.time()-t0:.2f}s", flush=True)

    # ── System 2: model routing ───────────────────────────
    # Web search tool only supported on Sonnet; Haiku gets plain call.
    use_web_search = "sonnet" in model
    stream_kwargs: dict = dict(
        model=model,
        max_tokens=1500,
        system=system_blocks,
        messages=req.messages,
    )
    if use_web_search:
        stream_kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]

    async def generate():
        ai_client = anthropic.AsyncAnthropic(api_key=api_key)
        collected: list[str] = []
        try:
            print(f"[STREAM] Calling Claude ({model}): {time.time()-t0:.2f}s", flush=True)
            first_token = True
            async with ai_client.messages.stream(**stream_kwargs) as stream:
                async for text in stream.text_stream:
                    if first_token:
                        print(f"[STREAM] First token: {time.time()-t0:.2f}s", flush=True)
                        first_token = False
                    collected.append(text)
                    yield f"data: {json.dumps({'token': text})}\n\n"
            print(f"[STREAM] Complete ({model}): {time.time()-t0:.2f}s", flush=True)
            yield "data: [DONE]\n\n"
            # Cache the full response if it's a static question
            if collected and _is_cacheable(question):
                _set_cached(question, req.system, "".join(collected), model)
                print(f"[STREAM] Cached response for: {question[:60]}", flush=True)
        except anthropic.AuthenticationError:
            yield f"data: {json.dumps({'error': 'Invalid Anthropic API key'})}\n\n"
        except anthropic.RateLimitError:
            yield f"data: {json.dumps({'error': 'Anthropic rate limit hit — try again shortly'})}\n\n"
        except Exception as exc:
            print(f"[STREAM] Error: {time.time()-t0:.2f}s — {exc}", flush=True)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
            "X-Model-Used":      model,
        },
    )


@app.get("/api/ping")
async def ping():
    """Keep-alive endpoint — frontend pings every 4 minutes to prevent Railway cold starts."""
    return {"ok": True}


@app.post("/api/force-refresh")
async def force_refresh(key: str = ""):
    """Owner-only: clear all OpenF1 backoffs and immediately re-fetch live data."""
    global _state
    if key != "atgaiimamw2026":
        raise HTTPException(status_code=403, detail="Forbidden")
    _backoff.clear()   # remove any rate-limit penalties
    log.info("[FORCE-REFRESH] Backoff cleared, fetching fresh state…")
    try:
        new_state = await _refresh()
        async with _lock:
            _state = new_state
        _broadcast(json.dumps(_state))
        return {"ok": True, "session": new_state.get("session_name"), "is_live": new_state.get("is_live"), "drivers": len(new_state.get("drivers", []))}
    except Exception as exc:
        log.warning("[FORCE-REFRESH] Failed: %s", exc)
        return {"ok": False, "error": str(exc)}



DATA_DIR      = os.environ.get("DATA_DIR", ".")
WAITLIST_FILE = os.path.join(DATA_DIR, "waitlist.csv")
_WAITLIST_LOG = Path(WAITLIST_FILE)
_WAITLIST_LOCK: asyncio.Lock | None = None   # initialised in _lifespan

@app.post("/api/waitlist")
async def waitlist_signup(request: Request):
    """Append a name + email to waitlist.csv."""
    body = await request.json()
    name  = str(body.get("name",  "")).strip()[:200]
    email = str(body.get("email", "")).strip()[:200]
    if not email:
        return {"error": "Email required"}
    ts  = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = [ts, name, email, _get_client_ip(request)]
    if _WAITLIST_LOCK is None:
        return {"ok": True}   # lock not ready (startup edge case)
    async with _WAITLIST_LOCK:
        try:
            if not _WAITLIST_LOG.exists():
                with open(_WAITLIST_LOG, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(["timestamp", "name", "email", "ip"])
            with open(_WAITLIST_LOG, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(row)
            log.info("[WAITLIST] %s <%s>", name, email)
        except Exception as exc:
            log.warning("[WAITLIST] Write failed: %s", exc)
    return {"ok": True}


@app.get("/api/waitlist-count")
async def waitlist_count(key: str = ""):
    """Owner-only: return signup count, today's count, and 5 most recent entries."""
    if key != "atgaiimamw2026":
        raise HTTPException(status_code=403, detail="Forbidden")
    if not _WAITLIST_LOG.exists():
        return {"total": 0, "today": 0, "recent": []}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows: list[dict] = []
    try:
        with open(_WAITLIST_LOG, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as exc:
        log.warning("[WAITLIST] Count read failed: %s", exc)
        return {"total": 0, "today": 0, "recent": []}
    total = len(rows)
    today_count = sum(1 for r in rows if r.get("timestamp", "").startswith(today))
    recent = [
        {"name": r.get("name", ""), "email": r.get("email", ""), "timestamp": r.get("timestamp", "")}
        for r in rows[-5:][::-1]
    ]
    return {"total": total, "today": today_count, "recent": recent}


@app.get("/api/waitlist-export")
async def export_waitlist(key: str = ""):
    """Owner-only: download waitlist.csv."""
    import io
    from fastapi.responses import StreamingResponse as _SR
    if key != "atgaiimamw2026":
        raise HTTPException(status_code=403, detail="Forbidden")
    if not _WAITLIST_LOG.exists():
        raise HTTPException(status_code=404, detail="No signups yet")
    content = _WAITLIST_LOG.read_text(encoding="utf-8")
    log.info("[WAITLIST] Export requested (%d bytes)", len(content))
    return _SR(
        iter([content.encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="waitlist.csv"'},
    )


@app.get("/api/export-questions")
async def export_questions(key: str = ""):
    """
    Owner-only: read questions_log.csv, deduplicate by normalised text,
    sort by frequency descending, return top 200 as a downloadable CSV.
    Protected by ?key=atgaiimamw2026.
    """
    from fastapi.responses import StreamingResponse as _SR
    import io

    if key != "atgaiimamw2026":
        raise HTTPException(status_code=403, detail="Forbidden")

    if not _QUESTIONS_LOG.exists():
        raise HTTPException(status_code=404, detail="No questions logged yet")

    # Read all rows
    freq: dict[str, dict] = {}   # normalised_q → {original, count, last_seen}
    try:
        with open(_QUESTIONS_LOG, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                q = row.get("question", "").strip()
                if not q:
                    continue
                norm = q.lower().strip()
                if norm not in freq:
                    freq[norm] = {"question": q, "count": 0, "last_seen": row.get("timestamp", "")}
                freq[norm]["count"] += 1
                freq[norm]["last_seen"] = row.get("timestamp", freq[norm]["last_seen"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read log: {exc}")

    # Sort by frequency, take top 200
    top = sorted(freq.values(), key=lambda x: x["count"], reverse=True)[:200]

    # Build CSV in memory
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["rank", "question", "times_asked", "last_seen"])
    for rank, item in enumerate(top, start=1):
        writer.writerow([rank, item["question"], item["count"], item["last_seen"]])
    buf.seek(0)

    log.info("[EXPORT] %d unique questions exported (top 200 of %d)", min(200, len(freq)), len(freq))

    return _SR(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="top_questions.csv"'},
    )


@app.post("/api/create-donation")
async def create_donation(request: Request):
    """$2 one-time donation for 10 extra questions during race weekend."""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": os.getenv("STRIPE_DONATION_PRICE_ID"), "quantity": 1}],
            mode="payment",
            success_url="https://www.askthegridai.com?donated=true&extra=10",
            cancel_url="https://www.askthegridai.com?cancelled=true",
        )
        return {"url": session.url}
    except Exception as e:
        print(f"[DONATION] Stripe error: {str(e)}", flush=True)
        return {"error": str(e)}


@app.post("/api/create-checkout")
async def create_checkout(request: Request):
    """Create a Stripe Checkout session and return the redirect URL."""
    print("[STRIPE] 1 — endpoint hit", flush=True)
    print(f"[STRIPE] 2 — key present: {bool(stripe.api_key)}", flush=True)

    price_id = os.getenv("STRIPE_PRICE_ID")
    print(f"[STRIPE] 3 — price_id: {price_id!r}", flush=True)

    if not stripe.api_key:
        print("[STRIPE] ERROR — STRIPE_SECRET_KEY not set", flush=True)
        return {"error": "Stripe secret key not configured"}

    if not price_id:
        print("[STRIPE] ERROR — STRIPE_PRICE_ID not set", flush=True)
        return {"error": "Stripe price ID not configured"}

    print("[STRIPE] 4 — calling stripe.checkout.Session.create", flush=True)
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url="https://www.askthegridai.com?subscribed=true",
            cancel_url="https://www.askthegridai.com?cancelled=true",
        )
        print(f"[STRIPE] 5 — session created: {session.id}", flush=True)
        return {"url": session.url}
    except Exception as e:
        print(f"[STRIPE] ERROR — {type(e).__name__}: {e}", flush=True)
        return {"error": str(e)}


@app.post("/api/webhook")
async def stripe_webhook(request: Request):
    """Stripe webhook — verifies signature and handles subscription events."""
    payload       = await request.body()
    sig_header    = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        log.warning("[STRIPE] Webhook signature error: %s", e)
        return {"error": str(e)}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email   = (session.get("customer_details") or {}).get("email")
        log.info("[STRIPE] New subscriber: %s", email)

    if event["type"] == "customer.subscription.deleted":
        log.info("[STRIPE] Subscription cancelled")

    return {"status": "ok"}


@app.get("/api/news")
async def get_news():
    """Return cached RSS news items with AI plain-English summaries."""
    async with _news_lock:
        return {
            "items":        _news_cache["items"],
            "refreshed_at": _news_cache["refreshed_at"],
        }


@app.get("/api/trending")
async def get_trending():
    """Return public trending data — Reddit excluded (use /api/reddit?key=... for that)."""
    async with _news_lock:
        news = list(_news_cache["items"])
    return {
        "trends": cached_trends,
        "news":   news,
    }


@app.get("/api/reddit")
async def get_reddit(key: str = ""):
    """Owner-only: return cached Reddit posts."""
    if key != "atgaiimamw2026":
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"reddit": cached_reddit}


# ── Fan topics cache ──────────────────────────────
_fan_topics_cache: dict = {"topics": [], "cached_at": None}
_FAN_TOPICS_TTL = 4 * 3600   # 4 hours

# ── Weather cache ─────────────────────────────────
_weather_cache: dict = {"data": None, "cached_at": None}  # reset on deploy
_WEATHER_TTL = 3600   # 1 hour

_CIRCUIT_COORDS: dict[str, dict] = {
    "Miami":        {"lat": 25.9581,  "lon": -80.2389},
    "Monaco":       {"lat": 43.7347,  "lon":   7.4206},
    "Silverstone":  {"lat": 52.0786,  "lon":  -1.0169},
    "Monza":        {"lat": 45.6156,  "lon":   9.2811},
    "Suzuka":       {"lat": 34.8431,  "lon": 136.5407},
    "Spa":          {"lat": 50.4372,  "lon":   5.9714},
    "Interlagos":   {"lat": -23.7036, "lon": -46.6997},
    "Singapore":    {"lat":  1.2914,  "lon": 103.8640},
    "Abu Dhabi":    {"lat": 24.4672,  "lon":  54.6031},
    "Barcelona":    {"lat": 41.5700,  "lon":   2.2611},
    "Baku":         {"lat": 40.3725,  "lon":  49.8533},
    "Melbourne":    {"lat": -37.8497, "lon": 144.9680},
    "Montreal":     {"lat": 45.5000,  "lon": -73.5228},
    "Zandvoort":    {"lat": 52.3888,  "lon":   4.5409},
    "Austin":       {"lat": 30.1328,  "lon": -97.6411},
    "Mexico City":  {"lat": 19.4042,  "lon": -99.0907},
    "Las Vegas":    {"lat": 36.1147,  "lon": -115.1728},
    "Jeddah":       {"lat": 21.6319,  "lon":  39.1044},
    "Bahrain":      {"lat": 26.0325,  "lon":  50.5106},
    "Shanghai":     {"lat": 31.3389,  "lon": 121.2197},
    "Imola":        {"lat": 44.3439,  "lon":  11.7167},
    "Spielberg":    {"lat": 47.2197,  "lon":  14.7647},
    "Budapest":     {"lat": 47.5789,  "lon":  19.2486},
    "Lusail":       {"lat": 25.4900,  "lon":  51.4542},
    "Yas Island":   {"lat": 24.4672,  "lon":  54.6031},
}

def _wmo_condition(code: int) -> str:
    if code == 0:          return "Clear"
    if code in [1, 2, 3]:  return "Partly Cloudy"
    if code in [45, 48]:   return "Foggy"
    if code in [51,53,55]: return "Drizzle"
    if code in [61,63,65]: return "Rain"
    if code in [71,73,75]: return "Snow"
    if code in [80,81,82]: return "Rain Showers"
    if code in [95,96,99]: return "Thunderstorm"
    return "Overcast"

@app.get("/api/weather")
async def get_race_weather():
    """7-day forecast for next race location via Open-Meteo (free, no key). 1-hour cache."""
    now = datetime.now(timezone.utc)
    if (
        _weather_cache["cached_at"]
        and (now - _weather_cache["cached_at"]).total_seconds() < _WEATHER_TTL
        and _weather_cache["data"]
    ):
        return _weather_cache["data"]

    # Determine next race from OpenF1
    location, race_name, race_date = "Miami", "Miami Grand Prix", "2026-05-01"
    fp1_date, qual_date, race_day_date = "2026-05-01", "2026-05-02", "2026-05-03"
    try:
        async with httpx.AsyncClient(timeout=8) as cl:
            r = await cl.get("https://api.openf1.org/v1/meetings?year=2026")
            meetings = r.json()
        upcoming = [
            m for m in meetings
            if m.get("date_start") and
               datetime.fromisoformat(m["date_start"].replace("Z", "+00:00")) > now
        ]
        upcoming.sort(key=lambda x: x["date_start"])
        if upcoming:
            nxt       = upcoming[0]
            location  = nxt.get("location", "Miami")
            race_name = nxt.get("meeting_name", "Miami Grand Prix")
            race_date = nxt.get("date_start", "2026-05-01")[:10]
            # Fetch individual sessions to get actual session dates
            try:
                mk = nxt.get("meeting_key")
                sr = await cl.get(
                    f"https://api.openf1.org/v1/sessions?meeting_key={mk}"
                )
                sessions = sr.json()
                for s in sessions:
                    sn = (s.get("session_name") or "").lower()
                    sd = (s.get("date_start") or "")[:10]
                    if not sd:
                        continue
                    if "practice 1" in sn or "fp1" in sn:
                        fp1_date = sd
                    elif "qualifying" in sn and "sprint" not in sn:
                        qual_date = sd
                    elif sn in ("race", "grand prix"):
                        race_day_date = sd
            except Exception:
                pass   # fall back to defaults below
        # Default offsets when sessions not available
        from datetime import date as _date, timedelta as _td
        _rd = _date.fromisoformat(race_date)
        if fp1_date  == "2026-05-01": fp1_date      = str(_rd)
        if qual_date == "2026-05-02": qual_date      = str(_rd + _td(days=1))
        if race_day_date == "2026-05-03": race_day_date = str(_rd + _td(days=2))
    except Exception as exc:
        log.warning("[WEATHER] Meeting lookup failed: %s", exc)

    coords = _CIRCUIT_COORDS.get(location, _CIRCUIT_COORDS["Miami"])
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={coords['lat']}&longitude={coords['lon']}"
        "&daily=temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,precipitation_sum,"
        "windspeed_10m_max,weathercode"
        "&timezone=auto&forecast_days=7"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as cl:
            wr = await cl.get(url)
        wd = wr.json()
        daily = wd.get("daily", {})
        forecast = [
            {
                "date":       daily["time"][i],
                "max_temp":   daily["temperature_2m_max"][i],
                "min_temp":   daily["temperature_2m_min"][i],
                "rain_chance": daily["precipitation_probability_max"][i],
                "rain_mm":    daily["precipitation_sum"][i],
                "wind_kmh":   daily["windspeed_10m_max"][i],
                "condition":  _wmo_condition(daily["weathercode"][i]),
            }
            for i in range(min(7, len(daily.get("time", []))))
        ]
    except Exception as exc:
        log.warning("[WEATHER] Forecast fetch failed: %s", exc)
        forecast = []

    result = {
        "location":      location,
        "race_name":     race_name,
        "race_date":     race_date,
        "fp1_date":      fp1_date,
        "qual_date":     qual_date,
        "race_day_date": race_day_date,
        "forecast":      forecast,
    }
    _weather_cache["data"]      = result
    _weather_cache["cached_at"] = now
    log.info("[WEATHER] Fetched %d days for %s", len(forecast), location)
    return result


_weather_analysis_cache: dict = {"data": None, "race": None, "cached_at": None}

_WET_DRIVER_KNOWLEDGE = """
Known 2026 F1 driver wet-weather profiles (use this to make accurate predictions):
EXCELLENT in wet: Lewis Hamilton (Ferrari) — widely regarded as the greatest wet-weather driver ever,
  multiple wet masterclasses at Nurburgring 2000, Brazil 2016, Germany 2019;
  Max Verstappen (Red Bull) — exceptional car control in tricky conditions, Brazil 2016 as a 19-year-old;
  Fernando Alonso (Aston Martin) — legendary wet pace, consistently extracts maximum from any car in rain.
  Lando Norris (McLaren) — increasingly brilliant in changeable conditions, excellent tyre judgement.
GOOD in wet: George Russell (Mercedes) — composed and precise, strong at managing intermediates;
  Charles Leclerc (Ferrari) — fast in wet when confident, occasionally over-drives;
  Kimi Antonelli (Mercedes) — still learning but raw talent shows in tricky conditions.
STRUGGLES in wet: Oscar Piastri (McLaren) — competent but not naturally outstanding in rain, tends to be conservative;
  Carlos Sainz (Williams) — inconsistent in rain, has had several wet-weather spins;
  Max's Red Bull often struggles with car balance in wet compared to Mercedes/Ferrari.
KEY FACTOR: Mercedes and McLaren 2026 cars have excellent aerodynamic stability in wet;
  Red Bull's 2026 car has been described as nervous — worse in changeable conditions.
"""

@app.post("/api/weather-analysis")
async def weather_analysis(request: Request):
    """AI analysis of race weekend weather impact. Cached per race to ensure consistent results."""
    body    = await request.json()
    weather = body.get("weather", {})
    race    = body.get("race_name", "the race")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "No API key"}

    # Return cached analysis for the same race (prevents different results each call)
    now = datetime.now(timezone.utc)
    cached = _weather_analysis_cache
    if (
        cached["race"] == race and cached["data"]
        and cached["cached_at"]
        and (now - cached["cached_at"]).total_seconds() < _WEATHER_TTL
    ):
        log.info("[WEATHER-ANALYSIS] Cache hit for %s", race)
        return cached["data"]

    # Extract race day rain chance for context
    race_day = next((d for d in (weather or []) if d), {})
    rain_pct = race_day.get("rain_chance", 0)

    prompt = (
        f"You are an expert F1 analyst predicting wet-weather performance at {race}.\n\n"
        f"Forecast rain chance on race day: {rain_pct}%.\n"
        f"Full forecast: {json.dumps(weather)}\n\n"
        f"{_WET_DRIVER_KNOWLEDGE}\n"
        "Based on the forecast AND the driver wet-weather knowledge above, return ONLY a JSON object:\n"
        "- summary: one sentence on overall weekend weather\n"
        "- rain_risk: 'high' (≥60%), 'medium' (30-59%), or 'low' (<30%)\n"
        "- race_day_condition: one specific sentence on race day conditions\n"
        "- wet_weather_winners: array of exactly 3 objects with 'driver' (full name) and "
        "'reason' (one short sentence on WHY they excel in wet — not just one word)\n"
        "- wet_weather_losers: array of exactly 3 objects with 'driver' (full name) and "
        "'reason' (one short sentence on WHY they struggle in wet)\n"
        "- strategy_impact: one sentence on how rain chance affects pit strategy\n"
        "- fan_tip: one casual engaging sentence on what fans should watch for\n"
        "Use the driver knowledge provided. Be specific and consistent. No extra text, just JSON."
    )
    try:
        cl   = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await cl.messages.create(
            model="claude-sonnet-4-20250514",   # Sonnet for better knowledge + consistency
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw    = resp.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        # Cache it so repeated calls return the same analysis
        _weather_analysis_cache["data"]      = result
        _weather_analysis_cache["race"]      = race
        _weather_analysis_cache["cached_at"] = now
        log.info("[WEATHER-ANALYSIS] Generated and cached for %s", race)
        return result
    except Exception as exc:
        log.warning("[WEATHER-ANALYSIS] Failed: %s", exc)
        return {"error": str(exc)}


@app.get("/api/fan-topics")
async def get_fan_topics():
    """AI-generated fan discussion topics, cached 4 hours."""
    now = datetime.now(timezone.utc)
    if (
        _fan_topics_cache["cached_at"]
        and (now - _fan_topics_cache["cached_at"]).total_seconds() < _FAN_TOPICS_TTL
        and _fan_topics_cache["topics"]
    ):
        return {"topics": _fan_topics_cache["topics"], "cached": True}

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"topics": _fan_topics_cache.get("topics", []), "cached": True}

    # Build brief race context for the prompt
    # Build race context for the prompt
    ctx_parts: list[str] = []
    standings = _standings_cache.get("data")
    if standings and standings.get("standings"):
        top3 = [
            f"P{d['position']} {d.get('driver','?')} ({d.get('team','?')})"
            for d in standings["standings"][:3]
        ]
        ctx_parts.append("Championship top 3: " + ", ".join(top3))
    state = _state
    if state.get("session_key"):
        ctx_parts.append(f"Next race: {state.get('circuit','?')} ({state.get('session_name','?')})")
    news = _news_cache.get("items", [])
    if news:
        ctx_parts.append("Latest: " + "; ".join(i["title"] for i in news[:2]))
    context = " | ".join(ctx_parts) or "2026 F1 season mid-point"

    prompt = (
        "You are an F1 fan community expert. "
        f"Based on this current F1 race weekend context: {context}\n\n"
        "Generate exactly 5 topics that real F1 fans would be actively discussing right now. "
        "Return ONLY a JSON array of 5 objects, each with keys: "
        "'topic' (short punchy title, max 8 words), "
        "'heat' (one of: 'hot', 'rising', 'trending'), and "
        "'why' (one sentence explaining why fans care right now, max 15 words). "
        "No extra text, just the JSON array."
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        topics = json.loads(raw)
        if isinstance(topics, list) and topics:
            _fan_topics_cache["topics"]    = topics[:5]
            _fan_topics_cache["cached_at"] = now
            log.info("[FAN-TOPICS] Generated %d topics", len(topics))
            return {"topics": topics[:5], "cached": False}
    except Exception as exc:
        log.warning("[FAN-TOPICS] Failed: %s", exc)

    return {"topics": _fan_topics_cache.get("topics", []), "cached": True}


@app.get("/api/news/insights")
async def get_news_insights(url: str):
    """
    Return AI insights for a given article URL.
    Cached per article so the same article is never re-summarised.
    """
    if not url:
        return {"error": "url param required"}, 400

    async with _insights_lock:
        if url in _insights_cache:
            return _insights_cache[url]

    # Find the article in the news cache
    async with _news_lock:
        items = list(_news_cache["items"])

    article = next((i for i in items if i.get("source") == url), None)
    if not article:
        return {"error": "article not found"}, 404

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "no API key"}, 503

    title   = article["title"]
    summary = article.get("summary", "")

    prompt = (
        f"F1 news article:\nHeadline: {title}\nSummary: {summary}\n\n"
        "You are an F1 analyst. Return a JSON object with exactly these keys:\n"
        "- news_summary: 2-3 sentences, plain English summary of the article\n"
        "- what_this_means: 2 sentences explaining what this means for the sport\n"
        "- why_its_important: 2 sentences on its significance\n"
        "- casual_fan_take: 1-2 simple sentences a casual fan would understand\n\n"
        "Return valid JSON only, no markdown, no code fences."
    )

    try:
        ai_client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await ai_client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = resp.content[0].text.strip()
        # Strip markdown fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        insights = json.loads(raw_text)
    except Exception as exc:
        log.warning("[INSIGHTS] Generation failed: %s", exc)
        insights = {
            "news_summary":     summary[:300],
            "what_this_means":  "Could not generate insights at this time.",
            "why_its_important": "Please try again later.",
            "casual_fan_take":  "Check back soon for analysis.",
        }

    async with _insights_lock:
        _insights_cache[url] = insights

    return insights


@app.get("/api/championship-standings")
async def get_championship_standings():
    global _standings_cache
    # Serve from cache if fresh (1 hour)
    if _standings_cache["data"] is not None and time.time() - _standings_cache["timestamp"] < 3600:
        return _standings_cache["data"]

    try:
        url = "https://api.jolpi.ca/ergast/f1/current/driverStandings/"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        standings_list = (
            data["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
        )
        standings = [
            {
                "position":   int(s["position"]),
                "driver":     s["Driver"]["familyName"],
                "first_name": s["Driver"]["givenName"],
                "team":       s["Constructors"][0]["name"],
                "points":     float(s["points"]),
                "wins":       int(s["wins"]),
                "nationality": s["Driver"]["nationality"],
            }
            for s in standings_list
        ]
        result = {"standings": standings, "source": "live", "season": "2026"}
        _standings_cache["data"] = result
        _standings_cache["timestamp"] = time.time()
        log.info("Championship standings fetched live (%d drivers)", len(standings))
        return result
    except Exception as exc:
        log.warning("Championship standings fetch failed (%s) — returning fallback", exc)
        result = {"standings": FALLBACK_STANDINGS, "source": "cached", "season": "2026"}
        _standings_cache["data"] = result
        _standings_cache["timestamp"] = time.time()
        return result


@app.get("/events")
async def sse(request: Request):
    """
    Server-Sent Events stream.  The frontend connects once and receives
    a push every time the poller fetches fresh data.
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=3)
    _subscribers.append(q)

    async def generate():
        try:
            # 1. Immediately send the current state so the UI updates at once
            async with _lock:
                snapshot = json.dumps(_state)
            yield f"data: {snapshot}\n\n"

            # 2. Then stream updates as they arrive
            while True:
                # If the client disconnected, the generator gets cancelled
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"   # prevents nginx / browser timeouts
        finally:
            try:
                _subscribers.remove(q)
            except ValueError:
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )
