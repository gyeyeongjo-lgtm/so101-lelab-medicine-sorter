# Jitter live A/B fresh-state precheck blocked

일자: 2026-10-27

## 승인 및 범위

- canonical follower: `/dev/ttyACM0`, USB serial `5AE6058306`
- read-only `robot-status`: 정확히 1회
- Goal/Torque/config write와 motor motion: 금지
- fresh 상태 확인 뒤 endpoint 하나를 사용자에게 먼저 제시하고, A와 B는 자동으로
  연속 실행하지 않는 조건

## 실행 전 확인

- Jetson checkout: `304bc3bae54ffa688d7f6c68764e52ea687e8dc9`
- `/dev/ttyACM0`: `5AE6058306` (follower)
- `/dev/ttyACM1`: `5AE6085272` (leader)
- 저장 config는 순간 포트가 반대로 기록돼 있었다. 원본 설정은 수정하지 않고
  `/tmp/medicine-sorter-jitter-status.json` 사본에서만 실제 serial 역할과 맞췄다.
- 확인한 process 목록에는 medicine_sorter/lerobot/teleop/record/inference 실행이
  나타나지 않았다. adapter의 process lock, canonical serial 확인, ownership 확인,
  serial `TIOCEXCL` 계약은 그대로 사용했다.

## 최초 결과

write firewall 설치와 `bus.connect(handshake=False)` 이후 첫 raw register read에서
즉시 실패했다.

```text
error = robot_status_read_failed
register = Goal_Position
motor_id = 1
retry = 0
driver_error = There is no status packet!
```

30개 상태값을 완성하지 못했으므로 일부 값을 정상 snapshot으로 취급하지 않는다.
승인된 중단 조건에 따라 자동·수동 재시도, 다른 포트, 대체 read 경로, endpoint
선정 및 motor motion은 수행하지 않았다.

## 안전 결과

```makefile
ROBOT_STATUS_TEST = FAIL
RETRY = 0
STATE_CHANGE_WRITE = 0
MOTOR_COMMAND = 0
ORIGINAL_MOTION = NOT_RUN
SMOOTH_MOTION = NOT_RUN
FREE_SPACE_TEST_POSES = NOT_SELECTED_FRESH_STATE_UNAVAILABLE
READY_FOR_SMOOTH_MOTION_TEST = NO
```

write 0 근거는 `SO101ReadOnlyStatusAdapter`가 bus의 `write`, `sync_write`,
`enable_torque`, `disable_torque`를 상태 변경 차단 함수로 교체한 뒤 read를 수행하는
구조다. 종료 경로는 `disconnect(disable_torque=False)`이며 Torque OFF를 요청하지
않는다.

## 남은 사항

motor ID 1이 응답하지 않은 원인(전원·케이블·bus 상태)을 현장에서 확인해야 한다.
fresh 5-register snapshot을 완성하기 전에는 현재 pose나 짧은 free-space endpoint를
추정하지 않는다. 다음 장비 read 또는 motion에는 새 승인이 필요하다.

## 현장 재확인 후 motor bus 진단

사용자가 follower 전원·USB·motor bus 케이블을 현장에서 다시 확인하고,
`/dev/ttyACM0`, serial `5AE6058306`의 write 차단 read-only bus diagnostic 1회를
별도로 승인했다. 한 serial session에서 ID별 `Present_Position`을 retry 0으로 한 번씩
독립 read했으며, 실패가 있더라도 다음 ID를 확인하는 방식으로 수행했다.

```ini
FOLLOWER_PORT = /dev/ttyACM0
MOTOR_BUS = RESPONDS
ID1 = RESPONDS
ID2 = RESPONDS
ID3 = RESPONDS
ID4 = RESPONDS
ID5 = RESPONDS
ID6 = RESPONDS
MOTOR_COMMAND = 0
READY_FOR_ROBOT_STATUS = YES
```

이 진단은 Goal/Torque/config write와 motion을 수행하지 않았다.

## Full robot-status 1회

추가 승인 후 동일 canonical follower에서 write 차단 `robot-status`를 정확히 1회
실행했다. 6개 motor의 Present, Goal, Torque, Moving, Temperature 총 30개 raw read가
완료됐다.

