# 2026-09-27 약통 bootstrap 재개

## 재개 사전 점검

- 사용자가 Jetson 연결과 약통 배치를 완료했다고 알려 기존 기록부터 확인했다.
- Jetson 시간 `2026-09-27T14:54:09+09:00`, Astra·RealSense preview는 모두 `ok=true`였다.
- LeLab 상태는 `teleoperation_active=true`, `recording_active=false`, `inference_active=false`였다.
- 텔레오퍼레이션·녹화·추론을 동시에 실행하지 않는 원칙과 모터 안전 규칙에 따라 새 frame 수집, label export, 학습, 로봇 명령을 모두 실행하지 않았다. 텔레오퍼레이션도 사용자 확인 없이 임의 종료하지 않았다.
- 이전 turn에서 업로드가 중단된 `/home/jetson3/export_medicine_label_proposals_v4.py`는 존재하지 않았다. 로컬 stem-prefix 변경과 단위 테스트는 보존돼 있으나 Jetson 배포는 `NOT_DEPLOYED`다.

## 다음 단계

- 사용자가 LeLab에서 텔레오퍼레이션을 Stop하고 follower arm 정지를 현장에서 확인한다.
- 이후 상태를 다시 읽어 `teleoperation_active=false`를 확인한 다음 현재 약통 자세를 camera-only로 수집한다.
- 새 자세가 기존 양성과 충분히 다르면 접두사가 붙은 고유 stem으로 임시 양성 30번째 표본을 export한다.

## 웹 촬영·검토 방식 전환

- 사용자 요청에 따라 SSH 단건 촬영 루프를 중단하고 기존 8010 상시 프리뷰 서버에 파일 기반 검토 큐를 결합했다.
- 8010 화면은 Astra/RealSense preview, 양성·음성 촬영 버튼, ID0–3 검출, 작업영역 약통 몸통/전체 박스 제안, 기존 29개 양성 중심과의 거리, 승인/제외, 상태별 수량을 표시한다.
- 모든 원본은 `/home/jetson3/so101-medicine-bootstrap/web-review-queue-v1/`에 보존한다. 차단 항목은 승인할 수 없고, 승인 항목도 `training_ready=false`, `medicine_identity_verified=false`, `robot_target=false`다. 삭제 API는 추가하지 않았다.
- 화면 전체 HSV 검출 smoke는 Astra 보라색 tint로 로봇/배경을 오인해 실패했다. 기존 검증 검색영역 안에서만 자동 몸통을 제안하도록 수정하고, 영역 밖 추가 약통/손/가림은 썸네일 사람 검토로 남겼다.
- 배포 중 첫 install 명령에서는 보조 모듈이 설치되지 않아 새 프로세스를 재시작하지 않았다. 이를 확인한 뒤 모듈을 별도 설치하고 서비스를 재시작했다. 기존 프로세스가 계속 동작해 그 사이 preview 장애는 없었다.
- 기존 server는 `/opt/so101-camera-preview/camera_preview_server.py.pre-web-review-20260927`에 백업했다. 최종 camera server SHA-256은 `966c1c8a...6019bc`다.
- 서비스 재시작 후 8010 health에서 Astra·RealSense `ok=true`, `/api/review` 정상, 실제 브라우저에서 두 preview와 촬영/검토 UI를 확인했다.
- 현재 장면의 중앙 약통은 기존 양성과 6.265 px 차이라 `near_duplicate`로 차단됐다. 전체 화면 왼쪽의 추가 약통도 사람 검토로 확인해 해당 항목을 `excluded` 처리했다. 승인/export는 0개다.
- 별도로 `/home/jetson3/so101_vlm_capture`의 기존 3카메라 VLM 사진·동작 영상 앱이 8011에서 실행 중임을 확인했다. 기존 앱은 변경하지 않았다.

## MD 기준 World→Robot Base 준비

