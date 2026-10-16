# CURRENT POSE HOLD RECOVERY 재시도 — Torque gate FAIL

사용자는 이전 fingertip/table 접촉이 풀렸고 팔을 지지한 채 정지·전체 비접촉이라고 재확인했다. 승인 범위는 fresh Present raw를 Goal raw에 1회 동기화하고 Torque OFF 상태에서 중단하는 것이며, Torque ON은 승인하지 않았다.

로컬 `tests.test_sync_follower_goal_to_present_only` 6/6 PASS. Jetson 격리 설치의 `sync_follower_goal_to_present_only.py`와 `so101_exclusive_bus.py` 및 read-only 도구 SHA가 로컬과 일치했다. LeLab teleoperation/recording/inference inactive, canonical follower `5AE6058306→/dev/ttyACM1`, leader `5AE6085272→/dev/ttyACM0`, privileged 양 포트 무점유를 확인했다.

사전 read-only 3회 동일: Present raw `[2065,1466,2649,2497,1611,490]`, arm degree `[-3.208791,-42.945055,+58.505495,+36.615385,-22.285714]`, gripper `4.712362%`, Goal raw 전 축 `0`, Torque 전 축 OFF, Moving 전 축 `0`, Tmax `36°C`. 직전 접촉 상태 표본과 자세가 달라졌으므로 해당 표본을 재사용하지 않았다.

승인된 Goal-only 도구를 한 번 실행했다. 출력은 `GOAL_PRESENT_SYNC_FAIL:RuntimeError:torque_not_all_off`; 자동 재시도하지 않았다. 도구는 Torque write 경로가 없지만 실패 출력에는 발생 단계와 Goal write count가 없다. 뒤이어 별도 쓰기 차단 read-only 3회에서 Goal raw = Present raw = `[2065,1466,2649,2497,1611,490]`, max raw diff `0`, Torque_Enable 전 축 `1`, Moving 전 축 `0`이었다. 관측된 온도 최대는 두 번째 표본의 gripper `48°C`이며 나머지 그리퍼 표본은 `36°C`였다. Goal이 0에서 현재 raw로 변했고 Torque가 OFF→ON으로 변했으나, 각각의 정확한 write 시점/주체는 이번 runner 출력만으로 확정하지 않는다. 특히 Torque ON은 요청·도구 코드 범위 밖이다.

사후 privileged 양 포트 무점유 확인 후 SSH 종료. 사용자가 **팔 지지·정지·전체 비접촉 유지**를 확인했다. 추가 Goal/Torque/motor write, 재시도, teaching, GRASP/LIFT는 `0`/`NOT_RUN`이다.

```ini
PHYSICAL_NON_CONTACT = HUMAN_CONFIRMED_PRE_AND_POST_RUN
FRESH_PRESENT = [2065,1466,2649,2497,1611,490] raw (3회 동일)
GOAL_SYNC = FAIL / NOT_ACCEPTED (torque_not_all_off)
MAX_GOAL_PRESENT_RAW_DIFF = 0 (post-run 3회)
TORQUE = ALL_ON (post-run 3회; actor UNKNOWN)
GOAL_WRITE = OBSERVED_GOAL_CHANGE; RUNNER_COUNT_NOT_RECORDED
TORQUE_WRITE_BY_THIS_RUNNER = 0 (code path)
NEXT_LIVE_COMMAND = NONE
```

원본 telemetry·비밀번호는 커밋하지 않는다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
