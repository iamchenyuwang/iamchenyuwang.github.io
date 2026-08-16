#!/usr/bin/env bash
set -euo pipefail

# Install or replace the monthly publication audit without disturbing the
# server's other cron jobs. Cron uses UTC on this server.

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run_monthly_publication_agent.sh"
MARKER="# Chenyu Wang website - monthly Codex-reviewed publication audit"
SCHEDULE="17 14 1 * * $SCRIPT_PATH"
CURRENT_CRONTAB="$(mktemp /tmp/iamchenyuwang-crontab-current.XXXXXX)"
UPDATED_CRONTAB="$(mktemp /tmp/iamchenyuwang-crontab-updated.XXXXXX)"

cleanup() {
    rm -f -- "$CURRENT_CRONTAB" "$UPDATED_CRONTAB"
}
trap cleanup EXIT

crontab -l > "$CURRENT_CRONTAB" 2>/dev/null || true

awk -v marker="$MARKER" -v schedule="$SCHEDULE" '
    $0 == marker { next }
    /scripts\/run_monthly_publication_agent\.sh/ { next }
    { print }
    END {
        print ""
        print marker
        print schedule
    }
' "$CURRENT_CRONTAB" > "$UPDATED_CRONTAB"

crontab "$UPDATED_CRONTAB"
echo "Installed: $SCHEDULE"
