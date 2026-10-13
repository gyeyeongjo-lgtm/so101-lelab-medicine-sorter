# 2026-10-12 SAFE_HIGH → HOME supervised teleop 시도 1

## 판정

```ini
HOME_RECORD = NOT_RUN
HOME_REACHED = NOT_VERIFIED
TELEOP = STOPPED
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED
```

사용자의 `RUN SUPERVISED TELEOP SAFE_HIGH TO HOME` 승인 범위로 canonical 8000 relative-start 텔레옵만 시작했다. HOME 자동 waypoint, Torque 변경, 서비스 재시작은 실행하지 않았다.

## 사전점검

- 8000 health 정상, teleoperation/recording/inference inactive
- 8002 teleoperation inactive
- 8003 listener 없음
- canonical USB: leader `5AE6085272→/dev/ttyACM0`, follower `5AE6058306→/dev/ttyACM1`
- canonical 8000 systemd user service active, restart count 0
- systemd user-manager `LELAB_TELEOP_MODE=relative_start`
- non-privileged `lsof`에서 ACM owner 없음

## 실제 실행

20:35:54 KST Mac `192.168.50.131`에서 canonical 8000 `/move-arm`을 한 번 호출했다. 서버는 양 장치를 연결했고 다음 로그를 남겼다.

```text
relative_start origins captured from fresh calibrated values
```

그러나 `/ws/joint-data`는 3초 startup 검사 동안 표본을 내지 않아 방송 기반 stillness를 판정하지 못했다. 서버 journal에서 20:36:03 다음 guard ABORT를 확인했다.

```text
relative_start arm command step exceeds 2 degrees:
wrist_flex 37.582418° → 35.560440°
step = -2.021978°
```

첫 세션은 follower/leader를 모두 disconnect하고 `Teleoperation stopped`로 종료했다. startup stillness gate를 통과하지 못했으므로 HOME 기록은 진행하지 않는다.

## 예상 밖 재시작과 원인 격리

- 20:36:30 Mac에서 `/stop-teleoperation`, 20:36:31 다시 `/move-arm` 요청이 들어왔고 canonical 8000이 relative-start로 재활성화됐다.
- 이 두 번째 시작은 에이전트가 의도한 단일 POST가 아니며 exact caller process는 access log에 기록되지 않았다.
- Mac 브라우저 inventory에서 사용자 측에 열려 있던 LeLab `http://192.168.50.20:8000/teleoperation` 탭을 확인했다. 해당 페이지 이외에 active teleop 클라이언트 후보는 발견하지 못했으며, 이 탭의 재시작 동작이 가장 직접적인 후보지만 network request trace가 없어 `PROBABLE_NOT_PROVEN`으로 둔다.
- 추가 자동 재시작을 차단하기 위해 LeLab 텔레옵 탭만 닫았다. ChatGPT 탭은 유지했다.
- 20:36:58 canonical `/stop-teleoperation`을 명시적으로 호출했다. follower/leader disconnect와 `Teleoperation stopped`, 8000/8002 `teleoperation_active=false`를 확인했다.
- 서비스나 server process는 종료하지 않았다. 8000 PID 548557과 8002 PID 3467은 그대로다.

## 다음 게이트

사용자가 `STOPPED·비접촉 확인`을 입력한 뒤 follower serial `5AE6058306`의 Present_Position만 3회 read-only로 읽었다. 세 표본은 완전히 동일했고 write/torque API 호출은 0이었다.

| joint | Present raw | calibrated | SAFE_HIGH 대비 |
|---|---:|---:|---:|
| Shoulder Pan | 2066 | -3.120879° | -4.395604° |
| Shoulder Lift | 918 | -91.120879° | -114.021978° |
| Elbow Flex | 3074 | +95.868132° | +169.142857° |
| Wrist Flex | 2521 | +38.725275° | -4.395604° |
| Wrist Roll | 1691 | -15.252747° | 0.000000° |
| Gripper | 446 | 2.019584% | 0.000000 pp |

Shoulder Lift는 calibration raw lower endpoint `796`에서 122 raw, Elbow는 upper endpoint `3087`에서 13 raw밖에 떨어져 있지 않다. 따라서 이 자세는 `extreme joint pose 아님`이라는 HOME 조건을 명확히 통과하지 못하며, HOME으로 저장하지 않는다. 기록된 SAFE_HIGH 값은 보존하되 현재 실제 pose로 간주하지 않는다.

```ini
CURRENT_POSE = LOW_NEAR_SERVO_EDGE
HOME = NOT_RECORDED
SAFE_HIGH = RECORDED_BUT_NOT_CURRENT
motor_or_goal_write = 0
```

새 teleop/motion은 별도 계획과 승인 전까지 실행하지 않는다.

이번 변경은 `NOT_COMMITTED/NOT_PUSHED`다.
