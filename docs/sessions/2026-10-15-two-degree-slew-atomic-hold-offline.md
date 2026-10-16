# 2° leader delta 분할 / ATOMIC_HOLD_RESTORE — offline only

## 승인 범위와 보존 상태

사용자 요청 A(2° 제한 유지 + 공통 interpolation fraction 분할), B(단일 exclusive session HOLD 복구 준비)만 구현했다. 실제 HOLD restore/teaching/Jetson 배치 승인이 아니다. 이번 턴은 SSH와 serial 연결도 하지 않았다.

직전 실제 관측은 Present raw `[2066,1098,2901,2503,1612,490]`, Goal all 0, Torque all OFF, Moving all 0, Tmax 37°C다. 사용자는 상태 변경을 의도했으며 팔 지지·정지·전체 비접촉이라고 확인했다. 이는 과거 관측/사용자 확인이며 이번 턴의 fresh 측정으로 표시하지 않는다. `TEACHING=ABORT_BEFORE_ARMING` 및 이전 실패 기록은 유지한다.

## A. 기존 2° guard를 유지한 coordinated slew

변경: `scripts/supervised_teaching_from_current_hold.py`, `tests/test_supervised_teaching_from_current_hold.py`.

- `MAX_ARM_COMMAND_STEP_DEG=2.0`은 그대로 읽어 사용한다. 전체 leader requested target에 먼저 기존 calibration/range·gripper guard를 적용한 뒤 하나의 공통 fraction을 사용해 candidate를 만든다. 각 cycle의 candidate에도 기존 2° guard를 다시 적용한다.
- `+5.3°` 단일축 요청은 fake command `+2.0°, +2.0°, +1.3°`로 전송된다. 다른 arm 축과 허용된 gripper 입력에도 같은 fraction을 적용한다. 부동소수 반올림이 2°를 넘기면 fraction을 축소하지, guard 값을 늘리지 않는다.
- 매 cycle 최신 leader 요청으로 재계산하며 미래 command queue는 만들지 않는다. 반전은 최신 방향을 따라가고, HOLD 시 previous를 진행하지 않으며, STOP 시 잔여 target을 보내지 않는다. previous는 실제 sender가 반환한 전송 target으로만 갱신한다.
- gripper의 닫힘 금지·최대 개방 `34.577723378%`·기존 2 percentage-point request guard를 유지한다. 큰 gripper 입력을 arm 분할로 감춰 허용하지 않는다. 이번 변경은 arm의 큰 delta에 대한 분할만 추가한다.
- `requests.jsonl`은 전체 requested target/guard 전 delta를 기록한다. `cycles.jsonl`과 first-sent 기록은 실제 emitted candidate와 전송 여부를 구별한다. 실제로 송신하지 않은 큰 요청을 첫 전송 Goal로 보고하지 않는다.
- `<2°`, `=2°`, `2–4°`, `>4°`, 음수/sign reversal, 다관절 공통분율, 1,000개 결정적 random 입력의 strict cap, HOLD/STOP, sender accepted target, full-target range/gripper regression을 검사했다. fake에서 확인한 최대 emitted arm command step은 `2.0°`다. 실제 encoder/raw 양자화 및 하드웨어 추종 결과는 이번에 검증하지 않았다.

기존 공유 relative-start 모듈의 2° 상수/검사, historical reference/exact-zero/quantized 판정, trajectory convergence tolerance, calibration, FK/GRASP TCP, torque/gain은 변경하지 않았다. 기존 LeLab UI/service에도 변경 없다.

## B. 단일 session ATOMIC_HOLD_RESTORE

신규: `scripts/atomic_hold_restore.py`, `tests/test_atomic_hold_restore.py`.

기존 recovery의 write retry·실패 시 torque OFF rollback은 이번 계약에 맞지 않아 사용하지 않는다. 기존 도구도 수정하지 않았다. 새 진입점 기본 실행은 비실기 계획 출력이며 하드웨어 SDK조차 import하지 않는다.

준비한 live 순서는 다음과 같다(이번에는 fake만 실행).

