# 현재 상태

업데이트: 2026-09-30

## 2026-09-30 Jetson 재연결·현장 배치 재점검

- `PASS (approved LeLab restart / preview recovery)`: 사용자 승인과 세 작업 inactive 재확인 후 systemd *user* `lelab.service` 8000을 한 번만 재시작했다. 새 MainPID 371356, health 정상, teleoperation·recording·inference active=false. Astra `/camera-preview/8`이 MJPEG 3.3 MB/3초로 복구됐고 기존 로봇 record·카메라 index·canonical USB 역할이 유지됐다. 토크 register는 직접 읽지 않아 `NOT_VERIFIED`다.
- `PASS (camera-only corrected-frame smoke)`: 재시작 후 저장한 Astra 1프레임(SHA `57e50f30...c327`)을 오프라인 판독해 ID0–3 모두 검출, X 6개 중심 추출했다. Jetson의 보정 config로 P1–P2=265.071 mm, P1–P4=167.996 mm로 사용자 약식 실측 260/160 mm와 가까웠다. 단일 프레임이며 marker/접촉의 시간 안정성은 검증하지 않았다. 새 영상은 이전 teach의 P5·P6 접촉 증거가 아니며 거부된 `T_B_W`를 승인하지 않는다.
- `PASS (GitHub latest)`: 저장소 좌표·ROI 보정과 교차검증 commit `5ccf145`, Jetson 설치/백업·승인 서비스 재시작·정면 저장 프레임 검사 commit `334caba`를 비공개 `origin/fix/usb-recording`에 push했다. 작업 트리는 clean. GitHub CLI 로그아웃으로 issue API 갱신은 `NOT_RUN`이다.
- `PASS (center-distance cross-check / repository config)`: 사용자 독립 실측 ID2–ID3≈400 mm, ID3–ID0≈346 mm와 edge-gap 보정 예측 397.667/346.758 mm의 차이는 각각 −2.333/+0.758 mm다. `configs/astra_rgbd.example.json`의 기준 중심·pickup ROI를 보정하고 과거 중심·edge-gap 원본을 보존했다. 역사적 RGB-D/바구니 XY 검증은 구 좌표계 사용으로 stale 표시했다. 관련 테스트 42개 통과. 이는 카메라 live 재검증이나 robot-world fit 통과가 아니다.
- `PASS (Jetson config-only deploy / backup)`: root 소유 `/opt/so101-rgbd/astra_rgbd.example.json`의 원본 SHA `ce43a0d0...d9e1`을 `/home/jetson3/so101-recovery-backups/20260930T192133+0900_aruco-center-correction/`에 보존·해시 확인했다. 8020 medicine YOLO 서비스 inactive에서 보정 JSON 한 파일만 설치했고 Jetson/저장소 SHA `40845529...ffd0` 일치. LeLab health 정상, 세 제어 작업 inactive. 8020 서비스는 재시작하지 않았고 새 좌표의 live 카메라 검증은 `NOT_RUN`; robot fit 거부·`robot_enabled=false` 유지.
- `HISTORICAL (preview busy owner)`: 재시작 전 root 읽기 전용 `fuser/lsof`에서 Astra bridge 외에 LeLab 8000 PID 367493이 `/dev/video8`을 여러 FD로 열고 있었다. `/camera-preview-stop` 1회 후에도 busy였고, 설치 소스·systemd user unit을 확인한 뒤 위 승인 재시작으로 프리뷰를 복구했다. 중복 FD의 최초 원인은 `NOT_VERIFIED`다.
- `ROOT_CAUSE_CONFIRMED (reference measurement semantics)`: 사용자가 ID0–3의 기존 여섯 거리값을 마커 중심 간이 아니라 검은 정사각형의 가까운 변/대각선 모서리 간 간격으로 잰 것이라고 확인했다. 이를 중심 좌표로 쓰던 과거 설정에 축척 오류가 있었다. 저장소 예시 좌표는 위와 같이 정정했지만 Jetson 설치본은 아직 구 버전이다.
- `PARTIAL (provisional offline edge-gap correction)`: 마커 폭 ID0=75 mm, ID1–3=70 mm와 축 정렬 검은 사각형 가정으로 center를 임시 적합했다. ID0=(0,0), ID1=(403.5,0), ID2≈(401.375,347.228), ID3≈(3.708,346.738) mm; 가장자리 간격 적합 RMS≈2.623 mm다. 새 X 간격 P1–P2≈265.6 mm, P1–P4≈167.6 mm로 사용자 실측 260/160 mm에 가까워졌다. 같은 관절값의 오프라인 fit은 RMSE 5.299 mm, 최대 9.218 mm, 조건수 8474.4로 여전히 거부다. 별도 읽기 전용 진단 도구·로컬 결과로 보존했고 `robot_enabled=false`, `motion_authorized=false` 유지한다.
- `PASS (GitHub)`: 단일 손끝 teach/안전 종료, ArUco 측정 기준 오류, 임시 진단 코드·테스트를 commit `84e24b8`로 비공개 `origin/fix/usb-recording`에 push했다. 원본 영상·관절 입력·거부 변환은 Git 제외 로컬 파일이다. GitHub CLI 로그아웃으로 issue API 갱신은 `NOT_RUN`이다.
- `PARTIAL (camera busy audit)`: Astra V4L2 bridge는 active이고 `/dev/video8`이 존재한다. Jetson에는 LeLab uvicorn이 8000·8002·8022로 여러 개 실행 중이다. `/camera-preview/8`은 텔레옵 종료 후에도 busy이며, 일반 사용자 `fuser/lsof`는 `/proc/*/fd` 접근 제한으로 점유 주체를 확정하지 못했다. 기존 프로세스·서비스를 중지/재시작하지 않았다.
- `PASS (single-fingertip capture / safe stop)`: 실패한 닫힌 두 손끝 데이터와 분리해, 표시한 한 손가락의 단단한 플라스틱 끝을 TCP 후보로 정했다. 새 카메라 좌표와 P1–P6 사용자 확인 접촉의 관절 방송값 각 15개를 Git-ignore 로컬 입력에 저장했다. P2 첫 15개는 미세 움직임으로 제외했다. `/stop-teleoperation` HTTP 200 뒤 health 정상, teleoperation·recording·inference 모두 inactive다. Follower torque register는 `NOT_VERIFIED`다.
- `REJECTED (single-fingertip T_B_W)`: 실제 설치 URDF와 새 6점의 오프라인 fit은 RMSE 12.665 mm(기준 ≤5), 최대 17.731 mm(≤8), 조건수 6774.9(≤1000), rank 9로 거부됐다. 어느 한 점을 제외해도 RMSE 9.080–13.625 mm로 실패한다. `robot_enabled=false`, `motion_authorized=false` 유지; 이 변환으로 이동하지 않는다. 입력·거부 결과는 각각 `configs/robot_world_pairs.20260930.single-fingertip.local.json`, `configs/robot_world_transform.20260930.single-fingertip.local.json`에 보존했고 source hash가 일치한다.
- `PARTIAL (visual QA)`: P1–P4는 정면 화면에서 표시 끝과 X 위치가 맞았다. P5부터 `/camera-preview/8`은 `Camera is unavailable or busy`를 반환했고 P5·P6 영상 접촉 QA는 `NOT_VERIFIED`다. 카메라 서비스·USB는 변경하지 않았다. 사용자의 X 중심 실측 P1–P2=260 mm, P1–P4=160 mm와 구 좌표계 219/134 mm 차이의 주된 원인은 위 marker 기준 측정 의미 오류로 좁혀졌다.
- `PASS (6-point broadcast capture / safe stop)`: 동일 정면 화면과 현장 안전 확인 후 기존 LeLab 텔레옵을 1회 재시작했다. P1 초기값은 접촉 위치 재정렬 전 후보에서 제외하고, 재정렬 P1 및 P2–P6에서 `/ws/joint-data`만 각 15개(총 90개) 수집했다. 사용자는 두 손끝의 물리 접촉을 확인했다. 최종 `/stop-teleoperation` HTTP 200, LeLab health 정상, teleoperation·recording·inference active=false다. follower torque register는 `NOT_VERIFIED`다.
- `REJECTED (2026-09-30 6-point T_B_W)`: 실제 설치 URDF SHA-256 `443d38d7...f67236`의 base→gripper FK와 6점으로 TCP offset·World→Base 동시 적합을 수행했다. RMSE 13.377 mm(기준 ≤5), 최대 19.111 mm(≤8), 조건수 6250.9(≤1000), rank 9. 어느 한 점을 제외해도 기준을 통과하지 못했다. Astra 렌즈 왜곡 보정 좌표로 재계산해도 RMSE 13.179 mm로 거부된다. `T_B_W`는 실제 이동에 쓰지 않고 `robot_enabled=false`, `motion_authorized=false` 유지한다.
- `PASS (offline reproducibility)`: 원본 관절 sample·World 점은 Git ignore된 `configs/robot_world_pairs.20260930.closed-tip.local.json`, 거부 결과는 `configs/robot_world_transform.20260930.closed-tip.local.json`에 별도 보존했다. 새 offline 진단 도구 `scripts/fit_robot_world_from_joint_samples.py`는 기존 URDF FK와 fit을 묶고 motion 차단·broadcast-only·jaw 안정성을 검증한다. 관련 테스트 4/4, 기존 fit 4/4, FK 3/3 통과. GitHub CLI 로그아웃으로 이슈 API 갱신은 `NOT_RUN`; 문서/코드 commit·push는 별도 확인한다.
- `NEXT (physical protocol revision, no motion yet)`: 현재 fingertip contact의 정확한 동일 물리점 여부가 영상만으로 모호하고, 6점 기하도 충분히 맞지 않는다. 한 개의 표시된 고정 fingertip 끝을 TCP로 선택하거나 안정적인 탈착 포인터를 고정한 뒤, 다양한 손목 자세의 독립 touch·holdout을 설계한다. 새 현장 준비·승인 전 추가 로봇 구동은 하지 않는다.
- `STOPPED_SAFE (6-point teach attempt)`: 사용자가 follower 범위 밖·즉시 중단 준비·리더/팔로워 시작 자세 정렬과 기존 텔레옵의 천천히 손으로 조작하는 방식에 동의했다. LeLab `/move-arm` 1회가 HTTP 200으로 시작되고 active 및 `/ws/joint-data` 방송을 확인했다. 리더 조작 전 P1 위치/보는 웹 주소가 혼동되어 `/stop-teleoperation` 1회로 즉시 중단했고 teleoperation·recording·inference는 모두 inactive다. P1–P6 sample은 0개, fit은 `NOT_RUN`, `robot_enabled=false`. Follower torque register는 종료 후 직접 확인하지 않아 `NOT_VERIFIED`다.
- `BLOCKED_VIEW_IDENTITY`: 천장 정면 `/camera-preview/8`(LeLab `192.168.50.20:8000`)에서 P1은 화면 왼쪽 위 X이며 바로 왼쪽의 ArUco ID2 옆이다. 사용자 화면의 ambient URL `192.168.50.22:8020`은 Mac에서 health 연결이 timeout되어 동일 현장 화면인지 확인하지 못했다. 기준 화면을 맞추기 전 텔레옵 재개는 하지 않는다.
- `USER_APPROVED / BLOCKED_SAFETY (6-point teach)`: 사용자가 "6점 저속 텔레옵 teach 승인"을 명시했다. 새 정면 영상에서 중앙 약통이 치워지고 X 6개가 보였으나, 두 차례 확인 모두 사람이 follower arm 뒤쪽 가까이에 보여 사람·손의 작업 범위 이탈을 확인할 수 없다. `/move-arm` 시작 요청은 보내지 않았고 모터·토크 변화는 `NOT_RUN`이다. 리더 조작자는 follower 이동 범위 밖에 자리하고 즉시 중단 방법이 준비됐다는 현장 확인이 필요하다.
- `PASS (teach preflight read-only)`: LeLab `/health` 정상, teleoperation·recording·inference 모두 active=false. 실제 설치 OpenAPI에서 `/move-arm`이 텔레옵 시작, `/stop-teleoperation`이 중단임을 확인했다. 저장된 `so-101` record는 leader=`/dev/ttyACM1`, follower=`/dev/ttyACM0`, 두 config=`so-101.json`이다. canonical serial↔ACM 연결은 앞선 같은 날 확인한 결과를 근거로 하며 이번 점검에서 serial bus를 열지 않았다.
- `PASS (camera-only 6 X coordinates)`: 정면 MJPEG 132프레임 중 ID0–3 네 마커가 모두 검출된 82프레임에서 검은 X 6개 중심을 추출하고, 프레임별 homography로 World 좌표를 재계산했다. P1–P6의 이전값 대비 최대 점별 차이는 약 1.98 mm, 점별 RMS 시간 변동은 0.22–0.43 mm였다. 새 좌표는 별도 로컬 `configs/robot_world_pairs.20260930.closed-tip.local.json`에 보존하고 2026-09-28 원본은 변경하지 않았다.
- `PASS (post-check read-only)`: LeLab `/health`는 정상, teleoperation·recording·inference 모두 active=false였다. recording status의 `current_phase=preparing`, `session_ended=false`는 남아 있어 세션 내부 정리는 `NOT_VERIFIED`이며 재시작하지 않았다.
- `BLOCKED_APPROVAL (physical teach)`: 닫힌 fingertip TCP와 P1–P6의 follower 관절 sample 수집은 모터·토크를 수반한다. 중앙 약통 모형을 치우고 현장 안전·중단 방법을 확인한 뒤 새 명시 승인 전까지 수행하지 않는다. 현재 `T_B_W` 거부, `robot_enabled=false`는 유지한다.
- `PASS (X visibility follow-up)`: LeLab 정면 `/camera-preview/8`의 새 640×480 프레임에서 검은 X 6개가 모두 보인다. 작업대 모서리의 ArUco 4장도 화면에 보이며, 바구니는 치워져 있고 약통 모형 1개가 중앙에 남아 있다. X는 6점 robot-world teach용 임시 접촉점이지 운영 중 바구니마다 필요한 마커가 아니다. 이 1프레임 육안 점검은 ArUco ID 판독·X world 좌표 재추출·로봇 teach 완료를 뜻하지 않는다.
- `NEXT (camera-only)`: 현 배치에서 ID0–3을 판독하고 X 6개 중심의 World 좌표를 다시 추출한다. 이후 모터·토크를 수반하는 teach는 별도 현장 안전 확인과 명시 승인 전까지 `NOT_RUN`이다. teach 완료 후 X 테이프는 제거할 수 있으나 ID0–3 작업대 기준 마커는 고정 유지하고, 바구니 ID4–6은 복귀 후 검출·색상 매핑을 재확인한다.
- `PASS (connection)`: Jetson `192.168.50.20:22` SSH와 LeLab `:8000/health`가 응답했다. 실제 로그인은 `jetson3`, Jetson 시각은 2026-09-30 15:53 KST였다.
- `PASS (control preflight)`: LeLab teleoperation·recording·inference는 모두 inactive였다. 이 점검에서는 serial 장치를 열거나 모터·토크를 변경하지 않았다. Follower torque register 값은 `NOT_VERIFIED`다.
- `PASS (USB/config identity)`: Leader stable serial `5AE6085272`→`/dev/ttyACM1`, Follower `5AE6058306`→`/dev/ttyACM0`이며 실제 `so-101.json`의 leader/follower port와 일치했다. 현재 camera record는 ceiling_vertical index 8, ceiling_oblique index 4, end_effector index 6의 3대다.
- `OBSERVED (preview ownership)`: `astra-v4l2-bridge.service`는 active이며 Astra를 `/dev/video8`에 공급한다. `medicine-yolo-preview.service` 8020은 2026-09-28 20:35부터 inactive다. LeLab `/camera-preview/8`과 `/camera-preview/4`는 HTTP 200과 실제 프레임을 반환했다. 기존 서비스 소유권을 변경하지 않았다.
- `PASS (camera-only current scene)`: Astra 정면 1프레임에서 DICT_4X4_50 ID0–6을 모두 검출했다. 기존 YOLO11n ONNX는 약통 모형 3개를 confidence 0.873/0.722/0.540으로 검출했다. 이는 단일 프레임 스모크이며 일반 성능·약품 정체성 검증이 아니다.
- `PASS (basket cross-check)`: 정면의 물리 배치는 왼쪽 ID5·가운데 ID6·오른쪽 ID4다. 사선 화면에서 왼쪽 초록·가운데 파랑·오른쪽 빨강을 확인해 기존 ID4=빨강, ID5=초록, ID6=파랑 매핑이 유지됨을 교차 검증했다. 바구니의 좌우 순서는 고정 가정으로 쓰지 않는다.
- `UNVERIFIED_TEACH_LAYOUT`: 2026-09-28의 검은 X 6점은 현재 약통·바구니에 가려져 중심 위치 유지 여부를 확인할 수 없다. `robot_world_pairs.20260928.closed-tip.local.json`의 World 좌표는 재검증 전 현재 teach에 재사용하지 않는다. 현재 `T_B_W`는 계속 거부 상태이며 `robot_enabled=false`다.
- `NEXT (physical)`: 6점 teach를 재개하려면 사용자가 빈 약통·바구니를 작업대에서 치워 X 6개와 ID0–3을 정면·사선 카메라에 노출하고, 팔 지지·작업 공간·중단 방법을 현장에서 확인해야 한다. 이후 새 World 좌표부터 다시 측정한다.
- `PASS (GitHub)`: 위 읽기 전용 점검과 다음 단계 기록을 commit `c83f537`로 비공개 `origin/fix/usb-recording`에 push했다.

## 2026-09-29 GitHub 기록 재개

- `PASS (local audit)`: `CODEX_LELAB_SO101_RECOVERY.md` 787행과 `MAC_SSH_GITHUB_START.md` 170행 전체를 다시 읽고 현재 기록 기준으로 사용했다.
- `BLOCKED_NETWORK`: 사용자가 Jetson이 offline임을 확인했고 `192.168.50.20` SSH 22, LeLab 8000, preview 8020은 모두 timeout이다. 네트워크·전원·USB는 변경하지 않았다.
- `NOT_RUN`: 2026-09-29 Jetson live USB·LeLab·torque 상태 재확인과 신규 Jetson 백업은 offline으로 실행하지 못했다. 2026-09-28까지의 근거는 실시간 재확인으로 바꾸어 쓰지 않는다.
- `PASS (Git read auth)`: 비공개 remote `gyeyeongjo-lgtm/so101-lelab-medicine-sorter` BRANCH 목록을 `git ls-remote` 로 읽었다. 다만 프로젝트 로컬 GitHub CLI는 현재 로그아웃 상태다.
- `PASS (Git push)`: 진행 기록·코드·테스트·ArUco 인쇄 자산 116개 파일을 commit `a68b39f`로 저장하고 `origin/fix/usb-recording`에 push했다.
- `DOCUMENTED`: `docs/CURRENT_SYSTEM_AND_ARUCO.md`에 물리 카메라 3대(Astra 정면, RealSense 사선, Generic USB 손목), 운영 ArUco 7개(ID0–3 작업대, ID4–6 바구니), ChArUco/검은 X의 구분, 현재 fit 거부 결과와 다음 6점 teach를 정리했다.
- `SAFETY`: 오늘 로봇 모터·토크·USB·전원·캘리브레이션을 변경하지 않았다. 오프라인 중이므로 직전 테레옵의 정상 종료나 torque 0을 오늘 확인했다고 주장하지 않는다.

