# Quick Start Guide

**Project Location:** `~/Downloads/Agent/Reconciliation`

## 🚀 Get Started in 5 Minutes

### Step 1: Extract to Correct Location
```bash
cd ~/Downloads
mkdir -p Agent
cd Agent
unzip /path/to/salary_reconciliation_agent.zip
mv salary_reconciliation_agent Reconciliation
cd Reconciliation
```

Your path should now be: **`~/Downloads/Agent/Reconciliation`**

### Step 2: Install Dependencies
```bash
cd ~/Downloads/Agent/Reconciliation
pip install -r requirements.txt
```

### Step 3: Verify Your Credentials
Your `.env` file already exists! Just verify it has all values filled in:

```bash
cat .env
```

It should look like this (with your actual values):
```ini
# Email Configuration
SENDER_EMAIL=your_email@company.com
SENDER_PASSWORD=your_email_password
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
RECIPIENT_EMAILS=recipient1@company.com,recipient2@company.com
TAX_TEAM_EMAIL=tax@company.com

# RMS Portal Credentials
RMS_USERNAME=your_rms_username
RMS_PASSWORD=your_rms_password
```

**Important:** Make sure ALL fields are filled in!

### Step 4: Test the Agent
```bash
cd ~/Downloads/Agent/Reconciliation
python3 test_agent.py
```

This will:
- ✓ Verify your configuration
- ✓ Check directories
- ✓ Test date logic
- ✓ Optionally send test emails

### Step 5: Deploy as Service (Production)
```bash
cd ~/Downloads/Agent/Reconciliation
sudo bash install_service.sh
sudo systemctl start salary-reconciliation-agent
sudo systemctl enable salary-reconciliation-agent
```

**OR** Run manually (keep terminal open):
```bash
cd ~/Downloads/Agent/Reconciliation
python3 scheduler.py
```

## 📅 What Happens Automatically

### Every 16th of Month (Morning)
- Sends email reminder to Tax Team
- Subject: "⚠️ Reminder: Upload EPF File for [Month]"
- Reminds to upload EPF file to `~/Downloads/Agent/Reconciliation/epf_uploads/`

### Every 17th of Month
- Logs into RMS portal
- Downloads:
  - Salary Sheet (Auto TDS panel)
  - TDS Sheet (Update TDS panel)  
  - Bank SOA (Bank Book Entry)
- Reads EPF file from `~/Downloads/Agent/Reconciliation/epf_uploads/`
- Performs complete reconciliation
- Generates Excel report with 6 sheets
- Sends HTML email with:
  - Executive summary
  - Discrepancy breakdown
  - Financial summary
  - Attached Excel report

## 📊 Report Contents

The generated Excel file contains:

1. **Summary Sheet**: Overall statistics
2. **Full Reconciliation**: All employee data
3. **Discrepancies Only**: Filtered view of mismatches
4. **Branch Wise**: Delhi (consolidated), Gurgaon, Goa, etc.
5. **Designation Wise**: Manager, Senior Engineer, etc.
6. **Department Wise**: IT, Sales, Finance, etc.

## 🔍 Important Notes

### EPF File Requirements
- **Location**: `~/Downloads/Agent/Reconciliation/epf_uploads/`
- **Format**: Excel (.xlsx or .xls)
- **Columns Required**:
  - Employee Code/ID
  - UAN Number  
  - EPF Amount
- **Upload Before**: 17th of each month

### Date Logic (Automatic)
The agent automatically calculates which months to process:

**If today is 1st to 15th:**
- Salary/TDS/EPF: 2 months back
- Bank SOA: 1 month back
- Example (Jan 11th): Nov salary, Dec bank

**If today is 16th to 31st:**
- Salary/TDS/EPF: 1 month back
- Bank SOA: Current month
- Example (Jan 17th): Dec salary, Jan bank

### Branch Mapping (Automatic)
- Gurgaon → Gurgaon
- Goa → Goa
- Chennai → Chennai
- Dehradun → Dehradun
- Bangalore/Bengaluru → Bangalore
- **All others including Delhi → Delhi**

## 🛠️ Troubleshooting

### "Login failed"
```bash
# Check credentials
cat ~/Downloads/Agent/Reconciliation/.env
```
→ Verify RMS_USERNAME and RMS_PASSWORD

### "EPF file not found"
```bash
# Upload EPF file
cp /path/to/epf.xlsx ~/Downloads/Agent/Reconciliation/epf_uploads/
```

### "Email not sent"
→ Verify SENDER_EMAIL and SENDER_PASSWORD in .env
→ Check SMTP settings

### "Permission denied"
```bash
cd ~/Downloads/Agent/Reconciliation
chmod 600 .env
chmod 755 downloads epf_uploads reports logs
```

### View Logs
```bash
# View application logs
tail -f ~/Downloads/Agent/Reconciliation/logs/*.log

# OR if running as service
sudo journalctl -u salary-reconciliation-agent -f
```

## 📞 Support Commands

```bash
# Go to project directory
cd ~/Downloads/Agent/Reconciliation

# Check service status
sudo systemctl status salary-reconciliation-agent

# Restart service
sudo systemctl restart salary-reconciliation-agent

# Stop service
sudo systemctl stop salary-reconciliation-agent

# View logs
tail -f logs/*.log

# Test manually (stop service first)
sudo systemctl stop salary-reconciliation-agent
python3 test_agent.py
```

## ✅ Checklist Before Going Live

- [ ] Project extracted to `~/Downloads/Agent/Reconciliation`
- [ ] All credentials filled in `.env` file
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Test run completed successfully (`python test_agent.py`)
- [ ] EPF upload directory created (`epf_uploads/`)
- [ ] Service installed and running (or scheduler started)
- [ ] Test email received successfully
- [ ] Email recipients confirmed

## 🎯 Quick Reference

| Task | Command |
|------|---------|
| Go to project | `cd ~/Downloads/Agent/Reconciliation` |
| Test agent | `python test_agent.py` |
| Run manually | `python scheduler.py` |
| Install service | `sudo bash install_service.sh` |
| Start service | `sudo systemctl start salary-reconciliation-agent` |
| Check status | `sudo systemctl status salary-reconciliation-agent` |
| View logs | `tail -f logs/*.log` |
| Upload EPF | Copy to `epf_uploads/` directory |

---

**🎉 Your automated salary reconciliation system is ready!**

**Project Path:** `~/Downloads/Agent/Reconciliation`

---

**Need Help?** Check the full README.md for detailed documentation.
