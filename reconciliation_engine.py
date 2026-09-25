"""
Reconciliation Engine Module
Performs salary reconciliation and generates reports
"""

import pandas as pd
import logging
import numpy as np
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def _to_num(s):
    return pd.to_numeric(s, errors="coerce")


def _is_empty_amount(x: pd.Series) -> pd.Series:
    # empty means NaN or 0
    return x.isna() | (x.fillna(0) == 0)


class ReconciliationEngine:
    def __init__(self, salary_data, tds_data, bank_data, epf_data):
        self.salary_data = salary_data
        self.tds_data = tds_data
        self.bank_data = bank_data
        self.epf_data = epf_data
        self.reconciled_data = None

    def reconcile(self):
        """
        Main reconciliation logic
        Merges all data sources and identifies discrepancies
        """
        try:
            logger.info("Starting reconciliation process")

            reconciled = self.salary_data.copy()

            # Merge TDS data
            reconciled = reconciled.merge(
                self.tds_data[["EmpCode", "TDS_Amount"]],
                on="EmpCode",
                how="left",
                suffixes=("", "_TDS"),
            )

            # Merge Bank data
            reconciled = reconciled.merge(
                self.bank_data[["EmpCode", "BankPayment", "PaymentDate", "TransactionID"]],
                on="EmpCode",
                how="left",
                suffixes=("", "_Bank"),
            )

            # Merge EPF data by UAN.
            # Both sides are normalised to plain digit strings first: the salary
            # sheet usually carries UAN as an integer while the ECR file carries it
            # as text, and merging int64 against object either raises or silently
            # matches nothing at all.
            def _norm_uan(s):
                s = s.astype(str).str.strip().str.replace(r"\.0+$", "", regex=True)
                sci = s.str.contains(r"[eE][+-]?\d+$", regex=True, na=False)
                if sci.any():
                    s = s.copy()
                    nums = pd.to_numeric(s[sci], errors="coerce")
                    s.loc[sci] = nums.apply(
                        lambda v: "" if pd.isna(v) else str(int(round(v)))
                    )
                return s.str.replace(r"[^\d]", "", regex=True)

            epf_side = self.epf_data.copy()
            if "UAN" in reconciled.columns:
                reconciled["UAN"] = _norm_uan(reconciled["UAN"])
            if "UAN" in epf_side.columns:
                epf_side["UAN"] = _norm_uan(epf_side["UAN"])

            reconciled = reconciled.merge(
                epf_side[["UAN", "EPF_Amount"]],
                on="UAN",
                how="left",
                suffixes=("", "_EPF"),
            )

            # ---- Normalize numeric fields (avoid NaN arithmetic issues) ----
            tds = _to_num(reconciled.get("TDS"))
            tds_amt = _to_num(reconciled.get("TDS_Amount"))

            net = _to_num(reconciled.get("FinalNetPayable"))
            bank = _to_num(reconciled.get("BankPayment"))

            epf = _to_num(reconciled.get("EPF"))
            epf_amt = _to_num(reconciled.get("EPF_Amount"))

            reconciled["TDS"] = tds
            reconciled["TDS_Amount"] = tds_amt
            reconciled["FinalNetPayable"] = net
            reconciled["BankPayment"] = bank
            reconciled["EPF"] = epf
            reconciled["EPF_Amount"] = epf_amt

            tol = 1  # tolerance (₹1)

            # ---- TDS Match Fix: treat (0/NaN) vs (0/NaN) as MATCH ----
            tds_empty = _is_empty_amount(tds)
            tds_amt_empty = _is_empty_amount(tds_amt)

            reconciled["TDS_Difference"] = (tds - tds_amt)
            reconciled.loc[tds_empty & tds_amt_empty, "TDS_Difference"] = 0

            reconciled["TDS_Match"] = np.where(
                tds_empty & tds_amt_empty,
                "Matched",
                np.where((tds - tds_amt).abs() <= tol, "Matched", "Mismatch"),
            )

            # ---- Bank Match ----
            net_empty = _is_empty_amount(net)
            bank_empty = _is_empty_amount(bank)

            reconciled["Bank_Difference"] = (net - bank)
            reconciled.loc[net_empty & bank_empty, "Bank_Difference"] = 0

            reconciled["Bank_Match"] = np.where(
                net_empty & bank_empty,
                "Matched",
                np.where((net - bank).abs() <= tol, "Matched", "Mismatch"),
            )

            # ---- EPF Match ----
            epf_empty = _is_empty_amount(epf)
            epf_amt_empty = _is_empty_amount(epf_amt)

            reconciled["EPF_Difference"] = (epf - epf_amt)
            reconciled.loc[epf_empty & epf_amt_empty, "EPF_Difference"] = 0

            reconciled["EPF_Match"] = np.where(
                epf_empty & epf_amt_empty,
                "Matched",
                np.where((epf - epf_amt).abs() <= tol, "Matched", "Mismatch"),
            )

            # ---- Rule: do not consider employee mismatch if no amounts in any cell ----
            no_data = (
                _is_empty_amount(net)
                & _is_empty_amount(bank)
                & _is_empty_amount(tds)
                & _is_empty_amount(tds_amt)
                & _is_empty_amount(epf)
                & _is_empty_amount(epf_amt)
            )

            reconciled.loc[no_data, "TDS_Match"] = "Matched"
            reconciled.loc[no_data, "Bank_Match"] = "Matched"
            reconciled.loc[no_data, "EPF_Match"] = "Matched"
            reconciled.loc[no_data, "TDS_Difference"] = 0
            reconciled.loc[no_data, "Bank_Difference"] = 0
            reconciled.loc[no_data, "EPF_Difference"] = 0

            # ---- Overall Status ----
            reconciled["Overall_Status"] = np.where(
                no_data,
                "No Data",
                np.where(
                    (reconciled["TDS_Match"] == "Matched")
                    & (reconciled["Bank_Match"] == "Matched")
                    & (reconciled["EPF_Match"] == "Matched"),
                    "Fully Matched",
                    "Has Discrepancies",
                ),
            )

            # ---- Remarks ----
            reconciled["Remarks"] = reconciled.apply(self._generate_remarks, axis=1)

            self.reconciled_data = reconciled

            total_records = len(reconciled)
            matched_records = len(reconciled[reconciled["Overall_Status"] == "Fully Matched"])
            discrepancy_records = len(reconciled[reconciled["Overall_Status"] == "Has Discrepancies"])
            no_data_records = len(reconciled[reconciled["Overall_Status"] == "No Data"])

            logger.info(f"Reconciliation complete: {total_records} total records")
            logger.info(
                f"Matched: {matched_records}, Discrepancies: {discrepancy_records}, No Data: {no_data_records}"
            )

            return reconciled

        except Exception as e:
            logger.error(f"Error during reconciliation: {str(e)}", exc_info=True)
            raise

    def _append_grand_total_row(self, report_df, label_col_name):
        total_row = {
            label_col_name: "Grand Total",
            "Employee Count": report_df["Employee Count"].sum(),
            "Fully Matched": report_df["Fully Matched"].sum(),
            "Has Discrepancies": report_df["Has Discrepancies"].sum(),
            "No Data": report_df["No Data"].sum(),
            "Total Gross Salary": report_df["Total Gross Salary"].sum(),
            "Total Net Payable": report_df["Total Net Payable"].sum(),
            "Total Bank Payment": report_df["Total Bank Payment"].sum(),
            "Total TDS": report_df["Total TDS"].sum(),
            "Total EPF": report_df["Total EPF"].sum(),
        }
        return pd.concat([report_df, pd.DataFrame([total_row])], ignore_index=True)

    def _generate_remarks(self, row):
        """Generate remarks for discrepancies (avoid nan text)"""
        if row.get("Overall_Status") == "No Data":
            return "No amounts present (ignored)"

        remarks = []

        if row.get("TDS_Match") == "Mismatch":
            diff = row.get("TDS_Difference")
            if pd.notna(diff):
                remarks.append(f"TDS Diff: {diff:.2f}")

        if row.get("Bank_Match") == "Mismatch":
            if pd.isna(row.get("BankPayment")):
                remarks.append("Bank payment not found")
            else:
                diff = row.get("Bank_Difference")
                if pd.notna(diff):
                    remarks.append(f"Bank Diff: {diff:.2f}")

        if row.get("EPF_Match") == "Mismatch":
            if pd.isna(row.get("EPF_Amount")):
                remarks.append("EPF not found")
            else:
                diff = row.get("EPF_Difference")
                if pd.notna(diff):
                    remarks.append(f"EPF Diff: {diff:.2f}")

        return "; ".join(remarks) if remarks else "All matched"

    def generate_summary_report(self):
        """Generate overall summary statistics"""
        if self.reconciled_data is None:
            raise ValueError("Reconciliation must be run before generating reports")

        summary = {
            "Total Employees": len(self.reconciled_data),
            "Fully Matched": len(self.reconciled_data[self.reconciled_data["Overall_Status"] == "Fully Matched"]),
            "Has Discrepancies": len(self.reconciled_data[self.reconciled_data["Overall_Status"] == "Has Discrepancies"]),
            "No Data": len(self.reconciled_data[self.reconciled_data["Overall_Status"] == "No Data"]),
            "TDS Mismatches": len(self.reconciled_data[self.reconciled_data["TDS_Match"] == "Mismatch"]),
            "Bank Mismatches": len(self.reconciled_data[self.reconciled_data["Bank_Match"] == "Mismatch"]),
            "EPF Mismatches": len(self.reconciled_data[self.reconciled_data["EPF_Match"] == "Mismatch"]),
            "Total Gross Salary": _to_num(self.reconciled_data.get("GrossSalary")).fillna(0).sum(),
            "Total Net Payable": _to_num(self.reconciled_data.get("FinalNetPayable")).fillna(0).sum(),
            "Total Bank Payment": _to_num(self.reconciled_data.get("BankPayment")).fillna(0).sum(),
            "Total TDS": _to_num(self.reconciled_data.get("TDS")).fillna(0).sum(),
            "Total EPF": _to_num(self.reconciled_data.get("EPF")).fillna(0).sum(),
        }

        return pd.DataFrame([summary])

    def _group_summary(self, group_col: str):
        """
        Common summary for Branch / Designation / Department.
        Includes counts and financial totals.
        """
        if self.reconciled_data is None:
            raise ValueError("Reconciliation must be run before generating reports")

        df = self.reconciled_data.copy()

        report = df.groupby(group_col).agg(
            **{
                "Employee Count": ("EmpCode", "count"),
                "Fully Matched": ("Overall_Status", lambda x: (x == "Fully Matched").sum()),
                "Has Discrepancies": ("Overall_Status", lambda x: (x == "Has Discrepancies").sum()),
                "No Data": ("Overall_Status", lambda x: (x == "No Data").sum()),
                "Total Gross Salary": ("GrossSalary", "sum"),
                "Total Net Payable": ("FinalNetPayable", "sum"),
                "Total Bank Payment": ("BankPayment", "sum"),
                "Total TDS": ("TDS", "sum"),
                "Total EPF": ("EPF", "sum"),
            }
        ).reset_index()

        # Append grand total
        report = self._append_grand_total_row(report, group_col)
        return report

    def generate_branch_wise_report(self):
        return self._group_summary("Branch")

    def generate_designation_wise_report(self):
        return self._group_summary("Designation")

    def generate_department_wise_report(self):
        return self._group_summary("Department")

    def get_discrepancies_only(self):
        """Get only records with discrepancies (excludes No Data automatically)"""
        if self.reconciled_data is None:
            raise ValueError("Reconciliation must be run before generating reports")

        return self.reconciled_data[self.reconciled_data["Overall_Status"] == "Has Discrepancies"]

    def save_reports(self, output_file):
        """Save all reports to a single Excel file with multiple sheets + strong styling"""
        try:
           logger.info(f"Saving reports to: {output_file}")

           from openpyxl.styles import PatternFill, Font, Alignment
           from openpyxl.utils import get_column_letter

           with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
               # --- Write sheets ---
               self.generate_summary_report().to_excel(writer, sheet_name="Summary", index=False, startrow=1)
               self.reconciled_data.to_excel(writer, sheet_name="Full Reconciliation", index=False, startrow=1)
               self.get_discrepancies_only().to_excel(writer, sheet_name="Discrepancies", index=False, startrow=1)
               self.generate_branch_wise_report().to_excel(writer, sheet_name="Branch Wise", index=False, startrow=1)
               self.generate_designation_wise_report().to_excel(writer, sheet_name="Designation Wise", index=False, startrow=1)
               self.generate_department_wise_report().to_excel(writer, sheet_name="Department Wise", index=False, startrow=1)

               wb = writer.book

               # Sheet theme colors
               THEME = {
                   "Summary": ("2E7D32", "SUMMARY"),
                   "Full Reconciliation": ("1565C0", "FULL RECONCILIATION"),
                   "Discrepancies": ("C62828", "DISCREPANCIES"),
                   "Branch Wise": ("00897B", "BRANCH WISE SUMMARY"),
                   "Designation Wise": ("6A1B9A", "DESIGNATION WISE SUMMARY"),
                   "Department Wise": ("EF6C00", "DEPARTMENT WISE SUMMARY"),
               }

               title_font = Font(bold=True, color="FFFFFF", size=14)
               header_font = Font(bold=True, color="FFFFFF")
               center = Alignment(horizontal="center", vertical="center", wrap_text=True)

               grand_fill = PatternFill("solid", fgColor="FFF9C4")
               grand_font = Font(bold=True, color="000000")

               for sheet_name, (hex_color, title_text) in THEME.items():
                   if sheet_name not in wb.sheetnames:
                       continue

                   ws = wb[sheet_name]

                   # Tab color (Excel only)
                   ws.sheet_properties.tabColor = hex_color

                   # Row 1 = big title bar (strong visible)
                   ws.insert_rows(1)
                   ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ws.max_column)
                   title_cell = ws.cell(row=1, column=1)
                   title_cell.value = title_text
                   title_cell.fill = PatternFill("solid", fgColor=hex_color)
                   title_cell.font = title_font
                   title_cell.alignment = center
                   ws.row_dimensions[1].height = 26

                   # Row 2 = column headers (because we wrote startrow=1 and then inserted a row)
                   header_fill = PatternFill("solid", fgColor=hex_color)
                   for cell in ws[2]:
                       cell.fill = header_fill
                       cell.font = header_font
                       cell.alignment = center
                   ws.row_dimensions[2].height = 18

                   # Freeze below headers
                   ws.freeze_panes = "A3"

                   # Auto width
                   for col in range(1, ws.max_column + 1):
                       col_letter = get_column_letter(col)
                       max_len = 0
                       for r in range(1, min(ws.max_row, 200) + 1):
                           v = ws.cell(row=r, column=col).value
                           if v is None:
                               continue
                           max_len = max(max_len, len(str(v)))
                       ws.column_dimensions[col_letter].width = min(max(10, max_len + 2), 50)

                   # Highlight "Grand Total" row (assumes label is in col 1)
                   for r in range(3, ws.max_row + 1):
                       v = ws.cell(row=r, column=1).value
                       if isinstance(v, str) and v.strip().lower() == "grand total":
                           for c in range(1, ws.max_column + 1):
                               ws.cell(row=r, column=c).fill = grand_fill
                               ws.cell(row=r, column=c).font = grand_font
                           break

           logger.info(f"Reports saved successfully to {output_file}")
           return True

        except Exception as e:
            logger.error(f"Error saving reports: {str(e)}", exc_info=True)
            return False
