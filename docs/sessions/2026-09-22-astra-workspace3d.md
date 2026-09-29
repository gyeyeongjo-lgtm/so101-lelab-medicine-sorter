# 2026-09-22 - Astra Camera XYZ와 작업대 3D 좌표 진단

## 범위와 안전

- 사용자 요청에 따라 Astra 천장 정면 카메라의 Camera→World 좌표 단계를 계속 진행한다.
- 이번 범위는 camera-only다. LeRobot, robot serial, torque, teleoperation, recording,
  inference, motor command는 사용하지 않는다.
- `T_B_W`, 로봇 한계, grasp offset이 없으므로 `robot_enabled=false`를 유지한다.

## 시작 상태

- Astra RGB intrinsic: 640×480, RMS 0.478 px.
- reference marker 중심(mm):
  - ID0=(0, 0, 0)
  - ID1=(343, 0, 0)
  - ID2=(332.181, 260.854, 0)
  - ID3=(6.242, 276.930, 0)
- basket mapping: ID4=red, ID5=green, ID6=blue.
- 사용자 승인에 따라 ID0=281/300, ID1–6=300/300인 마지막 원본 RGB 배치를
  M3 진단 진입 조건으로 사용한다. 이는 실제 로봇 이동 승인 조건이 아니다.

## 640×480 RGB-D 정지 조사

- RGB-only 640×480@30은 연속 수집됐다.
- Depth-only 640×480@30도 30/30 frames 연속 수집됐다.
- RGB+Depth 640×480@30은 hardware sync on/off, frame read order, 두 stream wait set을
  바꿔도 첫 frame 뒤 정지했다.
- 두 단독 stream이 정상이고 동시 stream만 멈추므로 legacy Astra/OpenNI의 USB2 동시
  대역폭 문제를 우선 원인으로 본다. USB reset/replug는 수행하지 않았다.

## 구현

- `scripts/orbbec_rgbd_pipe.cpp`
  - `--low-bandwidth`에서 RGB888와 DEPTH_1_MM을 320×240@30으로 연다.
  - depth→color registration은 필수로 유지한다.
  - legacy driver 정지를 피하려 hardware sync는 끄고 timestamp 차이 50 ms 이내 frame을
    software pairing한다.
  - protocol header와 row size를 실제 해상도에 맞게 동적으로 출력한다.
- `scripts/astra_depth_diagnostic.py`
  - 640×480 RGB intrinsic을 capture 해상도에 맞춰 scale한다.
  - 320×240 ArUco 검출은 원본과 2배 확대 결과를 ID별 병합한다.
  - registered depth와 RGB ray로 Camera XYZ를 계산한다.
  - ID0–3 실측 중심으로 multi-marker solvePnP를 수행해 `T_C_W`와 `T_W_C`를 계산한다.
  - World XYZ, PnP/depth Z 차이, 재투영 RMS, 기준 marker 3D 잔차를 JSONL과 summary에
    기록한다.
  - 다음 frame이 5초 안에 오지 않으면 실패 처리하고 helper를 종료하는 watchdog을 추가했다.
- `configs/astra_rgbd.example.json`
  - reference ID0–3 중심과 transform convention을 명시했다.

## 검증 상태

- `PASS (offline tests)`: ArUco table, depth ROI, protocol resync, intrinsic scaling,
  deprojection, rigid transform, workspace config 관련 테스트 21개가 통과했다.
- `NETWORK RECOVERED`: 사용자가 Jetson을 다시 연결한 뒤 `192.168.50.20` SSH와
  camera preview HTTP가 정상화됐다. 시작 전 LeLab health 정상, teleoperation·recording·
  inference 모두 inactive를 확인했다.
- `PASS (30-frame smoke)`: 320×240 RGB-D 30 frames를 1.549 s에 연속 수집했다.
  첫 frame 뒤 정지 현상은 없었고 ID0–6은 모두 30/30이었다.
- `PASS (300-frame stability)`: 300 frames/10.533 s, effective 28.482 FPS,
  RGB-depth timestamp 차이 중앙값 33.305 ms였다. ID0–6 모두 검출·유효 depth 300/300,
  중앙 depth 813 mm, 평균 invalid depth 32.606%, 유효 범위 655–2380 mm였다.
