# DEMO critical path — PRE_ARM_HOLD_STABILITY 국소 변경·Jetson fake PASS

목표 범위는 `SUPERVISED START→C APPROACH→GRASP→LIFT`다. 이번 턴은 직전 `Lift Goal−Present=2 raw`로 막힌 **teaching 무장 전 HOLD 판정**만 다뤘다. 실제 serial/teaching/GRASP/LIFT는 실행하지 않았다.

기존 실측 근거: [2026-10-11 tracking diagnostic](2026-10-11-robot-fk-tcp-pivot-diagnostic.md)의 read-only HOLD 구간에서 Torque 전 축 ON, Moving 전 축 0, Present raw span 전 축 0인 10개 연속 표본(약 1초)에 Goal−Present raw `[+2,+10,+4,+1,−1,0]`이 유지됐다. 이는 큰 잔차가 곧 움직임이라는 주장을 반박하는 **정지 사례**이지 teaching 성공 또는 일반 trajectory 수렴 근거가 아니다. [2026-10-14 C approach attempt1](2026-10-14-c-approach-teaching-attempt1.md)도 실행 전 현장 비접촉·Torque ON·Moving 0의 read-only 3회에서 Elbow 잔차 `−0.527473°`(약 6 raw)가 동일했다. 직전 fresh [실행 전 측정](2026-10-15-supervised-c-approach-teaching-lift-raw-gate-block.md)은 Lift 2 raw, 3회 동일이었다.

`scripts/supervised_teaching_from_current_hold.py`의 **quantized teaching PRE_ARM**에만, 위 실제 정지 기록의 최대값 `10 raw`를 상한으로 적용했다. pre-connect와 post-connect의 Present/Goal exact 일치, Torque ON, Moving 0, 정상 온도, 3초간 Present raw drift `0`, Goal 불변, 각 축 잔차가 최초 잔차보다 증가하지 않음, fresh leader/follower origin, 첫 Goal 생략, 기존 range/step/Elbow guard는 유지한다. 현장 physical non-contact는 다음 live 직전에 별도로 확인해야 한다. 기존 `hold_stable_quantized`의 `≤1 raw`, exact-zero 의미, historical reference, trajectory convergence tolerance는 변경하지 않았다. Goal sync, Torque toggle, correction 및 새 recovery는 `0`이다.

로컬 관련 fake `44/44 PASS`. Jetson 격리 폴더 `/home/jetson3/so101-current-hold-teaching-20261014/`의 진입점과 해당 fake 테스트만 배치하고 이전 파일 두 개를 `.pre_demo_prearm_20261015` 사본으로 보존했다. 배치 SHA 로컬/Jetson 일치(`3737e249…a1c96`, `4d417052…da44d2`). 설치 LeLab 서비스/worker/env는 변경·재시작하지 않았다. 설치 Python `3.14.7`에서 fake `44/44 PASS`, 기본 CLI dry-run 1회 PASS (`serial_open=0`, `goal_write=0`, `torque_write=0`, `config_write=0`). fake는 2/10 raw 안정 PASS, 11 raw·Present/Goal drift·Moving·온도 fault FAIL, 3초 후 origin/첫 Goal 생략·recorder와 write firewall을 포함한다.

```ini
PRE_ARM_HOLD_STABILITY = PASS_FAKE_DRY_RUN
PRE_ARM_GAP_BOUND = 10 raw (historical stationary HOLD evidence)
TRAJECTORY_CONVERGENCE_TOLERANCE = UNCHANGED
HISTORICAL_REFERENCE = UNCHANGED
SERIAL_OPEN = 0
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
TEACHING_ACTUAL_RUN = false
GRASP_PASS = NOT_RUN
LIFT_PASS = NOT_RUN
NEXT_LIVE_COMMAND = RUN SUPERVISED C APPROACH TEACHING
```

다음 live는 별도 승인, fresh port/Torque/Moving/온도/비접촉 확인과 실제 3초 무이동을 전제로 한다. 이번 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정).
