# Astra RGB-D → 작업대 → SO-101 좌표 파이프라인

## 현재 구조

```text
Camera capture: OpenNI2 `/opt/orbbec-openni2`, Astra RGB888
  - 상시 RGB preview: 640×480@30
  - RGB-D 진단: 320×240@30 저대역폭 모드
ArUco: `scripts/aruco_table.py`, DICT_4X4_50, 기본 70 mm + ID0 override 75 mm
Calibration: `configs/astra_color_intrinsics.local.json`, RGB RMS 0.478 px
Depth: OpenNI2 DEPTH_1_MM, depth→color registration
Robot: LeRobot SO101Follower / Feetech serial; 자율 Cartesian adapter 없음
Transforms: pixel→table 2D homography + reference center 기반 `T_C_W`/`T_W_C` 진단 구현
Config: reference ID 0–3, basket ID 4=red·5=green·6=blue
Unit: vision/workspace는 기존 구현을 보존해 mm로 통일
Missing: Depth 줄자 대조, 검증 완료된 T_W_C, T_B_W, limits, grasp offset
```

## 2026-09-27 Robot Base 준비 상태

- LeLab 0.6에는 SO follower FK/IK processor와 URDF가 있지만 `placo` runtime은 설치돼 있지 않다. 기존 LeLab 환경에 새 의존성을 임의 설치하지 않았다.
- 텔레오퍼레이션 worker는 이미 follower 관절값을 URDF joint radian으로 변환해 `/ws/joint-data`에 방송한다. 추후 teach UI는 이 단일 버스 소유자의 broadcast를 사용하고 별도 serial process를 열지 않는다.
- `scripts/urdf_forward_kinematics.py`는 버스를 열지 않고 URDF의 `base → gripper` 체인을 계산한다. 현재 target은 실제 TCP가 아니라 gripper link 원점이므로 gripper-tip offset 실측 전에는 `FK_ONLY_REQUIRES_PHYSICAL_VALIDATION`이다.
- `scripts/fit_robot_world_transform.py`는 4–8개 `World mm ↔ Robot Base mm` 쌍으로 rigid `T_B_W`와 point별 residual을 계산한다. 출력은 항상 `robot_enabled=false`, `motion_authorized=false`다.
- 예제 teach point 파일은 `configs/robot_world_pairs.example.json`이다. `robot_base_mm=null`은 의도된 미측정 상태이며 추정값을 넣지 않는다.
- 현재 USB 열거는 안정 ID `5AE6085272`(Leader)가 ACM1, `5AE6058306`(Follower)가 ACM0이다. LeLab robot record의 raw ACM 값은 현재 안정 역할과 일치한다. 재연결 뒤 ACM 번호가 바뀔 수 있으므로 실행 직전 stable ID를 다시 확인한다.

## 적용 원칙

- 변환 표기는 `T_A_B = B 좌표의 점을 A 좌표로 변환`으로 통일한다.
- 픽셀 좌표나 단순 scale 값을 로봇 명령으로 사용하지 않는다.
- 기준 작업대 좌표는 ID 0–3의 실측 marker 중심을 사용한다.
- 2026-09-30 정정: 2026-09-22의 여섯 수치는 실제로 검은 마커의 가까운 가장자리/대각선 모서리 간격이었다. 이를 중심 거리로 간주한 이전 reference 좌표와 모든 해당 XY 진단은 무효다. ID0 75 mm·나머지 가정 70 mm의 edge-gap 적합으로 중심을 다시 계산했고, 직접 중심 실측 ID2–ID3≈400 mm·ID3–ID0≈346 mm와 교차 확인했다. 저장소 예시 config만 보정했으며 Jetson 설치본과 live 카메라는 아직 재검증하지 않았다.
- ID 4–6은 바구니 검증용이며 물체 ID가 아니다.
- 내부 단위는 mm다. 추후 로봇 API가 다른 단위를 요구할 때 adapter 경계에서만 변환한다.
- `T_B_W`, 로봇 한계, 물체별 grasp offset이 모두 검증되기 전 `robot_enabled=false`를 유지한다.

