# 2026-10-13 PICK_READY / VISION_READY 기록

## 결과

사용자 승인 `RUN SUPERVISED TELEOP TO PICK_READY` 범위에서 canonical 8000 LeLab의 기존 `relative_start` teleoperation으로 사용자가 PICK_READY 자세를 만들었다. 사용자 입력 `PICK_READY REACHED` 직후 teleoperation을 종료했고, 다음 상태를 확인했다.

```text
teleoperation_active = false
leader /dev/ttyACM0 = PORT_UNOWNED
follower /dev/ttyACM1 = PORT_UNOWNED
```

사용자가 현장에서 다음을 확인했다.

```text
STOPPED
전체 링크 비접촉
주변 clear
camera view clear
```

그 뒤에만 write·torque API가 차단된 `scripts/read_follower_pose_telemetry.py`로 follower를 0.2초 간격 정확히 3회 읽었다. 세 표본은 모두 동일했다.

## canonical pose

```text
PICK_READY = RECORDED
VISION_READY = alias of PICK_READY

Pan   =  -4.263736 deg
Lift  = -68.703297 deg
Elbow = +68.879121 deg
Flex  =  +8.131868 deg
Roll  = -23.516484 deg

GRASP TCP = [+30.308815,-276.029085,+184.960142] mm
```

raw Present는 `[2053,1173,2767,2173,1597,447]`, raw Goal은 `[2052,1160,2754,2163,1595,446]`이다. Goal-Present는 Pan/Lift/Elbow/Flex/Roll `[-0.087912,-1.142857,-1.142857,-0.879121,-0.175824]°`다.

## acceptance

```text
table reference Z                 = 54.659000 mm
required PICK_READY TCP Z         = 154.659000 mm
measured GRASP TCP Z              = 184.960142 mm
margin above table                = +130.301142 mm
margin above PICK_READY criterion = +30.301142 mm
Moving                            = all 0
Temperature max                   = 36 C
Torque_Enable                     = all 1, unchanged
motor write by record runner      = 0
torque change by record runner    = 0
post-record follower port         = PORT_UNOWNED
PICK_READY acceptance             = PASS
```

`Present_Load=[0,64,64,52,20,0]`은 signed diagnostic으로만 저장했으며 numeric PASS/FAIL gate로 사용하지 않았다.

실제 calibration range에 대한 margin은 다음과 같다. 새 threshold는 만들지 않았다.

| 축 | lower margin | upper margin |
|---|---:|---:|
| Shoulder Lift | 33.142857° | 170.549451° |
| Elbow | 165.890110° | 28.131868° |

## 저장 및 근거

- canonical pose: `configs/poses.yaml`
- local raw evidence: `.local/pick-ready-20261013/pick_ready_post_stop_3sample.json`
- local/remote reader SHA-256: `7c440b81c503735df10d62662c72e1c4b8f1fee3dcbc4ceada5f5c40065f3c56`
- FK URDF: `.local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf`
- GRASP TCP: `configs/c_pick_grasp_tcp_candidate_20261012.json`
- calibration range: `configs/so101_follower_calibration_bounds_20261008.json`

YAML/schema, raw↔degree, Goal-Present, FK, clearance, calibration margin, telemetry 통계를 독립 재검산했고 `tests/test_recorded_pose_config.py` `5/5 PASS`, py_compile와 diff-check도 통과했다.

## 미검증 항목

```text
A/B/C automatic paths             = NOT_VERIFIED
RED/GREEN/BLUE automatic paths    = NOT_VERIFIED
9 combinations                    = NOT_VERIFIED
full mesh/environment collision   = NOT_VERIFIED
```

다음 단계는 이 canonical PICK_READY를 시작점으로 새 GRASP TCP 기준 `PICK_READY→C PRE_APPROACH` 경로를 오프라인으로 새로 생성·검증하는 것이다. 과거 HOME→C 실패 경로를 재사용하지 않는다.
