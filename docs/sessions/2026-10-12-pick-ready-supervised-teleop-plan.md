# 2026-10-12 PICK_READY/VISION_READY supervised teleop 기록 계획

## 긴급 일정 전략

2026-10-17 시연 성공을 최우선으로 두고 HOME→object 자동 경로 최적화와 HOME↔SAFE_HIGH 자동 왕복을 critical path에서 제외한다.

```text
canonical runtime start = PICK_READY
runtime alias           = VISION_READY
HOME role               = STORAGE_PARKING_ONLY
SAFE_HIGH role          = RECOVERY_FALLBACK_OPTIONAL_TRANSPORT
```

PICK_READY 기록 이후 runtime 구조는 다음으로 고정한다.

```text
PICK_READY
→ detect requested object
→ object robot XY
→ generic PRE_APPROACH(object_xy)
→ APPROACH
→ GRASP
→ LIFT
→ requested basket
→ PLACE
```

## 현재 상태

직전 HOME→C 자동 경로는 waypoint 29에서 Elbow no-progress로 FAIL했다. STOPPED 이후 current pose는 다음과 같다.

```text
Present =
[Pan +4.879121,
 Lift -40.571429,
 Elbow +78.461538,
 Flex -5.494505,
 Roll -12.615385]°

GRASP TCP = [-10.546107,-262.235242,+68.470056] mm
table point margin = +13.811056 mm
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED
```

이 자세는 낮고 Elbow가 upper calibration edge 쪽에 있어 PICK_READY로 저장하지 않는다.

```text
PICK_READY = NOT_RECORDED
```

## 기존 teleop 구조 확인

Jetson을 read-only로 확인했다.

```text
canonical server = 8000 / lelab.service active/running
LELAB_TELEOP_MODE = relative_start
teleoperation = inactive
recording = inactive
inference = inactive
leader = /dev/ttyACM0 / 5AE6085272
follower = /dev/ttyACM1 / 5AE6058306
8002/8003 listener = none
related control worker = none
```

canonical 8000의 기존 relative-start teleop만 사용한다. 임시 8003이나 새 teleop framework는 만들지 않는다.

## live 실행 순서

1. 사용자가 현재 팔의 실제 정지, 전체 링크·table·약통·바구니 비접촉, 주변 clear를 다시 확인한다.
2. read-only preflight에서 8000 health, 세 control inactive, USB serial identity, privileged leader/follower port 무점유를 확인한다.
3. canonical 8000 `/move-arm`을 한 번만 호출한다. 다른 teleop 요청과 브라우저 자동 재호출을 허용하지 않는다.
4. journal에서 `relative_start origins captured from fresh calibrated values`를 확인한다.
5. 사용자는 leader에 입력하지 않고 3초간 대기한다. follower startup jump가 없고 첫 target이 fresh follower origin인지 확인한다. 이상 movement가 있으면 즉시 stop하고 본 이동을 시작하지 않는다.
6. 사용자가 현장에서 팔 전체를 보면서 leader로 Lift/Elbow/Wrist를 부드럽게 함께 조작해 PICK_READY를 만든다. clearance가 확보되기 전 큰 Pan 회전은 피한다.
7. 사용자가 `PICK_READY REACHED`를 입력하면 teleop을 먼저 stop한다. follower/leader disconnect와 API inactive를 확인하기 전 기록을 시작하지 않는다.
8. 사용자가 실제 정지·전체 비접촉·주변 clear·camera view clear를 확인한다.
9. write/torque API를 차단한 도구로 follower Present를 정확히 3회 읽어 기록한다.

Torque OFF 상태에서 손으로 자세를 바꾸지 않으며 automatic waypoint는 사용하지 않는다.

## PICK_READY acceptance

기존에 사용한 table+100 mm clearance 기준을 재사용한다.

```text
table reference Z = 54.659 mm
required GRASP TCP Z >= 154.659 mm
Temperature <= 55°C
Moving = all 0 after stop
feedback = fresh
communication/SDK fault = none
```

다음 항목은 새 임의 threshold를 만들지 않고 측정값과 사용자 현장 확인을 함께 남긴다.

- Elbow calibration lower/upper margin
- Shoulder Lift calibration lower/upper margin
- A/B/C 일반 접근 가능 여부
- RED/GREEN/BLUE 방향 이동 방해 여부
- camera view occlusion 여부
- shoulder/upper arm/forearm/wrist/gripper의 실제 비접촉

9개 조합 전체 접근성과 full mesh/environment collision은 실제 검증 전까지 `NOT_VERIFIED`다.

## 3회 기록 형식

저장 위치:

```text
configs/poses.yaml
```

저장 필드:

```yaml
PICK_READY:
  joints:
    shoulder_pan:
      raw_mean:
      degree_mean:
      raw_std:
      degree_std:
    # 나머지 축 동일
  fk_grasp_tcp_mm:
    x:
    y:
    z:
  temperature_c:
    shoulder_pan:
      mean:
      maximum:
      std:
    # 나머지 축 동일
  recorded_at:
  note:
  sample_count: 3
```

`Present_Load`는 signed diagnostic으로 별도 기록하되 numeric PASS gate로 사용하지 않는다.

## 준비 변경과 검증

- `configs/poses.yaml`
  - `runtime_start_pose: PICK_READY`
  - HOME/SAFE_HIGH/PICK_READY 역할 metadata
  - `PICK_READY: NOT_RECORDED`
- `scripts/recorded_pose_config.py`
  - PICK_READY 3-sample record 지원
  - Temperature mean/max/std 지원
  - 기존 HOME+SAFE_HIGH return-pair 요구 유지
- `configs/pick_ready_record_plan_20261012.json`
  - live scope, identity, acceptance, 기록 필드 고정

```text
selected tests        = 15/15 PASS
py_compile            = PASS
JSON/YAML validation  = PASS
git diff --check      = PASS
hardware command      = 0
motor/Goal/Torque     = 0
service/USB change    = 0
```

## 기록 직후 자동으로 이어갈 offline 작업

PICK_READY가 기록되면 같은 turn에서 모터를 움직이지 않고 다음을 바로 수행한다.

1. PICK_READY fresh pose와 저장값 일치 확인
2. 새 GRASP TCP 기준 PICK_READY→C PRE_APPROACH 경로 생성
3. max step, TCP Z, table/self proxy, servo margin, orientation 검증
4. tests/dry-run
5. 다음 실제 한 단계 승인 문구 제시

table calibration, PIN/GRASP TCP separation, ArUco, C XY는 새 증거 없이 다시 분석하지 않는다.

## 시연 일정 기준선

```text
10/13  C PICK: GRASP_PASS + LIFT_PASS
10/14  C→RED full automatic cycle
10/15  generic PICK/PLACE + RED/GREEN/BLUE destination
10/16  A/B/C identification + 9 commands + repetition
10/17  fixed PICK_READY final demo
```

## 다음 승인

```text
RUN SUPERVISED TELEOP TO PICK_READY
```
