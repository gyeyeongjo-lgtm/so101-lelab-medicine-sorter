# 2026-09-20 - ChArUco 인쇄 보드 생성

## 목적과 안전 범위

- 천장 수직 C920 `/dev/video4`의 intrinsic calibration에 사용할 A4 ChArUco 보드를 준비했다.
- 파일 생성과 정적 검증만 수행했다. camera, robot serial, torque, teleoperation, recording, inference를 실행하지 않았다.

## 보드 규격

- Dictionary: `DICT_4X4_50`
- Squares: 6×8
- Square length: 30 mm
- Marker length: 22 mm
- Marker IDs: 10–33
- Board 크기: 180×240 mm
- Page: A4 portrait, 210×297 mm

작업대 기준 marker ID 0–3과 calibration board ID가 겹치지 않도록 ID 10–33을 사용했다.

## 생성 및 검증

- Jetson LeLab Python의 OpenCV 4.13에서 3600×4800 px 원본을 생성했다.
- 생성 원본을 다시 검출해 ID 10–33 전부 24/24를 확인했다.
- PDF page 크기: 595.276×841.890 pt(A4).
- 내장 board image: 3600×4800 px.
- PDF 배치 크기: 510.236×680.315 pt, 즉 180×240 mm.
- 150 DPI 렌더링을 시각 확인해 잘림, 겹침, marker 손상이 없음을 확인했다.
- 산출물: `output/pdf/charuco_6x8_30mm_22mm_ids10-33_a4.pdf`.

## 인쇄와 다음 단계

- A4 용지에 `100%` 또는 `Actual size`로 인쇄한다.
- `Fit`, `Scale`, `Shrink oversized pages`는 모두 끈다.
- 인쇄 후 체커 한 칸의 변을 재서 정확히 30 mm인지 확인한다.
- 크기가 맞으면 평평한 판에 붙인 뒤 `/dev/video4`에서 여러 위치·거리·기울기의 calibration frames를 수집한다.
- `NOT_RUN`: 실제 인쇄 크기 확인, frame 수집, intrinsic parameter 계산.
- `NOT_PUSHED`: Git commit·push를 수행하지 않았다.

## 인쇄 확인과 첫 live 검출

- 사용자 보고: A4 인쇄 완료, 체커 한 칸 30 mm 실측 완료, 천장 카메라 시야에 배치.
- 시작 전 `/health` 정상, teleoperation·recording·inference inactive, preview `stopping=0`을 확인했다.
- 첫 검사기는 OpenCV 4.13에서 제거된 `interpolateCornersCharuco` API 때문에 frame 처리 전에 종료됐다. 카메라·로봇 설정은 변경되지 않았다.
- 설치 버전의 `cv2.aruco.CharucoDetector`로 수정해 `/dev/video4` 640×480, 90 frames를 재검사했다.
- captured 90/90, marker 최대 24/24·평균 23.3, ChArUco corner 최대 35/35·평균 33.567, 12 corner 이상 87/90.
- 판정: 현재 자세의 ChArUco 가시성과 인쇄 품질 `PASS`.
- `NOT_RUN`: 여러 자세의 calibration frame 수집, intrinsic parameter 계산, reprojection error 검증.
- `SAFETY`: camera-only 검사이며 robot serial, torque, teleoperation, recording, inference를 실행하지 않았다.

## 바구니 marker 첫 검출과 배치 수정 필요

- 사용자 확정 매핑: ID 4=빨강, ID 5=초록, ID 6=파랑.
- 작업대 좌표계는 ID 0–3만 사용하며, ID 4–6은 바구니 위치 추적·검증에만 사용한다.
- `scripts/aruco_table.py`에 화면에서 검출된 모든 marker 중심의 table-mm 투영값과 marker별 평균·jitter 요약을 추가했고 단위 테스트 13개가 통과했다.
- 왜곡 보정된 `/dev/video4` 300-frame exact count 결과는 captured=300, ID 0=29, ID 1=300, ID 2=300, ID 3=300, ID 4=0, ID 5=0, ID 6=0으로 `FAIL`이다.
- 확인 이미지에는 개별 바구니 marker ID 4–6 대신 ChArUco calibration board의 ID 10–33이 보였으며, 보드와 바구니가 작업대 ID 0을 가렸다.
- 다음 물리 조정: ChArUco 보드는 완전히 치우고, ID 4·5·6을 각 바구니의 수평·단단한 상단 탭에 천장 방향으로 노출하고, marker 둘레에 10–20 mm 흰 여백을 확보한다. 작업대 ID 0–3도 모두 가리지 않아야 한다.
- `BLOCKED`: 사용자가 위 배치를 조정한 뒤 ID 0–6 300-frame exact count를 재실행한다.
- `SAFETY`: 이번 검사는 camera-only이며 robot serial, torque, teleoperation, recording, inference를 실행하지 않았다.

## 60초 calibration 수집과 계산

- 사용자 `시작` 확인 후 `/dev/video4`, 640×480에서 60초 수집을 실행했다.
- 총 관찰 frames: 1,793.
- 자세 다양성·정지 조건을 통과해 저장한 views: 25.
- view별 ChArUco corners: 최소 28, 최대 35.
- camera matrix: fx=672.182, fy=673.146, cx=322.530, cy=201.374.
- distortion coefficients: [0.185618, -1.048517, -0.009375, -0.002715, 0.952848].
- 전체 reprojection RMS: 0.428 px.
- view별 RMS 평균: 0.379 px, 최대: 0.873 px.
- 결과 파일: `configs/c920_video4_intrinsics.local.json`(Git 제외), SHA-256 `fbdf8c8340b755211823063b4993c780fd7f440ca51b3b4af663334ba3f9c6c3`.
- `configs/aruco_table.local.json`이 intrinsic 파일을 참조하도록 갱신했다.
- `scripts/aruco_table.py`가 calibrated frame을 undistort한 뒤 ArUco homography와 pose를 계산하도록 수정했다.
- `PASS`: 천장 C920 640×480 intrinsic parameter 계산 완료.
- `NOT_RUN`: 보드를 치운 상태에서 undistorted workspace ID 0–3 live 재검증.
- `NOT_VERIFIED`: robot-base 좌표 등록과 실제 로봇 도달 정확도.
- `SAFETY`: robot serial, torque, teleoperation, recording, inference를 실행하지 않았다.

## 보드 제거 후 왜곡 보정 작업대 재검증

- 사용자 보고: ChArUco 보드를 작업대에서 제거했다.
- 시작 전 `/health` 정상, teleoperation·recording·inference inactive, preview `stopping=0`을 확인했다.
- intrinsic을 적용해 frame을 undistort한 뒤 `/dev/video4` 300-frame ArUco homography·pose run을 완료했다.
- 주기 표본에서 ID 0–3 homography와 marker pose가 준비됐고 `pose_ready=true`였다.
- 안정화 후 최근 30-frame jitter는 약 0.15–0.21 mm RMS, 마지막 0.180 mm였다.
- 초반 주기 표본 한 번에서 ID 0이 빠져, 별도 300-frame exact count를 실행했다.
- exact count 결과: captured=300/300, ID 0=300, ID 1=300, ID 2=300, ID 3=300, `undistorted=true`, 판정 `PASS`.
- `PASS`: 천장 카메라 intrinsic, distortion correction, workspace marker detection, pixel→table homography, marker pose, short-term stability.
- `NOT_VERIFIED`: table↔robot-base 등록, 약통 slot·basket table 좌표, 실제 로봇 도달 정확도.
- `SAFETY`: camera-only 검사이며 robot serial, torque, teleoperation, recording, inference를 실행하지 않았다.
