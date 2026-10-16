# LeLab UI 안전 텔레옵 / 고정 포트 read-only 권한 배치

## 승인 범위

사용자는 LeLab 서비스에 `/dev/ttyACM0`, `/dev/ttyACM1`의 프로세스 점유 상태만 조회하는 최소 read-only 권한 추가를 승인했다. motor/serial write, process signal/kill, 임의 장치·경로 조회, 임의 sudo 명령은 금지했다. 이어서 UI의 기존 포트 소유권 검사가 이 helper를 사용하게 하고 실제 텔레옵은 시작하지 말라고 했다.

직전 실제 read-only 상태 `CURRENT_HOLD_USABLE=true`와 기존 `ATOMIC_HOLD_RESTORE=FAIL`, Torque ON 전환 원인 `UNKNOWN`은 구분해 유지한다. 이번에는 HOLD restore, Goal sync, Torque toggle, calibration/reference 변경을 하지 않았다.

## root-owned 고정 범위 helper

Jetson에 다음을 설치했다.

```text
/usr/local/sbin/so101-fixed-port-occupancy
  owner=root:root mode=0755
/etc/sudoers.d/so101-fixed-port-occupancy
  owner=root:root mode=0440
```

helper는 인자를 받지 않으며 코드에 고정된 `/dev/ttyACM0`, `/dev/ttyACM1`만 `/proc/<pid>/fd`에서 조회한다. 장치를 열거나 읽거나 쓰지 않는다. 출력은 tab-separated `port / FREE|OCCUPIED / PID / process-name`뿐이다. import는 `os`, `sys`, `pathlib` 계열뿐이며 AST 검사에서 `open`, `os.open`, `os.kill`, `os.killpg`, `signal.*`, `subprocess.*` 호출은 없었다.

sudoers의 유일한 NOPASSWD 명령은 **인자 없는** helper 하나다:

```sudoers
Cmnd_Alias SO101_FIXED_PORT_OCCUPANCY = /usr/local/sbin/so101-fixed-port-occupancy ""
jetson3 ALL=(root) NOPASSWD: SO101_FIXED_PORT_OCCUPANCY
```

staging 및 설치 sudoers 모두 `visudo -cf` PASS. 서비스와 같은 TTY 없는 `sg dialout` 문맥에서 인자 없는 실행은 exit0이었고, helper에 `/dev/ttyACM0` 인자를 추가한 실행은 `sudo: a password is required`, exit1로 차단됐다. 따라서 임의 경로나 helper 옵션을 NOPASSWD로 전달할 수 없다. `fuser`, `lsof`, shell에는 새 NOPASSWD 권한을 부여하지 않았다.

process-kill 옵션을 실제로 호출하는 검증은 안전 정책에 의해 실행하지 않았다. 대신 sudoers의 exact no-argument command, 추가 인자 거부, helper AST에 process-control API가 없는 것을 결합해 kill/signal 권한 부재를 확인했다.

## 실제 조회 검증 — motor/serial write 0

서비스 계정 문맥에서 최초 조회:

```text
/dev/ttyACM0  FREE      -       -
/dev/ttyACM1  FREE      -       -
```

각 포트를 한 번씩 `O_RDONLY|O_NONBLOCK|O_NOCTTY` 파일 디스크립터로만 열고 직렬 데이터·termios·motor register를 전혀 쓰지 않은 상태에서 helper를 조회했다:

```text
/dev/ttyACM0  OCCUPIED  581735  python
/dev/ttyACM1  OCCUPIED  581735  python
```

각 descriptor는 즉시 닫았고, 마지막 helper 조회에서 두 포트 모두 다시 `FREE`였다. 이 검증은 occupancy lookup 검증이지 LeRobot serial connection 또는 teleop 실행이 아니다.

## UI 안전 경로 연결

설치 LeLab의 `/move-arm`, `/stop-teleoperation`, `/teleoperation-status`, `/joint-positions` handler는 `LELAB_UI_NO_RECONFIG=1`일 때 새 `current_hold_ui_teleop` adapter만 사용하도록 최소 분기했다. 기존 일반 경로 코드는 삭제하지 않았다. systemd user service에는 drop-in만 추가했다:

