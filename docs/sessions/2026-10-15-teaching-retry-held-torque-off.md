# Teaching 재실행 요청 — fresh Torque OFF / Goal 0로 무장 전 중단

사용자 `다시 해봐` 요청으로 기존 no-reconfigure teaching 재실행 준비를 시작했다. 준비 중 `왜 제한이 걸려 있고 풀 수 없는가` 질문에는 기존 2°가 관절 최대각이 아니라 **한 번 송신하는 arm target의 변화량 제한**이고, 직전 Elbow −3.956° 요청이 그 제한을 넘었다고 설명했다. 큰 입력을 나눠 따라가는 방식을 대안으로 설명했지만 이번 턴에는 구현/배치 또는 제한 해제를 하지 않았다.

Jetson 설치본 SHA, canonical leader/follower, LeLab teleoperation/recording/inference inactive, privileged 양 포트 무점유를 확인했다. 기존 쓰기 차단 follower 도구로 0.2초 간격 3회 read-only 측정했다. 세 표본의 Present/Goal/Torque/Moving은 모두 동일했다.

```text
joint order = Pan / Lift / Elbow / Flex / Roll / Gripper
Present raw = [2066,1098,2901,2503,1612,490]
Present deg/% = [-3.120879121,-75.296703297,+80.659340659,+37.142857143,-22.197802198,4.712362301]
Goal raw = [0,0,0,0,0,0]
Torque = [0,0,0,0,0,0]
Moving = [0,0,0,0,0,0]
Tmax = 37 degC
Present span during 3 samples = all 0 raw
```

직전 실행 후와 비교해 Lift raw `1468→1098`, Elbow `2649→2901` 등 자세가 바뀌고 Torque는 ON→OFF, Goal은 전 축 0이었다. 사용자는 **`지지·정지·비접촉, 의도한 변경`**이라고 현장 확인했다. 따라서 상태 변경 원인을 추가 추적하지 않았다.

요청된 startup 조건 Torque all ON과 bounded Goal–Present를 만족하지 못해 `ABORT_BEFORE_ARMING`이다. live runner, leader 연결, one-shot ticket 생성, 3초 PRE_ARM_SETTLE, recorder arm을 시작하지 않았다. motor/Goal/Torque/config write `0`. Goal sync나 Torque toggle은 하지 않았고 자동 재시도 없다. raw 3회 기록은 Jetson `/home/jetson3/so101-current-hold-teaching-20261014/run-20261015-R1BPXK/pre_connect.json`에 보존했다. 종료 후 privileged `fuser rc=1`, LeLab 세 제어 inactive 확인.

```ini
TEACHING = ABORT_BEFORE_ARMING
BLOCKER = TORQUE_ALL_OFF_AND_GOAL_ALL_ZERO
PHYSICAL = SUPPORTED_STOPPED_NON_CONTACT_USER_CONFIRMED
STATE_CHANGE = USER_INTENDED
PRE_ARM_SETTLE = NOT_RUN
RECORDER = NOT_ARMED
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
GRASP = NOT_RUN
LIFT = NOT_RUN
NEXT_LIVE_COMMAND = NONE
```

기존 2° guard·calibration·historical reference·trajectory tolerance는 변경하지 않았다. 문서 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정). 원본 로그/비밀번호는 커밋하지 않는다.
