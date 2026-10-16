# 2026-10-16 read-only robot-status precheck 중단

## 승인 범위

- follower 후보: `/dev/ttyACM1`
- expected USB serial: `5AE6058306`
- 승인 명령:
  `python3 -m medicine_sorter --config configs/system.example.json robot-status`
- 최대 실행 횟수: `1`
- 금지: 재시도, 다른 포트, 다른 명령, Goal/Torque/config/motor write,
  `SO101Follower.connect()`
- 현장 확인: 사용자가 팔 지지·주변 비접촉을 확인함

## 로컬 실행 대상

```text
branch=fix/usb-recording
commit=d309c940407bf0dd112ceb16fddc3cf3f6f1be6f
origin/fix/usb-recording=d309c940407bf0dd112ceb16fddc3cf3f6f1be6f
medicine_sorter/robot.py sha256=d8f7598be481f325404290ac3aa4bd558be46a318968fee21322565beda123ec
medicine_sorter/cli.py sha256=e3486c323f7545348b30038c51129506ff255fcfff7e5989cc5c9718934e2cd9
configs/system.example.json sha256=e6627f7d85b37e4c27236b636f9d205a98b7e08e4a086ffb465be3089a2fb99d
```

로컬 `SO101ReadOnlyStatusAdapter`는 일반 `SO101Follower.connect()`를 사용하지
않고 `bus.connect(handshake=False)`를 호출하며, write/sync-write/
enable_torque/disable_torque를 차단한다. 종료 계약은
`bus.disconnect(disable_torque=False)`다.

## 실행 전 확인 결과

| 항목 | 결과 | 근거 |
| --- | --- | --- |
| branch/commit과 Jetson 설치본 동일 | FAIL | `/home/jetson3` 최대 depth 5에서 `*/medicine_sorter/robot.py` 결과 없음; 최대 depth 4에서 `.git` 결과 없음 |
| `/dev/ttyACM1` 다른 owner 없음 | NOT_RUN | 첫 gate FAIL 후 추가 검사 중단 |
| USB serial exact match | NOT_RUN | 첫 gate FAIL 후 추가 검사 중단 |
| 설치본 종료가 `disconnect(disable_torque=False)` | NOT_CONFIRMED_ON_JETSON | 로컬 계약은 확인됐지만 동일 설치본이 없어 Jetson 실행 계약으로 인정하지 않음 |

첫 조건 불일치 시 실행하지 말라는 사용자 지시에 따라 승인 명령은 실행하지 않았다.

## sanitized raw output

SSH banner, host login 이력, password는 기록하지 않았다. 실행본 검색 결과만 보존한다.

```text
PRECHECK_CODE_BEGIN
$ find /home/jetson3 -maxdepth 5 -type f -path '*/medicine_sorter/robot.py'
<no output>
$ find /home/jetson3 -maxdepth 4 -type d -name .git
<no output>
PRECHECK_CODE_END
```

## 모터별 결과

승인 명령을 실행하지 않았으므로 다음 값은 생성되지 않았다.

| ID | 모터 | Present | Goal | Present−Goal | Torque_Enable | Moving | Temperature |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | shoulder_pan | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 2 | shoulder_lift | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 3 | elbow_flex | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 4 | wrist_flex | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 5 | wrist_roll | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 6 | gripper | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |

## write와 Torque 판정

- 승인 명령 실행 횟수: `0`
- robot serial open: `0`
- Goal write: `0`
- Torque write: `0`
- config write: `0`
- motor command: `0`
- 실행 전후 Torque 변화: `NOT_OBSERVED`
- 이전 unexpected OFF→ON lifecycle 관련 판단: `NOT_EVALUATED`

write `0`의 근거는 write firewall runtime 결과가 아니라, 첫 코드 동일성 gate에서
중단돼 bus 생성과 승인 명령 자체가 실행되지 않았다는 control-flow 및 SSH 명령
기록이다.

## 판정

```ini
ROBOT_STATUS_TEST = FAIL_PRECHECK / NOT_RUN
RETRY = 0
ALTERNATE_PORT = 0
TEACHING_PLAN = NOT_WRITTEN_PASS_REQUIRED
NEXT_LIVE_COMMAND = NONE
GIT = NOT_COMMITTED / NOT_PUSHED
```

다음 단계는 사용자의 별도 지시 아래 정확한 commit의 단일 진입점과 config를
Jetson에 비동작 방식으로 배치·hash 확인하는 것이다. 이 배치 자체는 이번 1회
robot-status 승인에 포함된 것으로 간주하지 않았다.
