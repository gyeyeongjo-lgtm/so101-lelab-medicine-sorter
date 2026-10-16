# 2026-10-16 Jetson d309c94 비동작 배치

## 승인 범위

코드 배치와 장비 없는 확인만 수행했다. `/dev/ttyACM*`, serial open,
`robot-status`, LeRobot 실행, udev/권한, sudo, 시스템 패키지, 서비스에는
접근하거나 변경하지 않았다.

## 원격 및 배치

배치 전 GitHub 원격 확인:

```text
d309c940407bf0dd112ceb16fddc3cf3f6f1be6f refs/heads/fix/usb-recording
```

Jetson 대상 `/home/jetson3/so101-lelab-medicine-sorter`가 존재하지 않음을 확인한
뒤, 그 새 경로에만 `fix/usb-recording`을 clone하고 commit `d309c94`를 detached
checkout했다. 다른 디렉터리의 삭제·덮어쓰기·수정은 없었다.

## 확인 결과

| 항목 | 결과 | 값/근거 |
| --- | --- | --- |
| GitHub branch commit | PASS | `d309c940407bf0dd112ceb16fddc3cf3f6f1be6f` |
| Jetson path | PASS | `/home/jetson3/so101-lelab-medicine-sorter` |
| Jetson `git rev-parse HEAD` | PASS | full hash exact match |
| git clean before checks | PASS | porcelain empty |
| git clean after checks | PASS | porcelain empty |
| `medicine_sorter/robot.py` | PASS | present |
| `robot.py` local/Jetson SHA | PASS | `d8f7598be481f325404290ac3aa4bd558be46a318968fee21322565beda123ec` |
| `cli.py` SHA | PASS | `e3486c323f7545348b30038c51129506ff255fcfff7e5989cc5c9718934e2cd9` |
| system config SHA | PASS | `e6627f7d85b37e4c27236b636f9d205a98b7e08e4a086ffb465be3089a2fb99d` |
| `python3 -c "import medicine_sorter"` | PASS | `IMPORT_OK` |
| `python3 -m medicine_sorter --help` | PASS | parser help 출력 후 종료 |
| 기본 Python offline sorter tests | PASS | `30/30`, 0.039 s |
| LeLab Python import/help | PASS | device access 없이 정상 |
| LeLab Python offline sorter tests | PASS | `30/30`, 0.040 s |
| config follower port | PASS | `/dev/ttyACM1` |
| config follower serial | PASS | `5AE6058306` |

## Python 및 LeRobot

```text
default python3=/home/jetson3/miniforge3/bin/python3
default Python=3.14.6
default python3 lerobot=NOT_INSTALLED (find_spec=None)

LeLab Python=/home/jetson3/.local/share/uv/tools/lelab/bin/python
LeLab Python version=3.14.7
LeRobot version=0.6.0
```

설치 작업은 하지 않았다. 기본 `python3`에서는 import/help/mock test가 가능하지만
실제 read-only adapter가 bus factory를 만들 때 필요한 `lerobot`이 없다. 반면 기존
LeLab Python에는 필요한 LeRobot `0.6.0`이 이미 설치돼 있고 동일 오프라인 검사를
통과했다. 따라서 다음 live 시험에는 이전 literal `python3` 대신 이 기존 Python
절대 경로를 명시해야 한다. 이는 신규 설치가 아니라 기존 runtime 선택이다.

## 장치 비접근 근거

실행한 Python 작업은 package import, argparse help, JSON config read, mock/fake bus
unit tests뿐이다. 단일 진입점은 `robot-status` subcommand를 선택해야만
`SO101ReadOnlyStatusAdapter.from_config`를 호출하며 이번에는 선택하지 않았다.

```ini
TTY_QUERY = 0
SERIAL_OPEN = 0
ROBOT_STATUS = NOT_RUN
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
MOTOR_COMMAND = 0
SUDO = 0
PACKAGE_INSTALL = 0
```

## 다음 재승인 후보

```bash
cd /home/jetson3/so101-lelab-medicine-sorter
/home/jetson3/.local/share/uv/tools/lelab/bin/python -m medicine_sorter --config configs/system.example.json robot-status
```

범위는 follower 후보 `/dev/ttyACM1`, expected serial `5AE6058306`, 정확히 1회,
재시도·다른 포트 없음, Goal/Torque/config/motor write 0,
`SO101Follower.connect()` 금지다. 실행 전 commit/hash, port owner, serial,
`disconnect(disable_torque=False)`를 다시 확인하며 하나라도 다르면 실행하지 않는다.

```ini
DEPLOY_CHECK = PASS
SERIAL_OPEN = 0
MOTOR_COMMAND = 0
GIT = NOT_COMMITTED / NOT_PUSHED
```
