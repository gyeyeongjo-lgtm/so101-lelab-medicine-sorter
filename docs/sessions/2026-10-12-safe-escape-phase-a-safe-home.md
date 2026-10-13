# SAFE_ESCAPE 판정 개선·HOME 복귀 API

날짜: 2026-10-12
브랜치: `fix/usb-recording`

## 작업 시작 기준선

| 항목 | 최신 확인값 |
|---|---|
| Follower Present raw | `2118/2161/2151/2175/2049/446` |
| Follower Present | Pan `+1.450549°`, Lift `+18.153846°`, Elbow `+14.725275°`, Flex `+8.307692°`, Roll `+16.219780°`, Gripper `2.019584%` |
| Goal raw | `2128/2138/2130/2170/2053/446` |
| Goal−Present raw | `+10/-23/-21/-5/+4/0` |
| Torque_Enable | 6축 모두 `1` |
| Moving | 6축 모두 `0` |
| Load | `-52/104/96/32/-28/0` |
| Temperature | `38/40/39/36/37/40 °C` |
| physical stop | `FEEDBACK_AND_HUMAN_CONFIRMED` |
| follower port | 마지막 read-only 종료 후 privileged `fuser rc=1`, 무점유 |

`SAFE_ESCAPE_1DEG`는 Goal write는 성공했지만 Lift/Elbow가 약 `12 raw`
차이에서 Present 변화 없이 Moving `0`, Load 약 `60`으로 정체했다.
`SAFE_ESCAPE_2DEG` offline 후보는 fresh-relative `(+2,-2,-2,-2,+2)°`, 예상
raw delta `(+22,-23,-23,-23,+22)`, target TCP Z `75.993672 mm`였다.

관련 실행 경로는 `scripts/live_c_safe_escape_only.py`,
`scripts/so101_follower_transport.py`, `scripts/staged_cycle_execution.py`,
`scripts/continuous_following_execution.py`, FK는
`scripts/urdf_forward_kinematics.py`/
`scripts/plan_pick_grasp_tcp_ik.py`다.

## SAFE_ESCAPE_2DEG 실기 결과를 신규 판정으로 재해석

단 한 번의 target 송신 후 실제 이동은 다음과 같다.

| 축 | 요청 변화 | 실제 변화 | 이동률 | 판정 |
|---|---:|---:|---:|---|
| Pan | `+2.000000°` | `+1.054945°` | `52.7%` | PASS |
| Lift | `-2.000000°` | `0.000000°` | `0%` | FAIL |
| Elbow | `-2.000000°` | `-0.175824°` | `8.8%` | FAIL |
| Flex | `-2.000000°` | `-1.582418°` | `79.1%` | PASS |
| Roll | `+2.000000°` | `+1.582418°` | `79.1%` | PASS |

GRASP TCP는 `[5.406137,-365.783675,50.496139] mm`에서
`[-1.047681,-369.737597,55.316363] mm`로 변했고 Z는 `+4.820224 mm`
증가했다. 그러나 commanded 축 모두가 의도 방향으로 요청량의 50%
이상 이동해야 하므로 `SAFE_ESCAPE_PASS=false`다. 실패 후 자동 재시도,
3° 확대, approach/grasp/lift는 없었다.

## Phase A 구현

- terminal tolerance를 Shoulder Lift/Elbow `1.5°`, Pan/Flex/Roll `0.5°`,
  gripper `1.0 pp`로 분리했다. 이 항목은 진단용이며 escape PASS를
  대체하지 않는다.
- commanded 관절별 방향 일치·요청량 50% 이상, GRASP TCP Z 증가,
  non-commanded drift `≤1°`, `Temperature≤55°C`, fresh feedback,
  communication, settle를 검증한다.
- Goal/Present/Moving/Load/Temperature는 축별 개별 register read로 읽어
  과거의 오류 group packet을 의존하지 않는다.
- 2° 초과 step을 거부하고, 정지/정체 관찰 후 한 번만 판정한다.
- 검증된 Load 상한은 저장소에 없다. 설정은
  `verified_abs_load_limit: null`, runtime 표시는 `NOT_DEFINED`이며 PASS를
  fail-closed한다. test fixture의 상한은 production 값이 아니다.

## Phase C/D 구조

HOME/SAFE_HIGH 실기 기록은 하지 않았다. `recorded_pose_config.py`는 각
pose의 raw/degree/FK를 정확히 3회 받아 평균과 population standard deviation를
계산하고, HOME과 SAFE_HIGH가 모두 있을 때만 YAML을 저장한다.
실측값이 없으므로 `configs/poses.yaml`을 placeholder로 만들지 않았다.

`safe_home_return.py`는 기존 `interpolate_goals()`를 재사용해
`CURRENT→SAFE_ESCAPE→SAFE_HIGH_EXCEPT_PAN→PAN_ALIGNMENT→HOME`을 구성한다.
default step은 `≤2°`이고 gripper command는 변경하지 않는다. low TCP에서
외부에서 Phase-A-검증된 escape segment가 주어지지 않으면 계획을 거부한다.
어떤 segment에서든 예외/실패가 나면 `stop_commands()`를 호출하고 나머지
segment를 실행하지 않는다. 자동 recovery는 없고, `attempt_safe_recovery()`는
별도 사용자 승인과 정상 feedback/communication을 요구한다.

## 검증

```text
test_safe_escape_verification.py    6 PASS
test_live_c_safe_escape_only.py     8 PASS
test_so101_exclusive_transport.py  13 PASS
test_continuous_following_execution.py 8 PASS
test_recorded_pose_config.py        2 PASS
test_safe_home_return.py            5 PASS
targeted total                     42 PASS
py_compile                         PASS
git diff --check                   PASS
```

전체 unittest discover는 `385` tests 중 `380 PASS`, 샌드박스에서 localhost socket bind가
금지된 `teach_capture_web` 4건과 현재 venv에 `websocket` module이 없는 1건으로
`5 ERROR`다. 신규 타깃 테스트 failure는 없다.

## Phase 판정

```text
Phase A = PASS (code/tests; production Load limit is NOT_DEFINED/fail-closed)
Phase B = FAIL (completed 2° one-step trial; no retry)
Phase C = NOT_RUN
Phase D = PASS (offline API/tests; live path unavailable until Phase C)
Phase E = NOT_RUN
```

이 작업 중 신규 hardware command, serial open, Goal/Torque write, service restart는
`0`회다. 변경은 `NOT_COMMITTED/NOT_PUSHED`다.
