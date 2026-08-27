#!/bin/bash
# Back up the CURRENT installed user configuration before LoxBerry replaces plugin files.
set -u
PDIR="${3:-}"
if [ -z "$PDIR" ]; then
  echo "<WARNING> Plugin folder argument missing; configuration backup skipped."
  exit 0
fi
PCONFIG="${LBPCONFIG:?LBPCONFIG missing}/$PDIR"
BACKUP="/tmp/loxberry-unifipoe-${PDIR}-config-backup.json"
if [ -f "$PCONFIG/config.json" ]; then
  if python3 -m json.tool "$PCONFIG/config.json" >/dev/null 2>&1; then
    cp -p "$PCONFIG/config.json" "$BACKUP" || exit 1
    chmod 600 "$BACKUP" 2>/dev/null || true
    echo "<INFO> UniFi PoE user configuration backed up from $PCONFIG/config.json."
  else
    echo "<WARNING> Existing UniFi PoE configuration is invalid JSON; refusing to overwrite backup."
  fi
else
  echo "<WARNING> No existing UniFi PoE config.json found at $PCONFIG."
fi
exit 0
