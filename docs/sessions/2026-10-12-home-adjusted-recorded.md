# 2026-10-12 supervised HOME adjustment · canonical record

## 결과

```ini
HOME_USER_DESIRED = REFERENCE_ONLY_NOT_CANONICAL
HOME = RECORDED
SAFE_HIGH = RECORDED
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED
teleoperation = inactive
motor_write_after_stop = 0
torque_change_after_stop = 0
full_mesh_environment = NOT_VERIFIED
```

사용자가 원했던 외형의 첫 HOME 후보
`[-3.120879,-91.120879,+95.868132,+38.725275,-15.252747]°`는 Elbow
calibration upper endpoint까지 `1.142857°`밖에 남지 않아 reference로만
보존했다. 사용자가 LeLab supervised teleop으로 Elbow를 완화한 뒤
`STOPPED·비접촉 확인`을 보고했다.

## 제어 종료와 fresh feedback

- canonical 8000 LeLab teleoperation을 `/stop-teleoperation` 1회로 종료했고
  `teleoperation_active=false`를 확인했다.
- 첫 read-only 도구는 과거 고정 `/dev/ttyACM0`가 현재 USB 매핑과
  달라 serial identity gate에서 포트를 열기 전 중단됐다. 실패를 숨기지
  않는다.
- 현재 LeLab robot record는 leader `/dev/ttyACM0`, follower `/dev/ttyACM1`이다.
  follower serial `5AE6058306`을 재확인한 뒤, write/torque API를
  fail-closed한 스크립트로 follower를 3회 읽었다.
- 3회 Present raw는 모두 `2072/1212/2864/2284/1721/446`로 동일했고,
  전 축 `Moving=0`, `Torque_Enable=1`이었다. 종료 뒤 포트는 해제됐다.

## canonical HOME

| 축 | Present | raw | Goal | Goal-Present | Load diagnostic | Temperature |
|---|---:|---:|---:|---:|---:|---:|
| Pan | -2.593407° | 2072 | -2.329670° | +0.263736° | -24 | 37°C |
| Lift | -65.274725° | 1212 | -65.274725° | 0.000000° | 0 | 38°C |
| Elbow | +77.406593° | 2864 | +73.714286° | -3.692308° | +180 | 45°C |
| Wrist Flex | +17.890110° | 2284 | +17.362637° | -0.527473° | +36 | 37°C |
| Wrist Roll | -12.615385° | 1721 | -12.439560° | +0.175824° | -20 | 36°C |
| Gripper | 2.019584% | 446 | 2.019584% | 0.000000 pp | 0 | 39°C |

```text
GRASP TCP = [+20.324187, -253.265255, +99.167465] mm
table reference = +54.659 mm
GRASP TCP table margin = +44.508465 mm
self-collision centerline proxy = 55.827804 mm
Elbow upper calibration margin = 19.604396°
minimum arm calibration margin = 19.604396°
```

Elbow upper margin은 첫 후보의 `1.142857°`에서 `19.604396°`로 늘었다.
정지 전 WebSocket 방송에서 본 Elbow `59.296703°`는 canonical 값으로
사용하지 않았다. 정지 후 실제 follower Present 3회의 `77.406593°`를
저장했다. Present_Load는 검증된 absolute threshold가 없으므로 diagnostic
only이다. Elbow Goal-Present `-3.692308°`는 숫자를 숨기지 않고 기록하며,
향후 HOME 자동 왕복은 별도 offline 경로 검증과 실기 승인 전에는
실행하지 않는다.

canonical pose는 `configs/poses.yaml`에 `HOME=RECORDED`, `SAFE_HIGH=RECORDED`로
저장했다. 이번 정지 후 자동 motion은 `0`; full mesh/environment collision은
계속 `NOT_VERIFIED`다. 변경은 `NOT_COMMITTED/NOT_PUSHED`다.
