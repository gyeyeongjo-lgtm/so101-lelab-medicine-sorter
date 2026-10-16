# 2026-10-15 SINGLE_SESSION_DEMO 고정 포트 helper gate 연결

## 범위

직전 live attempt의 유일한 blocker `port_ownership_unknown`을 해결하기 위해, 이미 설치·승인된 root-owned 고정 포트 read-only helper를 SINGLE_SESSION_DEMO가 사용하는 `SystemBusProbe.owner_pids()`에 연결했다.

조회 범위는 다음 두 경로로 고정된다.

```text
/dev/ttyACM0
/dev/ttyACM1
```

calibration, HOME/SAFE_HIGH, HOLD/teaching/recorder/2° limiter, torque/gain 및 LeLab 서비스는 변경하지 않았다. process signal/kill, serial open/write, motor/Goal/Torque/config write는 수행하지 않았다.

## 판정 계약

helper의 각 고정 포트 레코드를 다음과 같이 해석한다.

- `FREE\t-\t-` → owner set empty, gate 통과 가능
- `OCCUPIED\tPID\tprocess` → PID owner set, busy로 차단
- helper nonzero/stderr, 누락·추가 포트, 잘못된 필드/state/PID → `port_ownership_unknown`

따라서 `QUERY_ERROR` 또는 잘못된 출력은 절대 FREE로 바뀌지 않는다. 허용 포트 이외의 조회도 실행 전 차단한다. helper는 인자를 받지 않고 `/proc`만 읽으며 serial device를 열지 않는다.

## 배치와 검증

Jetson 격리 대상:

```text
/home/jetson3/so101-current-hold-teaching-20261014/
```

기존 `scripts/so101_exclusive_bus.py`는 다음에 백업했다.

```text
deploy-single-session-port-helper-20261015/backup/
```

배치된 probe/test SHA-256은 로컬과 일치했다. 첫 Jetson fake 실행은 격리 폴더에 helper 소스의 테스트용 미러가 없어 import 단계에서 FAIL했다. root-owned 실제 helper나 권한 실패는 아니며, 동일 read-only 소스 미러를 격리 `scripts/`에 추가한 뒤 재검증했다.

- 로컬 관련 회귀: `131/131 PASS`
- Jetson helper parser fake: `6/6 PASS`
- Jetson 설치 Python compile/import: PASS
- SINGLE_SESSION_DEMO 기본 dry-run: serial/motor/Goal/Torque/config write `0`
- 실제 helper no-argument 실행: PASS
- 실제 `SystemBusProbe`:
  - LeLab controls idle: true
  - ACM0 canonical serial: `5AE6085272`
  - ACM0 owners: `[]`
  - ACM1 canonical serial: `5AE6058306`
  - ACM1 owners: `[]`
- follower/leader `ExclusiveFollowerLease.acquire()` 후 즉시 release, serial open 없음: `PORT_OWNERSHIP_GATE=PASS`
- 종료 재조회: ACM0/ACM1 모두 FREE
- SSH 종료

```ini
PORT_HELPER = PASS
ACM0 = FREE
ACM1 = FREE
PORT_OWNERSHIP_GATE = PASS
SERIAL_OPEN = 0
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
NEXT_LIVE_COMMAND = RUN SINGLE SESSION DEMO
```

- 실제 single-session demo 재실행: `NOT_RUN`
- 이슈 갱신: `NOT_RUN`
- Git: `NOT_COMMITTED / NOT_PUSHED`