- 설치 LeRobot은 0.6.0이고 SO follower FK/IK processor와 `so101_new_calib.urdf`가 있다. 다만 `placo` runtime은 설치돼 있지 않아 기존 LeLab tool 환경을 변경하지 않았다.
- LeLab 텔레오퍼레이션 worker는 follower 관절값을 URDF joint radian으로 변환해 `/ws/joint-data`로 이미 방송한다. 추후 teach는 이 broadcast를 사용해 serial bus 소유자를 추가하지 않는다.
- 현재 stable USB 역할은 `5AE6085272` Leader→ACM1, `5AE6058306` Follower→ACM0이다. LeLab record의 raw port는 현재 열거와 일치하므로 수정하지 않았다.
- `scripts/urdf_forward_kinematics.py`와 단위 테스트 3/3을 추가했다. Jetson 실제 URDF에서 `Rotation→Pitch→Elbow→Wrist_Pitch→Wrist_Roll` 체인을 확인했고 zero pose gripper link 원점은 `[20.615,-277.473,266.852]` mm, rotation determinant는 1.0이었다.
- `scripts/fit_robot_world_transform.py`, `configs/robot_world_pairs.example.json`, 단위 테스트 3/3을 추가했다. 4–8개 점의 rigid `T_B_W`, RMSE, 최대 오차, point별 residual을 계산하지만 항상 motion을 차단한다.
- 두 도구를 `/home/jetson3/so101-calibration/`에 배포하고 문법/help/hash를 확인했다. 실제 point pair 입력과 transform fit은 `NOT_RUN`이다.
- 다음 단계는 실제 gripper-tip TCP offset을 정의하고 follower TCP를 4–8개 World 기준점에 teach하는 것이다. 이는 텔레오퍼레이션과 실제 모터 이동을 포함하므로 현장 안전 확인과 사용자 명시 승인 전에는 실행하지 않는다.
- 종료 시 두 preview 정상, LeLab teleoperation·recording·inference inactive였다. Git commit/push `NOT_PUSHED`다.

## 안전 높이 텔레오퍼레이션·FK dry run

- 사용자가 `진행`으로 실제 구동을 승인했다. 시작 직전 Astra·RealSense preview 정상, teleoperation·recording·inference inactive, stable USB 기준 Leader `5AE6085272→ACM1`, Follower `5AE6058306→ACM0`를 재확인했다.
- 첫 `/move-arm`은 Follower ID4 `Lock` write에서 `There is no status packet`으로 실패했다. 제어 세션은 남지 않았다. bus를 움직이지 않는 broadcast ping에서 ID1–6이 모두 model 777로 응답해 영구 ID 설정 오류가 아님을 확인했고, 한 번만 재시도했다.
- 두 번째 `/move-arm`은 성공했고 Follower 관절 radian 1세트를 얻었다. 그러나 `/joint-positions` REST 호출이 worker와 같은 serial port를 동시에 사용해 `Goal_Position ... Port is in use`가 발생했고 LeLab이 텔레오퍼레이션을 자동 종료했다.
- 충돌 후 추가 구동은 하지 않았다. 다음 teach 구현은 LeLab이 이미 내보내는 `/ws/joint-data` WebSocket broadcast만 구독하며 `/joint-positions`는 사용하지 않는다.
- 관절 샘플을 `configs/fk-safe-pose-20260927.json`에 `use_for_robot_world_fit=false`로 저장하고 Jetson `/home/jetson3/so101-calibration/`에도 복사했다. 오프라인 URDF FK의 `base→gripper` link origin은 `[12.807,-117.958,127.822]` mm다.
- 이 좌표는 검증된 gripper-tip TCP가 아니고 알려진 World 기준점과도 연결되지 않았다. 따라서 실제 `T_B_W` pair와 fit은 `NOT_RUN`이다.
- 종료 재점검에서 두 preview `ok=true`, teleoperation·recording·inference 모두 inactive였다. Git commit/push는 `NOT_PUSHED`다.

## 8010 읽기 전용 관절 모니터

