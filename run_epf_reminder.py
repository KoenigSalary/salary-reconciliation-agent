"""
EPF upload reminder - fires automatically on the 14th, two days before the run.

The monthly reconciliation on the 16th downloads the salary sheet, TDS sheet and
bank statement from RMS by itself, but the EPF file has no RMS export and has to
be placed by hand. This reminder is what makes that deadline visible.

Usage
-----
  python3 run_epf_reminder.py           # always send
  python3 run_epf_reminder.py --auto    # skip if this month's reminder already went
                                        # out (used by launchd / scheduler.py)

Exit codes: 0 sent (or already sent) | 1 the email could not be sent
"""

import argparse
import logging

from config import Config
import recon_state as ledger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

log = logging.getLogger("run_epf_reminder")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="EPF upload reminder")
    p.add_argument("--auto", action="store_true",
                   help="Skip if this month's reminder was already sent")
    args = p.parse_args(argv)

    if args.auto and ledger.already_done(ledger.JOB_EPF_REMINDER):
        log.info(f"--auto: EPF reminder already sent for {ledger.month_key()} - skipping")
        return 0

    run_months = Config.get_run_months()
    log.info(
        f"EPF reminder for {run_months['salary_month_str']} "
        f"(the run on the 16th reconciles this period)"
    )

    from main import SalaryReconciliationAgent

    ok = SalaryReconciliationAgent().send_epf_reminder()

    if ok and args.auto:
        ledger.mark_done(ledger.JOB_EPF_REMINDER, note="reminder emailed")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
