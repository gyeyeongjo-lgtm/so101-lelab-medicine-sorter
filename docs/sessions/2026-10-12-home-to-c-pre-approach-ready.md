# 2026-10-12 HOME→C PRE_APPROACH 오프라인 준비

## 전략 기준선

canonical start는 SAFE_HIGH가 아니라 기록된 HOME이다.

```text
HOME
→ object detection
→ HOME→object PRE_APPROACH
→ APPROACH
→ GRASP
→ LIFT
→ destination
→ PLACE
```

SAFE_HIGH는 recovery/fallback/optional transport-safe pose로만 보존한다. 직전 SAFE_HIGH→C PRE_APPROACH 시도는 start mismatch로 command 전 차단됐고, 현재 critical path에서는 재사용하지 않는다. 기존 table→robot calibration, C robot XY, PIN calibration TCP, PICK GRASP TCP는 변경하지 않았다.

이번 작업의 hardware command는 `0`이다. 실제 모터, Goal, Torque, USB, 서비스에는 손대지 않았다.

## fresh HOME 확인

write/torque API를 차단한 read-only follower 도구로 3회 측정했고 세 표본은 동일했다.

```text
fresh Present:
Pan    -2.593407°
Lift  -63.956044°
Elbow +77.406593°
Flex  +18.241758°
Roll  -12.615385°

fresh - canonical HOME:
[0.000000,+1.318681,0.000000,+0.351648,0.000000]°
```

기존 HOME tolerance는 Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`다. 따라서 `HOME_NEAR=true`다.

```text
Moving                    = all 0
Torque_Enable             = all 1
Elbow Goal-Present        = -2.021978°
Elbow Load diagnostic     = 104
maximum Temperature       = 43°C
motor/Goal/Torque command = 0
```

## 고정 endpoint

```text
C robot XY = [-62.635354,-295.315566] mm

PICK GRASP TCP =
[-4.748354,-12.033741,-124.531737] mm

C PRE_APPROACH joints =
[+14.845130,-16.993354,+70.591582,-37.176891,-12.536328]°

final GRASP TCP =
[-62.635356,-295.315566,+100.000001] mm