1. 명시적 `RUN ATOMIC HOLD RESTORE` 승인과 현장 지지/정지/비접촉/주변 clear/즉시 중단 준비/다른 controller inactive 확인을 요구한다. 새 audit 경로의 생성 가능 여부도 연결 전 검사한다.
2. 기존 `ExclusiveFollowerLease`의 프로그램 lock·LeLab 세 제어 inactive·canonical USB identity·포트 무점유를 확인한다. 버스 write firewall을 먼저 설치하고 `connect(handshake=False)` 한 번, tty `TIOCEXCL`, 자신만의 PID 소유권 확인으로 연결한다. `robot.connect/configure/send_action`은 사용하지 않는다.
3. fresh Present/Goal/Torque/Moving/개별 Temperature를 raw read한다. Torque all OFF·Moving0·정상 온도·raw 유효성을 검사하고, write 직전 재측정의 Present/Goal 불변을 확인한다.
4. 그 fresh Present raw 6축을 **그대로** Goal에 sync-write 1회, `normalize=False, num_retry=0`. degree→raw 계산은 없다. gripper도 관측 raw 그대로다.
5. 같은 세션에서 Goal exact readback, Torque all OFF, Present 불변, Moving0를 확인한다. enable 직전 다시 fresh 검사를 통과해야 한다.
6. `Torque_Enable={전 축:1}` sync-write packet을 한 번만 시도한다(`num_retry=0`). 축별 retry/enable helper/자동 OFF 토글은 쓰지 않는다.
7. ON 직후 먼저 Present/Goal/Torque/Moving/Temperature를 읽고 검사한 뒤 소유권을 재확인한다. 실제 관측 표본 사이 최소 3초 동안 exact Present 불변·Goal=intended raw·Torque ON·Moving0·정상 온도를 확인해야 `HOLD_RESTORED`다. 느린 서비스/소유권 조회 시간만으로 3초 표본 관측을 대체하지 않는다.
8. 예상 밖 Goal/Torque/Present/Moving/온도, 통신 오류, 소유권 상실, STOP이면 후속 write를 중단한다. 모호한 Goal/ON 결과도 재전송하지 않는다. close는 `disable_torque=False`이며 자동 rollback이나 teaching 연결 실행은 없다.

`atomic`은 **하나의 exclusive session 안의 순서 보장**이다. 여섯 servo가 하나의 하드웨어 transaction으로 성공함을 보장하지 않는다. ON 이후 실패하면 일부 또는 전부 Torque ON이 남을 수 있으며 자동으로 끄지 않는다. live에서는 현장 지지를 계속 유지하고 마지막 readback/오류를 보고해야 한다. 소유권 probe는 LeLab teleop/recording/inference 상태와 실제 port owner를 검사한다. 독립 replay 프로세스 자체의 inactive 여부를 이번 fake 결과로 확인했다고 주장하지 않으며, 향후 실행 전 모든 다른 제어 작업 inactive를 현장에서/프로세스 상태로 확인해야 한다.

## 검증 결과

로컬 fake/회귀: **149/149 PASS**. 새 atomic suite는 **32/32 PASS**. 직접 CLI의 기본 비실기 실행, compile, `git diff --check`도 PASS다.

검사 모듈: `test_atomic_hold_restore`, `test_supervised_teaching_from_current_hold`, `test_relative_start_teleop`, `test_teleop_cycle_trace`, `test_so101_exclusive_transport`, `test_recover_follower_hold`, `test_sync_follower_goal_to_present_only`, `test_temporary_elbow_direction_guard`.

atomic fake는 raw passthrough/정확한 쓰기 순서·횟수, Torque 부분/전체 ON 차단, Moving/온도/raw 부정값, sync 전·후 Goal/Torque 변경, Present drift, 통신 실패/부분 enable의 무재시도·무rollback, STOP, 잘못된 USB/포트 경쟁/동일 lock 경쟁/LeLab 재활성화, connect 내부 임의 write 차단, 단일 connect/disconnect와 lock release를 검증한다. fake의 write는 메모리 상태 변경일 뿐 실제 motor command가 아니다.

```ini
TWO_DEGREE_SLEW_LIMITER = PASS
MAX_EMITTED_STEP = 2.0 deg (FAKE_ARM_COMMAND)
ATOMIC_HOLD_RESTORE_READY = PASS
EXCLUSIVE_PORT_CONTROL = PASS
VALIDATION = LOCAL_OFFLINE_FAKE_ONLY
JETSON_DEPLOY = NOT_RUN
SERIAL_OPEN = 0
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
ACTUAL_HOLD_RESTORE = NOT_RUN
TEACHING = ABORT_BEFORE_ARMING
GRASP = NOT_RUN
LIFT = NOT_RUN
NEXT_LIVE_COMMAND = RUN ATOMIC HOLD RESTORE
```

위 NEXT는 별도 승인 후보일 뿐 실행이 아니다. 실제 실행 전 Jetson 격리 배치·설치 Python/SDK와 retry/지원 옵션 확인·새 현장 확인 및 동일 세션 fresh gate가 필요하다. 실제 teaching으로 자동 연결하지 않는다. HOME/SAFE_HIGH/recovery 일반화/9-combination/UI 복구 작업을 하지 않았다.

변경 `NOT_COMMITTED/NOT_PUSHED`; 이슈 갱신 `NOT_RUN`(대상 미지정). 기존 dirty worktree와 무관한 삭제/변경은 보존했다. 원본 로그·비밀번호·키·토큰·데이터셋은 커밋하지 않았다.
