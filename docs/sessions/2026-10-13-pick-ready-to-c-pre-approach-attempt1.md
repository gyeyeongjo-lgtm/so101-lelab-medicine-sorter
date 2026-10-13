# 2026-10-13 PICK_READY→C PRE_APPROACH 실기 1 — human geometry FAIL

## 승인 범위

사용자 승인:

```text
RUN PICK READY TO C PRE APPROACH
```

허용 범위는 기록된 canonical PICK_READY에서 새 PICK GRASP TCP 기준 C PRE_APPROACH까지 한 번 이동하는 것이었다. APPROACH, gripper close, LIFT, RED PLACE는 포함하지 않았다.

변경 금지 기준선은 유지했다.

```text
table→robot calibration = unchanged
C robot XY              = [-62.635354,-295.315566] mm
PIN TIP TCP             = calibration only
PICK GRASP TCP          = [-4.748354423,-12.033741060,-124.531737248] mm
C PRE_APPROACH target   = [+14.845130,-16.993354,+70.591582,-37.176891,-12.536328] deg
```

## start gate와 실행

fresh start는 저장 PICK_READY와 일치했다.

```text
START_POSE_CONFIRMED = PICK_READY

Pan    -4.263736°
Lift  -68.703297°
Elbow +68.879121°
Flex   +8.131868°
Roll  -23.516484°
```

exclusive ownership, fresh feedback, calibration servo bounds, Temperature `<=55°C`, continuous-following과 final `Moving=0` gate를 통과해 기존 staged path를 실행했다.

```text
generated waypoints = 63
target sent         = 63 / 63
log actions         = SEND 63 / final PAUSE 2
ABORT               = 0
maximum Temperature = 37°C
maximum absolute following error = 1.491318°
automatic retry     = 0
```

## final feedback

runner의 final stable verification에서 Moving은 전 축 `0`이었다.

```text
Present arm =
[Pan +14.461538,
 Lift -16.571429,
 Elbow +70.725275,
 Flex -35.912088,
 Roll -12.879121]°

Present - target =
[-0.383592,+0.421925,+0.133693,+1.264803,-0.342793]°
```

사용자 `STOPPED` 뒤 read-only 3회 표본은 동일했다.

```text
Present arm = [+14.549451,-16.571429,+70.725275,-35.912088,-12.879121]°
Present raw = [2267,1766,2788,1672,1718,450]
Goal raw    = [2270,1761,2786,1657,1721,447]
Moving      = [0,0,0,0,0,0]
Load diagnostic = [-24,+32,+20,+72,-24,+24]
Temperature max = 37°C
Torque_Enable   = [1,1,1,1,1,1]
```

`Present_Load`는 numeric safety gate가 아니라 signed diagnostic으로만 기록했다.

## 실제 FK와 현장 판정

STOPPED 뒤 fresh actual pose의 새 GRASP TCP FK는 다음과 같다.

```text
actual GRASP TCP = [-60.641952,-293.652536,+93.607879] mm
nominal endpoint = [-62.635356,-295.315566,+100.000001] mm
actual→nominal distance = 6.899170 mm
C XY distance          = 2.596020 mm
```

사용자 현장 관찰:

```text
FAIL
거의 비슷했고 gripper 두 finger 끝이 C에 닿음
```

63개 waypoint의 controller tracking 완료는 실제 gripper geometry 정렬 성공을 뜻하지 않는다. 두 finger 사이 opening center가 C에 정렬되어야 한다는 현장 acceptance를 통과하지 못했으므로 사람 판정을 우선해 다음과 같이 고정한다.

```text
PICK_READY_TO_C_PRE_APPROACH_ATTEMPT1 = FAIL
PRE_APPROACH_PASS = false
FAIL_REASON = HUMAN_OBSERVED_FINGERTIP_CONTACT_BEFORE_ACCEPTABLE_ALIGNMENT
APPROACH = NOT_RUN
GRASP    = NOT_RUN
LIFT     = NOT_RUN
PLACE    = NOT_RUN
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED
```

이 관찰만으로 table→robot calibration, C XY, GRASP TCP, IK endpoint를 수정하지 않았다. PIN TIP 정렬 재발 증거도 없으며 fingertip/full mesh geometry는 계속 `NOT_VERIFIED`다.

## 로그

```text
local log = .local/pick-ready-20261013/pick_ready_to_c_pre_approach_attempt1.jsonl
SHA256    = d84aa86c355550467e735007d2170af2decd767c2fda0345a66fe2345b21d935
rows      = 65
actions   = SEND 63 / PAUSE 2
```

원본 JSONL은 로컬 증거이며 커밋 대상이 아니다. 다음 live 동작은 현재 C PRE_APPROACH actual pose에서 canonical PICK_READY로 복귀하는 별도 경로를 오프라인 검증하고 사용자에게 다시 승인받은 뒤에만 수행한다.
