# C approach teaching — CONTACT_RELEASED 현장 확인, fresh 상태 변경으로 live HOLD

사용자는 `CONTACT_RELEASED=true`, 현재 자세 유지, CURRENT→C PRE_APPROACH→C APPROACH에서 GRASP 전 정지를 요청했다. 현장 재확인에서 팔·리더 정지, 전체 링크·손가락 비접촉, C가 들어갈 실제 벌어짐 충분, 팔 지지 및 현재 Torque OFF·Lift/Elbow 자세 변경이 의도됐음을 확인했다. 이 현재 비접촉은 이전 `CONTACT_RELEASE_ATTEMPT1=FAIL`을 PASS로 소급하지 않는다. HOME/SAFE_HIGH/C calibration/GRASP TCP/UI 설정은 건드리지 않았다.

Jetson 8000 teleoperation/recording/inference는 inactive, canonical leader `/dev/ttyACM0=5AE6085272`, follower `/dev/ttyACM1=5AE6058306`, privileged fuser 무점유다. 기존 쓰기차단 follower 도구로 0.2초 간격 read-only 정확히 3회 측정했고 값은 동일했다. Present raw `[2030,891,3122,2423,1613,494]`, arm ° `[-6.285714,-93.494505,+100.087912,+30.109890,-22.109890]`, gripper encoder `4.957160%`. Goal raw 전 축 `0`, Torque_Enable 전 축 `0`, Moving 전 축 `0`, Tmax `36°C`. 이는 직전 attempt1 종료 pose와 크게 다르다. 기존 저장 servo bounds 기준 Elbow `+100.088°`는 upper `+95.011°` 바깥이고 Lift `-93.495°`는 lower `-99.846°`에 가깝다. Goal raw 0인 채 시작 과정에서 torque/configuration write가 발생하면 예기치 않은 움직임을 배제할 수 없다. 현장 팔 지지 확인에도 **실제 teaching 시작 gate는 FAIL**이다. 현재 자세 복귀, Goal sync, Torque 변경, gripper close/open, 세션 시작, one-shot ticket 생성은 하지 않았다.

요청한 guard 이전 증거는 기존 `CycleTrace`에 `requests.jsonl`을 추가하고 `PRE_GUARD_REQUEST`에 leader, requested target, 이전 target, 축별 delta, 제한 축, fresh actual Present/Goal 및 FK GRASP TCP XYZ를 flush하도록 준비했다. 첫 실제 전송 후 `FIRST_SENT_GOAL`에 raw Goal readback을 1회만 남긴다. 설치 worker에는 적용하지 않고 격리된 patch에서만 기존 servo/2° guard 판정 전 로그 기록과 첫 전송 직후 기록을 연결했다. 로컬 `tests.test_teleop_cycle_trace tests.test_relative_start_teleop` `35/35 PASS`; Jetson 설치 Python의 격리 stage fake에서 transient Moving settle, Goal/drift abort, one-shot, pre-guard/first Goal, arm-only gripper omit, 3회 final fake output 등 PASS, real serial/Goal/Torque/motor command `0`. installed `teleoperate.py` SHA `3a8d6a13…3122f`, installed trace SHA `5e19e172…94fdb`로 변경 없고 서비스 재시작도 없다. 이 패치는 현재 live 배치/실기 승인 상태가 아니다.

```ini
CONTACT_RELEASED = TRUE (human-confirmed current state; attempt1 remains FAIL)
FRESH_READ_ONLY_3 = PASS
MOVING = ALL_0
TORQUE = ALL_OFF
GOAL_RAW = ALL_0
SERVO_BOUNDS = FAIL (Elbow +100.088° > existing +95.011°)
PRE_GUARD_LOGGING = PASS (local/Jetson isolated fake only)
INSTALLED_WORKER_PATCH = NOT_DEPLOYED
TEACHING = NOT_RUN
C_APPROACH_EMPIRICAL = NOT_RECORDED
GRASP = NOT_RUN
LIFT = NOT_RUN
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
NEXT_LIVE_COMMAND = NONE
```

현재 pose는 되돌리지 않는다. 현장 상태를 유지하며 별도 승인 없는 Torque/Goal/teleop 조작은 금지한다. 원본 로그·비밀번호를 커밋하지 않는다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
