"""
Salary Reconciliation Dashboard - Streamlit app (Streamlit Community Cloud ready)

Two ways to use it:
  A) Upload the 4 raw RMS files -> reconciles in-process and shows the dashboard.
  B) Upload an already-generated Salary_Reconciliation_*.xlsx -> dashboard only.

The RMS download step (Selenium + Chrome) is NOT part of this app - it cannot run on
Streamlit Cloud. Run `python3 run_live.py` locally to fetch the files first.
"""

import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Salary Reconciliation Dashboard", layout="wide")


def _bridge_secrets():
    """Expose Streamlit secrets as env vars so config.py can read them."""
    keys = [
        "SENDER_EMAIL", "SENDER_PASSWORD", "SMTP_SERVER", "SMTP_PORT",
        "RECIPIENT_EMAILS", "TAX_TEAM_EMAIL",
        "RMS_USERNAME", "RMS_PASSWORD", "RMS_URL", "RECON_BASE_DIR",
    ]
    try:
        for k in keys:
            if k in st.secrets and not os.getenv(k):
                os.environ[k] = str(st.secrets[k])
    except Exception:
        pass


_bridge_secrets()

from config import Config                      # noqa: E402
from recon_core import run_reconciliation      # noqa: E402

SHEET_ORDER = ["Branch Wise", "Department Wise", "Designation Wise",
               "Discrepancies", "Full Reconciliation"]


def _read_report_sheet(src, sheet_name: str) -> pd.DataFrame:
    """
    Read one sheet from a generated report.

    The generator writes a merged title row above the headers (row 1 = title,
    row 2 = headers), so a naive header=0 read yields 'Unnamed: N' columns.
    Detect the real header row instead.
    """
    raw = pd.read_excel(src, sheet_name=sheet_name, header=None)
    if raw.empty:
        return raw
    header_idx = 0
    for i in range(min(5, len(raw))):
        if raw.iloc[i].notna().sum() >= 3:
            header_idx = i
            break
    df = raw.iloc[header_idx + 1:].copy()
    df.columns = [str(v).strip() for v in raw.iloc[header_idx].tolist()]
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    return df.dropna(how="all").reset_index(drop=True)


def load_report_from_bytes(data: bytes) -> dict:
    xls = pd.ExcelFile(BytesIO(data))
    return {n: _read_report_sheet(BytesIO(data), n) for n in xls.sheet_names}


def load_report_from_path(path: Path) -> dict:
    xls = pd.ExcelFile(path)
    return {n: _read_report_sheet(path, n) for n in xls.sheet_names}


def safe_int(x, default=0):
    try:
        return int(float(x))
    except Exception:
        return default


def fmt_inr(x):
    try:
        return f"Rs {float(x):,.2f}"
    except Exception:
        return "Rs 0.00"


def clean_for_display(df: pd.DataFrame) -> pd.DataFrame:
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")].copy()
    for c in df.columns:
        if df[c].dtype == "object":
            coerced = pd.to_numeric(df[c], errors="coerce")
            if coerced.notna().sum() >= max(1, int(0.8 * df[c].notna().sum())):
                df[c] = coerced
    return df