- `scripts/camera_preview_server.py`의 기존 8010 화면에 LeLab `/ws/joint-data` WebSocket만 직접 구독하는 패널을 추가했다. 관절 6개를 radian으로 표시하고 현재 sample JSON을 복사할 수 있다.
- copied JSON에는 `use_for_robot_world_fit=false`와 TCP/World point 미부착 경고가 들어간다. 페이지에는 `/joint-positions`, `/move-arm`, `/stop-teleoperation` 경로가 없다.
- `tests/test_camera_preview_joint_ws.py`를 추가했고 medicine review/FK/rigid-fit 회귀를 포함해 11개 테스트가 통과했다.
- Jetson 설치 전 기존 server를 `/opt/so101-camera-preview/camera_preview_server.py.pre-joint-ws-20260927T1532`로 백업했다. 설치 SHA-256은 `b1286a8a...943`이다.
- 서비스 재시작 뒤 두 preview `ok=true`, 브라우저에서 `WebSocket 연결됨 · 텔레오퍼레이션 관절 방송 대기`를 확인했다. 이번 배포 과정에서는 로봇 제어·토크·USB를 건드리지 않았다.
- 다음 단계는 TCP를 물리적으로 정의한 뒤, 8010 패널을 사용해 4–8개 분산 World teach point의 관절 sample을 수집하는 것이다. 실제 teach와 `T_B_W` fit은 아직 `NOT_RUN`이다.

## 추가 웹 수집 비파괴 감사·통합

- 추가 수집 뒤 8010 queue는 total 240, approved 52, excluded 57, blocked 131이었다. metadata 기준 approved는 positive 32, negative 20이다.
- 기존 `provisional-fullframe-combined-v2`는 positive 29, diverse negative 4이며 웹 승인본과 exact image duplicate는 없었다.
- 최초 임시 positive proximity 명령은 normalized label 값을 string 상태로 거리 계산해 `TypeError`로 실패했다. float 변환 후 전체 positive 61개 중 12px 미만 연결 component는 47개였고, 중복은 모두 기존 legacy positive 내부에 있었다.
- `scripts/prepare_medicine_training_candidates.py`와 단위 테스트를 추가했다. source pair/640×480/class-0 normalized label/safety flag를 검사하고, 양성 중심 12px cluster에서 사람 검토 우선·선명도 순으로 대표를 고르며 exact image hash도 검사한다. medicine review와 joint UI 회귀를 포함해 9개 테스트가 통과했다.
- Jetson 도구 SHA-256은 `56b244cd...bae6`이다. 새 비 Git 출력 `/home/jetson3/so101-medicine-bootstrap/training-candidates-audit-v1`에 input 85, kept positive 47, negative 24, excluded 14를 생성했다. 원본 경로는 수정하거나 삭제하지 않았다.
- output의 images/labels/metadata가 각각 71개로 일치한다. `audit.json`은 `training_ready=false`, `independent_evaluation_ready=false`, `robot_enabled=false`다.
- 양성·음성 접촉시트를 Mac `artifacts/training-candidates-audit-v1-reports/`로 복사해 시각 검사했다. 양성 bbox는 약통 전체에 맞았다. 음성은 기존 empty/직사각형/펜/휴대폰과 웹 음성이며, 일부 웹 음성은 서로 유사하므로 24개를 모두 독립 장면으로 보지 않는다.
- 다음 데이터 단계는 현재 후보와 섞이지 않는 별도 촬영 세션의 독립 평가 표본이다. 같은 장면의 frame random split은 독립 평가로 사용하지 않는다. 종료 시 두 preview 정상, LeLab 세 제어 inactive, 로봇·토크·USB·전원 조작 없음이다.

## 8010 독립 평가 큐

- 기존 학습 후보 버튼을 계속 사용할 때 평가 frame까지 같은 queue에 섞이는 문제를 막기 위해 8010에 별도 평가 패널을 추가했다.
- 평가 원본/overlay/metadata/export는 비 Git `/home/jetson3/so101-medicine-bootstrap/evaluation-web-v1`에만 저장된다. 현재 training audit 경로를 reference positive로 사용하므로 12px 이내 양성 위치는 `near_duplicate`로 차단된다.
- 페이지에는 `평가 양성 촬영`, `평가 음성 촬영`, 평가 전용 승인/제외와 별도 통계가 있다. 로봇 제어 endpoint는 추가하지 않았다.
- 회귀 테스트 10개 통과 후 server SHA `18e4da82...4171`을 설치하고 이전 파일을 `.pre-eval-queue-20260927T1600`으로 백업했다.
- 첫 restart 묶음 명령 뒤 기존 process가 유지돼 `/api/eval/review`가 404였다. service restart를 단독으로 다시 실행한 뒤 두 preview 정상, evaluation API 200, empty counts, 브라우저 평가 패널을 확인했다.
- 종료 시 teleoperation·recording·inference 모두 inactive다. 다음 사용자 작업은 학습 위치와 겹치지 않는 평가 양성 10개와 서로 다른 음성 5개를 새 평가 버튼으로 촬영·승인하는 것이다.