아래 `상태 요약`의 초기 주소·Git 상태는 2026-09-05 시점 이력이다. 현재 값은 위 최신 섹션과 후반 날짜별 기록을 우선한다.

## 상태 요약

- `OBSERVED`: Codex는 Mac 로컬 `/Users/jogyeyeong/Documents/ChatGPT/자율설계`에서 실행 중이다.
- `OBSERVED`: 작업 루트는 커밋이 아직 없는 기존 Git 저장소이며 remote가 없다.
- `OBSERVED`: 사용자 원본인 `prompt/`는 미추적 상태로 보존되어 있다.
- `OBSERVED`: `192.168.0.10:22`와 `192.168.0.10:8000`은 TCP 연결에 응답한다.
- `OBSERVED`: 실제 SSH 대상은 `jetson3@192.168.0.10:22`이다.
- `PASS`: 사용자가 ED25519 호스트 키를 확인했고, 프로젝트 전용 known-hosts 파일의 지문도 일치했다.
- `PASS`: 실제 SSH 계정 `jetson3`으로 인증했고 프로젝트 전용 소켓을 재사용 중이다.
- `PASS`: 공식 GitHub CLI v2.100.0 arm64 바이너리를 프로젝트 로컬 `.local/bin/gh`에 설치하고 배포 체크섬을 검증했다.
- `PASS`: 프로젝트 로컬 GitHub CLI가 macOS Keychain의 `gyeyeongjo-lgtm` 계정으로 인증됐고 API 호출도 통과했다.
- `PASS`: 비공개 GitHub 저장소 `gyeyeongjo-lgtm/so101-lelab-medicine-sorter`를 만들고 초기 `main` 커밋 `8dd6761`을 push했다.
- `PASS`: 후속 작업 브랜치 `fix/usb-recording`의 증거 문서 커밋 `48d788b`을 push하고 원격 SHA를 확인했다.
- `PASS`: 이슈 #1–#4를 생성하고 API에서 open 상태를 확인했다.
- `USER_REPORTED`: 기존 리더-팔로워 텔레오퍼레이션, 캘리브레이션, 웹캠, 네트워크 설정은 성공 상태였다.
- `PASS`: Jetson Phase A 환경 조사와 설정·캘리브레이션·소스·journal 백업을 완료했고 Jetson/Mac 양쪽 해시를 검증했다.
- `HISTORICAL`: Phase A 직후에는 serial `5AE6085272` 한 대만 보였고 저장된 팔로워 `5AE6058306` 및 `/dev/video*`가 일시적으로 누락됐다. 이후 물리 재연결 뒤 아래 최신 preflight를 다시 확인했다.
- `OBSERVED`: 19:32 캘리브레이션 TX/RX 오류는 동시 bus 읽기와 일치하고, 19:35 직렬화 패치 이후 두 캘리브레이션에서 재발하지 않았다.
- `PASS`: 메타데이터 전용 포트 검사와 preflight 스크립트의 오프라인 단위 테스트 3개가 통과했다.
- `FAIL`: Jetson preflight는 팔로워 serial, `/dev/video0`, `/dev/video2` 누락을 검출해 `ready=false`로 종료했다.
- `HISTORICAL`: 이 단계에서는 실제 데이터셋 녹화, 텔레옵 회귀, 모터/토크 관련 시험을 실행하지 않았다. 이후 아래 승인 시험으로 상태가 갱신됐다.
- `OBSERVED`: 21:53:19와 21:53:52 녹화 시도는 각각 torque enable id 5, follower `Present_Position` sync-read에서 실패했고 저장 episode는 0개였다.
- `PASS`: 최신 장치 preflight 7/7; 두 serial과 두 카메라가 존재하고 서로 다른 장치다.
- `PASS`: Mac에서 읽기 전용 follower 진단 도구 `scripts/diagnose_follower_bus.py`의 문법 검사와 기존 오프라인 단위 테스트 3개를 통과했다.
- `PASS`: 2026-09-06 Jetson standalone 읽기 전용 follower 시험에서 올바른 serial identity, ping 6/6, 개별 position read 30/30, group sync-read 5/5를 확인했다. ID 5도 정상이며 torque·register·USB 설정을 변경하지 않았다.
- `PASS`: 추가 20-round 읽기 전용 시험도 개별 120/120, group 20/20 성공했고 Mac backup에 hash 검증해 보존했다.
- `OBSERVED`: 11:10 텔레옵 약 62초 동안 follower 위치 read 오류 255건과 정상 joint snapshot 48건이 섞였다. 설치된 loop는 1 ms sleep으로 follower sync-write를 반복해 bus 포화 가능성이 높다.
- `PASS`: A/B 직전 캘리브레이션·robot record·설치 소스·journal 9개 파일을 Jetson과 Mac에 백업하고 SHA-256 전체 검증을 통과했다.
- `FAIL`: 카메라·video·streaming encoding을 제외한 최소 녹화도 `Devices ready` 직후 첫 follower observation에서 같은 sync-read 오류로 실패했다. saved episode 0, kernel USB event 없음.
- `PASS`: 실패 직후 standalone read 30/30·group 5/5가 다시 성공했고 시험 전후 설정 파일 hash가 동일했다.
- `PASS`: stale goal 차이는 최대 12 raw unit이었으며 torque-only 약 3초 시험에서 enable/disable, position+voltage 40/40, 12.2V 유지가 모두 통과했다.
- `PASS`: 구체적 안전 승인 뒤 configure+RX-clear+50ms 시험을 실행해 position+voltage 40/40, torque disable 성공을 확인했다.
- `FAIL`: 승인된 RX-clear patch를 Jetson에 배포하고 service를 재시작한 뒤 카메라 없는 실제 녹화를 회귀했다. patch log와 50 ms settle은 확인됐지만 첫 follower observation이 `There is no status packet`으로 즉시 실패했고 episode는 0개였다.
- `PASS`: 실패한 patch를 pre-A/B 원본으로 롤백했다. 현재 설치본과 보존 원본의 SHA-256은 모두 `779fd897...`로 같고 `lelab.service`, `/health`, 텔레옵·녹화 inactive 상태를 다시 확인했다.
- `PASS`: leader `/dev/ttyACM1` standalone 읽기 전용 시험도 serial `5AE6058306`, ping 6/6, 개별 position 120/120, group 20/20으로 통과했다.
- `PASS`: leader와 follower 포트를 동시에 열고 30 Hz로 120 rounds 교차 group read한 시험은 양쪽 모두 120/120, 오류 0건이었다. 단순 dual-open 및 양방향 read traffic은 재현 조건에서 약해졌다.
- `PASS`: patch 실패와 dual-read 결과를 Jetson/Mac 양쪽 backup에 보존하고 체크섬을 검증했다.
- `PASS`: 승인된 dual-configure 계측 전 현재 calibration·robot record·설치 소스·journal 10개를 `20260906T120356+0900_pre-dual-configure`로 Jetson/Mac 양쪽에 보존하고 hash를 검증했다.
- `NO_EFFECT`: 첫 계측 실행은 포트를 열기 전 내부 메서드명 불일치로 종료됐다. calibration/register/torque 호출은 0건이었고 service health를 복구했다.
- `PASS`: 호출별 계측 trial에서 follower configure 직후 첫 position group-read 3/3, 전체 follower→leader configure 직후 3/3이 모두 SDK `comm=0`이었다. 양쪽 teardown torque disable/disconnect도 성공했고 Goal_Position write는 0건이었다.
- `PASS`: 사전 group-read와 호출별 계측 지연을 제거한 cold full-order trial도 첫 follower read 3/3과 leader read 1/1이 모두 `comm=0`이었다.
- `PASS`: 시험 전후 follower/leader calibration과 robot record hash가 동일하고, live `record.py`는 원본 hash `779fd897...`, kernel USB event 0건, LeLab health 정상이다.
- `OBSERVED`: 동일 hardware sequence가 standalone에서는 재현되지 않아 calibration/configure 순서 자체의 결정적 결함은 약해졌다. 실제 녹화와 남은 주요 차이는 LeLab의 background `recording-worker`, 사전 dataset 생성/runtime context, 그리고 간헐성이다.
- `READY_FOR_APPROVAL`: 설치본을 건드리지 않는 `patches/lelab-20260906/record-worker-context.instrumentation.md` 계측안을 준비했다. worker thread, dataset 생성, 장치 준비 단계와 record_loop 경계만 기록하며 hardware sequence는 변경하지 않는다.
- `BLOCKED_ENV`: 승인 직후 배포 전 SSH 재확인 단계에서 실행 환경의 원격 SSH 권한/사용량 제한이 발생했다. 이번 턴에는 Jetson 설치본·서비스·하드웨어를 변경하지 않았다.
- `INFO`: 현재까지의 확정 사실·가설·배제 사항은 `docs/PROBLEM_SUMMARY_REFERENCE_2026-09-05.md`에 참고용으로 정리했다.
- `BLOCKED`: 녹화 초기화 직후 follower read 실패가 남아 있어 데이터셋 녹화를 회귀 통과로 판정할 수 없다.
- `PASS`: Draccus의 Python 3.14 parser 호환성 최소 patch 뒤 공식 `lerobot-record --help`와 실제 CLI 진입이 가능해졌다. 이 patch는 CLI parser 단계만 해결하며 TX/RX 원인을 고치지 않는다.
- `FAIL`: 승인된 공식 LeRobot CLI 무카메라 1회 비교군에서 LeLab service를 중지해 UI/worker 경쟁을 제거했는데도, episode 0 시작 뒤 follower `Present_Position` sync-read가 IDs 1–6 전체에서 3회 실패했다. SDK 원문은 `There is no status packet!`이고 episode는 완료되지 않았다.
- `OBSERVED`: 현재 물리 매핑은 follower `5AE6058306` (`/dev/ttyACM1`), leader `5AE6085272` (`/dev/ttyACM0`)이다. 역할 설정에는 각각의 `/dev/serial/by-id/...` 경로를 사용한다.
- `HYPOTHESIS`: UI/worker 동시 접근은 이번 오류의 주원인에서 제외됐다. 실제 control/torque lifecycle 뒤에만 나타나는 follower bus 전원·connector·기계적 결속/과전류·half-duplex timing의 간헐 문제를 우선 확인한다.
- `NOT_RUN`: CLI 종료 trap 뒤 LeLab service health 및 live `record.py`의 원본/계측 hash는 아직 새로 읽기 전용 확인하지 않았다. 확인 전에는 UI 녹화나 추가 hardware trial을 실행하지 않는다.
- `PASS`: 2026-09-08 현재 LeLab의 `so-101` robot record에 leader=`/dev/ttyACM1`, follower=`/dev/ttyACM0`가 저장된 것을 UI와 파일로 확인했다. 사용자가 확정한 실제 역할과 반대였다.
- `PASS`: 원본 record를 `/home/jetson3/so101-recovery-backups/20260908T163404+0900_port-map-correction/so-101.json.before`에 보존한 뒤, 포트 두 값만 leader=`...5AE6085272-if00`, follower=`...5AE6058306-if00`의 stable by-id 경로로 원자적으로 보정했다. LeLab restart와 `/health`은 통과했다.
- `FAIL`: 안전 승인된 UI Collect data 1회는 새 dataset 생성 후 follower/leader connect까지 통과했지만 `OpenCVCamera(0)` open 실패로 종료됐다. episode 0, session 0초, Hub upload 미실행. 이 trial은 record-loop/TX-RX 전 단계에서 멈췄다.
- `OBSERVED`: recording 직전 camera discovery는 `/dev/video0`–`/dev/video9`를 모두 열지 못했고 preview API도 indices 0/2에서 503이었다. 다음 단계는 camera node/점유/권한의 읽기 전용 조사다.
- `PASS`: 사용자 승인 아래 C920 두 대를 Jetson USB hub에 한 대씩 재연결했다. 현재 `/dev/video0`과 `/dev/video2`가 UVC/V4L2로 열거되며 `lerobot-find-cameras opencv`가 두 path 모두 640×480@30 FPS의 실제 test frame capture까지 통과했다. 기존 LeLab camera index 0/2와 일치한다.
- `PASS (UI summary)`: 최신 안전 승인 뒤 `Supermassive111/camera_recovery_regression_20260908_20260908_170150`로 Collect data를 1회 실행했다. 두 live feed가 표시된 상태에서 episode를 정상 종료했고 UI가 1 episode, 135 frames, 30 FPS를 보고했다. Hub upload는 명시적으로 건너뛰어 local dataset만 보존했다.
- `PENDING (read-only)`: 위 성공은 UI summary 기준이다. `meta/info.json`, parquet/video 파일, `LeRobotDataset`의 frame decode를 읽기 전용으로 확인하기 전에는 모든 frame의 offline 유효성이나 장기 안정성까지 주장하지 않는다.

## 2026-09-13 최신 갱신

- `PASS (UI)`: 새 오픈그리퍼 데이터셋 `Supermassive111/opengrip50_20260913_165317`의 Hub 업로드 완료 화면을 확인했다. Private Visualize Space의 401은 업로드 실패가 아니라 Space 접근 권한 제한이다.
- `PASS`: Mac MPS ACT 학습이 10,000 step으로 완료됐고, 최종 checkpoint의 6축 state/action 및 `312`·`camera_2` 640×480 input feature를 읽기 전용으로 확인했다.
- `PASS`: 사용자 승인으로 비공개 모델 `Supermassive111/act-so101-opengrip50-v1`을 업로드했다. 원격 private 상태와 필수 최종 모델 파일을 읽기 전용 검증했고 LeLab Import도 완료했다.
- `PASS (UI)`: 구체적 현장 안전 승인 뒤 새 모델을 30초 제한으로 1회 추론했다. UI의 RUNNING과 `Inference finished — Run completed`, 홈 Ready 복귀를 확인했다.
- `NOT_VERIFIED`: 실제 물체 집기 성공률·진동·자율 동작 품질은 현장 관찰이 필요하다. CPU rollout은 GPU 가속 복구를 의미하지 않는다.
- `NOT_PUSHED`: 작업 GitHub 저장소에 이번 세션 관련 커밋·push는 수행하지 않았다. 자세한 근거는 `docs/sessions/2026-09-13-opengripper-act-deployment.md`에 보존했다.

## 2026-09-14 데이터셋 병합·학습 준비 갱신

- `PASS`: 2026-09-14에 수집한 private 원본 네 개를 읽기 전용으로 구조 확인했다. 각 데이터셋은 동일한 6축 state/action, `312`·`camera_2` 640×480@30 FPS feature를 사용한다.
- `PASS`: episode 수는 각각 42, 14, 14, 30으로 합계 100이며, 병합본은 68,292 frames, 30 FPS, 단일 task로 검증됐다.
- `PASS`: 원본을 수정하지 않고 새 private 병합 저장소 `Supermassive111/opengrip100_20260914_merged`를 만들었다. Hub dry-run으로 metadata, parquet, 두 카메라 video를 포함한 14개 파일(약 1.3 GB)의 존재를 확인했다.
- `PASS`: 병합본의 모든 episode task를 `Pick an item from the pickup area and place it in the correct basket.`으로 통일했다. 원본 네 데이터셋은 변경하지 않았다.
- `PASS`: Mac MPS에서 병합 데이터셋 대상 ACT 학습 30,000 step을 완료했고, 최종 checkpoint `030000/pretrained_model`의 필수 model·전/후처리·학습 설정 파일을 확인했다. W&B 그래프의 원격 표시 상태는 별도 확인 전까지 `NOT_VERIFIED`다.
- `NOT_PUSHED`: 이번 데이터셋 병합·학습 준비 관련 Git 커밋과 GitHub push는 수행하지 않았다.

## 2026-09-15 ACT 30k 배포·1회 추론

- `PASS`: 사용자 승인으로 private 모델 `Supermassive111/act-so101-opengrip100-30k-v1`을 업로드했고, 원격 필수 모델 파일과 LeLab UI Import(표시명 `ACT open gripper 100 episodes 30k v1`)를 확인했다.
- `PASS (UI)`: 현재 카메라 바인딩 `312`→`#0 HD Pro Webcam C920`, `camera_2`→`#2 USB Camera`가 checkpoint의 640×480 feature와 일치함을 확인했다.
- `FAIL (UI)`: 구체적 현장 안전 승인 아래 30초 제한 ACT 추론을 정확히 1회 시작했다. UI가 policy loading 이후 `RUNNING`(00:06/00:30)까지 전환했으나, 30초 만료 전에 `Inference finished`, exit code `1`로 종료했다. 재시도·모터 설정 변경·서비스 재시작은 하지 않았다.
- `OBSERVED`: 종료 log tail에는 id 1의 `Torque_Enable=0` cleanup이 status packet을 받지 못해 6회 재시도 뒤 실패한 사실이 남았다. 사용자는 같은 1회 추론에서 follower 대신 leader arm이 움직였다고 보고했다.
- `OBSERVED`: 후속 읽기 전용 LeLab UI 확인에서 Leader (Teleoperator) port가 `/dev/ttyACM1`로 표시됐다. 기존에 확정·저장했던 leader=`...5AE6085272`(`/dev/ttyACM0`), follower=`...5AE6058306`(`/dev/ttyACM1`) 매핑과 반대이므로, 포트 역할 역전이 최우선 원인 후보다.
- `PASS (config only)`: 사용자 승인으로 LeLab 저장 포트 역할을 leader=`/dev/ttyACM0`, follower=`/dev/ttyACM1`로 보정했고 API 재조회로 두 값 모두 확인했다. 보정 전후 텔레오퍼레이션·녹화·추론은 모두 inactive였으며, 이 작업은 모터를 구동하지 않았다.
- `FAIL (UI)`: 뒤이은 1회 시험은 Calibration 화면용 포트만 보정된 상태에서 실행됐다. UI는 `RUNNING 00:31 / 00:30` 뒤 exit code `1`로 종료했고, 이후 모든 제어 작업은 inactive였다. 이 시험은 실제 `so-101` record가 아직 반대였음을 드러냈다.
- `CORRECTION`: 위 저장 포트는 Calibration 화면용 별도 값이었고, 추론이 실제 사용하는 `so-101` robot record는 여전히 leader=`/dev/ttyACM1`, follower=`/dev/ttyACM0`로 반대였다. 이것이 보정 뒤에도 leader가 움직인 직접 원인이다.
- `PASS (config only)`: 사용자 승인 범위에서 실제 `so-101` robot record의 두 port만 leader=`/dev/ttyACM0`, follower=`/dev/ttyACM1`로 patch했고 GET 재조회로 확인했다. leader/follower config와 두 camera binding은 보존했으며 모든 제어 작업은 inactive였다.
- `PASS (read-only)`: Jetson camera discovery는 C920 index 0과 USB Camera index 2를 available로 보고했고, 두 `/camera-preview` stream은 모두 HTTP 200으로 실제 MJPEG frames를 전송했다. 비녹화 상태의 UI `No preview`는 연결 실패 증거가 아니다.
- `PASS (UI)`: 별도 현장 안전 승인으로 보정된 실제 `so-101` record와 두 camera binding을 사용해 ACT 30k 추론을 30초 제한으로 1회 실행했다. UI가 `RUNNING`에서 `00:28 / 00:30`까지 진행한 뒤 `Inference finished — Run completed`, 홈 `Ready`로 복귀했다. 이후 모든 제어 상태도 inactive였다.
- `USER_REPORTED`: 위 정상 종료 run에서 follower arm은 실제로 움직였으나 물체를 잡지는 못했다. 따라서 포트 역할·기본 실행 경로는 통과했지만, 집기·분류 성능은 아직 `FAIL`이다.
- `HYPOTHESIS`: 현 단계의 2D ACT는 depth/거리 값을 직접 추정하지 않는다. 물체 시작 위치·자세·조명 편차, 그리퍼 닫힘 타이밍/시연 품질, 데이터 양이 집기 실패에 기여할 수 있다. 추가 데이터 또는 학습 step 수의 단독 변경 전에는 검증 설계를 분리한다.
- `PASS (UI)`: 별도 추가 안전 승인으로 같은 보정 포트·모델·두 카메라 조건에서 30초 제한 ACT를 1회 더 실행했다. UI는 `RUNNING 00:24 / 00:30` 및 `00:32 / 00:30`을 표시한 뒤 홈 `Ready`로 복귀했고, 종료 뒤 모든 제어 상태는 inactive였다. 실제 집기 결과는 현장 관찰이 필요하다.
- `NOT_VERIFIED`: 종료 뒤 상태 API는 완료 상태를 반환해 최초 오류를 보존하지 않았다. Jetson의 해당 inference log를 읽기 전용으로 확인하기 전까지 원인과 실제 물체 동작 성공/실패를 판정하지 않는다.
- `NOT_PUSHED`: 이번 배포·추론 관련 Git 커밋과 GitHub push는 수행하지 않았다.