- `FAIL (3D accuracy)`: world pose는 300/300 계산됐지만 재투영 RMS 중앙값 2.393 px였고,
  기준점 3D 잔차 중앙값은 ID0=43.82 mm, ID1=48.06 mm, ID2=137.00 mm,
  ID3=128.16 mm였다. depth-vs-PnP Z 차이도 각각 38.15, 45.22, 136.04,
  123.84 mm여서 현재 `T_W_C`를 로봇 좌표로 사용하면 안 된다.
- `PASS (resolution mapping check)`: 같은 고정 카메라의 640×480와 320×240 marker 중심은
  약 0.5배와 1px 안쪽 offset으로 대응했다. 저해상도 intrinsic 단순 scale이 큰 오차의
  주원인은 아니다.
- `PASS (FOV sanity check)`: OpenNI FOV 환산 320×240 focal은 fx=fy=285.17 px이고,
  ChArUco 축소값은 fx≈289.22, fy≈282.97 px라 focal 차이는 작았다.
- `REJECTED (PnP solver swap)`: IPPE의 두 평면 해와 ITERATIVE·SQPNP를 비교했지만
  실제 depth 경사와 일치하는 해는 없었다. 알고리즘만 바꾸는 보정은 적용하지 않는다.
- `PHYSICAL MEASUREMENT REQUIRED`: 70 mm 가정의 개별 marker PnP 거리와 depth를
  비교하면 실제 검은 사각형 폭이 약 63 mm일 때 일관되게 맞는다. 약 90% 인쇄 축소 여부를
  자로 확인해야 한다. 반복 재부착 후 ID0–3 중심 간 거리도 현재 배치에서 다시 실측해야 한다.
- `NOT_DEPLOYED`: 300-frame 수집은 통과했지만 3D 정확도가 실패했으므로 최신 M3 helper와
  diagnostic을 Jetson 설치 경로에 배포하지 않았다. 임시 파일만 사용했다.
- `NOT_PUSHED`: commit·push하지 않았다.

## 프리뷰 자원 복구

- systemd service와 별도로 사용자 SSH session에서 수동 실행된 preview server가 포트를
  점유해 서비스가 auto-restart 중인 상태를 확인했다.
- 수동 preview server만 정상 종료한 뒤 systemd service 단독 상태로 정리했다.
- service stop 시 server/helper가 모두 사라지는 것을 확인하고 다시 시작했다.
- 최종 preview는 service active, Astra·RealSense 모두 `ok=true`다.

## 재실측 전 계획

1. 검은 ArUco 사각형 한 변을 mm로 실측한다. 흰 종이/여백 크기가 아니다.
2. 현재 중심 기준 `0–1, 1–2, 2–3, 3–0, 0–2, 1–3`을 다시 실측한다.
3. 실측값으로 marker size와 reference center config를 갱신한다.
4. 같은 300-frame 진단에서 기준점 3D 잔차와 depth-vs-PnP Z 차이를 재검사한다.
5. 오차가 남으면 ChArUco intrinsic의 principal point/distortion을 재수집·검증한다.

## ID0–3 현재 거리 재실측 반영

- 사용자 재실측(mm): 0–1=331, 1–2=275, 2–3=325, 3–0=272,
  0–2=432, 1–3=434.
- 여섯 값은 정확한 평면 사각형으로는 조금 모순되므로 ID0=(0,0), ID1=(331,0)을
  고정하고 equal-weight nonlinear least squares로 적합했다.
- 새 중심(mm): ID0=(0,0), ID1=(331,0), ID2=(326.807,277.190),
  ID3=(-0.861,274.244).
- 거리 적합 RMS는 2.626 mm, 최대 절대 잔차는 3.487 mm다. 원본 여섯 실측값과
  적합 정보를 `configs/astra_rgbd.example.json`에 함께 보존했다.

### 실카메라 재검사

- 기존 ChArUco intrinsic으로 30-frame smoke를 다시 실행했다.
  - ID0–6 모두 30/30, world pose 30/30.
  - 재투영 RMS 중앙값 2.612 px.
  - 기준점 3D 잔차 중앙값: ID0=73.11, ID1=51.62, ID2=115.22,
    ID3=133.55 mm.
  - 새 중심 거리만으로는 `T_W_C`가 통과하지 않았다.
