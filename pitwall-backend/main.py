"""
PitWall AI — FastAPI backend
Fetches live race data from OpenF1 API, enriched with FastF1 session metadata.
Serves a /api/state REST endpoint and a /events SSE stream.
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
import fastf1
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Load .env (search from backend dir upward) ───────
load_dotenv(Path(__file__).parent / ".env")
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
POLL_INTERVAL_REGULAR = 15   # seconds — full data refresh
POLL_INTERVAL_CRITICAL = 5   # seconds — race_control / flag check only
BACKOFF_BASE = 10.0          # initial backoff on 429 (seconds)
BACKOFF_MAX  = 120.0         # cap backoff at 2 minutes

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

        try:
            r = await client.get(
                f"{OPENF1}{path}",
                params=params or {},
                timeout=15,
            )
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
            date_start = datetime.fromisoformat(sess["date_start"])
            date_end   = datetime.fromisoformat(sess["date_end"])
            s["is_live"] = date_start <= now <= date_end
        except Exception:
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
            log.info("Fetching race data (session_key=latest)…")
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

        await asyncio.sleep(POLL_INTERVAL_REGULAR)


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
    """Fetch race_control every POLL_INTERVAL_CRITICAL seconds and push flag/incident updates."""
    global _state
    while True:
        await asyncio.sleep(POLL_INTERVAL_CRITICAL)
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


# ── App lifespan ──────────────────────────────────────

@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _state
    _state = _blank_state()
    task_regular  = asyncio.create_task(_poller())
    task_critical = asyncio.create_task(_poll_critical())
    yield
    task_regular.cancel()
    task_critical.cancel()
    for task in (task_regular, task_critical):
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
_html_file = Path(__file__).parent / "pitwall-ai.html"

@app.get("/")
async def serve_frontend():
    from fastapi.responses import FileResponse
    return FileResponse(_html_file, media_type="text/html")


@app.get("/api/health")
async def health():
    key_set = bool(os.getenv("ANTHROPIC_API_KEY"))
    return {"ok": True, "last_updated": _state.get("last_updated"), "api_key_set": key_set}


@app.get("/api/state")
async def get_state():
    async with _lock:
        return _state


# ── Chat proxy ────────────────────────────────────────

class ChatRequest(BaseModel):
    system: str
    messages: list[dict]


@app.post("/api/chat")
async def chat(req: ChatRequest):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not found. Add it to pitwall-backend/.env"
        )

    client = anthropic.AsyncAnthropic(api_key=api_key)
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            system=req.system,
            messages=req.messages,
        )
        return {"reply": response.content[0].text}
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid Anthropic API key in .env")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Anthropic rate limit hit — try again shortly")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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
