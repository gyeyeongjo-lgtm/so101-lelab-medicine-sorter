# 2026-09-21 - Astra ArUco RGB-D 좌표 파이프라인 적용

## 요청과 방향

- 사용자 제공 문서의 목표는 Astra RGB/Depth와 ArUco로 Camera→World→Robot Base 좌표를 만들고, dry-run 검증 뒤에만 로봇을 움직이는 것이다.
- 이는 기존의 Astra 기준 ArUco 작업대 좌표와 YOLO/고정좌표 기반 제어 방향을 3D로 확장한 것이다.
- 실제 모터 동작은 이번 범위가 아니며 `robot_enabled=false`를 유지한다.

## Phase 1 조사 결과

```text
Camera capture: OpenNI2 /opt/orbbec-openni2, Astra RGB888 640×480@30
ArUco: scripts/aruco_table.py, DICT_4X4_50, marker 70 mm
Calibration: configs/astra_color_intrinsics.local.json, RMS 0.478 px
Depth: DEPTH_1_MM 640×480@30 sensor는 확인됐으나 기존 통합 코드는 없었음
Robot: LeRobot SO101Follower, Feetech serial; Cartesian adapter 없음
Transforms: pixel→table 2D homography와 개별 marker solvePnP
Config: reference 0–3, basket 4=red·5=green·6=blue, object ID 미정
Unit: 기존 vision/workspace는 mm
Missing: RGB-depth 정합 코드, Camera XYZ, T_W_C 3D, T_B_W, limits, grasp offset
```

## 구현

- `scripts/orbbec_rgbd_pipe.cpp`
  - 기존 OpenNI2 runtime을 그대로 사용한다.
  - RGB888와 DEPTH_1_MM 640×480@30을 동시에 연다.
  - `IMAGE_REGISTRATION_DEPTH_TO_COLOR`와 depth-color sync를 요구한다.
  - registration이 불가능하면 unaligned frame을 내보내지 않는다.
- `scripts/astra_depth_diagnostic.py`
  - raw depth와 colorized debug depth를 분리한다.
  - 중앙 및 ArUco 중심의 11×11 ROI에서 범위 밖/0을 제외한 median을 계산한다.
  - frame별 RGB-depth timestamp, invalid ratio, marker pixel/depth를 JSONL로 기록할 수 있다.
  - LeRobot·serial·torque·motion API를 import하지 않는다.
- `configs/astra_rgbd.example.json`
  - unit=mm, dry_run=true, robot_enabled=false.
  - object IDs, `T_B_W`, robot limits가 비어 있음을 명시하고 motion block 이유를 보존한다.
- `docs/ASTRA_RGBD_PIPELINE.md`
  - 좌표 convention과 남은 단계, 승인 경계를 기록했다.

## 첫 오류와 수정

- 최초 실행은 OpenNI의 `USB events thread` 경고가 helper stdout의 JSON 앞에 섞여 frame capture 전 종료됐다.
- OpenNI console output off와 metadata의 JSON line 선택, binary stream의 `RGBD` magic resync를 추가했다.
- 하드웨어나 robot 설정은 바뀌지 않았으며 이후 300-frame run은 통과했다.

## 실제 300-frame 결과

- 장치: Astra `2bc5:0401`, OpenNI `2.3.0.85`.
- RGB: RGB888 640×480@30.
- Depth: DEPTH_1_MM 640×480@30, 단위 1 mm.
- `registration_depth_to_color_supported=true`, `registration_enabled=true`, sync=true.
- 300 frames, 10.521 s, effective 28.515 FPS.
- RGB-depth timestamp delta 중앙값: 465.5 µs.
- 중앙 11×11 ROI depth 중앙값: 891 mm.
- 유효 depth 범위: 683–2414 mm.
- 평균 invalid depth: 30.895%.
- marker depth:
  - ID0: 728 mm, std 0.163 mm, 300/300.
  - ID1: 726 mm, std 0.442 mm, 15/300.
  - ID2: 901 mm, std 1.472 mm, 300/300.
  - ID3: 905 mm, std 0.244 mm, 300/300.
  - ID4: 788 mm, 205 frames.
  - ID5: 781 mm, 59 frames.
  - ID6: 검출 0.
