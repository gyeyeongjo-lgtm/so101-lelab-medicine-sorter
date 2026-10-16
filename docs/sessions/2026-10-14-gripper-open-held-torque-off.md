# C approach teaching 전 그리퍼 재개방 — Torque OFF로 실행 보류

## 목적과 현장 확인

사용자는 닫힌 그리퍼를 이전에 현장에서 수용한 opening까지만 열고자 했다. 이전 수용 시점의 Gripper Present는 `34.577723%`, Goal은 raw `985`였다. `36%` 추가 개방은 취소된 상태다. 사용자는 finger opening 전체 경로가 비접촉이라고 확인했다. 과거 encoder 값이 변해도 실제 손가락이 움직이지 않았으므로, 향후 물리적 개방은 현장 육안 확인이 필요하다.

읽기 전용 측정 후 사용자에게 재확인한 결과, 현재 팔·그리퍼는 정지·비접촉이며 Torque OFF와 Lift/Elbow를 포함한 자세 변경은 현장에서 **의도적으로 만든 상태**다. 이는 토크 재인가, Goal write, gripper 개방 또는 teaching 재시작 승인이 아니다.

## 이번 read-only 결과

Jetson LeLab의 teleoperation/recording/inference는 모두 inactive였다. canonical follower `/dev/ttyACM1=5AE6058306`의 제어 포트는 점유되지 않았다. 쓰기 API를 차단한 상태에서 follower를 3회 읽었으며 세 결과는 동일했다.

| 항목 | 측정 결과 |
| --- | --- |
| Arm Present (Pan/Lift/Elbow/Flex/Roll) | `[-6.109890, -27.472527, +67.560440, +27.736264, -22.197802]°` |
| Gripper Present | `4.712362%`, raw `490` |
| Goal | 전 축 raw `0` |
| Torque_Enable | 전 축 `0` |
| Moving | 전 축 `0` |
| 최고 Temperature | `38°C` |

읽기 종료 후 SSH 세션을 닫았고 follower 포트가 무점유임을 확인했다. 이번 측정은 register 상태 확인이며 실제 손가락 벌어짐의 물리적 측정은 아니다. 마지막 teaching attempt1 종료 자세와 비교하면 Lift/Elbow 등 현 arm 자세가 크게 달라졌으나, 사용자가 의도한 변경이라고 확인했다.

## 판정 및 재개 조건

현재 Goal raw가 전 축 `0`이므로 토크를 바로 재인가하면 예상하지 않은 동작 위험을 배제할 수 없다. 과거 arm 시작 자세와 C 경로에 결합된 기존 gripper-open runner의 gate를 우회하거나 그대로 재실행하지 않는다. 현 자세에서 팔 지지, Goal/Present 동기화 및 축별 토크 재인가 범위를 검증하고 별도 사용자 승인을 받은 뒤에만 다음 live action을 정한다.

이번 턴 gripper target/arm target/Goal write/Torque write/motor command `0`; teleop/teaching/실제 `PRE_ARM_SETTLE` `NOT_RUN`, GRASP/LIFT `NOT_RUN`. 원본 로그·비밀번호·키는 커밋하지 않았다. 이번 변경 `NOT_COMMITTED/NOT_PUSHED`; 이슈 갱신 `NOT_RUN`(대상 미지정).