def find_latest_report():
    reports_dir = Path(Config.REPORTS_DIR)
    if not reports_dir.exists():
        return None
    files = sorted(reports_dir.glob("Salary_Reconciliation_*.xlsx"),
                   key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def show_table(df, label):
    if df is None or len(df) == 0:
        st.warning(f"{label} sheet missing")
    else:
        st.dataframe(clean_for_display(df), width="stretch")


LOGO_PATH = ROOT / "assets" / "koenig-logo.png"
if LOGO_PATH.exists():
    st.sidebar.image(str(LOGO_PATH), width="stretch")

st.sidebar.header("Controls")
mode = st.sidebar.radio("Mode",
                        ["Run reconciliation from files", "View an existing report"],
                        index=0)

sheets = run_summary = report_bytes = report_name = None
latest_report = find_latest_report()

if mode == "Run reconciliation from files":
    st.sidebar.caption("Upload the 4 files. Reconciliation runs in-process - "
                       "no Chrome, no RMS login needed.")
    salary_file = st.sidebar.file_uploader("1) Salary Sheet (Salay_Sheet_*.xls)",
                                           type=["xls", "xlsx"], key="u_salary")
    tds_file = st.sidebar.file_uploader("2) TDS Sheet (Update TDS*.xlsx)",
                                        type=["xls", "xlsx"], key="u_tds")
    bank_file = st.sidebar.file_uploader("3) Bank Book (BankBookEntry*.xls)",
                                         type=["xls", "xlsx"], key="u_bank")
    epf_file = st.sidebar.file_uploader("4) EPF Upload (epf_*.xlsx)",
                                        type=["xls", "xlsx"], key="u_epf")

    default_label = Config.get_target_months()["salary_month"].strftime("%B %Y")
    month_label = st.sidebar.text_input("Period label", value=default_label)

    if st.sidebar.button("Run Reconciliation", type="primary"):
        uploaded = {"Salary": salary_file, "TDS": tds_file,
                    "Bank": bank_file, "EPF": epf_file}
        missing = [k for k, v in uploaded.items() if v is None]
        if missing:
            st.sidebar.error(f"Missing upload(s): {', '.join(missing)}")
        else:
            tmp = Path(tempfile.mkdtemp(prefix="recon_"))
            paths = {}
            for key, up in uploaded.items():
                fp = tmp / up.name
                fp.write_bytes(up.getvalue())
                paths[key] = fp
            with st.spinner("Running reconciliation..."):
                try:
                    result = run_reconciliation(paths["Salary"], paths["TDS"],
                                                paths["Bank"], paths["EPF"],
                                                out_dir=tmp, month_label=month_label)
                    report_bytes = Path(result["report_path"]).read_bytes()
                    report_name = Path(result["report_path"]).name
                    sheets = load_report_from_bytes(report_bytes)
                    run_summary = {"counts": result["counts"], "summary": result["summary"]}
                    st.session_state.update(report_bytes=report_bytes, report_name=report_name,
                                            sheets=sheets, run_summary=run_summary)
                    st.sidebar.success(f"Report ready: {report_name}")
                except Exception as e:
                    st.sidebar.error(f"Reconciliation failed: {e}")

    if sheets is None and "sheets" in st.session_state:
        sheets = st.session_state["sheets"]
        report_bytes = st.session_state.get("report_bytes")
        report_name = st.session_state.get("report_name")
        run_summary = st.session_state.get("run_summary")

    if sheets is None and latest_report is not None:
        if st.sidebar.checkbox("Auto-load latest report from reports/", value=True):
            sheets = load_report_from_path(latest_report)
            report_bytes = latest_report.read_bytes()
            report_name = latest_report.name
            st.sidebar.success(f"Auto-loaded: {latest_report.name}")
else:
    uploaded_report = st.sidebar.file_uploader("Upload Salary_Reconciliation_*.xlsx",
                                               type=["xlsx"], key="u_report")
    if uploaded_report is not None:
        sheets = load_report_from_bytes(uploaded_report.getvalue())
        report_bytes = uploaded_report.getvalue()
        report_name = uploaded_report.name
        st.sidebar.success("Report loaded")

st.sidebar.markdown("---")
st.sidebar.subheader("Automation status")
st.sidebar.write("Selenium RMS download: **local only** (needs Chrome)")

st.title("Salary Reconciliation Dashboard")
st.caption("Upload the raw files to reconcile, or open an existing "
           "Salary_Reconciliation_*.xlsx report.")

if run_summary:
    with st.expander("Run details", expanded=False):
        c = run_summary["counts"]
        st.write(f"Salary: **{c['salary_rows']}** | TDS: **{c['tds_rows']}** | "
                 f"Bank: **{c['bank_rows']}** | EPF: **{c['epf_rows']}** | "
                 f"Reconciled: **{c['reconciled_rows']}**")

if report_bytes is not None and report_name:
    st.download_button("Download generated Excel report", data=report_bytes,
                       file_name=report_name,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if sheets is None:
    st.info("Upload the 4 raw files in the sidebar and press **Run Reconciliation**, "
            "or switch to **View an existing report**.")
    st.stop()

summary_df = sheets.get("Summary")
full_df = sheets.get("Full Reconciliation")
disc_df = sheets.get("Discrepancies")
branch_df = sheets.get("Branch Wise")
dept_df = sheets.get("Department Wise")
desig_df = sheets.get("Designation Wise")

summary_row = {} if summary_df is None or summary_df.empty else summary_df.iloc[0].to_dict()

if full_df is None:
    st.error("Full Reconciliation sheet not found in this file.")
    st.stop()

st.subheader("KPI Summary")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Employees", safe_int(summary_row.get("Total Employees", len(full_df))))
c2.metric("Fully Matched", safe_int(summary_row.get("Fully Matched", 0)))
c3.metric("TDS Mismatches", safe_int(summary_row.get("TDS Mismatches", 0)))
c4.metric("Bank Mismatches", safe_int(summary_row.get("Bank Mismatches", 0)))
c5.metric("EPF Mismatches", safe_int(summary_row.get("EPF Mismatches", 0)))

st.subheader("Financial Summary")
f1, f2, f3, f4, f5 = st.columns(5)
f1.metric("Total Gross Salary", fmt_inr(summary_row.get("Total Gross Salary", 0)))
f2.metric("Total Net Payable", fmt_inr(summary_row.get("Total Net Payable", 0)))
f3.metric("Total Bank Payment", fmt_inr(summary_row.get("Total Bank Payment", 0)))
f4.metric("Total TDS", fmt_inr(summary_row.get("Total TDS", 0)))
f5.metric("Total EPF", fmt_inr(summary_row.get("Total EPF", 0)))

st.divider()
tabs = st.tabs(SHEET_ORDER)

with tabs[0]:
    st.subheader("Branch Wise"); show_table(branch_df, "Branch Wise")
with tabs[1]:
    st.subheader("Department Wise"); show_table(dept_df, "Department Wise")
with tabs[2]:
    st.subheader("Designation Wise"); show_table(desig_df, "Designation Wise")
with tabs[3]:
    st.subheader("Discrepancies (filters + export)")
    if disc_df is None:
        st.warning("Discrepancies sheet missing")
    else:
        d = clean_for_display(disc_df)
        k1, k2, k3 = st.columns(3)
        with k1:
            branches = ["All"] + sorted(d["Branch"].dropna().astype(str).unique().tolist()) \
                if "Branch" in d.columns else ["All"]
            f_branch = st.selectbox("Branch", branches)
        with k2:
            depts = ["All"] + sorted(d["Department"].dropna().astype(str).unique().tolist()) \
                if "Department" in d.columns else ["All"]
            f_dept = st.selectbox("Department", depts)
        with k3:
            f_emp = st.text_input("EmpCode contains")
        if f_branch != "All" and "Branch" in d.columns:
            d = d[d["Branch"].astype(str) == f_branch]
        if f_dept != "All" and "Department" in d.columns:
            d = d[d["Department"].astype(str) == f_dept]
        if f_emp and "EmpCode" in d.columns:
            d = d[d["EmpCode"].astype(str).str.contains(f_emp, na=False)]
        st.caption(f"{len(d)} row(s)")
        st.dataframe(d, width="stretch", height=500)
        st.download_button("Download Discrepancies CSV",
                           data=d.to_csv(index=False).encode("utf-8"),
                           file_name="discrepancies.csv", mime="text/csv")
with tabs[4]:
    st.subheader("Full Reconciliation (search)")
    f = clean_for_display(full_df)
    q1, q2 = st.columns(2)
    with q1:
        emp = st.text_input("Filter EmpCode contains", key="fr_emp")
    with q2:
        name = st.text_input("Filter EmployeeName contains", key="fr_name")
    if emp and "EmpCode" in f.columns:
        f = f[f["EmpCode"].astype(str).str.contains(emp, na=False)]
    if name and "EmployeeName" in f.columns:
        f = f[f["EmployeeName"].astype(str).str.contains(name, case=False, na=False)]
    st.caption(f"{len(f)} row(s)")
    st.dataframe(f, width="stretch", height=600)
