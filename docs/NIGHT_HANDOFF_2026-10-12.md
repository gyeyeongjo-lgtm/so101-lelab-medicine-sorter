# 2026-10-12 무인 야간 handoff

## 아침 한 줄 상태

`WRIST_DELAY_25`는 야간 전환 직전 실제 `PRE_APPROACH_PASS`를 달성했다. 다만 종료 시점의 현장 `STOPPED` 확인은 사용자가 떠난 뒤라 `physical_stop=NOT_VERIFIED`다. 아침 첫 행동은 **모션 재실행이 아니라 사람이 팔의 정지·현재 자세·비접촉을 확인하는 것**이다.

## 야간 안전 범위

- 무인 야간 모드 전환 뒤 실제 하드웨어 작업: **NONE**
- 실행하지 않은 것: motor motion, `send_action`, Goal/Torque 변경, teleop/replay/live approach, service restart, USB write, calibration 촬영, camera/robot 재배치
- 수행한 것: 로컬 로그·소스 분석, offline FK proxy, fake/unit test, dry-run, 문서화
- 실제 grasp/lift/place: `NOT_RUN`
- commit/push: `NOT_COMMITTED/NOT_PUSHED`

## 1. WRIST_DELAY_25 실제 결과와 추가 검증

야간 전환 직전 사용자의 승인으로 pre-approach만 1회 실행했다.

- fresh start: `[-7.252747, -38.989011, +57.274725, +68.791209, -7.604396]°`
- 71/71 waypoint 완료, skip/catch-up burst 없음
- 사용자 `APPROACH CONFIRMED`, 실행기 `PRE_APPROACH_PASS`
- final feedback−goal: Pan `-0.469°`, Lift `+0.668°`, Elbow `+1.177°`, Flex `+1.265°`, Roll `-0.141°`
- 전 축 기존 final tolerance `1.6°` 통과
- 원본 로그: `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_delayed_wrist_fresh5_attempt1.jsonl`

오프라인 재검산:

- 71회 `SEND`와 final stable-verification `PAUSE`
- config target과 실제 target 최대 차이 `0.0°`
- send 간격 `0.295–0.302 s`, median `0.298 s`
- 최대 target 변화율 `3.346°/s`, 전체 최대 joint step `0.991765°`
- servo bound 최소 여유 `29.824°`
- C XY 잔여 거리 `209.850 → 0.010 mm`, 전 구간 단조 감소
- minimum TCP Z `83.657 mm`

| 지점 | Lift / Elbow / Wrist (deg) | FK TCP XYZ (mm) | C XY 잔여 (mm) |
|---|---|---|---:|
| fresh | `-38.989 / 57.275 / 68.791` | `[-37.325,-86.998,98.217]` | 209.850 |
| WP 5 | `-34.623 / 52.390 / 68.791` | `[-39.281,-98.634,102.494]` | 198.064 |
| WP 21 | `-19.246 / 39.882 / 56.122` | `[-43.833,-153.604,97.833]` | 142.954 |
| WP 37 | `-3.869 / 27.374 / 43.454` | `[-51.612,-209.280,91.501]` | 86.738 |
| WP 53 | `+11.508 / 14.866 / 30.785` | `[-62.652,-261.802,83.657]` | 33.513 |
| WP 71 | `+11.508 / 14.866 / 12.933` | `[-62.643,-295.322,99.992]` | 0.010 |

이전 실측 Wrist stall은 target `(Lift -39.146, Elbow 56.069, Flex 68.576)`에서 Flex error/load `2.676°/136`이었다. 새 경로는 초반 5 waypoint에서 Wrist를 유지했고 load `0`, WP 6에서 Flex error/load `0.352°/32`였다. 전체 Elbow 최대 error/load는 `3.578°/176`, Wrist 최대는 `2.130°/112`; final Elbow/Wrist load는 `68/72`, Moving은 둘 다 0이었다. 이는 **실제 load simulation이 아니라 두 실측 로그의 비교**다.

## 2. Collision offline 검사

URDF에는 17개 collision element와 13종 STL 참조가 있지만 저장소에 STL 파일과 정확한 환경 geometry가 없어 full collision PASS는 낼 수 없다.

가능한 FK/skeleton proxy 결과:

- shoulder origin minimum Z `94.882 mm`
- upper arm `149.082 mm`
- lower arm `253.803 mm`
- wrist `198.536 mm`
- gripper origin `147.201 mm`
- TCP `83.657 mm`
- 비인접 centerline minimum distance `64.775 mm`
- 과거 table-contact TCP Z `54.659 mm`를 임시 평면으로 쓰면 TCP clearance proxy `28.998 mm`

계속 `NOT_VERIFIED`인 항목:

- full swept-link/environment collision
- mesh self/base collision
- 실제 finger/table clearance
- C와 주변 물체 clearance

## 3. 실패 시 fallback

