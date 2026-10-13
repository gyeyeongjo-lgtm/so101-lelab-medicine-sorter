# 2026-10-13 CURRENT→C PRE_APPROACH 실기 1 — Wrist lead timeout FAIL

## 승인 범위

사용자가 `RUN CURRENT TO C PRE APPROACH`를 승인했다. 범위는 CURRENT→C PRE_APPROACH까지이며 APPROACH, gripper close, GRASP, LIFT는 포함하지 않았다.

## preflight 시도 1

일반 권한 `fuser`가 Jetson `/proc` 권한 오류를 보고한 뒤 fallback `sudo -n fuser`가 인증 cache 부재로 실패했다.

```text
result        = port_ownership_unknown
serial open   = 0
SEND          = 0
Goal write    = 0
Torque change = 0
motor command = 0
```

이는 motion failure가 아니라 privileged read-only ownership probe failure다. 같은 승인 범위에서 `sudo -v`로 검사 권한만 확보한 뒤 runner를 재시작했다.

## 실기 결과

runner fresh gate가 확인한 start:

```text
arm = [+11.648352,-20.967033,+72.219780,-31.956044,-14.197802] deg
gripper = 34.577723378% / human-confirmed CURRENT route state
```

nominal route 6 waypoint 중 Wrist-only lead 2 waypoint만 전송했다.

```text
Wrist start            = -31.956044 deg
Wrist phase target     = -33.956044 deg
Wrist final Present    = -32.835165 deg
commanded delta        = -2.000000 deg
achieved delta         = -0.879121 deg
achieved ratio         = 43.956%
phase target error     = +1.120879 deg
post-stop Goal-Present = -1.142857 deg
Moving                 = all 0
failure                = final_joint_target_timeout
```

controller는 phase final tolerance `0.5°`를 완화하지 않고 ABORT했다. coupled finish target 4개는 전송하지 않았고 자동 재시도도 없었다.

## STOPPED 후 fresh feedback

사용자가 `STOPPED`를 확인했고 runner가 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`를 출력한 뒤 command-owning session을 종료했다. 별도 read-only 3회가 동일했다.

```text
Present arm deg =
[+11.736263736,-20.615384615,+72.747252747,-32.835164835,-14.197802198]

Gripper Present = 34.516523868% / raw 977
Gripper Goal    = 34.577723378% / raw 978
Goal raw        = [2234,1716,2805,1694,1703,978]
Present raw     = [2235,1720,2811,1707,1703,977]
Moving          = all 0
Load diagnostic = [0,28,36,64,0,0]
Temperature C   = max 39
Torque_Enable   = all 1
read-only writes/torque changes = 0/0
port released on read exit      = true
```

Wrist-only target 중 비명령 drift는 Pan `+0.087912°`, Lift `+0.351648°`, Elbow `+0.527473°`, Roll `0°`다. 모두 1° 이내지만 FK는 다음과 같다.

```text
GRASP TCP before = [-45.686225,-292.662760,+93.788216] mm
GRASP TCP after  = [-45.923279,-291.710762,+92.527143] mm
delta            = [-0.237054,+0.951998,-1.261073] mm
TCP Z gate       = FAIL
```

로그:

```text
SEND  = 2
PAUSE = 50
ABORT = 1
SHA256 = 1f1f33e116ed8774c42c57d9bbc00b5aa52205cd461dfeeb60e1bad54c12594f
```

원본 JSONL은 Jetson 실행 폴더에만 보존하고 repository에 커밋하지 않는다.

## 다음 경로 offline 검토

종료 후 fresh pose에서 기존 endpoint·C XY·GRASP TCP를 유지하고 재계산했다.

```text
current->target joint delta =
[+3.108866,+3.622031,-2.155671,-4.341726,+1.661474] deg

DIRECT_COUPLED waypoint count       = 5
maximum joint step                  = 1.0 deg
predicted TCP Z                     = 92.527143 -> 100.000001 mm
minimum predicted Z step            = +1.477010 mm
minimum TCP table proxy margin      = +37.868143 mm
self-collision centerline margin    = 63.903077 mm / PASS
minimum servo margin                = 22.263747 deg
full mesh/environment               = NOT_VERIFIED
```

`DIRECT_COUPLED`는 offline proxy에서 valid이지만 아직 live ready가 아니다. fresh gripper가 이번 human-confirmed exact state raw `978`에서 raw `977` / `34.516524%`로 변했다. global 35% gate나 exact-state policy를 임의로 완화하지 않고, 사용자가 현재 opening을 다시 육안 확인하기 전에는 live plan을 승인 가능 상태로 만들지 않는다.

## 판정

```text
CURRENT_TO_C_PRE_APPROACH = FAIL
FAIL_REASON               = WRIST_LEAD_FINAL_TARGET_TIMEOUT
WRIST_ACHIEVED_RATIO      = 43.956%
TCP_Z_DELTA               = -1.261073 mm
COUPLED_TARGET_SEND       = 0
PRE_APPROACH_PASS         = false
APPROACH/GRASP/LIFT       = NOT_RUN
physical_stop             = FEEDBACK_AND_HUMAN_CONFIRMED
DIRECT_COUPLED_OFFLINE    = VALID_PROXY
DIRECT_COUPLED_LIVE_READY = false
```
