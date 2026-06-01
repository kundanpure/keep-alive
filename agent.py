#!/usr/bin/env python3
"""
Travyn Phantom User Agent
=========================
An AI-powered simulation bot that behaves like real human users on the
Travyn platform. Powered by Google Gemini.

  - Keeps Render alive (hits the DB every 8-12 minutes)
  - Populates the discover feed with realistic trips and profiles
  - Simulates returning users, join requests, and approvals

Usage:
    python agent.py

Requirements:
    pip install -r requirements.txt
    (or: pip install google-generativeai requests python-dotenv)
"""

import io
import logging
import os
import random
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

# Force UTF-8 output on Windows so log lines never crash
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
TRAVYN_API_URL  = os.getenv("TRAVYN_API_URL", "https://travyn-backend.onrender.com/api/v1")

# Render sleeps after 15 min of inactivity → we run every 8–12 min
MIN_INTERVAL = 8  * 60   # seconds
MAX_INTERVAL = 12 * 60   # seconds

# Probability weights for each session strategy
WEIGHTS = {
    "new_traveler":    0.40,
    "returning_user":  0.35,
    "social_butterfly":0.15,
    "matcher":         0.10,
}

# ── Logging Setup ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agent.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# Lazy imports (after env is loaded)
from travyn_api import TravynAPI
from persona   import PersonaGenerator
import state

api         = TravynAPI(TRAVYN_API_URL)
persona_gen = PersonaGenerator(GEMINI_API_KEY)


# ═══════════════════════════════════════════════════════════════════════════
#  Utility helpers
# ═══════════════════════════════════════════════════════════════════════════

def _banner(title: str):
    line = "═" * 58
    log.info(f"\n{line}\n  {title}\n{line}")


def _think(lo: float = 1.5, hi: float = 4.5):
    """Simulate a human pause (reading, clicking, etc.)."""
    t = random.uniform(lo, hi)
    log.info(f"⏳ (thinking for {t:.1f}s…)")
    time.sleep(t)


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 1 — New Traveler
#  Register a brand-new AI persona, build their profile, post a trip.
# ═══════════════════════════════════════════════════════════════════════════

