"""
Email Module
Handles sending reminder and report emails
"""

import smtplib
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
from pathlib import Path
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


class EmailHandler:

    def __init__(self):
        self.sender_email = Config.SENDER_EMAIL
        self.sender_password = Config.SENDER_PASSWORD
        self.smtp_server = Config.SMTP_SERVER
        self.smtp_port = Config.SMTP_PORT

    def send_email(self, recipients, subject, body, attachments=None, is_html=False):
        """Send email with optional attachments"""
        try:
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = subject

            msg.attach(MIMEText(body, "html" if is_html else "plain"))

            if attachments:
                for file_path in attachments:
                    if Path(file_path).exists():
                        with open(file_path, "rb") as f:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                "Content-Disposition",
                                f"attachment; filename={Path(file_path).name}",
                            )
                            msg.attach(part)
                        logger.info(f"Attached file: {file_path}")
                    else:
                        logger.warning(f"Attachment not found: {file_path}")

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {', '.join(recipients)}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}", exc_info=True)
            return False

    def _sanitize_table_for_management(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Management email requirement:
        remove 'Has Discrepancies' column (if present) from embedded tables.
        """
        if df is None or df.empty:
            return df

        # normalize column names for matching
        cols_lower = {c: str(c).strip().lower() for c in df.columns}

        drop_cols = []
        for c, cl in cols_lower.items():
            if cl == "has discrepancies" or cl == "has_discrepancies":
                drop_cols.append(c)

        if drop_cols:
            df = df.drop(columns=drop_cols, errors="ignore")

        return df

    def _df_to_html_table(self, df, title, max_rows=25):
        """
        Convert a DataFrame to a clean HTML table for email.
        Shows at most max_rows rows, but always keeps Grand Total row if present.
        """
        if df is None or df.empty:
            return f"<h3>{title}</h3><p>No data available.</p>"

        # remove unwanted columns for management email
        df = self._sanitize_table_for_management(df)

        first_col = df.columns[0]
        is_grand = df[first_col].astype(str).str.strip().str.lower().eq("grand total")
        grand = df[is_grand]
        non_grand = df[~is_grand]

        if len(non_grand) > max_rows:
            non_grand = non_grand.head(max_rows)

        df_show = pd.concat([non_grand, grand], ignore_index=True) if not grand.empty else non_grand

        html = df_show.to_html(index=False, border=0)
        return f"""
            <h3 style="margin-top:18px;">{title}</h3>
            <div style="overflow-x:auto; border:1px solid #e5e5e5; padding:8px; border-radius:6px;">
                {html}
            </div>
        """

    def send_epf_reminder(self):
        """
        EPF upload reminder - sent automatically on the 14th, two days before the run.

        The period is taken from the run that will fire on the 16th (get_run_months),
        not from today's date, so the reminder always names exactly the same month as
        the report that follows it.
        """
        epf_month = Config.get_run_months()["salary_month_str"]

        subject = f"Reminder: upload the EPF file for {epf_month} by the 16th"

        body = f"""Dear Team,

This is an automated reminder that the EPF file for {epf_month} is due by the 16th.

The monthly reconciliation runs automatically on the evening of the 16th. The
salary sheet, the TDS sheet and the bank statement are downloaded from the RMS
portal on their own, so the EPF file is the only input that has to be placed by
hand - and the run cannot be completed without it.

Please upload the EPF file for {epf_month} to:

{Config.EPF_UPLOAD_DIR}

If the file is not there when the run fires, the report is held back and an alert
is sent instead; the run then retries by itself as soon as the file appears.

Thank you.
Salary Reconciliation Agent
"""
        recipients = [Config.TAX_TEAM_EMAIL] if Config.TAX_TEAM_EMAIL else Config.RECIPIENT_EMAILS
        return self.send_email(recipients=recipients, subject=subject, body=body, is_html=False)

    def send_epf_missing_alert(self, salary_month=None, epf_dir=None):
        """
        Alert sent when the monthly run fired but no EPF file had been uploaded.

        The report is deliberately withheld: a reconciliation without EPF marks every
        employee as "EPF not reconciled", which reads as a data problem rather than a
        missing input. An explicit alert is more useful than a misleading report.
        """
        salary_month = salary_month or Config.get_target_months()["salary_month_str"]
        epf_dir = epf_dir or Config.EPF_UPLOAD_DIR

        subject = f"ACTION NEEDED: EPF file missing - {salary_month} reconciliation on hold"

        body = f"""Dear Team,

The automated salary reconciliation ran but could NOT be completed, because no
EPF file was found for {salary_month}.

No report has been sent. A reconciliation without the EPF file would mark every
employee as "EPF not reconciled", which would be misleading.

What to do
----------
1. Place the EPF file for {salary_month} in:

   {epf_dir}

2. Nothing else is needed. The run retries by itself (every few hours) and emails
   the full report as soon as the file is in place.

The salary sheet, TDS sheet and bank statement were downloaded from RMS
successfully and are waiting in:

   {Config.DOWNLOAD_DIR}

Thank you.
Salary Reconciliation Agent
"""
        recipients = [Config.TAX_TEAM_EMAIL] if Config.TAX_TEAM_EMAIL else Config.RECIPIENT_EMAILS
        return self.send_email(recipients=recipients, subject=subject, body=body, is_html=False)

    def send_reconciliation_report(self, report_file, summary_data):
        """Send reconciliation report after completion (management format)"""
        target_months = Config.get_target_months()
        salary_month = target_months["salary_month_str"]
        bank_month = target_months["bank_month_str"]

        subject = f"Salary Reconciliation Report - {salary_month}"

        # -------- Build detailed tables HTML from Excel report --------
        try:
            branch_df = pd.read_excel(report_file, sheet_name="Branch Wise")
            dept_df = pd.read_excel(report_file, sheet_name="Department Wise")
            desig_df = pd.read_excel(report_file, sheet_name="Designation Wise")

            extra_tables_html = (
                '<div class="summary-box">'
                "<h2>Detailed Summary</h2>"
                + self._df_to_html_table(branch_df, "Branch Wise Summary", max_rows=50)
                + self._df_to_html_table(dept_df, "Department Wise Summary", max_rows=50)
                + self._df_to_html_table(desig_df, "Designation Wise Summary", max_rows=25)
                + "</div>"
            )
            logger.info(f"Email tables added. Length={len(extra_tables_html)}")

        except Exception as e:
            logger.warning(f"Could not load summary sheets from report for email HTML: {e}", exc_info=True)
            extra_tables_html = (
                "<div class='summary-box'>"
                "<h2>Detailed Summary</h2>"
                "<p><i>Detailed tables could not be loaded into the email. Please refer to the attached Excel report.</i></p>"
                "</div>"
            )

        body_html = f"""
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .header {{
            background-color: #4CAF50;
            color: white;
            padding: 20px;
            text-align: center;
        }}
        .content {{
            padding: 20px;
        }}
        .summary-box {{
            background-color: #f4f4f4;
            border-left: 4px solid #4CAF50;
            padding: 15px;
            margin: 20px 0;
        }}
        .status-good {{
            color: #4CAF50;
            font-weight: bold;
        }}
        .status-error {{
            color: #f44336;
            font-weight: bold;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 10px 0;
            font-size: 13px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Salary Reconciliation Report</h1>
        <p>Period: {salary_month} (Salary) | {bank_month} (Bank)</p>
        <p>Generated on: {datetime.now().strftime('%d %B %Y at %I:%M %p')}</p>
    </div>

    <div class="content">

        <div class="summary-box">
            <h2>Executive Summary</h2>
            <table>
                <tr><td><strong>Total Employees</strong></td><td>{summary_data.get('Total Employees', 0)}</td></tr>
                <tr class="status-good"><td><strong>Fully Matched</strong></td><td>{summary_data.get('Fully Matched', 0)}</td></tr>
            </table>
        </div>

        <div class="summary-box">
            <h2>Mismatch Summary</h2>
            <table>
                <tr><td><strong>TDS Mismatches</strong></td><td class="{('status-error' if summary_data.get('TDS Mismatches', 0) > 0 else 'status-good')}">{summary_data.get('TDS Mismatches', 0)}</td></tr>
                <tr><td><strong>Bank Payment Mismatches</strong></td><td class="{('status-error' if summary_data.get('Bank Mismatches', 0) > 0 else 'status-good')}">{summary_data.get('Bank Mismatches', 0)}</td></tr>
                <tr><td><strong>EPF Mismatches</strong></td><td class="{('status-error' if summary_data.get('EPF Mismatches', 0) > 0 else 'status-good')}">{summary_data.get('EPF Mismatches', 0)}</td></tr>
            </table>
        </div>

        <div class="summary-box">
            <h2>Financial Summary</h2>
            <table>
                <tr><td><strong>Total Gross Salary</strong></td><td>₹ {summary_data.get('Total Gross Salary', 0):,.2f}</td></tr>
                <tr><td><strong>Total Net Payable</strong></td><td>₹ {summary_data.get('Total Net Payable', 0):,.2f}</td></tr>
                <tr><td><strong>Total Bank Payment</strong></td><td>₹ {summary_data.get('Total Bank Payment', 0):,.2f}</td></tr>
                <tr><td><strong>Total TDS</strong></td><td>₹ {summary_data.get('Total TDS', 0):,.2f}</td></tr>
                <tr><td><strong>Total EPF</strong></td><td>₹ {summary_data.get('Total EPF', 0):,.2f}</td></tr>
            </table>
        </div>

        {extra_tables_html}

        <div class="footer">
            <p>This is an automated email generated by the Salary Reconciliation Agent.</p>
        </div>

    </div>
</body>
</html>
"""

        return self.send_email(
            recipients=Config.RECIPIENT_EMAILS,
            subject=subject,
            body=body_html,
            attachments=[report_file],
            is_html=True,
        )

    def send_error_notification(self, error_message):
        """Send error notification if reconciliation fails"""
        subject = "Salary Reconciliation Failed"

        body = f"""
Dear Team,

The automated salary reconciliation process encountered an error and could not complete successfully.

Error Details:
{error_message}

Timestamp: {datetime.now().strftime('%d %B %Y at %I:%M %p')}

Best regards,
Salary Reconciliation Agent
"""

        return self.send_email(
            recipients=Config.RECIPIENT_EMAILS,
            subject=subject,
            body=body,
            is_html=False,
        )
