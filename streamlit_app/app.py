import streamlit as st
import pandas as pd
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import os
import time

st.set_page_config(page_title="Salary Reconciliation Dashboard", layout="wide")

IS_CLOUD = os.getenv("STREAMLIT_SERVER_PORT") is not None  # simple heuristic

# Sidebar logo (top-left)
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "koenig-logo.png"
if LOGO_PATH.exists():
    st.sidebar.image(str(LOGO_PATH), use_container_width=True)
else:
    st.sidebar.warning("Logo not found: assets/koenig-logo.png")

BASE_DIR = Path.home() / "Downloads" / "Agent" / "Reconciliation"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
EPF_DIR = BASE_DIR / "epf_uploads"

st.title("Salary Reconciliation Dashboard")
st.caption("Management Dashboard • Upload Salary_Reconciliation_*.xlsx to view KPIs and drilldowns")

if IS_CLOUD:
    st.info("Upload the latest Salary_Reconciliation_*.xlsx report to view KPIs and drilldowns.")
else:
    st.info("Auto-load enabled: dashboard will load the latest report from reports/ if available.")

def find_latest_report():
    if not REPORTS_DIR.exists():
        return None
    files = sorted(REPORTS_DIR.glob("Salary_Reconciliation_*.xlsx"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None

def load_sheets_from_bytes(file_bytes: bytes):
    xls = pd.ExcelFile(BytesIO(file_bytes))
    return {name: pd.read_excel(BytesIO(file_bytes), sheet_name=name) for name in xls.sheet_names}

def load_sheets_from_path(path: Path):
    xls = pd.ExcelFile(path)
    return {name: pd.read_excel(path, sheet_name=name) for name in xls.sheet_names}

def safe_int(x, default=0):
    try:
        return int(float(x))
    except Exception:
        return default

def fmt_inr(x):
    try:
        return f"₹ {float(x):,.2f}"
    except Exception:
        return "₹ 0.00"

def show_kpis(summary_row, full_df):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Employees", safe_int(summary_row.get("Total Employees", len(full_df))))
    c2.metric("Fully Matched", safe_int(summary_row.get("Fully Matched", 0)))
    c3.metric("TDS Mismatches", safe_int(summary_row.get("TDS Mismatches", 0)))
    c4.metric("Bank Mismatches", safe_int(summary_row.get("Bank Mismatches", 0)))
    c5.metric("EPF Mismatches", safe_int(summary_row.get("EPF Mismatches", 0)))

def show_financials(summary_row):
    st.subheader("💰 Financial Summary")
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    fc1.metric("Total Gross Salary", fmt_inr(summary_row.get("Total Gross Salary", 0)))
    fc2.metric("Total Net Payable", fmt_inr(summary_row.get("Total Net Payable", 0)))
    fc3.metric("Total Bank Payment", fmt_inr(summary_row.get("Total Bank Payment", 0)))
    fc4.metric("Total TDS", fmt_inr(summary_row.get("Total TDS", 0)))
    fc5.metric("Total EPF", fmt_inr(summary_row.get("Total EPF", 0)))

def download_df_csv(df, name):
    return df.to_csv(index=False).encode("utf-8")

# -----------------------
# Sidebar: Load / Run
# -----------------------
st.sidebar.header("Controls")

# A) Upload FINAL report (xlsx) - optional
uploaded_report = st.sidebar.file_uploader(
    "Upload Final Reconciliation Report (.xlsx)",
    type=["xlsx"],
    key="upload_final_report"
)

st.sidebar.markdown("---")
st.sidebar.subheader("Manual Inputs (4 files)")

salary_file = st.sidebar.file_uploader(
    "1) Salary Sheet (Salay_Sheet_*.xls)",
    type=["xls", "xlsx"],
    key="upload_salary"
)

tds_file = st.sidebar.file_uploader(
    "2) TDS Sheet (Update TDS*.xlsx)",
    type=["xls", "xlsx"],
    key="upload_tds"
)

bank_file = st.sidebar.file_uploader(
    "3) Bank Book (BankBookEntry*.xls)",
    type=["xls", "xlsx"],
    key="upload_bank"
)

epf_file = st.sidebar.file_uploader(
    "4) EPF Upload (epf_*.xlsx)",
    type=["xls", "xlsx"],
    key="upload_epf"
)

latest_report = find_latest_report()
auto_load = st.sidebar.checkbox("Auto-load latest report from reports/", value=True)

report_path = None
sheets = None

if uploaded_report is not None:
    sheets = load_sheets_from_bytes(uploaded_report.getvalue())
    st.sidebar.success("Loaded uploaded final report")
else:
    if auto_load and latest_report:
        report_path = latest_report
        sheets = load_sheets_from_path(report_path)
        st.sidebar.success(f"Auto-loaded: {report_path.name}")
    else:
        st.info("Upload a report OR enable auto-load and ensure reports/ has a Salary_Reconciliation_*.xlsx file.")
        st.stop()

# Manual Run section
st.sidebar.subheader("Manual Run (if automation didn’t run)")
st.sidebar.caption("Runs your existing reconciliation script and generates a new Excel in reports/.")

if st.sidebar.button("Run Reconciliation Now"):
    with st.spinner("Running reconciliation... this may take a few minutes"):
        # Run main.py from base dir
        # IMPORTANT: This assumes your venv + .env are already configured
        cmd = [sys.executable, str(BASE_DIR / "test_agent.py")]
        # If your test_agent asks yes/no, it will block. Better: call main agent directly if available.
        # If you already have a non-interactive entry point, replace cmd accordingly.
        proc = subprocess.Popen(cmd, cwd=str(BASE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        output_lines = []
        start = time.time()
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                output_lines.append(line.rstrip())
                if len(output_lines) > 200:
                    output_lines = output_lines[-200:]
            if time.time() - start > 600:  # 10 minutes safety
                proc.kill()
                output_lines.append("Stopped: runtime exceeded 10 minutes.")
                break

        st.subheader("Run Output (tail)")
        st.code("\n".join(output_lines[-200:]), language="text")

        # reload latest report after run
        new_latest = find_latest_report()
        if new_latest:
            st.success(f"Latest report: {new_latest.name}")
            sheets = load_sheets_from_path(new_latest)

# Automation status info
st.sidebar.subheader("Automation Status")
st.sidebar.write(f"Latest report: **{latest_report.name if latest_report else 'None'}**")
if EPF_DIR.exists():
    epf_files = sorted(EPF_DIR.glob("*.xlsx"), key=lambda p: p.stat().st_mtime)
    st.sidebar.write(f"Latest EPF: **{epf_files[-1].name if epf_files else 'None'}**")
else:
    st.sidebar.write("EPF folder missing")

# -----------------------
# Main content
# -----------------------
summary_df = sheets.get("Summary")
full_df = sheets.get("Full Reconciliation")
disc_df = sheets.get("Discrepancies")
branch_df = sheets.get("Branch Wise")
dept_df = sheets.get("Department Wise")
desig_df = sheets.get("Designation Wise")

if summary_df is None or summary_df.empty:
    summary_row = {}
else:
    summary_row = summary_df.iloc[0].to_dict()

st.subheader("📌 KPI Summary")
if full_df is None:
    st.error("Full Reconciliation sheet not found in the report.")
    st.stop()

show_kpis(summary_row, full_df)
show_financials(summary_row)

st.divider()

def sanitize_df_for_streamlit(df):
    # Drop empty "Unnamed" columns created by merged/title rows
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    # Convert mixed object columns to string to avoid Arrow issues
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = df[c].astype(str)
    return df

    st.dataframe(sanitize_df_for_streamlit(df))

tabs = st.tabs([
    "Branch Wise", "Department Wise", "Designation Wise",
    "Discrepancies", "Full Reconciliation", "Downloads"
])

with tabs[0]:
    st.subheader("Branch Wise")
    if branch_df is not None:
        st.dataframe(branch_df, use_container_width=True)
    else:
        st.warning("Branch Wise sheet missing")

with tabs[1]:
    st.subheader("Department Wise")
    if dept_df is not None:
        st.dataframe(dept_df, use_container_width=True)
    else:
        st.warning("Department Wise sheet missing")

with tabs[2]:
    st.subheader("Designation Wise")
    if desig_df is not None:
        st.dataframe(desig_df, use_container_width=True)
    else:
        st.warning("Designation Wise sheet missing")

with tabs[3]:
    st.subheader("Discrepancies (filters + export)")
    if disc_df is None:
        st.warning("Discrepancies sheet missing")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            f_branch = st.selectbox("Branch", ["All"] + sorted(disc_df["Branch"].dropna().unique().tolist()) if "Branch" in disc_df.columns else ["All"])
        with col2:
            f_dept = st.selectbox("Department", ["All"] + sorted(disc_df["Department"].dropna().unique().tolist()) if "Department" in disc_df.columns else ["All"])
        with col3:
            f_emp = st.text_input("EmpCode contains")

        df = disc_df.copy()
        if f_branch != "All" and "Branch" in df.columns:
            df = df[df["Branch"] == f_branch]
        if f_dept != "All" and "Department" in df.columns:
            df = df[df["Department"] == f_dept]
        if f_emp and "EmpCode" in df.columns:
            df = df[df["EmpCode"].astype(str).str.contains(f_emp, na=False)]

        st.dataframe(df, use_container_width=True, height=500)

        st.download_button(
            "Download Discrepancies CSV",
            data=download_df_csv(df, "discrepancies.csv"),
            file_name="discrepancies.csv",
            mime="text/csv"
        )

with tabs[4]:
    st.subheader("Full Reconciliation (search)")
    col1, col2 = st.columns(2)
    with col1:
        emp = st.text_input("Filter EmpCode contains")
    with col2:
        name = st.text_input("Filter EmployeeName contains")

    df = full_df.copy()
    if emp and "EmpCode" in df.columns:
        df = df[df["EmpCode"].astype(str).str.contains(emp, na=False)]
    if name and "EmployeeName" in df.columns:
        df = df[df["EmployeeName"].astype(str).str.contains(name, case=False, na=False)]

    st.dataframe(df, use_container_width=True, height=600)

with tabs[5]:
    st.subheader("Downloads")
    if report_path:
        st.write(f"Current report: **{report_path.name}**")

    # allow downloading the currently loaded report if it was auto-loaded
    if report_path and report_path.exists():
        st.download_button(
            "Download Current Excel Report",
            data=report_path.read_bytes(),
            file_name=report_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("If you uploaded a file, use your browser download for that file or auto-load from reports/.")
