"""
main_instaloader.py -- continuous scheduler for the Instaloader path,
mirroring main_ig.py's unattended multi-day design but adapted for a
fragile, unofficial scraping path (per mentor instruction, item 3):
run repeatedly against real targets, several times a day, with real
delays -- NOT on a fixed robotic interval like the Graph API path.

Runs 3 slots/day (morning profile fetch, afternoon hashtag fetch,
evening tagged-posts fetch), each with randomized timing inside a
window (not a fixed clock time), and rotates targets day-to-day, so
the request pattern doesn't look machine-generated. Every attempt is
logged via run_logger.log_attempt(), success or failure, exactly like
the Graph API path -- so the same run_logger.py summary covers both
paths together.

Login: uses the anu7.havv throwaway account (login_as) -- NOT
mea7.singh, which is reserved for the Graph API path, so a checkpoint
triggered here can never take down that run.

Usage:
    python main_instaloader.py
Press Ctrl+C to stop (same as main_ig.py's scheduler).
"""

import random
import subprocess
import sys
import time
from datetime import datetime, timedelta

from run_logger import log_attempt, classify_error

LOGIN_AS = "anu7.havv"
LIMIT = 10

PROFILE_ACCOUNTS = ["theviralfever", "rvcjinsta", "ghantaa"]
HASHTAGS = ["indianmemes", "socialissues", "desimemes"]
TAGGED_ACCOUNTS = ["theviralfever", "ghantaa"]

# (slot name, start_hour, end_hour) -- local-time windows for each
# daily slot. A run fires at a random minute inside the window, not
# at a fixed clock time.
SLOTS = [
    ("profile", 9, 11),
    ("hashtag", 14, 16),
    ("tagged", 19, 21),
]


def run_command(cmd, path_label, target):
    """Run one fetch command as a subprocess, log the outcome via
    run_logger (success or failure, matching the Graph API path's
    logging), and return True/False."""
    print(f"[{datetime.now()}] Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr
        print(output)

        if result.returncode == 0 and "\u2717" not in output:
            log_attempt("instaloader", target, success=True,
                        extra={"path_label": path_label})
            return True
        else:
            err_type = classify_error(RuntimeError(output))
            log_attempt("instaloader", target, success=False,
                        error_type=err_type, error_message=output[-500:])
            return False
    except subprocess.TimeoutExpired as e:
        log_attempt("instaloader", target, success=False,
                    error_type="connection_error",
                    error_message=f"Timed out after 300s: {e}")
        return False
    except Exception as e:
        log_attempt("instaloader", target, success=False,
                    error_type=classify_error(e), error_message=str(e))
        return False


def next_slot_time(hour_start, hour_end, now=None):
    """Return a randomized datetime within [hour_start, hour_end) --
    today if that window hasn't passed yet, otherwise tomorrow."""
    now = now or datetime.now()
    jitter_minutes = random.randint(0, (hour_end - hour_start) * 60 - 1)
    candidate = now.replace(hour=hour_start, minute=0, second=0, microsecond=0) \
        + timedelta(minutes=jitter_minutes)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def run_slot(slot_name, day_index):
    if slot_name == "profile":
        target = PROFILE_ACCOUNTS[day_index % len(PROFILE_ACCOUNTS)]
        cmd = [sys.executable, "fetch_instaloader.py", target, str(LIMIT), LOGIN_AS]
        run_command(cmd, "profile", target)

    elif slot_name == "hashtag":
        target = HASHTAGS[day_index % len(HASHTAGS)]
        cmd = [sys.executable, "fetch_instaloader_extra.py",
               "hashtag-experimental", target, LOGIN_AS, str(LIMIT)]
        run_command(cmd, "hashtag-experimental", target)

    elif slot_name == "tagged":
        target = TAGGED_ACCOUNTS[day_index % len(TAGGED_ACCOUNTS)]
        cmd = [sys.executable, "fetch_instaloader_extra.py",
               "tagged", target, LOGIN_AS, str(LIMIT)]
        run_command(cmd, "tagged", target)


def main():
    print(f"[{datetime.now()}] Instaloader scheduler starting -- "
          f"3 randomized slots/day, rotating real targets, logged via run_logger.")
    day_index = 0
    slot_index = 0

    while True:
        slot_name, hour_start, hour_end = SLOTS[slot_index]
        run_at = next_slot_time(hour_start, hour_end)
        wait_seconds = (run_at - datetime.now()).total_seconds()

        print(f"[{datetime.now()}] Next slot: '{slot_name}' at "
              f"{run_at.strftime('%Y-%m-%d %H:%M:%S')} "
              f"(sleeping {wait_seconds/3600:.2f}h). Press Ctrl+C to stop.")
        try:
            time.sleep(max(wait_seconds, 0))
        except KeyboardInterrupt:
            print("Instaloader scheduler stopped by user.")
            break

        run_slot(slot_name, day_index)

        slot_index += 1
        if slot_index >= len(SLOTS):
            slot_index = 0
            day_index += 1

        # small real delay before the loop recomputes the next slot,
        # so consecutive transitions aren't razor-precise either
        time.sleep(random.randint(30, 90))


if __name__ == "__main__":
    main()
