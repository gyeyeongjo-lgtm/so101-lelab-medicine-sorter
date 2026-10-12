# C approach TCP frame 혼용 진단

날짜: 2026-10-12

## 범위와 안전 상태

- 코드, 저장 JSON, 설치 URDF 사본, 이미 확보된 관절값만 사용한 오프라인 계산이다.
- Jetson, LeLab, serial port, follower bus에 접근하지 않았다.
- motor/Goal_Position/Torque_Enable/gripper 명령, service restart, calibration capture는 모두 `NOT_RUN`이다.
- 사용자의 사진상 gripper opening center가 C와 정렬되지 않았으므로 `APPROACH_CONFIRMED`와 `APPROACH_PASS`는 부여하지 않는다.

## 1. Table→robot fit의 physical point

`scripts/pivot_tcp_capture.py`의 pivot 식은 다음과 같다.

```text
p_fixed = t_base_gripper + R_base_gripper @ tcp_offset_gripper
```

코드는 고정점의 물리적 이름을 구분하지 않지만, 사용자가 설명한 실제 pivot/capture 절차에서는 gripper 옆 장착부의 금속 핀 끝을 같은 작업대 점에 유지했다. 따라서 pivot 결과

```text
[-51.748354423, -73.033741060, -54.531737248] mm
```

는 현장 의미상 `PIN_TIP offset in gripper frame`이다.

`scripts/pivot_tcp_table_capture.py`는 각 5점 capture에서 다음을 계산했다.

```text
corrected_physical_tcp = gripper_origin + gripper_rotation @ tcp_offset
```

그리고 P1–P4의 이 XY를 table mark XY와 fit했다. 따라서 채택한 table→robot transform의 robot-side physical point는 PIN TIP이다. 기존 table scale, reflection, transform 및 C robot XY는 이 사실과 모순되지 않으며 재보정 대상이 아니다.

## 2. 현재 C IK가 맞춘 TCP

`scripts/c_red_vision_ik_dry_run.py::tcp_position_mm()`도 똑같이 다음 점을 IK residual에 사용한다.

```text
t_base_gripper + R_base_gripper @ tcp_offset_mm
```

현재 `configs/live_c_approach_only_20261012.json`에는 pivot offset이 그대로 `tcp_offset_gripper_mm`로 들어 있다. 따라서 현재 pre-approach/approach/grasp/lift 숫자상의 XYZ는 실제 opening center가 아니라 PIN TIP XYZ다.

현재 approach 입력:

```text
C robot XY                  = [-62.635354, -295.315566] mm
planner approach reference  = [-62.635354, -295.315566, 80.000000] mm
target arm deg              = [-0.096486, 17.400979, 14.407074, 10.648771, 14.577178]
```

주의: C의 물리적 3D 중심/실제 grasp 높이는 검증되지 않았다. 위 Z=80 mm는 현재 planner의 approach reference이며 `C physical XYZ`로 승격하지 않는다. 기존 dry-run의 grasp Z=50 mm도 `z_physically_verified=false`다.

## 3. Approach endpoint FK 수치

설치 URDF SHA `443d38d...f67236`, target joints, pivot offset으로 계산했다.

| point | base XYZ mm | approach reference까지 거리 |
|---|---:|---:|
| C/planner approach reference | `[-62.635354, -295.315566, 80.000000]` | `0` |
| PIN_TIP_TCP | `[-62.633534, -295.292436, 79.999429]` | `0.023209 mm` |
| GRASP_TCP exact | `NOT_VERIFIED` | `NOT_COMPUTABLE` |
| `gripper` link origin proxy | `[21.041429, -276.316864, 140.198749]` | `104.817194 mm` |
| field 62-mm vertical proxy | `[-62.633534, -295.292436, 141.999429]` | `61.999433 mm` |

PIN TIP에서 `gripper` origin proxy로 가는 base-frame vector는

```text
[+83.674963, +18.975571, +60.199320] mm
```

이며 base Z 차이 `+60.199320 mm`는 사용자가 관찰한 약 `+62 mm`와 `1.801 mm` 차이다. 다만 `gripper` link origin이 실제 opening center라는 정의는 URDF/코드에 없으므로 이 일치는 proxy 근거일 뿐 정확한 grasp offset 확정값은 아니다.

## 4. 마지막 settled feedback 교차검사

마지막 read-only settled arm feedback

```text
[-0.131868, 17.362637, 15.868132, 10.769231, 14.197802] deg
```

의 FK 결과:

| point | base XYZ mm | approach reference까지 거리 |
|---|---:|---:|
| PIN_TIP_TCP | `[-62.264998, -290.445675, 75.063370]` | `6.944301 mm` |
| `gripper` link origin proxy | `[21.191142, -273.431467, 136.146259]` | `103.238547 mm` |

이때 origin은 PIN보다 base Z `61.082888 mm` 높다. target endpoint의 `0.023 mm`와 달리 actual PIN이 `6.944 mm` 떨어진 것은 마지막 Elbow feedback이 target보다 `+1.461058°` 남아 있던 실제 관절 상태를 반영한다.

## 판정

```text
FRAME_MIXING_CONFIRMED_FOR_CURRENT_PICK_TARGET
```

