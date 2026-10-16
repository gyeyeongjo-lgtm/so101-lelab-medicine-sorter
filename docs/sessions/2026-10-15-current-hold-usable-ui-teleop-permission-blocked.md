# CURRENT HOLD 사용성 확인 / LeLab UI 안전 텔레옵 연결 보류

## 요청과 범위

사용자는 기존 `ATOMIC_HOLD_RESTORE=FAIL`을 유지하고 추가 HOLD restore/Goal sync/Torque toggle을 금지했다. 이후 직접 사용할 텔레옵을 요청했고, **LeLab 화면의 시작·종료 버튼을 안전한 경로로 연결**하는 방식을 선택했다. 이는 이번 작업에서 에이전트가 실제 텔레옵을 시작하라는 뜻으로 해석하지 않았다.

현장 확인은 **지지·정지·전체 비접촉 유지**였다. 기존 복구 실패의 Torque ON 주체/원인은 `UNKNOWN`으로 유지하며 추적 범위를 확장하지 않았다.

## 실제 read-only 안정성 검증 PASS

Jetson의 기존 `atomic_hold_restore` snapshot/check와 exclusive follower lease를 재사용하되, 복구 함수와 write 함수를 호출하지 않았다. 쓰기 차단 상태에서 canonical follower를 단독 연결해 측정했고, 종료 시 `disable_torque=False`로 연결만 해제했다.

- 실제 표본 18개, 관측 구간 **3.171461682초**.
- 축 순서 Pan / Lift / Elbow / Wrist Flex / Roll / Gripper.
- Present = Goal = `[2066,1098,2902,2502,1612,490]` raw.
- Present span 전 축 0 raw, Goal 변화 없음, Goal–Present residual 최대 0 raw.
- Torque 전 축 ON, Moving 전 축 0, 최대 온도 38°C.
- motor/Goal/Torque/config write 모두 0.
- `CURRENT_HOLD_USABLE=true`는 이 관측 구간의 판정이며, 기존 복구 절차 FAIL을 성공으로 바꾸지 않는다. 이후 사용자 시작 시에는 fresh 검사가 다시 필요하다.

원본은 Jetson에만 보존했다:

```text
/home/jetson3/so101-current-hold-teaching-20261014/
  hold-usable-readonly-20261015-ffk1We/stability.json
```

## 최소 로컬 코드 준비

`scripts/supervised_teaching_from_current_hold.py`에 명시적인 `trace=None, recorder_off=True` 계약만 추가했다. 기본 teaching은 여전히 recorder 필수다. UI가 추후 재사용할 recorder-free 경로는 trace/ticket/기록 파일 없이 기존 3초 정지, fresh origin, first Goal skipped, 2° 공통분율 보간, calibration/Elbow/gripper/STOP/외부 Goal 변화 검사를 유지한다. 정상 종료 시 read-only 3회도 유지한다. 패키지 이름에 종속되지 않도록 package-relative import를 사용하고 직접 실행 분기는 보존했다.

로컬 관련 fake/회귀 **85/85 PASS**, 기본 CLI `DRY_RUN_ONLY`, `git diff --check` PASS. 이 코드는 **Jetson에 배치하지 않았다**. UI adapter/handler 연결은 아직 완료하지 않았으며, fake core 통과를 LeLab UI 복구 완료로 보고하지 않는다.

## UI 배치 blocker: 독점 포트 확인 권한

설치 LeLab 0.1.0/Python 3.14.7의 `teleoperate.py`와 `server.py`를 읽기만 했다. 서비스는 user systemd `lelab.service`이며 `sg dialout`으로 uvicorn을 실행한다. 일반 시작 경로는 기존 trace 설정 외에도 calibration/configure/torque 초기화가 있으므로 단순히 trace 환경변수를 지워 실행하지 않았다.

기존 `SystemBusProbe.owner_pids()`는 일반 `fuser`가 `/proc` Permission denied로 불완전한 조회를 하면 `sudo -n fuser`를 요구한다. 서비스와 같은 primary group으로 읽기전용 조회해도 Permission denied가 발생했고, TTY 없는 문맥의 확인은 다음과 같았다:

```text
setsid --wait sg dialout -c 'sudo -n /usr/bin/fuser /dev/ttyACM1 /dev/ttyACM0'
sudo: a password is required
exit = 1
```

최초 `setsid` without `--wait`는 부모 exit0 이후 자식의 password-required 오류가 나왔다. 이를 성공으로 처리하지 않고 `--wait`로 자식 exit1을 확정했다. SSH TTY의 인증 캐시가 있는 privileged 조회는 성공했지만, 이를 UI 서비스 권한의 증거로 쓰지 않는다.

`dialout` 또는 `TIOCEXCL`만으로 이미 열린 다른 소유자 부재를 증명할 수 없으므로 기존 ownership gate를 약화하지 않았다. 서비스 권한 변경, sudoers 추가, 비밀번호 저장, 서비스 재시작은 하지 않았다. 완료하려면 **검증된 fuser 실행파일로 canonical 두 포트의 점유 상태만 읽는 최소 권한**에 대한 별도 승인이 필요하다. 임의 sudo 명령, 와일드카드 인자, 프로세스 종료 옵션은 허용 범위에 포함하지 않는다.

## 종료 상태

```ini
ATOMIC_HOLD_RESTORE = FAIL
TORQUE_STATE_CHANGE_CAUSE = UNKNOWN
CURRENT_HOLD_USABLE = true_at_readonly_observation
RECORDER_FREE_CORE = PASS_LOCAL_FAKE
LELAB_UI_SAFE_START_STOP = NOT_IMPLEMENTED_NOT_DEPLOYED
UI_DEPLOY_READY = BLOCKED_PRIVILEGED_READONLY_PORT_SCAN
SERVICE_CHANGED = NO
TELEOP_ACTUAL_RUN = false
RECORDER = OFF
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
NEXT_LIVE_COMMAND = NONE
```

종료 시 LeLab teleoperation/recording/inference API 모두 inactive, SSH TTY의 privileged `fuser` 양 포트 무출력/exit1로 무점유를 확인하고 SSH를 종료했다. calibration/reference/GRASP TCP/trajectory tolerance/모터 설정은 변경하지 않았다. 기존 사용자 변경·삭제는 보존했다. 이번 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정). 원본 측정 로그와 인증정보는 저장소로 복사하거나 커밋하지 않았다.
