"""
Monthly automation for the Salary Reconciliation Agent.

Schedule (local time)
---------------------
  14th, 09:00   EPF upload reminder  -> tax team
  16th, 18:00   Full monthly run     -> RMS download (salary + TDS + bank)
                                        + reconcile against the EPF file that was
                                          uploaded by hand by the 16th
                                        + email the report

The salary sheet, the TDS sheet and the bank SOA come out of the RMS portal
automatically. The EPF file has no RMS export - it has to be uploaded manually by
the 16th, which is why the reminder goes out two days earlier, on the 14th.

Idempotency
-----------
Both jobs are keyed by month in ``logs/run_ledger.json`` (see recon_state.py), so
the launchd agents and this scheduler can be installed side by side without ever
sending the same report twice.

Catch-up
--------
A job missed because the machine was asleep or off still runs at the next tick, as
long as it is the same calendar month. Failed runs - including one held back
because the EPF file was missing - are retried every RECON_RETRY_HOURS hours until
they succeed. Set RECON_CATCHUP=0 to disable catch-up entirely.

Usage
-----
  python3 scheduler.py                        # foreground loop, Ctrl+C to stop
  python3 scheduler.py --once                 # one check, then exit
  python3 scheduler.py --status               # ledger + what is due next
  python3 scheduler.py --run-now recon        # force the full run now
  python3 scheduler.py --run-now reminder     # force the EPF reminder now
  python3 scheduler.py --reset recon          # forget this month, so it can re-run
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from config import Config
import recon_state as ledger

log = logging.getLogger("scheduler")

# ---------------------------------------------------------------- schedule ----
REMINDER_DAY, REMINDER_HOUR, REMINDER_MINUTE = 14, 9, 0
RECON_DAY, RECON_HOUR, RECON_MINUTE = 16, 18, 0

# How often the loop wakes up to check the clock.
TICK_SECONDS = int(os.getenv("RECON_TICK_SECONDS", "300"))
# How long to wait before retrying a run that did not succeed.
RETRY_HOURS = float(os.getenv("RECON_RETRY_HOURS", "3"))
# Run a job whose scheduled minute has already passed (machine was asleep).
CATCHUP = os.getenv("RECON_CATCHUP", "1").strip().lower() not in ("0", "false", "no", "off")
# Hard ceiling on one job, so a hung browser cannot wedge the scheduler forever.
JOB_TIMEOUT = int(os.getenv("RECON_JOB_TIMEOUT", "3600"))

JOBS = {
    "reminder": {
        "title": "EPF upload reminder",
        "script": "run_epf_reminder.py",
        "day": REMINDER_DAY,
        "hour": REMINDER_HOUR,
        "minute": REMINDER_MINUTE,
        "ledger_key": ledger.JOB_EPF_REMINDER,
        "auto_args": ["--auto"],
    },
    "recon": {
        "title": "Monthly reconciliation",
        "script": "run_live.py",
        "day": RECON_DAY,
        "hour": RECON_HOUR,
        "minute": RECON_MINUTE,
        "ledger_key": ledger.JOB_RECONCILIATION,
        "auto_args": ["--auto"],
    },
}

# run_live.py exit code meaning "held back: no EPF file"
EXIT_EPF_MISSING = 3


def setup_logging():
    Path(Config.LOGS_DIR).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(Path(Config.LOGS_DIR) / "scheduler.log"),
            logging.StreamHandler(),
        ],
    )


def scheduled_at(spec: dict, now: datetime) -> datetime:
    """This month's scheduled moment for a job."""
    return now.replace(
        day=spec["day"], hour=spec["hour"], minute=spec["minute"],
        second=0, microsecond=0,
    )


def next_due(spec: dict, now: datetime) -> datetime:
    """The next moment this job will actually be allowed to run."""
    this_month = scheduled_at(spec, now)
    key = ledger.month_key(now)
    if now < this_month or not ledger.already_done(spec["ledger_key"], key):
        return this_month if now < this_month else now
    # already done this month -> next month's slot
    nxt = (this_month.replace(day=1) + timedelta(days=32)).replace(day=spec["day"])
    return nxt.replace(hour=spec["hour"], minute=spec["minute"])


def due_reason(spec: dict, now: datetime) -> str | None:
    """
    None if the job should run now, otherwise the reason it is being skipped.
    """
    sched = scheduled_at(spec, now)
    key = ledger.month_key(now)

    if now < sched:
        return f"not due until {sched:%d %b %H:%M}"

    if ledger.already_done(spec["ledger_key"], key):
        return f"already completed for {key}"

    if not CATCHUP:
        return "scheduled minute passed and catch-up is disabled (RECON_CATCHUP=0)"

    last = ledger.last_attempt(spec["ledger_key"], key)
    if last is not None:
        waited = now - last
        if waited < timedelta(hours=RETRY_HOURS):
            retry_at = last + timedelta(hours=RETRY_HOURS)
            return f"retry throttled - next attempt after {retry_at:%d %b %H:%M}"

    return None