## 현재 좌표 흐름과 빈 구간

```text
Astra RGB
  → ArUco pixel/corners
  → ID0–3 중심 multi-marker solvePnP
  → T_C_W / T_W_C (진단값, 정확도 검증 전)

Astra aligned Depth
  → RGB ray + ROI median depth → Camera XYZ (진단 근사)
  → T_W_C → World XYZ (기준 마커 3D 잔차로 교차검증)
  → [현재 여기까지]
  → T_B_W → Robot Base XYZ (미보정)
  → grasp offset + workspace limit
  → dry-run target
  → 사용자 승인 후에만 robot motion
```

## Phase 2/3 진단 도구

`scripts/orbbec_rgbd_pipe.cpp`는 OpenNI2에서 RGB와 depth를 동시에 열고
`IMAGE_REGISTRATION_DEPTH_TO_COLOR`를 활성화한다. 정합을 지원하거나 활성화하지 못하면
unaligned frame을 내보내지 않고 실패한다.

이 Astra/legacy OpenNI 조합은 640×480 RGB+Depth 동시 스트림이 첫 frame 뒤 정지하는
현상이 재현됐다. RGB-only와 Depth-only는 각각 정상이라 USB2 동시 대역폭 문제로 보고,
RGB-D 진단에만 `--low-bandwidth` 320×240 모드를 추가했다. 상시 RGB preview의
640×480 설정은 변경하지 않는다. 하드웨어 sync는 끄고 OpenNI timestamp 차이 50 ms
이내의 frame만 software pairing한다.

`scripts/astra_depth_diagnostic.py`는 다음만 수행한다.

- RGB와 정합된 raw depth를 읽는다.
- depth 해상도·FPS·단위, 중앙 11×11 ROI median, 유효 min/max, invalid 비율을 출력한다.
- ArUco 중심 11×11 ROI의 median depth를 `ID / (u,v) / depth mm`로 표시한다.
- 320×240에서는 원본과 2배 확대 검출 결과를 ID별 병합한다.
- RGB intrinsic을 capture 해상도에 맞춰 scale하고 Camera XYZ를 계산한다.
- ID0–3의 실측 중심으로 `T_C_W`/`T_W_C`를 추정하고 World XYZ, 재투영 RMS,
  기준점 3D 잔차, depth와 PnP 예측 Z 차이를 기록한다.
- RGB와 colorized depth를 나란히 저장하거나 `--display`에서 보여준다.
- 선택적으로 frame별 JSONL을 저장한다.
- 다음 frame이 기본 5초 안에 오지 않으면 실패 처리하고 helper를 종료해 카메라 점유를 해제한다.

## 2026-09-22 실기 판정

- `PASS`: 저대역폭 RGB-D 300 frames 연속 수집, 28.482 FPS, ID0–6 모두 300/300.
- `FAIL`: 기준점 3D 잔차가 43.82–137.00 mm라 현재 `T_W_C`는 진단값일 뿐이다.
- 640↔320 marker pixel은 약 0.5배로 대응하고 OpenNI FOV focal과 calibration focal도
  가까워 단순 해상도 scaling 문제는 아니다.
- 당시 기준 marker 거리 측정값은 중심 간이 아니라 검은 사각형 가장자리 간격이었다는 사실이 2026-09-30 확인됐다. 아래 2026-09-22 수치와 진단은 구 좌표계의 이력이며 현재 calibration 증거로 쓰지 않는다. ID0 검은 사각형 폭은 75 mm 실측, ID1–3은 70 mm 가정이다.
- 75 mm PnP Z와 depth는 marker별 약 122–250 mm 차이가 났다. RGB/depth edge 기반
  정합 최적값은 `(dx,dy)=(-2,-1)` px라 수십 pixel registration 오류는 원인이 아니다.
- ID5 실측 폭 70 mm를 적용한 live 30-frame 중앙값은 depth 771 mm, PnP Z 867.696 mm다.
  실제 직선거리 약 810 mm 대비 각각 −4.8%, +7.1%이며, 한 지점 근사 측정만으로 어느
  scale도 보정하지 않는다.
