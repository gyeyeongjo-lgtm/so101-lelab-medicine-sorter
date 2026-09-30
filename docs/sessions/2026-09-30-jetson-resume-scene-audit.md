# 2026-09-30 Jetson 재연결과 6점 teach 전 장면 감사

## 범위

- Mac에서 기존 확인된 SSH host key로 `jetson3@192.168.50.20`에 접속했다.
- 로봇 모터·토크·USB·전원·캘리브레이션·시스템 서비스를 변경하지 않았다.
- LeLab API, 서비스/USB metadata, 기존 카메라 preview, 저장된 ONNX 모델로 읽기 전용 검사만 했다.

## Jetson·LeLab 상태

- `PASS`: Jetson SSH 22와 LeLab `/health`가 응답했다.
- `PASS`: `/teleoperation-status`, `/recording-status`, `/inference-status`는 모두 active=false였다.
- `NOT_VERIFIED`: Follower ID1–6 torque register는 직접 읽지 않았다. inactive 표시만으로 torque 0을 단정하지 않는다.
- `PASS`: canonical by-id는 Leader `5AE6085272`→ACM1, Follower `5AE6058306`→ACM0였고 저장된 `so-101.json`의 leader/follower port는 각각 ACM1/ACM0였다.
- `PASS`: 저장 camera record는 ceiling_vertical index 8, ceiling_oblique index 4, end_effector index 6으로 3대다.
- `OBSERVED`: Astra→V4L2 bridge는 active, 8020 YOLO preview는 inactive다. LeLab 8000의 `/camera-preview/8`과 `/camera-preview/4`는 실제 MJPEG 프레임을 반환했다. 이 소유권 상태는 변경하지 않았다.
- `OBSERVED`: recording status에 2026-09-28에 시작된 다른 3-camera session 이름이 남아 있었다. 실제 저장 데이터 무결성은 이 점검 범위에서 `NOT_VERIFIED`다.

## 현재 장면의 camera-only 검사

- Astra 정면 640×480 프레임에서 ArUco `DICT_4X4_50` ID0–6이 모두 검출됐다.
- 기존 `best.onnx`를 저장 프레임에만 실행해 약통 모형 3개의 bbox/confidence 0.873369, 0.722266, 0.540081을 얻었다.
- 기존 ID0–3 중심 homography로 bbox 중심을 작업대 평면에 투영한 값은 약 `(255.2,254.6)`, `(81.3,262.6)`, `(174.6,249.3)` mm다. 물체 높이와 카메라-로봇 변환이 미보정이므로 로봇 목표가 아니다.
- 바구니 마커의 영상 좌우 순서는 ID5·ID6·ID4였다. 사선 영상의 실제 색은 초록·파랑·빨강이어서 기존 ID↔색상 매핑과 일치했다. 정면 Astra의 보라색 tint만으로 색을 해석하지 않는다.
- 단일 프레임 검사는 300-frame 안정성이나 실제 약품 식별을 의미하지 않는다.

## teach 재개 판정

- `UNVERIFIED_TEACH_LAYOUT`: 약통 3개와 바구니 3개가 2026-09-28의 검은 X 6점을 가려 중심 위치 유지 여부를 확인할 수 없다. 그때의 P1–P6 world 좌표는 재검증 전 현재 로봇 calibration에 재사용하지 않는다.
- 이전 fixed-Jaw 4점 fit은 RMSE 5.780 mm, condition number 5887.5로 거부된 상태다. `T_B_W`와 TCP를 실제 이동에 사용하지 않는다.
- `NEXT`: 사용자가 작업대의 약통·바구니를 잠시 치우고 X 6개를 다시 노출하면 새 정면 프레임에서 marker ID0–3과 X 6개를 확인한 뒤 World 좌표를 재추출한다. 그 다음 현장 안전 확인 범위에서 닫힌 fingertip TCP의 P1–P6 teach를 진행한다.

## 실패·제한

