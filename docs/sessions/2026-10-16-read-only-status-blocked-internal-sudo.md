# 2026-10-16 read-only robot-status 재승인 — 내부 sudo 경로 차단

## 승인과 결론

사용자는 다음 명령을 정확히 한 번 승인했다.

```bash
cd /home/jetson3/so101-lelab-medicine-sorter
/home/jetson3/.local/share/uv/tools/lelab/bin/python -m medicine_sorter --config configs/system.example.json robot-status
```

범위는 `/dev/ttyACM1`, expected serial `5AE6058306`, 재시도 0,
Goal/Torque/config/motor write 0, `SO101Follower.connect()` 금지,
`disconnect(disable_torque=False)`, sudo 금지다. 사용자는 팔 지지·주변 비접촉을
확인했다.

실행 전 정적 계약 감사에서 승인 조건과 충돌하는 경로가 확인돼 명령은
`0회/NOT_RUN`이다.

## 발견된 충돌

`medicine_sorter.robot.SO101ReadOnlyStatusAdapter`는 실제 bus를 만들기 전에
`_resolve_probe()`로 `scripts.so101_exclusive_bus.SystemBusProbe`를 만든다. 이어서
`connect()`에서 `probe.owner_pids(self.port)`를 호출한다.

배치 commit `d309c94`의 `SystemBusProbe.owner_pids()`는
`/usr/local/sbin/so101-fixed-port-occupancy`가 존재할 때 다음 argv를 실행한다.

```text
["sudo", "-n", "/usr/local/sbin/so101-fixed-port-occupancy"]
```

고정 helper 자체는 두 canonical port의 owner를 `/proc`에서 읽을 뿐 device open,
serial I/O, signal/kill 기능은 없다. 그러나 이번 승인에는 **sudo 사용 금지**가
명시돼 있으므로 helper의 안전성과 별개로 이 호출 경로는 승인 범위를 위반한다.

helper가 없을 때의 fallback도 unprivileged `fuser`가 `/proc` permission error를
내면 `sudo -n fuser`를 호출하므로 sudo 없는 complete ownership 판정을 현재 코드가
보장하지 못한다. 이를 무시하거나 UNKNOWN을 FREE로 바꾸지 않았다.

## 실행 전 항목

| 항목 | 결과 | 근거 |
| --- | --- | --- |
| Jetson 배치 commit/hash | 이전 배치 PASS, 이번 turn 재조회 NOT_RUN | sudo 계약 충돌을 로컬 exact commit에서 먼저 발견 |
| import source path | 이전 배치 PASS, 이번 turn NOT_RUN | 같은 이유로 SSH 전 중단 |
| LeLab/UI/teleop/lerobot process inactive | NOT_RUN | SSH/process 조회 전 중단 |
| `/dev/ttyACM1` owner 없음 | NOT_RUN | 승인 조건과 충돌하는 sudo 없이 complete query 불가 |
| USB serial exact match | NOT_RUN | device/sysfs 조회 전 중단 |
| LeRobot bus read/write-firewall 계약 | PARTIAL_PASS | `handshake=False`와 high-level write firewall은 유지되나 owner gate가 sudo를 호출함 |

## 모터별 결과

| ID | 모터 | Present | Goal | Present−Goal | Torque_Enable | Moving | Temperature |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | shoulder_pan | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 2 | shoulder_lift | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 3 | elbow_flex | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 4 | wrist_flex | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 5 | wrist_roll | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| 6 | gripper | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |

## write와 lifecycle 판정

```ini
JETSON_SSH_THIS_TURN = 0
APPROVED_COMMAND_EXECUTIONS = 0
TTY_QUERY = 0
SERIAL_OPEN = 0
REGISTER_READ = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
MOTOR_COMMAND = 0
SUDO = 0
RETRY = 0
TORQUE_BEFORE_AFTER = NOT_OBSERVED
OFF_TO_ON_LIFECYCLE_RELATION = NOT_EVALUATED
```

write `0`의 근거는 bus/write firewall runtime 로그가 아니라, 실행 전 정적 감사에서
중단돼 SSH와 승인 명령, bus 생성 자체가 없었다는 control-flow다.

## 판정

```ini
ROBOT_STATUS_TEST = FAIL_PRECHECK / NOT_RUN
TEACHING_PLAN = NOT_WRITTEN_PASS_REQUIRED
NEXT_LIVE_COMMAND = NONE
GIT = NOT_COMMITTED / NOT_PUSHED
```

다음 진행에는 두 선택 중 하나가 필요하다. 기존 root-owned fixed-port helper 한 건의
`sudo -n` 사용을 명시적으로 승인하거나, sudo 없이도 모든 프로세스의 owner를 완전하게
판정할 수 있는 별도 최소 변경을 검토·배치하고 다시 승인받아야 한다. 현재 gate를
제거하거나 불완전한 조회를 FREE로 간주해서는 안 된다.
