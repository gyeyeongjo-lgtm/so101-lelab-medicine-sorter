# 2026-10-15 SINGLE SESSION DEMO attempt 1 — port ownership unknown 중단

## 승인 및 현장 조건

- 사용자 명령: `RUN SINGLE SESSION DEMO`
- 사용자 현장 확인: 팔 지지, 전체 비접촉, 주변 clear, 즉시 중단 준비
- 직전 read-only 확인:
  - `/dev/ttyACM0`: FREE
  - `/dev/ttyACM1`: FREE
  - LeLab teleoperation: inactive
  - recording: inactive
  - inference: inactive
  - Jetson 배치 파일 SHA 일치

## 실제 실행

새 one-shot ticket과 출력 폴더를 만들고 승인된 single-session live entrypoint를 1회 호출했다.

```text
/home/jetson3/so101-current-hold-teaching-20261014/
run-single-session-20261015-live1/
```

현장 확인 문자열을 입력한 직후 첫 exclusive lease gate가 다음 오류로 중단했다.

```text
SINGLE_SESSION_DEMO_ABORT:PreflightError:port_ownership_unknown
```

`SystemBusProbe`가 서비스 문맥 밖 SSH 실행에서도 owner를 확정하지 못해 fail-closed했다. 고정 포트 helper의 FREE 결과를 entrypoint가 직접 사용하는 변경은 이번 live 승인 범위에서 수행하지 않았다. 사용자 지시대로 첫 실패에서 정지했으며 자동 재시도하지 않았다.

## 무명령 증거

- `hold_restore_audit.json`: `[]`
- startup trace: `PRE_ARM_ABORT / PreflightError / port_ownership_unknown`
- cycle count: `0`
- manifest `data_complete=false`, `physical_task_success_verified=false`
- one-shot ticket: 미소비 상태로 보존
- bus object 생성 및 serial open 전에 lease gate 실패
- Goal/Torque/config/motor write: 모두 `0`
- 종료 후 고정 포트 helper: ACM0/ACM1 모두 FREE
- SSH 종료

```makefile
HOLD_RESTORE = NOT_RUN
TEACHING = NOT_RUN
APPROACH_PASS = false
TRAJECTORY_RECORDED = false
FINAL_POSE_RECORDED = false
CURRENT_PHYSICAL_STATE = pre-run supported/non-contact; command에 의한 변화 없음; post-run 현장 재확인 NOT_RUN
NEXT_ACTION = STOP

SERIAL_OPEN = 0
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
AUTOMATIC_RETRY = 0
NEXT_LIVE_COMMAND = NONE
```

- 실제 HOLD/teaching/approach/grasp/lift: `NOT_RUN`
- 이슈 갱신: `NOT_RUN`
- Git: `NOT_COMMITTED / NOT_PUSHED`
