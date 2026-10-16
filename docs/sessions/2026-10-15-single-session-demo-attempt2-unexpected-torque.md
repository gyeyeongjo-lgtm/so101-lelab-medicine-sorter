# 2026-10-15 SINGLE SESSION DEMO attempt 2 — Goal copy 후 예상 밖 Torque ON

## 승인 및 사전 gate

- 사용자 명령: `RUN SINGLE SESSION DEMO`
- 사용자 현장 확인: 팔 지지, 전체 비접촉, 주변 clear, 즉시 중단 준비
- 고정 helper: ACM0 FREE, ACM1 FREE
- LeLab teleoperation / recording / inference: inactive
- helper 기반 follower/leader ownership gate가 적용된 배치본 사용

## 실제 실행

```text
/home/jetson3/so101-current-hold-teaching-20261014/
run-single-session-20261015-live2/
```

동일 exclusive session의 fresh 및 pre-sync recheck:

```ini
Present = [2021,835,3091,2585,1942,487]
Goal = [2025,839,3093,2570,1941,481]
Torque = ALL_OFF
Moving = ALL_0
Tmax = 37 C
```

fresh Present raw를 그대로 Goal_Position에 1회 기록했다. 다음 read-back에서 Present=Goal exact는 확인됐지만, 절차가 Torque_Enable packet을 보내기 전에 Torque가 전 축 ON으로 관측됐다.

```ini
GOAL_WRITE_ATTEMPTS = 1
TORQUE_ON_WRITE_ATTEMPTS_BY_PROCEDURE = 0
OBSERVED_TORQUE_AFTER_GOAL_COPY = ALL_ON
MOVING = ALL_0
```

따라서 기존 fail-closed 조건 `unexpected_torque:expected_all_0`로 즉시 중단했다. 3초 HOLD 안정성, firewall handoff, fresh origins, recorder arm, teaching은 실행하지 않았다. 자동 재시도와 추가 write는 없다.

## 종료

- `hold_restore_audit.json`에 fresh / pre-sync / Goal readback / abort 기록 보존
- cycle count 0
- approach trajectory 및 final empirical pose 미생성
- one-shot ticket 미소비
- 종료 후 ACM0/ACM1 FREE
- SSH 종료
- 현장 사후 확인: 사용자가 예상 밖 움직임은 **전혀 없었다**고 확인

```makefile
HOLD_RESTORE = FAIL
TEACHING = NOT_RUN
APPROACH_PASS = false
TRAJECTORY_RECORDED = false
FINAL_POSE_RECORDED = false
CURRENT_PHYSICAL_STATE = Goal readback 시 Moving all 0 / Torque all ON / 사용자 확인상 예상 밖 움직임 없음
NEXT_ACTION = STOP

GOAL_WRITE = 1
TORQUE_WRITE_BY_PROCEDURE = 0
CONFIG_WRITE = 0
AUTOMATIC_RETRY = 0
NEXT_LIVE_COMMAND = NONE
```

- GRASP/LIFT: `NOT_RUN`
- 이슈 갱신: `NOT_RUN`
- Git: `NOT_COMMITTED / NOT_PUSHED`
