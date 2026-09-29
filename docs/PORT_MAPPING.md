# SO-101 포트 매핑

최신 누적 확인: 2026-09-28
2026-09-29 live 재확인: `BLOCKED_NETWORK` (Jetson offline)

## 2026-09-28 최신 로봇 역할

stable serial을 영구 식별자로 사용하고, raw `/dev/ttyACM*`는 해당 열거 시점의 교차 확인용으로만 사용한다.

| 역할 | stable by-id | 당시 node | serial |
|---|---|---:|---|
| Leader | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6085272-if00` | `/dev/ttyACM1` | `5AE6085272` |
| Follower | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6058306-if00` | `/dev/ttyACM0` | `5AE6058306` |

이전 녹화/추론에서 raw ACM 번호와 robot record 역할이 뒤집혀던 이력이 있다. 새 세션 시작 전에는 UI 표시만 보지 말고 by-id→canonical node→실제 팔 역할을 다시 대조한다.

## 2026-09-21 이후 현재 카메라 3대

| 역할 | 장치 | 식별·경로 |
|---|---|---|
| 천장 정면 | Orbbec Astra | USB `2bc5:0401`, OpenNI2 `/opt/orbbec-openni2`; V4L2 node가 아님 |
| 천장 사선 | Intel RealSense D435 | USB `8086:0b07`, serial `236223023645`; V4L2 color by-id |
| 로봇팔·손목 | Generic USB Camera | USB `0bda:5844`; V4L2 by-id/node는 재열거 후 재확인 |

아래 C920 3대 표는 2026-09-20 카메라 교체 전 이력이다.

## 이력: 2026-09-20 C920 카메라 역할

세 카메라가 동시에 연결된 상태에서 `/dev/v4l/by-id`, sysfs, udev property와 실제
Safari preview를 대조했고 사용자가 물리 역할을 확정했다. 각 카메라의 `video-index0`
node만 영상 입력으로 사용하며 같은 장치의 index1 node는 별도 카메라로 세지 않는다.

| 역할 | stable by-id | 현재 node | USB serial / VID:PID |
|---|---|---:|---|
| 천장 사선 | `/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_27292FAF-video-index0` | `/dev/video0` | `27292FAF` / `046d:082d` |
| 로봇팔·손목 | `/dev/v4l/by-id/usb-Generic_USB_Camera_200901010001-video-index0` | `/dev/video2` | `200901010001` / `0bda:5844` |
| 천장 수직·ArUco 기준 | `/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_07FE1FAF-video-index0` | `/dev/video4` | `07FE1FAF` / `046d:082d` |

`/dev/video1`, `/dev/video3`, `/dev/video5`는 각각 위 세 물리 카메라의 index1 node다.
OpenCV index 숫자는 USB 재열거로 바뀔 수 있으므로 이후 설정은 stable by-id 지원 여부를
먼저 확인하고, UI가 숫자만 받는 경우 매 실행 전 위 canonical 매핑을 재검증한다.

## 이력: 2026-09 로봇 역할 보정

사용자가 실제 팔을 기준으로 역할을 확정했고, 공식 CLI 비교군도 아래 stable
`by-id` 경로로 실제 연결을 확인했다. `/dev/ttyACM*` 번호는 USB 재열거에 따라
바뀔 수 있으므로 역할 설정에는 쓰지 않는다.

| 역할 | 안정 경로 | 당시 tty | serial | 근거 |
|---|---|---:|---|---|
| 팔로워 | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6058306-if00` | `/dev/ttyACM1` | `5AE6058306` | 사용자 물리 확인 + 공식 CLI의 `robot.port` |
| 리더 | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6085272-if00` | `/dev/ttyACM0` | `5AE6085272` | 사용자 물리 확인 + 공식 CLI의 `teleop.port` |

아래 2026-09-05 표와 시간대별 내용은 당시 재열거 상태의 **이력**이다. 현재 역할
설정의 근거로 사용하지 않는다.

## 관측 결과

| 역할 | LeLab 저장값 | 현재 상태 | 물리 식별 근거 |
|---|---|---|---|
| 리더 | `/dev/ttyACM0` | 존재 | 현재 canonical `/dev/ttyACM0`, serial `5AE6085272`, VID:PID `1a86:55d3`, ID_PATH `platform-3610000.usb-usb-0:2.4:1.0` |
| 팔로워 | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6058306-if00` | 현재 없음 | 19:13 robot record와 이후 팔로워 연결 성공 로그에 저장된 별도 serial |
| 카메라 0 | OpenCV index 0, C920 | 현재 `/dev/video*` 없음 | 커널 이력의 Logitech `046d:082d` |
| 카메라 2 | OpenCV index 2, C920 | 현재 `/dev/video*` 없음 | 커널 이력의 Logitech `046d:08e5` |

현재 `/dev/ttyACM0`과 다음 별칭 2개는 같은 character device `(major=166, minor=0)`다.

- `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6085272-if00`
- `/dev/serial/by-path/platform-3610000.usb-usb-0:2.4:1.0`

이는 하나의 장치가 여러 경로로 열거된 정상적인 alias 관계다. 리더와 팔로워가 같은 장치를 가리킨다는 증거가 아니다.

## 시간대별 근거

- 19:13: 리더 `/dev/ttyACM1`, 팔로워 serial `5AE6058306`으로 robot record 저장.
- 19:27–19:28: 포트 분리 감지 뒤 리더가 `/dev/ttyACM0`으로 저장됨.
- 19:43: 저장된 팔로워 경로에서 SOFollower 연결 성공.
- 20:11: USB 허브와 C920 두 대가 커널에서 분리됨.
- 20:14: 직렬 어댑터 하나만 허브 포트에 다시 연결됨.
- 21:10–21:11: 같은 어댑터가 한 차례 분리·재연결됨.

## 판정

- `PASS`: 저장된 리더/팔로워 문자열은 서로 다르고 serial 값도 다르다.
- `OBSERVED`: 현재 존재하는 장치는 serial `5AE6085272` 하나뿐이다.
- `HYPOTHESIS`: `/dev/ttyACM0`은 재열거에 따라 바뀌는 이름이라, 리더 저장값을 고유 by-id로 바꾸는 편이 안정적일 수 있다.
- `BLOCKED`: 팔로워가 현재 열거되지 않아 두 장치의 동시 canonical 매핑과 실제 팔 역할을 이번 세션에서 아직 재확인하지 못했다.

설정 변경은 하지 않았다. 다음 물리 단계는 안전 확인 후 팔로워와 카메라가 연결된 정상 배선을 복원하고, 메타데이터 전용 검사만 다시 실행하는 것이다.
