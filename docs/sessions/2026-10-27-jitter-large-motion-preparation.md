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
| ORIGINAL cubic relative | 0.10 s | 38 | 3.80 s | 0.1010° | 1.9519° | 19.519°/s | 57.243°/s² | 101.024°/s³ |
| cubic absolute | 0.05 s | 75 | 3.75 s | 0.0262° | 0.9898° | 19.797°/s | 58.833°/s² | 209.299°/s³ |
| quintic absolute candidate | 0.05 s | 93 | 4.65 s | 0.0006° | 0.9978° | 19.956°/s | 57.707°/s² | 26.729°/s³ |

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

- fixed-demo/web: `60/60 PASS`
- sorter: `30/30 PASS`
- compile: `PASS`
- `git diff --check`: `PASS`
- serial open / motor command: `0 / 0`
- commit/push/Jetson deploy: `BLOCKED` — 자동 승인 검토 사용량 제한
- actual ORIGINAL/CUBIC/QUINTIC: `NOT_RUN`

로컬 변경은 보존돼 있으나 `NOT_COMMITTED/NOT_PUSHED`다. 배포가 가능해질 때까지
실제 A/B 명령을 실행하지 않는다.
