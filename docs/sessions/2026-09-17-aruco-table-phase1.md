# 2026-09-17 — ArUco 작업대 좌표계 1단계

## 범위

- 목표: 로봇을 움직이지 않고 천장 C920 영상에서 ArUco ID 0–3과 2D 작업대 좌표를 표시할 준비를 한다.
- 제외: 실제 모터 동작, torque, serial, USB 재연결, SO-101 calibration, ACT 추론, 카메라 내부 파라미터 보정.

## 시작 전 확인

- 최신 인계의 Jetson 주소 `192.168.0.30:8000`에서 LeLab health 정상 응답을 확인했다.
- `192.168.0.30`의 SSH ED25519 지문은 기존에 확인된 Jetson 지문과 일치했다.
- Jetson LeLab venv:
  - Python 3.14.7
  - OpenCV 4.13.0
  - `cv2.aruco=True`
  - `cv2.aruco.ArucoDetector=True`
- `/dev/video0`: character device, owner/group `root:video`, mode `660`.
- LeLab teleoperation, recording, inference는 모두 inactive였다.
- 위 확인에서 카메라와 serial을 열지 않았다.

## 추가한 산출물

- `scripts/generate_aruco_markers.py`
  - `DICT_4X4_50` marker SVG/PNG와 실제 크기 A4 SVG를 생성한다.
  - 기본 IDs 0,1,2,3, 한 변 70 mm.
- `scripts/aruco_table.py`
  - 정지 이미지 또는 카메라 한 대에서 marker를 검출한다.
  - marker 중심의 실측 작업대 좌표로 homography를 계산한다.
  - 화면 중심의 작업대 좌표와 최근 30-frame RMS jitter를 표시한다.
  - camera calibration JSON이 있으면 marker pose/axis를 표시하고, 없으면 `pose_ready=false`로 보고한다.
- `configs/aruco_table.example.json`
  - `600 × 400 mm` 값은 구조 설명용 예시이며 실제 현장 측정값이 아니다.
- `artifacts/aruco-markers/`
  - IDs 0–3 개별 SVG/PNG와 A4 인쇄본.
- `docs/ARUCO_TABLE.md`
  - 인쇄, 배치, 실측, 정지 이미지와 live 300-frame 검증 절차.

## 오프라인 검증

- Mac 기본 Python에서 syntax compile 통과.
- 전체 단위 테스트 10개 통과:
  - 새 ArUco config/SVG 테스트 4개
  - camera-only ArUco ID parsing 테스트 3개
  - 기존 port/preflight 테스트 3개
- Mac의 기존 LeRobot conda 환경은 OpenCV 4.13.0과 `cv2.aruco`를 제공했다.
- 640×480 합성 영상에 네 marker를 배치한 결과:
  - detected IDs: 0,1,2,3 모두 검출
  - `homography_ready=true`
  - frame center: 약 `(300.65, 200.67) mm`
  - 동일 프레임 30회 안정성 RMS: 약 `1.5e-13 mm`
- 합성 입력의 거의 0인 jitter는 계산 경로만 검증하며 실제 C920의 검출 안정성을 증명하지 않는다.

## 남은 상태

- `NOT_RUN`: 마커 인쇄 및 70 mm 실측 확인.
- `NOT_RUN`: 카메라 고정, 마커 부착, 현장 marker-center 거리 실측.
- `NOT_RUN`: 실제 `/dev/video0` frame read와 300-frame 안정성 검사.
- `NOT_VERIFIED`: 카메라 내부 파라미터와 marker pose.
- `NOT_DEPLOYED`: Jetson 영구 경로 배포. `/tmp` 합성 검증 전송은 SSH 암호 도우미 응답 중단으로 완료 여부를 확인하지 못했다.
- `NOT_PUSHED`: Git commit·push를 수행하지 않았다.

## 다음 한 단계

A4 SVG를 100%로 인쇄하고 70 mm를 확인한 뒤, ID 0–3을 작업대 네 모서리에 배치하고
각 marker 중심 좌표를 mm로 실측한다. 이 물리값 없이는 예시 config로 실제 좌표 검증을
진행하지 않는다.
