"""
Selenium-free reconciliation core.

This module is what makes the project deployable to Streamlit Cloud:
it needs only pandas + openpyxl, no Chrome, no RMS portal access.

Public API
----------
detect_files(directory)          -> {"salary": path, "tds": path, "bank": path}
find_epf_file(directory)         -> path | None
run_reconciliation(...)          -> dict(report_path, summary, counts, engine)
"""

import glob
import logging
import numpy as np
import os
from datetime import datetime
from pathlib import Path

from config import Config
from data_processor import DataProcessor
from reconciliation_engine import ReconciliationEngine

logger = logging.getLogger(__name__)

# Order matters — the RMS bank export is named
# "BankBookEntrySalaryUploaded_<date>.xls" and also contains the word
# "salary", so BANK must be tested before SALARY.
SALARY_PATTERNS = ("salay_sheet", "salary_sheet")
TDS_PATTERNS = ("update tds", "updatetds", "tds")
BANK_PATTERNS = ("bankbookentry", "bankbook", "bank")


def _excel_files(directory):
    """All Excel files in a directory, newest first. Junk/lock files excluded."""
    files = glob.glob(str(Path(directory) / "*.xlsx")) + glob.glob(
        str(Path(directory) / "*.xls")
    )
    files = [f for f in files if not os.path.basename(f).startswith("~$")]
    return sorted(files, key=os.path.getctime, reverse=True)


def detect_files(directory):
    """
    Detect salary / TDS / bank files by their real RMS filenames.
    Returns a dict with the keys it could find.
    """
    files = {}
    all_excel = _excel_files(directory)

    logger.info(f"Found {len(all_excel)} Excel file(s) in {directory}")
    for idx, f in enumerate(all_excel):
        logger.info(f"  {idx + 1}. {os.path.basename(f)} ({os.path.getsize(f):,} bytes)")

    for file in all_excel:
        name = os.path.basename(file).lower()

        # Order matters: check the most specific patterns first.
        if any(p in name for p in SALARY_PATTERNS) and "salary" not in files:
            files["salary"] = file
        elif any(p in name for p in TDS_PATTERNS) and "tds" not in files:
            files["tds"] = file
        elif any(p in name for p in BANK_PATTERNS) and "bank" not in files:
            files["bank"] = file

    return files


def find_epf_file(directory=None):
    """Newest Excel file in the EPF upload directory."""
    directory = directory or Config.EPF_UPLOAD_DIR
    excel_files = [f for f in _excel_files(directory)
                   if "_no_epf_placeholder" not in os.path.basename(f)]
    if not excel_files:
        logger.warning(f"No EPF file found in {directory}")
        return None

    others = SALARY_PATTERNS + TDS_PATTERNS + BANK_PATTERNS

    def _is_other(f):
        return any(p in os.path.basename(f).lower() for p in others)

    epf_like = [f for f in excel_files
                if "epf" in os.path.basename(f).lower()
                or "uan" in os.path.basename(f).lower()]
    if not epf_like:
        epf_like = [f for f in excel_files if not _is_other(f)]

    if not epf_like:
        logger.warning(f"No EPF file found in {directory}")
        return None

    logger.info(f"Found EPF file: {epf_like[0]}")
    return epf_like[0]


def run_reconciliation(
    salary_file,
    tds_file,
    bank_file,
    epf_file,
    out_dir=None,
    month_label=None,
    save_report=True,
    epf_available=True,
):
    """
    Full pipeline: 4 input files -> reconciled DataFrame -> styled Excel report.

    month_label: free-text period label, e.g. "December 2025".
                 Defaults to Config.get_target_months() logic.
    Returns a dict with report_path / summary / counts / engine / report_file.
    """
    out_dir = Path(out_dir or Config.REPORTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not month_label:
        month_label = Config.get_target_months()["salary_month"].strftime("%B_%Y")
    safe_label = str(month_label).replace(" ", "_").replace("-", "_")

    logger.info("Processing Salary Sheet...")
    salary_data = DataProcessor.process_salary_sheet(salary_file)

    logger.info("Processing TDS Sheet...")
    tds_data = DataProcessor.process_tds_sheet(tds_file)

    logger.info("Processing Bank SOA...")
    bank_data = DataProcessor.process_bank_soa(bank_file)

    logger.info("Processing EPF Sheet...")
    epf_data = DataProcessor.process_epf_sheet(epf_file)

    engine = ReconciliationEngine(salary_data, tds_data, bank_data, epf_data)
    reconciled = engine.reconcile()

    if not epf_available:
        # No EPF source at all. Flagging every employee as an EPF mismatch would be
        # factually wrong, so mark EPF as not reconciled and re-derive the status.
        r = engine.reconciled_data
        r["EPF_Match"] = "Not Reconciled"
        r["EPF_Difference"] = 0
        r["Overall_Status"] = np.where(
            r["Overall_Status"] == "No Data",
            "No Data",
            np.where(
                (r["TDS_Match"] == "Matched") & (r["Bank_Match"] == "Matched"),
                "Fully Matched",
                "Has Discrepancies",
            ),
        )
        r["Remarks"] = r.apply(engine._generate_remarks, axis=1)
        reconciled = r

    summary_df = engine.generate_summary_report()
    summary = summary_df.iloc[0].to_dict()

    report_file = out_dir / f"Salary_Reconciliation_{safe_label}.xlsx"
    if save_report:
        engine.save_reports(str(report_file))

    counts = {
        "salary_rows": int(len(salary_data)),
        "tds_rows": int(len(tds_data)),
        "bank_rows": int(len(bank_data)),
        "epf_rows": int(len(epf_data)),
        "reconciled_rows": int(len(reconciled)),
    }

    return {
        "report_path": str(report_file),
        "report_file": report_file,
        "summary": summary,
        "counts": counts,
        "engine": engine,
        "reconciled": reconciled,
    }


def run_from_downloads(downloads_dir=None, epf_dir=None, out_dir=None, month_label=None):
    """Auto-detect the 4 files and reconcile. Used by the CLI."""
    downloads_dir = downloads_dir or Config.DOWNLOAD_DIR
    epf_dir = epf_dir or Config.EPF_UPLOAD_DIR

    found = detect_files(downloads_dir)
    missing = [k for k in ("salary", "tds", "bank") if k not in found]

    epf_file = find_epf_file(epf_dir)
    if not epf_file:
        missing.append("epf")

    if missing:
        raise FileNotFoundError(
            f"Missing input files: {', '.join(missing)} "
            f"(searched {downloads_dir} and {epf_dir})"
        )

    return run_reconciliation(
        found["salary"],
        found["tds"],
        found["bank"],
        epf_file,
        out_dir=out_dir,
        month_label=month_label,
    )
