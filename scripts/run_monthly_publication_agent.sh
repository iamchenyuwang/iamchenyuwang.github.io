#!/usr/bin/env bash
set -euo pipefail

# Run a fresh Codex review in an isolated clone. The model, rather than a
# name-matching script, decides whether a paper belongs to Chenyu Wang.

PATH=/usr/local/bin:/usr/bin:/bin
export PATH

REPOSITORY_URL="git@github.com:iamchenyuwang/iamchenyuwang.github.io.git"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIRECTORY="$PROJECT_ROOT/logs/monthly-publications"
LOCK_FILE="/tmp/iamchenyuwang-monthly-publications.lock"
RUN_DIRECTORY=""

mkdir -p "$LOG_DIRECTORY"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    exit 0
fi

cleanup() {
    if [[ -n "$RUN_DIRECTORY" && -d "$RUN_DIRECTORY" ]]; then
        rm -rf -- "$RUN_DIRECTORY"
    fi
}
trap cleanup EXIT

RUN_DIRECTORY="$(mktemp -d /tmp/iamchenyuwang-publications.XXXXXX)"
RUN_LOG="$LOG_DIRECTORY/$(date -u +%Y-%m-%dT%H-%M-%SZ).log"
LAST_MESSAGE="$RUN_DIRECTORY/last-message.txt"

{
    echo "Monthly publication audit started at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    git clone --quiet --branch main --single-branch "$REPOSITORY_URL" "$RUN_DIRECTORY/repository"

    timeout 55m /usr/bin/codex exec \
        --cd "$RUN_DIRECTORY/repository" \
        --ephemeral \
        --approve-for-me \
        --output-last-message "$LAST_MESSAGE" \
        - < "$RUN_DIRECTORY/repository/automation/monthly_publication_prompt.md"

    echo
    echo "Final report:"
    if [[ -f "$LAST_MESSAGE" ]]; then
        sed -n '1,240p' "$LAST_MESSAGE"
    fi
    echo "Monthly publication audit finished at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$RUN_LOG" 2>&1
