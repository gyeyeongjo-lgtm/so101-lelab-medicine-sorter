# 2026-09-28 약통 YOLO 오프라인 스모크 학습·평가

## 범위

- 사용자 정의 범위는 약국 작업대의 연구용 약통 모형 존재·위치 검출이다.
- 임의 비대상 물체 종류별 hard-negative 성능은 이번 단계 완료 조건에서 제외한다.
- 카메라·로봇 serial·토크·텔레오퍼레이션·녹화·LeLab 추론은 사용하지 않았다.

## 데이터 패키징

- `scripts/prepare_yolo_medicine_dataset.py`를 추가했다. 기존 source/output을 덮어쓰지 않고, 승인·safety flag·image hash overlap을 검사한다.
- 개별 frame 무작위 분할 대신 30초 이내 연속 촬영을 한 capture-time block으로 유지한다.
- Jetson 비 Git 경로 `/home/jetson3/so101-medicine-bootstrap/yolo-medicine-v1`에 다음 split을 생성했다.
  - train: 71장 = positive 47 + negative 24
  - validation: 18장 = positive 12 + negative 6
  - test: 11장 = positive 10 + unique empty negative 1
- train/validation/test 사이 exact image hash overlap은 모두 0이다.
- Mac의 Git 제외 경로 `datasets/yolo-medicine-v1`로 같은 패키지를 복사했다.

## 학습 환경·결과

- Mac 격리 `.venv`에 PyTorch 2.14.0, Ultralytics 8.4.163을 설치했다.
- Apple M3 MPS에서 pretrained YOLO11n, 640 px, batch 8, seed 1000으로 최대 40 epoch를 실행했다.
- early stopping 기준 best는 epoch 30이며 checkpoint는 Git 제외 경로 `models/medicine-yolo/yolo11n-smoke-v1/weights/best.pt`다.
- validation best: precision 0.995, recall 1.000, mAP50 0.995, mAP50–95 0.766.
- MPS에는 일부 연산의 deterministic implementation이 없다는 PyTorch warning이 있었으므로 seed 지정만으로 bitwise 재현성을 주장하지 않는다.

## 별도 test 결과

- best checkpoint를 CPU에서 test split 11장에 평가했다.
- test metric: precision 0.995, recall 1.000, mAP50 0.995, mAP50–95 0.798.
- 실제 사용 후보 confidence 0.25에서 positive 10/10을 각각 정확히 1개씩 검출했고, empty negative 1장에는 검출 0개였다.
- positive box IoU는 최소 0.8392, 평균 0.8937이고 최소 confidence는 0.8921이다.
- 두 prediction contact sheet를 육안 확인해 박스가 약통 모형에 위치하고 empty frame에는 박스가 없음을 확인했다.

## 제한·다음 단계

- `PASS_OFFLINE_TARGET_PRESENCE_SMOKE`로 판정한다. test negative가 1개뿐이므로 robust false-positive rate 또는 일반 환경 독립 평가를 주장하지 않는다.
- `independent_evaluation_ready=false`, `false_positive_rate_ready=false`, `robot_enabled=false`를 유지한다.
- 다음 단계는 best model을 Jetson에서 실행 가능한 형식으로 export하고, 저장 frame → live preview 순으로 검출 overlay를 검증하는 것이다. 이때도 검출 결과를 로봇 명령으로 연결하지 않는다.
- Git commit/push는 `NOT_PUSHED`다.

## ONNX export·Jetson 저장 frame 재현

- best checkpoint를 opset 17, 640×640, static shape, NMS 미포함 ONNX로 export했다. Mac/Jetson 모델 SHA-256은 `d2f8452ed72decf38198ce5aaa8d82c81397e96b85b78c449dbb73bc2cc5c846`로 일치한다.
- `scripts/detect_medicine_onnx.py`를 추가했다. OpenCV DNN으로 저장 image/file만 읽고 새 overlay·JSON 경로만 생성하며 카메라·LeLab·robot endpoint를 열지 않는다. Mac/Jetson SHA-256은 `ad800e2703496607bb2cb9dd9e64f40c5865d92eb99f44dd1ca3796f4f2b9f53`다.
- detector unit test 3개와 dataset split test 7개를 통과했다.
- Mac OpenCV DNN test 11장에서 positive 10/10 각각 1 detection, empty negative 1/1 detection 0으로 `.pt` 결과를 재현했다.
- Jetson Python OpenCV 4.12.0·NumPy 2.2.6에서 같은 저장 test 11장을 실행했고 confidence와 bbox가 Mac ONNX 결과와 일치했다.

