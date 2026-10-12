# PICK GRASP TCP orientation-aware IK dry-run

날짜: 2026-10-12

## 범위와 불변 조건

- 저장된 URDF, JSON, trace만 사용한 순수 오프라인 계산이다.
- Jetson, camera, serial/follower port, LeLab service에 접근하지 않았다.
- motor/send_action/Goal_Position/Torque_Enable/gripper 명령은 `0`회이다.
- table→robot transform, C robot XY `[-62.635354,-295.315566] mm`, calibration은 변경하지 않았다.
- 현 follower로 쓴 자세는 마지막 저장 read-only snapshot `[-0.131868,+17.362637,+15.868132,+10.769231,+14.197802]°`이며, 이번 시점의 fresh feedback으로 승격하지 않는다.

## TCP frame 분리

```text
calibration_pin_tcp_offset_gripper_mm
= [-51.748354, -73.033741, -54.531737]

pick_grasp_tcp_offset_gripper_mm
= [ -4.748354, -12.033741, -124.531737]
Y uncertainty = -13.033741 .. -11.033741 mm
```

`scripts/c_red_vision_ik_dry_run.py`는 이제 PICK offset을 `--grasp-tcp-offset-mm`로 명시하지 않으면 calibration PIN TCP를 대신 사용하지 않고 차단한다. 오프라인 planner `scripts/plan_pick_grasp_tcp_ik.py`도 두 offset을 별도 필드로 검사한다.

## Orientation 기준

임의로 수직 tool-axis를 강제한 해는 Wrist Pitch servo 상한에 닿아 제외했다. 대신 2026-10-09 C→RED 수동 시연에서 사용자가 C 실제 grasp와 소폭 lift를 확인한 경계 `cycles.jsonl seq=60668` follower feedback

```text
[+18.065934, -11.296703, +60.000000, -32.307692, -11.560440]°
```

의 gripper rotation을 jaw orientation reference로 사용했다. SO-101은 arm 5축이므로 임의 6-DoF pose를 모두 정확히 강제하지 않고, reference orientation을 최소화한 branch를 찾은 뒤 GRASP TCP 위치를 정밀하게 재수렴시켰다.

## Endpoint 결과

| 항목 | pre-approach Z=100 mm | approach Z=80 mm |
|---|---:|---:|
| Pan | `+14.845130°` | `+14.845119°` |
| Lift | `-16.993354°` | `-2.443040°` |
| Elbow | `+70.591582°` | `+70.635112°` |
| Wrist Flex | `-37.176891°` | `-51.770491°` |
| Wrist Roll | `-12.536328°` | `-12.536312°` |
| GRASP TCP FK | `[-62.635354,-295.315566,100.000000] mm` | `[-62.635354,-295.315566,80.000000] mm` |
| GRASP TCP position error | `2.8e-8 mm` | `2.3e-8 mm` |
| full orientation error | `3.090411°` | `3.090420°` |
| tool-axis error | `3.089709°` | `3.089719°` |
| demonstrated jaw local-X error | `0.673228°` | `0.673464°` |
| minimum servo margin | `24.419418°` | `24.375888°` |

Approach endpoint에서 C target까지의 frame별 거리:

```text
GRASP TCP     0.000000023 mm
PIN TCP       104.067287 mm
gripper origin 125.201883 mm
```

저장 follower snapshot→approach 관절 delta는

```text
[+14.976987, -19.805677, +54.766980, -62.539722, -26.734114]°
max |delta| = 62.539722° (Wrist Flex)
```

다.

## 경로·충돌 proxy

- current→pre 65 targets, pre→approach 24 targets, 총 89 targets다.
- Shoulder Lift progress exponent `0.85`, Elbow `1.15`, Wrist Flex delay `10%`로 Lift가 Elbow보다 약간 앞서고 Wrist를 뒤로 미룬다.
- max joint step `0.988613°`, servo minimum margin `24.375888°`.
- non-adjacent link centerline minimum `64.775222 mm`: skeleton self-collision proxy `PASS`.
- non-base link-origin minimum Z `94.881700 mm`.
- GRASP TCP path minimum Z `48.451603 mm`는 저장된 시작 자세에서 발생하며 current→pre는 이보다 더 내려가지 않는다.
- 그러나 과거 table-contact TCP reference `54.659 mm`와의 nominal margin은 `-6.207397 mm`다. GRASP TCP 자체가 coarse 실측 후보이므로 실제 관통을 뜻하지는 않지만, environment collision proxy를 PASS로 올릴 수는 없다.
- STL이 저장소에서 Git LFS pointer이고 정확한 C/작업대 environment mesh가 없으므로 full swept mesh collision은 `NOT_VERIFIED`.

Y offset 범위 `-13.034/-12.034/-11.034 mm`의 approach orientation error는 `3.277528/3.090420/2.903243°`였고 전 후보에서 수치 IK는 성립했다. 하지만 table proxy는 모두 BLOCKED다.

## 검증과 상태

- `python3 -m py_compile`: PASS
- 신규 planner unit tests: `3/3 PASS`
- nominal dry-run: PASS, output status `OFFLINE_DRY_RUN_ONLY`
- `git diff --check`: PASS
- OpenCV가 없는 현 Mac system Python에서 기존 vision test module 전체는 `NOT_RUN`; 이번 planner는 OpenCV에 의존하지 않는다.
- collision status: `NOT_VERIFIED_BLOCKED_PROXY`
- actual motor command: `0`
- follower port/Goal/Torque/camera/service/Jetson: `NOT_RUN`
- grasp/lift: `NOT_RUN`
- 변경: `NOT_COMMITTED/NOT_PUSHED`
