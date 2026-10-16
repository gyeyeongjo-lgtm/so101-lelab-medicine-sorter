# TWO_DEGREE_SLEW_LIMITER / ATOMIC_HOLD_RESTORE Jetson 배치 — fake only

## 범위

사용자는 두 변경의 Jetson 배치와 실제 motor/serial 연결 없는 fake/dry-run만 승인했다. 이번에는 실제 HOLD restore, teaching, read-only motor snapshot도 실행하지 않았다. 앞선 physical supported/stopped/non-contact와 Torque OFF/Goal 0는 **이전 관측/사용자 확인**일 뿐 이번의 fresh 검증으로 승격하지 않는다.

확인한 런타임:

```text
Python = /home/jetson3/.local/share/uv/tools/lelab/bin/python
Python version = 3.14.7
LeLab = 0.1.0
LeRobot = 0.6.0
pyserial = 3.5
cwd = /home/jetson3/so101-current-hold-teaching-20261014
```

시작/종료 시 LeLab teleoperation/recording/inference 상태는 모두 inactive였다. 관련 독립 teaching/atomic/contact-release/LeRobot teleop/replay 이름의 실행 프로세스는 조회에서 발견되지 않았다. 서비스 재시작·설치 worker·환경·UI 변경은 하지 않았다. 실제 port ownership은 이번 fake PASS와 구별하며 live 전에 따로 검증해야 한다.

## 최소 배치와 보존

격리 폴더 내 변경 파일만 4개 전송했다.

| 파일 | 배치 SHA-256 |
| --- | --- |
| scripts/atomic_hold_restore.py | `715df70744bc6e45a21bacd404edecbafbe234b0265837f7d65e5c2b74207c92` |
| scripts/supervised_teaching_from_current_hold.py | `a79f390ce61942874a875bdaf0d5396978b6769561f22097167a7f95b9cbbe0b` |
| tests/test_atomic_hold_restore.py | `c465985187fc6de075d1ebaf525001d6e042e76b074920741e8063c2f1cb0775` |
| tests/test_supervised_teaching_from_current_hold.py | `6aeb10b982deed13eb59761235898c94f8ff4bcbde4b92e42355324353d84c58` |

모두 로컬/Jetson SHA가 일치한다. 기존 `relative_start_teleop.py`, `so101_exclusive_bus.py`, `teleop_cycle_trace.py`, `temporary_elbow_direction_guard.py`도 로컬 SHA와 일치하며 변경하지 않았다. 기존 trace test도 같은 파일임을 확인했다.

기존 teaching 스크립트/test는 아래에 원본 사본으로 보존했다.

```text
/home/jetson3/so101-current-hold-teaching-20261014/deploy-slew-atomic-20261015-yaMH2b/backup/
```

기존 teaching SHA는 `3737e249…a1c96`, 기존 test SHA는 `4d417052…da44d2`다. atomic 파일 두 개는 기존에 없음을 확인한 뒤 추가했다. 전송 archive SHA도 로컬/Jetson 일치한다. tar의 macOS provenance 확장 메타데이터 무시 경고가 있었으나 추출 뒤 소스 SHA 일치로 내용 무결성을 확인했다.

## 최초 검증 오류와 해결

첫 `unittest.loadTestsFromNames(['tests.test_...'])` 시도는 세 테스트 모듈을 찾지 못했다. 정확한 원인은 Jetson의 다음 정규 패키지가 격리 폴더의 namespace `tests/`보다 먼저 선택된 것이다.

```text
/home/jetson3/.local/share/uv/tools/lelab/lib/python3.14/site-packages/tests/__init__.py
ModuleNotFoundError: No module named 'tests.test_atomic_hold_restore'
```

진입점 두 개의 import는 이때도 성공했다. 오류 원본은 배치 폴더의 `fake-verification.txt`에 보존했다. 제어 코드·설치 패키지·reference·gate는 수정하지 않았다. 검증 호출만 절대 경로 `tests/` discovery로 변경했고, 아래 fake 검증이 성공했다. 이것은 실기 재시도가 아니다.

## Jetson fake/dry-run 결과

