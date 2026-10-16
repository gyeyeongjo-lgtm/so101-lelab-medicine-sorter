# Relative-start fresh origin과 historical reference 분리 — 오프라인

사용자 지정 historical `REFERENCE_PRESENT=[2065,1467,2649,2497,1612,490]`은 변경하지 않았다. 직전 fresh read-only 3회 Present `[2065,1467,2649,2498,1612,490]`, Goal `[2065,1466,2649,2497,1611,490]`은 모두 동일하고 Moving 전 축 0, Torque 전 축 ON, Tmax `36°C`, Goal–Present 최대 1 raw였다. Wrist Flex는 historical reference 대비 `+1 raw`; 이는 현재 관측값이지 baseline/target/reference가 아니다. 세 표본은 약 0.45초 구간이므로 실제 3초 startup stillness 판정은 `NOT_RUN`이다.

소스 확인: `capture_origins(read_leader, read_follower_action)`는 3초 stillness 이후 현재 follower action을 읽고, `relative_target()`은 `origins.follower + (leader_now - origins.leader)`를 쓴다. historical reference는 제어 수학에 들어가지 않는다. 기존 no-reconfigure 진입점에는 별도의 quantized historical exact-match **사전 gate**가 있어 `2498`을 차단했다. 이번에는 그 값을 바꾸지 않고 `REFERENCE_EXACT_MATCH` 비교 결과로만 기록하도록 quantized 경로를 수정했다. exact-zero 정책의 기존 reference gate는 그대로다.

quantized 경로는 여전히 fresh pre-connect와 최초 post-connect raw Present/Goal 일치, Torque ON, Moving 0, Goal–Present ≤1 raw, 온도 gate, 3초 연속 Present/Goal 불변, leader 정지, follower calibrated bounds, fresh origin 직후 재확인 및 첫 Goal 생략을 요구한다. startup summary는 `REFERENCE_EXACT_MATCH`, `CURRENT_FRESH_STABILITY`, historical reference와의 raw delta를 별도 필드로 기록한다. `2498`을 새 상수·저장 baseline·target으로 쓰지 않는다.

로컬 fake에서 fresh Wrist Flex `2498`은 `REFERENCE_EXACT_MATCH=false`, `CURRENT_FRESH_STABILITY=true`로 기록되며 실제 상대 목표의 Wrist Flex가 fresh action origin에서 출발한다. pre-connect와 post-connect가 1 raw만 달라도 송신 전에 ABORT하는 회귀도 확인했다. 관련 `61/61 PASS`, compile·기본 dry-run·diff-check PASS. 기본 dry-run은 serial/Goal/Torque/config write `0`. Jetson 배치·실제 serial·teaching 재시도 `NOT_RUN`; motor/Goal/Torque/config write `0`.

```makefile
REFERENCE_EXACT_MATCH = false
CURRENT_FRESH_STABILITY = PASS_3_SAMPLES_ONLY / LIVE_3S_NOT_RUN
RELATIVE_START_USES_FRESH_ORIGIN = true
HISTORICAL_REFERENCE_REQUIRED_FOR_CONTROL = false
BASELINE_CHANGED = NO
MOTOR_COMMAND = 0
NEXT_LIVE_COMMAND = NONE
```

변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
