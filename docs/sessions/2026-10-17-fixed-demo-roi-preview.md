# 2026-10-17 fixed-demo ROI PNG 명령

## 목적

`run --dry-run`에서 ID7–9의 slot 판정이 실제 왼쪽·가운데·오른쪽 배치와 다를 때,
로봇을 연결하지 않고 같은 카메라 좌표계에서 ROI 경계를 바로 확인한다.

## 명령

```bash
/home/jetson3/.local/share/uv/tools/lelab/bin/python -m medicine_sorter --config configs/system.example.json roi-preview --output /tmp/fixed-demo-roi.png
```

## 동작 경계

- 기존 8020 서비스의 `/manual-frame.json`을 정확히 한 번 GET한다.
- 한 HTTP 응답에 함께 담긴 snapshot과 JPEG만 사용하므로 중심 좌표와 이미지의
  frame sequence가 서로 어긋나지 않는다.
- dry-run과 같은 `undistorted_full_frame`, 640×480 좌표를 요구한다.
- PNG에 slot1/2/3 사각형, 검출된 모든 ArUco 중심, ID7=C·ID8=B·ID9=A의
  현재 slot을 표시한다. 어떤 slot에도 속하지 않으면 빨간색 `OUTSIDE`로 표시한다.
- 출력 JSON에 frame sequence, age, coordinate space, ROI 네 꼭짓점, marker별 중심과
  slot 판정을 남긴다.
- 카메라 HTTP read와 로컬 PNG 저장 외에 LeRobot import, `/dev/ttyACM*` 접근,
  Goal/Torque/config/motor write는 없다.

## 오프라인 검증

```text
fixed-demo tests = 35/35 PASS
existing sorter tests = 30/30 PASS
CLI help = PASS
OpenCV synthetic 640x480 JPEG -> PNG render smoke = PASS
Python compile = PASS
git diff --check = PASS
serial open = 0
motor command = 0
Jetson camera execution = NOT_RUN
```

추가 검사는 marker 중심의 slot/OUTSIDE 분류, 같은 bundle의 JPEG/sequence 전달,
PNG가 아닌 출력 경로의 camera fetch 전 거부를 포함한다. 실제 PNG는 Jetson에서
현재 Astra frame으로 생성한 뒤 판정을 확인한다.
