# Salary Reconciliation Agent

An automated agent that reconciles salary payments with bank statements, TDS, and EPF contributions on a monthly basis.

**Project Path:** `~/Downloads/Agent/Reconciliation`

## 🎯 Features

- **Automated File Downloads**: Automatically logs into RMS portal and downloads:
  - Salary Sheet from Auto TDS panel
  - TDS Sheet from Update TDS panel
  - Bank Statement of Account (SOA) from Bank Book Entry

- **Smart Date Logic**: 
  - If date ≤ 15th: Processes 2 months back data for salary/TDS/EPF, 1 month back for bank
  - If date > 15th: Processes 1 month back data for salary/TDS/EPF, current month for bank

- **Comprehensive Reconciliation**:
  - Matches Salary vs Bank payments by Employee ID
  - Matches TDS deductions by Employee ID
  - Matches EPF contributions by UAN number
  - Flags all discrepancies with detailed remarks

- **Multi-dimensional Reports**:
  - Overall summary statistics
  - Full reconciliation data
  - Discrepancies-only view
  - Branch-wise summary
  - Designation-wise summary
  - Department-wise summary

- **Branch Mapping**:
  - Automatically maps Gurgaon, Goa, Chennai, Dehradun, Bangalore
  - All other locations (including Delhi) → Delhi

- **Automated Email Notifications**:
  - Reminder on 16th morning to upload EPF file
  - Detailed HTML report email with reconciliation results on 17th
  - Error notifications if process fails

## 📋 Prerequisites

- Python 3.8 or higher
- Chrome browser installed
- ChromeDriver (automatically managed by webdriver-manager)
- Access to RMS portal
- Email account for sending notifications (Office 365)

## 🚀 Installation

### Step 1: Extract the Agent

Extract the ZIP file to your Downloads folder:
```bash
cd ~/Downloads
mkdir -p Agent
cd Agent
unzip /path/to/salary_reconciliation_agent.zip
cd Reconciliation
```

Your project structure should now be:
```
~/Downloads/Agent/Reconciliation/
```

### Step 2: Install Dependencies

```bash
cd ~/Downloads/Agent/Reconciliation
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
# The .env file should already exist with your credentials
# Verify it has all required values:
cat .env
```

Your `.env` file should contain:
```ini
# Email Configuration
SENDER_EMAIL=your_email@company.com
SENDER_PASSWORD=your_email_password
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
RECIPIENT_EMAILS=recipient1@company.com,recipient2@company.com
TAX_TEAM_EMAIL=tax_team@company.com

# RMS Portal Credentials
RMS_USERNAME=your_rms_username
RMS_PASSWORD=your_rms_password
```

**Important:** Make sure to fill in all values!

### Step 4: Create EPF Upload Directory

```bash
mkdir -p ~/Downloads/Agent/Reconciliation/epf_uploads
```

## 📁 Directory Structure

After installation, your directory structure will be:

```
~/Downloads/Agent/Reconciliation/
│
├── 📄 Core Files
│   ├── config.py                 # Configuration and settings
│   ├── main.py                   # Main orchestration logic
│   ├── scheduler.py              # Monthly scheduler
│   ├── rms_automation.py         # RMS portal automation
│   ├── data_processor.py         # Excel file processing
│   ├── reconciliation_engine.py  # Reconciliation logic
│   ├── email_handler.py          # Email sending functions
│   └── test_agent.py             # Manual testing script
│
├── ⚙️ Setup Files
│   ├── requirements.txt          # Python dependencies
│   ├── .env                      # Environment variables (YOUR CREDENTIALS)
│   └── install_service.sh        # Linux service installer
│
├── 📚 Documentation
│   ├── README.md                 # This file
│   ├── QUICKSTART.md             # Quick start guide
│   └── ARCHITECTURE.txt          # Visual architecture
│
└── 📁 Working Directories (auto-created when agent runs)
    ├── downloads/                # Downloaded files from RMS
    ├── epf_uploads/              # Manually uploaded EPF files
    ├── reports/                  # Generated reconciliation reports
    └── logs/                     # Application logs
```

## 🎮 Usage

### Option 1: Run with Scheduler (Recommended)

The scheduler automatically runs:
- **16th of every month**: Sends EPF upload reminder
- **17th of every month**: Runs full reconciliation

```bash
cd ~/Downloads/Agent/Reconciliation
python3 scheduler.py
```

Keep this running continuously (use `nohup` or `systemd` service for production).

### Option 2: Install as Linux Service (Production)

```bash
cd ~/Downloads/Agent/Reconciliation
sudo bash install_service.sh

# Start the service
sudo systemctl start salary-reconciliation-agent

# Enable auto-start on boot
sudo systemctl enable salary-reconciliation-agent

# Check status
sudo systemctl status salary-reconciliation-agent

# View logs
sudo journalctl -u salary-reconciliation-agent -f
```

### Option 3: Manual Execution

Run reconciliation manually:
```bash
cd ~/Downloads/Agent/Reconciliation
python3 main.py
```

### Option 4: Test Individual Components

```bash
cd ~/Downloads/Agent/Reconciliation
python3 test_agent.py
```

This will:
- ✓ Verify your configuration
- ✓ Check directories
- ✓ Test date logic
- ✓ Optionally send test emails