## 단일 live snapshot 통과·상시 웹 FAIL

- 시작 전 LeLab `teleoperation_active=false`, `recording_active=false`, `inference_active=false`를 확인했다.
- 기존 Astra bridge output `/dev/video8`에서 640×480 snapshot 1장을 읽어 ONNX detector를 실행했다. 약통 모형을 confidence 0.746739, bbox `[297.419,285.299,328.151,320.921]`로 검출했고 육안으로 박스 위치가 맞았다. 화면 오른쪽 위 다른 흰 용기는 검출하지 않았다.
- `scripts/medicine_yolo_web.py`를 추가해 port 8020에서 HTML·health·detections JSON·MJPEG만 제공하고 POST와 robot control을 차단했다. 로컬 read-only UI test를 통과했다.
- 임시 foreground web smoke는 sequence 8까지 confidence 약 0.78 검출을 갱신했으나 이후 `frame read failed`로 정지했다. 따라서 상시 live preview는 `FAIL`이며 완료로 판정하지 않는다.

## Astra bridge 장애·안전 종료

- journal 최초 오류는 13:38:40 KST의 GStreamer `fdsrc0: Internal data stream error`다. 그 전 bridge는 8시간 14분 이상 실행돼 있었다.
- 이후 service restart에서 OpenNI `Failed to send a USB control request`와 `No valid frames found before end of stream`이 반복됐다. web server 종료 뒤에도 복구되지 않았고 `NRestarts=61`까지 증가했다.
- 추가 USB control 요청 반복을 막기 위해 `astra-v4l2-bridge.service`만 `stop`했다. unit은 `enabled` 그대로이며 설정 파일·USB·전원은 변경하지 않았다.
- 임시 8020 web process와 listener는 종료됐다. 종료 재확인에서 LeLab teleoperation·recording·inference는 모두 inactive다.
- `BLOCKED_USER_ACTION`: 천장 Astra USB를 현장에서 한 번 분리·재연결해야 한다. 사용자가 완료를 알리면 bridge를 다시 start하고 안정 frame 증가를 먼저 확인한 뒤 8020 smoke를 재개한다.

## USB 재연결 후 bridge 재현·직접 RGB 우회

- USB 재연결 후 Astra `2bc5:0401`이 bus 001 device 020으로 재인식됐다. 시작 전 LeLab health 정상, 세 제어 상태 inactive를 다시 확인했다.
- consumer 없이 bridge를 start해도 즉시 `fdsrc Internal data stream error`로 restart했고 restart counter는 71이 됐다. 추가 반복을 막기 위해 bridge를 stop했다.
- Astra producer 단독은 RGB888 3 frame, 2,764,800 bytes를 정상 출력했다. 동일 GStreamer parse→fakesink도 3초 동안 정상이었다.
- 반면 `/dev/video8` v4l2loopback은 Astra와 무관한 `videotestsrc` 첫 frame에서도 `No free buffer found in the pool at index 0`, `failed queueing buffer 0: Invalid argument`를 재현했다. 이 결과로 Astra USB가 아니라 v4l2loopback output 구간을 실패 지점으로 격리했다.
- 커널 모듈 재로드나 `max_buffers=2` 설정 변경은 하지 않았다. 대신 web worker가 `/opt/orbbec-openni2/bin/orbbec-rgb-pipe`의 packed RGB888을 직접 읽는 옵션을 추가했다.
- `tests/test_medicine_yolo_web.py` 3개와 `tests/test_detect_medicine_onnx.py` 3개가 통과했고 Jetson `py_compile`도 통과했다. 배포 web script SHA-256은 `5666d19b43534caf653cc8b74fc1b55a2508735013c23d3428f28925f98dd6fc`다.
- 8020 health에서 sequence 39→200→582→950, frame age 0.091–0.166 s, inference 147.3–156.2 ms를 관찰했다. 약통은 1개로 계속 검출됐고 confidence는 0.748–0.785, bbox는 약 `[297,285,328,322]`였다.
- Mac에서 `http://192.168.50.20:8020/health`로 LAN 접근도 통과했다. POST·LeLab·robot endpoint는 없고 `robot_enabled=false`다.
- 자동 브라우저는 사설 IP 8020 이동을 보안 정책으로 차단했으므로 live overlay 육안 검수는 `PENDING_USER_VISUAL` 이다. 사용자가 URL을 직접 열고 박스 위치를 확인한다.
- 현재 8020은 임시 background process로 Astra를 소유한다. bridge와 8010 프리뷰는 inactive며, 천장 사선 RealSense preview는 일시 정지다. 세 LeLab 제어 상태는 inactive이고 로봇 직렬·토크·모터 명령은 실행하지 않았다.
- 다음 순서는 live box 육안 확인 → Astra YOLO·RealSense 사선 preview 통합 → 승인 전용 dry-run table coordinate overlay다. 실제 로봇 이동은 계속 금지한다.

