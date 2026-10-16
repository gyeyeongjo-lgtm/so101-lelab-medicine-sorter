# HOLD_STABLE_QUANTIZED 오프라인 판정

기존 `CURRENT_HOLD_STABLE=false`와 `Goal−Present=0 raw` 기준은 유지한다. 이전 read-only 기록의 6개 표본(약 21.79초)은 모두 Present raw `[2065,1467,2649,2497,1612,490]`, Goal raw `[2065,1466,2649,2497,1611,490]`, Moving 전 축 `0`, Torque 전 축 ON, 최고 온도 `36°C`였다. Present/Goal drift가 없고 Lift/Roll의 차이가 각 `1 raw`라 별도 `HOLD_STABLE_QUANTIZED=PASS`다. 원본 telemetry를 새로 읽은 것이 아니라 기존 세션에 기록된 6개 표본 요약에 적용한 판정이다. 현장 지지·정지·전체 비접촉 확인도 기존 기록에 의존한다.

독립 판정 함수는 최소 2개 연속 표본의 축 집합, Present/Goal 불변, Moving 전 축 0, Goal–Present 절댓값 전 축 `≤1 raw`, 온도 `0..55°C`를 검사한다. 기존 exact-zero 상수는 변경하지 않았다. teaching 진입점은 정책을 명시적으로 `quantized`로 선택할 때만 별도 기준 pose와 3초 startup 표본 판정을 사용한다. 기존 `exact_zero` 호출은 1 raw 차이를 계속 거부한다. 송신 전 Torque 전 축 ON, reference pose/Goal 일치, fresh pre-connect 일치, 3초 무이동, leader 정지와 기존 guard도 유지된다. 실제 관측값이 바뀌면 fail-closed다.

요청한 fake 사례 `stable+0`, `stable+1` PASS; `stable+2`, Moving=1, Present drift, Goal drift FAIL. 추가 6개 기록 요약 PASS, 온도 fault FAIL, exact-zero 보존 테스트 PASS. 관련 로컬 회귀 `58/58 PASS`, compile·기본 dry-run·diff-check PASS. 기본 dry-run 출력은 `serial_open=0`, `goal_write=0`, `torque_write=0`, `config_write=0`이다. Jetson 배치·실제 serial·teaching은 이번 범위에서 `NOT_RUN`; MOTOR_COMMAND/CONFIG_WRITE/TORQUE_WRITE `0`.

다음 승인 문구 후보는 `RUN SUPERVISED C APPROACH TEACHING` 하나다. 이는 **실행 완료 또는 Jetson 설치본 반영 확인이 아니다**. 실제 실행 전 코드 배치 일치, fresh read-only 상태, 현장 비접촉과 독점 포트, 새 ticket 등 기존 live gate를 다시 확인해야 한다. GRASP/LIFT는 `NOT_RUN`. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
