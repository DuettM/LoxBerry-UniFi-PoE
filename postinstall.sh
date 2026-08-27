#!/bin/bash
set -e
chmod 700 "$LBPBIN/unifipoe.py" "$LBPBIN/watchdog.py" 2>/dev/null || true
chmod 755 "$LBPHTMLAUTH/index.cgi" "$LBPHTMLAUTH/debug.cgi" "$LBPHTML/poe.cgi" 2>/dev/null || true
chmod 600 "$LBPCONFIG/config.json" 2>/dev/null || true
touch "$LBPCONFIG/unifipoe.log" 2>/dev/null || true
chmod 600 "$LBPCONFIG/unifipoe.log" 2>/dev/null || true
printf "%s [INFO] Plugin 0.5.0 installiert\n" "$(date "+%Y-%m-%d %H:%M:%S")" >> "$LBPCONFIG/unifipoe.log" 2>/dev/null || true
if [ -n "$LBPBIN" ] && [ -n "$LBPCONFIG" ]; then
  printf '* * * * * root %q %q >/dev/null 2>&1\n' "$LBPBIN/watchdog.py" "$LBPCONFIG/config.json" > /etc/cron.d/loxberry-unifipoe 2>/dev/null || true
  chmod 644 /etc/cron.d/loxberry-unifipoe 2>/dev/null || true
fi
exit 0
