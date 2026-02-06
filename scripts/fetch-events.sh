#!/usr/bin/env bash
# Fetch dance-related messages from Ubud WhatsApp groups
# Usage: ./fetch-events.sh [days_back]
# Default: 7 days back

set -euo pipefail

DAYS_BACK="${1:-7}"
AFTER_DATE=$(date -v-${DAYS_BACK}d +%Y-%m-%d 2>/dev/null || date -d "-${DAYS_BACK} days" +%Y-%m-%d)

# Source group JIDs
GROUP1="17609142454-1609066274@g.us"
GROUP2="6281338201923-1627265153@g.us"
GROUP3="120363324641442334@g.us"

echo "=== Ubud Dance Events (since $AFTER_DATE) ==="
echo ""

fetch_group() {
  local group="$1"
  local name="$2"
  echo "--- $name ($group) ---"
  
  # Single broad search for dance-related content
  wacli messages search "dance OR ecstatic OR improv OR movement OR workshop OR Paradiso OR RESONANZ" \
    --chat "$group" --after "$AFTER_DATE" --limit 30 --json 2>/dev/null | \
    jq -r '.data.messages[]? | select(.Text != "" and .Text != null) | "[\(.Timestamp)]\n\(.Text)\n---"' 2>/dev/null || \
  # Fallback: simpler search if OR syntax not supported
  wacli messages search "dance" --chat "$group" --after "$AFTER_DATE" --limit 30 --json 2>/dev/null | \
    jq -r '.data.messages[]? | select(.Text != "" and .Text != null) | "[\(.Timestamp)]\n\(.Text)\n---"' 2>/dev/null || true
  
  echo ""
}

fetch_group "$GROUP1" "Sayuri Academy"
fetch_group "$GROUP2" "Ubud Events 1"
fetch_group "$GROUP3" "Ubud Events 2"
