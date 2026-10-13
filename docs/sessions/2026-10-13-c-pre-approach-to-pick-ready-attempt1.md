# 2026-10-13 C PRE APPROACH→PICK_READY 복귀 실기 1 — pre-send stage contract ABORT

## 승인 범위

사용자 승인:

```text
RUN C PRE APPROACH TO PICK READY
```

허용 범위는 직전 C PRE_APPROACH actual pose에서 canonical PICK_READY로 한 번 복귀하는 것이었다. APPROACH, gripper close, LIFT, place와 TCP·calibration·C XY 변경은 포함하지 않았다.

## preflight와 fresh start

teleoperation/recording/inference inactive, canonical follower identity와 exclusive ownership을 확인했다. fresh start는 저장된 `C_PRE_APPROACH_ACTUAL_ATTEMPT1`과 정확히 일치했고, 그 feedback으로 계획된 복귀 경로 `61` waypoint를 생성했다.

```text
fresh arm =
[+14.549451,-16.571429,+70.725275,-35.912088,-12.879121]°

START_POSE_CONFIRMED = C_PRE_APPROACH_ACTUAL_ATTEMPT1
generated waypoints  = 61
```

## 첫 송신 전 ABORT

실제 `ContinuousFollowingCycle`은 기존 `StagedCycle` 계약을 사용하며 첫 내부 stage로 `STAGES[0]=approach`만 허용한다. return scope를 외부 동작과 구분하면서 내부 stage도 `return_to_pick_ready`로 넘긴 것이 계약 불일치였다.

```text
controller call = start_stage("return_to_pick_ready", ...)
expected first internal stage = approach
ABORT = ValueError: stage_order_or_cycle_complete
```

이 예외는 controller가 worker를 만들거나 첫 `send_goal()`을 호출하기 전에 발생했다. following log sink도 한 행도 기록하지 않아 log 파일 자체가 생성되지 않았다.

```text
following log file = NOT_CREATED
SEND               = 0
Goal write         = 0
motor command      = 0
waypoint reached   = 0 / 61
automatic retry    = 0
```

따라서 이번 결과는 return path의 tracking/geometry 실패가 아니다. **첫 target 전 runner와 기존 stage-machine 계약 불일치로 fail-closed 차단된 실행 배선 오류**다.

## 정지와 ownership

사용자가 현장에서 정지와 비접촉 상태를 확인했다.

```text
user confirmation = STOPPED
physical_stop      = FEEDBACK_AND_HUMAN_CONFIRMED
teleoperation / recording / inference = false / false / false
privileged follower fuser             = rc 1 / unowned
```

실제 명령이 없었으므로 follower는 C PRE_APPROACH actual pose에 그대로 있다.

## 국소 수정

새 stage나 control framework를 만들지 않았다. 외부 return 계약은 그대로 보존했다.

```text
scope             = live_c_return_to_pick_ready_only
run phrase        = RUN C PRE APPROACH TO PICK READY
completion phrase = PICK_READY CONFIRMED
reached marker    = PICK_READY_REACHED
pass marker       = PICK_READY_RETURN_PASS
```

fresh one-shot controller의 내부 stage만 기존 첫 stage인 `approach`로 매핑했다. return scope가 이 내부 stage를 사용하면서도 PRE_APPROACH marker가 아니라 return 전용 marker만 출력하는 회귀를 추가했다.

## 수정본 검증

```text
live runner tests          = 27/27 PASS
staged cycle tests         = 10/10 PASS
continuous following tests = 10/10 PASS
Jetson py_compile          = PASS
Jetson exact dry-run       = PASS: no port opened; no send_action
runner SHA local / remote  = a8bdda8e5c77d02d5a25bf0fd874412057462a4742a7c9c3e142f8f0c19bff13
```

## 현재 판정

```text
C_PRE_APPROACH_TO_PICK_READY_ATTEMPT1 = ABORT_BEFORE_SEND
FAIL_REASON            = STAGE_CONTRACT_MISMATCH
PICK_READY_RETURN_PASS = false
hardware command       = 0
actual retry           = NOT_RUN / NOT_AUTHORIZED
full mesh/environment  = NOT_VERIFIED
```

이 승인 범위는 ABORT로 종료됐다. 수정본 actual retry는 사용자의 정지·비접촉·주변 clear 재확인과 새 승인 뒤에만 실행한다.

```text
RUN C PRE APPROACH TO PICK READY
```
