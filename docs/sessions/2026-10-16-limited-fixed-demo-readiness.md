# 2026-10-16 제한된 고정 데모 readiness 감사

## 범위와 결론

카메라 독립 검증은 측정만 완료했다. 새 프레임 12표본 평면 오차 RMS는
`10.604 mm`, 최대는 `19.817 mm`이며 원인은 아직 분리되지 않았다. 이 결과를
보정 완료나 로봇 집기 정확도로 승격하지 않았고, 마커·카메라 설정·검증점은
변경하지 않았다.

목표를 약통 하나, 고정 집기 위치 하나, 고정 바구니 하나의 감독 데모로 줄였다.
실제 로봇 serial open, Goal/Torque/config write 및 모터 동작은 모두 `0/NOT_RUN`이다.

## 실제 adapter와 calibration 감사

- `SO101ReadOnlyStatusAdapter`: 실제 follower의 Goal/Present/Torque/Moving/Temperature를
  상태 변경 없이 읽도록 구현돼 있다. 일반 `SO101Follower.connect()`를 사용하지 않고
  bus를 `handshake=False`로 연다. 쓰기 API를 차단하고 종료 시
  `disconnect(disable_torque=False)`를 요구한다. 아직 Jetson 실제 상태 조회는
  `NOT_RUN`이다.
- `MockRobotAdapter`: mock 단계 실행만 구현돼 있다.
- `LiveRobotAdapter`: fail-closed placeholder다. Goal 전송, gripper close/open,
  lift, transport, place, return을 수행하는 실제 adapter는 **미구현**이다.
- follower servo calibration 파일은 Jetson에 존재한다.
  `/home/jetson3/.cache/huggingface/lerobot/calibration/robots/so_follower/so-101.json`,
  SHA-256 `2f74c1303b2fce03576eff539329e1185a652e2d551caa1ec82b026dafe29c2e`다.
  과거 실기에 쓰인 장치별 raw homing/range이지만 새 작업대 제한 데모에서 fresh
  상태·방향·범위를 재확인한 것이 아니므로 현재 상태는 `UNVERIFIED_NEW_DEMO`다.
- 과거 GRASP TCP config는 `OFFLINE_CANDIDATE_ONLY`다. 새 환경에서 유효하다고
  확인된 TCP는 없다.
- Jetson 활성 Astra 설정의 `T_B_W`는 `null`이다. 새 환경의 유효한
  작업대→로봇 베이스 변환은 없다. 따라서 약통 camera/table XY를 로봇 목표로
  변환하는 동작은 금지 상태를 유지한다.

## Torque lifecycle

Jetson 설치 SDK에서 일반 `SOFollower.connect()`는 bus connect 뒤 필요 시 calibration,
camera connect, `configure()`를 호출한다. `configure()`의 torque-disabled context는
모터 설정을 쓰고 context 종료 시 Torque를 다시 enable할 수 있다. 일반
`disconnect()`는 설정에 따라 torque disable을 수행한다. 과거 single-session에서는
절차의 Torque write가 `0`인데 Goal raw copy 이후 Torque가 OFF→ON으로 관측됐다.
그 실제 writer는 아직 `UNKNOWN/NOT_CONFIRMED`다.

따라서 read-only adapter는 이 경로를 우회하지만, 실제 motion adapter는 이 문제를
해결하지 않았다. `torque_lifecycle=unverified_unexpected_off_to_on_observed`를 독립
readiness 항목으로 추가해 티칭·고정 데모·전체 분류가 이를 숨기지 못하게 했다.

## 최소 코드 변경

작업별 readiness를 다음처럼 정리했다.

- `supervised_teaching`: robot identity, joint calibration, Torque lifecycle,
  explicit live enable. 티칭이 만들어야 하는 `motion_paths`는 선행 조건에서 제외했다.
- `fixed_demo`: robot identity, joint calibration, TCP, taught motion paths,
  Torque lifecycle, explicit live enable. camera intrinsic, camera↔table,
  table↔robot, basket opening은 요구하지 않는다.
