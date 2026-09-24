#!/bin/bash
#
# macOS installer - registers two launchd agents for the Salary Reconciliation Agent.
#
#   14th, 09:00   EPF upload reminder   (run_epf_reminder.py --auto)
#   16th, 18:00   full monthly run      (run_live.py --auto)
#
# launchd starts a job that came due while the Mac was asleep as soon as it wakes,
# so a closed lid at 18:00 does not lose the run. If the Mac is powered off for the
# whole day launchd skips it - for that case run `python3 scheduler.py` alongside
# this (it catches up a missed run within the same month). The monthly ledger in
# recon_state.py means the two never send the same report twice.
#
# Usage:
#   bash install_launchd.sh              install (or reload) both agents
#   bash install_launchd.sh status       show whether the agents are loaded
#   bash install_launchd.sh test         run both jobs now, ignoring the clock
#   bash install_launchd.sh logs         tail both log files
#   bash install_launchd.sh uninstall    remove the agents

set -euo pipefail

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="com.koenig.salary-recon"
LA_DIR="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"
DOMAIN="gui/$UID_NUM"

REMINDER_LABEL="$PREFIX.reminder"
RECON_LABEL="$PREFIX.monthly"
REMINDER_PLIST="$LA_DIR/$REMINDER_LABEL.plist"
RECON_PLIST="$LA_DIR/$RECON_LABEL.plist"

if [ "$(uname -s)" != "Darwin" ]; then
    echo "This installer is for macOS. On Linux use install_service.sh (systemd)."
    exit 1
fi

find_python() {
    if [ -x "$AGENT_DIR/.venv/bin/python" ]; then
        echo "$AGENT_DIR/.venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        command -v python3
    else
        echo ""
    fi
}

write_plist() {
    # $1 label  $2 plist path  $3 script  $4 day  $5 hour  $6 minute  $7 log file
    cat > "$2" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$1</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$AGENT_DIR/$3</string>
        <string>--auto</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$AGENT_DIR</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Day</key><integer>$4</integer>
        <key>Hour</key><integer>$5</integer>
        <key>Minute</key><integer>$6</integer>
    </dict>

    <key>RunAtLoad</key>
    <false/>

    <key>StandardOutPath</key>
    <string>$AGENT_DIR/logs/$7</string>
    <key>StandardErrorPath</key>
    <string>$AGENT_DIR/logs/$7</string>
</dict>
</plist>
PLIST
}

reload_agent() {
    local label="$1" plist="$2"
    launchctl bootout "$DOMAIN/$label" >/dev/null 2>&1 || true
    if launchctl bootstrap "$DOMAIN" "$plist" >/dev/null 2>&1; then
        echo "  loaded  $label"
    elif launchctl load -w "$plist" >/dev/null 2>&1; then
        echo "  loaded  $label (legacy launchctl load)"
    else
        echo "  FAILED  $label"
        echo "          run manually: launchctl bootstrap $DOMAIN \"$plist\""
        return 1
    fi
}

case "${1:-install}" in
    install)
        PYTHON="$(find_python)"
        if [ -z "$PYTHON" ]; then
            echo "No python3 found. Install Python 3 and re-run."
            exit 1
        fi

        if [ ! -f "$AGENT_DIR/.env" ]; then
            echo "WARNING: $AGENT_DIR/.env not found - copy .env.example to .env and"
            echo "         fill in the SMTP and RMS credentials, or the jobs will fail."
            echo ""
        fi

        mkdir -p "$LA_DIR" "$AGENT_DIR/logs"

        write_plist "$REMINDER_LABEL" "$REMINDER_PLIST" "run_epf_reminder.py" 14 9 0  "launchd_reminder.log"
        write_plist "$RECON_LABEL"    "$RECON_PLIST"    "run_live.py"          16 18 0 "launchd_monthly.log"

        echo "Installing launchd agents"
        echo "  project : $AGENT_DIR"
        echo "  python  : $PYTHON"
        echo "  agents  : $LA_DIR"
        echo ""
        reload_agent "$REMINDER_LABEL" "$REMINDER_PLIST"
        reload_agent "$RECON_LABEL"    "$RECON_PLIST"
        echo ""
        echo "Schedule"
        echo "  day 14 at 09:00  EPF upload reminder -> tax team"
        echo "  day 16 at 18:00  RMS download + reconcile + report email"
        echo ""
        echo "Check it:"
        echo "  bash install_launchd.sh status"
        echo "  bash install_launchd.sh test          # fire both jobs now"
        echo "  python3 scheduler.py --status         # what is due next"
        ;;

    status)
        echo "launchd agents:"
        launchctl print "$DOMAIN/$REMINDER_LABEL" 2>/dev/null | grep -E "^\s+(state|program) " || echo "  $REMINDER_LABEL : NOT loaded"
        launchctl print "$DOMAIN/$RECON_LABEL"    2>/dev/null | grep -E "^\s+(state|program) " || echo "  $RECON_LABEL : NOT loaded"
        echo ""
        python3 "$AGENT_DIR/scheduler.py" --status
        ;;

    test)
        echo "Kicking both agents (ignoring the clock)..."
        launchctl kickstart -k "$DOMAIN/$REMINDER_LABEL" && echo "  started $REMINDER_LABEL"
        launchctl kickstart -k "$DOMAIN/$RECON_LABEL"    && echo "  started $RECON_LABEL"
        echo ""
        echo "Watch the logs with:  bash install_launchd.sh logs"
        ;;

    logs)
        tail -n 60 -f "$AGENT_DIR/logs/launchd_reminder.log" "$AGENT_DIR/logs/launchd_monthly.log"
        ;;

    uninstall)
        echo "Removing launchd agents"
        launchctl bootout "$DOMAIN/$REMINDER_LABEL" >/dev/null 2>&1 || true
        launchctl bootout "$DOMAIN/$RECON_LABEL"    >/dev/null 2>&1 || true
        rm -f "$REMINDER_PLIST" "$RECON_PLIST"
        echo "  removed $REMINDER_LABEL and $RECON_LABEL"
        ;;

    *)
        echo "Usage: bash install_launchd.sh [install|status|test|logs|uninstall]"
        exit 1
        ;;
esac
