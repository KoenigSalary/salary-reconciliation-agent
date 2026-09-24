"""
Configuration file for Salary Reconciliation Agent
Updated for project path: Downloads/Agent/Reconciliation
"""

import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
from dotenv import load_dotenv

class Config:
    # Base project directory
    BASE_DIR = Path.home() / "Downloads" / "Agent" / "Reconciliation"
    
    # Load .env file
    env_path = BASE_DIR / ".env"
    load_dotenv(dotenv_path=env_path)
    
    # RMS Portal Configuration
    RMS_URL = "https://rms.koenig-solutions.com"
    RMS_USERNAME = os.getenv("RMS_USERNAME")
    RMS_PASSWORD = os.getenv("RMS_PASSWORD")
    
    # Email Configuration
    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.office365.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    RECIPIENT_EMAILS = os.getenv("RECIPIENT_EMAILS", "").split(",") if os.getenv("RECIPIENT_EMAILS") else []
    TAX_TEAM_EMAIL = os.getenv("TAX_TEAM_EMAIL")
    
    # File Paths - Updated to new project structure
    DOWNLOAD_DIR = str(BASE_DIR / "downloads")
    EPF_UPLOAD_DIR = str(BASE_DIR / "epf_uploads")
    REPORTS_DIR = str(BASE_DIR / "reports")
    LOGS_DIR = str(BASE_DIR / "logs")
    
    # Branch Mapping
    BRANCH_MAPPING = {
        "GOA": "Goa",
        "CHENNAI": "Chennai",
        "DEHRADUN": "Dehradun",
        "BANGALORE": "Bangalore",
        "BENGALURU": "Bangalore",
        # All others including Delhi map to Delhi
    }
    
    @staticmethod
    def get_target_months():
        """
        Calculate which months to fetch data for based on current date
        
        Logic:
        - If day <= 15: Salary/TDS/EPF = 2 months back, Bank = 1 month back
        - If day > 15: Salary/TDS/EPF = 1 month back, Bank = current month
        """
        today = datetime.now()
        current_day = today.day
        
        if current_day <= 15:
            # Before 15th: 2 months back for salary/TDS/EPF, 1 month back for bank
            salary_month = today - relativedelta(months=2)
            bank_month = today - relativedelta(months=1)
        else:
            # After 15th: 1 month back for salary/TDS/EPF, current month for bank
            salary_month = today - relativedelta(months=1)
            bank_month = today
        
        return {
            "salary_month": salary_month,
            "tds_month": salary_month,
            "epf_month": salary_month,
            "bank_month": bank_month,
            "salary_month_str": salary_month.strftime("%B - %Y"),
            "bank_month_str": bank_month.strftime("%B - %Y"),
            "salary_month_value": salary_month.strftime("%-m/1/%Y 12:00:00 AM"),  # Format for RMS dropdown
            "bank_start_date": bank_month.replace(day=1).strftime("%d-%b-%y"),
            "bank_end_date": (bank_month.replace(day=1) + relativedelta(months=1) - timedelta(days=1)).strftime("%d-%b-%y")
        }
    
    @staticmethod
    def map_branch(location):
        """Map employee location to standardized branch name"""
        if not location:
            return "Delhi"
        
        location_upper = str(location).upper().strip()
        
        # Check if it matches any specific branch
        for key, value in Config.BRANCH_MAPPING.items():
            if key in location_upper:
                return value
        
        # Default to Delhi for all others
        return "Delhi"