## 사용자 육안 통과·통합 카메라·table dry-run

- 사용자가 8020의 live 약통 box를 확인하고 `완료`로 통과시켰다. 이로써 이전 `PENDING_USER_VISUAL`은 해소됐다.
- 정면 Astra direct RGB+YOLO와 사선 RealSense `/dev/video4` YUYV 640×480을 8020 한 페이지에 통합했다. 브라우저 screenshot에서 두 실제 영상을 확인했고 두 stream의 sequence가 계속 증가했다.
- `medicine-yolo-preview.service`를 `/etc/systemd/system` 에 설치하고 enabled·active, `NRestarts=0`을 확인했다. 재부팅 경합을 막기 위해 실패한 `astra-v4l2-bridge.service`의 auto-start만 disabled했고 unit·모듈 설정은 보존했다. 8010 legacy preview도 disabled·inactive다.
- `/opt/so101-rgbd/astra_rgbd.example.json` SHA `ce43a0d0...d9e1`의 ID0–3 reference center와 pickup ROI를 사용했다. 현재 frame에서 ID0–6 모두 검출됐고 table homography가 ready다.
- YOLO 약통 2개의 bbox image center를 테이블에 투영했다. 한 개는 약 `(193.2,248.3) mm`로 pickup ROI 내부, 다른 하나는 약 `(250.4,316.0) mm`로 밖이다.
- 바구니 마커 투영값은 ID4 red 약 `(59.7,95.1) mm`, ID5 green 약 `(245.5,93.2) mm`, ID6 blue 약 `(152.6,95.8) mm`다. 화면에는 짧은 `RED/GREEN/BLUE ID` 라벨로 표시하고 정밀값은 health JSON에 남긴다.
- homography reference RMS 약 `0.000007 mm`는 네 점의 내부 재투영 오차일 뿐, 실제 로봇 절대 정확도를 의미하지 않는다. 또한 약통의 높이를 보정하지 않은 평면 투영이다.
- health는 `robot_enabled=false`, `robot_target_authorized=false`를 계속 반환한다. LeLab 세 제어 상태는 inactive고 로봇 serial·torque·motor 명령은 실행하지 않았다.
- 최종 설치 web script SHA-256은 `ae7333e26b25e6853944d88705c413198b43c663857e97037dc2fecc047c60cd`, unit은 `9656d7a4d4248bb44e30bbb677af0cf7001e7145b1b4cae36175d84cc6c434c4`다. 각 단계 설치 전 파일을 timestamp suffix로 보존했다.
- 다음 단계는 실제 TCP offset 확정과 World 4–8점 follower teach를 통한 `T_B_W` 등록이다. 이는 실제 로봇팔 구동이 필요하므로 현장 안전 확인과 새 명시 승인 전에는 `BLOCKED_APPROVAL`로 남긴다.

## 4점 World teach 준비·텔레옵 시작 실패

