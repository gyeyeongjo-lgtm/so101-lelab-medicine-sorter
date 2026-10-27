# Jitter smooth live candidate

일자: 2026-10-27

## 현장 확인과 범위

사용자는 승인된 `current → home` ORIGINAL 재배치에서 외부 링크가 실제로 home
방향으로 정상 이동했고 home 모습도 정상이었으나 떨림은 여전히 존재했다고 확인했다.
떨림 등급은 NONE/LOW/MEDIUM/HIGH 중 선택되지 않아 `PRESENT_UNRATED`로 기록한다.

이 확인은 encoder-only false positive를 해소하지만, 구간이 `current → home`이므로
계획된 동일 start/end A/B의 ORIGINAL `home → red_above` baseline을 대신하지 않는다.
이번 변경 중 실제 serial open, Goal/Torque write, motor motion은 모두 0이다.

## 측정 결론

재배치 ORIGINAL telemetry는 58 sample, interval mean `0.1052506 s`, std
`0.0002672 s`, max `0.1058187 s`였다. write duration은 mean `0.0005560 s`, max
`0.0007206 s`이고 planned 0.1 s보다 약 5.25 ms가 매 cycle 추가됐다. 큰 동작 관절의
Present 속도 부호 반전은 0회였고 elbow_flex는 max step `1.984°`, max
Goal−Present `6.505°`였다.

따라서 현재 근거는 큰 랜덤 serial timing jitter보다 다음 조합을 우선 지지한다.

```text
relative sleep + 처리시간의 일관된 누적
+ elbow의 2° cap 근처 계단 target
+ 실제 servo 추종 지연/정지마찰·백래시 가능성
```

마지막 두 기계·servo 원인은 scheduler A/B 전에는 확정하지 않는다. gain, Torque,
calibration, IK, TCP는 변경하지 않았다.

## live SMOOTH 후보

`motion-test --profile smooth`만 다음 후보에 연결했다.

- shared quintic `s(t)=10t³−15t⁴+6t⁵`
- absolute deadline, 만료 tick skip, catch-up burst 없음
- 기본 40Hz, 선택 30/40/50Hz
- 기본 arm velocity 20°/s, free-space 시험에서만 20/30/40°/s 선택
- synchronized emitted command, arm joint별 2° hard cap 유지
- 매 command cycle: Goal sync-write 1회
- 0.1초마다: Present, 실제 Goal register readback, Moving
- 약 1초마다와 최종 cycle: Torque, 6축 Temperature 및 servo Overload 상태
- 오류·Ctrl+C: 기존 fresh current HOLD
- 종료: `disconnect(disable_torque=False)`

첫 A/B는 40Hz·20°/s로 고정해 scheduler/curve만 비교한다. 30/40°/s는 smooth가 같은
속도에서 개선된 뒤에만 free-space 구간에서 한 변수씩 시험한다. 전체 `run --auto`와
web에는 아직 연결하지 않아 기본 fixed-demo는 기존 original 그대로다.

## telemetry schema v4

command row는 모든 Goal write의 planned/actual/write-complete timestamp와 target을
보존한다. sparse feedback row만 feedback timestamp, Present raw/normalized,
Goal raw/normalized, Moving과 Goal−Present를 가진다. Torque/Temperature sample도 실제
읽은 cycle에만 기록한다. 분석기는 command cadence와 feedback cadence를 분리하므로
미측정 cycle을 반복값으로 채워 Present 속도·방향 반전을 왜곡하지 않는다.

## 오프라인 결과

알려진 `home → red_above` delta를 사용한 결과:

| Hz | velocity | commands | duration | max step | cap binding | reversals |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | 20 | 140 | 4.6667 s | 0.662783° | 0 | 0 |
| 30 | 30 | 93 | 3.1000 s | 0.997796° | 0 | 0 |
| 30 | 40 | 70 | 2.3333 s | 1.325024° | 0 | 0 |
| 40 | 20 | 186 | 4.6500 s | 0.498898° | 0 | 0 |
| 40 | 30 | 124 | 3.1000 s | 0.748275° | 0 | 0 |
| 40 | 40 | 93 | 2.3250 s | 0.997796° | 0 | 0 |
| 50 | 20 | 233 | 4.6600 s | 0.398288° | 0 | 0 |
| 50 | 30 | 155 | 3.1000 s | 0.598707° | 0 | 0 |
| 50 | 40 | 117 | 2.3400 s | 0.793143° | 0 | 0 |

