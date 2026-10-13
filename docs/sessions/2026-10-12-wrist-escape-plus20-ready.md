# staged Wrist escape 후보 비교 및 +20 전용 실기 준비

날짜: 2026-10-12
상태: `OFFLINE_VALIDATED / LIVE_NOT_RUN`
Phase C: `HOLD`
하드웨어 명령: `0`

## 기준선

```text
SAFE_ESCAPE_2DEG = FAIL / NO_EFFECTIVE_MOVEMENT
verified_abs_load_limit = NOT_DEFINED
Present_Load = signed diagnostic only
current arm = [+1.450549,+18.153846,+14.725275,+8.307692,+16.219780] deg
current GRASP TCP = [-1.047681,-369.737597,+55.316363] mm
table reference Z = 54.659 mm
full mesh/environment collision = NOT_VERIFIED
```

기존 +40 후보 전체를 한 번에 실행하지 않고, 실제 목적을 Lift/Elbow가 다시
움직일 수 있는 하중 조건까지의 최소 탈출로 제한했다.

## +10/+20/+30/+40 후보 비교

모든 endpoint는 반복 횟수로 정하지 않고 FK에서 정확한 cumulative Z gain을
만드는 Wrist Flex 각도를 이분 탐색했다. endpoint까지 `≤2°`로 분할한 뒤 각
waypoint의 Z/table monotonicity, servo bounds, centerline proxy를 재검증했다.

| 후보 | endpoint joints Pan/Lift/Elbow/Flex/Roll [deg] | WP | Z gain | XY drift | tool-axis change | jaw-axis change | final table margin | min self-collision margin |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `WRIST_ESCAPE_Z_PLUS_10` | `[+1.450549,+18.153846,+14.725275,+4.303791,+16.219780]` | 3 | `+10.000000 mm` | `8.259301 mm` | `4.003901°` | `3.844474°` | `+10.657363 mm` | `64.775222 mm` |
| `WRIST_ESCAPE_Z_PLUS_20` | `[+1.450549,+18.153846,+14.725275,+0.504669,+16.219780]` | 4 | `+20.000000 mm` | `15.432549 mm` | `7.803024°` | `7.491990°` | `+20.657363 mm` | `64.775222 mm` |
| `WRIST_ESCAPE_Z_PLUS_30` | `[+1.450549,+18.153846,+14.725275,-3.132839,+16.219780]` | 6 | `+30.000000 mm` | `21.665359 mm` | `11.440531°` | `10.983738°` | `+30.657363 mm` | `64.775222 mm` |
| `WRIST_ESCAPE_Z_PLUS_40` | `[+1.450549,+18.153846,+14.725275,-6.640868,+16.219780]` | 8 | `+40.000000 mm` | `27.063709 mm` | `14.948560°` | `14.350370°` | `+40.657363 mm` | `64.775222 mm` |

공통 결과:

```text
maximum joint step <= 2 deg       PASS
GRASP TCP Z monotonic increase    PASS
table proxy monotonic nondecrease PASS
self-collision centerline proxy   PASS
servo bounds                      PASS
full mesh/environment             NOT_VERIFIED
XY acceptance threshold           NOT_DEFINED
```

## 추천

```text
recommended first live stage = WRIST_ESCAPE_Z_PLUS_20
expected Z gain             = +20.000000 mm
expected final TCP Z        = +75.316363 mm
XY drift                    = 15.432549 mm
tool-axis change            = 7.803024 deg
jaw-axis change             = 7.491990 deg
```

+20은 +40 대비 XY drift가 `11.631160 mm`, tool-axis 변화가 `7.145536°`,
jaw-axis 변화가 `6.858380°` 작다. table clearance는 증가하고 servo/centerline
proxy를 통과한다. 검증된 XY 허용 상한을 임의로 만들지 않았으며 실제 drift를
그대로 남겼다.

## +20 전용 live runner 계약

`scripts/live_wrist_escape_z_plus_20.py`는 dry-run이 기본이며 exact scope
`c_pick_wrist_escape_z_plus_20_only` 외에는 live를 거부한다.

- 시작 시 fresh feedback이 저장된 현장-confirmed pose에서 `0.5°` 이상 바뀌면
  첫 송신 전에 차단한다.
- 시작 GRASP TCP Z에 `+20 mm`인 target Z를 고정한다.
- 매 step actual fresh pose에서 remaining Z를 FK로 다시 계산하며 Wrist Flex만
  최대 `2°` 명령한다.
- 각 step에서 intended-direction actual movement `≥50%`, actual TCP Z 증가,
  non-commanded drift `≤1°`, Temperature `≤55°C`, feedback/communication/settle,
  servo bounds, table proxy 비악화, centerline self-collision proxy를 검사한다.
- Goal raw, Present raw/deg, achieved ratio, Moving, signed Present_Load와 delta,
  Temperature, GRASP TCP XYZ, cumulative Z, collision proxy를 step마다 출력한다.
- `Present_Load` absolute threshold는 사용하지 않는다.
- 첫 FAIL에서 추가 target을 생산하지 않고 `stop_commands()` 후 torque와 현재
  Goal을 유지한 채 STOP 확인으로 이동한다.
- +30/+40 자동 continuation, Lift/Elbow probe, HOME/SAFE_HIGH는 없다.

+20 성공 후에도 runner는 멈춘다. 이후 fresh pose를 읽어 Lift/Elbow/Wrist
sensitivity와 독립 2° probe를 **offline으로만** 계획해야 한다.

## 검증

```text
planner + live wrist runner + escape verification + legacy safe runner = PASS
recorded pose + safe-home + transport regression                         = PASS
related total                                                            = 44/44 PASS
py_compile / JSON parse / diff-check                                     = PASS
CLI dry-run                                                              = PASS
follower port open                                                       = 0
motor / Goal / Torque write                                              = 0
actual +20 run                                                           = NOT_RUN / NOT_AUTHORIZED
Phase C                                                                  = HOLD
```

## 첫 live 시작 시도 — 첫 송신 전 차단 및 수정

사용자 승인 뒤 canonical follower `/dev/ttyACM1=5AE6058306`, LeLab active,
teleoperation/recording/inference inactive, privileged `fuser rc=1`을 확인했다.
write 없는 3회 fresh Present raw는 모두 다음과 같았다.

```text
Pan/Lift/Elbow/Flex/Roll/Gripper = 2118/2161/2151/2175/2049/446
```

첫 live runner는 실제 target을 보내기 전에 다음 오류로 종료했다.

```text
ABORT: PreflightError: start_pose_not_verified
Goal write / motor target = 0
```

runner가 자체 fresh telemetry와 site-reference 비교는 수행했지만 transport 내부의
기존 `verify_start_pose()` latch를 호출하지 않은 wiring 누락이 원인이었다.
사용자 `STOPPED` 뒤 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; 종료 후 read-only
Present raw도 위 값과 정확히 같았다.

수정본은 fresh telemetry 확인 후 기존 `verify_start_pose()`를 호출하고, latch가
arm된 뒤 Goal/Present/Load/Temperature before-sample을 다시 읽는다. fake transport도
latch 없이 `send_goal()`을 호출하면 즉시 실패하도록 보강했다.

```text
related tests = 44/44 PASS
local/Jetson runner SHA = 07ae068e4b5e4c1f2d1eba4b3aee45807842147a5f63b5e0642c63cfa4ca6759
Jetson installed Python py_compile = PASS
Jetson dry-run = PASS / no port opened / no send_action
corrected live retry = NOT_RUN / NOT_AUTHORIZED
```
