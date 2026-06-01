"""
persona.py — Gemini-powered persona generator for the Travyn Phantom Agent.

Calls Gemini Flash to produce fully realistic Indian traveler profiles
with consistent backstories, matching travel styles, and believable trips.
Falls back to deterministic data if the API is unavailable.
"""
import json
import logging
import random
import re
import uuid
from datetime import date, timedelta

from google import genai
from google.genai import types as genai_types

log = logging.getLogger(__name__)

# ── Enum values that match the Travyn backend exactly ──────────────────────
DESTINATIONS = [
    "Manali, Himachal Pradesh", "Goa", "Leh, Ladakh", "Rishikesh, Uttarakhand",
    "Jaipur, Rajasthan", "Munnar, Kerala", "Coorg, Karnataka", "Darjeeling, West Bengal",
    "Andaman Islands", "Varanasi, Uttar Pradesh", "Shimla, Himachal Pradesh",
    "Ooty, Tamil Nadu", "Spiti Valley, Himachal Pradesh", "Kasol, Himachal Pradesh",
    "Hampi, Karnataka", "Udaipur, Rajasthan", "McLeod Ganj, Himachal Pradesh",
    "Kodaikanal, Tamil Nadu", "Pushkar, Rajasthan", "Ziro, Arunachal Pradesh",
    "Varkala, Kerala", "Rann of Kutch, Gujarat", "Meghalaya", "Sikkim",
]

TRIP_TYPES = [
    "BACKPACKING", "LUXURY", "ROAD_TRIP", "CULTURAL",
    "ADVENTURE", "WEEKEND", "REMOTE_WORK",
]
TRAVEL_STYLES = ["ADVENTURE", "CULTURAL", "RELAXATION", "PARTY", "BUDGET"]
FOOD_PREFS   = ["VEG", "NON_VEG", "VEGAN", "HALAL", "NO_PREFERENCE"]
SLEEP_SCHEDS = ["EARLY_BIRD", "NIGHT_OWL", "FLEXIBLE"]
GENDERS      = ["MALE", "FEMALE", "PREFER_NOT_TO_SAY"]

# Realistic fallback name pool
NAMES = [
    ("Arjun",  "Sharma"),   ("Priya",   "Patel"),  ("Rahul",  "Mehta"),
    ("Sneha",  "Iyer"),     ("Vikram",  "Singh"),   ("Ananya", "Das"),
    ("Rohan",  "Gupta"),    ("Kavya",   "Nair"),    ("Aditya", "Kumar"),
    ("Pooja",  "Verma"),    ("Siddharth","Joshi"),  ("Divya",  "Reddy"),
    ("Karan",  "Malhotra"), ("Shreya",  "Pillai"),  ("Nikhil", "Bose"),
    ("Tanvi",  "Chatterjee"),("Ishaan", "Kapoor"),  ("Meera",  "Rao"),
]


def _make_username(first: str, last: str) -> str:
    """Build a valid username: ^[a-z0-9_.]+$ with a random suffix."""
    raw = f"{first}{last}".lower()
    clean = re.sub(r"[^a-z0-9_.]", "", raw)
    suffix = random.randint(100, 9999)
    return f"{clean[:18]}_{suffix}"


def _future_dates(min_days_out: int = 45, max_days_out: int = 180,
                  min_duration: int = 3, max_duration: int = 14) -> tuple[str, str]:
    """Return (startDate, endDate) as ISO strings, both in the future."""
    offset   = random.randint(min_days_out, max_days_out)
    duration = random.randint(min_duration, max_duration)
    start = date.today() + timedelta(days=offset)
    end   = start + timedelta(days=duration)
    return start.isoformat(), end.isoformat()


