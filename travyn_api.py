"""
travyn_api.py — Clean HTTP wrapper for every Travyn API endpoint.
All calls are safe: they catch errors and return None/False instead of crashing.
"""
import logging
import requests
from typing import Optional

log = logging.getLogger(__name__)

TIMEOUT = 30  # seconds


class TravynAPI:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _auth_headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ── Auth ────────────────────────────────────────────────────────────────

    def register(self, payload: dict) -> Optional[dict]:
        """POST /auth/register — Returns auth response dict with accessToken."""
        try:
            r = self.session.post(
                f"{self.base_url}/auth/register", json=payload, timeout=TIMEOUT
            )
            if r.status_code in (200, 201):
                log.info(f"✅ Registered: {payload.get('email')}")
                return r.json()
            log.error(
                f"❌ Register failed [{r.status_code}]: {r.text[:300]}"
            )
            return None
        except requests.RequestException as e:
            log.error(f"❌ Register network error: {e}")
            return None

    def login(self, email: str, password: str) -> Optional[str]:
        """POST /auth/login — Returns JWT access token string or None."""
        try:
            r = self.session.post(
                f"{self.base_url}/auth/login",
                json={"email": email, "password": password},
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                # Backend uses @JsonProperty so field is "access_token" (snake_case)
                token = data.get("access_token") or data.get("accessToken")
                if token:
                    log.info(f"✅ Logged in: {email}")
                    return token
                log.error("❌ Login response has no access_token field")
                return None
            log.error(f"❌ Login failed [{r.status_code}]: {r.text[:300]}")
            return None
        except requests.RequestException as e:
            log.error(f"❌ Login network error: {e}")
            return None

    # ── Profile ─────────────────────────────────────────────────────────────

    def get_my_profile(self, token: str) -> Optional[dict]:
        """GET /users/me/profile — Initializes profile if not yet created."""
        try:
            r = self.session.get(
                f"{self.base_url}/users/me/profile",
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                log.info("✅ Profile fetched")
                return r.json()
            log.error(f"❌ Get profile failed [{r.status_code}]: {r.text[:200]}")
            return None
        except requests.RequestException as e:
            log.error(f"❌ Get profile network error: {e}")
            return None

    def update_profile(self, token: str, payload: dict) -> bool:
        """PUT /users/me/profile — Returns True on success."""
        try:
            r = self.session.put(
                f"{self.base_url}/users/me/profile",
                json=payload,
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                log.info("✅ Profile updated successfully")
                return True
            log.error(
                f"❌ Update profile failed [{r.status_code}]: {r.text[:300]}"
            )
            return False
        except requests.RequestException as e:
            log.error(f"❌ Update profile network error: {e}")
            return False

    # ── Trips ────────────────────────────────────────────────────────────────

    def discover_trips(
        self, destination: str = None, page: int = 0, size: int = 10
    ) -> Optional[dict]:
        """GET /trips — Public discover feed, optionally filtered."""
        try:
            params: dict = {"page": page, "size": size}
            if destination:
                params["destination"] = destination
            r = self.session.get(
                f"{self.base_url}/trips", params=params, timeout=TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                count = len(data.get("content", []))
                log.info(f"✅ Discover feed: {count} trip(s) returned")
                return data
            log.error(f"❌ Discover trips failed [{r.status_code}]: {r.text[:200]}")
            return None
        except requests.RequestException as e:
            log.error(f"❌ Discover trips network error: {e}")
            return None

    def create_trip(self, token: str, payload: dict) -> Optional[dict]:
        """POST /trips — Returns the created TripDTO or None."""
        try:
            r = self.session.post(
                f"{self.base_url}/trips",
                json=payload,
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code in (200, 201):
                trip = r.json()
                log.info(
                    f"✅ Trip created: '{trip.get('title', '?')}' → {trip.get('destination', '?')}"
                )
                return trip
            log.error(
                f"❌ Create trip failed [{r.status_code}]: {r.text[:400]}"
            )
            return None
        except requests.RequestException as e:
            log.error(f"❌ Create trip network error: {e}")
            return None

    def get_my_trips(self, token: str) -> Optional[list]:
        """GET /trips/my-trips — Returns list of user's trips."""
        try:
            r = self.session.get(
                f"{self.base_url}/trips/my-trips",
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                trips = r.json()
                log.info(f"✅ My trips: {len(trips)} found")
                return trips
            log.error(f"❌ Get my trips failed [{r.status_code}]")
            return None
        except requests.RequestException as e:
            log.error(f"❌ Get my trips network error: {e}")
            return None

    def join_trip(self, token: str, trip_id: str) -> bool:
        """POST /trips/{id}/join — Request to join a trip."""
        try:
            r = self.session.post(
                f"{self.base_url}/trips/{trip_id}/join",
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code in (200, 201):
                log.info(f"✅ Join request sent for trip: {trip_id}")
                return True
            # 409 = already a member, still not a crash
            if r.status_code == 409:
                log.info(f"ℹ️  Already a member of trip {trip_id}")
                return False
            log.error(f"❌ Join trip failed [{r.status_code}]: {r.text[:200]}")
            return False
        except requests.RequestException as e:
            log.error(f"❌ Join trip network error: {e}")
            return False

    def get_pending_requests(self, token: str, trip_id: str) -> Optional[list]:
        """GET /trips/{id}/requests — Returns pending join requests."""
        try:
            r = self.session.get(
                f"{self.base_url}/trips/{trip_id}/requests",
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                reqs = r.json()
                log.info(f"✅ Pending requests for trip {trip_id}: {len(reqs)}")
                return reqs
            # 403 = not the creator; treat gracefully
            if r.status_code == 403:
                log.info(f"ℹ️  Not the creator of trip {trip_id}, skipping.")
                return []
            log.error(f"❌ Get requests failed [{r.status_code}]")
            return None
        except requests.RequestException as e:
            log.error(f"❌ Get pending requests network error: {e}")
            return None

    def approve_join_request(self, token: str, trip_id: str, member_id: str) -> bool:
        """PUT /trips/{id}/requests/{memberId} with APPROVED status."""
        try:
            r = self.session.put(
                f"{self.base_url}/trips/{trip_id}/requests/{member_id}",
                json={"status": "APPROVED"},
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                log.info(f"✅ Approved member {member_id} for trip {trip_id}")
                return True
            log.error(
                f"❌ Approve failed [{r.status_code}]: {r.text[:200]}"
            )
            return False
        except requests.RequestException as e:
            log.error(f"❌ Approve request network error: {e}")
            return False

    def get_trip_members(self, token: str, trip_id: str) -> Optional[list]:
        """GET /trips/{id}/members — Returns approved members list."""
        try:
            r = self.session.get(
                f"{self.base_url}/trips/{trip_id}/members",
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                members = r.json()
                log.info(f"✅ Trip {trip_id} has {len(members)} member(s)")
                return members
            return None
        except requests.RequestException as e:
            log.error(f"❌ Get members network error: {e}")
            return None

    # ── Matching ─────────────────────────────────────────────────────────

    def save_match_preferences(self, token: str, payload: dict) -> bool:
        """POST /matches/preferences — Save match compatibility preferences."""
        try:
            r = self.session.post(
                f"{self.base_url}/matches/preferences",
                json=payload,
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                log.info("✅ Match preferences saved")
                return True
            log.error(f"❌ Save match prefs failed [{r.status_code}]: {r.text[:300]}")
            return False
        except requests.RequestException as e:
            log.error(f"❌ Save match prefs network error: {e}")
            return False

    def get_matches(self, token: str) -> Optional[list]:
        """GET /matches — Get list of compatible match candidates."""
        try:
            r = self.session.get(
                f"{self.base_url}/matches",
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                matches = r.json()
                log.info(f"✅ Matches found: {len(matches)}")
                return matches
            log.error(f"❌ Get matches failed [{r.status_code}]: {r.text[:200]}")
            return None
        except requests.RequestException as e:
            log.error(f"❌ Get matches network error: {e}")
            return None

    def get_mutual_matches(self, token: str) -> Optional[list]:
        """GET /matches/mutual — Get mutually connected matches."""
        try:
            r = self.session.get(
                f"{self.base_url}/matches/mutual",
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                mutual = r.json()
                log.info(f"✅ Mutual matches: {len(mutual)}")
                return mutual
            return None
        except requests.RequestException as e:
            log.error(f"❌ Get mutual matches network error: {e}")
            return None

    def connect_with_user(self, token: str, target_user_id: str) -> bool:
        """POST /matches/{targetId}/connect — Send a connect action."""
        try:
            r = self.session.post(
                f"{self.base_url}/matches/{target_user_id}/connect",
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                log.info(f"✅ Connected with user {target_user_id}")
                return True
            log.error(f"❌ Connect failed [{r.status_code}]: {r.text[:200]}")
            return False
        except requests.RequestException as e:
            log.error(f"❌ Connect network error: {e}")
            return False

    def pass_user(self, token: str, target_user_id: str) -> bool:
        """POST /matches/{targetId}/pass — Pass on a match candidate."""
        try:
            r = self.session.post(
                f"{self.base_url}/matches/{target_user_id}/pass",
                headers=self._auth_headers(token),
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                log.info(f"✅ Passed on user {target_user_id}")
                return True
            return False
        except requests.RequestException as e:
            log.error(f"❌ Pass network error: {e}")
            return False