- current IK가 C approach reference에 맞춘 점은 PIN TIP이다.
- opening center는 같은 점이 아니며, 현장 관찰과 FK proxy 모두 큰 잔여 offset을 지지한다.
- 정확한 `GRASP_TCP`는 아직 `NOT_VERIFIED`; 현재 숫자로 임의 확정하지 않는다.
- 기존 table→robot calibration, C robot XY, pivot fit 자체는 유지한다.
- 향후 PICK IK에서만 `pin_tip_offset_gripper_mm`와 별도의 검증된 `grasp_tcp_offset_gripper_mm`를 분리한다.
- 구현 의미는 다음과 같다.

```text
T_base_gripper = T_base_grasp_desired @ inverse(T_gripper_grasp)
```

- opening center offset 실측/검증 전 approach 재실행, grasp, lift는 금지 상태다.
- 코드 구현, fake test, Jetson 배포, 실제 모션은 이번 진단 범위에서 모두 `NOT_RUN`; 변경은 `NOT_COMMITTED/NOT_PUSHED`다.

## 추가 coarse 실측의 frame 확인 대기

사용자가 PIN TIP에서 opening center까지 `LEFT 47 mm / UP 70 mm`를 현장에서 coarse 측정했다. 현재 approach target FK의 rotation은 다음과 같다. 각 열은 gripper local `+X/+Y/+Z`가 base frame에서 향하는 방향이다.

```text
R_base_gripper =
[[+0.252790, +0.967520, -0.001250],
 [-0.652873, +0.171533, +0.737789],
 [+0.714041, -0.185690, +0.675030]]
```

따라서:

```text
base physical UP (+Z) in gripper = [+0.714041, -0.185690, +0.675030]
ceiling/table screen LEFT         = [+0.096636, +0.981097, +0.167664] gripper
ceiling/table screen UP           = [+0.693403, +0.054486, -0.718487] gripper
```

screen LEFT는 거의 gripper `+Y`지만, physical UP과 screen UP은 서로 다른 local-axis 조합이다. 관찰 frame 확인 없이 `47/70 mm`를 합치면 잘못된 3D offset을 만들 수 있으므로 `grasp_tcp_offset_gripper_mm` 후보는 아직 `PENDING_USER_FRAME_CONFIRMATION`이다. 실제 motion/torque/gripper command는 `NOT_RUN`이다.

## 첨부 사진 기반 axis mapping 정정과 coarse grasp TCP 후보

사용자가 앞선 `LEFT/UP` 표현을 철회하고 첨부 사진을 우선 근거로 지정했다. 사진은 PIN 축/장착 기준에서 opening center까지 gripper longitudinal 약 `70 mm`, 그와 수직인 사진 평면 방향 약 `47 mm`를 표시한다. PIN 장착 평면에서 PIN TIP까지의 제3축은 기존 현장 높이 `60–62 mm`로 둔다.

URDF와 설치 mesh의 축 관계:

- Wrist_Roll joint axis는 gripper local `Z`다.
- `wrist_roll_follower_so101_v1.stl`은 gripper origin에서 local `-Z`로 약 `104.4 mm` 뻗으므로 사진의 body→jaw longitudinal 방향은 `-Z`다.
- Jaw joint의 local axis를 gripper frame으로 변환하면 `-Y`다. 따라서 jaw 사진 평면은 `X–Z`, 사진 법선/핀 높이축은 `Y`다.
- moving jaw는 `+X` 측에 있고 opening center는 기존 pivot의 `X=-51.748 mm`에서 사진의 `+47 mm` 방향이다. 반대 `-X`는 opening center를 gripper lateral envelope 밖으로 보낸다.
- PIN TIP은 기존 pivot에서 `Y=-73.034 mm`이므로 PIN TIP→gripper plane 방향은 `+Y`; `60–62 mm`를 더하면 opening center 후보 Y는 `-13.034…-11.034 mm`로 body thickness 안에 남는다.

따라서 coarse 상대벡터는:

```text
pin_tip_to_grasp_center_gripper_mm = [+47, +(60..62), -70]
nominal midpoint                  = [+47, +61, -70] mm
```

기존 pivot offset과 합친 후보:

```text
pivot_offset_gripper_mm     = [-51.748354, -73.033741,  -54.531737]
grasp_tcp_offset_gripper_mm = [ -4.748354, -12.033741, -124.531737]  # Y midpoint 61
Y range                     = -13.033741 .. -11.033741 mm
```

nominal PIN→GRASP 거리 `104.067286 mm`, gripper origin→GRASP 후보 거리 `125.201882 mm`다. 기존 approach target joints에서 이 TCP의 base XYZ는 `[8.353834,-367.159182,54.980150] mm`이고 C approach reference까지 `104.052693 mm`로, 기존 endpoint가 opening center를 C에 맞추지 않았다는 현장 관찰과 일치한다.

같은 C reference `[-62.635354,-295.315566,80] mm`에 nominal grasp TCP를 맞추는 position-only IK를 오프라인으로 풀고 독립 FK 재계산한 residual은 `0.000275 mm`다. 이것은 수치 도달성만 뜻한다. 사진 실측은 coarse이고 orientation/collision/path/실물 opening-center 검증은 `NOT_VERIFIED`; 새 endpoint의 실제 채택, Jetson 배포, motor/Goal/Torque/gripper 명령은 모두 `NOT_RUN`이다. table→robot transform과 C robot XY는 변경하지 않았다.
