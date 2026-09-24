"""
Monthly run ledger - makes the automated jobs idempotent.

The automated entry points (the launchd agents and scheduler.py) run their jobs
with ``--auto``, which asks this module whether that job already completed for the
current month. Manual runs do NOT pass ``--auto``, so they are never blocked.

Why a ledger at all: the 16th run must fire exactly once per month. macOS launchd
and the optional long-running scheduler.py can both be installed at the same time,
and either of them can retry after a failure - without a shared "already done"
marker the tax team would receive the same report two or three times.

Ledger file: ``logs/run_ledger.json``

    {
      "reconciliation":   {"2026-09": {"done": true,  "at": "...", "note": "exit 0"}},
      "epf_reminder":     {"2026-09": {"done": true,  "at": "...", "note": "exit 0"}},
      "epf_missing_alert":{"2026-09": {"done": true,  "at": "...", "note": "alerted"}}
    }

Keys are ``YYYY-MM`` of the month the *run cycle* belongs to - i.e. the wall-clock
month of the 16th run, not the salary month being reconciled. A catch-up run on
the 18th therefore counts as the same cycle as the run that should have happened
on the 16th.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from config import Config

log = logging.getLogger(__name__)

LEDGER_PATH = Path(Config.LOGS_DIR) / "run_ledger.json"

# Job names used as top-level keys in the ledger.
JOB_RECONCILIATION = "reconciliation"
JOB_EPF_REMINDER = "epf_reminder"
JOB_EPF_MISSING_ALERT = "epf_missing_alert"


def month_key(dt: datetime | None = None) -> str:
    """The run-cycle key for a date: ``YYYY-MM``."""
    return (dt or datetime.now()).strftime("%Y-%m")


def _load() -> dict:
    try:
        if LEDGER_PATH.exists():
            data = json.loads(LEDGER_PATH.read_text())
            if isinstance(data, dict):
                return data
    except Exception as e:  # a corrupt ledger must never stop the run
        log.warning(f"Could not read run ledger {LEDGER_PATH}: {e}")
    return {}


def _save(data: dict) -> None:
    try:
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEDGER_PATH.write_text(json.dumps(data, indent=2, sort_keys=True))
    except Exception as e:
        log.warning(f"Could not write run ledger {LEDGER_PATH}: {e}")


def already_done(job: str, key: str | None = None) -> bool:
    """True if ``job`` already completed successfully for the given cycle."""
    key = key or month_key()
    return bool(_load().get(job, {}).get(key, {}).get("done"))


def mark_done(job: str, key: str | None = None, note: str = "") -> None:
    """Record that ``job`` finished successfully for this cycle."""
    key = key or month_key()
    data = _load()
    entry = data.setdefault(job, {}).setdefault(key, {})
    entry.update(
        done=True,
        at=datetime.now().isoformat(timespec="seconds"),
        note=note,
    )
    _save(data)
    log.info(f"Ledger: {job} marked done for {key}")


def record_attempt(job: str, key: str | None = None, note: str = "") -> None:
    """
    Record that a run was *started* but is not yet known to have succeeded.
    Used to throttle retries so a missing EPF file does not trigger a run every
    tick of the scheduler loop.
    """
    key = key or month_key()
    data = _load()
    entry = data.setdefault(job, {}).setdefault(key, {})
    entry["attempts"] = int(entry.get("attempts", 0)) + 1
    entry["last_attempt"] = datetime.now().isoformat(timespec="seconds")
    if note:
        entry["last_note"] = note
    _save(data)


def last_attempt(job: str, key: str | None = None) -> datetime | None:
    """When the last attempt for this cycle started, or None."""
    key = key or month_key()
    raw = _load().get(job, {}).get(key, {}).get("last_attempt")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def attempts(job: str, key: str | None = None) -> int:
    key = key or month_key()
    return int(_load().get(job, {}).get(key, {}).get("attempts", 0))


def clear(job: str, key: str | None = None) -> None:
    """Forget a cycle - lets an automated job run again for the same month."""
    key = key or month_key()
    data = _load()
    if job in data and key in data[job]:
        del data[job][key]
        _save(data)
        log.info(f"Ledger: cleared {job} for {key}")


def snapshot() -> dict:
    """The whole ledger, for `scheduler.py --status`."""
    return _load()
