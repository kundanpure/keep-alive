"""
run_once.py — Single session runner for GitHub Actions.
Runs exactly ONE agent session and exits.
The GitHub Actions cron schedule handles the timing.
"""
import io
import logging
import os
import random
import sys

from dotenv import load_dotenv

load_dotenv()

# UTF-8 safe output
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TRAVYN_API_URL = os.getenv("TRAVYN_API_URL", "https://travyn-backend.onrender.com/api/v1")

WEIGHTS = {
    "new_traveler":    0.40,
    "returning_user":  0.35,
    "social_butterfly":0.15,
    "matcher":         0.10,
}

from travyn_api import TravynAPI
from persona   import PersonaGenerator
import state

# Re-use all strategies from agent.py
from agent import (
    strategy_new_traveler,
    strategy_returning_user,
    strategy_social_butterfly,
    strategy_matcher,
    api,
    persona_gen,
)

if __name__ == "__main__":
    log.info("=== GitHub Actions: Running ONE agent session ===")
    log.info(f"Pool size: {len(state.load_users())} user(s)")

    strategies = [
        strategy_new_traveler,
        strategy_returning_user,
        strategy_social_butterfly,
        strategy_matcher,
    ]
    weights = list(WEIGHTS.values())
    chosen = random.choices(strategies, weights=weights, k=1)[0]
    log.info(f"Strategy chosen: {chosen.__name__}")

    try:
        chosen()
        log.info("=== Session complete. Exiting. ===")
    except Exception as e:
        log.error(f"Session error: {e}", exc_info=True)
        sys.exit(1)
