#!/usr/bin/env bash
# One approved, no-camera LeRobot CLI record trial.
# This script does not change motor IDs, calibration values, baud rate, USB
# topology, or dataset upload settings. It temporarily stops LeLab to ensure
# that no UI request can share either serial bus with the CLI process.
set -euo pipefail

PY=/home/jetson3/.local/share/uv/tools/lelab/bin/python
REC=/home/jetson3/.local/share/uv/tools/lelab/bin/lerobot-record
FOLLOWER=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6058306-if00
LEADER=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6085272-if00
CAL=/home/jetson3/.cache/huggingface/lerobot/calibration
TS=$(date +%Y%m%dT%H%M%S%z)
BACKUP=/home/jetson3/so101-recovery-backups/${TS}_official-cli-record
DATASET=Supermassive111/codex_cli_diag_${TS}

test -x "$REC"
test -c "$FOLLOWER"
test -c "$LEADER"
test -f "$CAL/robots/so_follower/so-101.json"
test -f "$CAL/teleoperators/so_leader/so-101.json"

mkdir -p "$BACKUP"
cp -p "$CAL/robots/so_follower/so-101.json" "$BACKUP/follower-calibration.before.json"
cp -p "$CAL/teleoperators/so_leader/so-101.json" "$BACKUP/leader-calibration.before.json"
sha256sum \
  "$CAL/robots/so_follower/so-101.json" \
  "$CAL/teleoperators/so_leader/so-101.json" > "$BACKUP/calibration.before.sha256"
"$REC" --help > "$BACKUP/lerobot-record.help.txt"

curl -fsS --max-time 3 http://127.0.0.1:8000/teleoperation-status > "$BACKUP/teleoperation.before.json"
curl -fsS --max-time 3 http://127.0.0.1:8000/recording-status > "$BACKUP/recording.before.json"
journalctl _SYSTEMD_USER_UNIT=lelab.service -n 200 --no-pager > "$BACKUP/lelab.journal.before.txt" || true

restore_service() {
  result=$?
  trap - EXIT
  set +e
  systemctl --user start lelab.service
  for _ in $(seq 1 30); do
    if systemctl --user is-active --quiet lelab.service &&
       curl -fsS --max-time 2 http://127.0.0.1:8000/health > "$BACKUP/health.after.json"; then
      break
    fi
    sleep 1
  done
  systemctl --user status lelab.service --no-pager > "$BACKUP/service.after.txt" || true
  sha256sum \
    "$CAL/robots/so_follower/so-101.json" \
    "$CAL/teleoperators/so_leader/so-101.json" > "$BACKUP/calibration.after.sha256" || true
  journalctl _SYSTEMD_USER_UNIT=lelab.service -n 200 --no-pager > "$BACKUP/lelab.journal.after.txt" || true
  echo "RESULT=$result"
  echo "DATASET=$DATASET"
  echo "BACKUP=$BACKUP"
  exit "$result"
}
trap restore_service EXIT

systemctl --user stop lelab.service

"$REC" \
  --teleop.type=so101_leader \
  --teleop.port="$LEADER" \
  --teleop.id=so-101 \
  --robot.type=so101_follower \
  --robot.port="$FOLLOWER" \
  --robot.id=so-101 \
  --robot.cameras='{}' \
  --dataset.single_task='approved no-camera diagnostic recording' \
  --dataset.repo_id="$DATASET" \
  --dataset.num_episodes=1 \
  --dataset.episode_time_s=5 \
  --dataset.reset_time_s=0 \
  --dataset.video=false \
  --dataset.push_to_hub=false \
  --display_data=false \
  2>&1 | tee "$BACKUP/lerobot-record.log"