## 2026-09-17 추가 ACT 30k v1 추론

- `PASS (UI)`: 별도 현장 안전 승인으로 `Supermassive111/act-so101-opengrip100-30k-v1@root`를 30초 제한으로 1회 실행했다. `312`→C920 index 0, `camera_2`→USB Camera index 2의 640×480 binding을 확인했고 UI는 `RUNNING 00:21 / 00:30`, `00:25 / 00:30`을 표시한 뒤 자동으로 설정 화면으로 복귀했다.
- `NOT_VERIFIED`: 이번 run의 실제 집기·분류 결과 및 종료 log/API 상태는 현장 관찰·읽기 전용 log 확인 전까지 판정하지 않는다.
- `NOT_PUSHED`: 이 기록에 대한 Git 커밋·push는 수행하지 않았다.

## 2026-09-17 50-episode v1 비교 추론

- `PASS (UI)`: 별도 현장 안전 승인으로 `Supermassive111/act-so101-opengrip50-v1@root`를 30초 제한으로 1회 실행했다. camera binding은 `312`→C920 index 0, `camera_2`→USB Camera index 2로 확인됐고, UI가 `RUNNING 00:21 / 00:30`, `00:26 / 00:30` 뒤 자동으로 설정 화면으로 복귀했다.
- `OBSERVED`: 시작 직전 이전 run 상태가 잠시 active로 남아 첫 요청을 차단했으나, 완료 화면을 재조회해 상태 정리 후에만 50-episode run을 시작했다. 중복 구동은 하지 않았다.
- `NOT_VERIFIED`: 실제 집기·분류 결과와 종료 log/API 상태는 현장 관찰·읽기 전용 확인이 필요하다.
- `NOT_PUSHED`: 이 기록에 대한 Git 커밋·push는 수행하지 않았다.

## 2026-09-17 ArUco 작업대 좌표계 1단계 시작

- `PASS (read-only)`: 최신 인계 주소 `192.168.0.30:8000`의 `/health`가 정상 응답했다. 새 IP가 제시한 SSH ED25519 지문은 기존 확인 지문 `SHA256:dG9hPvs6yZcfIlZ0mPofx8lUPGYwDwW1M4UDzeSfx3o`와 일치했다. 과거 문서의 `192.168.0.10`은 이전 주소로 취급한다.
- `PASS (read-only)`: Jetson의 실제 LeLab Python은 3.14.7, OpenCV는 4.13.0이며 `cv2.aruco.ArucoDetector`를 지원한다. `/dev/video0`은 `root:video`, mode `660`인 character device다.
- `PASS (read-only)`: 작업 전 LeLab health 정상, teleoperation·recording·inference 모두 inactive를 확인했다. 카메라나 serial 장치는 열지 않았다.
- `PASS (offline)`: `DICT_4X4_50`, IDs 0–3, 70 mm 인쇄용 A4 SVG와 개별 SVG/PNG를 생성했다. 합성 640×480 영상에서 네 ID, homography, 화면 중심의 작업대 좌표 변환을 확인했고 동일 영상 30-frame 안정성 계산은 약 `1.5e-13 mm`였다. 이 값은 합성 입력 검증일 뿐 실제 카메라 안정성을 뜻하지 않는다.
- `PASS (offline)`: ArUco ID parsing·config 검증을 포함해 하드웨어 없는 단위 테스트 10개가 통과했다.
- `NOT_RUN`: 실제 인쇄 크기 확인, 작업대 부착, 마커 중심 거리 실측, C920 live 검출, 실제 좌표 jitter 측정은 수행하지 않았다.
- `NOT_VERIFIED`: 카메라 내부 파라미터 calibration과 marker pose는 아직 검증하지 않았다. calibration 파일이 없으므로 현재 도구는 이를 `pose_ready=false`로 명시한다.
- `NOT_DEPLOYED`: 새 스크립트는 Jetson의 영구 경로에 배포하지 않았다. `/tmp` 합성 검증용 전송은 후속 SSH 암호 도우미 응답 중단으로 완료 여부를 확인하지 못했고, Mac의 기존 LeRobot OpenCV 4.13.0 환경에서 대신 검증했다.
- `NOT_PUSHED`: 이번 ArUco 작업에 대한 Git commit·push는 수행하지 않았다.

## 2026-09-17 ArUco Stage 1 준비

- `READY`: marker 출력 도구 `scripts/generate_aruco_markers.py`, Jetson camera-only 검출 도구 `scripts/check_aruco_workspace.py`, 출력·부착·검증 안내 `docs/ARUCO_STAGE1.md`를 준비했다.
- `SAFETY`: 이 단계의 도구는 marker 파일 생성 또는 지정 V4L2 camera read만 수행한다. 로봇 serial, torque, teleoperation, recording, inference는 열거나 실행하지 않는다.
- `BLOCKED (physical)`: marker 4장을 100% 크기로 출력하고 천장 C920 시야에 배치해야 실제 검출·camera calibration을 시작할 수 있다.
- `NOT_PUSHED`: 이 준비 작업의 Git 커밋·push는 수행하지 않았다.

## 2026-09-20 세 카메라 매핑·ArUco 실제 검출

- `PASS (read-only)`: `192.168.0.30` LeLab health 정상, teleoperation·recording·inference 모두 inactive를 확인한 뒤 camera-only 검사를 시작했다.
- `PASS`: 세 물리 카메라와 index0 node가 canonical USB 정보로 확인됐다. 천장 사선 C920 serial `27292FAF`=`/dev/video0`, 로봇팔 Generic USB=`/dev/video2`, 천장 수직 C920 serial `07FE1FAF`=`/dev/video4`다. 사용자가 실제 화면으로 세 역할을 확정했다.
- `PASS (camera-only)`: `/dev/video0` 640×480 90-frame read는 성공했지만 ArUco는 ID 2만 88/90 검출해 기준 카메라로 부적합했다.
- `PARTIAL (camera-only)`: `/dev/video4` 640×480 90-frame read에서 ID 0=90, ID 1=89, ID 2=88, ID 3=22회 검출됐다. 네 ID를 모두 찾았으나 ID 3 검출률이 약 24%라 안정성 성공 기준은 아직 통과하지 못했다.
- `PASS (UI)`: Safari에 `/camera-preview/0`, `/camera-preview/2`, `/camera-preview/4`를 별도 탭으로 열었고 각 640×480 stream을 확인했다. `/dev/video2`는 로봇 그리퍼, `/dev/video4`는 팔로워와 네 marker가 보였다.
- `SAFETY`: 위 검사는 camera read만 수행했다. robot serial, torque, teleoperation, recording, inference를 열거나 실행하지 않았다.
- `ACTIVE_RESOURCE`: 현재 Safari preview 세 탭이 카메라를 점유할 수 있다. 다음 detector·calibration·recording 전에 세 preview 탭을 닫고 release를 확인해야 한다.
- `NOT_VERIFIED`: 세 카메라 intrinsic calibration, 천장 카메라 homography/jitter, 손목 hand-eye calibration은 아직 실행하지 않았다.
- `NOT_PUSHED`: 이번 기록에 대한 Git commit·push는 수행하지 않았다.

### 2026-09-20 ArUco 실측 좌표

- `USER_MEASURED`: marker center 거리(mm)는 0–1=343, 1–2=274, 2–3=340, 3–0=277, 0–2=440, 1–3=436이다.
- `PASS (offline)`: ID 0을 원점, ID 0→1을 +X축으로 고정해 6개 거리의 최소제곱 평면 좌표를 계산했다. 좌표는 ID 0=(0,0), ID 1=(343,0), ID 2=(345.082,273.708), ID 3=(5.446,276.666) mm이며 거리 잔차 RMS는 약 0.34 mm다.
- `PASS (config only)`: 현장 config `configs/aruco_table.local.json`을 천장 수직 `/dev/video4`, 640×480@30으로 작성하고 parser 검증을 통과했다. local config는 `.gitignore` 대상이다.
- `PASS (service recovery)`: Safari preview 탭을 닫은 뒤에도 LeLab preview 1개가 카메라를 점유했다. 공식 `/camera-preview-stop`이 종료 신호만 남기고 release하지 못해, 모든 robot 작업이 inactive임을 확인한 상태에서 `lelab.service`만 재시작했다. 재시작 뒤 `/health` 정상, teleoperation·recording·inference inactive를 다시 확인했다.
- `PARTIAL (camera-only)`: 위 좌표를 적용해 `/dev/video4` 300-frame live homography 검사를 실행했다. ID 0·1·3은 계속 검출됐으나 ID 2 때문에 homography는 일부 프레임에서만 잠깐 성립했고 지속 jitter를 계산할 수 없었다. 실행 종료 코드는 `0`(한 번 이상 homography 성립)이지만 안정성 성공으로 판정하지 않는다.
- `FAIL (camera-only)`: 이어서 300 frames를 별도 집계한 결과 ID 0=300, ID 1=300, ID 2=0, ID 3=299였다. 마지막 frame에서 ID 2는 오른쪽 아래 흰 작업면 가장자리에 붙어 있어 바깥 흰 여백이 부족했다.
- `PASS (offline)`: Jetson OpenCV가 `/dev/video4` 문자열을 V4L2 camera name으로 열지 못한 사례를 반영해 두 camera-only 도구가 Linux `/dev/videoN`을 정수 index로 정규화하도록 수정했고 단위 테스트를 추가했다.
- `RELEASED`: Safari camera preview 탭을 닫았고 LeLab 재시작 뒤 detector가 카메라를 정상적으로 열어 종료 시 release했다.
- `NOT_VERIFIED`: 네 marker가 계속 보이는 조건의 homography jitter, intrinsic calibration, marker pose는 아직 검증하지 않았다.
- `PASS (camera-only, adjusted)`: 사용자가 ID 2를 안쪽으로 조정한 뒤 `/dev/video4` 300-frame 재검사에서 ID 0·1·2·3이 모두 300/300 검출됐다.
- `PASS (camera stability)`: 이어진 300-frame homography run의 모든 30-frame 주기 표본에서 네 ID와 homography가 준비됐고, 최근 30-frame 화면 중심 jitter는 약 0.20–0.22 mm RMS였다. 이 값은 이동 전 좌표 scale을 사용한 카메라 안정성 지표이며 절대 작업대 좌표 정확도 판정은 아니다.
- `STALE_CONFIG`: ID 2의 물리 위치가 바뀌었으므로 `configs/aruco_table.local.json`의 ID 2 좌표와 기존 1–2, 2–3, 0–2 실측 거리는 더 이상 유효하지 않다. 새 거리로 좌표를 다시 계산하기 전에는 로봇 목표 좌표에 사용하지 않는다.
- `USER_MEASURED (adjusted)`: ID 2 조정 후 중심 거리 1–2=260 mm, 2–3=325 mm, 0–2=424 mm를 다시 측정했다.
- `PASS (offline coordinates)`: 움직이지 않은 ID 0·1·3은 0–1=343, 3–0=277, 1–3=436 mm로 고정하고 ID 2만 최소제곱 적합했다. 새 좌표는 ID 2=(332.181,260.854), ID 3=(6.242,276.930) mm이며 ID 2 관련 세 거리의 잔차 RMS는 약 1.37 mm다.
- `PASS (config resolved)`: `configs/aruco_table.local.json`을 새 좌표로 갱신하고 parser 검증을 통과했다. stale-config 상태는 해소됐지만 intrinsic calibration 전까지 렌즈 왜곡 보정은 적용되지 않는다.
- `PASS (camera-only final)`: 새 좌표 설정으로 `/dev/video4` 300-frame homography run을 완료했다. 모든 주기 표본에서 ID 0·1·2·3과 homography가 준비됐고 종료 코드는 0이었다. 초기 안정화 뒤 최근 30-frame jitter는 약 0.04–0.11 mm RMS, 마지막 표본은 0.087 mm였다.
- `NOT_VERIFIED`: 천장 카메라 intrinsic calibration과 렌즈 왜곡 보정, 실제 로봇 기준 좌표 등록은 아직 수행하지 않았다.
- `PASS (print artifact)`: A4 세로 ChArUco 6×8 보드를 생성했다. 규격은 `DICT_4X4_50`, square 30 mm, marker 22 mm, IDs 10–33, 실제 board 180×240 mm다. 기존 작업대 ID 0–3과 충돌하지 않는다.
- `PASS (artifact verification)`: Jetson OpenCV 4.13에서 원본 marker ID 10–33을 24/24 검출했다. PDF는 A4 595.276×841.890 pt, 내장 원본 3600×4800 px, 배치 510.236×680.315 pt(180×240 mm)로 확인했고 렌더링 시 잘림·겹침이 없었다.
- `NOT_RUN (physical)`: ChArUco 실제 인쇄 크기 확인과 `/dev/video4` calibration frame 수집은 아직 수행하지 않았다.
- `PASS (user verified)`: 사용자가 A4 ChArUco 보드를 100%로 인쇄했고 체커 한 칸이 30 mm임을 실측했다.
- `PASS (camera-only live)`: 사용자가 보드를 천장 카메라 시야에 둔 상태에서 `/dev/video4` 640×480 90-frame 검사를 완료했다. captured 90/90, marker 최대 24/24·평균 23.3, ChArUco corner 최대 35/35·평균 33.567, 12 corner 이상 87/90으로 통과했다.
- `OBSERVED`: 첫 live 검사기는 OpenCV 4.13에서 제거된 `interpolateCornersCharuco`를 호출해 frame 처리 전에 종료됐다. 설치 버전의 `CharucoDetector`로 수정했고 재검사가 통과했다. 하드웨어나 설정 변경은 없었다.
- `NOT_RUN`: 다양한 위치·거리·기울기의 calibration frame 수집과 intrinsic parameter 계산은 아직 실행하지 않았다.
- `PASS (camera-only intrinsic calibration)`: 사용자 준비 확인 뒤 `/dev/video4` 640×480에서 60초간 ChArUco 자세 25개를 수집했다. 각 view는 28–35 corners를 포함했고 총 관찰 frame은 1,793개였다.
- `PASS (calibration quality)`: OpenCV `calibrateCamera` 결과 전체 reprojection RMS는 0.428 px, view별 평균 0.379 px, 최대 0.873 px였다. 계산 결과 SHA-256은 `fbdf8c83...f9c6c3`이며 `configs/c920_video4_intrinsics.local.json`에 보존했다.
- `PASS (config/code)`: `configs/aruco_table.local.json`이 위 intrinsic 파일을 참조하도록 갱신했고, `scripts/aruco_table.py`는 calibration이 있으면 frame을 undistort한 뒤 marker·homography·pose를 계산하도록 수정했다. 단위 테스트 13개가 통과했다.
- `NOT_RUN`: ChArUco 보드를 작업대에서 치운 뒤, 왜곡 보정된 ID 0–3 homography와 pose를 live 300 frames로 재검증하는 단계가 남았다.
- `NOT_VERIFIED`: intrinsic calibration은 완료됐지만 robot-base 좌표 등록과 실제 로봇 도달 정확도는 아직 검증하지 않았다.
- `PASS (camera-only undistorted workspace)`: 사용자가 ChArUco 보드를 치운 뒤 새 intrinsic을 적용한 `/dev/video4` 300-frame homography·pose 검사를 완료했다. 주기 표본에서 `pose_ready=true`였고 안정화 후 최근 30-frame jitter는 약 0.15–0.21 mm RMS, 마지막은 0.180 mm였다.
- `PASS (camera-only exact count)`: 별도 왜곡 보정 300-frame 집계에서 ID 0=300, ID 1=300, ID 2=300, ID 3=300, captured=300/300으로 통과했다.
- `PASS (ArUco stage 1)`: 천장 카메라 intrinsic, 렌즈 왜곡 보정, 네 작업대 marker 검출, pixel→table homography와 정지 안정성까지 camera-only 기준을 통과했다.
- `NOT_VERIFIED`: table 좌표와 robot-base 좌표의 등록, 약통 slot·basket 영역 확정, 실제 로봇 도달 정확도는 아직 수행하지 않았다.
- `USER_CONFIRMED (basket mapping)`: 바구니 marker는 ID 4=빨강, ID 5=초록, ID 6=파랑 순서다. ID 4–6은 바구니 추적·검증용이며 작업대 homography는 계속 ID 0–3만 사용한다.
- `FAIL (camera-only basket visibility)`: 왜곡 보정된 `/dev/video4` 300-frame 집계에서 ID 0=29, ID 1=300, ID 2=300, ID 3=300, ID 4=0, ID 5=0, ID 6=0이었다. 현재 화면에는 개별 바구니 marker 대신 ChArUco calibration board(ID 10–33)가 바구니 위에 놓여 있고, 그 배치가 작업대 ID 0도 가렸다.
- `BLOCKED (physical adjustment)`: ChArUco 보드를 작업 영역에서 완전히 치우고, 바구니별 ID 4·5·6을 천장 카메라를 향한 수평의 단단한 면에 흰 여백과 함께 노출하며, 바구니가 작업대 ID 0–3을 가리지 않도록 조정해야 한다. 조정 후 ID 0–6 exact-count 300-frame 검사를 다시 수행한다.

