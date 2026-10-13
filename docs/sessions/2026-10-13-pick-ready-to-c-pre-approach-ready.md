# 2026-10-13 PICK_READY→C PRE_APPROACH 오프라인 준비

## 범위

canonical `PICK_READY` 실측 자세를 시작점으로 새 PICK GRASP TCP 기준 C PRE_APPROACH까지의 경로만 새로 생성했다. 과거 HOME→C 실패 경로, HOME 전용 절대 Lift anchor, SAFE_HIGH 경로는 재사용하지 않았다.

변경 금지 기준선은 그대로 유지했다.

```text
table→robot calibration = unchanged
C robot XY              = [-62.635354,-295.315566] mm
PIN TIP TCP             = calibration only
PICK GRASP TCP          = [-4.748354423,-12.033741060,-124.531737248] mm
C PRE_APPROACH endpoint = [+14.845130,-16.993354,+70.591582,-37.176891,-12.536328] deg
```

## 실제 시작점

`configs/poses.yaml`에 저장된 3회 동일 표본의 평균을 사용했다.

```text
PICK_READY joints =
[-4.263736,-68.703297,+68.879121,+8.131868,-23.516484] deg

GRASP TCP = [+30.308815,-276.029085,+184.960142] mm
```

## 후보 탐색

낮은 Lift에서 Elbow를 먼저 크게 움직이지 않는 원칙을 유지해 다음 9개 조합을 비교했다.

```text
relative Lift relief = +2 / +4 / +6 deg
Wrist delay          = 25 / 35 / 45 percent
max joint step       = 1 deg
```

첫 stage는 Lift만 움직이고 Elbow/Wrist는 유지한다. 이후 Pan/Lift/Elbow/Roll을 결합하고 Wrist Flex를 지연 결합한다. 모든 후보는 새 PICK_READY로부터 다시 생성했으며 HOME 고정 경로를 사용하지 않았다.

선정 후보:

```text
RELIEF_PLUS_2P0_WRIST_DELAY_25
Lift relief target        = -66.703297 deg
expected Lift raw delta   = 23
measured effective basis  = 18 raw
waypoint count            = 63
maximum per-joint step    = 1.000000 deg
```

stage progression:

| stage | Pan | Lift | Elbow | Flex | Roll | GRASP TCP XYZ mm | C XY distance mm |
|---|---:|---:|---:|---:|---:|---|---:|
| PICK_READY | -4.263736 | -68.703297 | +68.879121 | +8.131868 | -23.516484 | `[+30.309,-276.029,+184.960]` | 94.924111 |
| LIFT_RELIEF | -4.263736 | -66.703297 | +68.879121 | +8.131868 | -23.516484 | `[+30.392,-277.143,+177.171]` | 94.785614 |
| WRIST_HOLD 25% | +0.513480 | -54.275811 | +69.307236 | +8.131868 | -20.771445 | `[+8.770,-277.212,+126.553]` | 73.664346 |
| WRIST_COUPLED 50% | +5.290697 | -41.848325 | +69.735351 | -6.971052 | -18.026406 | `[-14.053,-289.275,+119.151]` | 48.956799 |
| WRIST_COUPLED 75% | +10.067913 | -29.420840 | +70.163467 | -22.073971 | -15.281367 | `[-38.261,-295.421,+110.021]` | 24.374689 |
| C PRE_APPROACH | +14.845130 | -16.993354 | +70.591582 | -37.176891 | -12.536328 | `[-62.635,-295.316,+100.000]` | 0.000002 |

## 오프라인 검증

```text
GRASP TCP Z progression            = monotonic non-increasing
GRASP TCP Z range                  = 184.960142 → 100.000001 mm
minimum TCP/table point margin     = +45.341001 mm
minimum non-base link/table margin = +40.222700 mm
self-collision centerline margin   = 64.775222 mm PASS
minimum servo margin               = 24.419418 deg
final GRASP TCP target error       = 0.000002570 mm
final tool-axis error              = 3.089708 deg
final jaw-axis error               = 0.673228 deg
full mesh/environment              = NOT_VERIFIED
```

`configs/live_c_pre_approach_from_pick_ready_20261013.json`은 recorded PICK_READY와의 fresh-start gate를 적용한다.

```text
Pan/Flex/Roll start tolerance = 0.5 deg
Lift/Elbow start tolerance    = 1.5 deg
```

fresh follower가 이 범위를 벗어나면 first target 전 차단한다. 독립 안전 리뷰에서 기존 continuous-following telemetry가 온도를 읽지 않고 final `Moving=0`을 PASS 조건에 포함하지 않은 누락을 발견해 실행 전에 보완했다. 모든 fresh waypoint telemetry에서 6축 `Present_Temperature <=55°C`를 fail-closed로 검사하고, 최종 도달은 관절 tolerance·stable window와 함께 `Moving all 0`이어야 한다. 기존 error/no-progress, feedback freshness, servo, exclusive ownership, physical-stop gate는 유지하며 `Present_Load`는 numeric gate 없이 diagnostic only다.

## 검증과 배포

```text
record helper tests        = 5/5 PASS
new planner tests          = 5/5 PASS
live runner tests          = 22/22 PASS
continuous following tests = 10/10 PASS
exclusive transport tests  = 13/13 PASS
local py_compile/JSON       = PASS
local exact dry-run         = PASS: no port opened; no send_action
```

Jetson의 기존 디렉터리와 service는 수정하지 않고 다음 별도 폴더에 runner/config 사본만 배치했다.

```text
/home/jetson3/so101-pick-ready-c-pre-approach-20261013/
```

설치 LeLab Python py_compile과 exact dry-run이 통과했고 local/Jetson SHA가 일치했다.

```text
live_c_approach.py                                  592bad12...d15a3a
continuous_following_execution.py                   72d45298...58ab0
so101_exclusive_bus.py                              a578706c...92d37
so101_follower_transport.py                         6ded9bf6...149a
staged_cycle_execution.py                           e6f5fdca...6dd3d
live_c_pre_approach_from_pick_ready_20261013.json   043a8a36...db4f
```

이번 준비 중 actual motor/Goal/Torque command와 follower port open은 `0`이다. 실제 C PRE_APPROACH 이동은 `NOT_RUN/NOT_AUTHORIZED`다.

## 다음 승인

실행 직전 정지·비접촉·주변 clear, LeLab 세 control inactive, follower 포트 무점유, fresh PICK_READY gate를 다시 확인한다. 승인 범위는 C PREAPPROACH까지만이며 APPROACH, GRASP, LIFT는 포함하지 않는다.

```text
RUN PICK READY TO C PRE APPROACH
```