- 사용자 조정 후 최종 300-frame 재검사에서는 ID0–6과 world pose 모두 300/300이었지만,
  기준점 3D 잔차가 52.71–135.52 mm라 정확도 기준은 계속 실패했다.
- depth Camera XYZ 직접 강체변환은 기준점 평면 RMS 1.994 mm로 안정적이었으나 fit RMS가
  33.949 mm였다. 여섯 중심 거리는 world fitted 거리보다 모두 36.87–71.36 mm 길었다.
- similarity fit은 RMS 9.387 mm까지 낮췄지만 경험적 scale 0.868119를 요구해 채택하지 않았다.

이 도구는 LeRobot을 import하거나 serial·torque·robot command에 접근하지 않는다.

## 다음 승인 경계

1. 기존 ID0–3 homography로 pixel→table XY를 계산한다.
2. registered depth에서 기준 작업대 plane을 맞추고 plane 대비 상대 높이 Z를 계산한다.
3. XY/Z overlay와 JSONL만 출력하는 2.5D dry-run을 검증한다.

## 2.5D dry-run 결과

- homography table XY와 depth-plane 상대 높이를 frame/JSONL/summary/overlay에 구현했다.
- 300 frames에서 ID0–6, homography, depth plane 모두 300/300이었다.
- 기준점 높이는 약 ±1.51 mm, 바구니 높이는 약 54.56–56.76 mm로 안정적이었다.
- 바구니 XY 표준편차는 축별 최대 0.358 mm, 높이 표준편차는 최대 0.624 mm였다.
- 이는 camera-only 좌표 안정성 통과이며 robot target 정확도나 실제 grasp 성공을 뜻하지 않는다.
- 다음 입력은 pickup 구역에 놓인 대표 빈 약통/모형과 사용할 object class다.

## Pickup foreground bootstrap

- 저장된 RGB/uint16 depth snapshot에서 기준 작업대 plane보다 15–180 mm 높은 component를
  `scripts/depth_foreground_candidates.py`가 camera-only 후보로 추출한다.
- 구 좌표계의 초기 pickup ROI는 table X=80–220 mm, Y=200–300 mm였다. 보정된 예시 config에서는 같은 물리 영역의 보수적 경계 X=101–273 mm, Y=251–379 mm를 사용한다. 이 ROI는 live 재검증 전이다. 당시 대표 빈 약통은
  포함하고 로봇팔과 바구니 marker 영역은 제외한다.
- 최초 배치에서 선택 후보는 table `(140.254,242.293)` mm, 높이 중앙값 42.240 mm였다.
- 이 선택값은 데이터 수집용 proposal이며 YOLO 분류, 약품 식별, grasp pose 또는 robot target이
  아니다. 여러 위치·회전 표본과 별도 검증 전에는 robot control에 연결하지 않는다.
- 검토를 통과한 후보는 `--yolo-label-output`으로 class-0 normalized `xywh` pseudo-label을
  내보낼 수 있다. 기본 2 px margin과 영상 경계 clip을 적용하며 metadata에
  `review_required=true`를 기록한다. 자동 검출값을 사람 검토 없는 ground truth로 취급하지 않는다.
3. Camera XYZ와 ID0–3 `T_W_C`의 재투영 RMS·기준점 3D 잔차·PnP/depth Z 차이를 재판정한다.
4. 오차가 남으면 ChArUco intrinsic의 principal point/distortion을 재수집한다.
5. 필요하면 각 marker의 실제 회전 방향까지 실측해 중심 4점 대신 전체 corner를 사용한다.
6. 4–8개 teach point로 `T_B_W`를 계산하고 residual을 기록한다.
7. overlay·JSONL·10-frame 안정성·workspace limit을 통과한 dry-run만 만든다.
8. 별도 현장 안전 승인 전에는 실제 로봇 이동을 구현·실행하지 않는다.