## 2026-09-21 천장 카메라 RealSense D435 교체

- `USER_REPORTED`: 기존 천장 수직 C920을 Intel RealSense D435로 교체했고 작업대 ArUco marker의 물리 크기는 유지했다.
- `PASS (identity/network)`: 현재 Jetson 주소는 `192.168.50.20`이다. 이 주소의 ED25519 host key가 기존 Jetson의 고정 지문과 일치했고, LeLab health 정상 및 teleoperation·recording·inference inactive를 확인했다.
- `PASS (camera identity)`: USB `8086:0b07`, serial `236223023645`의 RealSense D435가 USB 3에 연결됐다. `/dev/video0`은 Z16 depth, `/dev/video2`는 IR 계열, `/dev/video6`은 YUYV color stream이며 현재 640×480@30으로 60/60 frame read가 성공했다.
- `OBSERVED`: Jetson에는 `rs-enumerate-devices`와 `pyrealsense2`가 설치되어 있지 않다. 이번 검사는 V4L2 color stream만 사용했으며 depth↔color alignment는 아직 실행하지 않았다.
- `PASS (code/test)`: camera-only ArUco/ChArUco 도구와 table detector에서 V4L2 FOURCC를 선택할 수 있게 했고 관련 단위 테스트 12개가 통과했다. RealSense color는 `YUYV`를 사용한다.
- `FAIL (camera-only framing)`: `/dev/video6` 90-frame ArUco 검사에서 ID 3=87, ID 0·1·2·4·5·6=0이었다. 현재 영상은 작업대 일부와 marker 한 장만 온전히 포함해 좌표계나 calibration을 시작할 수 없다.
- `STALE_CALIBRATION`: 기존 `configs/c920_video4_intrinsics.local.json`은 C920 전용이므로 RealSense 영상에 사용하지 않는다. 작업대 marker가 움직이지 않았다면 table-mm 실측 좌표는 재사용할 수 있지만, 새 color intrinsic과 live homography 검증은 다시 필요하다.
- `BLOCKED (physical framing)`: RealSense 장착 위치·각도를 먼저 고정하고 ID 0–3과 바구니 영역이 모두 완전히 보이게 조정한다. 이후 30 mm ChArUco 보드로 color intrinsic을 재계산하고, 보드를 치운 뒤 ID 0–6 exact-count와 homography jitter를 재검증한다.
- `CORRECTION (three physical cameras)`: 현재 물리 카메라는 RealSense D435, Generic USB Camera, Orbbec Astra의 세 대다. 영상 확인 결과 `/dev/video4` Generic USB Camera는 엔드이펙터이고 `/dev/video6` RealSense color는 사선 천장 시야다. 따라서 `/dev/video2`와 `/dev/video6`은 서로 다른 물리 카메라가 아니라 같은 RealSense의 IR/color stream이다.
- `FAIL (basket recheck)`: RealSense color 300-frame 재검사에서 ID2=237, ID3=63, ID0·1·4·5·6=0이었다. 현재 영상에는 세 바구니와 내부 marker가 보이지만 ID4·5·6은 바구니 바닥 안쪽에 있어 사선 시야에서 테두리에 가려진다.
- `BLOCKED (Orbbec access)`: Orbbec Astra USB `2bc5:0401`은 연결되어 있으나 V4L2 node를 만들지 않는다. 설치된 Debian `libopenni2-0`과 임시 추출한 `NiViewer2`로 조회했을 때 `no devices found`였으며, LeLab `/available-cameras`에도 Astra가 없다. Orbbec 전용 OpenNI2/SDK driver 없이는 천장 정면 영상을 확인하거나 calibration할 수 없다.
- `SAFETY`: 재검사는 camera-only였다. LeLab health 정상, teleoperation·recording·inference inactive를 전후 확인했고 시스템 package 설치와 로봇 제어는 수행하지 않았다.
- `PASS (Orbbec OpenNI2 install)`: 사용자 승인으로 Orbbec 공식 `ros2_astra_camera` commit `f7e71d9c...`의 ARM64 OpenNI2 redist를 `/opt/orbbec-openni2`에 격리 설치했다. 실행 래퍼는 `/usr/local/bin/orbbec-openni-capture`, 공식 udev rule은 `/etc/udev/rules.d/99-obsensor-libusb.rules`다. 기존 Debian OpenNI2 파일은 덮어쓰지 않았다.
- `PASS (Astra streams)`: `/dev/astra`가 USB `001/011`을 가리키고, 독립 검사기는 `Astra 2bc5:0401` 한 대를 열었다. color·IR·depth sensor와 지원 mode를 열거했고 color RGB888 640×480 30/30, IR GRAY16 640×480 30/30 frame 획득 및 저장을 통과했다.
- `PASS (source verification)`: 참고용 공식 Orbbec SDK v1.10.37 ARM64 zip은 GitHub release digest `3c269b7e...`와 일치했다. 실제 설치한 OpenNI2 library SHA-256은 `d7231df0...`, Astra driver는 `b6511b00...`, non-mirrored 검사기는 `1ac5f7b9...`, udev rule은 `04bd6ef1...`이다.
- `PARTIAL (Astra ArUco view)`: 천장 정면 color frame의 SDK mirror를 끈 뒤 ID2·3은 검출됐다. ID0·1은 화면 아래에서 일부 잘렸고, 바구니 ID4·5·6은 흰 quiet zone 없이 바구니 바닥에 놓여 검출 후보로만 남아 ID 판독은 실패했다.
- `BLOCKED (physical adjustment)`: Astra 각도를 화면 아래쪽으로 조금 옮기거나 높여 ID0–3 전체를 완전히 포함하고, ID4·5·6은 각 바구니 상단의 흰 판 위에 10–20 mm 흰 여백과 함께 수평 부착해야 한다. 이후 live 300-frame exact count와 ChArUco intrinsic을 진행한다.
- `NOT_VERIFIED`: 재부팅 또는 실제 USB 재연결 후 udev 지속성, LeLab web preview 통합, Astra intrinsic/depth calibration과 table homography는 아직 검증하지 않았다.

### 천장 정면·사선 상시 웹 프리뷰

- `PASS (camera-only service)`: 천장 정면 Orbbec Astra와 천장 사선 RealSense D435 color를 한 페이지에 표시하는 MJPEG 프리뷰를 Jetson `http://192.168.50.20:8010/`에 배포했다.
- `PASS (autostart configured)`: `so101-camera-preview.service`를 systemd에 등록하고 `enabled`·`active`를 확인했다. Astra는 non-mirrored RGB888 640×480 OpenNI pipe, RealSense는 canonical by-id가 가리키는 YUYV 640×480 color stream을 사용한다.
- `PASS (live verification)`: `/health`에서 두 stream 모두 `ok=true`였고 frame count가 증가했다. Mac에서 2초간 Astra 약 2.6 MB, RealSense 약 1.9 MB의 MJPEG 데이터를 수신했으며 인앱 브라우저에서 두 실제 영상을 확인했다.
- `RESOURCE OWNERSHIP`: 이 서비스가 두 카메라를 계속 점유한다. ChArUco/ArUco 검사·녹화처럼 같은 카메라를 직접 여는 작업 전에는 `sudo systemctl stop so101-camera-preview.service`, 종료 후에는 `sudo systemctl start so101-camera-preview.service`로 복구한다.
- `SAFETY`: 설치 전후 LeLab health 정상, teleoperation·recording·inference 모두 inactive였다. robot serial, torque, motor control은 실행하지 않았다.
- `NOT_RUN`: 실제 Jetson 재부팅을 통한 자동 시작 검증과 USB 분리·재연결 복구 시험은 수행하지 않았다. systemd unit은 boot enable 상태다.
- `NOT_PUSHED`: 상시 프리뷰 코드와 기록은 Git commit·push하지 않았다.

### Astra intrinsic 완료 / RealSense 대기

- `PASS (Astra capture)`: 상시 프리뷰를 중지한 뒤 동일한 6×8 ChArUco 보드(square 30 mm, marker 22 mm)로 Astra OpenNI RGB888 640×480의 서로 다른 자세 30개를 수집했다.
- `PASS (Astra refined calibration)`: 재투영 오차가 큰 view 2개를 제외하고 28개로 재계산했다. 전체 RMS 0.478 px, view별 평균 0.450 px, 최대 0.878 px이며 결과는 `configs/astra_color_intrinsics.local.json`에 보존했다. SHA-256은 `2be8287a...8bde73`이다.
- `FAIL (workspace exact count before board capture)`: RealSense 300 frames는 ID0=267, ID1=297, ID2=0, ID3=296, ID4–6=0이었다. Astra 300 frames는 ID0=272, ID1=25, ID2=300, ID3=300, ID4=0, ID5=57, ID6=0이었다. 이 검사는 intrinsic 적용 전이며 ChArUco 보드가 중간에 시야로 들어온 조건을 포함하므로 최종 workspace 판정으로 사용하지 않는다.
- `BLOCKED (physical)`: RealSense intrinsic 수집을 위해 ChArUco 보드를 사선 카메라 화면 중앙에 전체가 보이도록 먼저 배치해야 한다. 현재 RealSense 화면에는 보드가 없다.
- `PHYSICAL FOLLOW-UP`: 최종 homography 검사 전 ID2의 강한 사선 왜곡을 줄이고, 바구니 ID4–6을 바구니 바닥이 아니라 흰 여백이 있는 상단 수평 판에 노출해야 한다.
- `PASS (resource recovery)`: 대기 중 `so101-camera-preview.service`를 다시 시작했고 두 stream의 `/health ok=true`를 확인했다. LeLab teleoperation·recording·inference는 모두 inactive다.
- `NOT_RUN`: RealSense intrinsic, 두 카메라의 intrinsic 적용 후 ID0–6 exact-count·homography jitter는 아직 수행하지 않았다.
- `NOT_PUSHED`: calibration code와 기록은 commit·push하지 않았다.

### Astra RGB-D 좌표 파이프라인 적용

