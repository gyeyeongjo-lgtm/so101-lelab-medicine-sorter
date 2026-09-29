# ArUco Stage 1 — 작업대 좌표계 준비

> 이 문서는 2026-09-17 C920로 시작한 Stage 1 이력을 보존한다. 현재 천장 정면 운영 카메라는 Orbbec Astra이며 OpenNI2 경로를 사용한다. ID0은 후속 실측에서 75 mm, ID1–3은 70 mm로 확정됐다. 현재 실행 경로는 `docs/CURRENT_SYSTEM_AND_ARUCO.md`와 `docs/ASTRA_RGBD_PIPELINE.md`를 우선한다.

이 단계는 **카메라 읽기만** 한다. 로봇 serial port, 토크, 텔레오퍼레이션, LeLab 추론을 실행하지 않는다.

## 출력물

`assets/aruco/stage1-markers/`에는 다음 marker가 생성된다.

- Dictionary: `DICT_4X4_50`
- IDs: `0`, `1`, `2`, `3`
- 검은 marker 정사각형 한 변: 70 mm
- 흰 여백: 각 변 5 mm

SVG 파일을 **100% / Actual Size**로 출력한다. `Fit to Page`, 자동 축소, 양면 인쇄를 사용하지 않는다. 출력 후 검은 정사각형 한 변이 실제로 70 mm인지 자로 확인한다.

## 물리 배치

1. 천장 C920을 지금 위치에서 고정한다.
2. marker 네 장을 작업 영역의 네 모서리에 평평하게 붙인다. 기울어짐·주름·반사는 피한다.
3. marker가 약통이나 로봇팔에 가려지지 않게 한다.
4. 약통 시작 슬롯과 목적 바구니 위치를 테이프로 고정한다.
5. 아직 로봇팔을 움직이지 않는다.

ID의 정확한 모서리 방향·작업대 실제 길이는 다음 단계의 homography/pose 설정 때 기록한다. 지금은 네 ID가 천장 카메라에서 안정적으로 보이는지만 검증한다.

## Jetson 검출 확인

marker를 붙인 뒤 Jetson 터미널에서 프로젝트 사본의 스크립트를 실행한다.

```bash
PY=/home/jetson3/.local/share/uv/tools/lelab/bin/python
"$PY" scripts/check_aruco_workspace.py --camera /dev/video0 --expected 0,1,2,3
```

성공 기준은 JSON의 `status: "PASS"`, `captured_frames > 0`, 네 ID의 `seen_counts`가 모두 1 이상인 것이다. 이 명령은 C920만 열고, 로봇팔 serial 장치를 열지 않는다.

## 다음 단계

Stage 1 통과 후 marker 네 장의 실제 평면 좌표(mm)를 기록하고, 카메라 calibration/작업대 homography를 만든다. 그 뒤에야 YOLO 검출 좌표를 작업대 좌표로 변환한다.
