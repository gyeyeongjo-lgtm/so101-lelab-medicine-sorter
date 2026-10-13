# 2026-10-13 C PRE_APPROACH→PICK_READY 복귀 오프라인 준비

## 목적과 범위

PICK_READY→C PRE_APPROACH 실기 1이 현장 geometry acceptance에서 FAIL한 뒤, 사용자가 `STOPPED`를 확인한 actual pose에서 canonical PICK_READY로만 복귀하는 별도 경로를 준비했다.

```text
scope       = live_c_return_to_pick_ready_only
start       = C_PRE_APPROACH_ACTUAL_ATTEMPT1
destination = recorded PICK_READY
```

APPROACH, gripper close, LIFT, place, TCP·calibration·C XY 수정은 범위에 없다. 실제 hardware command는 아직 보내지 않았다.

## fresh actual start와 목적지

```text
actual start =
[+14.549451,-16.571429,+70.725275,-35.912088,-12.879121]°

actual start GRASP TCP =
[-60.641952,-293.652536,+93.607879] mm

recorded PICK_READY =
[-4.263736,-68.703297,+68.879121,+8.131868,-23.516484]°

PICK_READY GRASP TCP =
[+30.308815,-276.029085,+184.960142] mm
```

live runner는 실제 시작 pose를 저장 snapshot으로 대체하지 않는다. 송신 직전 fresh feedback이 위 actual start 기준 허용범위 Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`를 벗어나면 first target 전에 차단한다.

## 복귀 경로

전진 path의 실측 성공 coordination을 역방향 stage 순서로 재사용하되, 첫 구간은 nominal endpoint가 아니라 STOPPED 뒤 actual pose에서 다시 bounded interpolation했다.

```text
C PRE_APPROACH actual
→ forward 75% stage
→ forward 50% stage
→ forward 25% stage
→ Lift-relief stage
→ recorded PICK_READY
```

```text
waypoint count  = 61
segment counts  = 14 / 16 / 16 / 13 / 2
maximum step    = 1.000000°
gripper policy  = hold fresh position
```

첫 target:

```text
[+14.229341,-17.489244,+70.685146,-34.923651,-13.050710]°

fresh start 대비 delta =
[-0.320110,-0.917815,-0.040129,+0.988437,-0.171589]°

predicted GRASP TCP delta Z = +1.183870 mm
```

## 오프라인 검증

```text
GRASP TCP Z                    = 93.607879 → 184.960142 mm
TCP Z progression             = MONOTONIC_NON_DECREASING
negative Z waypoint           = 0
minimum delta Z / waypoint    = +0.397176 mm
C XY distance                 = 2.596020 → 94.924111 mm
minimum TCP/table margin      = +38.948879 mm
minimum commanded TCP margin  = +40.132748 mm
minimum non-base link margin  = +40.222700 mm
self-collision centerline     = 64.775222 mm / PASS
minimum servo margin          = 24.285725°
full mesh/environment         = NOT_VERIFIED
```

point/link-origin/centerline proxy가 양수여도 full mesh/environment collision PASS를 뜻하지 않는다.

## runner와 검증

기존 `scripts/live_c_approach.py`와 continuous-following/safety infrastructure를 재사용했다. PRE_APPROACH 실행 범위와 복귀 범위의 승인 문구와 PASS marker를 분리했다.

```text
run phrase        = RUN C PRE APPROACH TO PICK READY
completion phrase = PICK_READY CONFIRMED
pass marker       = PICK_READY_RETURN_PASS
```

복귀 중에도 fresh feedback, exclusive ownership, servo bounds, Temperature `<=55°C`, following/no-progress, final tolerance와 `Moving all 0`을 검사한다. Load는 diagnostic only다. 실패 시 추가 target을 금지하고 torque와 현재 Goal을 유지한 채 STOP한다.

독립 리뷰에서 기존 공통 arm final tolerance `1.6°`가 return endpoint의 canonical PICK_READY 검증을 느슨하게 만드는 blocker를 발견했다. 이를 공통 동작에 적용하지 않고 return scope에만 다음 tolerance를 fail-closed로 고정했다.

```text
Pan / Flex / Roll final tolerance = 0.5°
Lift / Elbow final tolerance      = 1.5°
gripper final tolerance           = 2.0 percentage points
```

기존 PICK_READY→C PRE_APPROACH scope와 marker의 동작은 변경하지 않았다.

검증:

```text
live runner tests          = 26/26 PASS
continuous following tests = 10/10 PASS
exclusive transport tests  = 13/13 PASS
py_compile                 = PASS
JSON validation            = PASS
exact dry-run               = PASS: no port opened; no send_action
diff-check                  = PASS
```

Jetson의 기존 실기 디렉터리와 service를 덮어쓰지 않고 다음 별도 폴더에 runner·의존 모듈·config 6개를 배치했다.

```text
/home/jetson3/so101-c-pre-approach-return-pick-ready-20261013/
```

설치 LeLab Python에서 py_compile과 exact dry-run이 통과했고 local/remote SHA 6개가 모두 일치했다. live 전 read-only 상태도 다음과 같다.

```text
teleoperation / recording / inference = false / false / false
canonical follower                     = /dev/ttyACM1
follower ID_SERIAL_SHORT               = 5AE6058306
privileged fuser                        = rc 1 / unowned
dry-run follower port open              = 0
dry-run send_action                     = 0
```

## 현재 판정

```text
C_PRE_APPROACH_TO_PICK_READY = OFFLINE_READY
actual return attempt 1      = ABORT_BEFORE_SEND / SEND 0
corrected actual retry       = NOT_RUN / NOT_AUTHORIZED
PICK_READY_RETURN_PASS       = false
hardware command             = 0
full mesh/environment        = NOT_VERIFIED
```

## 실기 1 이후 runner 보완

첫 actual return 승인에서는 fresh start 일치와 `61` waypoint 생성 뒤, 첫 target 전에 내부 stage 이름 `return_to_pick_ready`가 기존 `STAGES[0]=approach` 계약과 충돌해 `stage_order_or_cycle_complete`로 ABORT했다. following log 파일은 생성되지 않았고 `SEND=0`, motor command `0`이다.

외부 return scope·prompt·marker는 유지하고 one-shot controller의 내부 stage만 기존 `approach`로 사용하도록 국소 수정했다. 수정 후 live runner `27/27`, staged cycle `10/10`, continuous following `10/10` PASS, Jetson 설치 Python py_compile·exact dry-run PASS다. runner local/remote SHA는 `a8bdda8e5c77d02d5a25bf0fd874412057462a4742a7c9c3e142f8f0c19bff13`으로 일치한다.

사용자 `STOPPED`와 비접촉 확인으로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; 세 control은 false이고 follower는 무점유다. 수정본 actual retry는 아직 `NOT_RUN/NOT_AUTHORIZED`다. 상세: [실기 1](2026-10-13-c-pre-approach-to-pick-ready-attempt1.md).

현장 정지·전체 링크 비접촉·주변 clear를 다시 확인한 뒤 다음 문구로 새 승인을 받아야 한다.

```text
RUN C PRE APPROACH TO PICK READY
```