- OpenNI factory FOV focal과 영상 중심, zero distortion을 사용하는 별도 임시 intrinsic으로
  한 변수만 바꿔 30-frame 비교했다.
  - ID0=29/30, ID1–6=30/30, world pose 29/30.
  - 재투영 RMS 중앙값은 1.941 px로 개선됐다.
  - 기준점 3D 잔차는 ID0=68.41, ID1=64.91, ID2=102.05,
    ID3=106.06 mm로 여전히 실패했다.
- `REJECTED`: factory intrinsic을 활성 config로 채택하지 않는다. 원인은 단순 reference 거리나
  focal/principal point 하나만의 문제가 아니며 depth-to-color 정합/깊이 해석도 검증해야 한다.
- `BLOCKED (one physical value)`: 검은 ArUco 사각형의 실제 바깥 폭(mm)이 아직 없다.
  이 값으로 개별 marker PnP 거리와 depth scale/registration을 먼저 대조한다.
- `RESOURCE RECOVERED`: 검사 후 preview service를 다시 시작했고 Astra·RealSense 모두
  `ok=true`다. 최신 M3 코드는 정확도 실패로 설치하지 않았다.

## ID0 실제 폭 75 mm 반영과 RGB-depth 정합 분리

- 사용자가 ID0의 흰 여백을 제외한 검은 ArUco 바깥 폭을 75 mm로 실측했다.
- 처음에는 `configs/astra_rgbd.example.json`의 공통 `marker_size_mm`를 75로 갱신했으나,
  이후 ID5=70 mm 실측이 확인되어 아래 per-ID size 설정으로 교정했다.
- 원본 320×240 RGB와 16-bit depth snapshot을 동시에 저장할 수 있도록 diagnostic에
  `--rgb-output`, `--depth-output`, `--snapshot-require-expected`를 추가했다.
- 모든 ID가 들어온 원본 frame에서 75 mm marker별 PnP Z와 중심 depth를 비교했다.
  - ID0: 838.84 vs 717 mm
  - ID1: 869.85 vs 726 mm
  - ID2: 1159.75 vs 910 mm
  - ID3: 1076.07 vs 898 mm
  - ID4: 908.07 vs 774 mm
  - ID5: 914.79 vs 778 mm
  - ID6: 982.81 vs 781 mm
- 단일 공통 depth sampling offset 탐색은 reference ID0–3 기준 `(dx,dy)=(+5,-62)` px에서
  RMSE 37.28 mm까지 낮아졌지만, 이는 영상 위쪽의 더 먼 작업대 depth를 샘플링한 결과다.
- RGB Canny edge와 depth discontinuity edge를 독립적으로 비교한 실제 최적 정렬은
  `(dx,dy)=(-2,-1)` px, matched fraction 0.945였다. 무이동도 0.832라 RGB-depth 등록은
  거의 정렬되어 있고, 약 62 px 이동을 registration 보정으로 사용할 근거는 없다.
- 따라서 남은 큰 오차는 단순 pixel registration이 아니라 depth 거리 스케일 또는
  marker/PnP·intrinsic 기하에서 찾는다. 영상 중심에 가까운 ID5를 기준으로 Astra depth
  렌즈 광학 중심부터 marker 중심까지의 실제 직선거리를 한 번 실측하면 두 가설을 분리할 수 있다.
- 최신 변경은 정확도 기준 미통과로 `/opt`에 배포하지 않고 Jetson `/tmp`에서만 검사했다.
- `PASS (offline regression)`: 전체 camera-only 단위 테스트 24개, JSON config 구문 검사,
  Python bytecode compile이 통과했다.
- 검사 종료 후 preview service는 `active`, Astra·RealSense `/health`는 모두 `ok=true`였으며
  LeLab health 정상, teleoperation·recording·inference 모두 inactive였다. 로봇 제어는 없었다.

## ID5 줄자 거리 약 810 mm 대조

- 사용자가 Astra depth 렌즈 중심에서 ID5 marker 중심까지의 직선거리를 약 810 mm로
  실측했다.
