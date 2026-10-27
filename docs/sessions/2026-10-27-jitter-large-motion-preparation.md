# Jitter-only large-motion preparation

일자: 2026-10-27

## 범위

- HOME/teaching/calibration/vision/basket/grasp 로직 변경 없음
- Torque/gain/IK/TCP 변경 없음
- arm 2° per-cycle hard cap 유지
- 실제 motor motion 없음

## 후보 구간

기존 사용자 성공 이력이 있는 `red_above → home` 경로의 정확한 역방향인
`home → red_above`를 A/B 후보로 골랐다. 두 endpoint는 저장 pose 그대로이며 새
teaching이나 보정을 만들지 않는다. shoulder_lift와 elbow_flex가 각각 약 45–50°
움직여 외부 링크 운동을 영상으로 분명히 비교할 수 있다.

```makefile
TEST_START = home
TEST_END = red_above
NET_JOINT_DELTA = shoulder_pan:-28.131868, shoulder_lift:+49.494505, elbow_flex:-45.538462, wrist_flex:-7.296703, wrist_roll:-0.263736 deg
TCP_DISPLACEMENT = NOT_COMPUTED_IK_AND_TCP_UNCHANGED
```

현재 물리 자세는 `finish`이므로 이 후보를 실제로 시작하려면 `finish → home` 안전
재배치 한 번이 필요하다. 동일 start/end 방향으로 A와 B를 비교하려면 A 뒤
`red_above → home` reset도 필요하다. 이 두 동작을 A/B와 몰래 합치거나 자동 연속
실행하지 않으며, 각 구간마다 정지와 현장 확인을 거친다.

## 오프라인 profile 비교

가장 큰 변위인 shoulder_lift 기준:

| profile | period | samples | duration | first/last step | max step | max velocity | max acceleration | max discrete jerk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ORIGINAL cubic relative | 0.10 s | 38 | 3.80 s | 0.1010° | 1.9519° | 19.519°/s | 19.483°/s² | 101.024°/s³ |
| cubic absolute | 0.05 s | 75 | 3.75 s | 0.0262° | 0.9898° | 19.797°/s | 20.555°/s² | 209.299°/s³ |
| quintic absolute candidate | 0.05 s | 93 | 4.65 s | 0.0006° | 0.9978° | 19.956°/s | 13.208°/s² | 26.729°/s³ |

quintic은 시작·종료 첫 step과 discrete jerk 후보값이 cubic 20 Hz보다 작다. 이는
command profile 결과일 뿐 실제 떨림 개선을 의미하지 않는다. quintic live 실행은
아직 연결하거나 승인하지 않았다.

## telemetry 및 성공 계약

schema v3는 cycle마다 다음을 함께 기록하도록 구현했다.

- planned timestamp, write start/completion timestamp, write duration, actual interval
- target command
- normalized/raw Goal 및 Present
- Torque_Enable, Moving

완료 출력은 encoder raw가 최소 1 count 변했는지 보고하지만, 이를 외부 링크 운동과
동일시하지 않는다. 외부 링크가 시작/끝에서 실제로 달라졌다는 사용자 영상 확인 전
상태는 `EXTERNAL_CONFIRMATION_REQUIRED`다.

## 검증과 blocker

- Mac fixed-demo/web: `60/60 PASS`
- Mac sorter: `30/30 PASS`
- Jetson fixed-demo/web: `60/60 PASS`
- Jetson sorter: `30/30 PASS`
- compile: `PASS`
- `git diff --check`: `PASS`
- serial open / motor command: `0 / 0`
- commit/push: `b01cd84e1f559cb47001cc9922b9504d2446065d / PASS`
- Jetson deploy: `PASS`, clean checkout에서 같은 commit 확인
- Jetson `motion-compare home → red_above`: `PASS`, 실제 저장 pose 사용
- actual ORIGINAL/CUBIC/QUINTIC: `NOT_RUN`

## 다음 ORIGINAL 실측 계약

`home → red_above`를 기존 cubic relative 10 Hz로 정확히 한 번 실행한다. telemetry
v3 분석에는 전체 command interval mean/std/max와 관절별 command max step,
Goal−Present mean/std/max, Present velocity mean/std/max 및 Present velocity 부호
반전 횟수가 포함된다. 외부 링크가 영상에서 실제로 움직였다는 확인도 별도로 받는다.

