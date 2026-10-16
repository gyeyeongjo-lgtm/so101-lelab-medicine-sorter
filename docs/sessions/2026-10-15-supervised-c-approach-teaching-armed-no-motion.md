# Supervised C approach teaching — 실기 gate PASS, 조작 없이 정상 종료

사용자의 `RUN SUPERVISED C APPROACH TEACHING` 승인과 현장 `모두 유지, 무장 안내 전 리더 정지` 확인을 받고 검증된 no-reconfigure 진입점을 1회 실행했다. Jetson canonical leader `/dev/ttyACM0=5AE6085272`, follower `/dev/ttyACM1=5AE6058306`, privileged 포트 무점유, LeLab 세 제어 inactive 및 진입점 SHA `3737e249…a1c96`을 확인했다.

사전 쓰기 차단 read-only 3회는 Present raw `[2065,1468,2649,2498,1612,490]`, Goal raw `[2065,1466,2649,2497,1611,490]`, Torque 전 축 ON, Moving 전 축 0, Tmax `36°C`, Present/Goal 불변이었다. 실제 양 포트 연결 뒤 PRE_ARM_SETTLE **17개 표본, 기록 시각 간격 3.061749817초**에서 Present drift 0, Goal 불변, 잔차 최대 2 raw, Torque/Moving/온도 조건을 통과했다. fresh leader/follower origin capture와 첫 Goal 생략 후 teaching/recorder를 무장했다. historical reference exact match는 false로 별도 기록했고 변경하지 않았다.

사용자가 `C APPROACH EMPIRICAL ALIGNED`를 입력해 해당 runner PTY에 SIGINT 1회를 보냈다. 정상 stop 후 follower read-only 3회 측정·파일 저장·두 포트 해제가 완료됐다. 결과는 `STOPPED`, `cycle_count=126`, `error_count=0`, `goal_sends=0`, `first_goal_skipped=true`, `final_read_only_samples=3`, `data_complete=true`다. 126개 표본의 첫/끝 간격은 `34.582571537초`, 모든 leader axis 및 follower raw span은 0이다.

결과를 대조해 물은 뒤 사용자는 **`조작하지 않았음 — 정렬 완료 입력은 실수`**라고 정정했다. 그러므로 이 trace는 무장 후 정지 기록이며 C approach 이동 성공이나 정렬 성공이 아니다. `C_APPROACH_EMPIRICAL`은 등록하지 않았고, 정상 종료 최종 측정만 보존했다. 최종 3회 Present는 시작과 동일, GRASP TCP `[23.139625640,-235.115385759,66.547496134] mm`, gripper encoder `4.712362301%`, Moving 전 축 0, Tmax `36°C`다. 실제 finger opening/C 정렬의 새 확인으로 해석하지 않는다.

원본은 Jetson `/home/jetson3/so101-current-hold-teaching-20261014/run-20261015-u5o9sK/`에 보존했다:

- `pre_connect.json`
- `trace/startup.jsonl`, `trace/startup_summary.json`
- `trace/cycles.jsonl`, `trace/requests.jsonl`, `trace/manifest.json`
- `trace/final_pose_3sample.json`

cycle SHA-256 `f4a1c00eca907633cf86b28f46d763142a45d4845878b5e0459610e32b8c713e`. one-shot ticket은 무장 시 정상 소비되어 존재하지 않는다. 종료 후 privileged `fuser rc=1`(양 포트 무점유), LeLab teleoperation/recording/inference inactive 확인. 실제 motor/Goal/Torque/config write `0`, 자동 재시도 `0`; calibration/reference 변경 없음.

```ini
PRE_ARM_HOLD_STABILITY = PASS_ACTUAL_SERIAL
TEACHING_SESSION = STOPPED_NORMALLY
TRAJECTORY_RECORD = SAVED_STATIONARY_126_CYCLES
FINAL_READ_ONLY_SAMPLES = 3_SAVED
C_APPROACH_EMPIRICAL = NOT_CONFIRMED_NOT_REGISTERED
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
AUTOMATIC_RETRY = 0
GRASP = NOT_RUN
LIFT = NOT_RUN
```

이번 세션은 종료했다. 새 사용자 실행 요청 전 재시작하지 않는다. 원본 trace/비밀번호는 커밋하지 않는다. 이번 문서 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정).
