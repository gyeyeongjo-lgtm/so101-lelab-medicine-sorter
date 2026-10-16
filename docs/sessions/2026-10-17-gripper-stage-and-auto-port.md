# 2026-10-17 그리퍼 단계 분리·USB serial 포트 자동 선택

## 수정 결과

- 실행 자세를 두 종류로 분리했다.
  - `gripper_open`, `gripper_closed`: 팔 5축은 현재 값을 유지하고 그리퍼만 재생
  - `home`, `slot*_pre/grasp/lift`, `*_above/release`: 티칭한 팔 5축만 재생하고
    현재 그리퍼 값을 유지
- 한 약통의 순서는 아래와 같다.

```text
home → gripper_open → slot_pre → slot_grasp → gripper_closed → slot_lift
→ basket_above → basket_release → gripper_open → basket_above → home
```

- 약통이 여러 개면 위 11단계를 약통마다 반복한다. 따라서 각 약통의 첫 접근 전에
  명시적인 `gripper_open`이 다시 실행된다.
- 티칭 터미널은 `gripper_open/gripper_closed`만 그리퍼 값이 의미 있으며 나머지는
  팔 5축만 재생한다고 안내한다.

## USB 역할 자동 선택

- 저장된 순간 포트 번호가 아니라 config의 stable serial을 사용한다.
  - follower: `5AE6058306`
  - leader: `5AE6085272`
- connect 전에 `/dev/ttyACM*`만 열거하고 각 sysfs serial을 읽어 두 역할을 유일하게
  해석한다. 번호가 ACM0/ACM1 사이에서 바뀌어도 현재 serial에 맞는 포트를 사용한다.
- follower 또는 leader를 찾지 못하거나, 같은 serial을 두 역할에 설정했거나, 같은
  serial이 여러 tty에 나타나면 LeRobot 객체 생성과 serial open 전에 중단한다.
- sudo, lsof, fuser, process kill은 추가하지 않았다. 기존 process lock과 실제 열린
  FD의 `TIOCEXCL`, `disconnect(disable_torque=False)`는 유지한다.

## 오프라인 검증

```text
fixed-demo tests = 32/32 PASS
existing sorter tests = 30/30 PASS
Python compile = PASS
git diff --check = PASS
serial open = 0
Goal/Torque/config write = 0
motor command = 0
Jetson live = NOT_RUN
```

추가 검사는 arm-only 자세의 gripper 보존, open/closed만 gripper 변경, red/blue/green
3개 경로의 동일 11단계 반복, ACM 번호와 무관한 serial 역할 선택, serial 누락·충돌·
중복의 연결 전 거부를 포함한다.

## 남은 실제 단계

- Jetson에서 새 commit을 pull하는 작업: `NOT_RUN`
- 18개 pose 실제 티칭: `NOT_RUN`
- Astra 1-frame dry-run으로 ID→slot→destination 대조: `NOT_RUN`
- `run --step` 실제 모터 데모: `NOT_RUN`

실제 장비 명령은 사용자가 Jetson에서 현장 안전을 확인한 뒤 직접 실행한다.
