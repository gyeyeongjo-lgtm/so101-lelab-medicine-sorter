# Load 비게이트 정책 및 RESPONSIVE_JOINT_ESCAPE 오프라인 탐색

날짜: 2026-10-12
상태: `OFFLINE_DRY_RUN_ONLY` / `Phase C = HOLD`
하드웨어 명령: `0`

## 1. 고정 기준선

```text
SAFE_ESCAPE_2DEG = FAIL
FAIL_REASON = NO_EFFECTIVE_MOVEMENT
Lift achieved ratio  = 0.000%
Elbow achieved ratio = 8.791%
Pan/Flex/Roll         = 52.747/79.121/79.121%
GRASP TCP Z           = 50.496139 -> 55.316363 mm
verified_abs_load_limit = NOT_DEFINED
Phase C = HOLD
```

이 작업은 위 실기를 PASS로 재분류하지 않았으며, 3° 이상 step, motor command,
teleop, HOME/SAFE_HIGH, torque/USB 동작을 수행하지 않았다.

## 2. Load 정책 code-only 수정

`scripts/safe_escape_verification.py`에서 검증 상한이 없는 `Present_Load`를
automatic FAIL로 처리하던 동작을 제거했다.

```text
verified_abs_load_limit = NOT_DEFINED
load_gate_enabled       = false
load_gate_result        = NOT_APPLICABLE_NOT_DEFINED
load_ok                 = null
```

송신 전후 signed `Present_Load`와 축별 `after-before` delta를 기록한다. 향후
근거 있는 상한이 설정된 경우에만 absolute load gate가 활성화된다. Temperature
`<=55°C`, feedback freshness, communication, settle/Moving 관찰, commanded 방향,
50% actual movement, GRASP TCP Z 증가, non-commanded drift `<=1°`는 유지했다.
runner는 command 전에 fresh escape telemetry를 read-only로 취득하고 이후
telemetry와 비교한다.

## 3. 현재 pose FK Z 민감도

입력은 SAFE_ESCAPE_2DEG 종료 후 동일하게 반복된 settled Present다.

```text
arm = [+1.450549,+18.153846,+14.725275,+8.307692,+16.219780] deg
GRASP TCP = [-1.047681,-369.737597,+55.316363] mm
table reference Z = 54.659 mm
start table proxy margin = +0.657363 mm
```

고정 URDF와 GRASP TCP offset
`[-4.748354,-12.033741,-124.531737] mm`에서 각 축을 `+/-0.01°` 중앙차분했다.

| 관절 | d(TCP Z)/d(joint) [mm/deg] | escape 해석 |
|---|---:|---|
| Pan | `+0.000016` | Z 기여 사실상 없음 |
| Lift | `-5.527556` | 음의 방향은 Z 증가이나 직전 실기 0% 반응 |
| Elbow | `-4.451049` | 음의 방향은 Z 증가이나 직전 실기 8.791% 반응 |
| Wrist Flex | `-2.424472` | 음의 방향은 Z 증가, 직전 실기 79.121% 반응 |
| Wrist Roll | `+0.169191` | Z 기여 작음 |

직전 실기의 실제 before→after 관절 변화만 한 축씩 적용한 단독 FK Z 기여는
Pan `+0.000017`, Lift `0`, Elbow `+0.770339`, Flex `+3.771877`, Roll
`+0.260049 mm`였다. 비선형 interaction을 포함한 실제 총 변화는
`+4.820224 mm`다. 따라서 Wrist Flex가 실제 Z 상승의 주 기여축이었음이
수치적으로 확인된다.

## 4. 후보 비교

endpoint는 반복 2° 명령 횟수로 정하지 않고 FK Z target을 이분 탐색해
역산했다. 그 endpoint를 `<=2°`로 균등 분할하고 모든 waypoint에서 TCP Z가
증가하는지 다시 FK로 확인했다. Lift/Elbow/Pan/Roll은 고정했다.

| 후보 | Flex endpoint | waypoint | max step | final Z / gain | max XY drift | final table margin | min centerline | servo margin | final tool-axis change |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Z+20 | `+0.504669°` | 4 | `1.950756°` | `75.316363 / +20.000000 mm` | `15.432549 mm` | `+20.657363 mm` | `64.775222 mm` | `80.285725°` | `7.803024°` |
| Z+30 | `-3.132839°` | 6 | `1.906755°` | `85.316363 / +30.000000 mm` | `21.665359 mm` | `+30.657363 mm` | `64.775222 mm` | `80.285725°` | `11.440531°` |
| Z+40 | `-6.640868°` | 8 | `1.868570°` | `95.316363 / +40.000000 mm` | `27.063709 mm` | `+40.657363 mm` | `64.775222 mm` | `80.285725°` | `14.948560°` |

