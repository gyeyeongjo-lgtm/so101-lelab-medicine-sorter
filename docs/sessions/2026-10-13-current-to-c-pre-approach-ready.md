# 2026-10-13 CURRENT→C PRE_APPROACH 짧은 경로 OFFLINE READY·gripper blocker

## 범위와 시작 상태

사용자는 canonical PICK_READY 복귀를 중단하고, C PRE_APPROACH→PICK_READY 복귀 실기 2가 멈춘 뒤의 현재 follower pose에서 C PRE_APPROACH로 바로 이어지는 짧은 경로만 오프라인으로 생성하도록 지시했다. 이번 작업에는 actual motor, Goal/Torque, USB, service 변경이 포함되지 않는다.

직전 STOPPED 뒤 read-only 3회가 동일했던 기준은 다음과 같다.

```text
CURRENT arm =
[+11.736264,-22.197802,+71.164835,-27.032967,-14.197802] deg

fresh gripper = +2.264382%
GRASP TCP     = [-45.732137,-290.790629,+89.193802] mm
Moving        = all 0
Temperature   = max 40 C
Torque        = all 1 / unchanged
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED
```

live 실행기는 이 저장값을 현재값으로 가정하지 않는다. first target 전 fresh feedback을 다시 읽고 축별 start tolerance(Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`)를 통과해야 한다.

고정한 기존 값:

```text
C robot XY = [-62.635354,-295.315566] mm
GRASP TCP   = [-4.748354,-12.033741,-124.531737] mm
C PRE_APPROACH =
[+14.845130,-16.993354,+70.591582,-37.176891,-12.536328] deg
```

table→robot calibration, C XY, PIN/GRASP TCP 분리, endpoint와 orientation은 변경하지 않았다.

## 오프라인 비교와 선택

start→target joint delta는 다음과 같다.

```text
[Pan +3.108866, Lift +5.204448, Elbow -0.573253,
 Flex -10.143924, Roll +1.661474] deg
```

`DIRECT_COUPLED`, exact `WRIST_LEAD_2DEG`, exact `WRIST_LEAD_3DEG`를 비교했다. 세 후보 모두 nominal 11 waypoint와 TCP-point proxy를 통과했으므로 2° lead는 유일한 기하 해가 아니라 직전 forward 실기에서 확인한 Wrist terminal lag를 반영한 정책 선택이다. 3° 이상 Wrist-only 자동 escape를 만들지 않았다.

추천 경로는 Flex만 `-1° × 2` 보낸 뒤 actual feedback에서 나머지 9개 coupled waypoint를 다시 만드는 `WRIST_LEAD_2DEG`다.

```text
waypoints                        = 11 nominal
maximum per-joint step           = 1.000000 deg
GRASP TCP start                  = [-45.732137,-290.790629,+89.193802] mm
GRASP TCP after Wrist lead       = [-46.253094,-293.298410,+95.151348] mm
GRASP TCP endpoint               = [-62.635356,-295.315566,+100.000001] mm
TCP Z progression                = monotonic increasing
minimum predicted delta Z/step   = +0.537511 mm
C XY distance                    = 17.498394 -> 16.505980 -> 0.000002259 mm
minimum TCP table-point margin   = +34.534802 mm
non-base link-origin margin      = +40.222700 mm
self-collision centerline proxy  = 64.775222 mm / PASS
minimum servo margin             = 23.846165 deg
final GRASP TCP error            = 0.000002570 mm
tool-axis / jaw-axis error       = 3.089708 / 0.673228 deg
full mesh / environment          = NOT_VERIFIED
```

`non-base link-origin` 최소값은 고정 shoulder origin이 지배하므로 실제 finger/link mesh clearance의 단조 증가 증거로 사용하지 않는다. table 판정은 TCP-point proxy이며 full mesh/environment는 계속 `NOT_VERIFIED`다.

## 실행 계약

기존 `live_c_pre_approach_only` runner와 continuous-following infrastructure를 재사용했다. 새 control framework는 만들지 않았다.

CURRENT route는 다음 순서로만 동작한다.

```text
fresh start gate
-> Wrist Flex -1 deg
-> Wrist Flex -1 deg
-> fresh phase gate
-> PASS일 때만 actual feedback 기준 coupled remainder 재생성
-> C PRE_APPROACH final gate
```

Wrist phase gate는 의도 방향과 target `±0.5°`, `Moving=0`과 settle, non-commanded drift `≤1°`, actual FK `GRASP_TCP_Z_after > before`, Temperature `≤55°C`, feedback freshness/communication을 확인한다. FK용 URDF는 live에서 명시적으로 받아 SHA `443d38d…67236`을 검증한다. 하나라도 실패하면 coupled target을 보내지 않고 현재 Goal/torque를 유지한 채 STOP한다.

final tolerance는 Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`, gripper `2.0 pp`다. Present_Load는 numeric gate가 아니라 diagnostic only다.

## 새로 확인된 live blocker

현재 gripper feedback `2.264382%`는 기존 `c_grasp_open=35.0%`보다 닫힌 쪽이며, 성공 teleop 기록도 grasp에서 `61.409%→4.671%`로 닫혔다. 직전 C PRE_APPROACH 실기에서는 두 finger 끝이 C에 닿았다는 human FAIL이 있었다. 5축 TCP/centerline proxy는 finger sweep을 포함하지 않는다.

따라서 current-route runner는 기존 `c_grasp_open` 명령에서 가져온 `35.0%`를 최소 fresh opening으로 사용하며 initial/verified/pre-send feedback에서 세 번 fail-closed 확인한다. 현재 `2.264382%`에서는 arm `SEND=0`으로 차단된다. 별도 gripper-open-only 계획·현장 finger sweep clearance·사용자 승인이 생기기 전에는 `RUN CURRENT TO C PRE APPROACH`를 요청하지 않는다.

## 검증과 배포

```text
planner/live/continuous/transport tests = 61/61 PASS
py_compile                              = PASS
JSON validation                         = PASS
git diff --check                        = PASS
local explicit dry-run                  = PASS
Jetson Python                           = 3.14.7
Jetson explicit dry-run                 = PASS
dry-run result                          = no port opened; no send_action
```

Jetson의 기존 service·USB·실기 폴더를 변경하지 않고 다음 새 전용 폴더에 runner/config/URDF 사본만 배치했다.

```text
/home/jetson3/so101-current-to-c-pre-approach-20261013/
```

local/Jetson SHA 8개가 모두 일치한다. 배포 중 actual motor/Goal/Torque command와 follower port open은 `0`이다.

## 판정

```text
CURRENT_TO_C_PRE_APPROACH_OFFLINE = PASS
CURRENT_TO_C_LIVE                 = BLOCKED_GRIPPER_NOT_OPEN
PRE_APPROACH_PASS                 = false
hardware command                  = 0
full mesh/environment             = NOT_VERIFIED
commit/push                       = INCLUDED_IN_2026-10-13_COMMIT / origin/fix/usb-recording
```

다음 사용자 행동은 현재 자세를 유지한 채 실제 finger opening sweep이 C·table·주변과 비접촉인지 현장에서 확인하고, 별도 gripper-open-only plan 승인을 요청하는 것이다.