- `DIRECTION CONFIRMED`: 사용자 제공 `CODEX_ASTRA_ARUCO_ROBOT_ARM_PROMPT.md`의 Camera→World→Robot Base→dry-run 방향은 기존 YOLO/ArUco/고정좌표 로드맵과 일치한다. 기존 구현을 교체하지 않고 단계별로 확장한다.
- `PHASE 1 PASS`: camera capture는 `/opt/orbbec-openni2`, RGB는 RGB888 640×480@30, ArUco는 `DICT_4X4_50`, reference ID0–3, basket ID4=red·5=green·6=blue, RGB intrinsic은 RMS 0.478 px다. ID0 검은 사각형 실측 폭은 75 mm이며 기존 좌표 단위는 mm다.
- `MISSING`: object marker ID, 3D `T_W_C`, robot-base 등록 `T_B_W`, object→grasp offset, robot workspace limits, Cartesian robot adapter는 아직 없다. 따라서 `robot_enabled=false`, dry-run만 허용한다.
- `PASS (OpenNI capability)`: Astra/OpenNI 2.3.0.85에서 RGB888와 DEPTH_1_MM 640×480@30, depth 단위 1 mm, `IMAGE_REGISTRATION_DEPTH_TO_COLOR=true`, depth-color sync=true를 확인했다.
- `PASS (300-frame RGB-D diagnostic)`: 300 frames/10.521 s(28.515 FPS), RGB-depth timestamp delta 중앙값 465.5 µs, 화면 중앙 depth 중앙값 891 mm, 전체 유효 범위 683–2414 mm, 평균 invalid 30.895%였다.
- `PASS (aligned marker depth)`: ID0=728 mm/std 0.163(300/300), ID2=901 mm/std 1.472(300/300), ID3=905 mm/std 0.244(300/300), ID4=788 mm(205 frames), ID5=781 mm(59 frames)로 11×11 ROI median depth를 얻었다.
- `PARTIAL (visibility)`: ID1은 15/300, ID6은 0/300이었다. 진단 영상 왼쪽 가장자리에 ChArUco board 일부가 남아 ID24·27·29·30·33도 검출됐다. 최종 workspace/바구니 판정 전에 보드를 완전히 치우고 ID0–6의 가림·흰 여백을 수정해야 한다.
- `RECHECK (board removed)`: 사용자 조정 뒤 Astra RGB-D 300 frames를 다시 검사했다. ID0=300, ID1=173, ID2=300, ID3=300, ID4=266, ID5=86, ID6=0 frames였고 각 검출 frame의 11×11 depth는 모두 유효했다. 중앙 depth 중앙값 889 mm, effective 28.47 FPS, RGB-depth timestamp delta 중앙값 470.5 µs였다.
- `PASS (board removal)`: 재검사 영상에는 ChArUco board와 보드 marker ID가 남아 있지 않았다.
- `BLOCKED (marker visibility)`: ID1은 화면 하단 경계와 흰 판 가장자리에 가까워 간헐 검출되고, 바구니 ID5는 반사/가림으로 불안정하며 ID6은 영상에는 들어오지만 ArUco ID로 해독되지 않는다. 기존 실측 좌표를 보존하려면 ID1 중심은 옮기지 말고 카메라 framing 또는 불투명 흰 backing을 보정한다. ID5·6은 바구니 위의 평평한 흰 판에 투명 덮개·반사 없이 다시 노출한 뒤 exact-count를 재실행한다.
- `PASS (ID1 backing)`: ID1 중심을 옮기지 않고 불투명 흰 여백을 추가한 뒤 재검사에서 ID1이 173/300에서 300/300으로 개선됐다. ID0·3도 300/300, ID2는 297/300이었다.
- `BLOCKED (basket markers)`: 같은 run에서 ID4=139/300, ID5=26/300, ID6=0/300이었다. 진단 영상상 세 marker가 투명 바구니 안쪽 바닥에 있어 플라스틱 테두리·반사 영향을 계속 받는다. ID4–6을 바구니 밖의 카메라를 향한 평평한 불투명 흰 판에 부착하고, ID6이 계속 0이면 DICT_4X4_50 ID6 70 mm를 재인쇄한다.
- `FAIL (basket adjustment recheck)`: 추가 조정 뒤 300-frame run은 ID0=180, ID1=0, ID2=287, ID3=300, ID4=0, ID5=0, ID6=0이었다. 중앙 depth 887 mm, effective 28.517 FPS, sync delta 중앙값 450 µs였다.
- `OBSERVED`: 진단 영상에서 ID4–6은 천장을 향한 수평면이 아니라 바구니 앞쪽의 기울어진 면에 있고, 아래의 반사성 회색 판이 작업대와 ID1 주변 조건을 바꿨다. 반사판을 제거하고 ID1은 직전 300/300 상태로 복원하며, ID4–6은 무광 흰색 카드 위에 완전히 평평하게 천장 방향으로 고정해야 한다.
- `PARTIAL (flat basket tags)`: 재조정 뒤 ID4=300/300, ID6=300/300으로 바구니 tag 두 개는 통과했고 ID5=261/300으로 개선됐다. depth 중앙값은 ID4=779 mm, ID5=785 mm, ID6=788 mm였다.
- `REGRESSION (reference tags)`: 같은 run에서 ID0=122/300, ID1=0/300, ID2=0/300, ID3=300/300이었다. 진단 영상에서 ID1·2 종이가 평탄하지 않거나 인쇄면/문양이 정상적으로 노출되지 않은 상태로 보인다. ID1·2를 뒤집힘 없이 인쇄면이 카메라를 향하도록 무광 흰 바탕에 완전히 평평하게 복원하고, ID0 여백도 확인해야 한다.
- `PARTIAL (latest RGB exact count)`: RGB-D diagnostic 두 번이 각각 첫 frame 뒤 OpenNI read에서 멈춰 결과에서 제외하고 안전하게 중단했다. 상시 preview의 Astra RGB 전용 경로로 300 frames/9.978 s를 별도 집계한 결과 ID0=232, ID1=0, ID2=86, ID3=300, ID4=300, ID5=128, ID6=238이었다.
- `OBSERVED (latest image)`: ID1의 오른쪽 외곽이 어두운 반사판과 이어져 흰 quiet zone이 끊기며 검출 후보조차 되지 않는다. ID2는 사각 후보로 잡히지만 dictionary decoding에 실패한다. ID1·2는 DICT_4X4_50, 70 mm로 재인쇄해 기존 중심에 맞추고 사방 무광 흰 여백을 확보하는 것이 필요하다.
- `RESOURCE RECOVERED`: 실패한 RGB-D helper 잔류가 없음을 확인했고 상시 preview를 복구했다. Astra·RealSense `ok=true`, teleoperation·recording·inference 모두 inactive였다.
- `PARTIAL (latest physical recheck)`: 상시 Astra RGB 300 frames/9.960 s에서 ID0=189, ID1=300, ID2=274, ID3=300, ID4=300, ID5=6, ID6=300이었다. ID1은 완전히 복구됐고 ID3·4·6도 통과했다.
- `REJECTED (looser detector)`: 별도 300 frames에서 기본/강화 detector를 같은 frame에 비교했다. 강화 설정은 ID0·2를 개선하지 못했고 ID5도 9→14 frames에 그쳤으며 잘못된 ID17을 1회 만들었다. false positive 위험 때문에 적용하지 않는다.
- `BLOCKED (print/flatness)`: ID0·2·5는 화면 안에 있으나 검출이 불안정하다. 세 marker를 DICT_4X4_50, 70 mm로 재인쇄해 기존 중심에 맞추고 무광 흰 바탕에 평평하게 부착한다. ID1·3·4·6은 현재 배치를 유지한다.
- `PARTIAL (latest replacement check)`: 프레임별 중복을 분리한 Astra RGB 300-frame 재검사는 ID0=294, ID1=300, ID2=35, ID3=300, ID4=0, ID5=300, ID6=299였다.
- `FAIL (duplicate basket ID)`: ID5가 한 frame에 두 번 검출된 frame이 32/300이었다. 위치 확인 결과 왼쪽 바구니 ID6과 가운데 ID5는 정상이며, 오른쪽 바구니의 ID4 예정 marker가 ID4로는 전혀 해독되지 않고 간헐적으로 ID5로 잘못 해독됐다.
- `NEXT (two markers only)`: 현재 배치에서 다시 교체할 것은 왼쪽 위 작업대 ID2와 오른쪽 바구니 ID4 두 장이다. 둘을 DICT_4X4_50, 70 mm로 정확히 재인쇄하고 기존 중심/위치에 평평하게 부착한다. 나머지 ID0·1·3·5·6은 유지한다.
- `PASS (ID2/ID4 replacement)`: 교체 후 MJPEG 300 frames에서 ID1–6은 모두 300/300, duplicate 0으로 통과했고 ID0은 289/300이었다.
- `PASS (direct raw confirmation)`: preview를 잠시 중지하고 Astra OpenNI RGB888 원본 300 frames/10.447 s를 직접 집계했다. ID1–6은 모두 300/300, duplicate 0으로 재확인됐고 ID0은 281/300이었다.
- `PARTIAL (ID0 only)`: 남은 대상은 오른쪽 아래 작업대 ID0 한 장뿐이다. 기존 중심은 유지하고 marker 오른쪽·아래까지 포함해 사방 무광 흰 여백을 더 넓힌 뒤 최종 exact-count를 실행한다.
- `IMPLEMENTED`: `scripts/orbbec_rgbd_pipe.cpp`, `scripts/astra_depth_diagnostic.py`, `configs/astra_rgbd.example.json`, `docs/ASTRA_RGBD_PIPELINE.md`를 추가했다. OpenNI 정합 실패 시 unaligned depth 출력은 차단된다.
- `IMPLEMENTED (M3 diagnostic)`: Camera XYZ, ID0–3 중심 기반 `T_C_W`/`T_W_C`, World XYZ, 재투영 RMS, 기준점 3D 잔차, depth-vs-PnP Z 차이를 camera-only diagnostic에 추가했다.
- `IMPLEMENTED (USB2 fallback)`: RGB-only와 Depth-only 640×480은 각각 연속 수집되지만 RGB+Depth 640×480이 첫 frame 뒤 정지하는 현상을 재현했다. 상시 preview는 유지하고 RGB-D 진단에만 320×240 `--low-bandwidth`와 multi-scale ArUco 검출을 추가했다.
- `PASS (updated offline tests)`: intrinsic scaling, deprojection, rigid transform, reference center parsing을 포함한 관련 테스트 21개가 통과했다.
- `NETWORK RECOVERED (2026-09-22)`: 사용자 재연결 뒤 `192.168.50.20` SSH·preview HTTP가 정상화됐다. 시작 전 LeLab health 정상과 teleoperation·recording·inference inactive를 재확인했다.
- `PASS (low-bandwidth RGB-D live)`: 320×240 smoke 30 frames와 stability 300 frames를 모두 연속 수집했다. 300 frames/10.533 s(28.482 FPS), sync delta 중앙값 33.305 ms, 중앙 depth 813 mm, 평균 invalid 32.606%였고 ID0–6 모두 검출·유효 depth 300/300이었다.
- `FAIL (M3 geometry accuracy)`: world pose 300/300에도 재투영 RMS 중앙값 2.393 px, 기준점 3D 잔차 ID0=43.82, ID1=48.06, ID2=137.00, ID3=128.16 mm였다. depth-vs-PnP Z 차이도 38.15–136.04 mm라 현재 `T_W_C`는 로봇 좌표로 사용할 수 없다.
- `DIAGNOSED`: 640↔320 marker 중심은 약 0.5배로 대응하고 OpenNI FOV focal 285.17 px도 ChArUco 축소 focal과 가까워 단순 해상도 scaling은 주원인이 아니다. IPPE 두 해, ITERATIVE, SQPNP 교체도 문제를 해결하지 못했다.
- `PHYSICAL MEASUREMENT COMPLETE`: 사용자가 ID0의 검은 ArUco 바깥 폭은 75 mm, ID5는 70 mm이며 ID0만 75 mm일 가능성이 높다고 보고했다. config는 기본 70 mm에 ID0만 75 mm override로 고쳤고 ID1–4·6은 70 mm 가정으로 명시했다.
- `PASS (reference remeasurement fit)`: 사용자 재실측 0–1=331, 1–2=275, 2–3=325, 3–0=272, 0–2=432, 1–3=434 mm를 최소제곱 적합했다. 새 중심은 ID0=(0,0), ID1=(331,0), ID2=(326.807,277.190), ID3=(-0.861,274.244) mm이며 거리 적합 RMS 2.626 mm, 최대 잔차 3.487 mm다.
- `FAIL (remeasured 3D recheck)`: 새 중심으로 30 frames를 재검사했지만 기존 intrinsic 기준 3D 잔차가 ID0=73.11, ID1=51.62, ID2=115.22, ID3=133.55 mm였다. factory FOV/영상 중심/zero-distortion 비교도 재투영 RMS는 1.941 px로 좋아졌으나 3D 잔차 64.91–106.06 mm라 채택하지 않았다.
- `REJECTED (common 75 mm assumption)`: ID0–6 모두를 75 mm로 본 이전 PnP 비교는 ID5 실측 70 mm와 모순되어 현재 판정에 사용하지 않는다. 단일 공통 pixel offset을 위쪽 약 62 px 옮기는 보정도 작업대 depth 경사를 샘플링한 결과라 계속 기각한다.
- `PASS (RGB-depth edge alignment)`: RGB Canny 경계와 depth 불연속 경계를 ±80 px에서 비교한 최적 정렬은 `(dx,dy)=(-2,-1)` px였고 matched fraction은 0.945(무이동 0.832)였다. RGB-depth 등록 자체는 거의 맞으므로 수십 pixel 정렬 오류 가설을 기각했다.
- `PHYSICAL RANGE CHECK (corrected size)`: ID5 실측 폭 70 mm를 적용한 live 30-frame 중앙값은 depth 771 mm, single-marker PnP Z 867.696 mm였다. 실제 직선거리 약 810 mm 대비 각각 −39 mm(−4.8%), +57.7 mm(+7.1%)로 둘 다 이전보다 가까워졌지만 depth가 조금 더 가깝다.
- `NOT_APPLIED (depth scale)`: 한 지점의 약식 줄자 측정만으로 810/771=1.051 보정계수를 적용하지 않는다. PnP Z와 물리 직선거리도 완전히 같은 양은 아니므로 추가 기준점 없이 보정하지 않는다.
- `IMPLEMENTED (per-ID size)`: RGB-D diagnostic과 config가 기본 70 mm 및 ID별 override를 지원하고 frame/summary에 사용 크기, single-marker PnP Z, depth 차이를 기록한다. 전체 단위 테스트 26개가 통과했다.
- `PARTIAL (live recheck visibility)`: 크기 수정 후 30 frames에서 ID1·2·4·5·6은 30/30, ID3은 1/30, ID0은 0/30이었다. 기준 ID 네 개가 동시에 없어 world pose는 0/30이므로 3D 좌표 정확도는 재판정하지 않았다.
- `PASS (visibility retry)`: 사용자 조정 후 30-frame smoke와 300-frame stability를 다시 실행했다. 최종 300 frames에서 ID0–6 모두 검출·유효 depth 300/300, world pose 300/300, 27.628 FPS, sync delta 중앙값 12.754 ms로 가시성과 수집 안정성은 통과했다.
- `FAIL (3D accuracy retry)`: marker별 크기를 적용해도 300-frame world reprojection RMS 중앙값 2.367 px, 기준점 3D 잔차는 ID0=75.47, ID1=52.71, ID2=115.50, ID3=135.52 mm였다. 이 `T_W_C`는 로봇 좌표로 사용할 수 없다.
- `OBSERVED (single-marker ranges)`: 300-frame depth/PnP Z 중앙값은 ID0 716/811.27, ID1 728/825.73, ID2 910/1085.09, ID3 896/964.14, ID4 762/843.86, ID5 769/867.70, ID6 776/901.66 mm였다. 위치별 차이가 일정하지 않아 공통 scale 하나를 적용하지 않는다.
- `IMPLEMENTED (depth 3D fit)`: ID0–3의 registered-depth Camera XYZ와 실측 world 중심을 no-scale Kabsch 강체변환으로 맞추고, 기준점 평면성·여섯 상호거리·fit 잔차를 frame/summary에 기록한다. 전체 camera-only 단위 테스트 28개가 통과했다.
- `PASS (depth plane stability)`: 300 frames 모두 depth 기반 pose가 계산됐고 기준점 plane RMS 중앙값은 1.994 mm였다. 네 기준점은 안정적인 한 평면으로 관측된다.
- `FAIL (depth metric geometry)`: depth 기반 강체변환 RMS는 33.949 mm, 기준점별 잔차는 ID0=33.23, ID1=35.91, ID2=28.69, ID3=37.36 mm였다. 여섯 Camera XYZ 거리는 fitted world 거리보다 모두 36.87–71.36 mm 길었다.
- `REJECTED (empirical similarity scale)`: 진단용 similarity fit은 Camera/world scale 1.151915(역수 0.868119), RMS 9.387 mm였지만 물리적 calibration 근거가 없는 배율이므로 config에 적용하지 않았다.
- `DIRECTION (2.5D)`: 고정 작업대의 XY는 검증된 ArUco homography를 사용하고, Z는 depth 평면 대비 상대 높이로 구하는 2.5D 경로가 현재 full metric Camera XYZ보다 적합하다. robot-base 등록과 실제 이동은 계속 차단한다.
- `IMPLEMENTED (2.5D dry-run)`: 매 frame ID0–3 중심 homography로 pixel→table XY를 계산하고, registered-depth 기준점 plane의 카메라 방향 signed distance로 table 대비 높이를 계산한다. frame/JSONL/summary와 진단 overlay에 기록한다.
- `PASS (2.5D 300 frames)`: ID0–6, homography, depth plane 모두 300/300이었다. 기준점 높이는 약 ±1.51 mm 이내, 바구니 ID4·5·6 높이는 56.765·56.217·54.556 mm였다.
- `PASS (2.5D stability)`: 바구니 marker XY 표준편차는 축별 최대 0.358 mm, 높이 표준편차는 최대 0.624 mm였다. homography reference XY가 거의 0 오차인 것은 네 기준점을 그대로 맞춘 정의상 결과이므로 독립 정확도 증거로 과장하지 않는다.
- `PASS (camera-only deploy)`: 기존 `/opt/so101-rgbd/astra_depth_diagnostic.py`를 사용자 홈 recovery backup에 보존하고 검증된 2.5D dry-run 도구와 example config를 `/opt/so101-rgbd/`에 배포했다. script/config SHA-256은 각각 `2be2c650...804d1`, `306fcfa3...b4dc`다.
- `OBSERVED (deploy verification)`: 설치 경로 직접 bytecode compile은 root 소유 `__pycache__` write 때문에 최초 permission denied였고, `/tmp` pycache를 지정한 재검증은 통과했다. `--help` 실행과 설치 hash 일치도 통과했다.
- `SAFETY (2.5D)`: 도구는 자동 실행되지 않으며 camera-only dry-run이다. robot target 승인·`T_B_W`·motion command는 추가하지 않았다. 종료 후 preview 두 stream 정상, 모든 LeLab 제어 inactive, helper 잔류 없음이다.
- `PASS (medicine foreground bootstrap)`: 사용자가 pickup 구역에 빈 약통/모형 한 개를 배치한 뒤 RGB-D snapshot 30 frames에서 ID0–6, homography, depth plane이 모두 30/30이었고 plane RMS는 1.514 mm였다.
- `PASS (pickup ROI proposal)`: depth-plane 대비 15–180 mm foreground를 분리하고, 작업대 ROI X=80–220 mm/Y=200–300 mm를 적용하자 현재 약통 후보 C11만 선택됐다. 중심은 pixel=(178.943,123.679), table=(140.254,242.293) mm, 높이 중앙값/최대값=42.240/58.379 mm였다.
- `IMPLEMENTED (camera-only candidate tool)`: `scripts/depth_foreground_candidates.py`와 ROI config를 추가해 `/opt/so101-rgbd/`에 배포했다. 설치 script/config SHA-256은 각각 `e3c94e47...8dd95`, `d9027af4...a0fd`다. 기존 config는 `astra_rgbd.example.json.pre-pickup-roi-20260922`로 보존했다.
- `LIMIT`: 현재 결과는 단일 위치·단일 snapshot의 foreground proposal이다. YOLO 약통 분류, 약품 식별, grasp pose, robot-base 좌표, 실제 집기 성공을 검증하지 않았다. 로봇 명령으로 사용하지 않는다.
- `BLOCKED (pose 2 occlusion)`: 약통을 세운 채 두 번째 위치로 옮긴 30-frame capture는 ID0=29, ID1=30, ID2=30, ID3=0, ID4–6=30이었다. 약통이 기존 ID3 중심 `(227.75,114.5)` px에 겹쳐 reference homography가 0/30이었고 후보 선택은 의도대로 실패 폐쇄됐다. ID3 전체가 보이도록 약통을 프리뷰 기준 왼쪽으로 조금 옮긴 뒤 재수집해야 한다.
- `PASS (pose 2 retry)`: 약통만 조정한 재수집에서 ID0–6, homography, depth pose가 모두 30/30이었다. ROI가 선택한 C5는 pixel `(198.679,111.109)`, table `(81.956,286.512)` mm, 높이 중앙값/최대값 `94.752/97.453` mm였고 RGB overlay에서 실제 흰색 약통과 일치했다.
- `OBSERVED (pose diversity)`: 첫 위치 대비 table XY 이동량은 약 73.2 mm로 사용자 이동 지시와 일치했다. 첫 위치 높이 42.240 mm는 그리퍼 아래에서 약통 일부만 component로 분리된 값이고, 두 번째 위치는 약통 전체 윤곽이 분리되어 94.752 mm로 커졌다. 높이 일관성 기준에는 첫 자세를 사용하지 않는다.
- `PASS (pose 3)`: 세 번째 위치에서 ID0–6, homography, depth pose가 모두 30/30이었다. 선택 C4는 pixel `(168.506,121.397)`, table `(169.861,250.251)` mm, 높이 중앙값/최대값 `95.932/98.958` mm였고 overlay에서 실제 약통 전체와 일치했다. 두 번째 자세 높이와의 차이는 1.180 mm다.
- `IMPLEMENTED (YOLO bootstrap export)`: 리뷰를 통과한 pose 2/3만 Jetson의 비 Git 경로 `/home/jetson3/so101-medicine-bootstrap/`에 image, class-0 YOLO pseudo-label, JSON metadata로 내보냈다. 실패/부분 가림 pose는 제외했다. export label은 `review_required=true`이며 학습 준비 완료를 뜻하지 않는다.
- `PASS (export tool deploy)`: margin·clip을 포함한 YOLO bbox 변환과 export 옵션을 camera-only 후보 도구에 추가했다. 관련 로컬 검사 19개가 통과했고 설치 script SHA-256은 `4c683acb...0abe`다. 기존 도구는 `/opt/so101-rgbd/depth_foreground_candidates.py.pre-yolo-export-20260922`로 보존했다.
- `PASS (2026-09-23 immediate repeatability)`: 현재 정지 자세를 연속 재촬영한 두 결과는 table XY 차이 0.933 mm, pixel 중심 차이 0.154 px, 높이 차이 0.849 mm였다. 두 번째 run은 ID0–6/homography/depth pose 30/30, plane RMS 1.230 mm였다.
- `OBSERVED (overnight movement)`: 전날 pose 3와 첫 재촬영의 XY는 19.368 mm 달랐지만 reference ID0–3 pixel 이동은 최대 1.275 px였다. 카메라 좌표계 붕괴가 아니라 사이에 약통이 조금 이동한 것으로 판정한다.
- `SKIPPED (near duplicate)`: 즉시 반복 표본은 안정성 확인에만 사용하고 학습 데이터에는 추가하지 않았다. 위치 다양성 확보 전 거의 같은 frame을 늘리지 않는다.
- `BLOCKED (pose 4 outside ROI)`: 네 번째 배치의 실제 약통 후보 C4는 table `(232.956,240.492)` mm, 높이 94.707 mm로 보였지만 pickup ROI X 최대 220 mm를 12.956 mm 벗어났다. 바구니 ID6에도 가까워 자동 선택과 YOLO export가 안전하게 생략됐다. ROI를 임의로 넓히지 않고 약통만 프리뷰 기준 오른쪽·위쪽으로 조금 조정한다.
- `BLOCKED (pose 4 retry partial selection)`: 조정 뒤 약통 전체 C4는 table `(198.975,315.094)` mm로 ROI Y 최대 300 mm를 벗어났고, ROI 안의 작은 하단 조각 C5 `(6×7 px, area 35, height 43.765 mm)`가 선택되는 약점을 발견했다. 해당 표본은 저장하지 않았다.
- `IMPLEMENTED (whole-object fail-closed gate)`: bootstrap 선택에 area 100–500 px, median height 70–120 mm 조건을 추가했다. 같은 실패 snapshot은 `selected=null`, 기존 정상 pose 2/3은 그대로 선택됐다. 로컬 회귀검사 21개 통과 후 Jetson에 배포했다.
- `PASS (filter deploy)`: 설치 script/config SHA-256은 `af39ecc4...e189`, `ce43a0d0...d9e1`이다. 이전 설치본은 `.pre-whole-object-filter-20260923` suffix로 보존했다.
- `PASS (pose 4 final)`: 약통 전체 후보 C3가 bbox `15×15 px`, table `(204.641,263.851)` mm, 높이 중앙값/최대값 `95.672/99.035` mm로 강화 필터를 통과했다. 기존 pose 2/3과의 XY 거리는 124.760/37.344 mm이며 overlay에서 실제 약통 전체와 일치했다.
- `PASS (third positive export)`: `pose_004` image, class-0 YOLO pseudo-label, JSON metadata를 비 Git bootstrap 경로에 저장했다. label은 `0 0.48906250 0.48958333 0.05937500 0.07916667`이다. 현재 검토 통과 positive는 pose 002–004 세 건이다.
- `PASS (empty ROI negative)`: 약통을 치운 RGB-D에서 `selected=null`이었다. ROI 경계의 작은 바구니 조각 C8은 area 18 px/height 56.401 mm라 whole-object filter가 거부했다. 시각 확인 후 `empty_001` image, 0-byte label, JSON metadata로 저장했다.
- `PASS (bootstrap audit)`: images/labels/metadata stem이 모두 일치했고 normalized label 범위가 유효했다. 현재 총 4표본(positive 3, negative 1)이며 Git에는 넣지 않았다.
- `COLLECTION TARGET`: 현재 수동 1단계는 positive 8 + negative 2를 목표로 한다. 이후에는 반복 확인을 줄이는 자동 수집 흐름으로 50–100개의 서로 다른 실제 frame을 준비한다. 수동으로 수십 번 확인시키지 않는다.
- `BLOCKED (pose 5 outside ROI)`: 실제 약통 전체 C3은 bbox `15×13 px`, table `(73.479,263.292)` mm, 높이 95.914 mm였으나 ROI X 최소 80 mm보다 6.521 mm 밖이었다. ID3에 가까워 ROI를 넓히지 않고 약통을 프리뷰 기준 왼쪽으로 조금 옮긴다. 표본은 저장하지 않았다.
- `PASS (pose 5 retry)`: C4가 bbox `16×13 px`, table `(111.516,252.533)` mm, 높이 중앙값/최대값 `95.539/98.630` mm로 통과했고 overlay에서 실제 약통 전체와 일치했다. 기존 pose 002–004와의 최소 XY 거리는 45.037 mm다.
- `PASS (fourth positive export)`: `pose_005` image/label/metadata를 저장했다. label은 `0 0.58750000 0.50208333 0.06250000 0.07083333`이며 pair audit 후 현재 총 5표본(positive 4, negative 1)이다.
- `PASS (hard negative 002)`: 약통 없이 비원통형 물체가 있는 영상에서 `selected=null`이고 ROI 내 15 mm 이상 후보도 없었다. 시각 확인 후 빈 label로 저장해 현재 총 6표본(positive 4, negative 2)이다.
- `SCOPE LOCKED`: 현재 class 0은 연구용 흰 원통형 약통 모형 `white_medicine_bottle_model`이다. 약 상자·펜 등 비원통형 물체는 negative이며, 실제 약품 신원이나 모든 약품 용기를 뜻하지 않는다. `configs/medicine_bootstrap.example.json`에 기록했다.
- `BLOCKED (pose 6 outside ROI)`: 방향을 바꾼 실제 약통 전체 C3은 bbox `14×25 px`, table `(242.674,296.894)` mm, 높이 93.204 mm였으나 ROI X 최대 220 mm를 22.674 mm 벗어났다. overlay에서 방향 다양성은 유효하지만 저장은 차단했다.
- `PASS (pose 6 retry)`: 조정 뒤 C3가 bbox `16×14 px`, table `(209.179,284.667)` mm, 높이 중앙값/최대값 `95.930/97.959` mm로 통과했다. 기존 표본과 최소 XY 거리는 21.305 mm이고 overlay에서 실제 약통 전체와 일치했다.
- `PASS (fifth positive export)`: `pose_006` image/label/metadata를 저장했다. label은 `0 0.48125000 0.46250000 0.06250000 0.07500000`이며 현재 총 7표본(positive 5, negative 2)이다.
- `BLOCKED (pose 7 outside ROI)`: C3은 bbox `16×27 px`, table `(59.110,259.918)` mm, 높이 94.439 mm로 실제 약통 전체였지만 ROI X 최소 80 mm를 20.890 mm 벗어났다. overlay에서 ID3 quiet zone에도 너무 가까워 저장을 차단했다.
- `BLOCKED (pose 7 retry merged)`: 왼쪽 조정 후 약통이 로봇 그리퍼 바로 아래로 들어가 robot component C0 bbox `30×95 px`에 연결됐다. 독립 whole-object 후보가 없어 `selected=null`로 저장을 차단했다.
- `BLOCKED (pose 7 retry 2 merged)`: 오른쪽 조정 후에도 약통 상단과 그리퍼 하단이 맞닿아 C0 bbox `40×93 px`로 연결됐다. 오른쪽에는 ID3이 있어 수평 이동만으로 여유가 부족하므로 약통을 대각선 아래·왼쪽의 기존 검증 공간으로 옮긴다.
- `PASS (pose 7 final)`: C3가 bbox `15×24 px`, table `(108.202,259.417)` mm, 높이 중앙값/최대값 `95.572/99.788` mm로 독립 검출됐다. pose 005와 XY는 7.640 mm로 가깝지만 bbox가 `16×13`에서 `15×24`로 달라 방향 변화가 영상에 반영됐다.
- `PASS (sixth positive export)`: `pose_007` image/label/metadata를 저장했다. label은 `0 0.59531250 0.50416667 0.05937500 0.11666667`이며 현재 총 8표본(positive 6, negative 2)이다.
- `PASS (pose 8 rotation)`: 같은 위치에서 수직축 기준 약 90° 회전한 약통 전체 C3가 bbox `16×14 px`, table `(105.678,272.885)` mm, 높이 중앙값/최대값 `96.537/98.685` mm로 선택됐다. pose 007과 XY 차이는 13.702 mm, bbox는 `15×24 → 16×14 px`로 달라졌다.
- `PASS (seventh positive export)`: `pose_008` image/label/metadata를 저장했다. label은 `0 0.59687500 0.47916667 0.06250000 0.07500000`이며 파일 stem 검사 후 총 9표본(positive 7, negative 2)이다.
- `BLOCKED (Astra preview after pose 8)`: 마지막 30-frame RGB-D 수집과 ID0–6/homography/depth pose 30/30은 통과했지만, 15:05 프리뷰 재시작 직후 Astra OpenNI color stream 시작이 실패했다. 이후 USB device open의 control request 실패가 반복되고 `/health`는 Astra `ok=false`, RealSense `ok=true`로 503이다. 단독 preview service 재시작으로 복구되지 않았다.
- `DIAGNOSIS (USB state)`: `lsusb`에는 Astra `2bc5:0401`이 bus 001 device 006으로 남아 있지만 OpenNI가 열지 못한다. LeLab teleoperation·recording·inference는 inactive다. 원인 확정 전 USB 재연결·reset·전원 조작은 실행하지 않았다.
- `NOT_RUN (pose 9)`: positive 목표 마지막 1건은 Astra RGB-D 복구 전까지 촬영하지 않는다. `NOT_PUSHED`: 이번 코드·문서는 commit/push하지 않았다.
- `PASS (Astra USB reconnect recovery)`: 사용자가 Astra USB를 현장 재연결한 뒤 2026-09-23 15:35–15:36 KST 프리뷰 health가 HTTP 200으로 회복됐고 Astra·RealSense 모두 `ok=true`, frame count 증가를 확인했다. LeLab health 정상, teleoperation·recording·inference inactive, 별도 RGB-D helper 잔류 없음이다.
- `PENDING (pose 009 physical placement)`: 기존 dataset은 positive 7, negative 2이고 pose 009는 없다. 약통만 다른 비가림 위치로 옮기는 사용자 조치를 요청했다. 새 RGB-D 수집·export는 아직 `NOT_RUN`이다.
- `PASS (pose 009 camera capture)`: 사용자 이동 뒤 검증된 low-bandwidth helper로 RGB-D 30 frames를 수집했다. ID0–6/homography/depth pose 30/30, plane RMS 중앙값 1.266 mm였다. 일회성 추가 ID38이 있어 exact-count 통과로 보지 않는다.
- `FIXED (foreground XYZ)`: 첫 후보 추출에서 depth Z=788 mm가 계산식 안에서 33.409 mm로 변해 약통 높이가 678.8 mm로 오판된 것을 확인했다. 독립 출력 배열로 XYZ를 구성하도록 수정했고 Jetson 단위 테스트 8/8, 동일 snapshot C3 높이 95.307 mm 선택을 통과했다. 기존 설치본은 backup 후 SHA `382679e6...` 수정본으로 교체·검증했다.
- `NOT_SAVED (pose 009)`: 현재 위치는 pose 006과 3.107 mm 차이로 거의 중복이다. 깊이 후보 C3는 약통 상단만 감싸고 하단 C6과 분리됐으며, 화면 왼쪽에 미확인 흰 원통형 물체도 있다. 수동 검토 박스는 임시로 확인했지만 dataset export하지 않았다. 기존 positive 7/negative 2 유지다.
- `PENDING (physical rotation)`: 왼쪽 흰 물체를 화면 밖으로 치우고 중앙 약통만 수직축 기준 약 90° 회전하도록 요청했다. 완료 후 새 frame에서 단일 클래스 물체, 독립된 whole-object bbox, 방향 다양성을 확인한다.
- `PASS (pose 009 final)`: 사용자 회전/물체 제거 후 Astra RGB-D 30 frames에서 ID0–6/homography/depth pose 모두 30/30, 추가 ID 없음, plane RMS 중앙값 1.740 mm였다. 선택 C3 table `(212.800,282.508)` mm, 높이 95.160 mm다. 깊이상 분리된 약통 하단까지 RGB 검토 bbox `(146,105,16,25)`로 포함해 `pose_009`를 저장했고 image/label/metadata pair audit는 총 10건(positive 8, negative 2)을 통과했다.
- `PASS (positive bbox review)`: 접촉시트에서 기존 양성 6건의 하단 누락/여유 부족을 확인했다. 원본 label·metadata를 Jetson 비 Git `review-backups/20260923_whole_bottle_bbox_review_v1/`에 보존하고 전체 약통 bbox로 수정했다. 수정안 접촉시트, 10쌍 구조/값 검사, label review history 보존을 확인했다. 새 review script 단위 테스트 2/2 통과다.
- `LIMIT (full-frame negatives)`: `empty_001`·`hardneg_002`의 원본 전체 화면에는 ROI 밖에 대상 약통이 남아 있어 빈 label로 full-frame YOLO를 학습할 수 없다. 원본은 변경하지 않았다.
- `PASS (ROI-only derivative)`: 고정 pixel crop `[128,85,215,140]`의 87×55 ROI 파생본을 Jetson 비 Git `so101-medicine-bootstrap/roi-v1/`에 10쌍 생성했다. positive 8 box가 모두 crop 안에 있고 negative 2 crop에는 대상 약통이 없음을 시각 확인했다. 변환 단위 테스트 3/3과 pair audit가 통과했다.
- `NOT_TRAINING_READY`: 10장의 작은 ROI bootstrap은 실제 YOLO 학습/성능 검증에 충분하지 않다. 파생본 `training_ready=false`; 다음은 물리적으로 다양한 실제 frame 50–100개와 독립 평가 표본 수집이다.
- `BLOCKED_AUTH (GitHub issue sync)`: 비공개 저장소 이슈 #4 조회를 시도했지만 현재 Mac의 GitHub CLI 인증이 없어 로그인 안내로 종료됐다. 이슈 본문/댓글은 변경하지 않았다. 이번 코드·문서는 `NOT_PUSHED`다.
- `NOT_DEPLOYED (latest M3 changes)`: 수집 안정성은 통과했지만 3D 정확도가 실패했으므로 최신 helper/diagnostic은 Jetson 설치 경로에 배포하지 않았다.
- `PASS (preview ownership recovery)`: 별도 SSH session에서 수동 실행된 preview 인스턴스가 systemd와 충돌하던 상태를 정리했다. systemd service stop 시 server/helper가 모두 종료됨을 확인한 뒤 단독 재시작했고 Astra·RealSense `ok=true`다.
- `PASS (previous M2 deploy)`: 이전 M2 버전은 관련 테스트 17개 통과 뒤 Jetson의 `/opt/orbbec-openni2/bin/orbbec-rgbd-pipe`와 `/opt/so101-rgbd/astra_depth_diagnostic.py`에 설치했었다. 위 최신 M3 변경과는 구분한다.
- `SAFETY`: 최신 작업에서도 카메라만 열었고 robot serial, torque, teleoperation, recording, inference, motor command는 실행하지 않았다. 종료 전 세 제어 상태를 다시 확인한다.
- `NOT_VERIFIED`: ID1–4·6 marker 폭(현재 70 mm 가정), 두 번째 camera-to-marker 실측 거리, 정확한 depth Camera XYZ/multi-marker `T_W_C`, `T_B_W`, 실제 로봇 이동.
- `NOT_PUSHED`: 이번 통합 코드와 문서는 commit·push하지 않았다.