## 추가 수집 구제·v2 감사

- 추가 촬영분은 새 `evaluation-web-v1`이 아니라 기존 `web-review-queue-v1`에 들어갔다. 큐는 total 390, approved 70, excluded 58, blocked 262였고 승인 세부는 positive 44·negative 26이다. 직전 기록 대비 positive 12개·negative 6개가 추가됐다.
- 추가분을 버리지 않고 기존 legacy와 함께 비파괴 `/home/jetson3/so101-medicine-bootstrap/training-candidates-audit-v2`로 다시 준비했다. 결과는 input 103, kept positive 59, negative 30, excluded 14이다.
- v2 `audit.json`은 `training_ready=false`, `independent_evaluation_ready=false`, `robot_enabled=false`를 유지한다. 양성 접촉시트의 bbox는 연구용 약통 모형과 일치했다. 음성 접촉시트의 일부는 full-frame 가장자리에 손과 작은 물체가 보여, 약통 모형이 화면 안에 남은 frame이 있는지 개별 재검수해야 한다.
- Mac으로 `artifacts/training-candidates-audit-v2-reports/` contactsheet·audit JSON을 복사했다. 원본 v1/v2 큐와 생성물은 삭제하지 않았다.

## 학습 촬영 닫기·평가 전용 UI

- 같은 혼동이 반복되지 않도록 8010 화면의 기존 학습 양성/음성 촬영 버튼을 disabled로 바꾸고, 아래 `평가 양성 촬영`·`평가 음성 촬영`만 사용하도록 문구를 바꿘다.
- 기존 server는 `/opt/so101-camera-preview/camera_preview_server.py.pre-eval-only-20260927T1632`로 보존했다. 새 설치 파일 SHA-256은 `5b0491f3515366a1241c79c461b13c4796817c626aab4b821c8d7d627c194cd0`이다.
- service를 단독 restart한 뒤 process 시작 시간 갱신, 두 preview `ok=true`, 평가 API total 0을 확인했다. 브라우저에서 학습 버튼이 disabled이고 평가 버튼은 enabled인 것을 확인했다.
- 종료 시 LeLab teleoperation·recording·inference는 모두 inactive였다. 로봇 제어·토크·USB·전원은 건드리지 않았다. 독립 평가 표본은 아직 0개이며 다음 필요한 사용자 작업은 평가 양성 10개·평가 음성 5개 촬영·승인이다.

## 평가 near-duplicate 완화 준비·네트워크 대기

- 사용자가 평가 양성의 `near_duplicate` 차단이 과도하다고 보고했다. 확인 시 평가 큐는 total 19, approved negative 5, blocked positive 14였다.
- positive 14개 중 11개는 `near_duplicate`, 3개는 `workspace_target_count_not_one`이었다. 11개의 최근접 중심 거리는 2.915–10.966 px였고 실제 화면 검수에서 약통 위치가 분산돼 있고 bbox도 정상이었다.
- `MedicineReviewStore` constructor에 queue별 `near_duplicate_px`를 추가했다. 기존 학습 큐는 12 px를 유지하고 평가 큐는 3 px를 사용하도록 로컬 server를 수정했다. UI 안내도 위치/회전/자세 변화와 손 제거를 명시했다.
- 기존 11개 중 3 px 이상인 10개를 `pending_review`로 복구하고 2.915 px 1개는 blocked로 남길 계획을 세웠다. 자동 승인은 하지 않고 UI 검수 후 승인한다.
- 배포 직전 Jetson `192.168.50.20` SSH와 8010이 동시에 timeout으로 변했다. 브라우저는 `ERR_CONNECTION_TIMED_OUT`, SSH는 connect timeout을 보고했다. 따라서 이 수정은 `NOT_DEPLOYED`, 기존 metadata 재분류는 `NOT_RUN`이며 Jetson Wi-Fi/전원 복구가 필요하다.