- `PASS (physical workspace)`: 사용자가 바구니·약통·가위를 치운 뒤 천장 정면·사선 영상에서 작업대 ID0–3과 검은 X 4개가 모두 가림 없이 보였다.
- `PASS (World point extraction)`: Astra raw RGB의 ID0–3 중심으로 homography를 계산하고 X centroid를 World mm로 투영했다. 결과는 P1=`[273.493,321.191,0]`, P2=`[54.233,314.222,0]`, P3=`[60.112,183.993,0]`, P4=`[273.586,185.970,0]` mm이며 `configs/robot_world_pairs.20260928.local.json`에 보존했다.
- `OBSERVED (capture prefix)`: `/opt/orbbec-openni2/bin/orbbec-rgb-pipe`는 stdout 맨 앞에 86-byte OpenNI warning line을 내보냈다. raw 점 추출은 이 prefix를 정확히 제거한 921,600-byte RGB888 frame으로 수행했다. 8020 프리뷰는 각 캡처 후 즉시 복구했다.
- `AUTHORIZED`: 사용자가 4점 저속 텔레오퍼레이션 teach를 명시적으로 승인했다. 시작 전 stable ID는 Leader `5AE6085272`→ACM1, Follower `5AE6058306`→ACM0이고 recording·inference·teleoperation은 모두 inactive였다.
- `FAIL (teleop start 1)`: 첫 시작은 Follower ID4 `Torque_Enable=1` write의 `There is no status packet` 오류로 종료됐고 제어 세션은 남지 않았다.
- `PASS (read-only isolation)`: 양쪽 버스 3-round `Present_Position` sync-read는 Leader/Follower 전부 성공했고 serial identity도 일치했다.
- `FAIL (teleop start 2)`: 조건을 바꾸지 않은 단 1회 재시도는 Follower ID6 `Torque_Enable=1` write의 동일한 status-packet 오류로 실패했다. 추가 재시도는 하지 않았다.
- `PASS (safe end state)`: 실패 후 Follower ID1–6 `Torque_Enable` 전부 0, teleoperation·recording·inference inactive, 8020 Astra·RealSense preview와 table homography 정상을 확인했다.
- `PASS (read-only electrical snapshot)`: 안전 상태에서 Follower ID1–6 `Present_Voltage`는 모두 raw 122(12.2 V), 온도는 34–39°C였다. 정지 시 전압·온도 이상은 관찰되지 않았지만 쓰기 응답 누락 원인이 해소된 것은 아니다.
- `BLOCKED_HARDWARE`: 쓰기 패턴에서만 ID4/ID6 응답이 누락되는 간헐 버스 문제가 남아 4점 joint sample·FK·`T_B_W` fit은 `NOT_RUN`이다. TCP는 두 그리퍼 끝 사이 중앙으로 정의했지만 gripper-link offset은 아직 미검증이다.
- `NOT_PUSHED`: 이 기록과 local calibration input은 Git commit·push하지 않았다.

## 4점 teach 수집·TCP 동시 fit 판정

- `PASS (user-started teleoperation)`: 사용자가 LeLab 8000에서 텔레옵을 정상 활성화했다. API로 teleoperation active, recording·inference inactive, 8020 두 preview·ID0–3 homography 정상을 확인했다.
- `PASS (broadcast-only capture)`: P1–P4 각각 LeLab `/ws/joint-data` 15 samples를 수집했다. 모든 점의 관절 표준편차는 방송 해상도에서 0 rad이었고 `/joint-positions`나 추가 serial access는 사용하지 않았다. 첫 capture command는 JSON boolean을 `false`로 적어 `NameError`로 출력만 실패했고, `False`로 바꿄어 같은 방송 경로로 재수집했다.
- `PASS (safe stop)`: P4 수집 즉시 `/stop-teleoperation`이 성공했고 teleoperation·recording·inference는 inactive, Follower ID1–6 torque는 모두 0, 8020 preview와 table homography는 정상이다.
- `PASS (offline FK)`: 실제 `so101_new_calib.urdf`의 `base→gripper` FK로 P1–P4 link origin·rotation을 계산했다. P1 대비 gripper-link 방향 변화는 P2 40.32°, P3 46.67°, P4 9.07°였다. 첫 importlib 실행은 module을 `sys.modules`에 등록하지 않아 dataclass import에서 실패했고, 등록 후 같은 입력으로 성공했다.
- `IMPLEMENTED`: 여러 방향의 gripper-link pose와 known World touch point에서 고정 TCP offset과 `T_B_W`를 동시 추정하는 `scripts/fit_robot_world_tcp_transform.py`를 추가했다. 실패 폐쇄 임계값과 observability condition number를 출력하며 robot motion은 항상 차단한다. synthetic recovery·high-residual reject·rotation 테스트 3/3이 통과했다. 첫 unittest module 경로 실행은 `tests` package가 아니어 import 실패했고 discovery 실행으로 통과했다.
- `REJECTED (current 4 points)`: 동시 fit은 TCP offset `[22.362,-13.767,-45.344]` mm(크기 52.399 mm), RMSE 9.572 mm, max 12.073 mm, Jacobian rank 9, condition number 7031.4였다. RMSE 5 mm·max 8 mm·condition 1000 기준을 모두 넘어 `REJECTED_NEEDS_MORE_OR_BETTER_TEACH_SAMPLES`로 판정했다.
- `MOTION_BLOCKED`: 결과는 `configs/robot_world_transform.20260928.local.json`에 `robot_enabled=false`, `motion_authorized=false`로 보존했고 실제 이동에 사용하지 않는다. 다음은 그리퍼 벌림 간격을 고정한 P1·P2 repeat sample로 P1의 Jaw 차이와 repeatability를 보강한다.
- `NOT_PUSHED`: 새 script·test·local calibration result는 Git commit·push하지 않았다.