- 첫 SSH key-only 시도는 password 인증이 필요해 실패했으며, 기존 대화에서 승인된 SSH 인증으로 접속했다.
- 첫 robot-record 구조 출력은 `leader_config`를 dict로 가정해 `AttributeError`를 냈다. 실제 설치 파일의 schema에 맞춰 `leader_port`/`follower_port`만 다시 읽어 확인했다. 설정 변경은 없었다.
- 사선 MJPEG의 첫 프레임은 녹색 초기화 화면이었다. 같은 수신 구간의 후속 프레임에서 실제 장면을 확인했다.
- browser automation은 LAN 프리뷰 URL을 `ERR_BLOCKED_BY_CLIENT`로 차단했다. 기존 HTTP 프레임을 읽어 offline으로 영상과 ID를 확인했다.

Git commit/push: `c83f537`을 `origin/fix/usb-recording`에 push 완료. 이 문장의 결과 기록은 후속 문서 커밋에 포함한다.

## X 재노출 후 정면 프리뷰 확인

- 사용자가 X를 다시 보이게 조정했다. Mac에서 LeLab `/health` HTTP 200과 `/camera-preview/8`의 새 MJPEG 640×480 정면 프레임을 읽기 전용으로 확인했다.
- 단일 프레임 육안 검사에서 검은 X 6개와 작업대 모서리의 ArUco 4장이 화면에 보였다. 바구니는 작업대에 없고 약통 모형 1개가 중앙에 남아 있다.
- 이번 확인은 marker ID 자동 판독, X 중심 World 좌표 재추출, 로봇 teach 및 변환 적합을 수행하지 않았다. 기존 `T_B_W` 거부와 `robot_enabled=false`는 그대로다.
- X는 robot-world teach를 위한 임시 접촉점이다. 6점 teach와 적합 검증을 통과한 뒤 X 테이프를 치워 바구니 공간을 확보할 수 있다. 작업대 기준 ID0–3은 유지하며, 바구니 복귀 시 ID4–6 검출과 빨강/초록/파랑 매핑을 다시 확인한다.
- 모터·토크·USB·전원·서비스 설정 변경은 없었다. 실제 접촉 teach는 현장 안전 확인과 별도 명시 승인 전까지 `NOT_RUN`이다.

## X 6점 World 좌표 재측정

- LeLab 정면 `/camera-preview/8`에서 약 5초간 MJPEG 132프레임을 읽었다. OpenCV 5.0.0 `DICT_4X4_50`으로 ID0–3 모두 판독된 프레임은 82개다. 나머지 50개는 한 개 이상 누락돼 좌표 계산에서 제외했다.
- 각 유효 프레임에서 X 6개를 알려진 좁은 영상 영역의 검은 연결 성분으로 추출했다. `configs/astra_rgbd.example.json`의 ID0–3 실측 중심 좌표를 이용해 프레임별 homography를 만들고 X 중심의 World mm 중앙값을 계산했다.
- P1 `[276.093,297.597]`, P2 `[57.433,297.973]`, P3 `[59.713,168.125]`, P4 `[272.714,163.633]`, P5 `[212.448,251.704]`, P6 `[115.971,210.738]` mm. 2026-09-28 보존값 대비 점별 최대 차이는 P1 약 1.98 mm다. 점별 시간 RMS 변동은 0.215–0.434 mm다. 이는 영상 내 안정성이며 물리 절대 정확도는 아니다.
- 이전 입력을 덮어쓰지 않고 `configs/robot_world_pairs.20260930.closed-tip.local.json`에 새 pixel/World 값과 `robot_enabled=false`, `motion_authorized=false`, `teach_result=NOT_RUN`을 기록했다. 이 로컬 파일은 Git ignore 대상이므로 정확한 수치는 이 세션 문서에도 남긴다.
- 추출 후 LeLab `/health` 정상, teleoperation·recording·inference는 모두 active=false였다. recording status에 `current_phase=preparing`, `session_ended=false`가 남아 있어 내부 세션 정리 완료는 확인하지 않았다. 서비스·로봇·USB를 변경하지 않았다.
- 다음 실제 teach 전에 사용자가 중앙 약통 모형을 치우고 손·사람이 팔 작업 범위 밖에 있는지, 팔 지지와 즉시 중단 방법을 현장에서 확인해야 한다. 모터·토크 동작에 대한 새 명시 승인 전까지 teach는 `NOT_RUN`이다. 이전 거부된 `T_B_W`를 실제 이동에 사용하지 않는다.

## 6점 teach 승인 후 안전 preflight

