#!/bin/sh
# One image, two roles. Railway sets PROCESS per service.
set -e
case "$PROCESS" in
  web)
    exec daphne -b 0.0.0.0 -p "${PORT:-8000}" --proxy-headers -v1 backend.asgi:application
    ;;
  tick)
    # Railway starts this every 5 minutes. Outside peak hours (weekdays
    # 07:00-16:59 UTC = 08:00-17:59 Lagos, which covers NGX trading and the
    # morning and evening crons) only the runs in the first 10 minutes of each
    # hour go on to load Django; the rest exit here, in well under a second.
    # Off-peak, due tasks therefore run up to an hour late.
    # Set TICK_ALWAYS=1 to run every 5 minutes around the clock.
    if [ "${TICK_ALWAYS:-0}" != "1" ]; then
      dow=$(date -u +%u); hour=$(date -u +%H); min=$(date -u +%M)
      hour=${hour#0}; min=${min#0}
      if [ "$dow" -gt 5 ] || [ "$hour" -lt 7 ] || [ "$hour" -gt 16 ]; then
        if [ "$min" -ge 10 ]; then
          echo "tick: off-peak, skipping (next run on the hour)"
          exit 0
        fi
      fi
    fi
    exec python manage.py beat_tick
    ;;
  *)
    echo "Set PROCESS=web or PROCESS=tick" >&2; exit 1
    ;;
esac
