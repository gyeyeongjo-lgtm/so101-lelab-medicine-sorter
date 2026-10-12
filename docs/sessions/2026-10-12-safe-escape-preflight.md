# SAFE_ESCAPE_1DEG 현장 preflight·escape-only 준비

날짜: 2026-10-12

## 승인 범위와 현장 확인

- 사용자 확인: `정지·전체 링크 비접촉·주변 clear 확인`.
- 현 단계는 상태 read-only 확인과 escape-only 준비까지이다. 실제 motion 승인은 아니다.
- GRASP TCP, C reference, orientation, pre-approach/approach endpoint는 변경하지 않았다.

## Jetson read-only preflight

```text
teleoperation_active = false
recording_active     = false
inference_active     = false
related control worker = none
canonical follower   = /dev/ttyACM1 / 5AE6058306
privileged fuser     = rc 1 / unowned
```

write/sync_write/enable_torque/disable_torque를 예외로 차단한 read-only 세션에서 0.25초 간격 3회 Present_Position이 완전히 일치했다.

| joint | Present raw | calibrated | Goal raw | Torque | Moving | Load |
|---|---:|---:|---:|---:|---:|---:|
| shoulder_pan | 2101 | -0.043956° | 2100 | 1 | 0 | 0 |
| shoulder_lift | 2161 | +18.153846° | 2152 | 1 | 0 | 48 |
| elbow_flex | 2152 | +14.813187° | 2147 | 1 | 0 | 32 |
| wrist_flex | 2202 | +10.681319° | 2201 | 1 | 0 | 0 |
| wrist_roll | 2025 | +14.109890° | 2030 | 1 | 0 | -32 |
| gripper | 446 | 2.019584% | 446 | 1 | 0 | 0 |

read-only 종료 후 follower port는 다시 무점유였다. motor command, Goal write, Torque change는 모두 `0` 회이다.

## fresh start에서 재계산한 escape

기존 saved start는:

```text
[-0.131868,+17.362637,+15.868132,+10.769231,+14.197802]°
```

fresh와의 최대 차이는 Elbow `1.054945°`이다. 기존 고정 `SAFE_ESCAPE_1DEG` target은 fresh 기준 Lift `1.791209°`, Roll `1.087912°` step이 되어 `<=1°` 계약을 위반하므로 폐기했다.

동일한 GRASP-TCP Z-gradient 부호 `(+,-,-,-,+)`를 fresh pose에 적용한 새 단일 target:

```text
fresh start = [-0.043956,+18.153846,+14.813187,+10.681319,+14.109890]°
target      = [+0.956044,+17.153846,+13.813187,+9.681319,+15.109890]°
step        = [+1.000000,-1.000000,-1.000000,-1.000000,+1.000000]°
GRASP TCP   = [+1.945711,-371.411292,+61.412230] mm
P1 proxy margin at target = +6.753230 mm
```

full path는 음수 proxy인 현재 시작 sample에서 출발하므로 minimum point proxy는 `-5.715773 mm`이다. 이는 여전히 virtual opening-center와 single P1 infinite plane의 비교이며, 실제 mesh collision PASS/FAIL을 의미하지 않는다.

```text
ACTUAL_LINK_TABLE_COLLISION = NOT_VERIFIED
FULL_MESH_COLLISION         = NOT_VERIFIED
```

## escape-only 실행 계약

- 현장 확인 fresh pose에서 arm drift `<=0.5°`만 허용한다.
- 실행 직전 fresh feedback으로 target을 다시 `±1°` 생성한다.
- 모든 arm step `<=1°`, gripper 현위치 hold, servo bounds, installed URDF SHA, commanded target point proxy `>0` 경우에만 한 target을 송신한다.
- final arm tolerance는 `0.5°`; no-contact/table clearance non-degradation를 사용자가 확인해야 `SAFE_ESCAPE_PASS`다.
- approach/pre-approach/grasp/lift/auto-continuation 코드 경로는 없다.

## 검증과 배포

