# 2026-10-13 CURRENT pose gripper-open-only 실기 준비

## 범위와 기준선

recovery/HOME/PICK_READY 추가 개발을 중단하고 C 실제 PICK을 critical path로 고정했다. 이 작업은 현재 팔 pose를 유지한 채 gripper만 여는 단일 live step을 준비한다.

```text
stored CURRENT arm reference =
[+11.736264,-22.197802,+71.164835,-27.032967,-14.197802] deg

stored gripper reference = 2.264382%
physical_stop last confirmed = FEEDBACK_AND_HUMAN_CONFIRMED
```

이 저장 pose를 live current로 가정하지 않는다. live runner가 follower port를 단독 소유한 뒤 fresh feedback을 다시 읽어 arm과 gripper start gate를 검사한다. table calibration, C XY, PIN/GRASP TCP 분리, 기존 CURRENT→C 11-waypoint는 변경하지 않았다.

실제 gripper live motion과 arm motion은 모두 `NOT_RUN/NOT_AUTHORIZED`다.

## 35% 양자화 결정

Jetson의 실제 follower calibration 증거는 다음과 같다.

```text
gripper motor ID       = 6
drive mode             = 0
raw range              = 413..2047
calibration evidence SHA = 2f74c130...9c2e
LeRobot                = 0.6.0
```

LeRobot의 normalized target 변환은 `int()` 내림을 사용한다.

```text
35.0% request
-> raw 984
-> normalized feedback 34.94492044063648%
```

따라서 `>=35%` 성공 조건을 양자화 후에도 충족하는 최소 표현 가능 명령을 선택했다.

```text
requested target       = 35.0%
normalized command     = 35.0061199510404%
expected Goal raw      = 985
expected feedback      = 35.00611995104039%
raw direct write       = false
```

runner는 실행 직전 로드된 calibration에서 ID/range/drive mode와 normalized->raw->normalized 변환을 다시 재현한다. 또한 설치된 `SO101Follower.send_action()`의 partial-action 구현을 송신 전에 고정하기 위해, 실제 class source file 전체 SHA를 다음 검증본과 대조한다.

```text
so_follower.py SHA =
b7d9fcfcf67818c267d71744c993470dfb5077887f9ecedfe8cdf69f450be8fd

feetech.py SHA =
0460413cd6a641cede015ac19ac53d2cfe9c343af1bd18ed74e1951229f64ff2

motors_bus.py SHA =
ade55d42046f1f0fa737eb61c360d76ed98211f200e10918dc2e6fcfd640a688
```

세 소스 중 하나라도 일치하지 않으면 gripper write 전 `SEND=0`으로 차단한다. 또한 실제 `MotorsBus._get_ids_values_dict({"gripper": value})` 결과와 `_unnormalize` 결과의 key가 정확히 motor ID `{6}` 하나인지 재현한다. 다른 ID가 하나라도 포함되면 `SEND=0`이다.

## live 실행 계약

```text
LeLab teleoperation/recording/inference inactive
canonical follower /dev/ttyACM1, serial 5AE6058306
single exclusive owner
fresh CURRENT arm/gripper gate
0.5 s startup stillness
installed source/calibration/quantization verification
exactly one {"gripper.pos": 35.0061199510404} send_action
post-send settle and telemetry verification
human GRIPPER OPEN CONFIRMED
feedback + human STOPPED
command-owning port release
separate read-only CURRENT->C start-gate recheck
```

시작 arm tolerance는 Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`, gripper reference tolerance는 `2.0 pp`다. 전송 전 0.5초 동안 Present raw와 모든 Goal raw가 변하지 않아야 한다.

전송 action key는 `gripper.pos` 하나뿐이고, arm 5축 target은 포함하지 않는다. arm Goal raw 5축은 pre-send baseline과 모든 settle 표본, final, port release 후 별도 session의 fresh route gate에서 모두 같아야 한다. gripper Goal raw는 전 settle 표본, final, 별도 route gate에서 `985`여야 한다.

다음을 계속 검사한다.

- feedback/communication freshness
- arm Moving `0`; 최종은 gripper까지 Moving `0`
- 모든 servo Temperature `<=55°C`
- arm Present drift `<=1°`
- final gripper `>=35%`
- signed Present_Load before/after/delta logging

Present_Load는 검증된 numeric threshold가 없으므로 diagnostic only다. 임의 숫자로 PASS/FAIL하지 않는다. 하나라도 실패하면 추가 target은 없고, torque/현재 Goal을 유지한 채 STOP하며 자동 재시도하지 않는다. settle 대기 중 timeout/feedback 예외이 나도 그 전까지 받은 각 표본은 즉시 구조화 출력한다.

성공 후에도 arm 11-waypoint는 자동으로 시작하지 않는다. 별도 read-only gate가 통과할 때만 다음 live 승인 문구를 출력한다.

```text
RUN CURRENT TO C PRE APPROACH
```

## 오프라인 검증

```text
main gripper-only tests             = 21/21 PASS
related motion/safety regression    = 129/129 PASS
py_compile                          = PASS
JSON validation                     = PASS
git diff --check                    = PASS
explicit local dry-run              = PASS
dry-run result                      = no port opened; no send_action
independent review                  = PASS / blocker 0
```

## Jetson 배치·read-only preflight

기존 service/USB/실기 폴더를 변경하지 않고 새 격리 폴더에 실행기, 전이 의존성, 두 config 총 12개 파일을 배치했다.

```text
/home/jetson3/so101-gripper-open-only-20261013/
```

Jetson 검증:

```text
Python                   = 3.14.7
LeRobot                  = 0.6.0
NumPy                    = 2.2.6
remote py_compile        = PASS
remote explicit dry-run  = PASS
local/remote SHA         = 12/12 MATCH
so_follower runtime SHA  = b7d9fcfc...08fd / MATCH
feetech runtime SHA      = 0460413c...4ff2 / MATCH
motors_bus runtime SHA   = ade55d42...a688 / MATCH
remote dry-run motion    = 0
```

read-only preflight:

```text
LeLab 8000 health        = ok
teleoperation            = inactive
recording                = inactive
inference                = inactive
leader                    = /dev/ttyACM0, 5AE6085272
follower                  = /dev/ttyACM1, 5AE6058306
privileged fuser          = rc 1 / no owner output
related control worker    = none observed
```

첫 `sudo -n fuser`는 인증 ticket이 없어 실패했으며 그 rc를 무점유 근거로 쓰지 않았다. 이어서 privileged interactive read-only `fuser` 자체를 성공적으로 실행했고, owner output 없음/`rc=1`을 무점유 근거로 기록했다. 자격증명은 파일·로그·Git에 기록하지 않았다.

## 현재 판정

```text
GRIPPER_OPEN_ONLY_OFFLINE = PASS
GRIPPER_OPEN_LIVE         = NOT_RUN / NOT_AUTHORIZED
arm target send           = 0
gripper target send       = 0
torque/service/USB change = 0
CURRENT_TO_C route        = PRESERVED / NOT_RUN
full mesh/environment     = NOT_VERIFIED
commit/push               = INCLUDED_IN_2026-10-13_READINESS_COMMIT
```

다음 사용자 행동은 현장에서 팔이 정지해 있고, finger opening sweep 전체가 C/table/주변과 비접촉이며, 주변이 clear임을 확인하는 것이다.