세 후보 모두 `predicted TCP Z monotonic increase`, commanded-point table proxy
비악화, centerline self-collision proxy PASS, servo range PASS다. 현재 실제 mesh가
없으므로 `full_mesh_collision_status=NOT_VERIFIED`이며, 환경 충돌 PASS로 해석하지
않는다. `excessive XY drift`의 검증된 numeric threshold도 없어
`NOT_DEFINED`로 남기고 실제 drift를 그대로 표시했다.

## 5. 추천 Z+40 waypoint schedule

이전 Phase-B 목표였던 `GRASP TCP Z >= table reference +40 mm`를 만족하는
가장 작은 후보는 Z+40이다. 아래는 **오프라인 계산값**이며 실행 명령이 아니다.

Pan/Lift/Elbow/Roll은 모든 행에서 각각
`+1.450549/+18.153846/+14.725275/+16.219780°`로 고정된다.

| WP | Flex | step | GRASP TCP XYZ [mm] | step dZ | cumulative Z | XY drift | table margin | centerline | servo margin | tool-axis change |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `+6.439122°` | `-1.868570°` | `[-1.147414,-373.677763,+59.911335]` | `+4.594972` | `+4.594972` | `3.941428` | `+5.252335` | `64.775222` | `80.285725°` | `1.868570°` |
| 2 | `+4.570552°` | `-1.868570°` | `[-1.243302,-377.466054,+64.632383]` | `+4.721048` | `+9.316020` | `7.730933` | `+9.973383` | `64.775222` | `80.285725°` | `3.737140°` |
| 3 | `+2.701982°` | `-1.868570°` | `[-1.335242,-381.098441,+69.474483]` | `+4.842100` | `+14.158120` | `11.364483` | `+14.815483` | `64.775222` | `80.285725°` | `5.605710°` |
| 4 | `+0.833412°` | `-1.868570°` | `[-1.423138,-384.571062,+74.432488]` | `+4.958005` | `+19.116125` | `14.838216` | `+19.773488` | `64.775222` | `80.285725°` | `7.474280°` |
| 5 | `-1.035158°` | `-1.868570°` | `[-1.506896,-387.880222,+79.501124]` | `+5.068636` | `+24.184761` | `18.148436` | `+24.842124` | `64.775222` | `80.285725°` | `9.342850°` |
| 6 | `-2.903728°` | `-1.868570°` | `[-1.586426,-391.022403,+84.675002]` | `+5.173878` | `+29.358639` | `21.291623` | `+30.016002` | `64.775222` | `80.285725°` | `11.211420°` |
| 7 | `-4.772298°` | `-1.868570°` | `[-1.661645,-393.994263,+89.948617]` | `+5.273615` | `+34.632254` | `24.264435` | `+35.289617` | `64.775222` | `80.285725°` | `13.079990°` |
| 8 | `-6.640868°` | `-1.868570°` | `[-1.732471,-396.792641,+95.316363]` | `+5.367746` | `+40.000000` | `27.063709` | `+40.657363` | `64.775222` | `80.285725°` | `14.948560°` |

## 6. 검증

```text
tests.test_safe_escape_verification       PASS
tests.test_live_c_safe_escape_only        PASS
tests.test_plan_responsive_joint_escape   PASS
targeted total                            20/20 PASS
hardware command                          0
follower port open                        0
Goal/Torque write                         0
Phase C                                   HOLD
```

`RESPONSIVE_WRIST_FLEX_Z_PLUS_40MM`은 기존 `table+40 mm` intermediate 기준을
만족하는 최소 **오프라인** 후보다. 하지만 tool-axis change `14.948560°`, max
XY drift `27.063709 mm`, full-mesh/environment collision `NOT_VERIFIED`가 남아
있으므로 실기 승인 요청이나 Phase C 진입으로 간주하지 않는다.

> 후속 결정: +40 전체 경로는 첫 실기로 사용하지 않는다. staged +10/+20/+30/+40
> 재비교 결과 첫 live 후보는 `WRIST_ESCAPE_Z_PLUS_20`으로 대체됐다. 최신 근거는
> `2026-10-12-wrist-escape-plus20-ready.md`다.
