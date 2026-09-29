# 2026-09-17 — ArUco Stage 1 준비

## 목적과 안전 범위

- 목적: 천장 C920의 영상 안에서 작업대 기준 marker 네 장을 안정적으로 찾는 준비를 한다.
- 범위: marker 출력 파일 생성, OpenCV 기반 V4L2 camera read-only 검출 도구 준비와 오프라인 검사만 포함한다.
- 제외: robot serial port open, torque 변경, teleoperation, recording, inference, USB 재연결, camera calibration 값 저장.

## 준비한 산출물

- `assets/aruco/stage1-markers/aruco_DICT_4X4_50_id{0,1,2,3}.svg`
  - 70 mm 검은 marker square와 각 변 5 mm 흰 quiet zone을 포함한다.
  - SVG는 80 mm × 80 mm actual-size page를 지정한다.
- `assets/aruco/stage1-markers/manifest.json`
- `scripts/generate_aruco_markers.py`
  - OpenCV `DICT_4X4_50` marker를 SVG로 생성한다.
  - camera·serial port를 열지 않는다.
- `scripts/check_aruco_workspace.py`
  - Jetson에서 지정 V4L2 node를 샘플링해 ID 0–3 visibility를 JSON으로 보고한다.
  - robot serial port를 열거나 LeLab 제어 작업을 시작하지 않는다.
- `docs/ARUCO_STAGE1.md`
  - 출력 100% 확인, marker 부착, Jetson 검출 명령과 성공 기준을 기록한다.

## 로컬 검증

- Mac `lerobot-train` 환경 OpenCV: `4.13.0`, `cv2.aruco` 사용 가능.
- marker 생성 완료: ID 0, 1, 2, 3.
- `tests/test_check_aruco_workspace.py`: 3/3 PASS.
- `git diff --check`: PASS.

## Jetson 확인 상태

- `BatchMode=yes` SSH로 LeLab Python의 OpenCV ArUco 기능을 읽기 전용 확인하려 했지만, 현재 key-only 인증은 거부됐다. 비밀번호 입력 또는 Jetson 로컬 터미널에서 아래 명령을 실행해야 한다.

```bash
PY=/home/jetson3/.local/share/uv/tools/lelab/bin/python
"$PY" - <<'PY'
import cv2
print("cv2", cv2.__version__)
print("has_aruco", hasattr(cv2, "aruco"))
PY
```

- `NOT_RUN (physical)`: marker를 아직 출력·부착하지 않았으므로 Jetson `/dev/video0`에서의 실제 marker detection, camera intrinsic calibration, marker pose, pixel-to-table transform은 실행하지 않았다.
