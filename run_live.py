"""
Live end-to-end runner: RMS download -> reconcile -> email.

This is the ONLY entry point that exercises rms_automation.py (Selenium + Chrome),
so it must run on a host that can reach the RMS portal.

Usage
-----
  python3 run_live.py                  # download + reconcile + email
  python3 run_live.py --no-email       # download + reconcile only
  python3 run_live.py --skip-download  # reconcile files already in downloads/
  python3 run_live.py --headed         # visible browser (debugging)
  python3 run_live.py --force-email    # send even if the EPF file is missing
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import Config
from recon_core import detect_files, find_epf_file, run_reconciliation

log = logging.getLogger("run_live")


def setup_logging():
    Path(Config.LOGS_DIR).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _find_chrome():
    """Locate a Chrome/Chromium binary, platform-aware."""
    import os
    import platform

    if platform.system() == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        candidates = [
            "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium", "/usr/bin/chromium-browser",
        ]
    for c in candidates:
        if os.path.exists(c):
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        for d in os.environ.get("PATH", "").split(os.pathsep):
            f = os.path.join(d, name)
            if os.path.exists(f):
                return f
    return None


def preflight_downloader():
    """
    Check the downloader's prerequisites before touching the browser, so a missing
    package produces one actionable message instead of a stack trace.
    """
    import platform

    missing = []
    for mod, pkg in (("selenium", "selenium==4.15.2"),
                     ("webdriver_manager", "webdriver-manager==4.0.1")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if missing:
        print()
        print("=" * 74)
        print("MISSING DEPENDENCY - the RMS downloader needs extra packages")
        print("=" * 74)
        print("The dashboard and the file-based CLI do NOT need these; only the")
        print("browser download step does. Install them with:")
        print()
        print(f"    pip install {' '.join(missing)} schedule==1.2.0 xlrd==2.0.1")
        print()
        print("Then re-run:  python3 run_live.py")
        print()
        print("Or skip the download and reconcile files you already have:")
        print("    python3 reconcile_files.py --auto")
        print("=" * 74)
        return False

    chrome = _find_chrome()
    if not chrome:
        print()
        print("=" * 74)
        print("GOOGLE CHROME NOT FOUND - the downloader drives a real browser")
        print("=" * 74)
        if platform.system() == "Darwin":
            print("Install it with Homebrew:")
            print()
            print("    brew install --cask google-chrome")
        else:
            print("Install it with your package manager, e.g. on Debian/Ubuntu:")
            print()
            print("    wget -O /tmp/chrome.deb https://dl.google.com/linux/direct/")
            print("        google-chrome-stable_current_amd64.deb")
            print("    sudo apt-get install -y /tmp/chrome.deb")
        print()
        print("Or skip the download and reconcile files you already have:")
        print("    python3 reconcile_files.py --auto")
        print("=" * 74)
        return False

    log.info(f"Preflight OK - selenium present, Chrome at {chrome}")
    return True


def download(headed=False):
    """Log into RMS and pull the salary sheet, TDS sheet and bank SOA."""
    if not preflight_downloader():
        raise SystemExit(2)

    from rms_automation import RMSAutomation

    tm = Config.get_target_months()
    log.info("=" * 78)
    log.info(f"Target months -> salary/TDS/EPF: {tm['salary_month_str']} | bank: {tm['bank_month_str']}")
    log.info(f"RMS month dropdown value: {tm['salary_month_value']}")
    log.info(f"Bank date range: {tm['bank_start_date']} -> {tm['bank_end_date']}")
    log.info("=" * 78)

    rms = RMSAutomation()
    rms.setup_driver(headed=headed)
    try:
        if not rms.login():
            raise RuntimeError("RMS login failed - see the log above for the reason")

        log.info("Downloading Salary Sheet...")
        if not rms.download_salary_sheet(tm["salary_month_value"]):
            raise RuntimeError("Salary Sheet download failed")

        log.info("Downloading TDS Sheet...")
        if not rms.download_tds_sheet(tm["salary_month_value"]):
            raise RuntimeError("TDS Sheet download failed")

        log.info("Downloading Bank SOA...")
        if not rms.download_bank_soa(tm["bank_start_date"], tm["bank_end_date"]):
            raise RuntimeError("Bank SOA download failed")

        log.info("All three downloads reported success")
    finally:
        rms.close()


def main(argv=None):
    p = argparse.ArgumentParser(description="Live salary reconciliation run")
    p.add_argument("--skip-download", action="store_true")
    p.add_argument("--no-email", action="store_true")
    p.add_argument("--force-email", action="store_true",
                   help="Send the report even when no EPF file was found")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--month", help='Period label, e.g. "August 2026"')
    args = p.parse_args(argv)

    setup_logging()
    log.info("=" * 78)
    log.info(f"LIVE RUN STARTED — {datetime.now():%d %B %Y at %I:%M %p}")
    log.info("=" * 78)

    if not args.skip_download:
        download(headed=args.headed)

    # ---- detect the files that actually landed ----
    found = detect_files(Config.DOWNLOAD_DIR)
    log.info(f"Detected in downloads/: { {k: Path(v).name for k, v in found.items()} }")

    missing = [k for k in ("salary", "tds", "bank") if k not in found]
    if missing:
        log.error(f"Missing downloaded files: {missing}")
        return 2

    real_epf = find_epf_file()
    epf_available = real_epf is not None

    if real_epf is None:
        log.warning(f"No EPF file in {Config.EPF_UPLOAD_DIR}")
        if not args.no_email and not args.force_email:
            log.error(
                "HOLDING EMAIL: without an EPF file the report cannot show a real EPF "
                "reconciliation. Upload the EPF file, or pass --force-email to send anyway."
            )
            return 3
        tmp_epf = Path(Config.EPF_UPLOAD_DIR) / "_no_epf_placeholder.xlsx"
        pd.DataFrame({"UAN": [], "EPF Amount": []}).to_excel(tmp_epf, index=False)
        epf_file = str(tmp_epf)
    else:
        epf_file = real_epf

    result = run_reconciliation(
        found["salary"], found["tds"], found["bank"], epf_file,
        out_dir=Config.REPORTS_DIR,
        month_label=args.month,
        epf_available=epf_available,
    )

    log.info("=" * 78)
    log.info("RECONCILIATION COMPLETE")
    log.info(f"Report : {result['report_path']}")
    log.info(f"Counts : {result['counts']}")
    for k, v in result["summary"].items():
        log.info(f"   {k:<22}: {v}")
    log.info("=" * 78)

    if args.no_email:
        log.info("Email skipped (--no-email)")
        return 0

    from email_handler import EmailHandler

    ok = EmailHandler().send_reconciliation_report(
        report_file=result["report_path"], summary_data=result["summary"]
    )
    log.info(f"Email sent: {ok}")
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