## SSH 호스트 키 후보

2026-09-05에 `192.168.0.10`이 제시한 지문이다. 사용자가 ED25519 지문을 확인했고 프로젝트 전용 known-hosts 파일에 고정했다.

- RSA: `SHA256:E8sPqGMqQByy2SlJTg1RBxe3rWTp7yQfdDg7wKpJDyM`
- ECDSA: `SHA256:IBpxmbAkhxgYKSGgcTwLkb1yp6j4siHHUhWT3w6b8Lo`
- ED25519: `SHA256:dG9hPvs6yZcfIlZ0mPofx8lUPGYwDwW1M4UDzeSfx3o`

## 원본 지시서 무결성

- `CODEX_LELAB_SO101_RECOVERY.md`: `603ea8a57a21b28a019149b8f6ff25d407e1b5fe4e25dfe85e8c8d454362fb6f`
- `MAC_SSH_GITHUB_START.md`: `1827fc1b3484e9888ae81dbf398983b468c7b0583fb48614c6318a225f4e30cd`

## 다음 실행 한 단계

MD Phase 6의 다음 유효 단계는 검증 가능한 TCP를 먼저 정의한 뒤, 작업영역 전체에 분산된
World 기준점 4–8개에 TCP를 teach하는 것이다. 관절값은 8010의 읽기 전용 모니터가
LeLab `/ws/joint-data` broadcast에서 받아야 하며 `/joint-positions` REST endpoint는 사용하지
않는다. 각 sample에 known World point와 검증된 TCP offset이 함께 있을 때만 `T_B_W` fit에
포함한다. fit 후에도 Phase 7 Robot Base 좌표 overlay/dry-run을 먼저 수행하고 실제 이동은 차단한다.
YOLO 데이터 경로에서는 현재 통합 후보와 섞이지 않는 별도 촬영 세션의 평가 양성/음성을
먼저 확보한다. 같은 장면의 무작위 frame 분할은 독립 평가로 간주하지 않는다.

### 2026-09-23 프리뷰 기반 자동 후보 수집 smoke

