# 2026-10-13 CURRENT→C PRE_APPROACH — human-confirmed gripper clearance READY

## 범위

사용자는 현장에서 현재 gripper opening이 C 약통을 받아들이기에 최분하고 추가 opening은 기계적으로 불안하다고 판단했다. 따라서 36% opening을 취소하고 현재 exact gripper feedback만 이번 CURRENT→C run의 human-confirmed clearance로 인정했다.

```text
global minimum opening = 35.0% (unchanged)
route-local policy     = HUMAN_CONFIRMED_CURRENT_STATE
confirmed Present      = 34.57772337821298%
confirmed raw          = 978
RUN GRIPPER OPEN TO 36 ONLY = CANCELLED_BY_USER
```

C XY, GRASP TCP, table calibration은 변경하지 않았다.

## fresh read-only feedback

LeLab teleoperation/recording/inference inactive를 먼저 확인했다. write·sync_write·torque API를 차단한 기존 read-only 도구로 follower를 `0.2 s` 간격 3회 읽었고 세 표본의 Present가 동일했다.

```text
Present arm deg =
[+11.736263736,-20.967032967,+72.219780220,-31.956043956,-14.197802198]

Gripper Present = 34.577723378% / raw 978
Gripper Goal    = 35.006119951% / raw 985
Goal raw        = [2232,1710,2795,1706,1703,985]
Present raw     = [2235,1716,2805,1717,1703,978]
Moving          = all 0
Load diagnostic = [24,36,52,56,0,-40]
Temperature C   = max 39
Torque_Enable   = all 1
motor writes    = 0
torque changes  = 0
port released   = true
```

## route-local gate

`minimum_fresh_gripper_open_percent=35.0`을 유지했다. CURRENT route에만 추가된 helper는 다음 중 하나만 인정한다.

1. fresh Present `>=35%`
2. policy가 `HUMAN_CONFIRMED_CURRENT_STATE`이고 Present가 exact normalized `34.57772337821298%`; raw가 제공되는 pre-send gate에서는 raw도 `978`

`34.9%`, `34.5%`, wrong raw는 FAIL이다. initial, verified-start, pre-send 모두 같은 helper를 사용하며 다른 route나 global calibration을 완화하지 않는다.

## fresh CURRENT→C 오프라인 재검증

```text
candidate                         = WRIST_LEAD_2DEG
waypoints                         = 6
max joint step                    = 1.0 deg
joint delta                       = [+3.108866,+3.973679,-1.628198,-5.220847,+1.661474] deg
GRASP TCP start                   = [-46.099790,-292.560444,+93.788217] mm
GRASP TCP after Wrist lead        = [-46.564437,-294.797166,+99.857310] mm
GRASP TCP endpoint                = [-62.635356,-295.315566,+100.000001] mm
TCP Z progression                 = MONOTONIC_INCREASING
minimum Z increase/waypoint       = +0.002029 mm
C XY distance                     = 16.763519 -> 0.000002259 mm
minimum TCP table proxy margin    = +39.129217 mm
self-collision centerline margin  = 64.775222 mm / PASS
minimum servo margin              = 22.791220 deg
full mesh/environment             = NOT_VERIFIED
```

## 검증·배치

- local targeted tests: `61/61 PASS`
- local py_compile/JSON/diff-check: `PASS`
- local CURRENT→C explicit dry-run: `PASS / no port opened / no send_action`
- Jetson runner SHA: `50bbec67858cbb32ee8a2d0b4003ec8117e4413796ea8b994034a7aad215f481`
- Jetson route SHA: `e8afb3f2b7998d8045649ae594e09b28b306393f8305e536e23dee46eb0909b1`
- local/Jetson SHA: `MATCH`
- Jetson installed Python compile and CURRENT→C dry-run: `PASS`
- cancelled 36% plan: `GRIPPER_OPEN_NOT_STARTED: gripper_open_plan_cancelled_by_user`

첫 cancelled-plan 검증에서 gripper CLI가 explicit `--dry-run`을 지원하지 않는 것을 놓쳐 argparse exit `2`가 나왔다. 이는 port open 전이고 hardware command는 `0`이다. 지원되는 기본 dry-run 호출로 재실행해 cancelled gate의 정상 차단을 확인했다.

마지막에 LeLab 세 control은 모두 inactive였고, privileged `fuser /dev/ttyACM1`은 점유자 출력 없음(rc `1`)이다.

## 판정

```text
GRIPPER_OPEN_CONFIRMED            = true (this CURRENT run only)
GLOBAL_35_PERCENT_GATE            = UNCHANGED
RUN_GRIPPER_OPEN_TO_36_ONLY       = CANCELLED_BY_USER
CURRENT_TO_C_PRE_APPROACH_OFFLINE = PASS
CURRENT_TO_C_PRE_APPROACH_LIVE    = NOT_RUN / NOT_AUTHORIZED
hardware command                 = 0
follower port                    = FREE
```

다음 live action은 사용자의 별도 승인 `RUN CURRENT TO C PRE APPROACH`만 받아 실행한다.