- 같은 snapshot의 ID5 등록 depth는 778 mm로 실측보다 32 mm 짧고 오차율은 −3.95%다.
- ID5도 ID0과 같은 75 mm 폭이라고 가정한 PnP Z는 914.79 mm로 실측보다 104.79 mm
  길고 오차율은 +12.94%다. 현재 비교에서는 depth가 실제 거리 쪽에 훨씬 가깝다.
- 다만 줄자 값이 근사치이고 단일 지점뿐이므로 810/778=1.04113 depth 보정계수는 적용하지 않는다.
- ID5의 실제 검은 사각형 폭은 아직 미확인이다. 현 intrinsic에서 810 mm에 맞는 역산 폭은
  약 66.41 mm이므로, 다음에는 ID5 검은 사각형 바깥 폭을 직접 재어 ID별 인쇄 크기 차이와
  PnP/intrinsic 오차를 분리한다.

## ID5 70 mm 확인과 마커별 크기 적용

- 사용자는 ID5 검은 사각형 폭이 70 mm이고, ID0만 75 mm일 가능성이 높다고 보고했다.
- config를 기본 70 mm, ID0 override 75 mm로 교정했다. ID0과 ID5는 실측값이고
  ID1–4·6은 사용자 보고에 근거한 70 mm 가정으로 구분해 기록했다.
- diagnostic에 per-ID marker size loader와 single-marker PnP Z 진단을 추가했다. frame과
  summary는 실제 적용 크기, PnP Z, depth−PnP Z를 각각 기록한다.
- offline 단위 테스트는 26개 통과했고 JSON 구문 및 Python compile도 통과했다.
- 실제 30-frame 재검사에서 ID5는 depth 중앙값 771 mm, 70 mm PnP Z 867.696 mm였다.
  약 810 mm 줄자 거리 대비 depth는 −39 mm(−4.81%), PnP Z는 +57.696 mm(+7.12%)다.
  한 지점 근사값만으로 어느 쪽에도 scale correction을 적용하지 않았다.
- 같은 run에서 ID1·2·4·5·6=30/30, ID3=1/30, ID0=0/30이었다. 기준 marker 부족으로
  world pose는 0/30이며 이 run은 3D 좌표 정확도 판정에 사용하지 않는다.
- 종료 후 preview service `active`, Astra·RealSense `ok=true`, LeLab health 정상,
  teleoperation·recording·inference inactive를 확인했다. robot serial과 motor command는 없었다.

## 사용자 조정 후 30/300-frame 재검사

- LeLab health 정상과 teleoperation·recording·inference inactive를 확인한 뒤 preview를
  잠시 중지하고 같은 320×240 RGB-D 저대역폭 조건으로 재검사했다.
- 30-frame smoke는 ID0–6과 world pose 모두 30/30이었다.
- 300-frame stability 결과:
  - 300 frames, 27.628 FPS, sync delta 중앙값 12.754 ms.
  - ID0–6 검출 및 유효 depth 모두 300/300.
  - world pose 300/300, 재투영 RMS 중앙값 2.367 px.
  - 기준점 3D 잔차 중앙값: ID0=75.47, ID1=52.71, ID2=115.50,
    ID3=135.52 mm.
  - depth / per-ID-size single-marker PnP Z 중앙값(mm): ID0 716/811.27,
    ID1 728/825.73, ID2 910/1085.09, ID3 896/964.14, ID4 762/843.86,
    ID5 769/867.70, ID6 776/901.66.
- `PASS`: marker 가시성, RGB-D 연속 수집, world pose 계산 가능 frame 수.
- `FAIL`: 기준점 3D 정확도. 위치별 depth/PnP 차이가 일정하지 않아 공통 scale 보정은
  적용하지 않으며 최신 M3를 `/opt`에 배포하지 않는다.
- 다음 camera-only 진단은 ID0–3의 depth Camera XYZ 상호거리·평면성을 실측 여섯 거리와
  직접 비교하고, depth 3D 대응점 기반 강체변환 잔차를 PnP pose와 비교하는 것이다.
- 종료 후 preview service `active`, Astra·RealSense `ok=true`, LeLab health 정상,
  teleoperation·recording·inference inactive, 진단 helper 잔류 없음이 확인됐다.