def run_job(name: str, spec: dict, auto: bool = True) -> int:
    """Launch a job as a subprocess. Never raises - a failure must not kill the loop."""
    key = ledger.month_key()
    cmd = [sys.executable, str(Path(Config.BASE_DIR) / spec["script"])]

    if auto:
        cmd += spec["auto_args"]

    # Tell run_live.py to send the "EPF missing" alert, but only once per month.
    alerting = False
    if name == "recon" and not ledger.already_done(ledger.JOB_EPF_MISSING_ALERT, key):
        cmd.append("--alert-on-missing-epf")
        alerting = True

    log.info("=" * 78)
    log.info(f"[{name}] {spec['title']} - launching")
    log.info(f"[{name}] {' '.join(cmd)}")
    log.info("=" * 78)
    ledger.record_attempt(spec["ledger_key"], key, note=f"launch {spec['script']}")

    try:
        proc = subprocess.run(cmd, cwd=str(Config.BASE_DIR), timeout=JOB_TIMEOUT)
    except subprocess.TimeoutExpired:
        log.error(f"[{name}] timed out after {JOB_TIMEOUT}s - will retry")
        return -1
    except Exception as e:
        log.error(f"[{name}] could not start: {e}")
        return -1

    rc = proc.returncode

    if rc == 0:
        ledger.mark_done(spec["ledger_key"], key, note="exit 0")
        log.info(f"[{name}] completed successfully")

    elif rc == EXIT_EPF_MISSING:
        if alerting:
            ledger.mark_done(ledger.JOB_EPF_MISSING_ALERT, key, note="alerted")
        log.warning(
            f"[{name}] held back: no EPF file in {Config.EPF_UPLOAD_DIR}. "
            f"Upload it and the run will retry automatically "
            f"(every {RETRY_HOURS:g}h while the loop is running)."
        )

    else:
        log.error(f"[{name}] exit code {rc} - will retry")

    return rc


def check_all(auto: bool = True) -> list[str]:
    """One pass over every job. Returns the names of the jobs that ran."""
    now = datetime.now()
    ran = []
    for name, spec in JOBS.items():
        reason = due_reason(spec, now)
        if reason is None:
            log.info(f"[{name}] due now - running")
            run_job(name, spec, auto=auto)
            ran.append(name)
        else:
            log.debug(f"[{name}] skipped: {reason}")
    return ran


def print_status() -> None:
    now = datetime.now()
    key = ledger.month_key(now)
    snap = ledger.snapshot()

    print()
    print("=" * 74)
    print("SALARY RECONCILIATION - AUTOMATION STATUS")
    print("=" * 74)
    print(f"  Now                : {now:%d %B %Y, %H:%M}")
    print(f"  Project directory  : {Config.BASE_DIR}")
    print(f"  EPF upload folder  : {Config.EPF_UPLOAD_DIR}")
    print(f"  Catch-up           : {'enabled' if CATCHUP else 'DISABLED'}")
    print(f"  Retry interval     : every {RETRY_HOURS:g}h until a run succeeds")
    print("-" * 74)

    for name, spec in JOBS.items():
        sched = scheduled_at(spec, now)
        done = ledger.already_done(spec["ledger_key"], key)
        n_attempts = ledger.attempts(spec["ledger_key"], key)
        last = ledger.last_attempt(spec["ledger_key"], key)
        reason = due_reason(spec, now)

        print(f"  [{name}] {spec['title']}")
        print(f"      schedule       : day {spec['day']} at {spec['hour']:02d}:{spec['minute']:02d}")
        print(f"      this month     : {sched:%d %B %H:%M}  ->  {'DONE' if done else 'pending'}")
        if n_attempts:
            print(f"      attempts ({key}): {n_attempts}"
                  + (f", last {last:%d %b %H:%M}" if last else ""))
        print(f"      next run       : {next_due(spec, now):%d %B %Y %H:%M}"
              if not done else f"      next run       : next month")
        print(f"      state now      : {reason or 'DUE NOW'}")
        print()

    if snap:
        print("-" * 74)
        print("  Ledger (logs/run_ledger.json):")
        for job, months in sorted(snap.items()):
            for month, entry in sorted(months.items()):
                mark = "done" if entry.get("done") else "incomplete"
                print(f"      {job:<20} {month}  {mark}"
                      + (f"  ({entry.get('note')})" if entry.get("note") else ""))
    print("=" * 74)
    print()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Salary reconciliation monthly scheduler")
    p.add_argument("--once", action="store_true",
                   help="Check the clock once and exit (for cron / launchd)")
    p.add_argument("--status", action="store_true",
                   help="Print the schedule and ledger, then exit")
    p.add_argument("--run-now", choices=["recon", "reminder", "all"],
                   help="Force a job immediately, ignoring the schedule and ledger")
    p.add_argument("--reset", choices=["recon", "reminder", "all"],
                   help="Forget this month's completion so the job can run again")
    args = p.parse_args(argv)

    setup_logging()

    if args.status:
        print_status()
        return 0

    if args.reset:
        targets = JOBS if args.reset == "all" else {args.reset: JOBS[args.reset]}
        for name, spec in targets.items():
            ledger.clear(spec["ledger_key"])
            if name == "recon":
                ledger.clear(ledger.JOB_EPF_MISSING_ALERT)
        print(f"Cleared ledger entries for: {', '.join(targets)} ({ledger.month_key()})")
        return 0

    if args.run_now:
        targets = JOBS if args.run_now == "all" else {args.run_now: JOBS[args.run_now]}
        for name, spec in targets.items():
            # a forced run is a manual run: no --auto, so nothing is skipped
            run_job(name, spec, auto=False)
        return 0

    log.info("=" * 78)
    log.info("SALARY RECONCILIATION AGENT - SCHEDULER STARTED")
    log.info(f"Project directory : {Config.BASE_DIR}")
    log.info(f"EPF reminder      : day {REMINDER_DAY} at {REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d}")
    log.info(f"Monthly run       : day {RECON_DAY} at {RECON_HOUR:02d}:{RECON_MINUTE:02d}")
    log.info(f"Catch-up          : {'enabled' if CATCHUP else 'disabled'}"
             f" | retry every {RETRY_HOURS:g}h")
    log.info("Press Ctrl+C to stop")
    log.info("=" * 78)

    while True:
        try:
            check_all()
        except Exception as e:  # a bad tick must never kill the loop
            log.error(f"Scheduler tick failed: {e}", exc_info=True)

        if args.once:
            return 0

        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.info("Scheduler stopped by user")
