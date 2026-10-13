# 2026-10-13 C PRE APPROACH→PICK_READY 복귀 실기 2 — waypoint 9 no-progress FAIL

## 승인 범위

사용자 승인:

```text
RUN C PRE APPROACH TO PICK READY
```

허용 범위는 직전 C PRE_APPROACH actual pose에서 canonical PICK_READY로 한 번 복귀하는 것이었다. APPROACH, gripper close, LIFT, place와 TCP·calibration·C XY 변경은 포함하지 않았다.

## preflight와 fresh start

teleoperation/recording/inference inactive, canonical follower identity와 exclusive ownership을 확인했다. fresh start는 저장된 `C_PRE_APPROACH_ACTUAL_ATTEMPT1`과 정확히 일치했고, 그 feedback으로 복귀 경로 `61` waypoint를 생성했다.

```text
fresh arm =
[+14.549451,-16.571429,+70.725275,-35.912088,-12.879121]°

START_POSE_CONFIRMED = C_PRE_APPROACH_ACTUAL_ATTEMPT1
generated waypoints  = 61
```

복귀 경로의 오프라인 검증 기준은 그대로였다.

```text
maximum per-joint step    = 1.0°
predicted GRASP TCP Z     = 93.607879 → 184.960142 mm, monotonic increase
predicted C XY distance   = 2.596020 → 94.924111 mm
minimum table proxy       = +38.948879 mm
self-collision proxy      = 64.775222 mm PASS
minimum servo margin      = 24.285725°
full mesh / environment   = NOT_VERIFIED
```

## 실행 결과

수정된 기존 stage 계약으로 실제 실행을 시작했다. waypoint `1–9`의 target만 송신했고, waypoint `9/61`에서 Shoulder Lift가 target을 충분히 추종하지 못했다.

```text
waypoint 9 target =
[+11.668462,-24.831764,+70.364113,-27.016156,-14.423422]°

fresh feedback at waypoint 9 =
[+11.736264,-22.197802,+71.164835,-27.032967,-14.197802]°

following error at waypoint 9 =
[+0.067802,+2.633962,+0.800723,-0.104724,+0.225620]°

Shoulder Lift following error = 2.633962°
Moving                       = all 0
Load diagnostic             = [0,132,52,0,24,0]
Temperature max             = 40°C
```

controller는 `following_limit_exceeded`로 PAUSE한 뒤 약 1초 동안 유효한 진전이 없어 `following_no_progress_timeout`으로 ABORT했다.

```text
SEND               = 9
PAUSE              = 1
ABORT              = 1
remaining targets  = 52 / NOT_SENT
automatic retry    = 0
```

추가 target은 보내지 않았고 tolerance, following gate, gain, torque와 endpoint를 변경하지 않았다. `PICK_READY_RETURN_PASS=false`다.

## STOPPED 이후 fresh 상태

사용자 `STOPPED` 확인 뒤 read-only follower feedback 3회는 동일했다.

```text
Present raw = [2235,1702,2793,1773,1703,450]
Goal raw    = [2234,1672,2783,1773,1700,450]

Present =
[+11.736264,-22.197802,+71.164835,-27.032967,-14.197802,+2.264382]°

Goal-Present =
[-0.087912,-2.637363,-0.879121,0.000000,-0.263736,0.000000]°

Moving      = all 0
Load diag   = [0,132,52,0,24,0]
Temperature = max 40°C
Torque      = all 1, unchanged
```

새 GRASP TCP FK와 proxy는 다음과 같다.

```text
GRASP TCP                         = [-45.732137,-290.790629,+89.193802] mm
TCP delta from run start          = [+14.909815,+2.861907,-4.414077] mm
C XY distance                     = 17.498394 mm
table point proxy margin          = +34.534802 mm
self-collision centerline margin  = 64.775222 mm PASS
minimum servo margin              = 23.846165°
full mesh / environment           = NOT_VERIFIED
```

사용자 정지 확인과 fresh feedback `Moving all 0`을 함께 근거로 다음 상태를 기록한다.

```text
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED
follower port = PORT_UNOWNED / privileged fuser rc 1
```

## 로그와 최종 판정

```text
local log = .local/pick-ready-20261013/c_pre_approach_to_pick_ready_attempt2.jsonl
SHA256    = 7e5617b76e36df6b712755a60db2a3e7fafec3e4924bc123fff6c486b3099712
rows      = 11
actions   = SEND 9 / PAUSE 1 / ABORT 1
```

원본 JSONL은 로컬 증거이며 ignored 상태로 유지하고 커밋하지 않는다.

```text
C_PRE_APPROACH_TO_PICK_READY_ATTEMPT2 = FAIL
FAIL_REASON                           = SHOULDER_LIFT_FOLLOWING_NO_PROGRESS
PICK_READY_RETURN_PASS                = false
no further target                     = true
retry                                 = NOT_RUN / NOT_AUTHORIZED
```

현재 pose는 canonical PICK_READY가 아니며, 새 복귀 동작은 별도 오프라인 검토와 새 사용자 승인 전까지 실행하지 않는다.