- 진단 영상에서 RGB 왼쪽과 registered depth의 작업대/바구니 경계가 대응하는 것을 시각 확인했다.
- ChArUco board 일부가 왼쪽 가장자리에 남아 ID24·27·29·30·33이 추가 검출됐다.

## 검증과 배포

- ROI filtering과 binary header resync를 포함한 하드웨어 없는 관련 테스트 17개가 통과했다.
- Jetson 설치:
  - `/opt/orbbec-openni2/bin/orbbec-rgbd-pipe`
  - `/opt/so101-rgbd/astra_depth_diagnostic.py`
- 설치 binary SHA-256: `5b732b4d...ffc126`.
- 설치 diagnostic SHA-256: `c37b3bf9...5804d1`.
- 상시 preview를 다시 시작했고 Astra·RealSense 모두 `ok=true`였다.
- 종료 시 LeLab health 정상, teleoperation·recording·inference 모두 inactive였다.

## 판정과 다음 단계

- `PASS`: Phase 1 repository 조사, Phase 2 depth 독립 진단, Phase 3 RGB-depth registration과 ArUco 중심 depth 결합.
- `PARTIAL`: 화면 전체 invalid depth 약 30.9%; 플라스틱/가장자리에서는 hole이 보인다. ROI median은 유지한다.
- `BLOCKED (physical)`: ChArUco 보드를 완전히 치우고 ID1·ID6의 가림과 quiet zone을 수정해야 최종 exact-count를 수행할 수 있다.
- `NOT_VERIFIED`: 891 mm의 줄자 대조, Camera XYZ, 3D World transform, `T_B_W`, robot-base dry-run, 실제 motion.
- `NOT_PUSHED`: commit·push하지 않았다.

## 보드 제거·마커 재배치 후 300-frame 재검사

- 사용자가 ChArUco 보드를 치우고 marker 배치를 조정한 뒤 같은 Astra RGB-D 경로를 다시 검사했다.
- 300 frames, 10.537 s, effective 28.47 FPS, RGB-depth timestamp delta 중앙값 470.5 µs였다.
- 화면 중앙 depth 중앙값은 889 mm, 유효 범위는 682–2484 mm, 평균 invalid depth는 31.321%였다.
- marker 검출/유효 depth frame:
  - ID0: 300/300, depth 717 mm, std 0.115 mm.
  - ID1: 173/300, depth 731 mm, std 0.398 mm.
  - ID2: 300/300, depth 905 mm, std 0.376 mm.
  - ID3: 300/300, depth 898 mm, std 0.837 mm.
  - ID4(red): 266/300, depth 794 mm, std 0.489 mm.
  - ID5(green): 86/300, depth 794 mm, std 0.000 mm.
  - ID6(blue): 0/300.
- ChArUco board와 보드 marker는 진단 영상에서 제거된 것을 확인했다.
- ID1은 화면 하단 경계에 가까워 간헐 검출되고, ID5는 바구니의 반사/가림 영향이 크며, ID6은 영상에 보이지만 사전 ID로 해독되지 않는다.
- 상시 preview를 다시 시작했고 Astra·RealSense `/health` 모두 `ok=true`였다. 종료 시 LeLab health 정상, teleoperation·recording·inference 모두 inactive였다.
- `BLOCKED (physical)`: 기존 작업대 실측 좌표를 보존하기 위해 ID1 중심은 옮기지 말고 카메라 framing 또는 불투명 흰 backing을 보정한다. ID5·6은 평평한 흰 판 위에 투명 덮개·반사 없이 노출한 뒤 exact-count를 다시 수행한다.
- `SAFETY`: 이번 재검사도 camera-only였고 robot serial, torque, motor command는 사용하지 않았다.

## ID1 흰 여백 추가 후 재검사

- 사용자가 ID1 중심 위치를 유지한 채 불투명 흰 여백을 추가했다.
- 300 frames, 10.520 s, effective 28.517 FPS, RGB-depth timestamp delta 중앙값 469.0 µs였다.
- ID0=300/300, ID1=300/300, ID2=297/300, ID3=300/300으로 ID1 문제가 해결됐다.
- 바구니는 ID4=139/300, ID5=26/300, ID6=0/300으로 통과하지 못했다.
- 중앙 depth 중앙값은 889 mm였고, 검출된 marker frame의 depth는 모두 유효했다.
- 진단 영상에서 ID4–6이 여전히 투명 바구니 안쪽 바닥에 있어 플라스틱 테두리와 반사의 영향을 받는 것을 확인했다.
- 상시 preview를 복구했고 Astra·RealSense `/health` 모두 `ok=true`였다. 종료 시 teleoperation·recording·inference 모두 inactive였다.
- `NEXT`: ID4–6을 바구니 밖의 카메라를 향한 평평한 불투명 흰 판에 부착한다. ID6이 계속 검출되지 않으면 DICT_4X4_50 ID6 70 mm를 재인쇄한다.
- `SAFETY`: camera-only 검사였으며 robot serial, torque, motor command는 사용하지 않았다.