```ini
ROBOT_STATUS = PASS
PRESENT_RAW = [1981,820,3078,2628,1611,1090]
GOAL_RAW = [0,0,0,0,0,0]
TORQUE = [0,0,0,0,0,0]
MOVING = [0,0,0,0,0,0]
TEMPERATURE_C = [27,27,27,26,26,30]
STATE_CHANGE_WRITE = 0
```

현재 raw pose와 저장된 pose의 `present_raw`를 장치 없이 비교하면 `finish`가 가장
가깝다. current−finish arm raw 차이는 `[7,5,-3,37,-2]`이고 현재 calibration scale
기준 최대 차이는 wrist_flex 약 3.25°다. 따라서 direct short endpoint 후보는
`finish` 하나지만, 기존 `motion-test`가 요구하는 named start pose 각 1° 이내 조건은
충족하지 않는다. 임의로 gate를 완화하거나 reposition하지 않았으며
`READY_FOR_ORIGINAL_TEST=NO`다. original/smooth motion은 모두 `NOT_RUN`이다.

## ORIGINAL 실행 판정 정정

승인된 current→finish ORIGINAL 한 구간은 command 6회를 전송하고 프로그램상
COMPLETE를 반환했으나, 사용자가 촬영·현장 관찰로 외부 로봇 링크가 물리적으로 전혀
움직이지 않았다고 확인했다. 따라서 `ORIGINAL_TEST=PASS`를 취소하고
`FAIL_NO_PHYSICAL_MOTION`으로 정정한다. SMOOTH는 실행하지 않았다.

원본 JSONL의 첫/마지막 cycle을 분리 분석한 결과는 다음과 같다(관절 순서는
shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper).

```text
Present start = [-10.681319,-99.648352,96.219780,48.131868,-22.285714,41.432069]
Present final = [-10.945055,-99.560440,96.219780,46.197802,-22.109890,41.432069]
Present delta = [-0.263736,+0.087912,0,-1.934066,+0.175824,0]

Goal start(log cycle 1) = [-10.769231,-99.736264,96.219780,47.868132,-22.285714,41.432069]
Goal final             = [-11.208791,-100.175824,96.483516,44.879121,-22.109890,41.432069]
Goal delta             = [-0.439560,-0.439560,+0.263736,-2.989011,+0.175824,0]

max command step = [0.126984,0.126984,0.063492,0.783069,0.042328,0]
max Present step = [0.263736,0.087912,0,0.703297,0.175824,0]
```

Wrist Flex의 fresh start→finish 요청은 `-3.252747°`(37 raw count), 첫 logged Goal→final
Goal은 `-2.989011°`(34 count), logged Present start→final은 `-1.934066°`(22 count)다.
기존 arm encoder 한 count는 약 `0.087912°`이므로 encoder 변화 자체는 측정 가능 범위를
넘는다. 그러나 이는 servo 내부 encoder의 변화이며 사용자 관찰상 외부 링크 운동은
없었다. mechanical transmission/backlash/coupling 또는 육안에 작은 운동 등 원인은
현재 로그만으로 확정하지 않는다.

JSONL schema v2에는 cycle별 Torque가 없다. hold 안정성 30 sample과 segment 종료
검사에서는 ALL ON이었지만 6개 command cycle 각각의 Torque를 소급 생성하지 않는다.
Moving은 cycle별로 일부 arm joint에서 모두 1이었고 gripper는 모두 0이었다.

false positive 원인은 완료 판정이 Goal write 성공 후 `Moving=0` 및 arm별 5° settle
tolerance만 확인했기 때문이다. 외부 링크 운동 증거를 포함하지 않았고, 마지막 logged
Wrist Flex Goal-Present도 `-1.318681°`였지만 5° 안이라 허용됐다. 앞으로 encoder raw
변화와 외부 영상/관찰을 분리하고, cycle별 raw Goal/Present/Torque를 기록한 뒤에만
motion 성공을 판정한다. 추가 motor write와 SMOOTH는 수행하지 않는다.