def strategy_new_traveler():
    _banner("🆕  NEW TRAVELER")

    # 1. Generate persona with Gemini
    log.info("🧠 Generating new traveler persona with Gemini AI…")
    persona = persona_gen.generate_new_traveler()
    reg  = persona["register"]
    prof = persona["profile"]
    trip = persona["trip"]
    meta = persona["_meta"]

    log.info(
        f"👤  {reg['firstName']} {reg['lastName']}  |  "
        f"{meta.get('occupation', '?')} from {meta.get('city', '?')}"
    )
    log.info(f"✈️   Trip: \"{trip['title']}\"  →  {trip['destination']}")

    # 2. Register (auto-verified because email ends in @travyn-agent.internal)
    auth = api.register(reg)
    if not auth:
        log.error("❌ Registration failed. Aborting session.")
        return

    # Backend uses @JsonProperty("access_token") — snake_case in JSON
    token = auth.get("access_token") or auth.get("accessToken")
    if not token:
        log.error(f"❌ No access_token in register response. Keys: {list(auth.keys())}")
        return

    log.info("🔑 JWT acquired — agent account auto-verified by backend")
    _think(1, 2)

    # 3. Initialize profile (GET triggers auto-create on backend)
    log.info("📋 Initialising profile…")
    api.get_my_profile(token)
    _think(2, 4)

    # 4. Fill out the full travel profile
    log.info("✍️  Writing travel profile…")
    api.update_profile(token, prof)
    _think(2, 5)

    # 5. Browse the discover feed (simulate scrolling/reading)
    log.info("🔍 Browsing discover feed…")
    feed = api.discover_trips()
    if feed:
        count = len(feed.get("content", []))
        log.info(f"👀 Scanned {count} trip(s) on the discover feed")
    _think(3, 7)

    # 6. Set up match preferences (like filling in a dating-app style card)
    log.info("💘 Setting up match preferences…")
    match_prefs = persona_gen.generate_match_preferences()
    api.save_match_preferences(token, match_prefs)
    _think(1, 3)

    # 7. Browse match candidates
    log.info("👀 Browsing match candidates…")
    matches = api.get_matches(token)
    if matches:
        log.info(f"   Found {len(matches)} candidate(s) to review")
        # Connect with first 1-2, pass on the rest (realistic behaviour)
        connect_count = min(len(matches), random.randint(1, 2))
        for i, candidate in enumerate(matches[:3]):
            target_id = str(candidate.get("userId") or candidate.get("id", ""))
            if not target_id:
                continue
            _think(2, 5)  # "User is reading the profile"
            if i < connect_count:
                log.info(f"   💚 Connecting with candidate {i+1}…")
                api.connect_with_user(token, target_id)
            else:
                log.info(f"   ❌ Passing on candidate {i+1}…")
                api.pass_user(token, target_id)
    _think(2, 5)

    # 8. Post their own trip
    log.info("📝 Posting new trip…")
    created_trip = api.create_trip(token, trip)

    # 7. Save user to state pool
    user_record = {
        "email":     reg["email"],
        "password":  reg["password"],
        "firstName": reg["firstName"],
        "lastName":  reg["lastName"],
        "tripIds":   [],
    }
    if created_trip:
        trip_id = str(created_trip.get("id", ""))
        if trip_id:
            user_record["tripIds"].append(trip_id)

    state.save_user(user_record)
    log.info(
        f"✅ New Traveler session complete! "
        f"Pool now has {len(state.load_users())} user(s)."
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 2 — Returning User
#  Log back in as an existing simulated user, browse, maybe join a trip.
# ═══════════════════════════════════════════════════════════════════════════

def strategy_returning_user():
    _banner("🔄  RETURNING USER")

    user = state.get_random_user()
    if not user:
        log.info("💡 Pool is empty — switching to New Traveler strategy")
        return strategy_new_traveler()

    log.info(f"👤 Returning as: {user['firstName']} {user['lastName']}  ({user['email']})")

    # 1. Login
    token = api.login(user["email"], user["password"])
    if not token:
        log.error("❌ Login failed. Aborting session.")
        return
    _think(1, 3)

    # 2. Check own trips
    log.info("📋 Checking my trips page…")
    my_trips = api.get_my_trips(token)
    if my_trips is not None:
        log.info(f"📊 User has {len(my_trips)} trip(s) in My Trips")
    _think(2, 4)

    # 3. Browse the discover feed with a random destination filter
    search_targets = [
        "Goa", "Manali", "Leh", "Rishikesh", "Jaipur",
        "Munnar", "Shimla", "Kasol", "Coorg", "Darjeeling",
    ]
    query = random.choice(search_targets)
    log.info(f"🔍 Searching trips for: \"{query}\"…")
    feed = api.discover_trips(destination=query)
    _think(3, 7)  # Simulate reading results

    if feed:
        trips = feed.get("content", [])
        open_trips = [t for t in trips if t.get("status") == "OPEN"]

        if open_trips:
            target = random.choice(open_trips)
            trip_id    = str(target.get("id", ""))
            trip_title = target.get("title", "?")
            log.info(f"🤝 Requesting to join: \"{trip_title}\"")
            _think(2, 5)  # "User is reading the trip details"
            api.join_trip(token, trip_id)
        else:
            log.info("ℹ️  No OPEN trips matched this search — that's fine!")

    log.info(f"✅ Returning User session complete for {user['firstName']}!")


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 3 — Social Butterfly
#  Log in as a trip creator, review & approve pending join requests.
# ═══════════════════════════════════════════════════════════════════════════

def strategy_social_butterfly():
    _banner("🦋  SOCIAL BUTTERFLY (Trip Manager)")

    trip_creators = state.get_users_with_trips()
    if not trip_creators:
        log.info("💡 No trip creators in pool yet — switching to New Traveler")
        return strategy_new_traveler()

    user = random.choice(trip_creators)
    log.info(f"👤 Trip creator: {user['firstName']} {user['lastName']}  ({user['email']})")

    # 1. Login
    token = api.login(user["email"], user["password"])
    if not token:
        log.error("❌ Login failed. Aborting session.")
        return
    _think(1, 3)

    # 2. Check each trip for pending join requests
    trip_ids      = user.get("tripIds", [])
    total_approved = 0

    log.info(f"🗂️  Checking {len(trip_ids)} trip(s) for pending requests…")
    for trip_id in trip_ids:
        pending = api.get_pending_requests(token, trip_id)
        if not pending:
            log.info(f"  Trip {trip_id}: no pending requests")
            continue

        log.info(f"  Trip {trip_id}: {len(pending)} pending request(s)")
        for req in pending:
            # Response structure: memberId or id depending on DTO
            member_id = str(req.get("memberId") or req.get("id") or "")
            if not member_id:
                continue
            requester = req.get("firstName", req.get("userId", member_id))
            log.info(f"    👤 Reviewing request from: {requester}")
            _think(1.5, 4)  # Simulate reading the requester's profile
            ok = api.approve_join_request(token, trip_id, member_id)
            if ok:
                total_approved += 1

        _think(1, 2)

    # 3. Verify final member list for first trip
    if trip_ids:
        log.info(f"👥 Final member count for trip {trip_ids[0]}…")
        members = api.get_trip_members(token, trip_ids[0])
        if members is not None:
            log.info(f"  ✅ Trip now has {len(members)} approved member(s)")

    log.info(
        f"✅ Social Butterfly session complete. "
        f"Approved {total_approved} join request(s)."
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 4 — Matcher
#  Log in as a returning user, set/update match preferences, browse
#  candidates and send connect / pass actions to simulate the match feed.
# ═══════════════════════════════════════════════════════════════════════════

def strategy_matcher():
    _banner("💘  MATCHER (Browsing & Connecting)")

    user = state.get_random_user()
    if not user:
        log.info("💡 Pool is empty — switching to New Traveler")
        return strategy_new_traveler()

    log.info(f"👤 Matching as: {user['firstName']} {user['lastName']}  ({user['email']})")

    # 1. Login
    token = api.login(user["email"], user["password"])
    if not token:
        log.error("❌ Login failed. Aborting session.")
        return
    _think(1, 2)

    # 2. Update match preferences (simulate user refining their settings)
    log.info("⚙️  Updating match preferences…")
    prefs = persona_gen.generate_match_preferences()
    api.save_match_preferences(token, prefs)
    _think(2, 4)

    # 3. Browse match candidates
    log.info("🔍 Opening match feed…")
    matches = api.get_matches(token)
    _think(3, 6)  # Simulate scrolling through profiles

    if matches:
        log.info(f"👥 {len(matches)} candidate(s) in match feed")
        connect_count = min(len(matches), random.randint(1, 3))

        for i, candidate in enumerate(matches[:5]):  # Review up to 5
            target_id   = str(candidate.get("userId") or candidate.get("id", ""))
            target_name = candidate.get("firstName", f"User {i+1}")
            score       = candidate.get("compatibilityScore", "?")
            if not target_id:
                continue

            log.info(f"   👤 Reviewing: {target_name} (score: {score})")
            _think(2, 6)  # "Reading their profile"

            if i < connect_count:
                log.info(f"   💚 Sending connect to {target_name}…")
                api.connect_with_user(token, target_id)
            else:
                log.info(f"   ❌ Passing on {target_name}…")
                api.pass_user(token, target_id)
    else:
        log.info("ℹ️  No candidates in match feed yet — more users needed!")

    # 4. Check mutual matches
    log.info("🤝 Checking mutual connections…")
    mutual = api.get_mutual_matches(token)
    if mutual:
        log.info(f"✨ {len(mutual)} mutual match(es)! These users both connected.")
    _think(1, 3)

    log.info(f"✅ Matcher session complete for {user['firstName']}!")


# ═══════════════════════════════════════════════════════════════════════════
#  Session runner
# ═══════════════════════════════════════════════════════════════════════════

def run_session():
    """Pick a random strategy and execute it. Errors are caught — never crashes."""
    strategies = [
        strategy_new_traveler,
        strategy_returning_user,
        strategy_social_butterfly,
        strategy_matcher,
    ]
    weights = [
        WEIGHTS["new_traveler"],
        WEIGHTS["returning_user"],
        WEIGHTS["social_butterfly"],
        WEIGHTS["matcher"],
    ]
    chosen = random.choices(strategies, weights=weights, k=1)[0]
    try:
        chosen()
    except Exception as exc:
        log.error(f"Unexpected error in session: {exc}", exc_info=True)
        log.info("Recovering... agent will continue to the next session.")


# ═══════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print(
        "\n"
        "  +======================================================+\n"
        "  |     TRAVYN  PHANTOM  USER  AGENT  (Gemini AI)        |\n"
        "  |  Simulating real human users - Keeping Render alive  |\n"
        "  +======================================================+\n"
    )

    if not GEMINI_API_KEY:
        log.error("❌ GEMINI_API_KEY is missing from your .env file. Exiting.")
        sys.exit(1)

    log.info(f"🎯 Target API  : {TRAVYN_API_URL}")
    log.info(f"👥 Pool size   : {len(state.load_users())} existing user(s)")
    log.info(f"⏰ Interval    : {MIN_INTERVAL // 60}–{MAX_INTERVAL // 60} minutes")
    log.info(f"Strategies  : New Traveler {int(WEIGHTS['new_traveler']*100)}% | "
             f"Returning {int(WEIGHTS['returning_user']*100)}% | "
             f"Social {int(WEIGHTS['social_butterfly']*100)}% | "
             f"Matcher {int(WEIGHTS['matcher']*100)}%")

    session_num = 0
    while True:
        session_num += 1
        log.info(f"\n{'─' * 58}")
        log.info(f"🚀 Session #{session_num}  started at {datetime.now().strftime('%H:%M:%S')}")

        run_session()

        wait = random.randint(MIN_INTERVAL, MAX_INTERVAL)
        wake = datetime.fromtimestamp(time.time() + wait).strftime("%H:%M:%S")
        log.info(
            f"😴 Session #{session_num} done. "
            f"Sleeping {wait // 60}m {wait % 60}s → next wake at {wake}"
        )
        time.sleep(wait)


if __name__ == "__main__":
    main()