- `full_sort`: 기존 전체 조건에 Torque lifecycle을 추가했다.
- 기존 호출 호환용 `supervised_motion`은 `fixed_demo`와 같은 조건으로 유지했다.

이 변경은 readiness 판정만 다루며 motion adapter, recovery 실행기, 승인 문자열,
새 상태 파일을 만들지 않는다.

## 오프라인 검증

- sorter 관련 단위 테스트: `30/30 PASS`
- CLI `status`: `serial_open=0`, `camera_open=0`, `motor_write=0`
- `supervised_teaching`: `joint`, `torque_lifecycle`, `robot.live_enabled` 때문에 BLOCKED
- `fixed_demo`: `joint`, `tcp`, `motion_paths`, `torque_lifecycle`,
  `robot.live_enabled` 때문에 BLOCKED
- `fixed_demo`는 camera/table calibration 부재 때문에 차단되지 않음
- `full_sort`는 camera/table/TCP/path/Torque lifecycle을 계속 요구함
- Python compile, `git diff --check`: PASS

전체 legacy discovery도 실행했으나 현재 로컬 Python에 `cv2`가 없어 8개가
import/error였고, 과거 600 mm reference를 기대하는
`test_diagnose_aruco_reference_gaps` 1개가 새 ID0–1 좌표 `527.324 mm`와
불일치해 실패했다. 총 `510`개 실행 결과는 `1 FAIL, 8 ERROR, 4 SKIPPED`이며
이번 readiness 변경으로 인한 회귀 통과로 표현하지 않는다.

## 첫 시험과 다음 motion 후보

실제 motion 전 첫 시험은 read-only 상태 확인 한 번이다.

```bash
python3 -m medicine_sorter --config configs/system.example.json robot-status
```

대상 후보는 follower `/dev/ttyACM1`, expected serial `5AE6058306`이다. 실행 직전
canonical node와 serial을 fresh 대조해야 한다. 이 시험은 현재 자세에서 목표 자세,
속도, 이동 경로가 모두 `NONE`이며 Goal/Torque/config write가 없어야 한다. 종료는
`disconnect(disable_torque=False)`이고 partial failure에도 serial과 lock을 해제한다.

통과 기준은 올바른 follower identity, exclusive port, 30개 raw read 응답,
`state_change_writes=0`, 종료 후 port free다. 식별 불일치, 다른 owner, SDK 계약 불일치,
통신 오류, write attempt가 하나라도 있으면 즉시 중단하며 재시도하지 않는다.

그 다음 첫 motion 후보는 전체 자동 집기가 아니라 기존 relative-start 방식으로
**현재 자세→고정 약통의 물리적으로 확인된 집기 전 접근 자세** 하나를 티칭·기록하는
감독 시험이다. 시작 자세는 fresh follower/leader origin과 정지·비접촉을 확인한
현재 자세, 목표는 사용자가 실제 간극을 보며 정한 비접촉 pre-approach이며 camera XY나
임의 높이를 사용하지 않는다. 기존 emitted joint step 상한 `2°`를 유지하고 사용자가
leader를 천천히 움직이는 경로만 기록한다. 의도하지 않은 접촉·큰 움직임·Torque 변화·
통신 오류 시 즉시 stop하고, grasp/운반/놓기/복귀는 이어서 실행하지 않는다.

이 motion 후보는 현재 단일 진입점에 검증된 live adapter가 없고 Torque lifecycle도
미확정이므로 아직 `BLOCKED/NOT_RUN`이다.

## 기록 상태

```ini
CAMERA_INDEPENDENT_ACCURACY = UNRESOLVED
LIVE_MOTION_ADAPTER = NOT_IMPLEMENTED
JOINT_CALIBRATION_FOR_NEW_DEMO = UNVERIFIED
TCP_FOR_NEW_DEMO = MISSING
TABLE_TO_ROBOT_BASE = MISSING
TORQUE_LIFECYCLE = UNRESOLVED
ROBOT_IO = 0
MOTOR_COMMAND = 0
GIT = COMMITTED_AND_PUSHED_AS_d0b00e0
```