## 📊 EPF File Format

The EPF file should be uploaded manually to `~/Downloads/Agent/Reconciliation/epf_uploads/` before 17th.

**Expected columns** (names can vary, agent will auto-detect):
- Employee Code/ID
- UAN Number
- EPF Amount

**Supported formats**: .xlsx, .xls

Example:
```
Employee Code | UAN           | EPF Amount
3730          | 101234567890  | 1800
3566          | 101234567891  | 2100
```

## 📧 Email Reports

### EPF Reminder (16th)
- Plain text email
- Sent to TAX_TEAM_EMAIL
- Reminds to upload EPF file

### Reconciliation Report (17th)
- HTML formatted email with color-coded summary
- Attached Excel file with multiple sheets
- Sent to all RECIPIENT_EMAILS

**Excel Report Sheets**:
1. **Summary**: Overall statistics
2. **Full Reconciliation**: All employee records
3. **Discrepancies**: Only mismatched records
4. **Branch Wise**: Summary by branch
5. **Designation Wise**: Summary by designation
6. **Department Wise**: Summary by department

## 🔧 Troubleshooting

### Issue: Login fails
- Verify RMS_USERNAME and RMS_PASSWORD in .env
- Check if RMS portal is accessible
- Ensure Chrome and ChromeDriver are compatible

### Issue: Files not downloaded
- Check RMS portal element IDs haven't changed
- Verify download directory permissions: `~/Downloads/Agent/Reconciliation/downloads/`
- Check logs in `logs/` directory

### Issue: EPF file not found
- Ensure EPF file is uploaded to `~/Downloads/Agent/Reconciliation/epf_uploads/` directory
- Check file format (.xlsx or .xls)
- Verify file contains required columns

### Issue: Email not sent
- Verify SMTP settings (Office 365: smtp.office365.com:587)
- Check email credentials in .env
- Ensure sender email has SMTP access enabled

### Issue: Permission denied
```bash
# Fix permissions
cd ~/Downloads/Agent/Reconciliation
chmod 600 .env
chmod +x install_service.sh
chmod 755 downloads epf_uploads reports logs
```

### View Logs
```bash
# Application logs
tail -f ~/Downloads/Agent/Reconciliation/logs/*.log

# Service logs (if running as service)
sudo journalctl -u salary-reconciliation-agent -f
```

## 🔐 Security Considerations

1. **Never commit .env file** to version control
2. **Use application-specific passwords** for email accounts
3. **Restrict file permissions**:
   ```bash
   chmod 600 ~/Downloads/Agent/Reconciliation/.env
   ```
4. **Store credentials securely** in production
5. **Use encrypted connection** for RMS portal (HTTPS)

## 📝 Customization

### Change Salary Sheet Column Positions

Edit `data_processor.py` → `process_salary_sheet()`:
```python
'GrossSalary': pd.to_numeric(df.iloc[:, 13], errors='coerce'),  # Change 13 to your column index
```

### Modify Branch Mapping

Edit `config.py` → `BRANCH_MAPPING`:
```python
BRANCH_MAPPING = {
    "MUMBAI": "Mumbai",
    "PUNE": "Pune",
    # Add more branches
}
```

### Add More Reports

Edit `reconciliation_engine.py` and add new methods:
```python
def generate_custom_report(self):
    # Your custom report logic
    pass
```

## 🤝 Support

For issues or questions:
1. Check logs in `~/Downloads/Agent/Reconciliation/logs/` directory
2. Review error emails sent by the agent
3. Verify all prerequisites are met
4. Run `python test_agent.py` for diagnostics
5. Contact system administrator

## 📜 Project Paths Summary

- **Main Directory**: `~/Downloads/Agent/Reconciliation/`
- **Downloads**: `~/Downloads/Agent/Reconciliation/downloads/`
- **EPF Uploads**: `~/Downloads/Agent/Reconciliation/epf_uploads/`
- **Reports**: `~/Downloads/Agent/Reconciliation/reports/`
- **Logs**: `~/Downloads/Agent/Reconciliation/logs/`
- **Config**: `~/Downloads/Agent/Reconciliation/.env`

## 📜 License

Internal use only - Koenig Solutions

---

**Version**: 1.0.0  
**Last Updated**: January 2026  
**Maintained by**: IT Team  
**Project Location**: ~/Downloads/Agent/Reconciliation

---

## Monthly automation

The reconciliation runs by itself on the machine that can reach the RMS portal -
the salary sheet, TDS sheet and bank statement are downloaded automatically, and
the report is emailed:

| When | What |
|---|---|
| **14th** | EPF upload reminder emailed to the tax team |
| **16th** | Full run: RMS download + reconcile + report email |

The EPF file is the only manual input (RMS has no export for it), which is why the
reminder lands two days early. If it is missing on the 16th the report is held back
and an alert is sent instead; the run retries by itself until the file appears.

Install and operate it:

```bash
bash install_launchd.sh          # macOS: register the two launchd agents
python3 scheduler.py --status    # what is due, what already ran
```

Full details - schedule, catch-up, the per-month ledger that stops double sends,
and the Streamlit-versus-automation split - are in **[AUTOMATION.md](AUTOMATION.md)**.