```text
/home/jetson3/.config/systemd/user/lelab.service.d/20-safe-ui.conf
Environment=LELAB_UI_NO_RECONFIG=1
```

새 adapter는 다음 계약을 유지한다.

- request port/config를 `/dev/ttyACM0`, `/dev/ttyACM1`, `so-101.json`으로 고정 검증.
- helper 기반 양 버스 owner 확인, 로컬 lock 및 `TIOCEXCL` 유지.
- `connect(handshake=False)`, stored calibration read-only 사용; `setup_calibration_files`, `write_calibration`, `configure`, torque/config write 호출 금지.
- recorder/inference/replay OFF. recorder-free core는 명시적인 `trace=None, recorder_off=True`에서만 허용.
- Torque ON/Moving0/Goal 불변·bounded residual·온도·Present drift 0의 3초 gate 후 fresh leader/follower origin capture.
- first Goal skipped, historical reference 비차단 quantized path, 기존 2° 공통분율 slew/servo/Elbow/gripper-open-only guards 유지.
- Stop event와 send lock으로 Stop 수락 뒤 새 Goal packet 진입 차단. 상태는 양 버스 disconnect(`disable_torque=False`)와 lease release 이후에만 inactive.
- `/joint-positions`는 worker의 same-owner telemetry cache만 반환하며 병렬 serial read를 하지 않는다.

설치 전 기존 package 파일은 `/home/jetson3/lelab-safe-ui-deploy-20261015/backup/`에 보존했다. 새 모듈은 원래 존재하지 않았음을 기록했다. staging과 설치본 주요 4파일 SHA가 일치했다.

## 비실기 검증

- 로컬 helper/core/UI/trace/relative 회귀 **95/95 PASS**, compile·diff-check PASS.
- Jetson 설치 Python 3.14.7 compile/import PASS.
- 설치 `SystemBusProbe.owner_pids()`가 helper 결과로 ACM0/ACM1 free를 파싱했고, `serial.Serial`을 예외로 막은 검사에서 `SERIAL_OPEN=0`.
- 설치 UI handler fake worker에서 Start→`ARMED`, duplicate Start reject, Stop→`INACTIVE` PASS. `SERIAL_OPEN=0`, `MOTOR_COMMAND=0`.
- 설치 recorder-free core 기본 CLI는 `DRY_RUN_ONLY`, serial/Goal/Torque/config write 0.
- service restart 전 기존 LeLab 세 제어 inactive와 privileged 포트 무점유 확인. drop-in 적용 후 MainPID `581703`, 환경 `LELAB_UI_NO_RECONFIG=1`, service active.
- 재시작 후 `/teleoperation-status`는 `INACTIVE`, recording/inference inactive, joint endpoint는 cache 없음으로 정상 fail-closed. helper 최종 양 포트 `FREE`.

초기 정적 grep 검증은 잘못된 bracket pattern으로 exit2였고, 이를 근거로 쓰지 않았다. 이후 AST 검사로 대체했다. process-kill 명령 자체는 실행하지 않았다.

## 최종 상태

```ini
PORT_OCCUPANCY_PERMISSION = PASS
ACM0_QUERY = PASS
ACM1_QUERY = PASS
PRIVILEGE_SCOPE = READ_ONLY_FIXED_PORTS
UI_SAFE_START_STOP = PASS_DEPLOYED_FAKE_VERIFIED
TELEOP_ACTUAL_RUN = false
RECORDER = OFF
INFERENCE = OFF
REPLAY = OFF
SERIAL_WRITE = 0
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
GRASP = NOT_RUN
LIFT = NOT_RUN
NEXT_LIVE_COMMAND = RUN SUPERVISED C APPROACH TEACHING
```

실제 UI Start는 별도 live 승인과 fresh 현장 지지·정지·전체 비접촉 확인 전까지 누르지 않았다. 기존 calibration, historical reference, GRASP TCP, trajectory tolerance, 카메라와 네트워크 설정은 변경하지 않았다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정). 비밀번호·원본 hardware telemetry는 저장소에 쓰지 않았다.
