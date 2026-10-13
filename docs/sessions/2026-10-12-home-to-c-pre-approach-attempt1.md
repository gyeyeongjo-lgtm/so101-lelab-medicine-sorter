# 2026-10-12 HOME→C PRE_APPROACH 실기 1 — waypoint 29 FAIL

## 승인 범위

사용자 승인:

```text
RUN HOME TO C PRE APPROACH
```

허용 범위는 canonical HOME에서 새 GRASP TCP 기반 C PRE_APPROACH까지 한 번 이동하는 것이다. APPROACH, gripper close, lift, RED place는 포함하지 않았다.

## preflight

```text
LeLab health             = OK
teleoperation            = inactive
recording                = inactive
inference                = inactive
follower                 = /dev/ttyACM1
follower ID_SERIAL_SHORT = 5AE6058306
privileged fuser         = rc 1 / unowned
runner SHA               = 44bf9e782e6e8055b507eafc04896a2beb37f6190c88e045f0eb0b208d67c590
config SHA               = f9a63ec428a29b0b612b7ffec17a3b65f018163e0a0693cec1816b8339dfde36
```

첫 원격 시작은 `sudo`가 TTY password read를 거부해 ownership gate 전에 종료됐다. follower port open, Goal write, motor command, log 생성은 모두 `0`이었다. 같은 승인 범위에서 `sudo -S`로 privileged ownership 검사만 정상화해 다시 시작했다.

fresh start:

```text
Pan    -2.593407°
Lift  -63.956044°
Elbow +77.406593°
Flex  +18.241758°
Roll  -12.615385°
```

canonical HOME 대비 차이는 `[0,+1.318681,0,+0.351648,0]°`이며 기존 HOME tolerance Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`를 통과했다.

```text
START_POSE_CONFIRMED = HOME
generated waypoints  = 60
gripper hold         = 2.019584%
```

canonical pose 오프라인에서는 62 waypoint였으나, live runner는 허용범위 안의 fresh pose에서 첫 stage까지를 다시 bounded interpolation해 60개를 생성했다.

## 실제 진행

| 지점 | 결과 | Elbow target | Elbow error | Elbow Load | 설명 |
|---|---|---:|---:|---:|---|
| waypoint 4 | 진행 | +77.406593° | +1.230769° | 68 | Lift-only relief endpoint |
| waypoint 18 | 진행 | +75.702841° | +2.934522° | 148 | `COUPLED_TRANSITION` endpoint |
| waypoint 29 | PAUSE/ABORT | +74.364178° | +4.097361° | 200 | `WRIST_COUPLED` 도중 limit 초과·no progress |

waypoint 29 target 전체 관절:

```text
[Pan +5.191654,
 Lift -40.800604,
 Elbow +74.364178,
 Flex -6.693373,
 Roll -12.580091]°
```

controller는 Elbow following error가 기존 limit `4.0°`를 넘자 추가 target을 PAUSE했다. 약 1초 뒤에도 Elbow Present가 진전되지 않아:

```text
ABORT: following_no_progress_timeout
```

로 종료했다.

```text
target sent       = 29 / 60
remaining targets = 31 / 60 NOT_RUN
PRE_APPROACH_PASS = false
APPROACH          = NOT_RUN
GRASP             = NOT_RUN
LIFT              = NOT_RUN
PLACE             = NOT_RUN
automatic retry   = 0
```

## STOPPED 이후 fresh telemetry

사용자의 `STOPPED`와 runner의 feedback stillness를 통과했다.

```text
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED

Present =
[Pan +4.879121,
 Lift -40.571429,
 Elbow +78.461538,
 Flex -5.494505,
 Roll -12.615385]°

Goal - Present =
[+0.263736,-0.263736,-4.131868,-1.230769,0.000000]°

Goal raw    = [2160,1490,2829,2004,1721,446]
Present raw = [2157,1493,2876,2018,1721,446]
Moving      = [0,0,0,0,0,0]
Load diagnostic = [-24,+24,+200,+68,0,0]
Temperature °C  = [36,37,45,35–36,35,39]
Torque_Enable   = [1,1,1,1,1,1]
```

3회 Present 표본은 동일했다. read-only viewer는 motor write와 torque change를 각각 `0`으로 유지하고 포트를 해제했다.

## 실제 final FK

```text
actual GRASP TCP = [-10.546107,-262.235242,+68.470056] mm
C XY remaining   = 61.705733 mm
C 3D distance    = 69.294551 mm
table point proxy margin = +13.811056 mm
self-collision centerline proxy = 53.946249 mm / PASS
servo margin = 16.549462°
full mesh/environment = NOT_VERIFIED
```

waypoint 29의 nominal target GRASP TCP는 `[-13.182192,-276.673074,+91.972426] mm`다. 실제 Z가 nominal보다 낮은 것은 Elbow `+4.131868°`, Wrist Flex `+1.230769°` tracking lag와 일치한다. point/centerline proxy가 양수여도 full mesh/environment PASS를 의미하지 않는다.

## 로그와 종료 상태

```text
local log = .local/home-c-pre-approach-20261012/home_to_c_pre_approach_attempt1.jsonl
SHA256    = df364bd5a6854bc637299c385f745730fe102ba356d1901420f0c0f537cf0de1
rows      = 31
actions   = SEND 29 / PAUSE 1 / ABORT 1

post-run teleoperation/recording/inference = inactive
post-run follower port = unowned
```

## 판정

```text
HOME_TO_C_PRE_APPROACH_ATTEMPT1 = FAIL
FAIL_REASON = ELBOW_FOLLOWING_LIMIT_THEN_NO_PROGRESS
PRE_APPROACH_PASS = false
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED
next live command = NONE
```

tolerance, following limit, TCP, C XY, calibration, gain, torque를 변경하지 않았고 자동 재시도하지 않는다.
