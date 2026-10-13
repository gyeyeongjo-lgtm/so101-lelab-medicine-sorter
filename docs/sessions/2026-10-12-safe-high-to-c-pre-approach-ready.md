# 2026-10-12 SAFE_HIGH→C PRE_APPROACH 오프라인 준비

## 전략 변경

- HOME↔SAFE_HIGH automatic round trip은 현재 C→RED critical path에서 제외했다.
- HOME 기록은 보존한다. HOME trace recording/replay와 synthetic HOME 경로는 현재 중단한다.
- 기록된 SAFE_HIGH를 canonical `START_POSE / VISION_READY`로 사용한다.
- 이번 작업은 완전 오프라인이다. follower port, serial, Goal, Torque, service, camera를 건드리지 않았다.

## 고정 입력

```text
SAFE_HIGH joints =
[+1.274725,+22.901099,-73.274725,+43.120879,-15.252747] deg

SAFE_HIGH GRASP TCP =
[+2.090996,-389.902432,+364.853599] mm

C robot XY = [-62.635354,-295.315566] mm
C pre-approach Z = 100.000000 mm

PICK GRASP TCP =
[-4.748354,-12.033741,-124.531737] mm
```

PIN TIP TCP는 삭제하거나 변경하지 않고 calibration 전용으로 유지한다.

## endpoint와 orientation

```text
C PRE_APPROACH joints =
[+14.845130,-16.993354,+70.591582,-37.176891,-12.536328] deg

FK GRASP TCP =
[-62.635356,-295.315566,+100.000001] mm

GRASP_TCP→C pre-approach error = 0.000002570 mm
full orientation error = 3.090411 deg
tool-axis error = 3.089709 deg
jaw-axis error = 0.673228 deg
```

orientation reference는 실제 C grasp가 확인된 과거 follower 자세다. position-only 0만으로 승인하지 않고 위 orientation error도 config와 test에 고정했다.

## 실행기 기준 경로

기존 `live_c_approach.py`의 staged interpolation과 bounded continuous-following 구조를 그대로 사용한다. Lift/Elbow coupling과 Wrist delay를 보존하는 25/50/75% intermediate posture 세 개를 둔다.

| 지점 | Pan | Lift | Elbow | Flex | Roll | GRASP TCP XYZ mm |
|---|---:|---:|---:|---:|---:|---|
| SAFE_HIGH | +1.274725 | +22.901099 | -73.274725 | +43.120879 | -15.252747 | `[+2.090996,-389.902432,+364.853599]` |
| Stage 1 | +4.667326 | +10.622141 | -44.060787 | +29.737917 | -14.573642 | `[-20.241178,-395.080608,+337.611770]` |
| Stage 2 | +8.059928 | +0.768265 | -8.444937 | +7.432981 | -13.894538 | `[-42.896816,-396.396594,+277.731591]` |
| Stage 3 | +11.452529 | -8.339157 | +30.067914 | -14.871955 | -13.215433 | `[-59.777257,-366.352367,+189.929233]` |
| PRE_APPROACH | +14.845130 | -16.993354 | +70.591582 | -37.176891 | -12.536328 | `[-62.635356,-295.315566,+100.000001]` |

```text
waypoint count                     = 146
maximum per-joint step             = 0.989329 deg
GRASP TCP Z range                  = 364.853599 ... 100.000001 mm
GRASP TCP Z progression            = monotonic non-increasing
minimum TCP/table proxy margin     = +45.341001 mm
minimum link-origin/table margin   = +40.222700 mm
minimum self-collision centerline  = 64.775222 mm (PASS proxy)
minimum calibration servo margin   = 21.736275 deg
full mesh/environment              = NOT_VERIFIED
```

table 값은 TCP point와 URDF link-origin proxy이며 실제 triangle mesh 검증으로 승격하지 않는다.

## fresh start gate

live 전 supervised teleop은 종료되어야 하고 follower port가 release된 상태여야 한다. 실행 직후 fresh follower feedback을 읽고 저장된 SAFE_HIGH 전 arm joint와 최대 `1.0°` 이내일 때만:

```text
START_POSE_CONFIRMED=SAFE_HIGH
```

를 출력하고 경로를 생성한다. 범위를 벗어나면 target을 보내기 전에 fail-closed한다. fresh gripper 값은 전 구간 hold한다.

## 변경과 검증

- 추가: `configs/live_c_pre_approach_from_safe_high_20261012.json`
- 수정: `scripts/live_c_approach.py`
  - 기존 runner에 allowlisted 승인 문구 추가
  - SAFE_HIGH start name/tolerance 검증 및 확인 출력 추가
  - config의 orientation/collision 상태를 dry-run에 그대로 표시
- 수정: `tests/test_live_c_approach.py`
  - 기록 SAFE_HIGH 일치, 146-waypoint 생성, max step, FK endpoint, table/self-collision/servo proxy, orientation을 재계산
  - 미등록 승인 문구 fail-closed 검사

```text
unit tests = 19/19 PASS
selected tests including trace regressions = 38/38 PASS
py_compile = PASS
dry-run = PASS
git diff --check = PASS
hardware command = 0
follower port open = 0
Goal/Torque write = 0
actual motion = NOT_RUN/NOT_AUTHORIZED
```

Jetson의 기존 실기 폴더와 LeLab 서비스는 수정하지 않았다. 새 전용 경로에 실행 사본만 배포하고 설치 LeLab Python으로 같은 dry-run을 통과했다.

```text
Jetson directory = /home/jetson3/so101-safe-high-c-pre-approach-20261012/
runner SHA256 = 664ec12cb11c5b17f76531e921b3dde00c839618ef7f2cf9837e4f5c8870ef33
config SHA256 = efd8e2945b41892d0be4109ccd132fcfc8ee7eeefeb01c79333d383a678f2064
local/Jetson SHA match = PASS
Jetson py_compile = PASS
Jetson dry-run = PASS: no port opened; no send_action
service restart / USB / Goal / Torque = 0
```

## 다음 승인

```text
RUN SAFE HIGH TO C PRE APPROACH
```
