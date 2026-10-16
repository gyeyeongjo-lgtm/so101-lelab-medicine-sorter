# 2026-10-16 고정 칸 ArUco 티칭·재생 데모

## 범위

자유 배치 자율 집기가 아닌, 현재 Astra 카메라와 고정 칸 3개를 쓰는
제한 데모다. 약통의 ArUco ID로 A/B/C를 알고 마커 중심 pixel이
어느 칸인지만 판정한다. T_B_W, IK, table XY, 카메라 위치 오차는 로봇
목표로 쓰지 않는다.

```text
ID7 = C = red
ID8 = B = blue
ID9 = A = no destination; ignored
```

## 구현

- 단일 CLI에 `teach`, `run --dry-run`, `run --step`을 추가했다.
- `teach`는 16개 named pose를 leader relative-start로 맞춘 뒤 Enter로 캡처한다.
- follower를 일반 `SO101Follower.connect()`로 열지 않고 bus를
  `handshake=False`로 열며 configure/calibration write를 firewall로 차단한다.
- Torque ALL OFF일 때만 fresh Present raw→Goal raw exact copy 1회, read-back,
  Torque ON 1회를 수행한다. 예상 밖 Torque 변화나 mixed state는 중단한다.
- `run --dry-run`은 `/manual-frame.json`의 snapshot에서 ArUco 중심만 사용하고
  hardware session을 생성하지 않는다.
- `run --step`은 각 자세 전환 직전 Enter를 요구한다. 재생 순서는
  `home → open → slot_pre → slot_grasp → close → slot_lift →
  basket_above → basket_release → open → basket_above → home`이다.
- multi-joint smoothstep, 관절별 속도·가속도·segment travel, arm step 2°,
  gripper step 2pp를 모두 적용한다.
- Ctrl+C는 새 명령을 중단한 후 fresh Present raw를 Goal raw로 한 번
  복사해 현재 위치 HOLD를 요청한다. Torque OFF를 의미하지 않는다.
- 종료는 follower/leader 모두 `disconnect(disable_torque=False)`다.
- sudo/lsof/fuser, process kill/signal, service restart는 없다. sysfs USB serial,
  per-user process lock, serial FD `TIOCEXCL`만 사용한다.

## 오프라인 검증

```text
fixed demo unit tests = 17/17 PASS
existing sorter tests = 30/30 PASS
python compile = PASS
git diff --check = PASS
hardware serial open = 0
Goal write = 0
Torque write = 0
config write = 0
motor command = 0
```

테스트는 C→red/B→blue/A no-route, slot unique match, stale/wrong coordinate
space 차단, 계획 단계 순서, 다관절 공통 fraction, 속도·2° step·segment
travel, dry-run hardware 0, raw HOLD exact copy, Torque ON exactly once, already-ON no
toggle, mixed Torque abort, Ctrl+C raw hold one-shot, no-sudo path를 포함한다.

## 미실행·제한

- Jetson 배치: `NOT_RUN` (사용자가 Git pull 후 실행)
- 실제 teach/pose JSON: `NOT_RUN`
- 실제 dry-run의 ID→slot 판정: `NOT_RUN`
- 실제 `run --step`: `NOT_RUN`
- 실제 Goal/Torque/config/motor I/O: `0`
- 현재 slot ROI는 기존 고정 배치 픽셀 대역을 새 프레임에서 확인하도록
  `provisional_verify_in_dry_run`으로 표기했다. 이 상태에서 non-step 자동 run은 차단된다.
- YOLO detection은 카메라 UI에 보이는 확인용이며 계획 gate나 신원 판정에
  쓰지 않는다.

## Jetson 실행 순서

```bash
cd /home/jetson3/so101-lelab-medicine-sorter
git switch fix/usb-recording
git pull --ff-only origin fix/usb-recording

/home/jetson3/.local/share/uv/tools/lelab/bin/python -m medicine_sorter --config configs/system.example.json teach
/home/jetson3/.local/share/uv/tools/lelab/bin/python -m medicine_sorter --config configs/system.example.json run --dry-run
/home/jetson3/.local/share/uv/tools/lelab/bin/python -m medicine_sorter --config configs/system.example.json run --step
```
