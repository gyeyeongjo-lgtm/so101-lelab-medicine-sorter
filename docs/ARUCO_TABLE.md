# ArUco 작업대 2D 좌표 변환

> 2026-09-21 후속 장비 교체 후 천장 정면 소스는 Orbbec Astra RGB로 바뀌었다. 아래 C920/단일 V4L2 명령은 초기 재현 이력이고, 현재 운영은 `docs/ASTRA_RGBD_PIPELINE.md`와 OpenNI2 설정을 따른다.

`docs/ARUCO_STAGE1.md`의 인쇄·부착·ID 가시성 검사를 마친 뒤 사용하는 좌표 변환
단계다. 목표는 **로봇을 전혀 움직이지 않고** 천장 C920 영상에서 marker ID
`0,1,2,3`과 안정적인 2D 작업대 좌표(mm)를 표시하는 것이다. 카메라 pose는 내부
파라미터 보정 파일이 생긴 뒤 별도로 활성화한다.

## 안전·소유권 경계

- `scripts/generate_aruco_markers.py`는 파일만 만든다.
- `scripts/aruco_table.py`는 이미지 파일 또는 카메라 한 대만 읽는다.
- 두 스크립트 모두 LeRobot을 import하지 않고 serial, torque, calibration, robot
  record에 접근하지 않는다.
- live 검출 전 LeLab의 teleoperation, recording, inference가 모두 inactive인지 확인한다.
- 검출기를 실행하는 동안 LeLab camera preview나 다른 `/dev/video0` 사용자는 열지 않는다.

## 1. 마커 인쇄

권장값은 `DICT_4X4_50`, IDs `0,1,2,3`, 한 변 `70 mm`다. 생성된 A4 SVG를
**100% / 실제 크기**로 인쇄한다. `페이지에 맞춤`은 끈다.

```bash
/home/jetson3/.local/share/uv/tools/lelab/bin/python \
  scripts/generate_aruco_markers.py \
  --output-dir artifacts/aruco-markers \
  --dictionary DICT_4X4_50 \
  --ids 0 1 2 3 \
  --size-mm 70
```

인쇄 후 자로 검은 정사각형 전체 폭이 `70 mm`인지 확인한다. 반사가 심한 코팅이나
구김은 피하고, 마커 바깥에 흰 여백을 남긴다.

## 2. 작업대 배치와 실측

천장 카메라 영상을 기준으로 다음 순서로 붙인다.

| 위치 | ID |
| --- | ---: |
| 좌상단 | 0 |
| 우상단 | 1 |
| 우하단 | 2 |
| 좌하단 | 3 |

카메라 위치와 줌/초점을 먼저 고정하고 네 마커가 모두 프레임 가장자리에서 잘리지 않게
한다. 마커 사이 영역에 로봇, 약통 슬롯, 바구니가 들어오게 배치한다.

`configs/aruco_table.example.json`의 `600 × 400 mm`는 **예시일 뿐 실제 작업대 치수가
아니다**. ID 0의 중심을 `(0, 0)`으로 두고, 각 마커 중심까지의 X/Y 거리를 자로 재어
실제 config에 적는다. 사각형이 정확하지 않다면 각 중심의 실측값을 각각 기록한다.

```bash
cp configs/aruco_table.example.json configs/aruco_table.local.json
```

`configs/aruco_table.local.json`은 현장별 값이므로 Git에 커밋하지 않는다.

## 3. 정지 이미지 검사

먼저 한 장의 정지 이미지로 ID와 좌표 변환을 검사한다.

```bash
/home/jetson3/.local/share/uv/tools/lelab/bin/python scripts/aruco_table.py \
  --config configs/aruco_table.local.json \
  --image /path/to/c920-frame.jpg \
  --output /tmp/aruco-annotated.jpg
```

정상 결과는 JSON의 `detected_ids`에 `0,1,2,3`이 모두 있고,
`homography_ready=true`인 상태다. `pose_ready=false`는 아직 카메라 내부 파라미터
보정을 하지 않았다는 뜻이며 1단계 실패가 아니다.

## 4. live 안정성 검사

LeLab camera preview를 닫고 다른 제어 작업이 inactive인 상태에서만 실행한다.

```bash
/home/jetson3/.local/share/uv/tools/lelab/bin/python scripts/aruco_table.py \
  --config configs/aruco_table.local.json \
  --max-frames 300 \
  --json-every 30 \
  --output /tmp/aruco-live-last.jpg
```

검출기는 화면 중심이라는 고정 픽셀을 작업대 좌표로 바꾼 값의 최근 30-frame RMS를
`frame_center_jitter_mm`로 출력한다. 카메라와 마커가 고정된 상태에서 이 값이 낮고
튀지 않는지 확인한다. 절대 통과 기준은 실제 작업 거리와 허용 오차를 확인한 뒤 정한다.

## 판정

- `PASS`: 네 ID가 연속 검출되고 `homography_ready=true`이며 좌표와 jitter가 표시된다.
- `NOT_VERIFIED`: 인쇄 크기 또는 마커 중심 간 실측값을 확인하지 않았다.
- `BLOCKED`: 네 마커 중 하나라도 반복적으로 가려지거나, 카메라 초점/노출이 고정되지
  않아 검출이 끊긴다.
- 카메라 내부 파라미터와 marker pose는 다음 단계다. 보정 파일을 만들기 전에는
  `pose_ready=false`를 그대로 보고한다.
