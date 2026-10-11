# 2026-10-17 약통 자동 분류·Pick-and-Place 목표

## 최종 목표

2026-10-17까지 시스템은 약통 `A/B/C`를 구별하고 사용자가 지정한 `RED/GREEN/BLUE` 바구니로 자동 pick-and-place할 수 있어야 한다.

지원해야 하는 조합은 다음 9개다.

```text
PICK(A|B|C) × PLACE(RED|GREEN|BLUE)
```

`C → RED`는 첫 end-to-end validation case이며 최종 시스템의 고정 route가 아니다.

## 고정 파이프라인 계약

```text
detect/select object
  → object robot XY
  → generic PICK(object_xy, pick_profile)
  → select destination basket
  → basket robot XY
  → generic PLACE(basket_xy, place_profile)
```

- object identity와 destination identity는 motion 함수 밖에서 결정한다.
- PICK은 `object_xy`를 입력받으며 `A/B/C` 문자열로 관절값이나 trajectory를 분기하지 않는다.
- PLACE는 `basket_xy`를 입력받으며 `RED/GREEN/BLUE` 문자열로 관절값이나 trajectory를 분기하지 않는다.
- identity별 차이가 실제로 필요한 경우 좌표·검증된 profile 데이터로 주입하며 전용 함수나 숨은 상수로 넣지 않는다.
- IK, bounded interpolation, feedback/tolerance, stop 처리는 대상 identity와 무관한 공통 구현을 사용한다.
- perception 결과, table→robot transform, TCP, object/basket pose의 출처와 freshness를 plan에 명시한다.

## 현재 단계

현재 단기 목표는 `C → RED` 전체 자동 사이클 1회 성공이다. 이 성공 전에는 A/B 또는 다른 바구니 실기 작업으로 분산하지 않는다.

2026-10-11 야간 전환 직전 `WRIST_DELAY_25` 실제 pre-approach가 71/71 waypoint와 final 전 축 `1.6°` tolerance를 통과했고 사용자의 `APPROACH CONFIRMED` 뒤 실행기가 `PRE_APPROACH_PASS`를 출력했다. grasp/lift는 `NOT_RUN`이다. 종료 시점은 사용자 퇴근 뒤여서 현장 `STOPPED`를 확인하지 못했고 `physical_stop=NOT_VERIFIED`다. 다음 현장 첫 행동은 자동 재실행이 아니라 사람이 팔의 정지·현재 자세·비접촉을 확인하는 것이다.

현재의 `scripts/live_c_approach.py`, `scripts/prepare_c_red_phases.py`, `configs/c_red_*`는 C→RED 첫 검증을 위한 제한된 하네스/과거 후보다. 이 파일을 최종 9조합 planner API로 간주하거나 C/RED 상수를 공통 motion 경로에 복사하지 않는다.

공통 기반으로 재사용 가능한 현재 요소:

- `scripts/medicine_fixed_slot_command.py`: A/B/C와 red/green/blue 명령 해석
- `scripts/staged_cycle_execution.py`: identity 비의존 stage/feedback/stop 상태기
- table→robot transform, pivot TCP, bounded waypoint 및 follower transport의 검증된 공통 부분

아직 공통 생산 경로로 구현·검증되지 않은 부분:

- `object_xy` 입력 기반 generic PICK plan 생성
- `basket_xy` 입력 기반 generic PLACE plan 생성
- 동일 plan schema에서 pick/place IK와 phase 실행 연결
- basket opening 좌표와 release/retreat 높이의 독립 검증
- A/B/C identity: 현재 YOLO는 단일 bottle class이며 nearest-slot은 임시 fallback일 뿐이다
- RED/GREEN/BLUE opening pose: 색↔marker ID만 확정됐고 opening center/yaw/height는 미검증이다

## 단계 순서

1. C → RED 전체 자동 사이클 1회 성공
2. A/B/C identity 일반화
3. RED/GREEN/BLUE basket pose 등록
4. 9개 명령 조합 시험

## 현재 안전 상태

- 이 목표 고정 자체는 모터 동작 승인이 아니다.
- pre-approach 이외의 실제 approach/grasp/lift/place, torque 변경, teleop 시작은 별도 현장 확인과 명시 승인 전 `NOT_RUN`이다.
- 무인 야간 모드 전환 뒤 실제 하드웨어 작업은 `NONE`; commit/push는 `NOT_COMMITTED/NOT_PUSHED`다.
- full swept-link/environment collision, 실제 finger/table/C clearance는 `NOT_VERIFIED`다.
- 상세 아침 인계는 [NIGHT_HANDOFF_2026-10-12.md](NIGHT_HANDOFF_2026-10-12.md)를 따른다.