- `PASS (camera-only)`: 기존 Astra 프리뷰를 읽는 ROI 검토 대기 수집기를 구현해 Mac 단위 테스트 4/4와 Jetson 20초 smoke를 통과했다. 로봇 또는 카메라 직접 점유 없음.
- `PASS (fail-closed)`: 검토 frame 38개에서 ID0–3 누락 10개를 버리고 정지 중복 11개를 버렸다. 독립성을 확인하지 않은 후보 1장만 비 Git review queue에 저장했으며 YOLO label·학습 데이터에는 추가하지 않았다.
- `PARTIAL (ID2 visibility)`: Astra MJPEG에서 ID2는 3배 확대 검사 시 30 frame 중 22 frame만 검출됐다. 기준 marker 중심과 카메라는 고정하고 ID2 주변 흰 여백/가림/반사를 개선할 필요가 있다.
- `PASS (end state)`: 천장 정면·사선 프리뷰 모두 정상이고 LeLab teleoperation·recording·inference 모두 inactive. 로봇·USB·토크·전원 조작 없음.
- `NEXT (physical)`: ID2 가시성을 개선하고 약통만 ROI 내 여러 새 위치/회전으로 묶어 바꾼 뒤 수집한다. 사람 검토 없는 자동 label/학습 또는 로봇 이동은 하지 않는다. 이슈 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.
- `PASS (2-minute candidate run)`: 사용자 준비 확인 후 기존 프리뷰를 읽는 수집기를 120초 실행했다. decoded 3606/검사 228 frame 중 marker 누락 70, 불안정 99, 중복 47을 거르고 ROI/context 후보 4장만 비 Git review queue에 저장했다. 네 장의 ROI에 흰 약통이 보이는 것을 시각 확인했으나 whole-object bbox·기존 bootstrap과의 독립성은 미검증이므로 아직 학습 수에 포함하지 않는다.
- `PASS (post-run safety)`: Astra·RealSense 프리뷰 모두 `ok=true`, LeLab 세 제어 inactive. 로봇·토크·전원·USB 조작 없음. GitHub issue 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.
- `PASS (second candidate run)`: 사용자와 함께 180초 추가 수집해 검토 대기 후보 10장을 별도 비 Git queue에 저장했다. 검사 342회에서 기준 marker 누락 147회, marker shift 초과 0회였다.
- `REJECTED (ROI clipping)`: 추가 run의 candidate_001·005·007·008은 약통이 crop 경계에 잘려 전체 약통 positive로 사용할 수 없다. 나머지 6장과 첫 run 4장은 bbox·중복 검토 전이므로 학습 표본으로 **확정하지 않았다**. 두 run 총 14장 중 적어도 4장 제외; 학습 및 로봇 동작 `NOT_RUN`.
- `PASS (high-resolution candidate capture)`: 기존 수집기 파일을 보존하고 v2를 Jetson 사용자 홈에서 camera-only 검증했다. 정지 장면 12초 smoke의 후보 1장에 대해 기존 87×55 ROI/320×240 context와 174×110 ROI/640×480 context가 모두 저장됐고 shape·stem·manifest를 확인했다. smoke 장면은 학습 수에 추가하지 않는다.
- `PENDING (diverse frames)`: 이전 14장은 87×55 원본으로만 저장돼 해상도 복원이 불가능하다. 위치가 기존 8개 또는 서로 가까운 후보가 있어 독립 표본 수는 아직 미확정이다. 새 수집은 사람이 약통 배치를 바꾸는 동안만 의미가 있으며, 50–100개 실제 변화와 독립 평가 분할 전 `training_ready=false`다.
- `PASS (post-v2 safety)`: 두 프리뷰 `ok=true`, LeLab 세 제어 inactive. 로봇·USB·토크·전원 조작 없음. GitHub issue 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.
- `PASS (5-minute high-resolution capture)`: 사용자 시작 확인 후 카메라-only v2를 300초 실행했다. 9014 decoded/573 검사 frame에서 31개 검토 대기 후보를 저장했고 각 후보의 174×110 ROI 및 640×480 context 쌍을 보존했다. 기준 marker shift 초과 0회, 기준 ID 누락 182회는 fail-closed로 버렸다.
- `PASS (conservative ROI screen)`: 새 비파괴 감사 도구와 단위 테스트 3/3을 통과했다. 31장 중 몸통이 ROI 경계에 닿는 13장, 보라색 몸통 확인이 안 되는 3장을 분리했고 15장을 `needs_human_review`로 남겼다. 가까운 위치의 후보 쌍도 있어 독립 학습 표본 수는 미확정이며 새 YOLO label·평가 분할·학습은 `NOT_RUN`이다.
- `PASS (post-capture safety)`: Astra·RealSense 프리뷰 모두 `ok=true`, LeLab teleoperation·recording·inference 모두 inactive. 로봇·토크·USB·전원 조작 없음. GitHub issue 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.
- `PASS (bbox proposals only)`: 감사 통과 15장에 빨간 약통 전체 박스 overlay와 제안 JSON을 비 Git queue에 생성했다. 접촉시트 육안 확인에서 004·012는 그리퍼가 뚜껑에 닿아 보이고 근접 위치 후보 쌍도 있어 사용자 검토가 필요하다. 새 YOLO label 0개, `training_ready=false`, 학습 `NOT_RUN`.
- `PASS (provisional ROI export)`: 004·012를 제외한 13개 174×110 ROI 박스 제안을 원본과 분리해 export했다. stem/shape/normalized label/metadata safety flag/exact duplicate 검사를 통과했지만 임시 색상 기반 라벨이고 중복 검토가 남아 `training_ready=false`다.
- `PASS (full-frame recovery)`: 좁은 ROI에서 잘린 장면도 640×480 context에 남아 있어 전체 31장에서 약통 몸통 후보가 각각 하나씩 검출됐다. 004·012를 제외한 29개 full-frame 박스 overlay를 육안 확인했다. 새 도구 단위 테스트 3/3 통과다.
- `REJECTED (scope metadata)`: 최초 `provisional-fullframe-v1`은 이미지/라벨 값은 정상이지만 dataset scope를 `pickup_roi_only`로 잘못 기록해 사용 금지했다. 원인 보존을 위해 삭제하지 않았다.
- `PASS (provisional full-frame v2)`: 수정된 export 도구로 `provisional-fullframe-v2` 29장을 `scope=full_frame`으로 새로 생성했다. stem 일치, 640×480 shape, class 0 normalized 범위, review/training/identity/robot safety flag를 검증했다. 한 세션 임시 양성만 있고 진짜 full-frame negative와 독립 평가 표본이 없어 학습 `NOT_RUN`, `training_ready=false`다.
- `PASS (first true full-frame negative)`: 사용자가 약통을 화면 밖으로 치운 뒤 정지 frame을 수집했다. 자동 약통 몸통 후보 0개와 전체 화면상 약통 부재를 확인하고 `empty_fullframe_001` 640×480 이미지·빈 label·metadata를 별도 `fullframe-negatives-v1`에 저장했다. 새 export 도구 단위 테스트 2/2 및 pair/shape/safety metadata 검사가 통과했다.
- `NEXT (hard negatives)`: 같은 빈 장면 복제는 중단한다. 약통 없이 펜·작은 상자·휴대폰 등 비대상 물체를 pickup 구역에 둔 실제 hard-negative가 필요하다. 양성 29장은 임시 제안이고 전체 목표 50–100개·독립 평가 분할 전 `training_ready=false`, 학습/로봇 동작 `NOT_RUN`.
- `PASS (first hard negative)`: 사용자가 작은 흰색 직사각형 비대상 물체를 pickup 구역에 둔 뒤 640×480 정지 frame을 수집했다. 전체 화면상 약통·손 부재와 약통 몸통 후보 0개를 확인하고 `hardneg_fullframe_001` 이미지·빈 label·metadata를 별도 저장했다. 현재 진짜 full-frame 음성은 empty 1 + hard negative 1이다.
- `NEXT (second hard negative)`: 현재 비대상 물체를 치우고 형태가 다른 펜 또는 휴대폰 한 개를 배치한다. 같은 장면 반복 저장은 하지 않으며 학습/로봇 동작은 계속 `NOT_RUN`이다.
- `PASS (second hard negative)`: 약통 없이 흰 작업 영역에 놓인 펜 한 개를 확인했다. 보라색 약통 몸통 후보 0개, 640×480 image, 빈 label, `training_ready=false`, `robot_target=false`를 검증하고 Jetson 비 Git 경로 `fullframe-hardnegative-002`에 저장했다.
- `PASS (combined full-frame candidates)`: 임시 양성 29장과 검토된 음성 3장(empty 1, 흰 직사각형 1, 펜 1)을 비파괴 병합했다. `provisional-fullframe-combined-v1` 총 32장의 stem/pair/shape/count와 safety flag 검사가 통과했다.
- `NOT_TRAINING_READY`: 양성은 한 촬영 세션의 색상 기반 임시 제안이고 음성은 3장뿐이며 독립 평가 세트가 없다. 다음은 휴대폰 같은 어두운 직사각형 hard negative와 최소 21개의 추가 다양한 양성이다. 학습·추론·로봇 구동은 `NOT_RUN`이다.
- `PASS (phone hard negative)`: 약통 없이 흰 작업 영역 중앙에 놓인 어두운 직사각형 휴대폰 한 개를 640×480 전체 화면에서 확인했다. 손은 없고 ID0–6과 세 바구니가 보였다. 보라색 약통 몸통 후보 0개, 빈 label, safety flag 검사를 통과했다.
- `PASS (combined full-frame v2)`: 휴대폰 음성을 추가해 `provisional-fullframe-combined-v2`를 비파괴 생성했다. 총 33장(임시 양성 29, 검토 음성 4), stem/pair 일치, 전 이미지 640×480, `training_ready=false`, `robot_enabled=false`를 확인했다.
- `NEXT (positive diversity)`: 음성 종류를 늘리는 1차 단계는 완료했다. 휴대폰을 치우고 연구용 흰 약통 모형만 작업 영역의 새 위치·방향에 두어 최소 21개의 추가 다양한 양성을 수집한다. 독립 평가 분할과 학습·추론·로봇 구동은 여전히 `NOT_RUN`이다.
- `REJECTED (new positive 01 near-duplicate)`: 새 640×480 frame에서 약통 전체와 ID0–6을 확인하고 full-frame 박스 `[374,234,31,41]`를 제안했으나, 중심 `(389.5,254.5)` px가 기존 `candidate_027` 중심과 3.54 px밖에 다르지 않았다. 기존 장면과 사실상 같은 위치이므로 label/export 및 29개 양성 수 합산을 하지 않았다.
- `NEXT (sparse placement)`: 기존 양성 중심 분포에서 안전 후보는 대략 `(460,255)` px다. 현재 위치에서 프리뷰 기준 오른쪽으로 약통 폭 약 2개 이동하되 ID1 검은 마커와 닿지 않게 하고, 뚜껑 방향도 약 90° 바꾼다.
- `BLOCKED (2026-09-27 active teleoperation)`: 사용자 재개 요청 후 Jetson 연결과 두 preview `ok=true`를 확인했지만 LeLab `teleoperation_active=true`였다. recording/inference는 inactive다. 한 버스 제어 소유권 원칙에 따라 새 촬영·label export를 실행하지 않았고 텔레오퍼레이션도 임의 종료하지 않았다. 사용자가 LeLab에서 Stop 후 현장 정지를 확인해야 한다.
- `NOT_DEPLOYED (export v4)`: 이전 중단 시도에서 stem-prefix 지원 exporter의 Jetson 배포가 완료되지 않았고 `/home/jetson3/export_medicine_label_proposals_v4.py`도 존재하지 않았다. 텔레오퍼레이션 종료 확인 후 다시 배포·검증한다.
- `PASS (web review console)`: 8010 상시 프리뷰에 카메라-only 약통 촬영/검토 UI를 추가했다. 양성/음성 촬영, ID0–3 검사, 작업영역 보라색 몸통 박스, 기존 양성과의 중심 거리, 승인/제외, 원본 보존, `training_ready=false`, `robot_enabled=false`를 제공한다.
- `PASS (web deploy)`: 기존 server는 `/opt/so101-camera-preview/camera_preview_server.py.pre-web-review-20260927`에 백업했다. 서비스 재시작 뒤 두 preview `ok=true`, `/api/review` 정상, 브라우저에서 촬영 버튼·통계·검토 카드가 표시됐다.
- `PASS (web workflow smoke)`: 현재 중앙 약통은 기존 양성과 6.265 px 차이라 `near_duplicate`로 차단됐다. 화면 왼쪽의 두 번째 약통도 사람 검토에서 확인해 해당 건을 제외 처리했다. export 파일은 0개이며 원본/metadata는 보존됐다.
- `OBSERVED (existing 8011 app)`: `/home/jetson3/so101_vlm_capture`의 기존 3카메라 VLM 사진·동작 영상 UI가 8011에서 실행 중이다. 8010은 빠른 YOLO 박스/중복 검토, 8011은 풍부한 VLM/동작 라벨 수집으로 역할을 분리했고 기존 8011 코드는 변경하지 않았다.
- `PASS (canonical USB recheck)`: 현재 `5AE6085272`(Leader)→ACM1, `5AE6058306`(Follower)→ACM0이며 LeLab robot record도 leader ACM1/follower ACM0다. raw ACM 번호는 재열거 결과이므로 안정 ID 역할과 모순되지 않는다.
- `IMPLEMENTED (T_B_W preparation)`: 4–8개 teach pair rigid fit/residual 도구와 버스 비접속 URDF FK 도구를 추가했다. 로컬 단위 테스트는 각각 3/3 통과했고 Jetson에서 실제 SO-101 `base→gripper` 5-joint chain, zero pose gripper origin `[20.615,-277.473,266.852]` mm, rotation determinant 1.0을 확인했다.
- `BLOCKED_AUTH (physical teach)`: 다음 MD 단계는 follower TCP를 4–8개 World 기준점에 teach하는 실제 모터 작업이다. LeRobot connect는 calibration write, torque-disabled configure, motor register write를 수행한다. 현장 안전 확인과 사용자 명시 승인 전에는 시작하지 않는다. `gripper` link→실제 tip offset도 미측정이다.
- `AUTHORIZED/RUN (safe-height teleoperation dry run)`: 사용자가 현장 장애물 제거·정지 준비 조건의 짧은 캘리브레이션 준비 구동에 `진행`으로 승인했다. 시작 전 두 preview 정상, recording/inference/teleoperation inactive, stable ID 기준 Leader→ACM1·Follower→ACM0를 재확인했다.
- `OBSERVED (transient ID4 start failure)`: 첫 시작은 Follower ID4 `Lock` write의 `There is no status packet`으로 실패했다. 제어 잔류가 없음을 확인하고 read-only broadcast ping에서 ID1–6 전부 model 777 응답을 확인한 뒤, 조건을 바꾸지 않은 1회 재시도는 성공했다.
- `INCIDENT (REST joint read bus collision)`: 텔레오퍼레이션 중 `/joint-positions`를 호출하자 worker의 동시 `Goal_Position` sync write가 `Port is in use`로 실패하고 세션이 자동 종료됐다. 추가 재시도는 하지 않았다. 이후 teach 수집은 serial bus를 다시 여는 REST endpoint가 아니라 기존 `/ws/joint-data` broadcast만 구독한다.
- `PASS (joint→FK plumbing)`: 충돌 직전 얻은 URDF radian 관절값을 `configs/fk-safe-pose-20260927.json`에 `use_for_robot_world_fit=false`로 기록했다. 오프라인 FK 결과 `base→gripper` link origin은 `[12.807,-117.958,127.822]` mm였다. 실제 TCP가 아니므로 World→Base fit에는 사용하지 않는다.
- `PASS (post-run safe state)`: 두 preview는 계속 `ok=true`이며 LeLab teleoperation·recording·inference는 모두 inactive다. 실제 World teach point, TCP offset 측정, `T_B_W` fit은 아직 `NOT_RUN`이다.
- `PASS (passive joint web monitor)`: 8010 비전 콘솔에 LeLab `/ws/joint-data`를 직접 구독하는 읽기 전용 관절 패널과 JSON 복사 기능을 추가했다. `/joint-positions`, `/move-arm`, `/stop-teleoperation` 호출은 코드에 없고 copied sample은 기본 `use_for_robot_world_fit=false`다. 회귀 테스트 11개 통과 후 SHA `b1286a8a...943`로 배포했으며 기존 파일은 `.pre-joint-ws-20260927T1532`로 백업했다.
- `PASS (web UI verification)`: 브라우저에서 두 카메라 preview, `WebSocket 연결됨 · 텔레오퍼레이션 관절 방송 대기`, 읽기 전용 설명과 복사 버튼을 확인했다. 서비스 재시작 뒤 두 카메라 health `ok=true`; 로봇은 다시 움직이지 않았다.
- `PASS (web collection expanded)`: 8010 queue는 총 240건, approved 52, excluded 57, blocked 131로 늘었다. 승인 세부는 positive 32, negative 20이다. blocked는 주로 near-duplicate이며 원본은 삭제하지 않았다.
- `PASS (non-destructive candidate preparation)`: 기존 `provisional-fullframe-combined-v2` 33건과 웹 승인 52건을 새 `training-candidates-audit-v1`로 감사했다. 입력 85건에서 기존 양성 내부 12px 미만 위치 중복 14건을 별도 exclusion 목록으로 남기고 positive 47, negative 24, 총 71쌍을 생성했다. images/labels/metadata 수가 모두 71로 일치하고 exact image duplicate는 없었다.
- `PASS (candidate visual audit)`: 양성 접촉시트의 47개 빨간 bbox가 연구용 약통 모형 전체와 일치함을 확인했다. 음성은 empty·흰 직사각형·펜·휴대폰 및 웹 음성으로 구성되지만 일부 웹 음성의 장면 변화가 작아 완전히 독립적인 24장으로 과대평가하지 않는다.
- `NOT_TRAINING_READY`: prepared audit는 `training_ready=false`, `independent_evaluation_ready=false`, `robot_enabled=false`다. 같은 카메라/세션 frame을 무작위로 나눈 평가는 금지하며, 다음은 별도 세션의 독립 평가 표본이다. proximity 임시 감사의 첫 실행은 normalized label string을 float로 변환하지 않아 실패했고 변환 후 61 positive/47 position component를 확인했다.
- `PASS (end state after data audit)`: 두 preview `ok=true`, LeLab teleoperation·recording·inference 모두 inactive다. 데이터 감사 중 로봇·토크·USB·전원은 조작하지 않았다.
- `PASS (separate evaluation queue)`: 8010에 `독립 평가 표본 촬영 · 별도 큐`를 추가했다. 기본 저장 경로는 비 Git `/home/jetson3/so101-medicine-bootstrap/evaluation-web-v1`이고, `training-candidates-audit-v1`을 중복 기준으로 사용한다. 평가 양성/음성 촬영·검토·승인은 학습 후보 큐와 물리적으로 분리된다.
- `PASS (evaluation UI deploy)`: 회귀 테스트 10개 통과 후 camera server SHA `18e4da82...4171`을 설치했고 기존본은 `.pre-eval-queue-20260927T1600`으로 보존했다. 첫 restart 묶음 명령 뒤 기존 process가 남아 evaluation API가 404였고, restart를 단독 실행해 frame counter 초기화·`/api/eval/review` HTTP 200·빈 queue·브라우저 새 패널을 확인했다.
- `NEXT (independent evaluation capture)`: 학습 후보 버튼은 더 사용하지 않는다. 카메라·보드·ArUco는 고정하고, 별도 평가 큐에 학습 위치와 다른 양성 10개와 장면이 다른 음성 5개를 한 장씩 수집한다. 완료 전 학습/추론은 `NOT_RUN`이다.
- `PASS (additional training-queue salvage)`: 사용자의 추가 촬영은 독립 평가 큐가 아니라 기존 학습 후보 큐에 저장됐다. 기존 승인본 대비 positive 12개·negative 6개가 추가돼 총 approved positive 44개·negative 26개가 됐다. 원본은 삭제하지 않았다.
- `PASS (candidate audit v2)`: legacy 33건과 갱신된 web 승인 70건을 비파괴 `training-candidates-audit-v2`로 다시 감사했다. input 103, kept positive 59, negative 30, 기존 legacy 양성 위치 중복 excluded 14이며 `training_ready=false`, `independent_evaluation_ready=false`, `robot_enabled=false`를 유지했다.
- `REVIEW_REQUIRED (negative scope)`: v2 음성 접촉시트에는 현재 검출 범위인 full frame 가장자리에 손과 작은 물체가 보이는 frame이 있다. 연구용 약통 모형이 화면 안에 남은 frame이 있다면 음성으로 사용하지 않도록 개별 재검수가 필요하다.
- `PASS (evaluation-only UI)`: 추가 혼합을 막기 위해 8010의 기존 학습 양성/음성 촬영 버튼을 disabled 처리했다. Jetson 설치 SHA-256은 `5b0491f3...4cd0`, 백업은 `.pre-eval-only-20260927T1632`이다. 부브라우저에서 학습 버튼 disabled·평가 버튼 enabled·평가 total 0을 확인했다.
- `PASS (end state after v2 audit)`: Astra·RealSense preview는 모두 `ok=true`, LeLab teleoperation·recording·inference는 모두 inactive였다. 로봇·토크·USB·전원 조작은 수행하지 않았다. 독립 평가는 아직 `0/15` 이므로 다음은 아래 평가 버튼으로 양성 10개·음성 5개를 새로 수집하는 것이다.
- `OBSERVED (evaluation threshold too strict)`: 독립 평가 큐는 total 19, approved negative 5, blocked positive 14였다. positive 차단 중 11개가 중심점 12 px 기준의 `near_duplicate`, 3개가 `workspace_target_count_not_one`였다. 화면 검수에서 near-duplicate 후보들은 서로 다른 위치에 정상 bbox로 보여 12 px 정책이 과도하다.
- `PREPARED_NOT_DEPLOYED (evaluation 3 px policy)`: 기존 학습 큐 12 px 기준은 유지하고 평가 큐만 3 px로 조정하는 로컬 코드를 준비했다. 기존 near-duplicate 11개 중 거리 3 px 이상 10개를 재검토 대기로 복구하고 2.915 px 1개는 차단 유지할 예정이다.
- `BLOCKED_NETWORK`: 배포 직전 `192.168.50.20:22`와 `:8010`이 모두 timeout으로 변했고 브라우저도 `ERR_CONNECTION_TIMED_OUT`을 표시했다. 로컬 수정은 Jetson에 `NOT_DEPLOYED`, 기존 metadata 재분류도 `NOT_RUN`이다. 사용자가 Jetson Wi-Fi/전원 연결을 복구한 뒤 계속한다.
- `PASS (evaluation 3 px deploy)`: 사용자의 네트워크 복구 후 학습 큐는 12 px를 유지하고 평가 큐만 3 px를 사용하는 코드를 배포했다. server/module SHA-256은 `6c912bc7...01a0`, `f0c9160a...7689`이며 설치 전 코드와 평가 큐 전체를 `pre-eval-3px-20260927T2019`로 보존했다.
- `OBSERVED (first install command incomplete)`: 최초 복수 명령에서 백업만 실행되고 설치 두 명령이 반영되지 않아 설치 hash가 기존값으로 남았다. service를 다시 중지하고 파일을 각각 설치한 뒤 예상 hash 일치를 확인해 복구했다.
- `PASS (evaluation reclassification)`: 비파괴 queue 백업 후 추적 기록을 남기는 별도 도구로 sole `near_duplicate` 11개 중 거리 3 px 이상 10개를 `pending_review`로 복구했다. 2.915 px 1개와 target-count 실패 3개는 blocked로 남겼고 자동 승인/자동 export는 0개였다.
- `PASS (evaluation approved set)`: UI 상태와 원격 metadata/export 교차 확인 결과 approved 15 = positive 10 + negative 5, export images/labels/metadata 각 15개였다. 양성 label 10개와 빈 음성 label 5개가 일치했다.
- `REVIEW_REQUIRED (evaluation internal duplicate)`: 승인 양성 10개를 서로 비교하니 `20260927T074028_614344Z`와 `20260927T073948_405741Z`의 중심 거리가 1 px였다. 앞의 frame이 bbox crop Laplacian variance 2974.911로 뒤 frame 2776.703보다 선명하므로 선명한 한 장만 최종 평가에 사용한다. 원본/승인본은 삭제하지 않았다. 현재 유효 독립 평가는 positive 9 + negative 5이며 새 위치 positive 1개가 더 필요하다.
- `PARTIAL (angled preview ownership)`: 8010 재시작 후 Astra는 정상이지만 RealSense `/dev/video4`는 LeLab uvicorn PID 239863이 점유해 8010이 열지 못했다. LeLab을 임의 정지하지 않았고 USB도 건드리지 않았다. 평가 저장본 검수와 Astra 촬영은 가능하지만 사선 preview는 추가 조정이 필요하다.
- `BLOCKED (additional evaluation positive)`: 재연결 뒤 새 위치의 평가 양성 `20260927T112718_990769Z`를 촬영했지만 marker 0–3만 검출되고 약통 색상 본체 후보가 0개라 `workspace_target_count_not_one`으로 차단됐다. 약통이 follower gripper 바로 아래에 가려지고 색상 면이 거의 보이지 않았다. 승인/export는 하지 않았으며, 그리퍼 그림자 밖의 새 위치에서 색상 면을 천장 카메라 쪽으로 보이게 한 양성 1개가 여전히 필요하다.
- `PASS (evaluation positive target reached)`: 사용자 재배치 뒤 `20260927T112957_608824Z`에서 marker 0–3, 약통 몸통 후보 1개, bbox `[378,223,27,41]`, 기존 학습 양성 최근접 거리 12.54 px를 확인했다. overlay 육안 검수 후 승인했으며, 기존 1 px 중복 한 장을 선정에서 제외하면 유효 양성 10개가 된다.
- `REJECTED (evaluation negative scene duplicates)`: 승인 음성 5장은 5초 안에 촬영된 같은 빈 장면이며 pairwise dHash 거리가 1–6이라 한 장면 cluster로 판단했다. 첫 `evaluation-final-v1` 초안은 삭제하지 않고 `evaluation-final-v1-rejected-negative-duplicates`로 이름을 바꾸고 `independent_evaluation_ready=false`로 정정했다. 중복 감사를 추가한 v2 준비는 positive 10·negative 1로 fail-closed했고 출력 디렉터리를 만들지 않았다.
- `NEXT (four distinct evaluation negatives)`: 약통을 화면 밖으로 치운 뒤 빈 장면과 다른 비대상 배치 4종(예: 펜, 휴대폰, 작은 상자, 케이블/테이프)을 한 장면씩 평가 음성으로 촬영·승인한다. 마커 0–3을 가리지 않고, 같은 배치 연속 촬영은 하지 않는다. 학습과 로봇 구동은 계속 `NOT_RUN`이다.
- `CONCURRENT_CHANGE (Astra V4L2 bridge)`: 20:31 KST 다른 Jetson TTY 세션이 `/etc/modprobe.d/astra-v4l2loopback.conf`, `/etc/modules-load.d/astra-v4l2loopback.conf`, `astra-v4l2-bridge.service`를 설치하고 `systemctl disable --now so101-camera-preview.service`를 실행했다. 이어 `/dev/video8` 대상 OpenNI→GStreamer bridge를 enable/start했다. 8010 중지는 camera server 오류가 아니라 이 외부 변경이며, 충돌을 피하려고 재활성화하지 않았다. bridge는 active, 8000만 listen 중이고 8010/8011은 현재 내려가 있다.