## 고정 그리퍼 벌림 P1–P4 repeat

- `PASS (repeat capture)`: 사용자가 텔레옵을 다시 활성화한 뒤 P1·P2 repeat와 P3·P4 repeat를 두 번의 세션에서 수집했다. repeat Jaw는 P1/P2 `0.04379 rad`, P3/P4 `0.03845 rad`으로 가깝고 모든 sample은 `/ws/joint-data`로만 수집했다.
- `PASS (safe stop)`: 각 repeat 세션 후 텔레옵 종료가 성공했고 최종 확인에서 Follower ID1–6 torque 0, 세 제어 inactive, 8020 preview·ID0–3 homography 정상이다.
- `PASS (selection support)`: `fit_robot_world_tcp_transform.py`에 `fit_pair_names` 선택을 추가해 Jaw 조건이 다른 원본과 repeat를 혼합하지 않게 했다. 선택 테스트를 추가한 후 전체 4/4 테스트가 통과했다.
- `REJECTED (fixed-jaw repeats)`: repeat P1–P4 네 건만 선택한 fit은 RMSE 5.780 mm, max 6.694 mm, condition number 5887.5였다. max-error는 8 mm 이하지만 RMSE 5 mm와 condition 1000 기준을 넘어 거부했다. 원본 P1을 추가한 5건 fit도 RMSE 6.037 mm, condition 6757.2로 더 나아지지 않았다.
- `FAIL (holdout diagnostic)`: repeat-only fit에서 제외한 원본 P1–P4의 오차는 각각 9.03, 10.02, 22.31, 35.15 mm였다. Jaw가 다른 P2–P4는 엄밀한 holdout이 아니지만, 가까운 P1도 9 mm로 현 fit의 외부 정확도를 인정할 수 없다.
- `MOTION_BLOCKED`: 최종 진단은 `configs/robot_world_transform.20260928.fixed-jaw.local.json`에 `REJECTED_NEEDS_MORE_OR_BETTER_TEACH_SAMPLES`, `robot_enabled=false`, `motion_authorized=false`로 보존했다. 다음은 그리퍼를 명령으로 닫아 두 끝이 만나는 단일 TCP를 사용하고 6개 이상 분산 point를 재-teach해야 한다. 그리퍼를 손으로 억지로 닫지 않는다.
- `NOT_PUSHED`: repeat data·fit·code·test·docs는 Git commit·push하지 않았다.

## 닫힌 tip TCP용 6점 배치

- `PASS (visibility)`: 사용자가 작업대에서 손·몸을 제거한 뒤 천장 정면·사선 프리뷰에서 ID0–3과 검은 X 6개가 모두 가림 없이 보였다. P5는 안쪽 왼쪽, P6는 안쪽 오른쪽에 엇갈려 있다.
- `PASS (camera-only coordinate extraction)`: preview를 일시 중지하고 OpenNI 86-byte warning prefix를 제거한 RGB888 원본에서 ID0–3 homography와 X centroid를 계산했다. P1 `[276.693,299.484,0]`, P2 `[57.275,297.925,0]`, P3 `[60.137,167.664,0]`, P4 `[273.536,164.708,0]`, P5 `[212.898,252.880,0]`, P6 `[115.771,210.949,0]` mm이다.
- `OBSERVED (layout changed)`: 이전 4점 좌표와 비교할 때 현재 P1–P4의 World Y가 약 16–22 mm 변했다. 현재 6점은 새 layout으로 취급하고 이전 joint teach sample을 재사용하지 않는다.
- `PASS (resource recovery)`: 원본 capture 후 `medicine-yolo-preview.service`를 바로 복구했고 active를 확인했다. capture 전 teleoperation·recording·inference는 모두 inactive였다.
- `READY_FOR_TEACH`: 새 input은 `configs/robot_world_pairs.20260928.closed-tip.local.json`에 보존했다. 다음은 텔레옵 명령으로만 그리퍼를 닫아 두 fingertip의 만나는 점을 TCP로 고정하고 P1–P6를 수집하는 것이다. 손으로 그리퍼를 억지로 닫지 않는다.
- `NOT_PUSHED`: 6점 local config·기록은 Git commit·push하지 않았다.
