# 2026-10-15 DEMO CAPTURE RUN — LIVE PRECHECK Torque OFF 중단

## 요청 범위

- 사용자 진술상 다른 컴퓨터에서 실행 중이던 LeLab은 종료됐다.
- 현재 검증된 기능만 사용해 `CURRENT START → supervised relative-start → C approach → 가능하면 grasp → 가능하면 short lift` 순서로 진행하고, 첫 실패 단계에서 정지한다.
- calibration, HOME/SAFE_HIGH, recovery, global tolerance, torque/gain, 2° step limit 및 무관한 기능은 변경하지 않는다.

## 실행 전 제어 상태

- LeLab teleoperation / recording / inference: inactive
- canonical `/dev/ttyACM0`, `/dev/ttyACM1`: 점유 프로세스 없음
- 이번 실행의 실제 물리 비접촉 확인: `NOT_CONFIRMED_CURRENT_RUN`
  - fresh register gate 중 Torque 조건에서 먼저 실패했으므로 사용자에게 새 현장 확인을 요청하기 전에 중단했다.

## fresh read-only 결과

follower와 leader를 각각 3회 읽었으며 각 장치의 세 표본은 동일했다.

```ini
FOLLOWER_PRESENT_RAW = [2021,835,3091,2585,1942,487]
FOLLOWER_GOAL_RAW = [2025,839,3093,2570,1941,481]
FOLLOWER_TORQUE = [0,0,0,0,0,0]
FOLLOWER_MOVING = [0,0,0,0,0,0]
FOLLOWER_MAX_TEMPERATURE_C = 37

LEADER_PRESENT_RAW = [2062,904,3066,2469,2194,2068]
LEADER_GOAL_RAW = [0,0,0,0,0,0]
LEADER_TORQUE = [0,0,0,0,0,0]
LEADER_MOVING = [0,0,0,0,0,0]
LEADER_MAX_TEMPERATURE_C = 30

PRESENT_DRIFT = NONE_ACROSS_3_SAMPLES
```

## 판정

필수 LIVE PRECHECK 조건인 follower `Torque = ALL ON`을 만족하지 못했다. 따라서 첫 실패 단계에서 즉시 정지했고, 3초 settle, fresh origin capture, relative-start arm, recorder, teaching, approach, grasp, lift는 모두 실행하지 않았다.

직전 사용 가능 HOLD pose `[2066,1098,2902,2502,1612,490]`와 현재 follower pose의 차이가 크지만 상태 변화의 주체와 원인은 확인하지 않았다. 임의 Goal sync, HOLD restore, Torque toggle 또는 자세 복구를 수행하지 않는다. 이전 `ATOMIC_HOLD_RESTORE=FAIL` 및 예상 밖 Torque 상태 변화 원인 `UNKNOWN`도 유지한다.

```makefile
LIVE_PRECHECK = FAIL — follower Torque ALL OFF
TEACHING = NOT_RUN
APPROACH_PASS = false
GRASP_PASS = NOT_RUN
LIFT_PASS = NOT_RUN
CURRENT_PHYSICAL_STATE = register상 Moving all 0 / 현장 비접촉 NOT_CONFIRMED_CURRENT_RUN
NEXT_ACTION = STOP

ABORT_BEFORE_ARMING = true
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
NEXT_LIVE_COMMAND = NONE
```

## 종료 상태

- teleoperation / recording / inference: inactive
- `/dev/ttyACM0`, `/dev/ttyACM1`: FREE
- SSH: 종료
- 자동 재시도: 0
- 이슈 갱신: `NOT_RUN`
- Git: `NOT_COMMITTED / NOT_PUSHED`
