# 2026-09-21 - 천장 카메라 RealSense D435 교체

## 범위와 안전

- 사용자가 기존 천장 수직 C920을 RealSense로 교체했다고 보고했다.
- 이번 작업은 네트워크·USB·V4L2 정보 확인과 camera-only frame read만 수행했다.
- robot serial, torque, teleoperation, recording, inference는 열거나 실행하지 않았다.

## Jetson과 장치 식별

- 기존 `192.168.0.30`은 현재 네트워크에서 응답하지 않았다.
- ARP 후보를 SSH host key로 대조해 새 주소 `192.168.50.20`을 확인했다.
- ED25519 지문은 기존 고정값 `SHA256:dG9hPvs6yZcfIlZ0mPofx8lUPGYwDwW1M4UDzeSfx3o`와 일치한다.
- LeLab `/health` 정상, teleoperation·recording·inference 모두 inactive였다.
- 장치: Intel RealSense D435, USB ID `8086:0b07`, serial `236223023645`, USB 3 연결.
- V4L2 mapping:
  - `/dev/video0`: Z16 16-bit depth
  - `/dev/video2`: GREY/UYVY/Y8I/Y12I IR 계열
  - `/dev/video6`: YUYV color
- `/dev/video6` 640×480@30 color read는 60/60 frame에 성공했다.
- Jetson에는 `rs-enumerate-devices`와 `pyrealsense2`가 없어서 factory intrinsic 조회와 depth-color alignment는 수행하지 않았다.

## 코드 호환과 첫 ArUco 검사

- C920용 MJPG 고정을 제거할 수 있도록 다음 도구에 FOURCC 선택을 추가했다.
  - `scripts/check_aruco_workspace.py`
  - `scripts/check_charuco_board.py`
  - `scripts/calibrate_charuco_camera.py`
  - `scripts/aruco_table.py`
- RealSense color에는 `YUYV`를 사용한다.
- 관련 단위 테스트 12개가 통과했다.
- 90-frame ID 0–6 검사 결과: captured=90, ID3=87, ID0·1·2·4·5·6=0, `FAIL`.
- 확인 영상은 작업대 전체가 아니라 일부만 포함한다. 현재 시야로는 table homography 또는 ChArUco intrinsic 수집을 진행하지 않는다.

## 필요한 다음 조정

1. RealSense 위치와 각도를 고정한다.
2. color 화면에 작업대 ID 0–3과 세 바구니 영역이 모두 완전히 들어오도록 높이·각도를 조정한다.
3. ID 0–3 가시성 검사를 먼저 통과한다.
4. 동일한 6×8, square 30 mm, marker 22 mm ChArUco 보드로 RealSense color intrinsic을 새로 계산한다.
5. 보드를 치운 뒤 ID 0–6 exact-count 300 frames, live homography와 jitter를 재검증한다.

- 기존 C920 intrinsic은 `STALE_CALIBRATION`이며 RealSense에 적용하지 않는다.
- 작업대 marker가 물리적으로 움직이지 않았다면 기존 table-mm 중심 좌표는 재사용 가능하다.
- `NOT_VERIFIED`: RealSense depth scale, depth-color alignment, table plane depth, robot-base 등록.
- `NOT_PUSHED`: Git commit·push를 수행하지 않았다.

## 세 물리 카메라 재확인과 바구니 배치

- 사용자 설명: 엔드이펙터 1대, 천장 정면 1대, 천장 사선 1대로 총 세 대이며 바구니 ID4·5·6을 배치했다.
- USB identity는 RealSense D435, Generic USB Camera, Orbbec Astra 세 대다.
- `/dev/video4` frame을 직접 확인해 Generic USB Camera가 엔드이펙터 카메라임을 확정했다.
- `/dev/video6` RealSense color frame은 로봇과 작업대를 비스듬히 보는 사선 천장 시야다.
- `/dev/video2`와 `/dev/video6`은 같은 RealSense의 IR/color stream이므로 별도 물리 카메라 두 대로 세면 안 된다.
- RealSense color 300-frame ID0–6 결과: ID2=237, ID3=63, ID0=0, ID1=0, ID4=0, ID5=0, ID6=0.
- 현재 frame에는 바구니 세 개와 바닥 안쪽의 marker가 보이나, 사선 시야에서 바구니 테두리에 가려져 ID4–6이 검출되지 않는다.
- Orbbec Astra USB `2bc5:0401`은 연결됐지만 V4L2 node가 없다. LeLab `/available-cameras`에는 RealSense stream index 2·6과 Generic USB index 4만 표시된다.
- 시스템에는 Debian `libopenni2-0`만 설치되어 있다. 시스템 설치 없이 `/tmp`에만 추출한 `openni2-utils`의 `NiViewer2`로 확인했으나 `DeviceOpen using default: no devices found`였다.
- 판정: 현재 Orbbec 전용 OpenNI2/SDK driver가 없어 천장 정면 영상은 `BLOCKED`다. driver를 준비하기 전에는 Astra intrinsic이나 ID0–6 검출을 시작할 수 없다.
- `SAFETY`: camera-only 검사이며 package 설치, robot serial, torque, teleoperation, recording, inference를 실행하지 않았다.

