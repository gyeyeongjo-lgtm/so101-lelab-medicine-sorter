#!/usr/bin/env bash
set -euo pipefail

LIVE=/home/jetson3/.local/share/uv/tools/lelab/lib/python3.14/site-packages/lelab/record.py
PY=/home/jetson3/.local/share/uv/tools/lelab/bin/python
TS=$(date +%Y%m%dT%H%M%S%z)
B=/home/jetson3/so101-recovery-backups/${TS}_pre-worker-instrumentation
EXPECTED=779fd897ef8384850b82c0491c08b2eaa803a502ad20c16fbb69db71cd82cba0

mkdir -p "$B"
ACTUAL=$(sha256sum "$LIVE" | awk '{print $1}')
test "$ACTUAL" = "$EXPECTED"

cp -p "$LIVE" "$B/record.py.original"
CAL=/home/jetson3/.cache/huggingface/lerobot/calibration
if [ -d "$CAL" ]; then cp -a "$CAL" "$B/calibration"; fi
systemctl --user status lelab.service --no-pager > "$B/service.before.txt" || true
systemctl --user show lelab.service \
  -p ActiveState -p SubState -p MainPID -p ExecStart > "$B/service.show.before.txt"
curl -sS --max-time 3 http://127.0.0.1:8000/teleoperation-status > "$B/teleoperation.before.json"
curl -sS --max-time 3 http://127.0.0.1:8000/recording-status > "$B/recording.before.json"
journalctl --user -u lelab.service -n 200 --no-pager > "$B/journal.before.txt"
sha256sum "$LIVE" /tmp/record-worker-instrumented.py > "$B/hashes.before.txt"

"$PY" -m py_compile /tmp/record-worker-instrumented.py
systemctl --user stop lelab.service
cp -p /tmp/record-worker-instrumented.py "$LIVE"
sha256sum "$LIVE" > "$B/record.py.instrumented.sha256"
systemctl --user start lelab.service

healthy=0
for i in $(seq 1 20); do
  if systemctl --user is-active --quiet lelab.service &&
     curl -fsS --max-time 2 http://127.0.0.1:8000/health >/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done
test "$healthy" = 1

systemctl --user is-active lelab.service
curl -fsS --max-time 3 http://127.0.0.1:8000/health
echo
echo "BACKUP=$B"
echo "LIVE_SHA256=$(sha256sum "$LIVE" | awk '{print $1}')"