## 2.5D table XY + relative height dry-run

- ID0–3 중심 homography로 pixel→table XY를 계산하고, depth 기준점 best-fit plane의
  카메라 방향 signed distance로 table 대비 높이를 계산하도록 diagnostic을 확장했다.
- homography reference 오차가 거의 0인 것은 네 기준점을 그대로 사용하는 정의상 결과다.
  독립 정확도 평가는 물체 기준점 또는 별도 check point로 수행해야 한다.
- frame/JSONL/summary에는 `table_xy_mm`, `height_above_table_mm`, 각 median/std를 기록하고,
  overlay 오른쪽 depth panel에 겹치지 않는 ID별 2.5D 목록을 표시한다.
- offline regression은 camera-only 테스트 30개, Python compile, JSON config, diff check를 통과했다.
- 30-frame smoke는 homography/depth pose 30/30, plane RMS 1.557 mm였다. 바구니 높이는
  ID4=56.17, ID5=55.79, ID6=55.29 mm였다.
- 300-frame stability:
  - 300 frames, 28.372 FPS, sync delta 중앙값 11.987 ms.
  - ID0–6, homography, depth plane 모두 300/300.
  - plane RMS 중앙값 1.475 mm.
  - 기준점 높이 중앙값: ID0=−1.44, ID1=+1.47, ID2=−1.51, ID3=+1.48 mm.
  - 바구니 table XY/height 중앙값: ID4=(65.21,168.61)/56.76,
    ID5=(145.61,175.66)/56.22, ID6=(240.77,179.76)/54.56 mm.
  - 바구니 XY 표준편차 축별 최대 0.358 mm, 높이 표준편차 최대 0.624 mm.
- 시각 검증에서 RGB marker와 depth panel의 ID별 2.5D 값이 대응함을 확인했다. 초기 overlay의
  RGB 텍스트 겹침은 depth panel 고정 목록 방식으로 정리했다.

### Camera-only 도구 배포

- 기존 `/opt/so101-rgbd/astra_depth_diagnostic.py`는
  `/home/jetson3/so101-recovery-backups/20260922T194500+0900_astra-25d/`에 보존했다.
- 검증 버전과 example config를 `/opt/so101-rgbd/`에 설치했다.
  - script SHA-256 `2be2c650a6a48c97cd8b8b0ca7333bc206129b9ea132fdfdf236db00ad7b544f`
  - config SHA-256 `306fcfa3476decf837e79914a9c35c01bdcdac5df7b54bd61b40fa0a16f2b4dc`
- 최초 배포 config도 같은 backup directory의 `astra_rgbd.example.json.before-validation`으로
  보존한 뒤 최종 300-frame validation metadata가 포함된 config로 갱신했다.
- 설치 경로에서 기본 bytecode compile은 root 소유 `__pycache__` 생성 권한으로 최초 실패했다.
  `/tmp/astra-25d-pycache`를 지정한 compile은 통과했고 `--help`도 정상 실행됐다.
- 이 배포는 자동 실행 service를 추가하거나 기존 preview 설정을 바꾸지 않는다.
- 종료 후 preview service `active`, 두 stream `ok=true`, LeLab health 정상,
  teleoperation·recording·inference inactive, 진단 helper 잔류 없음이었다.
- 다음 단계는 대표 빈 약통/모형을 pickup 구역에 배치한 뒤 object detection과 2.5D 좌표를
  연결하는 것이다. 물체 배치와 class 정의가 필요하므로 여기서 현장 입력을 기다린다.

## 빈 약통 foreground 후보 연결

- 사용자가 바구니 밖 pickup 구역에 빈 약통/모형 한 개를 배치했다.
- preview를 잠시 중지하고 30-frame RGB-D snapshot을 수집한 뒤 즉시 복구했다. ID0–6,
  homography, depth plane은 모두 30/30이었고 plane RMS는 1.514 mm였다.
- 저장된 RGB/depth에서 작업대 plane보다 15–180 mm 높은 foreground connected component를
  추출했다. ArUco 영역은 mask했고 이 처리는 저장 영상에 대한 camera-only 분석이다.
