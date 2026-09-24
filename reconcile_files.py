"""
Headless CLI entry point — runs the reconciliation with NO Selenium / RMS access.

Examples
--------
# Explicit files
python reconcile_files.py \
    --salary downloads/Salay_Sheet_November_2025.xls \
    --tds    "downloads/Update TDS.xlsx" \
    --bank   downloads/BankBookEntrySalaryUploaded_11-Jan-2026.xls \
    --epf    epf_uploads/epf_nov_2025.xlsx

# Auto-detect everything from the standard folders
python reconcile_files.py --auto

# Auto-detect + custom period label + JSON summary on stdout
python reconcile_files.py --auto --month "November 2025" --json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from config import Config
from recon_core import run_from_downloads, run_reconciliation


def setup_logging():
    Path(Config.LOGS_DIR).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Salary reconciliation (no Selenium)")
    parser.add_argument("--salary", help="Salary sheet (.xls/.xlsx)")
    parser.add_argument("--tds", help="TDS sheet (.xls/.xlsx)")
    parser.add_argument("--bank", help="Bank SOA / BankBookEntry (.xls/.xlsx)")
    parser.add_argument("--epf", help="EPF sheet (.xls/.xlsx)")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-detect the 4 files in the standard folders")
    parser.add_argument("--downloads-dir", default=Config.DOWNLOAD_DIR)
    parser.add_argument("--epf-dir", default=Config.EPF_UPLOAD_DIR)
    parser.add_argument("--out-dir", default=Config.REPORTS_DIR)
    parser.add_argument("--month", help='Period label, e.g. "November 2025"')
    parser.add_argument("--json", action="store_true", help="Print summary JSON only")
    args = parser.parse_args(argv)

    setup_logging()

    try:
        if args.auto or not all([args.salary, args.tds, args.bank, args.epf]):
            result = run_from_downloads(
                downloads_dir=args.downloads_dir,
                epf_dir=args.epf_dir,
                out_dir=args.out_dir,
                month_label=args.month,
            )
        else:
            result = run_reconciliation(
                args.salary, args.tds, args.bank, args.epf,
                out_dir=args.out_dir, month_label=args.month,
            )
    except Exception as e:
        logging.getLogger(__name__).error(f"Reconciliation failed: {e}")
        print(json.dumps({"status": "error", "error": str(e)}))
        return 1

    payload = {
        "status": "ok",
        "report": result["report_path"],
        "counts": result["counts"],
        "summary": {k: (float(v) if hasattr(v, "item") else v)
                    for k, v in result["summary"].items()},
    }

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print("=" * 70)
        print("RECONCILIATION COMPLETE")
        print("=" * 70)
        print(f"Report   : {result['report_path']}")
        print(f"Inputs   : {result['counts']}")
        print("-" * 70)
        for k, v in payload["summary"].items():
            print(f"  {k:<22}: {v}")
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
