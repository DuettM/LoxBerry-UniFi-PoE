#!/bin/bash
set -u
PDIR="${3:-}"
if [ -n "$PDIR" ] && [ -n "${LBPBIN:-}" ]; then
  TARGET="$LBPBIN/$PDIR/mqtt_listener.py"
  pkill -f -- "$TARGET" 2>/dev/null || true
  echo "<INFO> UniFi PoE MQTT listener for $PDIR stopped."
fi
exit 0
