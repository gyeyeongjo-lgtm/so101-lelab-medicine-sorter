# 2026-10-13 CURRENT→C DIRECT_COUPLED 재시험 READY

## 입력 기준선

사용자가 CURRENT→C 실기 1 종료 후 현재 finger opening을 현장에서 다시 확인했다.

```text
CURRENT OPENING CONFIRMED
Gripper Present = 34.516523867809056%
Present raw     = 977
```

이 확인은 이번 next CURRENT route에만 적용한다. global `minimum_fresh_gripper_open_percent=35.0`과 다른 route의 계약은 변경하지 않았다.

## 경로 정책

직전 `WRIST_LEAD_2DEG`는 achieved ratio `43.956%`에 그쳤고 실제 TCP Z가 `-1.261073 mm` 감소했다. 따라서 같은 Wrist-only phase를 재시도하지 않고, 정지 후 fresh pose에서 5축을 bounded coupled로 움직이는 가장 짧은 valid path를 선택했다.

```text
path candidate = DIRECT_COUPLED
fresh arm =
[+11.736263736,-20.615384615,+72.747252747,-32.835164835,-14.197802198] deg

target arm =
[+14.845130,-16.993354,+70.591582,-37.176891,-12.536328] deg

joint delta =
[+3.108866,+3.622031,-2.155671,-4.341726,+1.661474] deg
```

## offline 기하 검증

```text
waypoints                        = 5
maximum actual joint step        = 0.868345 deg
configured maximum step          = 1.0 deg
GRASP TCP start                  = [-45.923279,-291.710762,+92.527143] mm
GRASP TCP endpoint               = [-62.635356,-295.315566,+100.000001] mm
TCP Z progression                = MONOTONIC_INCREASING
minimum TCP Z increase/waypoint  = +1.477010 mm
C XY distance                    = 17.096434 -> 0.000002259 mm
minimum TCP table proxy margin   = +37.868143 mm
self-collision centerline margin = 63.903077 mm / PASS
minimum servo margin             = 22.263747 deg
tool-axis / jaw-axis error       = 3.089708 / 0.673228 deg
full mesh/environment            = NOT_VERIFIED
```

C XY, GRASP TCP, table calibration, endpoint는 변경하지 않았다.

## runner gate

기존 `live_c_approach.py`와 `bounded_continuous_following`을 재사용했다. 새 control framework를 만들지 않았다.

- start pose: `C_WRIST_LEAD_ACTUAL_ATTEMPT1`
- run phrase: `RUN CURRENT TO C PRE APPROACH`
- start/final tolerance: Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`, gripper final `2 pp`
- gripper gate: global `>=35%` 또는 exact human-confirmed percent/raw `34.516523868% / 977`
- initial, verified-start, pre-send 세 번 검증
- pre-send에서 raw mismatch면 target send `0`
- Temperature `<=55°C`, feedback freshness, Moving/following/no-progress gate 유지
- Present_Load: diagnostic only

## 검증·배치

```text
local targeted tests = 64/64 PASS
py_compile            = PASS
JSON validation       = PASS
git diff --check      = PASS
local dry-run         = PASS / no port opened / no send_action

Jetson runner SHA = 20bfc9e2b20cbe88ec6da2b52dae9ae43301c37c397dc63db04f7e440badc188
Jetson live config SHA = 11a7a09343904a2fc80bc96216fdf279d3c062e57cdd9de509a03c431aad4c7f
Jetson planning config SHA = f7ce7f19e1f6d1defa2eb793d7bd4d8768d1abbbe709b4838fe25eed2d8c4d80
local/Jetson SHA = MATCH
Jetson installed Python compile/dry-run = PASS
```

배치 후 read-only 3회는 plan의 fresh arm과 gripper raw `977`에 정확히 일치했다. Moving all `0`, Torque all `1`, Tmax `38°C`; read-only motor/torque change `0/0`, port released on exit다.

## 판정

```text
CURRENT_OPENING_CONFIRMED = true
DIRECT_COUPLED_OFFLINE    = PASS
DIRECT_COUPLED_DRY_RUN    = PASS
LIVE                      = NOT_RUN / NOT_AUTHORIZED
hardware command          = 0
```

다음 actual motor command는 사용자가 정지·비접촉·주변 clear를 유지한 상태에서 `RUN CURRENT TO C PRE APPROACH`를 새로 승인한 뒤에만 실행한다.