## Orbbec Astra 공식 OpenNI2 드라이버 설치

- 사용자 승인 뒤 천장 정면 카메라를 Orbbec Astra로 확정하고 드라이버 설치를 진행했다.
- Orbbec 공식 문서에 따라 구형 OpenNI protocol Astra에는 SDK v2가 아니라 OpenNI2/SDK v1 계열을 선택했다.
- 참고 검증용 공식 Orbbec SDK v1.10.37 ARM64 release zip의 SHA-256은 GitHub asset digest `3c269b7eac354dbb69a6d4519cc587b21b6390baaacce7ce79331593c97489a0`과 일치했다.
- 최신 통합 SDK v1.10.37은 user/root 모두에서 이 `2bc5:0401`을 열거하지 못해 실제 설치에는 Orbbec 공식 `ros2_astra_camera`의 ARM64 OpenNI2 redist를 사용했다.
- 공식 repository commit: `f7e71d9ce806e788cb48d8580aac2c778fba4214`.
- 설치 경로:
  - runtime/driver: `/opt/orbbec-openni2`
  - wrapper: `/usr/local/bin/orbbec-openni-capture`
  - udev: `/etc/udev/rules.d/99-obsensor-libusb.rules`
- 기존 `/usr/lib/aarch64-linux-gnu/libOpenNI2.so.0`과 Debian `libopenni2-0` package는 덮어쓰지 않았다.
- udev rule 적용 뒤 `/dev/astra -> bus/usb/001/011`, node mode `0666`, group `video`를 확인했다.
- 설치 hash:
  - `/opt/orbbec-openni2/libOpenNI2.so`: `d7231df09a6a242990507fce4eb75329a67c8f298bd8f110baa8dddc344f6bda`
  - `OpenNI2/Drivers/liborbbec.so`: `b6511b00891360bda20f452847db5f25d67d588597bad5991a9756ef5dffa95b`
  - camera-only checker: `1ac5f7b9511657253f6d76e1b57ced463748e2e7bf10f73797bea626148ef9e0`
  - udev rule: `04bd6ef1e10cb7cf5ab15d78d6ef00987ca5412ee99a5f1a6b1a5bba760fb473`

## Astra frame 검증

- 장치 열거: `Astra`, URI `2bc5/0401@1/11`, vendor `Orbbec`.
- sensor: color, IR, depth 모두 available.
- color RGB888 640×480: 60/60 및 영구 설치 후 30/30 frame 성공.
- IR GRAY16 640×480: 30/30 frame 성공.
- OpenNI color mirror는 ArUco bit pattern을 뒤집으므로 검사기에서 명시적으로 off 처리했다.
- non-mirrored color frame에서 ID2·3은 검출됐다.
- ID0·1은 화면 하단에서 잘렸고, 바구니 ID4·5·6은 바구니 바닥 안쪽의 색상/슬랫 배경 때문에 흰 quiet zone이 없어 판독되지 않았다.
- 다음 물리 조정:
  1. Astra 시야를 약간 아래로 이동하거나 카메라 높이를 조절해 ID0–3 전체를 포함한다.
  2. ID4=빨강, ID5=초록, ID6=파랑 marker를 각 바구니 상단의 흰 수평 판에 붙이고 10–20 mm 흰 여백을 둔다.
  3. ID0–6 exact count 300 frames를 통과시킨 뒤 ChArUco color intrinsic을 수집한다.
- `NOT_VERIFIED`: reboot/physical reconnect 뒤 udev 지속성, LeLab preview integration, color intrinsic, depth scale/alignment, homography.
- `SAFETY`: motor, torque, robot serial, teleoperation, recording, inference를 실행하지 않았다.

## 천장 정면·사선 상시 프리뷰

- 사용자 요청으로 엔드이펙터 카메라는 제외하고 다음 두 영상을 한 웹 페이지에 구성했다.
  - 천장 정면: Orbbec Astra OpenNI color, RGB888 640×480, mirror off
  - 천장 사선: Intel RealSense D435 V4L2 color, YUYV 640×480, canonical by-id 사용
- URL: `http://192.168.50.20:8010/`
- endpoint:
  - `/astra.mjpg`
  - `/realsense.mjpg`
  - `/health`
- Jetson 설치:
  - `/opt/orbbec-openni2/bin/orbbec-rgb-pipe`
  - `/opt/so101-camera-preview/camera_preview_server.py`
  - `/etc/systemd/system/so101-camera-preview.service`
