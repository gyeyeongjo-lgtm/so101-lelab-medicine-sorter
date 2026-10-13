# SAFE_ESCAPE_2DEG fresh rebase·실기 준비

날짜: 2026-10-12

## 고정 기준선

- table→robot calibration, C robot XY, calibration PIN TCP, PICK GRASP TCP `[-4.748354,-12.033741,-124.531737] mm`를 변경하지 않았다.
- tolerance 확대, raw feed-forward, torque/gain 변경을 하지 않았다.
- full mesh collision은 `NOT_VERIFIED`로 유지한다.
- 이번 범위에는 전체 pre-approach/approach, gripper close, lift가 없다.

## read-only fresh preflight

사용자의 `정지·전체 링크 비접촉·주변 clear 확인` 이후 다음을 재확인했다.

```text
teleoperation_active = false
recording_active     = false
inference_active     = false
related control worker = none
canonical follower   = /dev/ttyACM1 / 5AE6058306
privileged fuser before/after = rc 1 / unowned
```

write/sync_write/enable_torque/disable_torque/send_action을 예외로 차단하고 0.25초 간격으로 읽은 3표본은 완전히 동일했다.

| joint | Present raw | calibrated | Goal raw | Torque | Moving | Load |
|---|---:|---:|---:|---:|---:|---:|
| shoulder_pan | 2106 | +0.395604° | 2111 | 1 | 0 | -32 |
| shoulder_lift | 2161 | +18.153846° | 2149 | 1 | 0 | 60 |
| elbow_flex | 2153 | +14.901099° | 2140 | 1 | 0 | 64 |
| wrist_flex | 2193 | +9.890110° | 2190 | 1 | 0 | 24 |
| wrist_roll | 2031 | +14.637363° | 2036 | 1 | 0 | -32 |
| gripper | 446 | 2.019584% | 446 | 1 | 0 | 0 |

motor/Goal/Torque write attempt는 0회였고 read-only 종료 후 포트는 무점유였다.

## fresh-relative 2° 후보

```text
direction = [Pan +, Lift -, Elbow -, Flex -, Roll +]
fresh     = [+0.395604,+18.153846,+14.901099,+9.890110,+14.637363]°
target    = [+2.395604,+16.153846,+12.901099,+7.890110,+16.637363]°
step      = [+2.000000,-2.000000,-2.000000,-2.000000,+2.000000]°
gripper   = 2.019584% hold
target raw = [2128,2138,2130,2170,2053,446]
raw delta  = [+22,-23,-23,-23,+22,0]
```

오프라인 FK/proxy 결과:

```text
GRASP TCP target XYZ             = [-7.174142,-378.973903,+75.993672] mm
commanded table proxy margin     = +21.334672 mm
self-collision centerline proxy  = 64.775222 mm / PASS
minimum servo margin             = 80.109901°
maximum joint step               = 2.0°
full mesh collision              = NOT_VERIFIED
```

시작 sample의 virtual GRASP point는 single-P1 infinite-plane reference보다 `-4.162861 mm` 낮다. 이는 앞서 확정한 proxy 의미와 같으며 실제 link-table collision 판정으로 승격하지 않는다.

## runner·검증

- `scripts/live_c_safe_escape_only.py`는 정확히 2°인 fresh-relative target만 허용한다.
- 승인 문구는 `RUN SAFE ESCAPE 2DEG ONLY`다.
- 한 target만 송신하고 final tolerance `0.5°`를 적용한다.
- gripper는 fresh 값을 유지한다.
- approach/pre-approach/grasp/lift/automatic continuation 경로가 없다.
- fake safe-escape 6개 + exclusive transport 12개 = `18/18 PASS`.
- py_compile, `git diff --check`, Jetson SHA 검증, Jetson dry-run PASS.
- Jetson SHA: runner `418e1509fb0bdb2337d47676c6b06e723bf9e8ca1161b7013f179bd372e3a0e6`, config `6607c5289f6d4e6314e5b5aa2c1b54648408fa6dc73071f7fe8a3cd38e976e5c`.
- dry-run 출력은 `no port opened; no send_action; escape/approach/grasp/lift unavailable`; 종료 후 follower `fuser rc=1`이다.

## 현재 판정

```text
SAFE_ESCAPE_2DEG_READY = true
actual_motor_command_count = 0
motion_authorized = false
next_explicit_approval = RUN SAFE ESCAPE 2DEG ONLY
```

실패 시 자동 재시도하지 않는다. Goal raw, Present raw, calibrated error, Moving, Load, fresh joints를 read-only로 보고한다. 성공 시에도 사용자의 실제 링크 비접촉·table clearance 비악화 확인 전에는 `SAFE_ESCAPE_PASS=true`로 확정하지 않는다.

변경은 `NOT_COMMITTED/NOT_PUSHED`다.
