# Deploying to GitHub + Streamlit Cloud

Two things to know before you start:

1. **The dashboard deploys; the RMS downloader does not.** Streamlit Cloud has no Chrome and
   no route to `rms.koenig-solutions.com`. Keep `main.py` / `scheduler.py` running on a
   machine inside the network and let them push files (or just use the dashboard's upload form).
2. **Never commit `.env`.** `.gitignore` already blocks it. If your credentials were ever
   committed, rotate them now (email app-password + RMS password).

---

## Step 1 — Push to GitHub

Canonical install path: **`~/Downloads/Agent/Reconciliation`**. All commands below assume
you are in that directory.

```bash
cd ~/Downloads/Agent/Reconciliation
```



```bash
cd Reconciliation

git init                                  # skip if .git already exists
git add .
git status                                # confirm .env is NOT in the list
git commit -m "Selenium-free reconciliation core + working Streamlit dashboard"
git branch -M main
git remote add origin https://github.com/<your-org>/<your-repo>.git
git push -u origin main
```

Using the GitHub CLI instead:

```bash
gh auth login
gh repo create salary-reconciliation-agent --private --source=. --push
```

> If you already have a repo (e.g. `KoenigSalary/salary-reconciliation-agent`), keep the
> existing remote and just `git add -A && git commit -m "..." && git push`.

**Verify before pushing** — this must print nothing:

```bash
git ls-files | grep -E '\.env|secrets'
```

### ⚠️ This repo currently tracks `.ENV.save`

`git ls-files` in the existing repo lists **`.ENV.save`** — a backup copy of the credentials
file. It contains the real SMTP app-password and RMS password, so it must be removed from
version control *and* from history before this repo is made public:

```bash
# 1. rotate the credentials first (email app-password + RMS password)
# 2. stop tracking the file
git rm --cached .ENV.save
echo ".ENV.save" >> .gitignore
git commit -m "Stop tracking .ENV.save (credentials)"

# 3. purge it from history (rewrites history — coordinate with any collaborators)
pip install git-filter-repo
git filter-repo --invert-paths --path .ENV.save
git push --force origin main
```

If the repo has never been pushed, steps 2-3 are enough.


---

## Step 2 — Deploy on Streamlit Community Cloud

1. Go to <https://share.streamlit.io> → **Create app** → **Deploy a public app from GitHub**.
2. Repository: `<your-org>/<your-repo>` · Branch: `main`.
3. **Main file path: `streamlit_app/app.py`** ← this is the important one.
4. Python version: 3.11 (matches `runtime.txt`).
5. Click **Deploy**. The first build takes ~3-5 minutes.

Streamlit installs `requirements.txt` from the repo root automatically. That file deliberately
does **not** include Selenium — the cloud build stays small and needs no browser.

---

## Step 3 — Add secrets

In the Streamlit app: **Settings → Secrets**. Paste (TOML):

```toml
SENDER_EMAIL = "your_sender@yourcompany.com"
SENDER_PASSWORD = "your_app_password"
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = "587"
RECIPIENT_EMAILS = "recipient1@yourcompany.com,recipient2@yourcompany.com"
TAX_TEAM_EMAIL = "tax_team@yourcompany.com"

# Only needed if you ever run the downloader on the same host
RMS_URL = "https://rms.koenig-solutions.com"
RMS_USERNAME = "your_rms_username"
RMS_PASSWORD = "your_rms_password"
```

`streamlit_app/app.py` copies these into the environment at startup, so `config.py` reads
them exactly like it reads `.env`. For local runs, create `.streamlit/secrets.toml` with the
same content (it is git-ignored).

The dashboard itself needs **no** secrets — reconciliation is pure pandas.

---

## Step 4 — Post-deploy checklist

Run the diagnostic first — it answers most "cannot find" questions in one shot:

```bash
cd ~/Downloads/Agent/Reconciliation
python3 doctor.py
```


- [ ] App opens and shows the upload form
- [ ] Upload the 4 files → **Run Reconciliation** → KPIs and tabs populate
- [ ] "Download generated Excel report" produces a valid 6-sheet workbook
- [ ] `Summary` / `Branch Wise` tabs are not full of `Unnamed: 0` columns
      (that would mean the header-row detection failed — tell me and I'll look)
- [ ] No credentials visible anywhere in the GitHub repo

---

## Step 5 — Keeping the RMS downloader running

The downloader needs to live where the portal is reachable:

```bash
# on an internal machine / VM
cd Reconciliation
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install selenium==4.15.2 webdriver-manager==4.0.1 schedule==1.2.0 xlrd==2.0.1
sudo bash install_service.sh          # systemd unit: salary-reconciliation-agent
```

`install_service.sh` installs a `salary-reconciliation-agent` service that runs `scheduler.py`
(16th → EPF reminder, 18th → full reconciliation + email).

If you would rather not keep a service alive, run it by hand:

```bash
python3 main.py                        # download + reconcile + email
python3 reconcile_files.py --auto      # reconcile only, from files already in downloads/
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Cloud build fails on `selenium` | You re-added it to `requirements.txt`. Keep it commented out on the cloud. |
| `Could not read file ...` on a `.xls` | The RMS export is an HTML table; `lxml` must be installed (it is in `requirements.txt`). |
| Dashboard shows `Unnamed: 0` columns | Report file has an unexpected layout — the header detector looks for the first row with ≥3 filled cells. |
| `Missing upload(s)` in the sidebar | All four files are required for a run. |
| EPF mismatches = every employee | The EPF file was not recognised; check it has a UAN column and an amount column. |
| Cloud app can't reach RMS | Expected. Run the downloader on-prem. |
