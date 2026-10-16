# CURRENT POSE HOLD RECOVERY — 접촉 gate 차단

사용자는 Elbow out-of-range blocker를 fresh raw `2774` / `+69.494505°` 근거로 해제하고, Torque OFF 상태에서 `Goal_Position raw = fresh Present raw` 1회 동기화까지만 요청했다. Torque ON, teaching은 승인하지 않았다. 실행 전 팔 지지·정지·전체 비접촉 현장 확인을 요청했고 사용자는 **그리퍼 끝부분만 테이블에 접촉**한다고 답했다.

기존 Goal-only 도구 `scripts/sync_follower_goal_to_present_only.py`를 점검했다. 3회 안정 Present/Goal 및 fresh snapshot에 Torque OFF·Moving 0·온도·독점 버스 gate를 적용한 뒤 raw Present를 그대로 각 축 Goal에 `sync_write` 1회만 수행하고 read-back을 검증하며 Torque write 경로는 없다. 로컬 fake `6/6 PASS`; 이번 Jetson live 실행은 비접촉 gate 전이므로 `NOT_RUN`이다.

Jetson LeLab teleoperation/recording/inference inactive, follower `5AE6058306→/dev/ttyACM1`, privileged follower/leader 포트 무점유에서 기존 쓰기 차단 측정 도구로 3회 read-only를 수행했다. Present raw `[2029,1472,2774,2658,1612,489]`, arm `[-6.373626,-42.417582,+69.494505,+50.769231,-22.197802]°`, gripper encoder `4.651163%`, Goal raw 전 축 `0`, Torque 전 축 OFF, Moving 전 축 `0`, Tmax `36°C`; 세 표본이 같았다. 첫 기본 Python은 serial 모듈이 없어 사용하지 않았고 실제 LeLab 설치 Python으로 측정했다. 측정 종료 뒤 privileged 양 포트 무점유 확인 후 SSH 종료.

현재 물리 접촉 때문에 이 3회 표본을 Goal write 근거로 사용하지 않는다. 사용자가 Torque OFF 상태에서 팔을 지지하고 수동으로 최소 접촉 해제한 뒤 정지·비접촉을 새로 확인하면, 그 변경된 현재 자세에서 3회 read-only를 다시 측정해야 한다.

사용자는 수동 접촉 해제가 어렵고 접촉이 유지된다고 추가로 확인했다. 이 절차를 중단한다. 접촉 중 Goal write/Torque ON/teleop을 임의로 시도하지 않으며, 별도 안전한 접촉 해제 방식에 대한 현장 판단과 새 승인 전에는 다음 live command가 없다.

```ini
PHYSICAL_NON_CONTACT = NO (human-confirmed fingertip/table contact)
FRESH_PRESENT = [2029,1472,2774,2658,1612,489] (read-only, before manual release)
GOAL_SYNC = NOT_RUN / BLOCKED_BY_CONTACT
MAX_GOAL_PRESENT_RAW_DIFF = NOT_MEASURED_AFTER_SYNC
TORQUE = ALL_OFF (last read-only snapshot)
GOAL_WRITE = 0
TORQUE_WRITE = 0
MOTOR_COMMAND = 0
NEXT_LIVE_COMMAND = NONE
```

원본 telemetry·자격증명은 저장/커밋하지 않았다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