## 평가 3 px 배포·기존 표본 복구

- 사용자의 재연결 후 SSH가 복구됐고 LeLab teleoperation·recording·inference는 모두 inactive였다. 8010 service는 17:45부터 inactive였다.
- 기존 evaluation queue 전체를 `/home/jetson3/so101-medicine-bootstrap/evaluation-web-v1.pre-eval-3px-20260927T2019`로 보존했다. 기존 server/module은 각각 `.pre-eval-3px-20260927T2019`로 보존했다.
- 첫 복수 설치 명령은 백업만 실행되고 설치가 반영되지 않았다. hash 검증으로 즉시 발견하고 service를 중지한 뒤 두 파일을 각각 설치했다. 최종 server/module SHA-256은 `6c912bc7fe7aab68e389623312e29e899b4030840e8c57264284f0702ed201a0`, `f0c9160a9867ee9a2b128b47e0b6c27b31415b19fba06c0894e1f2563f757689`이다.
- `scripts/reclassify_evaluation_near_duplicates.py`를 추가했다. dry-run과 apply 모두 3 px 이상 10개를 복구 대상, 2.915 px 1개를 차단 유지로 일치했다. apply는 `recheck_history`를 남기고 `pending_review`만 설정했으며 승인/export는 하지 않았다.
- 부브라우저에서 3 px 안내, pending 10, approved 5, blocked 4를 확인했다. 후속 승인 상태는 원격 metadata/export로 교차 확인했으며 approved positive 10·negative 5, export 세 폴더 각 15개, non-empty positive label 10개·empty negative label 5개였다.
- 평가 양성 내부 pairwise 중심 비교의 최솟거리는 1 px였다. 해당 두 표본 중 `20260927T074028_614344Z` bbox crop이 Laplacian variance 2974.911로 `20260927T073948_405741Z` 2776.703보다 선명했다. 원본은 보존하고 최종 평가 선정에서만 뒤 frame을 제외한다.
- 따라서 최종 독립 평가에 쓸 수 있는 현재 수량은 positive 9 + negative 5다. 새 위치/자세의 positive 1개만 더 촬영·승인하면 목표 10+5를 채운다.
- 8010 service는 active로 복구됐고 Astra는 frame 증가와 `ok=true`다. RealSense canonical video4는 LeLab uvicorn PID 239863이 점유 중이어 8010에서 open 실패했다. LeLab 정지·USB 재연결은 수행하지 않았다.

## 재연결 후 추가 평가 양성 시도

- 20:25 KST 재점검에서 8010과 Astra·RealSense가 모두 정상이고 LeLab teleoperation·recording·inference가 inactive임을 확인했다.
- 현재 Astra 화면의 약통을 새 위치 표본으로 촬영하려 했으나, 요청 직전 8010 service가 외부 SIGTERM으로 정상 종료돼 첫 UI 클릭은 저장되지 않았다. service를 다시 시작했으며 로봇·토크·USB·LeLab 제어는 건드리지 않았다.
- 재시작 뒤 Astra는 정상 복구됐지만 RealSense는 LeLab과의 장치 소유권 충돌로 open 실패했다. 평가 촬영에는 Astra만 사용했다.
- 평가 양성 `20260927T112718_990769Z`를 저장했으나 `workspace_target_count_not_one`으로 blocked됐다. marker 0–3은 모두 검출됐지만 약통 색상 본체 후보가 0개였다. 원본은 보존하고 승인/export하지 않았다.
- 화면상 약통이 follower gripper 바로 아래에 있고 색상 면이 거의 보이지 않아, 사용자에게 약통을 그리퍼 그림자 밖의 새 위치로 옮기고 색상 면이 천장 카메라를 향하게 한 뒤 손을 빼도록 요청해야 한다.

## 평가 양성 목표 달성·음성 다양성 재감사