장비 없는 검증:

- fixed-demo `59/59 PASS`
- web `6/6 PASS`
- sorter `31/31 PASS`
- Python compile `PASS`
- `git diff --check` `PASS`
- serial open / motor command `0 / 0`
- implementation commit `28acf6e9f2f68bc1b666ae40b691bba7d6b07df4`
- GitHub `fix/usb-recording` push `PASS`

## 다음 gate

현재 최종 Present는 과거 telemetry에서 저장 home의 elbow보다 약 4.84° 남았으므로,
다음 live 전에 write 차단 fresh `robot-status`로 실제 start pose를 다시 확인한다.
저장 home의 1° start gate를 임의로 완화하지 않는다. 필요하면 별도 승인된 재정렬을
먼저 수행한다.

그 뒤에도 A와 B를 자동 연속 실행하지 않는다.

1. ORIGINAL `home → red_above` 1회와 외부 영상 확인
2. 정지 및 별도 `red_above → home` reset 확인
3. SMOOTH 40Hz·20°/s 동일 `home → red_above` 1회
4. telemetry와 사용자 육안 비교

SMOOTH live, reset, run/web 연결, 30/40°/s 시험은 모두 `NOT_RUN/NOT_APPLIED`다.

## Jetson 배포 및 fresh read-only 상태

Jetson은 `git pull --ff-only`로 최신
`532323fdbc1fbd4b1d5803fbd523283a7047872e`에 배치됐다. 사용자가 이어서 실행한
`robot-status`는 canonical follower `/dev/ttyACM0`, serial `5AE6058306`을 선택했고
30 read request, state-change write 0, `disconnect(disable_torque=False)`로 끝났다.

| joint | Goal raw | Present raw | Goal−Present | Torque | Moving | °C |
|---|---:|---:|---:|---:|---:|---:|
| shoulder_pan | 2100 | 2096 | +4 | 1 | 0 | 33 |
| shoulder_lift | 1394 | 1394 | 0 | 1 | 0 | 33 |
| elbow_flex | 2205 | 2248 | −43 | 1 | 0 | 43 |
| wrist_flex | 2696 | 2695 | +1 | 1 | 0 | 33 |
| wrist_roll | 1615 | 1614 | +1 | 1 | 0 | 31 |
| gripper | 1090 | 1090 | 0 | 1 | 0 | 35 |

Goal은 저장 home raw와 일치하고 사용자의 외부 home 모습 확인도 정상이지만,
elbow residual 43 raw는 약 3.78°이며 감독 `--stable-hold-gap-raw` 상한 40을 3 count
초과한다. 따라서 현재 ORIGINAL을 호출해도 실제 구간 전에 fail-closed할 상태다.
상한 40과 저장 pose start 1° gate를 완화하거나 Goal/Torque를 변경하지 않는다.
ORIGINAL/SMOOTH actual motion은 계속 `NOT_RUN`이다.

두 번째 write 0 `robot-status`도 Goal/Present/Torque/Moving이 첫 확인과 완전히
같았다. 따라서 elbow `−43 raw` residual은 자연 수렴하지 않았고, elbow 온도는
`43→45°C`로 상승했다. 이는 움직임 중 scheduler jitter와 별개로 현재 home HOLD에서
정적 하중 또는 servo deadband가 존재할 가능성을 높이지만, gain/기계 원인으로
확정하지 않는다. 50°C prestart limit에 접근하므로 추가 live motion은
`BLOCKED_COOL_DOWN_REQUIRED`; 안전 gate 완화, Goal/Torque write, 자동 재시도는 0이다.