- 사용자가 "6점 저속 텔레옵 teach 승인"을 명시했다. 시작 전 정면 MJPEG를 두 차례 새로 읽어 중앙 약통 모형이 치워졌고 X 6개가 노출된 것을 확인했다.
- 두 영상 모두 사람의 몸이 follower arm 뒤쪽 가까이에 보였다. 리더 조작자가 팔로워의 실제 이동 범위 밖에 있는지 영상만으로 확정할 수 없어 텔레옵 시작을 보류했다. 현장 위치와 즉시 중단 수단에 대한 사용자 확인이 필요하다.
- LeLab `/health` 정상, `/teleoperation-status`, `/recording-status`, `/inference-status`의 active는 모두 false였다. recording status의 `current_phase=preparing`, `session_ended=false`는 계속 남아 있지만 active는 false다.
- 현재 설치 OpenAPI를 읽어 `/move-arm`이 실제 텔레옵 시작 API이고 필수 입력이 leader/follower port와 config임을 확인했다. 실제 `so-101` record는 leader ACM1, follower ACM0, 두 config `so-101.json`이다. 이번 점검은 serial bus를 열지 않았다.
- `/move-arm` 또는 로봇 이동·토크·전원·USB·서비스 변경 요청은 하지 않았다. P1–P6 joint sample과 transform fit은 `NOT_RUN`; `robot_enabled=false` 유지.

## 6점 teach 텔레옵 시작과 안전 중단

- 사용자는 팔로워 이동 범위 밖에 있고 중단 준비가 됐다고 확인했다. 이어 리더·팔로워 시작 자세를 맞췄고 기존 텔레옵에서 리더를 천천히 조작하는 방식에 동의했다. OpenAPI에는 별도의 속도 상한 인자가 없으므로 소프트웨어 속도 제한을 적용했다고 주장하지 않는다.
- 시작 직전 LeLab teleoperation·recording·inference 모두 inactive였다. 저장된 `so-101`의 leader ACM1, follower ACM0, config `so-101.json`을 그대로 사용해 `/move-arm`을 단 한 번 호출했다. HTTP 200 `Teleoperation started successfully`, active=true, `/ws/joint-data`에서 `Rotation`, `Pitch`, `Elbow`, `Wrist_Pitch`, `Wrist_Roll`, `Jaw` 방송 3건을 확인했다. 별도 serial reader와 `/joint-positions`는 사용하지 않았다.
- 사용자가 P1 위치를 물었고 리더 조작은 아직 하지 않았다고 밝혔다. 사용자가 보고 있는 인앱 웹 URL은 `192.168.50.22:8020`으로, 실제 제어 중인 LeLab `192.168.50.20:8000`과 주소가 달랐다. Mac의 `.22:8020/health`는 timeout이어서 같은 작업대 화면인지 확인되지 않았다.
- 위치·화면 혼동 상태에서는 teach를 진행하지 않고 `/stop-teleoperation`을 1회 호출해 HTTP 200 `Teleoperation stopped successfully`를 받았다. 종료 후 teleoperation·recording·inference active=false를 확인했다. follower torque register는 직접 확인하지 않아 `NOT_VERIFIED`다.
- P1–P6 관절 sample 0개, TCP·`T_B_W` 적합 `NOT_RUN`, 실제 이동 승인 없음, `robot_enabled=false` 유지. 정면 카메라 기준 X 배열은 위쪽 P1/P2, 아래쪽 P4/P3이고 follower arm은 영상의 위쪽에 보인다. P1은 영상 왼쪽 위, ArUco ID2 바로 오른쪽 X다. 같은 기준 화면을 사용자와 확인하기 전 재시작하지 않는다.

## 동일 화면 확인 후 6점 teach 수집