- 사용자 재배치 뒤 `20260927T112957_608824Z`를 촬영했다. marker 0–3, 몸통 후보 `[[383,241,17,20]]`, bbox `[378,223,27,41]`, 기존 학습 양성 최근접 거리 12.54 px였고 overlay 박스가 약통 전체에 맞아 승인했다.
- 평가 승인 큐는 positive 11·negative 5가 됐다. 기존 1 px 양성 중복에서 덜 선명한 `20260927T073948_405741Z`만 최종 선정에서 제외하면 positive 10은 충족한다.
- `scripts/prepare_medicine_evaluation_set.py`를 추가해 승인 상태, human review, 640×480 pair, safety flag, positive 중심 중복, negative dHash 장면 중복을 검사하도록 했다. Jetson 설치 SHA-256은 `78f603ba40e73922264b816efae201f1d722587dd44e69dfa6b6206464f3c288`이다.
- 최초 평가 초안은 positive 10·negative 5로 생성됐지만 접촉시트에서 음성 5개가 같은 빈 장면의 연속 frame임을 발견했다. pairwise dHash 거리는 1–6이었다.
- 잘못된 완료 상태를 남기지 않도록 초안은 비파괴 `evaluation-final-v1-rejected-negative-duplicates`로 이름을 바꾸고 audit status를 `REJECTED_NEGATIVE_SCENE_NEAR_DUPLICATES`, `independent_evaluation_ready=false`로 정정했다. Mac 접촉시트도 같은 rejected 이름으로 보존했다.
- 음성 dHash 중복 검사를 적용한 v2 준비는 `positive=10 negative=1`로 의도대로 실패했고 `evaluation-final-v2`는 생성되지 않았다. 최종 독립 평가 완료에는 서로 다른 hard-negative 장면 4개가 더 필요하다.
- 종료 점검 중 8010이 다시 내려간 원인을 journal에서 확인했다. 20:31 KST 다른 Jetson TTY 세션이 Astra V4L2 loopback 설정과 `astra-v4l2-bridge.service`를 설치하면서 `systemctl disable --now so101-camera-preview.service`를 명시적으로 실행했다. 이는 camera server 자체 장애가 아니다.
- 현재 `astra-v4l2-bridge.service`는 `/opt/orbbec-openni2/bin/orbbec-rgb-pipe | gst-launch ... v4l2sink device=/dev/video8`로 active다. 충돌 방지를 위해 8010을 재시작하거나 bridge·LeLab·USB를 변경하지 않았다. 8000만 listen 중이며 8010/8011은 내려가 있다.

## 약국 대상 검출 범위 정정·YOLO 패키징 준비

- 사용자는 기본 장면이 약국이며 현재는 약통만 대상으로 삼으므로 임의 비대상 물체가 올라간 장면의 종류별 hard-negative 성능은 중요하지 않다고 범위를 명시했다.
- 이 기준으로 `training-candidates-audit-v2` 음성 접촉시트 30장을 다시 검토했다. 손·펜·휴대폰 등은 일부 보이지만 작업영역에 목표 약통 모형이 남아 있는 음성은 발견하지 않았다. 이전 negative scope 재검토 요구와 서로 다른 hard-negative 4개 추가 요구는 현재 범위에서 superseded다.
- 평가 승인본은 양성 중심 3 px와 음성 dHash 기준을 그대로 적용해 `/home/jetson3/so101-medicine-bootstrap/evaluation-final-v2`에 positive 10·고유 empty negative 1로 비파괴 준비했다. audit는 `evaluation_profile=pharmacy_target_presence_smoke`, `smoke_evaluation_ready=true`, `independent_evaluation_ready=false`, `false_positive_rate_ready=false`, `robot_enabled=false`다.
- 이 test set은 약통 존재·위치 검출 파이프라인 스모크에는 사용할 수 있지만 robust false-positive rate나 일반 환경 독립 평가에는 사용할 수 없다.
- 다음 offline 단계로 `scripts/prepare_yolo_medicine_dataset.py`를 추가한다. training 후보를 개별 frame random split하지 않고 30초 이내 연속 촬영 block 단위로 train/validation에 분리하며, evaluation-final-v2는 test 전용으로 복사한다. 기존 source는 수정하지 않고 기존 output을 덮어쓰지 않는다.
