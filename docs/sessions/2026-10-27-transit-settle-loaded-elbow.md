# 적재 중 elbow transit settle 조정

일자: 2026-10-27

## 현장 실패

사용자가 smooth 기본 web 실행에서 A를 집어 `slot1_lift`까지 완료한 뒤 바구니 위로
이동하는 stage에서 `segment_settle_timeout`을 보고했다.

```text
elbow_flex target_present_error = -5.01 deg
other arm joint errors = <1 deg
Moving = all 0
maximum temperature = 33 C
```

기존 arm settle tolerance는 전 축 5°라 elbow가 0.01° 초과했고, 적재 중 중력 처짐이
정지 상태로 남아 8초 timeout까지 진행한 것으로 본다. 오류는 해결 전 성공으로
기록하지 않는다.

## 변경

relaxed transit settle을 다음 exact stage에만 적용한다.

```text
home
slot1_lift, slot2_lift, slot3_lift
red_above, blue_above, green_above
```

이 stage의 도착 계약:

- elbow_flex tolerance: 8°
- 다른 arm joint tolerance: 기존 5°
- gripper tolerance: 기존 100 percentage points
- 모든 motor `Moving=0`과 모든 tolerance 충족이 연속 0.5초 유지돼야 완료
- Moving 재발 또는 tolerance 이탈 시 0.5초 dwell을 처음부터 재시작
- 최대 settle timeout: 기존 8초

`slot*_grasp`, `*_release`를 포함한 나머지 stage는 elbow 포함 arm 5°와 기존 즉시
도착 판정을 유지한다. `slot*_pre`와 `finish`도 요청에 포함되지 않아 정밀 기준을
유지한다. timeout 출력에는 적용 policy, tolerance, dwell, 마지막 연속 안정 시간을
추가했다.

## 보존한 안전 계약

- smooth quintic absolute-deadline 40Hz·20°/s 기본 profile
- arm emitted command `<=2°` hard cap
- 실행 중 55°C stop
- servo Overload 및 motion/feedback fault current HOLD
- CLI Ctrl+C HOLD / web 정지 버튼 HOLD
- `disconnect(disable_torque=False)`

global config, taught pose, calibration, gain, Torque policy, IK, TCP는 변경하지 않았다.

## 장비 없는 검증

- fixed-demo + web: `71/71 PASS`
- sorter: `31/31 PASS`
- Python compile: `PASS`
- `git diff --check`: `PASS`
- serial open / motor command: `0 / 0`

테스트에는 elbow 오차 5.01°인 `red_above`가 8초 전에 완료되는 것, 0.5초 도중
`Moving=1`이 한 번 나오면 dwell이 reset되는 것, 같은 5.01° 오차의 grasp/release가
기존 5° 정밀 기준으로 timeout되는 것이 포함됐다. 수정 후 실제 web 실행은
`NOT_RUN`이다.
