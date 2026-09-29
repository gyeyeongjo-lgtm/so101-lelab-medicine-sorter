# Jetson 카메라 열거 실패 조사

대상: SO-101 LeLab 데이터 수집 복구

작성: 2026-09-08 KST
범위: Jetson에서의 USB 웹캠 열거와 LeLab OpenCV 녹화 실패. 모터 설정·calibration·USB serial 문제는 이 보고서 범위 밖이다.

## 결론

현재 2026-09-08 UI Collect data 회귀의 최초 실패는 camera 연결이다. LeLab은
follower/leader bus 연결과 calibration file 존재 확인을 통과한 뒤
`OpenCVCamera(0)`을 열지 못해 session을 episode 0, duration 0초로 종료했다.

이것은 camera index가 단순히 바뀐 경우나 다른 process가 camera를 점유한 경우보다
앞선 계층의 문제다. Jetson 현장 점검에서 `/dev/video*`와 `/dev/v4l/by-id`가 모두
없고, USB topology에도 Video-class device가 없다. 따라서 두 webcam은 현재 Jetson
커널에 열거되어 있지 않다. LeLab 설정, OpenCV backend, 권한을 변경해도 이 상태에서는
camera를 열 수 없다.

## 현장 증거

| 관측 | 결과 | 해석 |
|---|---|---|
| `/dev/video*` | 없음 | V4L2 video node가 없음 |
| `/dev/v4l/by-id` | 없음 | stable camera symlink도 없음 |
| `fuser /dev/video0 /dev/video2` | 대상 node 없음 | 다른 process의 점유가 아님 |
| `v4l2-ctl --list-devices` | camera 없음 | V4L2가 열거할 camera 없음 |
| `lsusb -t` | CDC ACM, HID, hub만 표시; Video class 없음 | webcam USB device가 Jetson에 인식되지 않음 |
| LeLab log | `/camera-preview/0` 및 `/camera-preview/2` = 503 | UI preview도 실제 capture에 실패 |
| LeLab recording log | `OpenCVCamera(0)` connect 실패 | record loop / TX-RX 이전에 종료 |

## 공식 자료와의 대조

LeRobot은 Linux USB webcam을 `OpenCVCamera`로 사용하며, camera identifier를
auto-discovery로 찾도록 안내한다. 이 명령은 실제 장치와 identifier를 나열한다.
현재 Jetson에서는 해당 장치 node 자체가 없으므로 discovery가 빈 결과가 되는 것이
예상된다. [LeRobot Cameras](https://huggingface.co/docs/lerobot/main/en/cameras)

LeRobot의 quick check는 `lerobot-find-cameras`이며, 발견된 index와 output을 검증하는
용도다. camera가 다시 kernel에 열거된 뒤에만 이 도구로 새 index/path를 확인하고
LeLab 설정과 비교해야 한다. [LeRobot Cheat Sheet](https://huggingface.co/docs/lerobot/main/en/cheat-sheet)

## 보정된 역할 포트와 독립성

동일 회귀에서 follower/leader bus connect는 통과했다. 2026-09-08에 robot record의
반전된 포트값을 stable by-id로 수정했으며, 이 camera failure는 해당 serial port
수정의 실패 증거가 아니다. Camera 복구 후에만 serial record path의 TX/RX 회귀를
재판정한다.

## 안전한 다음 단계

1. 사용자 안전 승인 후, robot serial adapter나 motor cable은 건드리지 않고 webcam
   두 대만 Jetson USB hub에 **한 대씩** 재연결한다.
2. 매 연결 뒤 `/dev/video*`, `/dev/v4l/by-id`, `lsusb -t`로 열거 여부를 확인한다.
3. 두 camera가 보이면 `lerobot-find-cameras opencv`로 실제 index/path를 확인한다.
4. 기존 `camera_2=2`, `312=0` 설정과 발견 결과가 일치하는 경우에만 1회 녹화를
   다시 실행한다. 다르면 먼저 camera config를 백업하고 stable device path를 검토한다.

## 재연결 후 검증 결과

두 webcam을 한 대씩 Jetson hub에 재연결한 뒤 다음이 확인됐다.

| 물리 camera | stable by-id | 영상 node | LeRobot 실제 open |
|---|---|---|---|
| C920 serial `07FE1FAF` | `usb-046d_HD_Pro_Webcam_C920_07FE1FAF-video-index0` | `/dev/video0` | PASS |
| C920 (serial 미노출) | `usb-046d_HD_Pro_Webcam_C920-video-index0` | `/dev/video2` | PASS |

`lerobot-find-cameras opencv`는 `/dev/video0`과 `/dev/video2`를 V4L2 backend로
열었고, 각각 YUYV 640×480 30 FPS profile 및 test image 저장을 보고했다. 따라서
현재 LeLab의 camera index 0/2 설정은 이번 연결 상태와 일치한다. 새 현장 안전
확인 후 1회 actual recording을 실행했고, 두 live feed가 나온 상태에서 episode를
종료했다. LeLab UI summary는 local dataset
`Supermassive111/camera_recovery_regression_20260908_20260908_170150`에 1 episode,
135 frames, 30 FPS를 보고했다. Hub upload는 건너뛰었다. 다음 단계는 hardware 동작이
없는 offline metadata·frame decode 검증이다.

## 제한

webcam이 Jetson에 물리적으로 연결되어 있지 않은지, USB hub 전원/케이블 접촉이
문제인지, 또는 host USB controller가 reset됐는지는 이 출력만으로 구분할 수 없다.
물리 재연결 후의 한 대씩 열거 결과가 필요하다.
