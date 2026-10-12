# SAFE_ESCAPE static-deadband 후보 오프라인 비교

날짜: 2026-10-12

## 범위

- 기존 실기 로그와 저장 calibration/URDF만 사용했다.
- Jetson, serial port, motor, Goal/Torque, service, camera에 접근하지 않았다.
- GRASP TCP `[-4.748354,-12.033741,-124.531737] mm`, C XY, PICK endpoint, table proxy 해석, tolerance를 변경하지 않았다.
- raw feed-forward는 사용하지 않았다.

## 실측 deadband 근거

직전 `SAFE_ESCAPE_1DEG`:

```text
Lift/Elbow Goal-Present = -12 raw
Lift/Elbow Present movement = 0 raw
Moving = 0
Load = 60
```

전체 실기가 `PRE_APPROACH_PASS`를 낸 `WRIST_DELAY_25` 로그에서 현재 Elbow 자세/Load와 가장 가까운 coupled waypoint 50–53을 추출했다. `Goal-prev Present raw`는 해당 target 송신 직전 표본과 Goal의 차이고, `toward movement`는 다음 fresh Present가 Goal 방향으로 움직인 raw 양이다.

| waypoint | Lift feedback | Lift gap / toward / load | Elbow feedback | Elbow gap / toward / load |
|---:|---:|---:|---:|---:|
| 50 | +8.571° | +12 / 12 / 0 | +18.154° | -18 / 7 / 56 |
| 51 | +9.538° | +11 / 11 / 0 | +17.626° | -20 / 6 / 68 |
| 52 | +10.418° | +11 / 10 / 0 | +16.747° | -23 / 10 / 64 |
| 53 | +11.209° | +12 / 9 / -24 | +15.692° | -22 / 12 / 52 |

같은 성공 로그의 waypoint 54–71에서 Elbow Goal이 고정된 후 gap `10–14 raw`, load `52–68`일 때는 Present가 정체하거나 하중 방향으로 1 raw drift했다. 따라서 현 자세의 Elbow에 대해:

```text
10–14 raw = measured non-effective/stalled range
18 raw    = smallest measured effective gap in the successful run
20–23 raw = repeated effective movement range
```

`live_c_approach_only_attempt1` 전체는 final Elbow timeout으로 실패했으나 개별 waypoint 움직임은 보조 근거다. Elbow gap `-12 raw/load 60`에서 이동 0, `-15 raw/load 68`에서 목표 방향 1 raw, `-21 raw/load 88`에서 2 raw였다. 이 결과도 `18–23 raw`가 더 신뢰할 수 있는 출발 범위라는 판정과 모순되지 않는다.

Lift는 성공 로그에서 목표 방향 이동이 `11–12 raw`에서 시작됐지만, 그 표본은 현재와 반대 방향이고 load도 `-24…0`이다. 현재 Lift 방향/Load `60`에 대한 직접 threshold 증거로 사용하지 않는다.

## 계산 기준

직전 종료 후 read-only fresh pose를 오프라인 기준으로 사용했다.

```text
current joints deg = [+0.307692,+18.153846,+14.813187,+9.890110,+14.637363]
current raw        = [2105,2161,2152,2193,2031]
escape direction  = [+,-,-,-,+]
```

raw는 저장 follower calibration raw midpoint와 LeRobot DEGREE normalization `raw=int(deg*4095/360+midpoint)`으로 계산했다. 이 식은 1° 실기의 계산 Goal raw `2111/2149/2140/2190/2036`과 전축에서 일치했다.

## 후보 비교

joint/target/raw 순서는 `Pan/Lift/Elbow/Flex/Roll`이다.

| candidate | first target joints ° | joint delta ° | expected raw target | expected raw delta | GRASP TCP XYZ mm | target table proxy margin | self-collision centerline proxy | servo margin |
|---|---|---|---|---|---|---:|---:|---:|
| SAFE_ESCAPE_1P5DEG | `[+1.807692,+16.653846,+13.313187,+8.390110,+16.137363]` | `[+1.5,-1.5,-1.5,-1.5,+1.5]` | `[2122,2143,2134,2175,2048]` | `[+17,-18,-18,-18,+17]` | `[-3.416186,-376.245640,+69.878524]` | `+15.219524 mm` | `64.775222 mm` | `80.197813°` |
| **SAFE_ESCAPE_2DEG** | `[+2.307692,+16.153846,+12.813187,+7.890110,+16.637363]` | `[+2,-2,-2,-2,+2]` | `[2127,2138,2129,2170,2053]` | `[+22,-23,-23,-23,+22]` | `[-6.638732,-379.281955,+76.405304]` | `+21.746304 mm` | `64.775222 mm` | `80.197813°` |
| SAFE_ESCAPE_2P5DEG | `[+2.807692,+15.653846,+12.313187,+7.390110,+17.137363]` | `[+2.5,-2.5,-2.5,-2.5,+2.5]` | `[2133,2132,2123,2164,2059]` | `[+28,-29,-29,-29,+28]` | `[-9.907916,-382.141743,+83.023475]` | `+28.364475 mm` | `64.775222 mm` | `80.197813°` |

각 segment를 0.1° 간격으로 FK 재검산했다. 현재 시작 virtual GRASP point가 단일 P1 plane 기준으로 낮으므로 세 segment 모두 전체 minimum proxy는 `-3.777924 mm`이다. 위 표의 table margin은 **first target에서의 commanded-point margin**이다. 기존 판정을 유지한다.

```text
ROOT_CAUSE_OF_NEGATIVE_PROXY
= VIRTUAL_GRASP_POINT_VS_SINGLE_P1_INFINITE_PLANE_AT_SAVED_START

ACTUAL_LINK_TABLE_COLLISION = NOT_VERIFIED
FULL_MESH_COLLISION         = NOT_VERIFIED
```

## 추천

```text
RECOMMENDED_MINIMUM_EFFECTIVE_ESCAPE = SAFE_ESCAPE_2DEG
```

근거:

1. 1.5°의 Elbow `18 raw`는 실측 성공 경계와 동일하여 하중·방향 차이에 대한 여유가 없다.
2. 2.0°의 Elbow/Lift/Flex `23 raw`는 성공 window에서 Elbow가 반복적으로 이동한 `20–23 raw` 범위의 상단이다.
3. 2.5°의 `29 raw`까지 키워야 한다는 실측 근거는 없고 단일 joint-space 이동만 커진다.
4. 2.0° target은 target P1 proxy, centerline self proxy, servo bounds를 오프라인에서 통과한다. 단 full mesh는 검증되지 않았다.

Lift의 현재 방향/Load가 일치하는 성공 표본이 없으므로 이 추천은 `LIKELY_MINIMUM`, 실기 성공 확정이 아니다. 실행 전에는 fresh pose로 다시 rebase하고, 별도 현장 clearance 확인과 명시 승인을 받아야 한다.

## 결과 상태

```text
actual motor command = 0
hardware access      = 0
candidate execution  = NOT_RUN / NOT_AUTHORIZED
path/endpoint change = 0
tolerance change     = 0
raw feed-forward     = NOT_USED
commit/push          = NOT_COMMITTED / NOT_PUSHED
```

## 근거 파일

- `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_delayed_wrist_fresh5_attempt1.jsonl`
- `.local/c-red-pivot-tcp-table-20261011-s01/live_c_approach_only_attempt1.jsonl`
- `configs/so101_follower_calibration_bounds_20261008.json`
- `.local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf`
- `docs/sessions/2026-10-12-safe-escape-preflight.md`