class PersonaGenerator:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-1.5-flash"

    # ── Public API ──────────────────────────────────────────────────────────

    def generate_new_traveler(self) -> dict:
        """
        Ask Gemini to generate a fully realistic Indian traveler persona.
        Returns a dict with keys: register, profile, trip, _meta.
        Falls back to deterministic data if Gemini fails.
        """
        destination = random.choice(DESTINATIONS)
        trip_type   = random.choice(TRIP_TYPES)
        gender      = random.choice(GENDERS)
        start_date, end_date = _future_dates()

        prompt = f"""
You are a realistic data generator for an Indian solo travel app called Travyn.

Create a highly specific, believable Indian traveler. Avoid generic descriptions.
Give them a real job, a specific hometown, genuine interests, and a personal travel story.

Return ONLY valid JSON with these exact keys:

{{
  "firstName": "realistic Indian first name",
  "lastName": "realistic Indian surname",
  "occupation": "specific job title (e.g. UX Designer at a Bangalore startup)",
  "city": "Indian city they live in",
  "bio": "2-3 sentences, personal and specific, max 380 characters. Written in first person.",
  "travelStyles": ["1 or 2 values from: ADVENTURE, CULTURAL, RELAXATION, PARTY, BUDGET"],
  "budgetMin": 40,
  "budgetMax": 200,
  "foodPreference": "one of: VEG, NON_VEG, VEGAN, HALAL, NO_PREFERENCE",
  "sleepSchedule": "one of: EARLY_BIRD, NIGHT_OWL, FLEXIBLE",
  "personalityScale": 7,
  "languages": "Hindi, English (add 1-2 regional languages if realistic for their city)",
  "remoteWorker": false,
  "tripTitle": "A catchy, specific trip title (max 80 chars) for this trip",
  "tripDescription": "2-3 sentences describing the trip and what kind of travel companion they want (max 500 chars)",
  "tripMaxSize": 4,
  "tripApprovalMode": "MANUAL"
}}

Context for this persona:
- Gender: {gender}
- Trip destination: {destination}  
- Trip type: {trip_type.replace("_", " ").title()}
- Trip dates: {start_date} to {end_date}

Important rules:
- budgetMin must be less than budgetMax
- personalityScale must be an integer 1–10
- tripMaxSize must be an integer 2–12
- bio must be under 380 characters
- tripDescription must be under 500 characters
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            raw = response.text.strip()
            # Strip markdown code fences if Gemini wraps JSON
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            log.info(
                f"🧠 Gemini persona: {data.get('firstName')} {data.get('lastName')} "
                f"| {data.get('occupation')} from {data.get('city')}"
            )
            return self._build_persona(data, destination, trip_type, gender, start_date, end_date)

        except Exception as e:
            log.warning(f"⚠️  Gemini persona generation failed ({e}), using fallback.")
            return self._fallback_persona(destination, trip_type, gender, start_date, end_date)

    def generate_match_preferences(self) -> dict:
        """
        Generate a random but internally consistent set of match preferences.
        Uses all exact enum values from the Travyn backend.
        Returns a dict ready to POST to /matches/preferences.
        """
        smoking  = random.choice(["NEVER", "SOCIALLY", "REGULARLY"])
        drinking = random.choice(["NEVER", "SOCIALLY", "REGULARLY"])
        pace     = random.choice(["PACKED", "BALANCED", "GO_WITH_FLOW"])
        accom    = random.choice(["HOSTEL_DORM", "PRIVATE_ROOM", "HOTEL", "ANYTHING_WORKS"])
        planning = random.choice(["DETAILED", "ROUGH", "ZERO"])
        clean    = random.choice(["VERY_TIDY", "MODERATE", "RELAXED"])
        social   = random.choice(["MEET_EVERYONE", "BALANCED", "MOSTLY_SOLO"])
        experience = random.choice(["FIRST_TIMER", "FEW", "EXPERIENCED", "SEASONED"])

        all_motivations = ["ESCAPE", "GROWTH", "ADVENTURE", "CULTURE", "PEOPLE", "MEMORIES", "PEACE", "FOOD"]
        all_meanings    = ["FREEDOM", "LEARNING", "CONNECTION", "PEACE", "CHALLENGE", "INSPIRATION"]
        motivations = random.sample(all_motivations, k=random.randint(2, 4))
        meanings    = random.sample(all_meanings,    k=random.randint(2, 3))

        return {
            "smokingHabit":      smoking,
            "drinkingHabit":     drinking,
            "tripPace":          pace,
            "accommodationStyle":accom,
            "planningStyle":     planning,
            "cleanliness":       clean,
            "socialEnergy":      social,
            "travelMotivations": motivations,
            "travelMeanings":    meanings,
            "tripExperience":    experience,
        }

    # ── Internal helpers ────────────────────────────────────────────────────

    def _build_persona(self, data: dict, destination: str, trip_type: str,
                       gender: str, start_date: str, end_date: str) -> dict:
        uid  = str(uuid.uuid4())[:8]
        first = str(data.get("firstName", "Rahul")).strip()
        last  = str(data.get("lastName",  "Kumar")).strip()
        email = f"{first.lower()}.{last.lower()}.{uid}@travyn-agent.internal"

        # Guard: travelStyles must be a list
        styles = data.get("travelStyles", ["ADVENTURE"])
        if isinstance(styles, str):
            styles = [styles]
        valid_styles = [s for s in styles if s in TRAVEL_STYLES]
        if not valid_styles:
            valid_styles = [random.choice(TRAVEL_STYLES)]

        budget_min = max(10,  int(data.get("budgetMin", 40)))
        budget_max = max(budget_min + 10, int(data.get("budgetMax", 120)))

        personality = max(1, min(10, int(data.get("personalityScale", 6))))
        max_size    = max(2, min(12, int(data.get("tripMaxSize", 4))))
        approval    = data.get("tripApprovalMode", "MANUAL")
        if approval not in ("MANUAL", "AUTO"):
            approval = "MANUAL"

        food_pref = data.get("foodPreference", "NO_PREFERENCE")
        if food_pref not in FOOD_PREFS:
            food_pref = "NO_PREFERENCE"

        sleep = data.get("sleepSchedule", "FLEXIBLE")
        if sleep not in SLEEP_SCHEDS:
            sleep = "FLEXIBLE"

        return {
            "register": {
                "firstName": first,
                "lastName":  last,
                "username":  _make_username(first, last),
                "email":     email,
                "password":  f"TravynAgent#{uid}!2026",
                "gender":    gender,
            },
            "profile": {
                "bio":             str(data.get("bio", ""))[:480],
                "travelStyles":    valid_styles,
                "budgetMin":       budget_min,
                "budgetMax":       budget_max,
                "foodPreference":  food_pref,
                "sleepSchedule":   sleep,
                "personalityScale":personality,
                "languages":       str(data.get("languages", "Hindi, English"))[:490],
                "remoteWorker":    bool(data.get("remoteWorker", False)),
                "locationName":    str(data.get("city", "India"))[:250],
            },
            "trip": {
                "title":       str(data.get("tripTitle", f"Trip to {destination}"))[:190],
                "destination": destination,
                "description": str(data.get("tripDescription", ""))[:1990],
                "tripType":    trip_type,
                "startDate":   start_date,
                "endDate":     end_date,
                "maxSize":     max_size,
                "approvalMode":approval,
                "womenOnly":   False,
                "trustScoreMin": 0,
            },
            "_meta": {
                "occupation":  data.get("occupation", ""),
                "city":        data.get("city", ""),
                "destination": destination,
            },
        }

    def _fallback_persona(self, destination: str, trip_type: str,
                          gender: str, start_date: str, end_date: str) -> dict:
        """Deterministic fallback: no Gemini needed."""
        uid   = str(uuid.uuid4())[:8]
        first, last = random.choice(NAMES)
        email = f"{first.lower()}.{last.lower()}.{uid}@travyn-agent.internal"

        cities = ["Mumbai", "Bangalore", "Delhi", "Hyderabad", "Pune", "Chennai",
                  "Kolkata", "Ahmedabad", "Jaipur", "Kochi"]
        jobs   = ["Software Engineer", "Graphic Designer", "Teacher", "Doctor",
                  "Content Creator", "Startup Founder", "Journalist", "Architect",
                  "Freelance Photographer", "Management Consultant"]
        city = random.choice(cities)
        job  = random.choice(jobs)

        bio = (
            f"{job} from {city}, taking time off to explore India. "
            f"Planning a {trip_type.lower().replace('_', ' ')} adventure to {destination} "
            f"and looking for like-minded companions who love real experiences over tourist traps."
        )[:480]

        return {
            "register": {
                "firstName": first,
                "lastName":  last,
                "username":  _make_username(first + uid, last),
                "email":     email,
                "password":  f"TravynAgent#{uid}!2026",
                "gender":    gender,
            },
            "profile": {
                "bio":              bio,
                "travelStyles":     random.sample(TRAVEL_STYLES, k=random.randint(1, 2)),
                "budgetMin":        random.randint(30, 80),
                "budgetMax":        random.randint(100, 250),
                "foodPreference":   random.choice(FOOD_PREFS),
                "sleepSchedule":    random.choice(SLEEP_SCHEDS),
                "personalityScale": random.randint(4, 9),
                "languages":        "Hindi, English",
                "remoteWorker":     random.choice([True, False]),
                "locationName":     city,
            },
            "trip": {
                "title":       f"{trip_type.replace('_',' ').title()} Adventure — {destination}"[:190],
                "destination": destination,
                "description": (
                    f"Looking for travel companions for an amazing trip to {destination}. "
                    f"We'll be doing a {trip_type.lower().replace('_',' ')} style trip. "
                    f"Reach out if you're spontaneous, respectful, and love genuine travel!"
                )[:1990],
                "tripType":    trip_type,
                "startDate":   start_date,
                "endDate":     end_date,
                "maxSize":     random.randint(2, 6),
                "approvalMode":"MANUAL",
                "womenOnly":   False,
                "trustScoreMin": 0,
            },
            "_meta": {"occupation": job, "city": city, "destination": destination},
        }