설치 Python의 테스트 프로세스에서 `serial.Serial.open`과 `serial.serialposix.Serial.open`을 실패 함수로 교체하고, Python audit hook으로 `/dev/` 장치 열기를 차단했다(`/dev/null` 제외). 실제 시리얼 열기 시도/차단 발생은 **0회**였다. 테스트의 bus는 FakeBus, 장치 조회는 fake probe, 시간은 fake clock이다. FK sibling import regression의 subprocess도 검사된 import-only 코드이며 serial을 열지 않는다.

절대 tests 경로 discovery 결과 **88/88 PASS**:

- atomic HOLD 32개: exclusive flow, canonical identity/경쟁 owner/동일 lock/LeLab 활성 차단, raw integer exact copy, readback mismatch, Torque ON exactly once, retry 0, partial enable/통신 오류/STOP 시 추가 write 없음, 3초 표본 시간, 정상/오류 cleanup.
- supervised teaching 37개: 2° 경계·분할·다관절 fraction·방향 반전·HOLD·STOP, gripper 기존 규칙, raw/historical/startup gate, 첫 Goal 생략·recorder 등.
- 기존 trace 19개: guard 전 요청 기록, 첫 실제 Goal, fresh origins/startup/ticket/recorder 관련 회귀.

추가 fake 예제의 arm delta `(Pan +2.65, Lift −1.325, Elbow +5.3, Flex +0.53, Roll 0)`와 허용 gripper `+1.5pp`에 같은 fraction을 적용했다. Elbow emitted step은 `+2.0,+2.0,+1.3°`, 최대 arm step은 **2.0°**다. raw/실제 기계적 추종을 검증한 값은 아니다.

atomic fake는 single connect/disconnect 각 1회와 lock release, Goal packet 1회에 fresh raw의 정확한 복사, Torque ON packet 1회, Torque OFF packet 0회, config write 0회, immediate readback 및 **31표본/3.0초** 관측을 확인했다. fake 결과의 `HOLD_RESTORED`는 메모리 모의 장치 결과이며 실제 로봇 HOLD 성공이 아니다.

기본 direct CLI 두 개와 네 파일 compile도 PASS:

```text
python scripts/atomic_hold_restore.py
  OFFLINE_PLAN_ONLY, serial_open=0, motor_command=0, live_restore=NOT_RUN
python scripts/supervised_teaching_from_current_hold.py
  DRY_RUN_ONLY, serial_open=0, goal_write=0, torque_write=0, config_write=0
```

실제 명령은 위에 기록한 설치 Python으로 실행했다. fake 성공 로그는 배치 폴더의 `fake-verification-discovery.txt`, 두 기본 CLI 결과는 `atomic-default-dry-run.txt`, `teaching-default-dry-run.txt`, 최종 배치 SHA는 `deployed-sha256.txt`에 보존했다. 원본 로그는 저장소로 가져오거나 커밋하지 않았다.

## 종료

```ini
JETSON_DEPLOY = PASS
TWO_DEGREE_SLEW_LIMITER = PASS
MAX_EMITTED_STEP = 2.0 deg (FAKE)
ATOMIC_HOLD_RESTORE_READY = PASS
EXCLUSIVE_PORT_CONTROL = PASS
VALIDATION = JETSON_FAKE_DRY_RUN_ONLY
SERIAL_LIVE = false
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
ACTUAL_HOLD_RESTORE = NOT_RUN
TEACHING_ACTUAL_RUN = false
NEXT_LIVE_COMMAND = RUN ATOMIC HOLD RESTORE
```

PASS는 배치 및 fake 준비 완료 의미다. 실제 장치 3초 안정성·포트 독점·비접촉을 확인한 것으로 해석하지 않는다. 다음 명령은 별도 승인 후보이며 이번에 실행하지 않았다. SSH 종료 완료. 기존 calibration, GRASP TCP, historical reference, trajectory convergence tolerance, 2° 제한, torque/gain, LeLab 정상 서비스는 보존했다.

변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정). 기존 사용자 dirty worktree 보존. 비밀번호/키/원본 로그는 커밋하지 않았다.