- 사용자가 P1을 `192.168.50.20:8000/camera-preview/8` 정면 화면의 ID2 오른쪽 X로 확인했고 기존 안전·자세·텔레옵 방식 승인을 유지했다. 재시작 직전 정면 영상의 작업대 중앙이 비었고 세 제어 작업 모두 inactive였다.
- 저장된 `so-101` leader ACM1/follower ACM0/config `so-101.json` 그대로 `/move-arm` 1회 HTTP 200, teleoperation active를 확인했다. LeLab OpenAPI에는 속도 상한 인자가 없으므로 사용자에게 리더를 천천히 조작하도록 안내했다.
- 사용자가 각 X 접촉을 확인한 뒤 `/ws/joint-data` 15개씩만 읽었다. 첫 P1 후보는 손끝 위치 재정렬 전 샘플로 제외하고, 재정렬 P1 및 P2–P6의 총 90개를 채택 후보로 로컬 입력 파일에 보존했다. 모든 점의 방송 중 최대 관절 표준편차는 수치 반올림 수준(≤2.3e-16 rad), Jaw 범위는 0.082246–0.087587 rad(폭 0.005341 rad)였다. serial bus를 추가로 열거나 `/joint-positions`를 호출하지 않았다.
- 정면 영상에서 P1–P5 손끝은 각 X 부근에 있었으나 일부 시점에서 손끝 간 틈처럼 보였다. 사용자는 P4에서 두 손끝이 실제로 서로 맞닿는다고 확인했다. 영상만으로 TCP의 반복 가능한 단일 물리점과 테이블 접촉 오차를 입증한 것은 아니다. P6는 사용자 접촉 확인과 방송값을 받았으며, 종료 후 영상은 이미 팔이 작업대 위에서 물러난 상태라 P6 접촉 프레임 검증은 `NOT_VERIFIED`다.
- P6 방송 직후 `/stop-teleoperation` HTTP 200을 받았다. 종료 확인에서 LeLab `/health` 정상, teleoperation·recording·inference 모두 active=false였다. follower torque register는 직접 읽지 않아 `NOT_VERIFIED`다. 원본 카메라 녹화나 실제 물체 이동은 하지 않았다.

## FK·TCP·World→Base 오프라인 적합 판정

- Jetson에 설치된 LeLab의 `so101_new_calib.urdf`를 Mac 임시 폴더로 읽기 전용 복사했다. SHA-256 `443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236`; `base→gripper` 체인의 zero-pose `[20.615,-277.473,266.852]` mm가 이전 기록과 일치했다.
- 기존 `urdf_forward_kinematics.py`의 FK와 `fit_robot_world_tcp_transform.py`의 동시 fit으로 6점 결과는 `REJECTED_NEEDS_MORE_OR_BETTER_TEACH_SAMPLES`다. RMSE `13.377 mm`(허용 5), 최대 `19.111 mm`(허용 8), 조건수 `6250.9`(허용 1000), rank 9, TCP offset norm `75.409 mm`. 점별 residual P1–P6은 약 `7.260,16.068,19.111,15.811,10.498,6.115 mm`다. 조건수는 파라미터 단위/스케일에도 좌우되므로 이것만으로 원인을 확정하지 않으며, 위치 오차 기준 자체가 명확히 실패했다.
- 한 점씩 제외한 여섯 번의 오프라인 fit에서도 RMSE가 `9.472–14.268 mm`, 조건수 `5997.7–11237.9`로 모두 거부됐다. 하나의 명백한 이상점만 제거해 해결되지 않는다.
- Astra intrinsic을 기존 MJPEG 좌표에 적용해 6개 World 점을 다시 투영했을 때 변화는 각 점 최대 약 2.75 mm였고, 그 좌표의 fit도 RMSE `13.179 mm`로 거부됐다. 렌즈 왜곡만으로 설명되지 않는다.
- 새 `scripts/fit_robot_world_from_joint_samples.py`는 방송 sample 안정성·고정 Jaw·motion 차단을 검증한 뒤 실제 URDF FK와 기존 fit을 재사용한다. 로컬 거부 결과 `configs/robot_world_transform.20260930.closed-tip.local.json`에 입력·URDF SHA, `robot_enabled=false`, `motion_authorized=false`를 기록했다. 신규 입력 검사 4/4, 기존 fit 4/4, FK 3/3 단위 테스트가 통과했다. 거부된 변환은 로봇 목표 좌표로 사용하지 않는다.
- 다음은 동일한 단일 접촉점을 눈으로 명확히 확인할 수 있도록 한 고정 fingertip 끝 또는 탈착 포인터를 TCP로 정하고, 손목 방향 다양성과 독립 holdout을 포함한 teach를 재설계하는 것이다. 새 현장 준비·안전 승인 전 추가 모터 동작은 `NOT_RUN`이다. 프로젝트 로컬 GitHub CLI는 로그아웃 상태라 issue API 갱신은 `NOT_RUN`이다.
