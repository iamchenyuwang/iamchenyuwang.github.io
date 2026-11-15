#!/usr/bin/env bash
set -euo pipefail
umask 077

# Monthly publication audit.
#
# Codex researches new papers on the open web and may edit index.html in a
# throwaway copy of the site. Web pages can contain prompt injections, so Codex
# runs inside a transient systemd sandbox that sees only that copy, its own
# login, and the network: no other projects, SSH keys, GitHub tokens, host
# sockets, or root capabilities. This script, not Codex, validates the edit
# against the untouched clone and publishes it.
#
# Options (for manual testing):
#   --dry-run       run the audit and validation, but do not commit or push
#   --prompt FILE   use FILE instead of automation/monthly_publication_prompt.md

PATH=/usr/local/bin:/usr/bin:/bin
export PATH

REPOSITORY_URL="git@github.com:iamchenyuwang/iamchenyuwang.github.io.git"
SITE_URL="https://iamchenyuwang.github.io/"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIRECTORY="$PROJECT_ROOT/logs/monthly-publications"
LOCK_FILE="$PROJECT_ROOT/logs/.monthly-publications.lock"
VALIDATOR="$PROJECT_ROOT/scripts/validate_publication_diff.py"
CODEX_HOME_SOURCE="/root/.codex"
DRY_RUN=0
PROMPT_OVERRIDE=""
RUN_DIRECTORY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --prompt) PROMPT_OVERRIDE="$(realpath -- "$2")"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

mkdir -p "$LOG_DIRECTORY"
chmod 700 "$PROJECT_ROOT/logs" "$LOG_DIRECTORY"
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
PUBLISH_REPOSITORY="$RUN_DIRECTORY/publish"   # never visible to Codex
SANDBOX_WORK="$RUN_DIRECTORY/work"            # mounted at /root/work for Codex
VALIDATED_INDEX="$RUN_DIRECTORY/index.validated.html"
UNIT_NAME="iamchenyuwang-publication-audit-$(date -u +%Y%m%d%H%M%S)"

run_codex_in_sandbox() {
    local prompt_file="$1"
    # A private copy of the Codex config; the login file is bind-mounted so a
    # token refresh during the run is written back to the real login.
    cp -- "$CODEX_HOME_SOURCE/config.toml" "$RUN_DIRECTORY/codex-config.toml"

    systemd-run --quiet --wait --pipe --collect \
        --unit="$UNIT_NAME" \
        --property=RuntimeMaxSec=55min \
        --property=WorkingDirectory=/root/work/repository \
        --setenv=HOME=/root \
        --setenv=PATH="$PATH" \
        --setenv=LANG=C.UTF-8 \
        --property=CapabilityBoundingSet= \
        --property=NoNewPrivileges=yes \
        --property=ProtectSystem=strict \
        --property=PrivateTmp=yes \
        --property=PrivateDevices=yes \
        --property=ProtectKernelTunables=yes \
        --property=ProtectKernelModules=yes \
        --property=ProtectKernelLogs=yes \
        --property=ProtectControlGroups=yes \
        --property=ProtectClock=yes \
        --property=ProtectHostname=yes \
        --property=RestrictSUIDSGID=yes \
        --property=LockPersonality=yes \
        --property=TemporaryFileSystem=/root \
        --property=TemporaryFileSystem=/run \
        --property=BindReadOnlyPaths=/run/systemd/resolve \
        --property=BindPaths="$SANDBOX_WORK:/root/work" \
        --property=BindPaths="$CODEX_HOME_SOURCE/auth.json:/root/.codex/auth.json" \
        --property=BindPaths="$RUN_DIRECTORY/codex-config.toml:/root/.codex/config.toml" \
        --property="InaccessiblePaths=-/home -/srv -/mnt -/media -/opt -/snap -/var/lib -/var/www -/var/backups -/var/log -/var/mail -/var/spool -/var/cache -/etc/shadow -/etc/gshadow -/etc/ssh -/etc/letsencrypt -/etc/systemd/system -/etc/nginx -/swapfile -/swapfile2" \
        /usr/bin/codex exec \
            --cd /root/work/repository \
            --ephemeral \
            --dangerously-bypass-approvals-and-sandbox \
            --output-last-message /root/work/last-message.txt \
            - < "$prompt_file"
}

