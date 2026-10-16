# Historical reference 비교 분리 / fresh-origin teaching Jetson 비실기 배치

사용자 범위는 Jetson 독립 no-reconfigure teaching 진입점의 배치와 fake/dry-run만이다. 실제 serial open, teleop, Goal/config/Torque/motor write는 실행하지 않았다. historical `REFERENCE_PRESENT=[2065,1467,2649,2497,1612,490]`과 기존 exact-zero 정책은 불변이다. Wrist Flex `2498`은 새 baseline/target/reference가 아니다.

Jetson 기존 격리 폴더 `/home/jetson3/so101-current-hold-teaching-20261014/`에 진입점, `teleop_cycle_trace` 기록 모듈, fake 테스트 3개만 반영하고 이전 파일을 `.pre_fresh_origin_20261014`로 보존했다. LeLab 서비스·설치 worker·환경변수는 변경하거나 재시작하지 않았다. 설치 Python `3.14.7` compile PASS, fake `19/19 PASS`, 기본 CLI dry-run PASS (`serial_open=0`, `goal_write=0`, `torque_write=0`, `config_write=0`). 세 파일의 로컬/Jetson SHA-256이 각각 `e1735075…b6bb62`, `84c7dbc8…88a91b`, `34e2c99e…72c93`으로 일치한다. LeLab teleoperation/recording/inference는 검증 종료 시 모두 inactive였다.

fake는 quantized fresh Wrist Flex `2498`에서 historical exact match를 `false`로 별도 기록해도 차단하지 않는 것, 3초 settle 뒤 leader/follower fresh origin 캡처, 첫 Goal 생략, recorder arm 가능, pre-connect/post-connect 1 raw 차이는 계속 ABORT, exact-zero 경로의 1 raw 거부를 확인한다. relative target 수학은 `fresh follower origin + (leader_now - fresh leader origin)`이다. no-reconfigure write firewall 테스트에서 torque/config/unarmed Goal을 차단한다. 이 fake 내부의 sender는 가짜 객체이며 실제 follower command는 없다.

이전 실제 read-only 3회는 Goal–Present 최대 1 raw와 같은 Present/Goal을 보였지만, **이번 배치 턴에는 실제 serial을 열지 않았다**. 다음 live 전 새 현장 비접촉·지지, fresh follower snapshot, Torque/Moving/온도, 포트 단독, 3초 stillness 및 새 ticket을 다시 확인해야 한다. 실제 teaching/GRASP/LIFT는 `NOT_RUN`.

```ini
JETSON_DEPLOY = PASS (isolated independent entrypoint; LeLab service unchanged)
RELATIVE_START_FRESH_ORIGIN = PASS_FAKE
HISTORICAL_REFERENCE_BLOCKING = NO (quantized path only)
FIRST_GOAL_SKIPPED = PASS_FAKE
NO_RECONFIG_TEACHING_READY = PASS_FAKE_DRY_RUN_ONLY
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
TELEOP_ACTUAL_RUN = false
NEXT_LIVE_COMMAND = RUN SUPERVISED C APPROACH TEACHING
```

변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