모두 `DRY_RUN_ONLY/NOT_RUN`이며 실제 성공한 경로가 있으므로 지금 실행할 이유가 없다.

| 후보 | targets | max step | coupled Wrist step | min TCP Z | final Wrist-only |
|---|---:|---:|---:|---:|---:|
| delay20/rate0.75 | 71 | 0.961° | 0.792° | 85.327 mm | 15.318° |
| delay25/rate0.75 | 71 | 0.992° | 0.792° | 83.657 mm | 17.852° |
| delay30/rate0.75 | 75 | 0.977° | 0.792° | 82.211 mm | 20.386° |
| delay25/rate0.70 | 74 | 0.977° | 0.739° | 82.211 mm | 20.386° |

재현 시험에서 Wrist만 다시 실패할 때의 최소 fallback은 `delay25 + rate0.70`이다. Shoulder–Elbow coupling, endpoint, C XY, calibration, final tolerance는 바꾸지 않는다.

## 4. STS3215 추종 조사

설치 소스와 trace를 read-only로 확인했다.

- position mode
- P/I/D `16/0/32`
- `Maximum_Acceleration=254`, `Acceleration=254`
- speed/Goal_Velocity 명시 write 없음
- Elbow/Wrist별 torque/current limit 설정 없음
- deadband/compliance register read/write 없음
- autonomous transport는 configure를 다시 쓰지 않음
- `Present_Load`는 보정 토크 명령이 아니라 signed firmware telemetry
- `Moving=0`은 Goal 도달을 의미하지 않음

현재 live-retained register 값은 `NOT_VERIFIED`다. gain/torque 변경은 제안하거나 실행하지 않는다.

## 5. A/B/C identity 권장안

현재 모델은 3-class 분류기가 아니라 class 0 `white_medicine_bottle_model` 하나인 병 검출기다. detector dataset은 100장(train 71/val 18/test 11), label id는 전부 0이다. 사용자 후보 원본은 A 23/B 35/C 23, 총 81장이지만 클래스별 고정 슬롯에서 연속 촬영되어 위치 편향과 leakage가 있다.

외형상 A는 높이로 비교적 분리되지만 B/C bbox 크기 범위는 겹친다. 따라서 10/17까지의 권장안은 다음 하나다.

> 기존 1-class YOLO 유지 → detector ROI와 위치별 pixel-scale가 보정된 W/H/aspect/area 특징 → 경량 3-class identity head → confidence fail-closed

nearest-slot은 첫 C→RED의 임시 fallback/교차검사로만 두며 최종 9조합 identity로 인정하지 않는다. 내일 로봇을 움직이지 않고 A/B/C를 공통 3위치에 각각 5개 독립 자세/회전으로 놓아 최소 45장을 수집하고, 위치 block 단위 split과 한 위치 전체 holdout을 만든다. 기존 81장은 train 보조만 사용한다. 예상은 수집 30–45분, feature/model/offline test 2–4시간이다. 무인 야간에는 학습하지 않았다.

## 6. 바구니 일반화

확정된 신원은 `RED=ID4`, `GREEN=ID5`, `BLUE=ID6`이다. marker center는 opening center가 아니다.

아래 XY는 2026-10-08 저장 20-frame 묶음의 stale diagnostic이며 현재 pose로 승격하거나 place target으로 사용하면 안 된다. table scale `0.8941815921` 적용값이다.

| basket | marker | marker table XY corrected (mm) | opening offset | 상태 |
|---|---:|---|---|---|
| RED | 4 | `[248.017,120.846]` | raw `[-2.269,+98.737] mm` 추정치만 존재 | marker 안정, offset `NOT_VERIFIED` |
| GREEN | 5 | `[154.790,118.468]` | `MISSING` | opening pose `NOT_VERIFIED` |
| BLUE | 6 | `[55.357,118.891]` | `MISSING` | opening pose `NOT_VERIFIED` |

RED의 scale-corrected diagnostic opening은 `[245.988,209.135] mm`지만 사진 육안 추정치라 목표로 사용 금지다. 세 바구니 모두 opening center/yaw/height/robot XY/place path가 `NOT_VERIFIED`다.

내일 최소 측정:

1. 바구니 고정 뒤 fresh ceiling frame에서 ID0–6과 실제 색↔ID 확인
2. 각 바구니 marker center→내부 opening center의 table-axis `ΔX,ΔY` 측정
3. 세 바구니의 동일 규격/동일 yaw 여부 및 내부 L×W, rim height 확인
4. opening XY와 별도로 safe release Z와 gripper 외접 여유 확인

## 7. Generic PICK/PLACE 계약

```text
command
→ detect/select object
→ object robot XY
→ generic PICK(object_xy, object_profile)
→ select destination
→ basket robot XY
→ generic PLACE(basket_xy, basket_profile)
```

권장 상태기:

