# Goal/Present raw 동기화 — 실행 직전 Torque OFF gate 실패

## 승인 범위

현재 물리 자세 유지. fresh read-only 상태에서 `Moving=all 0`, `Torque=all OFF`, 현장 팔 지지·정지·비접촉을 확인한 뒤에만, 여섯 축의 fresh `Present_Position raw`를 동일 축 `Goal_Position raw`에 한 번 복사한다. Torque ON, 새 자세 목표, 그리퍼 개방, teleop/teaching은 금지한다. 사용자는 현장에서 팔 전체 지지·정지·비접촉·즉시 중단 준비를 확인했다.

## 사전 읽기

Jetson LeLab teleoperation/recording/inference inactive, canonical follower `/dev/ttyACM1=5AE6058306`, privileged fuser 무점유를 확인했다. 기존 쓰기 차단 도구 SHA는 로컬·Jetson 모두 `7c440b81…f3c56`이다. 설치 Python `3.14.7`로 0.2초 간격 read-only 3회가 모두 동일했다.

| 축 | Present raw | Present °/% | Goal raw | Torque | Moving | Temperature °C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pan | 2032 | -6.109890° | 0 | 0 | 0 | 35 |
| Lift | 1642 | -27.472527° | 0 | 0 | 0 | 35 |
| Elbow | 2752 | +67.560440° | 0 | 0 | 0 | 34 |
| Flex | 2396 | +27.736264° | 0 | 0 | 0 | 34 |
| Roll | 1612 | -22.197802° | 0 | 0 | 0 | 35 |
| Gripper | 490 | 4.712362% | 0 | 0 | 0 | 38 |

## 전용 실행 경로와 실패

기존 `recover_follower_hold.py`는 Goal을 기록한 뒤 Torque ON까지 수행하므로 사용하지 않았다. `scripts/sync_follower_goal_to_present_only.py`는 독점 포트/USB/제어 idle 확인과 직렬 포트 seal, 3회 안정 snapshot 및 fresh snapshot의 Torque OFF·Moving 0을 확인한 뒤에만 raw Goal을 1회 기록하도록 만들었다. 코드에 Torque write 경로는 없다. 로컬 fake `6/6 PASS`, py_compile/diff check PASS. Jetson 격리 폴더에 배치하고 SHA 일치 및 설치 Python compile을 확인했다.

실제 실행은 `GOAL_PRESENT_SYNC_FAIL:RuntimeError:torque_not_all_off`로 **첫 snapshot gate에서 중단**됐다. Goal write 전이므로 `Goal_Position` 명령은 보내지 않았다. 실패한 snapshot의 축별 Torque 값은 출력되지 않아 ON 축과 변화 시점은 `UNKNOWN`이다. 사전 읽기와 다른 조건을 임의로 해소하지 않았고 자동 재시도하지 않았다. 실패 뒤 privileged follower fuser 무점유, LeLab 3제어 inactive, SSH 종료를 확인했다. 추가 serial read나 토크 조작은 하지 않았다.

## 최종 상태

```ini
GOAL_PRESENT_SYNC = FAIL
MAX_GOAL_PRESENT_RAW_DIFF = NOT_MEASURED_AFTER_ABORT
TORQUE = NOT_ALL_OFF_AT_EXECUTION_GATE / CURRENT_UNKNOWN
PHYSICAL_MOTION = NOT_VERIFIED_AFTER_ABORT
GOAL_WRITE = 0
TORQUE_WRITE = 0
MOTOR_COMMAND = 0
NEXT_LIVE_COMMAND = NONE
```

현장 추가 정지·비접촉 확인과 Torque 상태 변화 원인 파악 전에는 Torque ON, 그리퍼 개방, teleop/teaching을 하지 않는다. 원본 로그·비밀번호·키·개인정보는 커밋하지 않는다. 이번 변경 `NOT_COMMITTED/NOT_PUSHED`; 이슈 갱신 `NOT_RUN`(대상 미지정).
