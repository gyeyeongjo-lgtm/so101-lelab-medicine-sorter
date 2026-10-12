# PICK table-collision proxy 국소 분리

날짜: 2026-10-12

## 범위

- GRASP TCP, calibration PIN TCP, C robot XY, pre-approach/approach endpoint는 고정했다.
- 저장된 89-target path의 table proxy와 URDF link/collision origin만 오프라인 재검산했다.
- motor/Goal/Torque/gripper/service/USB/camera 명령은 `0`회이다.

## 1. 최저 table margin sample

기존 `-6.207397 mm`는 89개 target 중의 waypoint가 아니다. planner가 path 앞에 포함한 저장 시작 snapshot, 즉 sample index 0이다.

| 항목 | 저장 시작 sample 0 | 실제 target 최저 waypoint 1 |
|---|---:|---:|
| joints `[Pan,Lift,Elbow,Flex,Roll] deg` | `[-0.131868,+17.362637,+15.868132,+10.769231,+14.197802]` | `[+0.098547,+16.374025,+16.318246,+10.769231,+13.786508]` |
| GRASP TCP XYZ mm | `[+8.564787,-361.894645,+48.451603]` | `[+7.214374,-361.926922,+51.751058]` |
| P1 Z=54.659 mm margin | `-6.207397 mm` | `-2.907942 mm` |

waypoint 2 margin은 `-1.104603 mm`, waypoint 3은 `+0.164633 mm`로 양수가 된다.

## 2. 가장 가까운 link와 mesh 한계

waypoint 1의 비-base moving link 중:

```text
lowest link centerline/origin = shoulder
shoulder link origin Z        = 94.881700 mm

lowest collision-element origin center
= shoulder / rotation_pitch_so101_v1.stl
Z = 48.481700 mm
```

collision-element origin은 mesh를 배치하는 기준점이지 mesh 최저 vertex가 아니다. 로컬 workspace에는 URDF가 참조하는 STL 삼각형 데이터가 없다. 이전 기록에서 Jetson uv cache의 실제 STL을 확인했으나, 이번 read-only SSH는 `Permission denied (publickey,password)`로 파일 경로 조회 단계에서 중단됐다. 따라서 waypoint 1 전후 ±3의 mesh 최저 Z와 full mesh-vs-table은 `NOT_VERIFIED/NOT_COMPUTABLE`이다.

## 3. `-6.207 mm` 해석

`-6.207397 mm`는 capsule radius를 빼서 만든 margin이 아니며, link mesh vertex가 table을 통과했다는 결과도 아니다. 물질이 없는 gripper opening-center 점의 Z에서 P1 contact Z 하나를 무한 평면으로 두고 뺀 값이다.

저장된 contact FK Z 자체도 다음처럼 산포한다.

```text
P1/P2/P3/P4 = 54.659 / 50.504 / 50.249 / 48.528 mm
H1/Repeat P1/Repeat P3 = 44.928 / 47.584 / 49.252 mm
```

P1–P4 least-squares plane은 현 GRASP-TCP XY에서 `Z=51.290 mm`, 전체 7점 plane은 `Z=48.670 mm`를 예측한다. 즉 P1 단일 무한 평면의 `-6.207 mm`는 보수적 proxy이며 **실제 link 침범의 증거가 아니다.** 반대로 contact FK 산포가 크므로 실제 무충돌 PASS의 증거로도 쓸 수 없다.

## 4. 최소 path-shape 후보

endpoint와 orientation을 고정하고, 시작 GRASP-TCP Z의 local joint gradient 부호로 첫 target만 조정했다.

| candidate | targets | first/commanded min table margin | full path min | self centerline min | final GRASP error | tool/jaw error | max step | servo margin |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BASELINE | 89 | `-2.907942 mm` | `-6.207397 mm` | `64.775222 mm` | `2.3e-8 mm` | `3.089719° / 0.673464°` | `0.988613°` | `24.375888°` |
| SAFE_ESCAPE_0.6DEG | 89 | `+1.179032 mm` | `-6.207397 mm` | `64.775222 mm` | 동일 | 동일 | `0.992923°` | `24.375888°` |
| **SAFE_ESCAPE_1DEG** | 90 | **`+6.186159 mm`** | `-6.207397 mm` | `64.775222 mm` | 동일 | 동일 | `1.000000°` | `24.375888°` |

`SAFE_ESCAPE_1DEG` first target:

```text
joints = [+0.868132,+16.362637,+14.868132,+9.769231,+15.197802] deg
GRASP TCP = [+2.514583,-369.024235,+60.845159] mm
```

이 후보는 first command 이후 P1-plane proxy를 양수로 만드는 가장 큰 여유를 1° 이하 step에서 준다. 다만 연속 경로는 음수 proxy인 시작점을 반드시 통과하므로, **시작 실물 clearance/full mesh 검증 전에 전체 path margin PASS라고 보고할 수 없다.**

## 판정

```text
ROOT_CAUSE_OF_NEGATIVE_PROXY
= VIRTUAL_GRASP_POINT_VS_SINGLE_P1_INFINITE_PLANE_AT_SAVED_START

ACTUAL_LINK_TABLE_COLLISION
= NOT_VERIFIED

RECOMMENDED_OFFLINE_PATH_CANDIDATE
= SAFE_ESCAPE_1DEG

MOTION_AUTHORIZED
= false
```

실행 전에는 fresh follower pose, 현장 시작 clearance, 실제 STL과 작업대의 유한 평면/footprint를 확인해야 한다. 이번 작업은 motor/Goal/Torque를 변경하지 않았고 grasp/lift를 실행하지 않았다. `NOT_COMMITTED/NOT_PUSHED`.