- repository source:
  - `scripts/orbbec_rgb_pipe.cpp`
  - `scripts/camera_preview_server.py`
  - `systemd/so101-camera-preview.service`
- `PASS`: OpenNI raw RGB 한 frame 921,600 bytes를 수신했고 값 범위 0–255를 확인했다.
- `PASS`: systemd 상태는 `enabled`와 `active`; 서비스 하위 process는 Python server와 OpenNI pipe 두 개다.
- `PASS`: `/health`에서 Astra와 RealSense 모두 `ok=true`, frame age 약 0.03초였고 frame count가 계속 증가했다.
- `PASS`: Mac 외부 접근으로 2초 동안 Astra 2,655,180 bytes, RealSense 1,914,440 bytes의 MJPEG를 수신했다.
- `PASS (visual)`: Codex 인앱 브라우저에서 두 카메라의 실제 영상이 한 페이지에 표시되는 것을 확인하고 결과 탭을 유지했다.
- `RESOURCE OWNERSHIP`: 프리뷰가 두 카메라를 상시 점유하므로 camera calibration, detector, recording에서 같은 camera를 열기 전에 서비스를 stop하고 작업 종료 뒤 start한다.
- 운영 명령:
  - 중지: `sudo systemctl stop so101-camera-preview.service`
  - 재개: `sudo systemctl start so101-camera-preview.service`
  - 상태: `systemctl status so101-camera-preview.service`
- `SAFETY`: 작업 전후 LeLab health 정상, teleoperation·recording·inference inactive를 확인했다. 로봇 제어는 수행하지 않았다.
- `NOT_RUN`: 실제 재부팅 후 자동 시작 검증과 USB 분리·재연결 복구 검증은 하지 않았다. unit은 multi-user target에 enable했다.
- `NOT_PUSHED`: commit·push하지 않았다.

## 카메라 조정 후 intrinsic 진행

- 사용자 보고로 세 카메라 조정이 완료된 뒤 camera-only 검사를 시작했다.
- 작업 전 LeLab health 정상, teleoperation·recording·inference inactive를 확인하고 상시 프리뷰 서비스만 일시 중지했다.
- intrinsic 전 workspace exact-count:
  - RealSense 300/300 frames: ID0=267, ID1=297, ID2=0, ID3=296, ID4=0, ID5=0, ID6=0.
  - Astra 300/300 frames: ID0=272, ID1=25, ID2=300, ID3=300, ID4=0, ID5=57, ID6=0.
- RealSense의 현재 정지 영상에서 작업대 ID2는 사선 원근 왜곡이 크고, 바구니 ID4–6은 바구니 바닥 안쪽에 있어 테두리에 가려졌다.
- Astra 검사 중 ChArUco 보드가 화면 가장자리로 들어와 workspace marker count 조건이 바뀌었다. 따라서 위 count는 최종 homography 판정으로 사용하지 않는다.

### Astra color intrinsic

- 기존 `calibrate_charuco_camera.py`에 OpenNI raw RGB pipe 입력을 추가했다. 이 경로는 robot serial을 열지 않는다.
- ChArUco 6×8, square 30 mm, marker 22 mm 보드로 Astra RGB888 640×480 자세 30개를 수집했다.
- 최초 결과: reprojection RMS 0.658 px, view별 평균 0.572 px, 최대 3.109 px.
- 저장 이미지를 다시 검출하고 view RMS가 1.0 px를 넘는 `view_06.jpg`, `view_04.jpg`를 제외해 28개 view로 재계산했다.
- 최종 결과: reprojection RMS 0.478 px, view별 평균 0.450 px, 최대 0.878 px.
- Jetson 원본: `/home/jetson3/calibration/astra_color_20260921/astra_color_intrinsics_refined.json`.
- Mac local config: `configs/astra_color_intrinsics.local.json` (`.gitignore` 대상).
- 양쪽 SHA-256: `2be8287af33b15bccec80b71b41b47de85be510323e50f7033cbb517658bde73`.
- `PASS`: Astra color intrinsic은 camera-only 품질 기준을 통과했다.

### 남은 단계

- `BLOCKED (physical)`: RealSense 화면에는 ChArUco 보드가 아직 없다. 보드 전체를 사선 화면 중앙에 배치한 뒤 30개 자세를 수집해야 한다.
- `NOT_RUN`: RealSense intrinsic 및 두 카메라에서 보드를 치운 뒤 intrinsic 적용 ID0–6 exact-count, homography/jitter 검증.
- 대기 중 상시 프리뷰를 재시작했고 Astra·RealSense `/health` 모두 `ok=true`였다.
- 작업 종료 시 LeLab teleoperation·recording·inference는 모두 inactive였다.
- `NOT_PUSHED`: commit·push하지 않았다.