wait_for_live_page() {
    local expected_sha="$1" live_sha attempt
    for attempt in $(seq 1 30); do
        live_sha="$(curl -fsS "${SITE_URL}?audit=$(date +%s)" | sha256sum | cut -d' ' -f1 || true)"
        if [[ "$live_sha" == "$expected_sha" ]]; then
            echo "Live homepage matches the published index.html (check $attempt)."
            return 0
        fi
        sleep 30
    done
    echo "WARNING: the live homepage did not match the published index.html within 15 minutes."
    return 1
}

{
    echo "Monthly publication audit started at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "Dry run: nothing will be committed or pushed."
    fi

    git clone --quiet --branch main --single-branch "$REPOSITORY_URL" "$PUBLISH_REPOSITORY"
    BASE_COMMIT="$(git -C "$PUBLISH_REPOSITORY" rev-parse HEAD)"
    echo "Base commit: $BASE_COMMIT"

    mkdir "$SANDBOX_WORK"
    cp -a -- "$PUBLISH_REPOSITORY" "$SANDBOX_WORK/repository"

    PROMPT_FILE="${PROMPT_OVERRIDE:-$PUBLISH_REPOSITORY/automation/monthly_publication_prompt.md}"
    CODEX_STATUS=0
    run_codex_in_sandbox "$PROMPT_FILE" || CODEX_STATUS=$?

    echo
    echo "Final report:"
    if [[ -f "$SANDBOX_WORK/last-message.txt" && ! -L "$SANDBOX_WORK/last-message.txt" ]]; then
        head -c 65536 -- "$SANDBOX_WORK/last-message.txt"
        echo
    fi
    if [[ "$CODEX_STATUS" -ne 0 ]]; then
        echo "Codex exited with status $CODEX_STATUS; nothing was published."
        exit "$CODEX_STATUS"
    fi

    if cmp -s -- "$PUBLISH_REPOSITORY/index.html" "$SANDBOX_WORK/repository/index.html"; then
        echo "No change to index.html; nothing to publish."
    else
        echo
        echo "Validating the proposed index.html:"
        if ! python3 -I "$VALIDATOR" \
                "$PUBLISH_REPOSITORY/index.html" \
                "$SANDBOX_WORK/repository/index.html" \
                "$VALIDATED_INDEX"; then
            echo "Proposed diff (not published):"
            diff -u -- "$PUBLISH_REPOSITORY/index.html" "$SANDBOX_WORK/repository/index.html" | head -n 400 || true
            exit 1
        fi

        cp -- "$VALIDATED_INDEX" "$PUBLISH_REPOSITORY/index.html"
        git -C "$PUBLISH_REPOSITORY" --no-pager diff --stat
        git -C "$PUBLISH_REPOSITORY" --no-pager diff
        if [[ "$DRY_RUN" -eq 1 ]]; then
            echo "Dry run: validated change was not committed."
        else
            git -C "$PUBLISH_REPOSITORY" add index.html
            git -C "$PUBLISH_REPOSITORY" commit --quiet -m "Update publication record from monthly audit"
            git -C "$PUBLISH_REPOSITORY" push --quiet origin HEAD:main
            echo "Pushed $(git -C "$PUBLISH_REPOSITORY" rev-parse HEAD) to main."
            wait_for_live_page "$(sha256sum "$PUBLISH_REPOSITORY/index.html" | cut -d' ' -f1)" || true
        fi
    fi
    echo "Monthly publication audit finished at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$RUN_LOG" 2>&1
