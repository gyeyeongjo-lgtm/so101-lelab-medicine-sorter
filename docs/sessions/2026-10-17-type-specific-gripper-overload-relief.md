# 2026-10-17 약통 종류별 그리퍼·Overload 완화

## 실제 실패 기록

- 사용자가 Jetson에서 `run --step`을 실행했다.
- 큰 약통 A는 `slot1_lift`까지 실제 성공했다.
- 이후 `blue_above` 이동 중 gripper motor ID 6이
  `[RxPacketError] Overload error!`로 중단됐다.
- 기존 작은 약통 기준 `gripper_closed` Goal이 큰 약통을 계속 미는 문제가 원인으로
  판단됐으며, 이 기록을 데모 완료로 표현하지 않는다.

## 변경

- pose 파일 호환용 기본 18개는 유지하고 다음 세 자세를 추가했다.

```text
gripper_closed_A
gripper_closed_B
gripper_closed_C
```

- run의 닫기 단계는 인식된 A/B/C에 맞는 자세의 gripper 값만 사용한다.
- `teach --only ...`는 완성된 기본 18-pose 파일을 읽고 지정 자세만 추가·덮어쓰며,
  선택 자세를 Enter로 저장할 때마다 같은 최종 JSON을 atomic replace한다. 지정하지
  않은 기존 자세는 보존한다. 잘못된 이름·중복·`--resume/--overwrite` 충돌은
  hardware session 생성 전에 차단한다.
- `gripper_closed_A/B/C` 후 Moving=0일 때 actual gripper가 원 목표에서 2 pp보다
  많이 남은 채 정지했다면 접촉 정지로 처리한다. 원 목표로 계속 누르지 않고 fresh
  actual에서 닫는 방향 1 pp만 더한 Goal로 재고정하고, 이후 arm-only stage에서도
  이 완화된 gripper Goal을 유지한다.
- servo read 오류는 motor name/ID, register, 원문, status와 SDK status bit를
  구조화한다. 확인한 매핑은 Overload=32, Overheat=4, Over-current=8,
  voltage=1, angle sensor=2다. status packet 오류에는 register 값이 없으므로
  임의 값을 만들지 않고 `register_value=null`, `servo_status_value=<bit>`로 남긴다.
- `Present_Temperature` read가 ID 6 Overload를 반환해도 generic temperature read
  failure로 덮지 않는다. 정상 read된 실제 온도가 55°C를 넘으면 motor ID와 온도값,
  limit를 보고한다.
- motion fault에서는 후속 stage를 실행하지 않고 fresh Present raw→Goal raw current
  HOLD를 한 번 요청한다. HOLD 자체가 실패하면 원래 fault와 hold error를 함께 보존한다.
- 현장 재현값대로 arm 5축 settle tolerance를 5.0°, gripper를 100.0 pp,
  settle timeout을 8.0 s로 반영했다.

## 오프라인 검증

```text
fixed-demo tests = 41/41 PASS
sorter tests = 30/30 PASS
Python compile = PASS
git diff --check = PASS
hardware serial open = 0
motor command = 0
Jetson live retry = NOT_RUN
```

검증 범위에는 18개 기본 pose 보존, 선택 3-pose 저장, A/B/C별 stage·값 선택,
접촉 정지 후 actual 근처 re-anchor, ID6 Overload 원문/status value 32 보존,
온도 61°C의 motor ID/value 보고, fault current HOLD 1회가 포함된다.

전체 legacy discovery는 현재 Mac 기본 Python에 `cv2`가 없어 8 errors가 있고,
기존 continuous-following timing 2 failures와 과거 600 mm marker 기준 1 failure가
남아 있어 전체 PASS로 표현하지 않는다. 이번 변경의 focused test와 sorter test는
각각 독립적으로 PASS했다.

## 다음 실기

- 실제 Overload 해제, gripper 냉각, 팔 지지·주변 비접촉을 먼저 현장에서 확인한다.
- 새 커밋을 pull한 뒤 `teach --only gripper_closed_A gripper_closed_B
  gripper_closed_C`로 세 값만 저장한다.
- 그 뒤 같은 감독 `run --step --rule C=green B=red A=blue`을 사용자가 직접
  실행한다. 자동 재실행은 하지 않았다.