C XY error = 0.000002 mm
full/tool/jaw orientation error =
3.090410° / 3.089708° / 0.673228°
```

PIN TIP TCP는 calibration 전용으로 유지한다.

## load-aware 후보 비교

근거 로그:

- `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_strong_unload_fresh3_attempt1.jsonl`
- `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_delayed_wrist_fresh5_attempt1.jsonl`

실측 deadband 근거는 `10–14 raw 정체`, `18 raw movement 시작`, `20–23 raw 반복 movement`다. 첫 stage에서 Elbow와 Wrist를 고정하고 Lift만 load-relief 방향으로 이동한 뒤 Shoulder–Elbow coupled motion과 delayed Wrist를 적용했다.

| 후보 | Lift relief | 예상 raw | 판정 | Waypoint | max step | TCP min Z | TCP/table margin | self proxy | servo margin |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| `LIFT_NEG65P0` | -65° | 3 | FAIL: deadband 미달 | 57 | 0.983339° | 98.211302 mm | +43.552302 mm | 55.827804 mm | 17.604407° |
| `LIFT_NEG60P0` | -60° | 60 | PASS / 추천 | 62 | 0.983339° | 81.035347 mm | +26.376347 mm | 55.827804 mm | 17.604407° |
| `LIFT_NEG55P0` | -55° | 117 | PASS | 67 | 0.983339° | 64.377267 mm | +9.718267 mm | 55.827804 mm | 17.604407° |

`LIFT_NEG60P0`는 실측 최소 유효 raw를 넘는 후보 중 Lift 변화가 가장 작고 `LIFT_NEG55P0`보다 table proxy 여유가 크므로 선택했다. full mesh/environment collision은 `NOT_VERIFIED`다.

## 추천 stage와 FK 진행

| Stage | Pan | Lift | Elbow | Flex | Roll | GRASP TCP XYZ mm | C XY 거리 | tool/jaw error |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| HOME | -2.593407 | -65.274725 | +77.406593 | +17.890110 | -12.615385 | `[+20.324,-253.265,+99.167]` | 93.008 mm | N/A |
| LIFT_RELIEF | -2.593407 | -60.000000 | +77.406593 | +17.890110 | -12.615385 | `[+20.078,-247.837,+81.035]` | 95.372 mm | 26.398° / 23.526° |
| COUPLED_TRANSITION | +1.766228 | -49.248339 | +75.702841 | +4.123360 | -12.595620 | `[+2.434,-265.240,+87.655]` | 71.684 mm | 20.557° / 17.745° |
| WRIST_COUPLED | +6.125862 | -38.496677 | +73.999088 | -9.643391 | -12.575856 | `[-17.668,-279.397,+93.013]` | 47.701 mm | 14.599° / 12.000° |
| WRIST_COUPLED_FINAL | +10.485496 | -27.745015 | +72.295335 | -23.410141 | -12.556092 | `[-39.613,-289.613,+97.103]` | 23.718 mm | 8.601° / 6.298° |
| C_PRE_APPROACH | +14.845130 | -16.993354 | +70.591582 | -37.176891 | -12.536328 | `[-62.635,-295.316,+100.000]` | 0.000002 mm | 3.090° / 0.673° |

```text
waypoint count                        = 62
maximum per-joint step                = 0.983339°
minimum GRASP TCP Z                   = 81.035347 mm
minimum TCP/table proxy margin        = +26.376347 mm
minimum non-base link/table margin    = +40.222700 mm
minimum self-collision centerline     = 55.827804 mm
minimum calibration servo margin      = 17.604407°
full mesh/environment                 = NOT_VERIFIED
```

## 변경 파일과 검증

- `scripts/plan_home_to_c_pre_approach.py`: 포트를 열 수 없는 오프라인 후보 planner
- `configs/home_to_c_pre_approach_planning_20261012.json`: 고정 입력과 실측 근거
- `configs/live_c_pre_approach_from_home_20261012.json`: HOME 전용 live config
- `scripts/live_c_approach.py`: HOME 승인 문구와 기존 축별 HOME tolerance 지원, start pose/승인 문구 결합 검사
- `tests/test_plan_home_to_c_pre_approach.py`, `tests/test_live_c_approach.py`: 후보 선택·FK proxy·start gate 회귀

검증 결과:

```text
focused regression tests = 53/53 PASS
py_compile               = PASS
exact runner dry-run     = PASS
git diff --check         = PASS
hardware command         = 0
follower port open       = 0
Goal/Torque write        = 0
```

Jetson의 기존 폴더와 LeLab service는 수정하지 않고 새 전용 폴더에 runner/config 사본만 배포했다.

```text
Jetson directory = /home/jetson3/so101-home-c-pre-approach-20261012/
runner SHA256     = 44bf9e782e6e8055b507eafc04896a2beb37f6190c88e045f0eb0b208d67c590
config SHA256     = f9a63ec428a29b0b612b7ffec17a3b65f018163e0a0693cec1816b8339dfde36
local/Jetson SHA  = MATCH
Jetson py_compile = PASS
Jetson dry-run    = PASS: no port opened; no send_action
```

## 현재 판정

```text
canonical START_POSE = HOME
SAFE_HIGH role       = RECOVERY_FALLBACK_OPTIONAL_TRANSPORT_ONLY
HOME_NEAR            = true
HOME→C PRE_APPROACH  = OFFLINE_READY
actual motion        = NOT_RUN / NOT_AUTHORIZED
full mesh/environment= NOT_VERIFIED
```

다음 실제 단계는 HOME fresh gate를 다시 통과한 뒤 C PRE_APPROACH까지만 실행한다. APPROACH, GRASP, LIFT는 포함하지 않는다.

```text
RUN HOME TO C PRE APPROACH
```
