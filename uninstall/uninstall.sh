#!/bin/bash
pkill -f '/bin/plugins/.*/mqtt_listener.py' 2>/dev/null || true
rm -f /etc/cron.d/loxberry-unifipoe 2>/dev/null || true
exit 0