## GitHub

- 저장소: <https://github.com/gyeyeongjo-lgtm/so101-lelab-medicine-sorter>
- 공개 범위: private (`PASS`)
- 기본 브랜치/초기 커밋: `main` / `8dd6761`
- 작업 브랜치/진단 결과 커밋: `fix/usb-recording` / `c670c7a`
- 이슈: #1 포트 식별, #2 녹화 TX/RX, #3 회귀·데이터 검증, #4 후속 로드맵

## 2026-09-27 약국 대상 검출 범위 정정

- `USER_SCOPE_CORRECTION`: 실제 운용 가정은 약국 작업대이며 현재 1차 목표는 연구용 약통 모형의 존재와 위치 검출이다. 손·펜·휴대폰 등 임의 비대상 물체의 종류별 성능을 이번 단계의 완료 조건으로 요구하지 않는다.
- `PASS (negative visual recheck)`: `training-candidates-audit-v2` 음성 30장을 다시 육안 확인했다. 일부 frame에 손이나 다른 물체가 있지만 작업영역에 목표 약통 모형이 남은 음성은 발견하지 않았다. 따라서 이전 `REVIEW_REQUIRED (negative scope)`의 추가 hard-negative 요구는 위 사용자 범위에서 해제한다.
- `PASS (smoke evaluation set)`: 비파괴 `/home/jetson3/so101-medicine-bootstrap/evaluation-final-v2`를 positive 10·고유 empty negative 1로 준비했다. status는 `READY_FOR_OFFLINE_DETECTION_SMOKE_EVALUATION`, profile은 `pharmacy_target_presence_smoke`다.
- `LIMITATION`: 음성 장면이 1개이므로 robust false-positive rate 또는 일반 환경 성능을 주장할 수 없다. `independent_evaluation_ready=false`, `false_positive_rate_ready=false`, `robot_enabled=false`를 유지한다.
- `NEXT (offline only)`: 감사된 training positive 59·negative 30을 capture-time block 기준 train/validation으로 분리하고 위 10+1은 test 전용으로 유지하는 YOLO 패키지를 준비한다. 설치·학습·추론과 로봇 동작은 이 기록 시점에는 아직 `NOT_RUN`이다.

## 2026-09-28 YOLO11n 약통 검출 스모크

- `PASS (dataset packaging)`: `yolo-medicine-v1`을 train 71(positive 47/negative 24), validation 18(12/6), test 11(10/1)로 준비했다. validation은 30초 capture block 단위로 분리했고 세 split 간 exact image overlap은 0이다.
- `PASS (offline training)`: Mac 격리 환경의 PyTorch 2.14.0·Ultralytics 8.4.163, Apple M3 MPS에서 YOLO11n을 학습했다. 40 epoch 중 best는 epoch 30이고 validation precision 0.995, recall 1.000, mAP50 0.995, mAP50–95 0.766이다.
- `PASS (offline test smoke)`: 별도 test 11장에서 precision 0.995, recall 1.000, mAP50 0.995, mAP50–95 0.798을 확인했다. confidence 0.25에서 positive 10/10은 각각 1 detection, empty negative 1/1은 0 detection이었다. box IoU 최소 0.8392·평균 0.8937, 최소 confidence 0.8921이다.
- `PASS (visual prediction review)`: 두 test prediction contact sheet를 육안 확인했고 박스가 약통 모형에 위치하며 empty frame에는 박스가 없었다.
- `LIMITATION`: test negative가 고유 empty scene 1개뿐이므로 `PASS_OFFLINE_TARGET_PRESENCE_SMOKE`까지만 판정한다. robust false-positive rate·일반 환경 독립 성능은 `NOT_VERIFIED`이고 `robot_enabled=false`다.
- `NEXT`: best checkpoint를 Jetson 실행 형식으로 export한 뒤 저장 frame과 live preview에서 overlay를 확인한다. 검출을 로봇 명령으로 연결하는 단계는 아직 금지한다.
- `NOT_PUSHED`: 데이터셋·checkpoint는 Git 제외 경로에 있고 이번 변경도 commit/push하지 않았다.

## 2026-09-28 ONNX Jetson 배포·live preview 장애

- `PASS (ONNX export/deploy)`: best checkpoint를 ONNX opset 17로 export하고 Jetson 새 비 Git 모델 디렉터리에 배포했다. 모델 SHA-256은 Mac/Jetson 모두 `d2f8452e...c846`이다.
- `PASS (Jetson saved-frame inference)`: Jetson OpenCV 4.12.0 DNN에서 저장 test 11장을 실행해 positive 10/10 각각 1 detection, empty negative 1/1 detection 0을 Mac 결과와 동일하게 재현했다.
- `PASS (single live snapshot)`: `/dev/video8`의 640×480 snapshot에서 약통을 confidence 0.746739로 검출했고 bbox 위치를 육안 확인했다. 다른 흰 용기는 검출하지 않았다.
- `FAIL (continuous live preview)`: read-only port 8020 web smoke는 8 frame 뒤 `frame read failed`로 정지했다. bridge journal의 최초 오류는 13:38:40 GStreamer internal data stream error이며 이후 OpenNI USB control request 실패가 반복됐다.
- `SAFETY_STOP`: 임시 YOLO web process를 종료했고, 자동 재시작이 61회 반복된 `astra-v4l2-bridge.service`를 stop했다. unit은 enabled로 보존했으며 USB·전원·설정은 변경하지 않았다. 8020 listener는 없다.
- `PASS (control end state)`: LeLab teleoperation·recording·inference는 모두 inactive다.
- `BLOCKED_USER_ACTION`: 사용자가 천장 Astra USB를 한 번 분리·재연결한 뒤 알려줘야 한다. 그 후 bridge start→stable frame→read-only 8020 preview 순으로 재검증한다.

## 2026-09-28 Astra 재연결 후 live YOLO 직접 입력 우회

- `PASS (USB reconnect)`: 사용자가 Astra USB를 재연결한 뒤 `2bc5:0401` 장치가 새 bus device로 재인식됐다. LeLab health는 정상이고 teleoperation·recording·inference는 모두 inactive였다.
- `FAIL (bridge isolated)`: 카메라 consumer가 없는 상태에서 `astra-v4l2-bridge.service`를 재기동했지만 GStreamer `v4l2sink` frame 1부터 `No free buffer found` / `failed queueing buffer 0` / `Internal data stream error`로 실패했다. Astra RGB producer는 640×480 RGB888 3 frame(2,764,800 bytes)을 정상 연속 전달했고, `videotestsrc`도 동일 `v4l2sink` 오류를 재현해 원인을 `/dev/video8` v4l2loopback 출력 버퍼 구간으로 격리했다.
- `SAFETY_STOP`: 자동 재시작 횟수가 71까지 증가한 bridge를 다시 stop했다. `enabled`와 모듈·unit 설정은 바꾸지 않았다.
- `PASS (direct Astra live YOLO)`: `medicine_yolo_web.py`에 packed RGB888 subprocess 입력을 추가해 v4l2loopback을 건너뛰다. 로컬 회귀 테스트 6개와 Jetson syntax 검사를 통과했다.
- `PASS (LAN 8020 smoke)`: Jetson `http://192.168.50.20:8020/` 임시 read-only server가 Astra RGB를 직접 소유한다. sequence 39→200→582→950으로 계속 증가했고 frame age 0.091–0.166 s, inference 147.3–156.2 ms, 약통 1개 confidence 0.748–0.785를 표시했다. Mac LAN `/health`도 성공했고 `robot_enabled=false`다.
- `PENDING (human visual)`: 자동 브라우저는 사설 IP의 새 8020 URL 이동을 보안 정책으로 차단했다. 사용자가 해당 URL을 직접 열어 live box 위치를 한 번 확인해야 한다.
- `RESOURCE OWNERSHIP`: 현재 8020 임시 process가 Astra를 소유하므로 `so101-camera-preview.service` 8010과 bridge는 inactive다. 천장 사선 RealSense preview는 이 smoke 동안 일시 정지다. 로봇 직렬·토크·모터 명령은 실행하지 않았다.
- `NOT_PERSISTENT`: 8020은 systemd로 등록하지 않은 임시 process다. 육안 검수 후 천장 정면 YOLO·사선 preview를 한 페이지로 통합한 뒤 서비스화한다. Git commit/push는 `NOT_PUSHED`다.

## 2026-09-28 통합 프리뷰·작업대 dry-run 좌표

- `PASS (user visual)`: 사용자가 8020 live 화면의 약통 YOLO 박스를 육안 확인하고 `완료`로 통과시켰다.
- `PASS (integrated cameras)`: 같은 8020 페이지에 천장 정면 Astra YOLO와 천장 사선 RealSense D435 프리뷰를 통합했다. 브라우저에서 두 실제 영상과 health `ok=true`를 확인했다.
- `PASS (persistent service)`: `medicine-yolo-preview.service`를 설치해 enabled·active, `NRestarts=0`을 확인했다. 실패한 `astra-v4l2-bridge.service`는 unit을 삭제하지 않고 boot auto-start만 disabled했다. 기존 8010 `so101-camera-preview.service`도 disabled·inactive다.
- `PASS (ArUco table projection)`: 매 frame ID0–3 homography를 계산해 `table.ready=true`, 실측 ID0–6 모두 검출, reference RMS 약 `0.000007 mm`를 확인했다. 이 RMS는 네 기준점 homography 내부 재투영값이며 실제 로봇 절대좌표 정확도가 아니다.
- `PASS (pickup ROI dry-run)`: 현재 약통 2개 중 1개는 영상 중심의 평면 투영값 약 `(193.2, 248.3) mm`로 pickup ROI X 80–220/Y 200–300 mm 내부였고, 다른 1개는 약 `(250.4, 316.0) mm`로 ROI 밖이었다.
- `PASS (basket mapping)`: ID4=red 약 `(59.7,95.1) mm`, ID5=green 약 `(245.5,93.2) mm`, ID6=blue 약 `(152.6,95.8) mm`의 현재 table-plane 투영 좌표를 표시한다.
- `SAFETY`: 약통 좌표는 bbox 영상 중심을 테이블 평면에 투영한 높이 미보정 dry-run이다. `robot_enabled=false`, `robot_target_authorized=false`고 LeLab teleoperation·recording·inference는 모두 inactive다. 로봇 직렬·토크·모터 명령은 없었다.
- `DEPLOY HASH`: web script `ae7333e2...60cd`, systemd unit `9656d7a4...34c4`다. 설치 전 web·unit은 timestamp suffix backup으로 보존했다.
- `BLOCKED_APPROVAL (next phase)`: 다음 유효 단계는 그리퍼 link에서 실제 TCP offset을 확정하고 World 기준점 4–8개에 follower TCP를 teach해 `T_B_W`를 구하는 것이다. 실제 팔 구동이 필요하므로 현장 안전 확인과 새 명시 승인 전에는 시작하지 않는다. Git commit/push는 `NOT_PUSHED`다.

## 2026-09-28 4점 World teach 시작 결과

- `PASS`: 빈 작업대의 검은 X 4개를 천장 정면·사선 프리뷰에서 확인했고, ID0–3 homography로 World 좌표 P1 `[273.493,321.191,0]`, P2 `[54.233,314.222,0]`, P3 `[60.112,183.993,0]`, P4 `[273.586,185.970,0]` mm를 확정했다.
- `AUTHORIZED`: 사용자가 4점 저속 텔레옵 teach를 승인했고 시작 전 stable ID Leader→ACM1, Follower→ACM0와 세 제어 inactive를 확인했다.
- `FAIL`: 텔레옵 시작은 첫 회 ID4, 읽기 전용 3-round 정상 확인 후 단 1회 재시도에서 ID6 `Torque_Enable=1` status packet 누락으로 각각 실패했다. 추가 재시도는 중단했다.
- `PASS (safe end state)`: Follower ID1–6 torque는 모두 0, teleoperation·recording·inference inactive, 8020 두 preview와 table homography 정상이다.
- `PASS (read-only)`: Follower ID1–6 정지 시 전압은 모두 12.2 V, 온도는 34–39°C였다. 이 정적 snapshot은 정상이지만 쓰기 시 status-packet 누락은 아직 미해결이다.
- `BLOCKED_HARDWARE`: 4점 joint sample, TCP offset 검증, FK pair, `T_B_W` fit은 `NOT_RUN`이다. 쓰기 시에만 반복되는 follower bus status-packet 누락을 해결한 뒤 재개한다.
- `NOT_PUSHED`: 이 변경은 commit·push하지 않았다.

## 2026-09-28 닫힌 tip TCP 6점 준비

- `PASS`: 새 P5·P6를 내부에 엇갈려 배치한 현재 6개 X가 ID0–3과 함께 두 preview에서 모두 보인다.
- `PASS (coordinates)`: 현재 World mm는 P1 `[276.693,299.484,0]`, P2 `[57.275,297.925,0]`, P3 `[60.137,167.664,0]`, P4 `[273.536,164.708,0]`, P5 `[212.898,252.880,0]`, P6 `[115.771,210.949,0]`이다.
- `CORRECTION`: 현재 P1–P4는 이전 teach 때보다 World Y가 약 16–22 mm 변했으므로 이전 4/8개 joint sample을 현 layout fit에 재사용하지 않는다.
- `READY_FOR_TEACH`: 새 6점 config은 `robot_world_pairs.20260928.closed-tip.local.json`이다. 다음은 리더 명령으로 닫은 그리퍼 tip을 TCP로 한 P1–P6 WebSocket teach다. 로봇 이동은 계속 차단한다.
- `NOT_PUSHED`: 이 변경은 commit·push하지 않았다.

## 2026-09-28 고정 Jaw repeat 최종 판정

- `PASS`: P1–P4 repeat sample을 Jaw 0.038–0.044 rad로 수집했고 각 세션 후 텔레옵 종료, Follower torque 0, 세 제어 inactive, 8020 preview·homography 정상을 확인했다.
- `PASS (tooling)`: TCP+`T_B_W` 동시 fit에 pair-name 선택 기능을 추가해 Jaw 조건이 다른 sample을 혼합하지 않게 했고 테스트 4/4를 통과했다.
- `REJECTED`: fixed-Jaw repeat 4건 fit은 RMSE 5.780 mm, max 6.694 mm, condition 5887.5로 RMSE·observability 기준을 통과하지 못했다. 가까운 Jaw의 원본 P1 holdout도 9.03 mm 오차였다.
- `MOTION_BLOCKED`: 현 `T_B_W`·TCP 결과는 실제 이동·pick에 사용하지 않는다. 다음 필요 조치는 명령으로 닫은 그리퍼 단일 tip TCP와 6개 이상 분산 point 재-teach이다.
- `NOT_PUSHED`: 이 변경은 commit·push하지 않았다.

## 2026-09-28 4점 teach 수집·fit 판정

- `PASS`: 사용자가 LeLab UI에서 텔레옵을 활성화한 뒤 P1–P4 각 15개 관절 sample을 `/ws/joint-data` broadcast로만 수집했다. `/joint-positions`와 추가 serial reader는 사용하지 않았다.
- `PASS (safe end state)`: P4 수집 직후 텔레옵을 정상 종료했고 Follower ID1–6 torque 0, 세 제어 inactive, 8020 두 preview·homography 정상을 확인했다.
- `IMPLEMENTED`: known World point·FK link pose에서 gripper-link TCP offset과 `T_B_W`를 동시 추정하고 residual·observability로 fail-closed 판정하는 `fit_robot_world_tcp_transform.py`를 추가했고 단위 테스트 3/3을 통과했다.
- `REJECTED`: 현재 4점 fit은 RMSE 9.572 mm, max 12.073 mm, condition number 7031.4로 모든 허용 기준을 넘었다. TCP offset 추정치는 `[22.362,-13.767,-45.344]` mm이지만 실제 명령에 사용하지 않는다.
- `MOTION_BLOCKED`: `robot_world_transform.20260928.local.json`은 `robot_enabled=false`, `motion_authorized=false`다. 다음은 현재 P4와 같은 그리퍼 벌림을 유지한 P1·P2 repeat teach로 Jaw 차이·수동 재현성을 보강한 뒤 재계산한다.
- `NOT_PUSHED`: 이 변경은 commit·push하지 않았다.
