# Automation - what runs when, and how to install it

The reconciliation runs **by itself twice a month**, on the machine that can reach
the RMS portal. The Streamlit dashboard is a separate, read-only view - it cannot
schedule anything and cannot open a browser (see *Why not on Streamlit Cloud* below).

---

## The two events

| When | What | Job |
|---|---|---|
| **14th, 09:00** | EPF upload reminder emailed to the tax team | `run_epf_reminder.py` |
| **16th, ~18:00** | Salary + TDS + bank downloaded from RMS, reconciled against the EPF file, report emailed | `run_live.py` |

The reminder goes out two days early because of one asymmetry:

* **Salary sheet, TDS sheet, bank statement** - downloaded automatically from RMS.
  No human involved.
* **EPF file** - no RMS export exists. It has to be **uploaded by hand**, and it is
  the only manual input. Without it the run cannot be completed.

---

## What happens if the EPF file is missing on the 16th

The run does **not** send a report. A reconciliation without EPF marks every employee
as `EPF not reconciled`, which looks like a data defect rather than a missing input.

Instead:

1. The salary / TDS / bank files are still downloaded and left in `downloads/`.
2. An **alert email** goes to the tax team: *"EPF file missing - reconciliation on hold"*,
   naming the folder to drop the file into. This alert is sent **once per month**, not
   on every retry.
3. The run **retries automatically** (every 3 hours while the scheduler is running).
4. As soon as the EPF file appears in `epf_uploads/`, the retry completes and emails
   the full report.

To bypass the guard deliberately - for example to send a report with the EPF column
blank - run `python3 run_live.py --force-email` by hand.

---

## Installing on macOS (launchd)

```bash
cd ~/Downloads/Agent/Reconciliation
bash install_launchd.sh
```

That registers two launchd agents in `~/Library/LaunchAgents/`:

| Agent | Fires |
|---|---|
| `com.koenig.salary-recon.reminder` | day 14, 09:00 |
| `com.koenig.salary-recon.monthly` | day 16, 18:00 |

launchd runs a job that came due **while the Mac was asleep** as soon as it wakes,
so a closed lid at 18:00 does not lose the run.

Useful commands:

```bash
bash install_launchd.sh status     # are the agents loaded, and what is due next
bash install_launchd.sh test       # fire both jobs right now
bash install_launchd.sh logs       # tail both job logs
bash install_launchd.sh uninstall  # remove both agents
```

**One gap:** if the Mac is *powered off* (not merely asleep) for the whole of the
16th, launchd skips the day. Cover that by also running the catch-up loop:

```bash
python3 scheduler.py               # leave it running (tmux/screen, or a login item)
```

A missed 16th run is then executed at the next tick, as long as it is still the same
calendar month.

---

## Installing on Linux (systemd)

```bash
sudo bash install_service.sh
```

Installs `scheduler.py` as the `salary-reconciliation-agent` service:

```bash
sudo systemctl start   salary-reconciliation-agent
sudo systemctl enable  salary-reconciliation-agent   # start on boot
sudo journalctl -u salary-reconciliation-agent -f
```

---

## The scheduler

`scheduler.py` is the fallback trigger for both platforms. It is a plain
standard-library loop - no `schedule` package needed.

```bash
python3 scheduler.py                  # foreground loop, checks the clock every 5 min
python3 scheduler.py --once           # single check, then exit (drop-in for cron)
python3 scheduler.py --status         # schedule + ledger + what is due next
python3 scheduler.py --run-now recon  # force the full run now
python3 scheduler.py --run-now reminder
python3 scheduler.py --reset recon    # forget this month, so it can run again
```

Sample `--status` output:

```
  [recon] Monthly reconciliation
      schedule       : day 16 at 18:00
      this month     : 16 September 18:00  ->  pending
      next run       : 16 September 2026 18:00
      state now      : not due until 16 Sep 18:00
```

### Catch-up and retries

* A job whose scheduled minute has passed still runs at the next tick - same calendar
  month only. A run missed on the 16th therefore completes on the 17th, 18th, … 30th.
* A run that failed, or was held back for a missing EPF file, is retried every
  `RECON_RETRY_HOURS` hours until it succeeds.
* Disable catch-up with `RECON_CATCHUP=0` if you want strict date-only behaviour.

### Never sent twice

Every automated job is keyed by month in `logs/run_ledger.json`:

```json
{
  "reconciliation":    {"2026-09": {"done": true, "at": "2026-09-16T18:04:11", "note": "report emailed"}},
  "epf_reminder":      {"2026-09": {"done": true, "at": "2026-09-14T09:00:03", "note": "reminder emailed"}},
  "epf_missing_alert": {"2026-09": {"done": true, "at": "2026-09-16T18:04:09", "note": "alerted"}}
}
```

That is what lets launchd **and** `scheduler.py` both be installed without the tax
team receiving the same report twice.

**Manual runs ignore the ledger.** Only `--auto` (used by launchd, systemd and the
scheduler) skips a completed month. Running `python3 run_live.py` by hand always runs.

---

## Environment variables

Set these in `.env` (never committed):

| Key | Used for |
|---|---|
| `RECIPIENT_EMAILS` | who receives the reconciliation report |
| `TAX_TEAM_EMAIL` | who receives the reminder and the missing-EPF alert (falls back to `RECIPIENT_EMAILS`) |
| `SENDER_EMAIL` / `SENDER_PASSWORD` / `SMTP_SERVER` / `SMTP_PORT` | Office 365 SMTP |
| `RMS_URL` / `RMS_USERNAME` / `RMS_PASSWORD` | RMS portal login |
| `RECON_BASE_DIR` | optional override of the project directory |

Tuning knobs (optional, environment only):

| Variable | Default | Effect |
|---|---|---|
| `RECON_CATCHUP` | `1` | `0` disables catch-up of missed runs |
| `RECON_RETRY_HOURS` | `3` | wait between retries of a failed run |
| `RECON_TICK_SECONDS` | `300` | how often the scheduler loop checks the clock |
| `RECON_JOB_TIMEOUT` | `3600` | hard ceiling on one job, in seconds |

---

## Why not on Streamlit Cloud

Streamlit Community Cloud is the right place for the dashboard and the wrong place
for this automation. It cannot:

* run Chrome / Selenium, so it cannot log into the RMS portal and download anything;
* keep a scheduler alive between visits (apps sleep);
* reach the internal RMS portal from its network.

So the split is:

| Component | Runs on | Does |
|---|---|---|
| `run_live.py` + `scheduler.py` / launchd | the Mac (or a Linux box) | downloads, reconciles, emails |
| `streamlit_app/app.py` | Streamlit Cloud | shows the latest report, re-runs on uploaded files |

---

## Testing the plumbing without waiting for a date

```bash
python3 doctor.py                       # environment + credential check
python3 run_live.py --skip-download --no-email   # reconcile files already in downloads/
python3 scheduler.py --run-now reminder          # send the real reminder email now
python3 scheduler.py --run-now recon             # full run: download + reconcile + email
python3 scheduler.py --reset recon               # allow this month to run again
```
