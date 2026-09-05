# SO-101 포트 매핑

확인 시각: 2026-09-05T21:18:17+09:00

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
