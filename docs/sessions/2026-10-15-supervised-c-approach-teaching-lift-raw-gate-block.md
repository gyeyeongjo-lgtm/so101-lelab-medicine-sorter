# Supervised C approach teaching — Lift Goal–Present gate로 무장 전 중단

사용자 `RUN SUPERVISED C APPROACH TEACHING` 승인 후, 현장에서 팔 지지·follower/leader 정지·전체 비접촉·경로 clear·3초 리더 정지·즉시 중단 준비를 확인했다. 기존 safety gate나 reference는 변경하지 않았다.

Jetson canonical USB는 leader `/dev/ttyACM0=5AE6085272`, follower `/dev/ttyACM1=5AE6058306`였고, privileged `fuser` 무점유, LeLab teleoperation/recording/inference 모두 inactive였다. Jetson 격리 teaching entrypoint SHA `aa5cfeb6…74a3e1`, FK import 수정 SHA `ebc5d82c…ed4ff1`, 기존 쓰기 차단 read-only 도구 SHA `7c440b81…f3c56`을 확인했다.

기존 쓰기 차단 도구로 follower serial을 **read-only** 연결해 0.2초 간격 정확히 3회 측정했다. 3회 모두 Present raw `[2065,1468,2649,2498,1612,490]`, Goal raw `[2065,1466,2649,2497,1611,490]`, Torque 전 축 ON, Moving 전 축 0이었다. Present/Goal의 관측 중 drift는 없고 최고 온도는 `41°C`(첫 gripper 표본; 뒤 두 표본 `35/36°C`)였다. 그러나 Lift의 `abs(Goal−Present)=2 raw`로 기존 quantized startup 허용치 `1 raw`를 넘었다. Wrist Flex/Roll은 각 `1 raw`, 나머지 `0 raw`다.

따라서 사용자 조건의 fresh gate 실패로 **`ABORT_BEFORE_ARMING`**. 3초 PRE_ARM_SETTLE, leader 연결, fresh origin capture, recorder arm, teaching `--live`, one-shot ticket 생성, Goal/Torque/config/motor write는 하지 않았다. read-only 도구는 포트를 종료했고 종료 후 privileged `fuser` 무점유를 다시 확인했다. 물리 비접촉은 현장 사용자 확인이며 센서로 독립 검증한 값은 아니다.

```ini
TEACHING = ABORT_BEFORE_ARMING
BLOCKER = LIFT_GOAL_PRESENT_DIFF_2_RAW_EXCEEDS_EXISTING_1_RAW_GATE
PHYSICAL_NON_CONTACT = USER_CONFIRMED
PRESENT_DRIFT_DURING_3_SAMPLES = NO
TORQUE = ALL_ON
MOVING = ALL_0
TEMPERATURE_ABNORMAL = NO
PRE_ARM_SETTLE = NOT_RUN
RECORDER = NOT_ARMED
LEADER_PORT_OPEN = NO
FOLLOWER_PORT_OPEN = READ_ONLY_THEN_RELEASED
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
AUTOMATIC_RETRY = 0
GRASP = NOT_RUN
LIFT = NOT_RUN
NEXT_LIVE_COMMAND = NONE
```

원인 변경 또는 Goal 동기화는 요청 범위 밖이므로 수행하지 않았다. 이번 기록 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정).
