# 2026-10-17 실행 규칙·green pose·resume 티칭

## 변경 결과

```text
marker identity: ID7=C, ID8=B, ID9=A (unchanged)
destinations: red, blue, green
runtime syntax: --rule C=green B=red A=blue
pose count: 18
```

- A/B/C 각각에 red/blue/green 전부를 지정할 수 있다.
- 다른 약통을 같은 바구니에 지정할 수 있다.
- rule에 없는 약통은 인식되어도 `not_selected_by_rule`로 건너뛴다.
- A rule이 있으면 ID9도 계획과 재생에 포함된다.
- `--rule`이 없을 때만 config `destination_rules` default를 쓴다.
- 모르는 약통/색, `=`가 없는 token, 중복 약통 지정은 robot connect 전에
  fail-closed한다.
- `green_above`, `green_release`를 pose 목록에 추가했다.

## Jetson 재현 반영

```ini
MAX_VELOCITY_ALL = 20.0
MAX_ACCELERATION_ALL = 60.0
GRIPPER_SETTLE_TOLERANCE = 100.0
TEACH_GOAL_PRESENT_RAW_TOLERANCE = 40
POST_GOAL_DELAY_S = 0.2
POST_GOAL_READ_RETRY = 3
```

fresh Present raw→Goal raw write 후 Torque가 ALL ON으로 바뀌면
`AUTO_ENABLED_BY_GOAL`로 인정하고 별도 Torque ON을 쓰지 않는다. ALL OFF면
기존대로 Torque ON을 한 번 쓰고, mixed state는 중단한다. 이 변경은
과거 unknown writer를 숨기는 것이 아니라 사용자가 실제 Feetech에서 재현한
Goal-write auto-enable lifecycle을 명시적으로 처리한 것이다.

teach relative target이 calibration range를 벗어나면 세션을 종료하지 않고
해당 range의 양끝에서 1° 안쪽으로 clamp한다. 현재 clamp joint를 터미널에
표시한다.

## 재개 저장

18개 pose 중 Enter로 캡처한 각 pose를 즉시
`configs/fixed_demo_poses.partial.json`에 atomic replace로 저장한다. 중단되어도
이미 저장된 prefix는 유지된다. `teach --resume`은 follower serial, schema,
pose order, 관절 key를 검증한 후 첫 missing pose부터 이어간다. 18개가 완료되면
최종 `configs/fixed_demo_poses.json`을 쓰고 partial을 제거한다. 두 파일은
Git ignore 대상이다.

## 오프라인 검증

```text
fixed-demo tests = 27/27 PASS
existing sorter tests = 30/30 PASS
invalid rule CLI pre-camera rejection = PASS
Python compile = PASS
git diff --check = PASS
serial open = 0
Goal/Torque/config write = 0
motor command = 0
Jetson live = NOT_RUN
```

검증은 9개 label→color pair, same-basket multi-bottle, unspecified skip, A/ID9 route,
green stage, invalid rule, 18 pose, Goal auto-enable/Torque write 0, explicit Torque 1회 path,
post-Goal retry, calibration inner clamp, partial prefix load, dry-run hardware 0을 포함한다.