absolute 30–50 Hz, live quintic, loop read decimation, free-space 전용 velocity 상향과
`run --profile smooth`/web 연결은 baseline 로그를 분석하기 전에는 적용하지 않는다.
따라서 현재 기본 fixed-demo 실행 경로와 gain/Torque/IK/calibration/TCP에는 변화가 없다.

## ORIGINAL attempt 1 — pre-motion HOLD gate abort

Jetson commit `c9c4f4b19a8dcf91eeb72977839e0f1dd942f692`에서 사용자가
`home → red_above`, profile `original`, `--step`을 시작했다. 첫 현장 확인 뒤 serial
session은 열렸지만 `establish_hold()`의 already-ON 분기에서
`already_on_goal_present_gap`으로 중단됐다.

- Torque: ALL ON으로 판정된 경로
- gate: 적어도 한 축에서 raw `|Goal−Present| > 10`
- Goal/Torque/motion write: `0/0/0`
- telemetry samples: `0`
- current-position HOLD write: `0` (`motion_armed` 전 실패)
- physical motion: `NOT_RUN`
- ORIGINAL baseline: `NOT_MEASURED`
- SMOOTH/QUINTIC: `NOT_RUN`

어느 축이 얼마나 벌어졌는지는 오류 payload에 포함되지 않아 아직 `UNKNOWN`이다.
자동 재실행이나 임의 Goal sync를 하지 않고, 다음은 write 차단 fresh read-only status로
Present/Goal/Torque/Moving/Temperature를 확인하는 단계다.

첫 `robot-status` 시도는 config가 가리킨 ACM에서 leader serial `5AE6085272`를
관측해 `wrong_follower_usb_identity`로 bus open 전에 중단됐다. expected follower는
`5AE6058306`이며 USB 재연결로 ACM 번호가 교체된 상태다. fixed-demo의 serial 기반
선택과 일치하도록 `robot-status`도 `/dev/ttyACM0`과 `/dev/ttyACM1`의 sysfs serial을
먼저 읽고 follower serial의 유일한 match만 연다. 0개 또는 중복 match는 serial open
전에 fail-closed한다.

수정 후 read-only status는 `/dev/ttyACM0`, serial `5AE6058306`에서 30/30 read로
PASS했다. state-change write는 0이고 종료는 `disconnect(disable_torque=False)`다.

| joint | Goal raw | Present raw | Goal−Present | Torque | Moving | °C |
|---|---:|---:|---:|---:|---:|---:|
| shoulder_pan | 1974 | 1976 | −2 | 1 | 0 | 32 |
| shoulder_lift | 815 | 822 | −7 | 1 | 0 | 34 |
| elbow_flex | 3081 | 3078 | +3 | 1 | 0 | 31 |
| wrist_flex | 2591 | 2605 | −14 | 1 | 0 | 35 |
| wrist_roll | 1613 | 1613 | 0 | 1 | 0 | 31 |
| gripper | 1090 | 1090 | 0 | 1 | 0 | 34 |

현재 Present와 저장 `finish` raw 차이는 `[+2,+7,−3,+14,0,−2]`로 현재가 finish임을
확인했다. 반면 저장 `home`과의 차이는 `[−124,−572,+873,−91,−2,+1]`이다. 따라서
`home → red_above` baseline을 바로 재시도할 수 없고, baseline과 분리된
`finish → home` 재배치가 먼저 필요하다. wrist 14 raw gap을 임의 Goal sync하거나
Torque toggle하지 않았으며, 이를 허용하려면 별도 안전 계약과 사용자 승인이 필요하다.

Jetson 첫 테스트 호출은 `tests.test_fixed_demo` 모듈 경로 방식이 Python 3.14에서
`ModuleNotFoundError`로 실패했다. 장비 접근 없는 실행 형식 오류였고, 동일 파일을
`unittest discover`로 실행해 `54+6=60/60 PASS`를 확인했다. 실제 A/B는 현장 안전
확인과 별도 실행 승인 전까지 실행하지 않는다.
