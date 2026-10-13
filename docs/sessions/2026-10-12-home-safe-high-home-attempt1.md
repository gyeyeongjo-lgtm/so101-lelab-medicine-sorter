# 2026-10-12 HOME→SAFE_HIGH→HOME 1회 실기 1 — waypoint 1 FAIL·STOPPED

## 승인 범위

- 사용자 승인: `RUN HOME SAFE_HIGH HOME ONCE`
- 허용 범위: 기록된 HOME에서 SAFE_HIGH를 거쳐 HOME으로 돌아오는 자동 왕복 1회
- 3회 반복, grasp/place, Torque/gain/register 변경은 승인·실행하지 않았다.

## 실행 전 차단과 복구

- 첫 시작은 motor command 전에 `port_ownership_unknown`으로 fail-closed됐다. Goal/Torque write와 serial open은 `0`이었다.
- 원인은 follower 점유가 아니라 unprivileged `fuser`의 `/proc` permission error 뒤 `sudo -n fuser`가 관리자 인증 캐시 없이 실행되어 privileged scan을 완료하지 못한 것이었다.
- USB identity는 `/dev/ttyACM1 = 5AE6058306`, LeLab teleoperation/recording/inference는 모두 inactive였다.
- 사용자가 제공한 SSH/sudo 인증으로 같은 승인 범위 안에서 privileged `fuser rc=1 / unowned`를 확인한 뒤 한 번 다시 시작했다. ownership gate를 우회하거나 완화하지 않았다.

## 실제 전송 결과

- fresh HOME start는 기록 pose와 일치해 start gate를 통과했다.
- 총 156 waypoint 중 **waypoint 1 하나만** 전송했다.
- waypoint 1 segment: `SAFE_HIGH_EXCEPT_PAN`

```text
requested arm target deg:
Pan   -2.593407
Lift -64.114517
Elbow +75.423944
Flex  +18.222094
Roll  -12.650087

Goal raw    = [2072,1225,2841,2287,1720,446]
Present raw = [2072,1227,2864,2288,1721,446]

Present after deg:
Pan   -2.593407
Lift -63.956044
Elbow +77.406593
Flex  +18.241758
Roll  -12.615385
```

관절별 실제 이동:

| 관절 | requested delta | achieved delta | achieved ratio | 판정 |
|---|---:|---:|---:|---|
| Lift | `+1.160208°` | `+1.318681°` | `113.659%` | PASS |
| Elbow | `-1.982649°` | `0.000000°` | `0.000%` | FAIL |
| Wrist Flex | `+0.331984°` | `+0.351648°` | `105.923%` | PASS |

- Elbow Goal-Present error는 `+1.982649°`, Moving `0`, Load diagnostic `104`였다.
- 모든 축 Moving은 `0`, 최고 Temperature는 Elbow `52°C`로 temperature gate는 통과했다.
- Present_Load는 numeric safety gate가 아니라 diagnostic으로만 기록했다.

## TCP·proxy 판정

```text
GRASP TCP before = [20.324187,-253.265255,99.167465] mm
GRASP TCP after  = [20.241125,-251.432048,93.640789] mm
delta Z          = -5.526677 mm
table margin     = +38.981789 mm
self-collision centerline proxy = 55.827804 mm
full mesh/environment = NOT_VERIFIED
```

- 명목 경로는 Elbow 감소가 Lift/Wrist 변화의 Z 감소를 상쇄하는 coupled waypoint였다.
- 실물에서는 Elbow가 움직이지 않고 Lift/Wrist만 움직여 GRASP TCP Z와 table proxy margin이 악화됐다.
- `movement_ok=false`와 `table_proxy_ok=false`로 `waypoint_verification_failed:1`이 발생했다.
- 실행기는 후속 155개 target을 전송하지 않고 STOP prompt로 이동했다.

## 정지·종료

- 사용자 `STOPPED`와 fresh feedback 정지 검증으로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`를 복구했다.
- 종료 후 privileged follower `fuser rc=1 / unowned`다.
- LeLab teleoperation/recording/inference는 모두 inactive다.
- Torque는 변경하지 않았다.

## 오프라인 국소 진단

HOME에서 GRASP TCP Z의 중앙차분 민감도는 다음과 같다.

```text
dZ/dPan   = +0.000011 mm/deg
dZ/dLift  = -3.482535 mm/deg
dZ/dElbow = -5.062734 mm/deg
dZ/dFlex  = -2.741795 mm/deg
dZ/dRoll  = +0.161788 mm/deg
```

따라서 현재 SAFE_HIGH 방향의 첫 coupled step은 Elbow 감소가 실제로 따라오지 않으면 Z가 감소하는 구조다. 기존 HOME 기록 당시 Elbow Goal-Present는 이미 `-3.692308°`였고, 이번 `<=2°` Elbow target은 그 기존 gap보다 작은 명령이므로 Elbow를 새롭게 움직일 근거가 없었다. 현재 경로를 그대로 재실행하지 않는다.

```ini
HOME_SAFE_HIGH_HOME_ONCE=FAIL
FAIL_WAYPOINT=1/156
FAIL_REASON=ELBOW_NO_MOVEMENT_AND_TCP_Z_DECREASE
FOLLOW_UP_TARGETS_SENT=0
THREE_ROUND_TRIPS=NOT_RUN/PROHIBITED
NEXT_LIVE_COMMAND=NONE
hardware_command_count=1
Torque_change=0
physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED
follower_port=FREE
full_mesh_environment=NOT_VERIFIED
git=NOT_COMMITTED/NOT_PUSHED
```
