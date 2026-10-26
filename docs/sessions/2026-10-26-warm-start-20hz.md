# 감독 1회 warm start 및 20Hz 보간

일자: 2026-10-26

## 요청과 범위

- 온도 제한을 이번 한 번만 완화한다.
- 로봇이 버벅이는 현상을 줄이기 위해 보간 프레임을 높인다.
- 실제 모터 실행은 사용자가 Jetson에서 직접 수행하며, 이번 변경 과정에서는
  robot serial을 열거나 motor command를 보내지 않는다.

## 구현

- 기본 및 web auto의 시작 온도 조건은 기존과 같은 `<50°C`다.
- `run --step --warm-start-once`에서만 시작 한도를 `<52°C`로 바꿔 50°C와 51°C를
  허용한다. 52°C 이상은 연결 직후 첫 Goal/Torque write 전에 차단한다.
- 실행 중 `55°C` hard stop, Overload 검사, fault/Ctrl+C current HOLD,
  `disconnect(disable_torque=False)`는 유지한다.
- control period는 `0.1 s`에서 `0.05 s`로 변경했다. 명령 주기는 10Hz에서 20Hz가
  되지만, max velocity 20, max acceleration 60, arm/gripper 최대 emitted step
  2°/2 percentage point는 그대로다.

## 오프라인 검증

- fixed-demo 및 web: `53/53 PASS`
- sorter: `30/30 PASS`
- Python compile: `PASS`
- `git diff --check`: `PASS`
- hardware serial open: `0`
- motor command: `0`

테스트는 기본 모드에서 50°C 차단, warm mode에서 51°C 허용 및 52°C 차단,
`--auto --warm-start-once`가 camera/session 생성 전에 거부되는지, 설정 주기가
0.05초인지 확인한다.

전체 legacy test discovery도 실행했으나 전체 PASS는 아니다. 최초 오류는 로컬
Python에 `cv2`가 없어 vision audit test를 import하지 못한 것이고 같은 원인의
error가 8건이었다. 별도로 예전 600 mm marker 기준을 기대하는
`test_diagnose_aruco_reference_gaps` 1건이 현재 527.324 mm 좌표와 달라 실패했다.
이는 이번 fixed-demo 변경 전부터 문서화된 환경/과거 기준 문제이며 숨기지 않고
분리 기록한다.

## 실기 상태와 첫 시험

- Jetson 배포: `NOT_RUN`
- 실제 20Hz motion: `NOT_RUN`
- 현재 web preflight에서 A(ID9)가 slot1에 없다는 최근 상태는 별도 해소가 필요하다.

최초 시험은 A를 slot1에 복귀시키고 팔 주변을 비운 뒤 한 약통만 감독형 단계 실행한다.

```bash
cd /home/jetson3/so101-lelab-medicine-sorter && git pull --ff-only origin fix/usb-recording && /home/jetson3/.local/share/uv/tools/lelab/bin/python -m medicine_sorter --config configs/system.example.json run --step --warm-start-once --rule A=green
```

실제 시작 온도가 52°C 이상이면 실행하지 않고 냉각한다. 한 약통 `--step`이 부드럽고
안전하게 성공한 뒤에만 8030 web server를 재시작해 새 20Hz 설정을 적용한다. web
자동 실행에는 warm override가 없다.

## 결과

`IMPLEMENTATION=PASS`, `OFFLINE_TEST=PASS`, `JETSON_DEPLOY=NOT_RUN`,
`HARDWARE_TEST=NOT_RUN`, `SERIAL_OPEN=0`, `MOTOR_COMMAND=0`
