# 2026-10-15 SINGLE_SESSION_DEMO 최소 통합 / Jetson fake 배치

## 범위

현재 follower Torque 전 축 OFF, Moving 전 축 0, 양 포트 FREE 및 teaching `NOT_RUN` 상태에서 실제 serial·모터 명령 없이 다음만 수행했다.

1. 검증된 atomic HOLD와 no-reconfigure teaching 종료 경로의 Torque OFF 여부 확인
2. 두 단계를 한 follower/leader 연결 생명주기 안에서 잇는 최소 entrypoint 준비
3. 로컬 및 Jetson 격리 설치본에서 fake/dry-run 검증

calibration, historical reference, GRASP TCP, HOME/SAFE_HIGH, gain/tolerance, 2° limiter, LeLab 서비스 및 UI 설정은 변경하지 않았다.

## 종료 경로 확인

확인한 범위:

- `scripts/atomic_hold_restore.py`
- `scripts/supervised_teaching_from_current_hold.py`
- `scripts/current_hold_ui_teleop.py`
- Jetson 배치 대상 entrypoint의 `finally` / Stop 경로

이 경로들은 모두 종료 때 `bus.disconnect(disable_torque=False)`를 명시한다. Stop은 중단 flag만 설정하며 `disable_torque()`를 호출하지 않는다. 따라서 **이 검증된 경로의 코드상** 결과는 다음과 같다.

```ini
TORQUE_OFF_ON_SESSION_END = NO
```

이는 과거 실기에서 세션 사이 Torque가 OFF로 관측된 주체를 확정한 것이 아니다. 그 실제 상태 변화의 주체/원인은 계속 `UNKNOWN`이며 이번 critical path에서 추가 조사하지 않았다.

## 최소 통합

새 `scripts/single_session_demo.py`는 별도 제어 framework가 아니라 기존 두 함수를 이어 붙이는 얇은 orchestration entrypoint다.

```text
same exclusive follower/leader connection
  → restore_hold()
  → raw Goal exact copy 1회
  → Torque ON 1회
  → 3초 HOLD stability
  → atomic raw-write gate 종료
  → disconnect 없이 teaching Goal firewall로 handoff
  → 동일 연결의 fresh diagnostics를 pre-connect 기준으로 사용
  → run_teaching_from_hold()
  → fresh origins / first Goal skip / recorder / 2° common-fraction slew
  → teaching 종료 뒤에만 disconnect(disable_torque=False)
```

`OneShotRawWrites.handoff_to_teaching()`은 Goal_Position 1회와 Torque_Enable 1회가 모두 완료된 뒤에만 raw sync-write gate를 해제한다. config/individual torque API 차단은 유지되고, 즉시 기존 armed-Goal-only teaching firewall이 설치된다.

## 검증

### 로컬

- 관련 회귀 `125/125 PASS`
- compile PASS
- 기본 CLI dry-run PASS
- `git diff --check` PASS

통합 fake에서:

- follower connect `1회`
- HOLD→teaching 사이 disconnect `0회`
- Goal raw exact copy `1회`
- Torque OFF→ON packet `1회`
- Torque OFF packet `0회`
- 3초 HOLD 후 teaching 3초 settle 및 fresh origin
- first Goal skipped
- recorder armed / manifest complete
- 큰 Elbow 요청 `+5.3°`가 `+2.0,+2.0,+1.3°`로 분할
- maximum emitted arm step `2.0°`
- 최종 disconnect argument `False`, fake Torque ON 유지

### Jetson 격리 설치본

대상:

```text
/home/jetson3/so101-current-hold-teaching-20261014/
```

기존 atomic/teaching 파일과 테스트는 아래에 백업했다.

```text
deploy-single-session-20261015/backup/
```

배치 파일 SHA-256은 로컬과 일치했다. 설치 Python `/home/jetson3/.local/share/uv/tools/lelab/bin/python` 3.14.7에서 compile PASS 및 fake `84/84 PASS`. 기본 entrypoint는 다음을 출력했다.

```json
{"entrypoint":"SINGLE_SESSION_DEMO_DRY_RUN_ONLY","serial_open":0,"motor_command":0,"goal_write":0,"torque_write":0,"config_write":0,"hold_to_teaching_without_disconnect":"READY_FAKE_ONLY"}
```

검증 후 고정 포트 helper 결과는 `/dev/ttyACM0 FREE`, `/dev/ttyACM1 FREE`. SSH는 종료했다. LeLab 상태를 추정한 세 URL은 `404 Not Found`여서 제어 inactive의 근거로 사용하지 않았으며 서비스는 변경·재시작하지 않았다.

## 결과

```ini
TORQUE_OFF_ON_SESSION_END = NO              # 검증된 entrypoint 코드 범위
SINGLE_SESSION_DEMO_READY = PASS_FAKE_DEPLOYED
HOLD_TO_TEACHING_WITHOUT_DISCONNECT = PASS_FAKE
TWO_DEGREE_SLEW_LIMITER = PASS
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
SERIAL_LIVE = false
NEXT_LIVE_COMMAND = RUN SINGLE SESSION DEMO
```

실제 실행 전에는 현장 `arm supported / physical non-contact / surroundings clear / emergency stop ready` 확인과 LeLab control inactivity 및 양 포트 독점 확인이 다시 필요하다.

- 실제 single-session demo: `NOT_RUN`
- 이슈 갱신: `NOT_RUN`
- Git: `NOT_COMMITTED / NOT_PUSHED`