```text
targeted safe-escape tests + exclusive transport tests = 17/17 PASS
py_compile = PASS
git diff --check = PASS
Jetson SHA match = PASS
Jetson dry-run = PASS
Jetson dry-run message = no port opened; no send_action
post dry-run follower fuser = rc 1 / unowned
```

Jetson 임시 폴더 SHA:

```text
live_c_safe_escape_only.py = 176e4d4a44aba81536e7421a4e4567bb12bbd5950de2ebb04c224bcbb3dbe521
c_pick_safe_escape_only_20261012.json = 3174eb0404be40c73f6ede6cf013cc7febf9a370aa52c6c0cd8f599b6856aee2
plan_pick_grasp_tcp_ik.py = 210047734131e4b8128e30233d911a4951cd39c0a146f34ba8402f72f2f33f8e
urdf_forward_kinematics.py = cc2c4d5f16e368dd24a04c9cfd2d0e90ded5a17a6439a020a64d5124937a51f1
```

## 현재 판정

```text
physical_clearance_human_confirmed = true
fresh_feedback_stationary          = true
escape_only_runner_ready           = true
actual_motor_command_count         = 1 (later separately authorized trial)
motion_authorized                  = false after trial
next explicit approval             = NONE
commit/push                        = NOT_COMMITTED / NOT_PUSHED
```

## 실기 1 결과

사용자의 별도 `RUN SAFE ESCAPE ONLY` 승인 후 runtime fresh feedback에서 단 하나의 target을 생성했다.

```text
fresh start arm = [-0.131868,+18.153846,+14.813187,+10.681319,+14.109890]°
escape target   = [+0.868132,+17.153846,+13.813187,+9.681319,+15.109890]°
step            = [+1.000000,-1.000000,-1.000000,-1.000000,+1.000000]°
gripper hold    = 2.019584%
GRASP TCP       = [+2.480205,-371.439797,+61.412228] mm
target P1 proxy = +6.753228 mm
```

실행기는 한 target만 송신했고 final arm tolerance `0.5°`를 검증했다.

| joint | final error | result |
|---|---:|---|
| shoulder_pan | -0.560° | FAIL |
| shoulder_lift | +1.000° | FAIL |
| elbow_flex | +1.000° | FAIL |
| wrist_flex | +0.209° | PASS |
| wrist_roll | -0.473° | PASS |
| gripper | 0.000 pp | PASS |

```text
result = ABORT
reason = safe_escape_failed:joint_target_timeout
SAFE_ESCAPE_PASS = false
additional target = 0
approach/grasp/lift = NOT_RUN
```

사용자가 `STOPPED`를 확인했고 실행기의 encoder stillness도 통과했다.

```text
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED
```

종료 후 독립 read-only 3회는 다음 값으로 일치했다.

| joint | Present raw | calibrated | Goal raw | Goal-Present raw | Torque | Moving | Load |
|---|---:|---:|---:|---:|---:|---:|---:|
| shoulder_pan | 2105 | +0.307692° | 2111 | +6 | 1 | 0 | -36 |
| shoulder_lift | 2161 | +18.153846° | 2149 | -12 | 1 | 0 | 60 |
| elbow_flex | 2152 | +14.813187° | 2140 | -12 | 1 | 0 | 60 |
| wrist_flex | 2193 | +9.890110° | 2190 | -3 | 1 | 0 | 24 |
| wrist_roll | 2031 | +14.637363° | 2036 | +5 | 1 | 0 | -32 |
| gripper | 446 | 2.019584% | 446 | 0 | 1 | 0 | 0 |

Goal write는 반영됐지만 Lift/Elbow Present는 출발 raw에 머물렀고 `Moving=0`, load `60`이었다. 이 세션에서 원인을 tolerance 문제나 기계적 deadband/load로 확정하지 않았고, target/path/tolerance를 수정하지 않았으며 자동 재시도를 금지했다. teleop/recording/inference는 종료 후도 inactive, follower port는 `fuser rc=1` 무점유다.