- 작업대 ROI X=80–220 mm, Y=200–300 mm를 적용하자 현재 약통 후보 C11이 선택됐다.
  - bbox `(176,120,7,9)` px, area 53 px
  - centroid `(178.943,123.679)` px
  - table XY `(140.254,242.293)` mm
  - 높이 중앙값 42.240 mm, 최대 58.379 mm
- 영상에서 C11이 로봇 그리퍼 아래의 작은 흰색 약통과 겹치고, 로봇팔과 세 바구니는 ROI
  밖이라 제외되는 것을 확인했다.
- `scripts/depth_foreground_candidates.py`와 pickup ROI config를 `/opt/so101-rgbd/`에 배포했고
  설치 경로로 재실행해 같은 C11/좌표/높이를 확인했다. 배포 전 config backup은
  `/opt/so101-rgbd/astra_rgbd.example.json.pre-pickup-roi-20260922`다.
- 로컬 camera-only 회귀검사 18개, Python compile, JSON parse, diff check가 통과했다.
- `LIMIT`: 이는 단일 snapshot의 foreground proposal일 뿐 YOLO class/약품 식별/집기 자세가
  아니다. `T_B_W`와 motion command는 추가하지 않았고 로봇 serial·torque에도 접근하지 않았다.
- `NEXT`: 같은 약통을 pickup ROI 안의 여러 위치와 회전으로 옮겨 반복 검출 자료를 수집한다.

### 두 번째 자세 시도: ID3 가림

- 사용자가 약통을 세운 채 위치와 수평 방향을 바꾼 뒤 30-frame RGB-D를 다시 수집했다.
- capture는 성공했지만 marker count는 ID0=29, ID1=30, ID2=30, ID3=0, ID4–6=30이었다.
  ID3가 없어 table homography와 depth pose는 0/30이었고 foreground tool은
  `all four reference markers are required`로 안전하게 중단됐다.
- 이전 ID3 중심은 `(227.75,114.5)` px이며 두 번째 영상에서 약통이 이 영역을 가린 것을
  시각 확인했다. 이는 약통 검출 실패가 아니라 reference marker occlusion이다.
- preview service는 capture 직후 다시 시작했고 Astra·RealSense stream `ok=true`를 확인했다.
- `NEXT (physical)`: ArUco나 바구니는 유지하고 약통만 프리뷰 화면 기준 왼쪽으로 약 4–5 cm
  옮겨 ID3 검은 사각형과 흰 여백 전체를 노출한 뒤 pose 2를 재수집한다.

### 두 번째 자세 재시도 통과

- 사용자가 약통만 프리뷰 기준 왼쪽으로 옮긴 뒤 같은 절차로 30-frame RGB-D를 재수집했다.
- ID0–6, table homography, depth pose가 모두 30/30이었고 reference plane RMS는 2.079 mm였다.
- pickup ROI의 선택 후보 C5:
  - bbox `(191,105,16,13)` px, area 165 px
  - centroid `(198.679,111.109)` px
  - table XY `(81.956,286.512)` mm
  - 높이 중앙값 94.752 mm, 최대 97.453 mm
- RGB/overlay 시각 검사에서 C5 box가 실제 흰색 약통 전체와 일치했다. 첫 자세
  `(140.254,242.293)` mm에서 약 73.2 mm 이동해 사용자 지시 범위와도 일치한다.
- 첫 자세의 42.240 mm component는 그리퍼 바로 아래에서 약통 일부만 분리된 작은
  `7×9 px` 영역이었다. 두 번째 자세는 `16×13 px` 전체 윤곽이어서 높이 비교 기준으로 더
  신뢰하며, 첫 자세의 높이를 물체 높이 ground truth로 사용하지 않는다.
- capture 후 preview Astra·RealSense `ok=true`, LeLab teleoperation·recording·inference
  inactive, 진단 helper 잔류 없음이다. 로봇 제어는 없었다.
- `NEXT (physical)`: marker나 바구니를 건드리지 않고 약통만 세 번째 비가림 위치로 옮겨
  pose 다양성을 추가한다.

### 세 번째 자세 및 YOLO bootstrap export

