#!/usr/bin/env bash
# Push the project to GitHub, safely.
#
#   bash push_to_github.sh
#
# Handles: secret purge, history rewrite, and the case where files were added
# through GitHub's web UI (which makes local and remote diverge).
set -euo pipefail

REPO_URL="https://github.com/KoenigSalary/salary-reconciliation-agent.git"

echo "======================================================================"
echo " 1. Pre-flight"
echo "======================================================================"
[ -f .gitignore ] || { echo "ERROR: run this from the project root"; exit 1; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "ERROR: not a git repo"; exit 1; }

# Make sure the remote exists (filter-repo removes it as a safety measure)
if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "$REPO_URL"
  echo "  added remote: $REPO_URL"
else
  echo "  remote: $(git remote get-url origin)"
fi

# Secrets must be ignored
for pat in '.env' '.ENV.save' '.streamlit/secrets.toml'; do
  grep -qxF "$pat" .gitignore || { echo "$pat" >> .gitignore; echo "  gitignore += $pat"; }
done

echo
echo "======================================================================"
echo " 2. Untrack the credential file"
echo "======================================================================"
if git ls-files --error-unmatch .ENV.save >/dev/null 2>&1; then
  git rm --cached .ENV.save
  git commit -m "Stop tracking .ENV.save (contains credentials)"
  echo "  untracked and committed"
else
  echo "  .ENV.save not tracked - nothing to do"
fi

echo
echo "======================================================================"
echo " 3. Purge it from history"
echo "======================================================================"
PURGED=0
if git log --oneline --all -- .ENV.save | grep -q .; then
  command -v git-filter-repo >/dev/null 2>&1 || pip install git-filter-repo
  git filter-repo --invert-paths --path .ENV.save --force
  git remote remove origin 2>/dev/null || true
  git remote add origin "$REPO_URL"
  PURGED=1
  echo "  history rewritten; remote re-added"
else
  echo "  not present in history - skipping"
fi

echo
echo "======================================================================"
echo " 4. Stage the project"
echo "======================================================================"
# Explicit paths: keeps generated test data and reports out of the repo
git add .gitignore .env.example DEPLOY.md README.md QUICKSTART.md \
        MACOS_INSTALL.md PYTHON_VERSION_FIX.md CRITICAL_FIX.md ARCHITECTURE.txt \
        config.py data_processor.py reconciliation_engine.py email_handler.py \
        rms_automation.py main.py scheduler.py test_agent.py \
        recon_core.py reconcile_files.py run_live.py doctor.py \
        push_to_github.sh install_service.sh \
        requirements.txt requirements-agent.txt requirements-dashboard.txt runtime.txt \
        assets streamlit_app .streamlit .devcontainer \
        sample_data/generate_sample_data.py 2>/dev/null || true

git status --short | head -40

if git diff --cached --quiet; then
  echo "  nothing new to commit"
else
  git commit -m "Add Selenium-free reconciliation core, working dashboard and deployment docs"
  echo "  committed"
fi

echo
echo "======================================================================"
echo " 5. Verify (both checks must print NOTHING)"
echo "======================================================================"
echo "  tracked secret files:"; git ls-files | grep -iE '\.env|secret' || echo "    (none)"
echo "  .ENV.save in history:";  git log --oneline --all -- .ENV.save || echo "    (none)"

echo
echo "======================================================================"
echo " 6. Push"
echo "======================================================================"
if [ "$PURGED" = "1" ]; then
  echo "  history was rewritten -> force push required"
  git push --force origin main
else
  echo "  reconciling with the remote first (in case files were added on GitHub)"
  git pull --rebase origin main
  git push origin main
fi

echo
echo "Done. Confirm at: $REPO_URL"
