#!/usr/bin/env bash
# Recover from the failed rebase and get the project onto GitHub cleanly.
#
#   bash fix_and_push.sh
#
# What it does:
#   1. aborts the in-progress rebase
#   2. saves the remote's current state to a local branch (safety net)
#   3. untracks .ENV.save and the generated test data
#   4. purges .ENV.save from the whole history
#   5. force-pushes the clean result
set -euo pipefail

REPO_URL="https://github.com/KoenigSalary/salary-reconciliation-agent.git"

echo "======================================================================"
echo " 1. Leave the rebase"
echo "======================================================================"
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  git rebase --abort
  echo "  rebase aborted"
else
  echo "  no rebase in progress"
fi

echo
echo "======================================================================"
echo " 2. Safety net - save the remote's current state"
echo "======================================================================"
git fetch origin 2>/dev/null || echo "  (could not fetch - continuing)"
if git rev-parse --verify origin/main >/dev/null 2>&1; then
  git branch -f remote-backup origin/main
  echo "  origin/main saved to local branch 'remote-backup'"
  echo "  commits on the remote: $(git rev-list --count origin/main)"
  echo "  files on the remote:"
  git ls-tree -r --name-only origin/main | sed 's/^/    /' | head -30
else
  echo "  no origin/main yet"
fi

echo
echo "======================================================================"
echo " 3. Untrack the credential file and generated test data"
echo "======================================================================"
git rm --cached .ENV.save 2>/dev/null && echo "  untracked .ENV.save" || echo "  .ENV.save not tracked"

for f in sample_data/*.xls sample_data/*.xlsx sample_data/out/*.xlsx; do
  [ -e "$f" ] && git rm --cached "$f" >/dev/null 2>&1 && echo "  untracked $f"
done

[ -f .gitignore ] || touch .gitignore
for pat in '.env' '.ENV.save' '.streamlit/secrets.toml' 'sample_data/*.xls' 'sample_data/*.xlsx'; do
  grep -qxF "$pat" .gitignore || { echo "$pat" >> .gitignore; echo "  gitignore += $pat"; }
done
git add .gitignore

git commit -m "Remove credential file and generated test data from tracking" \
  && echo "  committed" || echo "  nothing to commit"

echo
echo "======================================================================"
echo " 4. Purge .ENV.save from history"
echo "======================================================================"
command -v git-filter-repo >/dev/null 2>&1 || pip install -q git-filter-repo
git filter-repo --invert-paths --path .ENV.save --force >/dev/null 2>&1 \
  && echo "  history rewritten" || echo "  filter-repo reported an issue"
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
echo "  remote: $(git remote get-url origin)"

echo
echo "======================================================================"
echo " 5. Verify (both checks must print NOTHING)"
echo "======================================================================"
echo "  tracked secret files:"
git ls-files | grep -iE '\.env|secret' || echo "    (none)"
echo "  .ENV.save anywhere in history:"
git log --oneline --all -- .ENV.save || echo "    (none)"
echo "  credential strings in history:"
if git grep -I -q -E 'rzf|Sec@' $(git rev-list --all) 2>/dev/null; then
  echo "    !! STILL PRESENT - do not push, tell me"
else
  echo "    (clean)"
fi

echo
echo "======================================================================"
echo " 6. Push"
echo "======================================================================"
echo "  history was rewritten, so this needs --force."
echo "  the old remote state is preserved locally as 'remote-backup'."
git push --force origin main

echo
echo "Done. Check: $REPO_URL"
echo "If anything on the remote was unique, recover it with:"
echo "    git log remote-backup --oneline"
