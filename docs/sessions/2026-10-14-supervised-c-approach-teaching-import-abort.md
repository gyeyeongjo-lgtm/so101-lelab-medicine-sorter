# SUPERVISED C APPROACH TEACHING — FK import 오류로 무장 전 중단

사용자는 `RUN SUPERVISED C APPROACH TEACHING`을 승인했다. 현장 팔 지지·정지·전체 비접촉·주변 clear·3초 리더 정지·즉시 중단 준비를 두 번 확인했다. Jetson no-reconfigure 진입점의 정상 종료 경로를 최소 수정해 로컬 관련 `62/62`, Jetson fake `20/20`, compile/dry-run PASS로 확인했다. 변경된 진입점 SHA `aa5cfeb6…74a3e1`. 설치 LeLab 서비스는 변경하지 않았다.

실행 직전 LeLab teleoperation/recording/inference inactive, canonical follower `/dev/ttyACM1=5AE6058306`, leader `/dev/ttyACM0=5AE6085272`, privileged 양 포트 무점유를 확인했다. 쓰기 차단 follower 3회는 모두 Present raw `[2065,1467,2649,2498,1612,490]`, Goal raw `[2065,1466,2649,2497,1611,490]`, Torque 전 축 ON, Moving 전 축 0, Tmax `36°C`, Goal–Present 최대 `1 raw`. read-only 도구는 motor/torque write `0`, 포트 해제. 현장에서는 직후에도 팔 지지·정지·전체 비접촉이 유지됐다.

전용 세션의 pre-connect snapshot과 새 one-shot ticket을 만들고 `--live` 진입점을 1회 호출했다. 현장 확인 문구 입력 직후, follower/leader 버스를 열기 **전** `load_grasp_fk()`에서 첫 오류 `ImportError: attempted relative import with no known parent package`가 발생했다. 원인은 `scripts/teleop_cycle_trace.py`가 직접 스크립트 실행의 top-level import일 때 `from .urdf_forward_kinematics`를 선택하는 경로다. 이전 FK 오프라인 검증은 `from scripts.teleop_cycle_trace` 패키지 import 경로였으므로 이 실행형 import 차이를 재현하지 못했다. 오류 전에 `CycleTrace`/lease/port 연결은 생성되지 않았다.

프로세스 종료, LeLab teleoperation inactive, trace 미생성, one-shot ticket 미소비를 read-only 확인했다. 미소비 ticket은 재사용 방지를 위해 `.aborted-before-arm`으로 **이름만 변경해 보존**했다. 자동 재시도 없음. 사용자 현장 재확인은 `정지·전체 비접촉 유지`였다.

```ini
TEACHING = ABORT_BEFORE_ARMING
PRE_ARM_SETTLE = NOT_RUN
RECORDER = NOT_ARMED
FOLLOWER_PORT_OPEN = NO
LEADER_PORT_OPEN = NO
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
MOTOR_COMMAND = 0
GRASP = NOT_RUN
LIFT = NOT_RUN
NEXT_LIVE_COMMAND = NONE
```

직접 스크립트 import 경로를 별도 오프라인 수정·검증한 뒤 새 승인 없이는 재실행하지 않는다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
