"""
Environment diagnostic.

Run this first whenever something "cannot find" a file or a credential.
It prints the resolved project paths, which credentials loaded, whether the
working directories exist, today's date logic, and whether the browser
dependencies are available.

    python doctor.py
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Keep library chatter out of the report - doctor prints its own lines.
# Errors still surface; warnings are reported by doctor itself.
logging.basicConfig(level=logging.ERROR, format="        [%(levelname)s] %(message)s")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config  # noqa: E402

OK, BAD, WARN = "  OK  ", " FAIL ", " WARN "


def line(status, label, detail=""):
    print(f"[{status}] {label}" + (f"  ->  {detail}" if detail else ""))


def mask(v, keep=3):
    if not v:
        return None
    s = str(v)
    if "@" in s:
        u, _, d = s.partition("@")
        return f"{u[:keep]}***@{d}"
    return s[:keep] + "*" * max(0, len(s) - keep)


def main():
    print("=" * 74)
    print("SALARY RECONCILIATION AGENT - ENVIRONMENT DIAGNOSTIC")
    print("=" * 74)

    # ---- paths ----
    print("\nPATHS")
    base = Path(Config.BASE_DIR)
    line(OK, "BASE_DIR", str(base))
    line(OK if (base / "config.py").exists() else BAD, "config.py present")
    env_file = base / ".env"
    line(OK if env_file.exists() else BAD, ".env", str(env_file))

    for name in ("DOWNLOAD_DIR", "EPF_UPLOAD_DIR", "REPORTS_DIR", "LOGS_DIR"):
        d = Path(getattr(Config, name))
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
        line(OK if d.exists() else BAD, name, str(d))

    # ---- credentials ----
    print("\nCREDENTIALS (masked)")
    checks = [
        ("RMS_USERNAME", Config.RMS_USERNAME),
        ("RMS_PASSWORD", Config.RMS_PASSWORD),
        ("SENDER_EMAIL", Config.SENDER_EMAIL),
        ("SENDER_PASSWORD", Config.SENDER_PASSWORD),
        ("RECIPIENT_EMAILS", Config.RECIPIENT_EMAILS),
        ("TAX_TEAM_EMAIL", Config.TAX_TEAM_EMAIL),
    ]
    missing = []
    for label, val in checks:
        if not val:
            missing.append(label)
            line(BAD, label, "not set")
        else:
            shown = mask(val[0]) if isinstance(val, list) else mask(val)
            line(OK, label, str(shown))
    line(OK, "SMTP_SERVER", f"{Config.SMTP_SERVER}:{Config.SMTP_PORT}")
    line(OK, "RMS_URL", Config.RMS_URL)

    # ---- date logic ----
    print("\nDATE LOGIC (today)")
    tm = Config.get_target_months()
    line(OK, "today", datetime.now().strftime("%d %B %Y (day %d)") % ())
    line(OK, "salary / TDS / EPF", tm["salary_month_str"])
    line(OK, "bank SOA", tm["bank_month_str"])
    line(OK, "RMS month value", tm["salary_month_value"])
    line(OK, "bank date range", f"{tm['bank_start_date']} -> {tm['bank_end_date']}")

    # ---- browser deps (only needed for the downloader) ----
    print("\nBROWSER DEPENDENCIES (only needed to download from RMS)")
    try:
        import selenium  # noqa: F401
        line(OK, "selenium importable")
    except Exception:
        line(WARN, "selenium", "not installed - fine for the dashboard / CLI")

    chrome = None
    for exe in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        p = Path("/usr/bin") / exe
        if p.exists():
            chrome = str(p)
            break
    line(OK if chrome else WARN, "chrome binary", chrome or "not found")

    # ---- input files ----
    print("\nINPUT FILES")
    try:
        from recon_core import detect_files, find_epf_file
        found = detect_files(Config.DOWNLOAD_DIR)
        for key in ("salary", "tds", "bank"):
            line(OK if key in found else WARN, f"{key} file",
                 Path(found[key]).name if key in found else "not found in downloads/")
        epf = find_epf_file()
        line(OK if epf else WARN, "epf file",
             Path(epf).name if epf else "not found in epf_uploads/")
    except Exception as e:
        line(WARN, "file detection", f"{type(e).__name__}: {e}")

    # ---- verdict ----
    print("\n" + "=" * 74)
    if missing:
        print(f"RESULT: {len(missing)} credential(s) missing -> {', '.join(missing)}")
        print("Copy .env.example to .env and fill it in, then re-run doctor.py")
    else:
        print("RESULT: configuration looks good.")
    print("=" * 74)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
