# Fixed-demo motion smoothing A/B

일자: 2026-10-27

## 범위

- 성공한 티칭 pose, 위치, IK, calibration, GRASP TCP를 변경하지 않는다.
- servo gain과 Torque 정책을 변경하지 않는다.
- 2° limiter를 제거하지 않고 hard safety cap으로 유지한다.
- 기존 original trajectory를 보존하고 smooth 후보는 A/B 가능한 별도 경로로 둔다.
- 실제 첫 시험은 전체 pick-and-place가 아니라 동일 시작/종료 pose 사이 한 짧은
  free-space segment만 허용한다.

## 기존 코드 및 로그 감사

기존 `smooth_interpolation`은 이미 전 관절에 동일한 cubic smoothstep
`s(t)=3t²-2t³`를 사용한다. duration은 velocity/acceleration 제한에서 계산하고,
관절당 최대 emitted delta가 arm 2°/gripper 2 pp를 넘으면 sample count를 늘린다.
따라서 단순히 같은 식을 다시 추가하는 것은 개선이 아니다.

기존 executor는 각 Goal write 직후 `sleep(control_period_s)`를 수행한다. 이 구조는
serial write 자체의 시간과 scheduler 지연이 명령 간격에 더해지는 relative cadence다.
최근 설정은 0.05 s지만 과거 성공 baseline은 0.1 s였다. 큰 이동의 중앙부에서
`20 deg/s × 0.1 s ≈ 2°`가 가능하므로 계단이 관측될 가능성은 있으나, current
fixed-demo의 실제 cycle log가 없으므로 2° cap이 실제 jitter의 원인이라고 확정하지
않는다.

기존 성공 run은 command timestamp/position, Present, Goal, Moving을 cycle별로
저장하지 않았다. web 상태에는 stage와 온도, write count만 남는다. Jetson에
read-only SSH로 기존 로그를 확인하려 했으나 port 22 timeout이었다. 그러므로 실제
요청 지표는 현재 `NOT_AVAILABLE`; 다른 과거 teleop trace나 계획값을 current
pick-and-place 실측으로 대체하지 않았다.

## 구현

### Original 보존

기존 `run`, `run --auto`, web은 계속 `motion_profile=original` 기본값을 사용한다.
pose JSON과 모든 위치/보정값은 수정하지 않았다.

### Smooth 후보

- 모든 arm joint는 동일한 elapsed-time 기반 cubic `s(t)`를 사용한다.
- absolute deadline cadence로 실행해 write 지연을 다음 interval에 누적하지 않는다.
- deadline이 지난 sample은 back-to-back으로 몰아 보내지 않고 건너뛴다.
- late sample이 2°/2 pp를 넘으려 하면 한 관절만 자르지 않고 전체 joint delta에 같은
  fraction을 적용해 synchronized hard cap을 유지한다.
- 작은 최소 step은 강제하지 않는다. Elbow/Lift deadband 보상을 가장한 gain, Torque,
  offset 변경도 없다.

### Logging 및 분석

`motion-test`의 JSONL은 Git ignored `.local/fixed-demo-motion/` 안의 새 파일만 허용하고
기존 파일은 덮어쓰지 않는다. 각 command cycle에 다음을 기록한다.

- monotonic command timestamp와 UTC 관측 시각
- scheduled offset, stage/profile/sequence
- command joint position
- Present/Goal joint position과 Goal−Present
- Moving

`motion-compare --actual-log`는 관절별 command interval mean/std, emitted delta list와
max, direction reversals, Present velocity finite-difference mean/std/max,
Goal−Present mean/std/peak-to-peak/direction reversals, Moving true cycle count를 계산한다.

`segment_settle_timeout`도 generic 문자열만 남기지 않고 마지막 target, Goal, Present,
Goal−Present, target−Present, Moving과 profile을 fault에 보존한다.

## 안전 범위

`motion-compare`는 ignored pose JSON만 읽고 robot serial을 열지 않는다.
`motion-test`는 다음을 모두 만족해야 한 segment만 실행한다.

- 명시적 `--step`
- 서로 다른 두 arm pose; gripper pose 금지
- 현장 Enter 확인 두 번
- 현재 arm 5축이 `--from-pose`와 각 1° 이내
- Moving all zero
- 시작 온도 기본 `<50°C`
- gripper Goal 미변경
- 기존 velocity/acceleration/travel/bounds/2°/settle/temperature/Overload guard
- 오류·Ctrl+C 시 fresh current HOLD
- 종료 `disconnect(disable_torque=False)`

현재 로봇의 물리 자세와 짧은 free-space start/end가 아직 확정되지 않았으므로 실제
명령은 제공하거나 실행하지 않는다.

## 검증

- fixed-demo+web: `57/57 PASS`
- sorter: `30/30 PASS`
- Python compile: `PASS`
- CLI help: `PASS`
- `git diff --check`: `PASS`
- hardware serial open: `0`
- motor command: `0`
- Jetson deploy: `NOT_RUN`
- actual trajectory log: `NOT_AVAILABLE`
- actual free-space motion: `NOT_RUN`

```makefile
JITTER_ROOT_CAUSE = UNCONFIRMED_CURRENT_FIXED_DEMO_CYCLE_LOG_NOT_AVAILABLE
ORIGINAL_COMMAND_INTERVAL = PLANNED_0.1S / MEASURED_NOT_AVAILABLE
ORIGINAL_MAX_STEP = REQUIRES_JETSON_POSE_OFFLINE_COMPARE
ORIGINAL_DIRECTION_REVERSALS = REQUIRES_JETSON_POSE_OFFLINE_COMPARE

SMOOTHING_METHOD = SHARED_CUBIC_SMOOTHSTEP_ABSOLUTE_DEADLINE
CONTROL_PERIOD = 0.05S
SMOOTH_MAX_STEP = <=2DEG_HARD_CAP / ACTUAL_NOT_RUN
EXPECTED_IMPROVEMENT = NO_RELATIVE_SLEEP_DRIFT_OR_EXPIRED_TICK_BURST

TORQUE_GAIN_CHANGED = NO
IK_CHANGED = NO
READY_FOR_SMOOTH_MOTION_TEST = NO
```