- 세 번째 위치의 30-frame RGB-D에서 ID0–6, homography, depth pose가 모두 30/30이었다.
- pickup ROI 선택 C4:
  - bbox `(161,115,16,14)` px, area 174 px
  - centroid `(168.506,121.397)` px
  - table XY `(169.861,250.251)` mm
  - 높이 중앙값 95.932 mm, 최대 98.958 mm
- overlay에서 C4가 실제 흰색 약통 전체와 일치했다. 두 번째 자세 높이 94.752 mm와 차이는
  1.180 mm라, 비가림 두 자세의 상대 높이가 일관된다.
- 후보 도구에 선택 bbox를 0–1 normalized YOLO `xywh`로 내보내는 옵션을 추가했다. 영상
  경계 clip과 기본 2 px margin을 적용하며 JSON에 `review_required=true`를 남긴다.
- 시각 검토를 통과한 pose 2/3만 `/home/jetson3/so101-medicine-bootstrap/` 아래 images,
  labels, metadata로 저장했다. 첫 부분가림 자세와 ID3 가림 실패 자세는 제외했다.
- pose 2/3 label은 각각 `0 0.62187500 0.46458333 0.06250000 0.07083333`,
  `0 0.52812500 0.50833333 0.06250000 0.07500000`이다.
- 로컬 camera-only 검사 19개와 export 두 건이 통과했다. 설치 script SHA-256은
  `4c683acb06986664993b91d4317fcf053e8807de9a66180fdf7c070c48c20abe`다.
- 이 두 표본은 pseudo-label bootstrap일 뿐 학습/검증용 데이터셋 규모가 아니다. 물체 종류나
  약품 신원을 보증하지 않고 robot target으로 사용하지 않는다.
- `NEXT (physical)`: 같은 약통을 네 번째 비가림 위치로 옮겨 검토 표본을 추가한다.

## Depth 3D 대응점 강체변환 진단

- `scripts/astra_depth_diagnostic.py`에 no-scale Kabsch rigid fit을 추가했다. ID0–3의 world
  중심을 registered-depth Camera XYZ에 맞춰 `T_C_W`/`T_W_C`를 별도 계산하고 기존 PnP
  pose와 혼동하지 않도록 `depth_world_pose`로 기록한다.
- 함께 기록하는 값은 네 기준점의 best-fit plane RMS, 여섯 쌍의 world/depth 거리 차이,
  rigid fit RMS, 기준점별 depth-world 잔차다.
- offline regression은 camera-only 단위 테스트 28개, Python compile, diff check를 통과했다.
- 30-frame smoke에서 depth pose 30/30, rigid RMS 33.685 mm, plane RMS 2.137 mm였다.
- 300-frame stability에서 PnP/depth pose 모두 300/300, 27.586 FPS, sync delta 중앙값
  21.711 ms였다.
- 300-frame depth 결과:
  - rigid fit RMS 중앙값 33.949 mm.
  - 기준점별 잔차 중앙값 ID0=33.23, ID1=35.91, ID2=28.69, ID3=37.36 mm.
  - plane RMS 중앙값 1.994 mm.
  - depth Camera XYZ 쌍 거리−fitted world 거리: 0–1=+41.61, 0–2=+59.71,
    0–3=+58.45, 1–2=+51.37, 1–3=+71.36, 2–3=+36.87 mm.
- 네 점의 300-frame median Camera XYZ에 진단용 similarity fit을 적용하면 camera/world
  scale 1.151915(역수 0.868119), RMS 9.387 mm였다. 이는 metric reconstruction이 전체적으로
  커진 정황이지만, 줄자 한 점과도 완전히 일치하지 않아 경험적 scale은 적용하지 않았다.
- `DECISION`: full metric Camera XYZ 기반 `T_W_C`는 계속 실패 상태다. 고정 작업대 XY는
  ArUco homography, Z는 depth 평면 대비 상대 높이를 쓰는 2.5D dry-run 경로로 진행한다.
- 최신 코드는 정확도 실패로 Jetson `/tmp`에서만 검사했고 `/opt`에는 배포하지 않았다.
- 종료 후 preview service `active`, Astra·RealSense `ok=true`, LeLab health 정상,
  teleoperation·recording·inference inactive, 진단 helper 잔류 없음이 확인됐다.
