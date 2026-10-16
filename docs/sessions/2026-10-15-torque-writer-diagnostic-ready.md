# 2026-10-15 unknown Torque writer 진단 준비

## 범위

- 목표는 SINGLE_SESSION_DEMO attempt2에서 Goal raw exact-copy 뒤, 절차의 명시적 Torque write 전에 전 축 Torque가 ON으로 관측된 원인 추적이다.
- teaching, trajectory, calibration, HOME/SAFE_HIGH, recovery, safety tolerance는 변경하지 않았다.
- live connect 진단은 별도 승인 문구 `RUN TORQUE WRITER DIAGNOSTIC` 전에는 실행하지 않는다.

## 정적 경로 확인

- 설치된 `SO101Follower.connect()`는 `configure()`를 호출한다.
- `configure()`는 `bus.torque_disabled()` context를 사용하고, 그 context의 `finally`가 `enable_torque()`를 호출한다. 따라서 일반 `SO101Follower.connect()`는 implicit Torque writer다.
- 검증 대상 `SINGLE_SESSION_DEMO`는 이 high-level connect를 호출하지 않고 `follower.bus.connect(handshake=False)`를 사용한다.
- 설치된 `FeetechMotorsBus.connect(handshake=False)`는 포트 open/timeout 설정만 수행한다.
- `Goal_Position` sync-write는 address 42/length 2, `Torque_Enable`은 address 40/length 1이라 register overlap 근거는 없다.
- 실패한 live path의 명시적 Torque ON packet은 Goal copy 뒤 Torque OFF 재확인 이후인데, 그 재확인에서 먼저 중단돼 해당 Torque packet은 실행되지 않았다.

따라서 일반 LeRobot connect 경로의 writer는 확인했지만, 실패한 SINGLE_SESSION_DEMO 경로에서 실제로 Torque를 켠 writer는 아직 확정하지 못했다. 현 단계 분류는 `EXTERNAL_OR_FIRMWARE_CHANGE_NOT_YET_CONFIRMED`이며 UNKNOWN을 안전으로 간주하지 않는다.

## write firewall

새 `scripts/torque_writer_diagnostic.py`는 다음 write layer를 진단용으로 가로채 실제 전송 전에 차단하고 register, motor ID, value, timestamp, Python call stack을 JSON에 기록한다.

- `bus.write`, `bus.sync_write`
- `bus.enable_torque`, `bus.disable_torque`
- `bus.configure_motors`, `bus.write_calibration`
- `bus._write`, `bus._sync_write`
- `port_handler.writePort`

기본 실행은 hardware-free이며 serial/motor/Goal/Torque/config write 모두 0이다. live 모드는 고정 승인 문구와 현장 문구, fresh audit 경로, leader FREE, follower exclusive lease를 모두 요구한다. firewall을 bus connect 전에 설치하고 `connect(handshake=False)`만 1회 수행한 뒤 read-only 두 표본을 읽고 `disconnect(disable_torque=False)`한다. teleop/teaching/configure/Goal motion은 호출하지 않는다.

## 검증

- 로컬 단위 테스트 `5/5 PASS`.
- 이전 관련 회귀를 포함한 로컬 결과 `46/46 PASS`, compile PASS, 기본 dry-run에서 serial/motor/Goal/Torque/config write 0.
- Jetson 대상 스크립트와 테스트 파일 배치 SHA는 로컬과 일치:
  - script `f9ec73e2781966924fda1ca4d6e1df5065d24ebcde8229ef1c15956cd274e2f4`
  - test `c7bfdf8123d0d0f4d8b82d62a57f30fd829c73fca917e800fada30d1ac7d0738`
- Jetson compile/test 시작 시 SSH가 timeout으로 끊겼고 재접속도 timeout이었다. 따라서 Jetson 설치 Python test는 `BLOCKED_NETWORK/NOT_COMPLETED`; 실제 serial open과 live diagnostic은 `NOT_RUN`이다.

## 결과

```ini
TORQUE_WRITER = NOT_CONFIRMED_IN_SINGLE_SESSION_PATH
FIX = WRITE_FIREWALL_DIAGNOSTIC_DEPLOYED_TEST_INCOMPLETE
JETSON_TEST = BLOCKED_NETWORK
READY_FOR_SINGLE_SESSION_DEMO = NO
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
NEXT_LIVE_COMMAND = NONE
```

변경은 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`이다.