## ID2·4 교체 후 원본 RGB 확인

- 상시 MJPEG 300-frame 검사에서 ID0=289, ID1–6=300, duplicate=0이었다.
- preview를 잠시 중지하고 Astra OpenNI RGB888 640×480 원본을 직접 300 frames/10.447 s 집계했다.
- 원본 결과는 ID0=281, ID1=300, ID2=300, ID3=300, ID4=300, ID5=300, ID6=300, 모든 ID duplicate=0이었다.
- 첫 원본 검사 시 300-frame 수집 뒤 helper의 graceful 종료가 3초를 초과해 요약 전에 wrapper가 종료됐다. helper 잔류가 없음을 확인하고 두 번째 run은 수집 결과를 먼저 기록한 뒤 종료해 통과했다.
- `PASS`: ID1–6의 인쇄/배치와 basket mapping은 통과했다.
- `PARTIAL`: 오른쪽 아래 작업대 ID0만 281/300이다. 중심 위치를 유지하고 오른쪽·아래를 포함한 사방 무광 흰 여백을 넓힌 뒤 최종 재검사한다.
- 검사 후 preview를 복구해 Astra·RealSense `/health ok=true`였고 teleoperation·recording·inference는 모두 inactive였다.
- `SAFETY`: camera-only 검사였으며 robot serial, torque, motor command는 사용하지 않았다.

## 최신 교체 후 ID 중복 확인

- Astra RGB 300-frame 첫 집계에서 ID5 occurrence가 313으로 frame 수를 초과해 중복 marker 가능성을 발견했다.
- 프레임별 중복을 분리해 다시 300 frames를 집계한 결과 ID0=294, ID1=300, ID2=35, ID3=300, ID4=0, ID5=300, ID6=299였다.
- ID5가 한 frame에 두 번 검출된 경우가 32/300이었다.
- 마지막 raw frame의 중심 좌표는 왼쪽 바구니 ID6≈(298,273), 가운데 ID5≈(368,276)이었고 오른쪽 바구니 marker는 해독되지 않았다. 즉 오른쪽 ID4 예정 marker가 일부 frame에서 ID5로 오해독된 것이다.
- `PASS`: ID1·3·5는 300/300, ID0·6은 각각 294/300·299/300으로 안정적이다.
- `BLOCKED`: 왼쪽 위 작업대 ID2와 오른쪽 바구니 ID4만 재인쇄/교체가 필요하다. DICT_4X4_50, 70 mm, 무광 흰 여백 조건을 유지하고 기존 중심/위치에 부착한다.
- Astra·RealSense preview는 계속 `ok=true`였고 종료 시 teleoperation·recording·inference 모두 inactive였다.
- `SAFETY`: camera-only 검사였으며 robot serial, torque, motor command는 사용하지 않았다.

## ID1·2 재조정 후 RGB 재검사

- 상시 Astra MJPEG에서 300 frames/9.960 s를 집계했다.
- 결과는 ID0=189, ID1=300, ID2=274, ID3=300, ID4=300, ID5=6, ID6=300이었다.
- ID1은 0에서 300/300으로 완전히 복구됐고 ID3·4·6도 통과했다.
- 별도 동일-frame 300회 비교에서 기본 detector는 ID0=168, ID2=230, ID5=9였고, error correction/corner refinement를 강화해도 각각 168, 230, 14에 그쳤다. 강화 설정은 잘못된 ID17을 1회 만들었다.
- `REJECTED`: false positive 위험이 있어 detector 완화 설정은 적용하지 않는다.
- `NEXT`: ID0·2·5를 DICT_4X4_50, 70 mm로 재인쇄해 기존 중심에 겹치고 무광 흰 바탕에 평평하게 부착한다. ID1·3·4·6은 움직이지 않는다.
- Astra·RealSense preview는 계속 `ok=true`였고 종료 시 teleoperation·recording·inference 모두 inactive였다.
- `SAFETY`: camera-only 검사였으며 robot serial, torque, motor command는 사용하지 않았다.