```text
IDLE → VISION_READY → PICK_PLAN_READY → PRE_APPROACH → APPROACH
→ GRASP → LIFT → DESTINATION_READY → TRANSPORT → PREPLACE
→ PLACE → RELEASE → RETREAT → COMPLETE
```

각 stage는 자동 진입하지 않고 fresh feedback, tracking, vision/현장 evidence gate를 통과해야 한다. 필수 fail-closed 상태는 `VISION_STALE`, `IDENTITY_AMBIGUOUS`, `TRANSFORM_UNVERIFIED`, `IK_UNSOLVED`, `COLLISION_NOT_VERIFIED`, `BUS_OWNERSHIP_CONFLICT`, `TRACKING_LIMIT`, `GRASP_UNVERIFIED`, `OBJECT_LOST`, `BASKET_POSE_UNVERIFIED`, `RELEASE_UNVERIFIED`, `STOP_NOT_VERIFIED`, `COMM_ERROR`다. C→RED 성공 전 production refactor는 하지 않는다.

## 8. Command parser

offline parser는 다음 canonical 결과를 낸다.

```json
{"object":"C","destination":"RED"}
```

`A를 파란 바구니에 넣어`, `C를 빨강 바구니에 옮겨`를 포함해 A/B/C × RED/GREEN/BLUE 9개 조합 unit test가 통과했다. 기존 fixed-slot parser 9조합 회귀도 통과했다. 로봇 실행에는 연결하지 않았다.

## 9. 현장 go/no-go checklist

| Phase | 성공 기준 | 실패 시 확인 | 허용되는 최소 수정 | 다음 단계 |
|---|---|---|---|---|
| 0. 현장 복구 | 사람이 팔 정지·현재 자세·비접촉 확인, `physical_stop` 복구 | 지지 상태, 주변 간섭, unexpected motion | 자세/현장만 안전화; 자동 재실행 금지 | fresh pose/제어 비활성/버스 단일 소유 확인 |
| 1. Pre-approach 상태 확인 | 기존 `PRE_APPROACH_PASS` 위치가 안전하고 fresh feedback 정상 | final target/feedback, tracking, port owner | 필요할 때만 별도 승인으로 WRIST_DELAY_25 재시험 | approach 승인 요청 |
| 2. Approach | 기존 C XY의 approach endpoint 도달·stable feedback | joint errors/load/Moving, C freshness | 동일 path 내 최소 schedule 조정 | grasp 승인 요청 |
| 3. Grasp | gripper close 후 C 확보가 영상/feedback으로 확인 | grip position, object shift/loss | close target/settle만 한 변수씩 | lift 승인 요청 |
| 4. Lift | C가 유지된 채 검증 Z 도달 | object loss, collision proxy, tracking | lift height/schedule 한 변수 | RED opening 확인 |
| 5. RED opening | fresh ID4, 실측 opening offset/height/clearance 검증 | marker freshness, basket yaw/geometry | opening offset/height 측정만 | transport 승인 요청 |
| 6. Transport/place | preplace→place→release→retreat 각 gate 통과 | object/basket pose, release evidence, tracking | 실패 stage 한 변수만 | `C→RED COMPLETE` |

Phase 0가 확인되기 전에는 어떤 모션도 시작하지 않는다. 기존 pre-approach를 자동 반복하지 않는다.

## 10. 10/17 critical path

- **10/12:** physical stop 복구 → fresh pose → C approach → grasp → lift → RED opening 실측
- **10/13:** C→RED 전체 사이클 1회 성공
- **10/14:** generic PICK/PLACE 추출, 3 basket destination 등록
- **10/15:** A/B/C identity 일반화, 9 command software integration
- **10/16:** 실제 조합 반복 시험, 실패율 개선, rehearsal
- **10/17:** 시연

Critical path:

```text
physical stop 복구
→ approach/grasp/lift
→ RED opening 검증
→ C→RED 전체 성공
→ generic화
→ A/B/C identity + 3 baskets
→ 9조합 시험
```

## 11. 야간 검증과 저장소 상태

- 핵심 path/runner/parser 회귀: `55/55 PASS`
- OpenCV가 필요한 7개 vision/calibration 모듈은 `lerobot` 환경에서 별도 실행: `41/41 PASS`
- 관련 Python 파일 `py_compile`: `PASS`
- `git diff --check`: `PASS`
- 전체 discovery는 기본/번들 Python의 `cv2`·`websocket` 부재와 샌드박스의 localhost bind 금지 때문에 clean run이 아니었다. discovery 자체는 309개를 통과했고 12개 collection/bind error를 냈다. 이 중 `cv2` 관련 7개 모듈은 위 41개 별도 실행으로 해소했다. `websocket` 의존 모듈과 localhost server bind가 필요한 4개 test는 이 환경에서 `NOT_RUN`; 제품 실패로 재분류하지 않는다.
- 기존 사용자 변경을 포함한 dirty worktree를 그대로 보존했다. commit/push하지 않았다.
