#!/usr/bin/env bash
# Recover from the stuck rebase and publish the project with a clean history.
#
#   bash recover_and_push.sh
#
# Why a fresh history: the remote was force-pushed with an unrelated history that
# deleted files your commit touches, so git cannot replay your work on top of it.
# The old history also contains .ENV.save with live credentials - so replacing it
# is both the easiest fix and the safer one.
#
# Nothing is destroyed: a full backup (including .git) is taken first.
set -uo pipefail

REPO_URL="https://github.com/KoenigSalary/salary-reconciliation-agent.git"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$HOME/recon_backup_$STAMP"

echo "======================================================================"
echo " 1. Full backup (including .git)"
echo "======================================================================"
mkdir -p "$BACKUP"
cp -R . "$BACKUP/project" 2>/dev/null
echo "  backup: $BACKUP/project"
echo "  size:   $(du -sh "$BACKUP/project" 2>/dev/null | cut -f1)"
echo
echo "  To undo everything later:  rm -rf .git && cp -R \"$BACKUP/project/.git\" ."

echo
echo "======================================================================"
echo " 2. Clear the stuck rebase state"
echo "======================================================================"
rm -rf .git/rebase-merge .git/rebase-apply 2>/dev/null
git rebase --abort 2>/dev/null
echo "  rebase state cleared (files on disk are untouched)"

echo
echo "======================================================================"
echo " 3. Verify your source files are all present"
echo "======================================================================"
MISSING=0
for f in config.py data_processor.py reconciliation_engine.py email_handler.py \
         rms_automation.py main.py scheduler.py recon_core.py reconcile_files.py \
         run_live.py doctor.py requirements.txt runtime.txt streamlit_app/app.py \
         assets/koenig-logo.png .env; do
  if [ -e "$f" ]; then printf "  ok   %s\n" "$f"; else printf "  MISS %s\n" "$f"; MISSING=1; fi
done
if [ "$MISSING" = "1" ]; then
  echo
  echo "  Some files are missing. Restore them from the backup:"
  echo "    cp -R \"$BACKUP/project/.\" ."
  echo "  Then re-run this script. Stopping here so nothing is pushed half-empty."
  exit 1
fi

echo
echo "======================================================================"
echo " 4. Start a clean history"
echo "======================================================================"
rm -rf .git
git init -q -b main
git config user.name  "$(git config --global user.name  || echo 'Koenig Salary')" 2>/dev/null
git config user.email "$(git config --global user.email || echo 'noreply@koenig-solutions.com')" 2>/dev/null
echo "  fresh repository initialised on branch main"

cat > .gitignore <<'IGN'
# Secrets - never commit
.env
.ENV.save
.streamlit/secrets.toml

# Virtualenv
venv/
.venv/
env/

# Python cache
__pycache__/
*.pyc
*.pyo

# macOS
.DS_Store
__MACOSX/

# Runtime folders
downloads/
epf_uploads/
reports/
logs/
scheduler.log

# Generated test data (keep the generator)
sample_data/*.xls
sample_data/*.xlsx
sample_data/out/

# Excel lock files
~$*
IGN
echo "  wrote .gitignore"

echo
echo "======================================================================"
echo " 5. Stage only source files"
echo "======================================================================"
git add .gitignore .env.example DEPLOY.md README.md QUICKSTART.md \
        MACOS_INSTALL.md PYTHON_VERSION_FIX.md CRITICAL_FIX.md ARCHITECTURE.txt \
        config.py data_processor.py reconciliation_engine.py email_handler.py \
        rms_automation.py main.py scheduler.py test_agent.py \
        run_epf_reminder.py run_monthly_reco.py diagnose_and_fix.py \
        recon_core.py reconcile_files.py run_live.py doctor.py \
        recover_and_push.sh install_service.sh \
        requirements.txt requirements-agent.txt requirements-dashboard.txt runtime.txt \
        assets streamlit_app .streamlit .devcontainer \
        sample_data/generate_sample_data.py 2>/dev/null

git add -A 2>/dev/null
# .gitignore protects the rest; unstage anything sensitive if it slipped in
git reset -q .ENV.save .env .streamlit/secrets.toml 2>/dev/null

echo "  staged files:"
git diff --cached --name-only | sed 's/^/    /'

echo
echo "======================================================================"
echo " 6. Verify - all three checks must be clean"
echo "======================================================================"
echo "  a) tracked secret files:"
if git diff --cached --name-only | grep -iE '\.env|secret'; then
  echo "     !! ABORT - a credential file is staged"
  exit 1
else
  echo "     (none)"
fi

echo "  b) conflict markers in staged files:"
BAD=0
for f in $(git diff --cached --name-only); do
  [ -f "$f" ] || continue
  if grep -qE '^(<<<<<<<|>>>>>>>|=======$)' "$f" 2>/dev/null; then
    echo "     !! $f contains conflict markers"
    BAD=1
  fi
done
[ "$BAD" = "0" ] && echo "     (none)" || { echo "     Fix these before pushing."; exit 1; }

echo "  c) live credential strings in staged content:"
if git diff --cached | grep -qE 'rzf|Sec@|SENDER_PASSWORD='; then
  echo "     !! ABORT - credential text found in staged content"
  exit 1
else
  echo "     (clean)"
fi

echo
echo "======================================================================"
echo " 7. Commit and push"
echo "======================================================================"
git commit -q -m "Salary reconciliation agent: Selenium-free core, Streamlit dashboard, deployment docs"
echo "  commit: $(git rev-parse --short HEAD)  files: $(git ls-files | wc -l | tr -d ' ')"

git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
echo "  remote: $(git remote get-url origin)"
echo
echo "  Pushing with --force: this REPLACES the remote's history."
echo "  The previous remote state is in the backup at: $BACKUP/project/.git"
echo
git push --force origin main

echo
echo "======================================================================"
echo " Done"
echo "======================================================================"
echo "  Repo:   $REPO_URL"
echo "  Backup: $BACKUP"