## 최신 배치 확인과 RGB-D 첫-frame 정지

- RGB-D diagnostic을 두 번 실행했으나 두 run 모두 첫 frame 뒤 OpenNI stdout read에서 정지했다. 두 결과는 exact-count 판정에서 제외하고 `KeyboardInterrupt`로 종료했으며 helper 잔류가 없음을 확인했다.
- 상시 preview의 Astra RGB 전용 MJPEG 경로로 대체 300-frame 검사를 수행했다. captured=300, elapsed=9.978 s였다.
- RGB exact count는 ID0=232, ID1=0, ID2=86, ID3=300, ID4=300, ID5=128, ID6=238이었다.
- 최신 raw frame에서 ID1 오른쪽 quiet zone이 어두운 반사판과 이어져 외곽 사각형 후보가 만들어지지 않았다.
- ID2는 사각 후보가 검출되지만 DICT_4X4_50 decoding에 실패했다. 재인쇄 후 기존 중심에 정확히 겹치는 것이 필요하다.
- `NEXT`: ID1·2를 DICT_4X4_50, 70 mm로 재인쇄하고 사방 무광 흰 여백을 확보한다. ID0·5·6도 외곽 여백/평탄도를 보정한다.
- 상시 preview는 active이며 Astra·RealSense `/health ok=true`다. 종료 시 teleoperation·recording·inference 모두 inactive였다.
- `SAFETY`: camera-only 검사였으며 robot serial, torque, motor command는 사용하지 않았다.

## 바구니 수평 배치 후 재검사

- 300 frames, 10.539 s, effective 28.465 FPS, RGB-depth timestamp delta 중앙값 447.5 µs였다.
- 바구니 tag는 ID4=300/300(depth 779 mm), ID5=261/300(depth 785 mm), ID6=300/300(depth 788 mm)으로 크게 개선됐다.
- 작업대 기준 tag는 ID0=122/300, ID1=0/300, ID2=0/300, ID3=300/300이었다.
- 화면 중앙 depth 중앙값은 889 mm였고 검출된 marker의 depth frame은 모두 유효했다.
- `PARTIAL`: ID4와 ID6은 통과했고 ID5는 평탄도/여백을 조금 더 보정해야 한다.
- `REGRESSION`: ID1·2 종이가 평탄하지 않거나 인쇄면/문양이 정상적으로 노출되지 않은 상태로 보여 기준 좌표계를 만들 수 없다. 뒤집힘 없이 인쇄면을 카메라로 향하게 하고 무광 흰 바탕에 평평하게 복원한다.
- 상시 preview를 복구했고 Astra·RealSense `/health` 모두 `ok=true`였다. 종료 시 teleoperation·recording·inference 모두 inactive였다.
- `SAFETY`: camera-only 검사였으며 robot serial, torque, motor command는 사용하지 않았다.

## 바구니 추가 조정 후 재검사

- 300 frames, 10.520 s, effective 28.517 FPS, RGB-depth timestamp delta 중앙값 450.0 µs였다.
- 검출 결과는 ID0=180/300, ID1=0/300, ID2=287/300, ID3=300/300, ID4=0/300, ID5=0/300, ID6=0/300이었다.
- 화면 중앙 depth 중앙값은 887 mm였고 검출된 marker의 depth frame은 모두 유효했다.
- 진단 영상상 ID4–6은 바구니 앞쪽의 기울어진 면에 있고, 반사성 회색 판이 작업대와 ID1 주변 조건을 바꿨다.
- `FAIL`: 바구니 marker 조정은 통과하지 못했으며 직전 300/300이던 ID1도 검출되지 않았다.
- `NEXT`: 반사판을 제거하고 ID1을 직전 조건으로 복원한다. ID4–6은 각각 무광 흰색 카드 위에 완전히 평평하게 붙여 천장 카메라 방향을 향하게 한다.
- 상시 preview를 복구했고 Astra·RealSense `/health` 모두 `ok=true`였다. 종료 시 teleoperation·recording·inference 모두 inactive였다.
- `SAFETY`: camera-only 검사였으며 robot serial, torque, motor command는 사용하지 않았다.
