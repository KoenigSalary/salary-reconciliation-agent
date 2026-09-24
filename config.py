"""
Configuration file for Salary Reconciliation Agent

BASE_DIR resolution order (important for GitHub / Streamlit Cloud):
  1. RECON_BASE_DIR environment variable
  2. the directory this file lives in, IF it holds a .env
  3. legacy fallback: ~/Downloads/Agent/Reconciliation
  4. the directory this file lives in
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv


def _resolve_base_dir() -> Path:
    """
    Resolve the project base directory.

    Rule 2 before rule 3 matters: a fresh extraction that carries its own .env
    must never be silently redirected to an older copy at the legacy path.
    """
    env_dir = os.getenv("RECON_BASE_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    here = Path(__file__).resolve().parent
    legacy = Path.home() / "Downloads" / "Agent" / "Reconciliation"

    if (here / ".env").exists() and (here / "config.py").exists():
        return here
    if legacy.exists() and (legacy / "config.py").exists():
        return legacy
    return here


BASE_DIR = _resolve_base_dir()

# Make the resolved path visible on every run - a wrong BASE_DIR is the most
# common source of "it cannot find my files" confusion.
import logging as _logging
_logging.getLogger("config").info(f"Project base directory: {BASE_DIR}")

load_dotenv(dotenv_path=BASE_DIR / ".env")
load_dotenv()


class Config:
    BASE_DIR = BASE_DIR

    # RMS Portal Configuration
    RMS_URL = os.getenv("RMS_URL", "https://rms.koenig-solutions.com")
    RMS_USERNAME = os.getenv("RMS_USERNAME")
    RMS_PASSWORD = os.getenv("RMS_PASSWORD")

    # Email Configuration
    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.office365.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    RECIPIENT_EMAILS = (
        [e.strip() for e in os.getenv("RECIPIENT_EMAILS", "").split(",") if e.strip()]
        if os.getenv("RECIPIENT_EMAILS")
        else []
    )
    TAX_TEAM_EMAIL = os.getenv("TAX_TEAM_EMAIL")

    # File Paths
    DOWNLOAD_DIR = str(BASE_DIR / "downloads")
    EPF_UPLOAD_DIR = str(BASE_DIR / "epf_uploads")
    REPORTS_DIR = str(BASE_DIR / "reports")
    LOGS_DIR = str(BASE_DIR / "logs")

    BRANCH_MAPPING = {
        "GURGAON": "Gurgaon",
        "GURUGRAM": "Gurgaon",
        "GOA": "Goa",
        "CHENNAI": "Chennai",
        "DEHRADUN": "Dehradun",
        "BANGALORE": "Bangalore",
        "BENGALURU": "Bangalore",
    }

    @staticmethod
    def get_target_months(now: datetime | None = None):
        """day <= 15: salary/TDS/EPF = 2 months back, bank = 1 back.
        day >  15: salary/TDS/EPF = 1 month back,  bank = current."""
        today = now or datetime.now()
        if today.day <= 15:
            salary_month = today - relativedelta(months=2)
            bank_month = today - relativedelta(months=1)
        else:
            salary_month = today - relativedelta(months=1)
            bank_month = today

        return {
            "salary_month": salary_month,
            "tds_month": salary_month,
            "epf_month": salary_month,
            "bank_month": bank_month,
            "salary_month_str": salary_month.strftime("%B - %Y"),
            "bank_month_str": bank_month.strftime("%B - %Y"),
            "salary_month_value": salary_month.strftime("%m/1/%Y 12:00:00 AM"),
            "bank_start_date": bank_month.replace(day=1).strftime("%d-%b-%y"),
            "bank_end_date": (
                bank_month.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
            ).strftime("%d-%b-%y"),
        }

    @staticmethod
    def map_branch(location):
        if location is None or (isinstance(location, float) and location != location):
            return "Delhi"
        location_upper = str(location).upper().strip()
        if not location_upper or location_upper in ("NAN", "NONE"):
            return "Delhi"
        for key, value in Config.BRANCH_MAPPING.items():
            if key in location_upper:
                return value
        return "Delhi"
