# 2026-10-01 P6 재측정 재개 사전 점검

## 의도와 승인 범위

- 전날 사용자는 P6 재측정 텔레옵을 승인하고 작업대 정리·팔로워 범위 이탈·즉시 중단 준비·시작 자세 정렬을 확인했다. 이후 같은 손가락에 표식을 다시 붙였다고 답했다.
- 이번 재개 요청에 따라 상태·장면을 새로 검사했다. 전날의 물리 배치와 안전 확인을 오늘의 현재 상태로 간주하지 않는다.

## 읽기 전용 검사와 웹 서비스 복구

- Jetson `192.168.50.20`은 ping과 SSH 22에 응답했다. LeLab 8000은 처음에 연결되지 않았다.
- `systemctl --user show lelab.service`에서 `ActiveState=inactive`, `MainPID=0`, `Result=success`, `ExecMainStatus=15`, `InactiveEnterTimestamp=2026-09-30 22:20:10 KST`를 확인했다. 종료 원인의 세부 사항은 `NOT_VERIFIED`다.
- canonical USB 링크는 Leader `5AE6085272`→ACM1, Follower `5AE6058306`→ACM0였다. 8002·8022 LeLab 서버는 떠 있었으나 두 서버의 teleoperation·recording·inference 모두 inactive였다.
- 기존 설정을 변경하지 않고 `systemctl --user start lelab.service`를 한 번 실행했다. 8000의 `ActiveState=active`, `MainPID=393471`, health 정상, teleoperation·recording·inference active=false를 확인했다. recording의 `current_phase=preparing`, `session_ended=false` 내부 정리 여부는 `NOT_VERIFIED`다. serial bus·토크·캘리브레이션·USB·전원은 건드리지 않았다.

## 카메라 확인과 중단 판정

- 손목 `/camera-preview/6` 새 프레임에는 그리퍼 안쪽 두 면이 보였다. 한 손가락에 붙였다는 표식과 실제 접촉할 단단한 플라스틱 끝 한 점은 영상에서 식별되지 않았다.
- 정면 Astra `/camera-preview/8` 새 프레임에는 약통 모형 3개와 바구니 3개가 다시 배치돼 P6 X가 가려져 있었다. 분홍색 조각은 작업대 왼쪽에 보였다. 이 조각이 손가락 표식에서 떨어진 것인지는 `NOT_VERIFIED`다.
- 따라서 물리 장면이 전날의 승인 조건과 다르다. `/move-arm`은 호출하지 않았고 P6 joint sample·fit은 `NOT_RUN`. 현재 거부된 robot-world 변환, `robot_enabled=false`, `motion_authorized=false`를 유지한다.
- 다음은 약통·바구니를 잠시 치워 P6과 ID0–3을 노출하고, 동일 손가락 표식이 실제로 붙어 있으며 단단한 플라스틱 접촉점은 노출됐는지 현장에서 확인하는 것이다. 이후 사람의 범위 이탈·즉시 중단 준비·리더/팔로워 시작 자세와 저속 조작 승인을 현재 시점에 다시 확인해야 한다.

## 기록 경계

- 원본 카메라 프레임, 원본 로그, 인증정보는 Git에 넣지 않는다.
- 첫 사전 점검 기록은 commit `afeb6fc`로 비공개 `origin/fix/usb-recording`에 push했다. 이 후속 P6 결과의 commit/push는 종료 시 별도로 검증한다.

## 사용자의 작업대 정리 후 재검사

- 사용자가 약통·바구니를 치웠다고 알렸다. 새 `/camera-preview/8` 프레임에서 ID0–3과 X 6개가 보이며 P6은 더 이상 바구니에 가리지 않는다.
- 왼쪽 작업대에 흰 컵과 분홍 조각이 남아 있다. 손가락 표식의 부착 상태와 노출 플라스틱 접촉점은 정면 영상으로 확정할 수 없다. 두 물체 제거와 동일 손가락·접촉점의 현장 확인을 요청했다.
- 8000 `/health` 정상, teleoperation·recording·inference active=false다. `/robots/so-101`의 leader ACM1, follower ACM0, config `so-101.json`, camera index 8/4/6이 오늘의 canonical USB 역할과 일치한다.
- 사람의 팔로워 이동 범위 이탈, 즉시 중단 준비, 리더/팔로워 시작 자세, 천천히 리더 조작 및 P6 1점 텔레옵 승인 여부를 현재 시점에 다시 질문했다. 답변 전 `/move-arm`, joint sample, fit은 `NOT_RUN`이고 거부된 transform·`robot_enabled=false`·`motion_authorized=false`를 유지한다.

## P6 1점 승인 텔레옵·안전 종료

- 사용자는 남은 흰 컵·분홍 조각을 치웠고 이전과 같은 손가락의 단단한 플라스틱 끝이 노출됐다고 확인했다. 현재 사람은 팔로워 이동 범위 밖에 있고 즉시 중단 준비, 리더/팔로워 시작 자세 정렬, 리더를 천천히 조작하는 P6 1점 텔레옵을 명시 승인했다.
- 시작 전 새 정면 프레임에서 ID0–3과 X 6개가 보이고 작업대의 컵·분홍 조각은 사라졌다. 8000 teleoperation·recording·inference active=false, 저장된 `so-101` leader ACM1/follower ACM0, config `so-101.json`을 확인했다. root 읽기 전용 `fuser /dev/ttyACM0 /dev/ttyACM1`은 점유 PID를 반환하지 않았다.
- `/move-arm` 1회가 HTTP 200 `Teleoperation started successfully`를 반환했다. 사용자가 표시 손가락의 플라스틱 끝으로 P6 X 중심에 가볍게 닿고 안정됐다고 보고했다. `/ws/joint-data`에서 15개 방송을 수집했고 모든 관절의 표준편차와 범위는 0 rad였다. 별도 serial reader, `/joint-positions`, 녹화, 추론을 실행하지 않았다.
- 수집 직후 `/stop-teleoperation` 1회가 HTTP 200 `Teleoperation stopped successfully`를 반환했다. 이후 8000 health 정상, teleoperation·recording·inference active=false. follower torque register는 직접 읽지 않아 `NOT_VERIFIED`다. 종료 뒤 정면 프레임에는 팔이 다시 위쪽에 있어 P6 *접촉 순간*의 영상 QA는 `NOT_VERIFIED`다.

## 오프라인 진단과 판정

- 원본 방송 15개는 Mac 임시 로컬 파일에, 기존 P1–P5와 새 P6 관절 평균을 묶은 임시 입력은 Git-ignore `configs/robot_world_pairs.20261001.p6-reteach.local.json`에 보존했다. 이전 P1–P5의 관절값·X World 좌표는 2026-09-30 수집본이므로 날짜가 섞인 진단일 뿐 동일 세션 6점 teach가 아니다. 과거 로컬 입력은 덮어쓰지 않았다.
- 기존 설치 URDF 사본과 보정 ArUco 중심 모델로 재적합한 6점 결과는 `REJECTED_NEEDS_MORE_OR_BETTER_TEACH_SAMPLES`: RMSE 3.988 mm, 최대 잔차 5.907 mm, 조건수 5555.7(허용 ≤1000), TCP offset norm 143.072 mm다. 위치 잔차 기준은 통과했지만 조건수 기준은 실패했다.
- P1–P5만으로 적합하면 훈련 RMSE 2.999 mm, 최대 3.893 mm, 조건수 15298.8로 이미 거부다. 여기서 제외한 새 P6의 독립 holdout 오차는 9.932 mm로 최대 허용 8 mm를 초과한다. 따라서 새 P6을 더해도 로봇 좌표 변환을 승인하지 않는다.
- 임시 결과는 Git-ignore `configs/aruco_reference_gap_diagnostic.20261001.p6-reteach.local.json`에 보존했고 source-pairs SHA-256은 `80245f6b97d793582702afbd15daa290884f94537a08fc4104d5869cd475a49c`이다. `robot_enabled=false`, `motion_authorized=false`; 실제 약통 이동은 `NOT_RUN`이다.
- 다음은 접촉 순간을 정면·사선에서 검증할 수 있는 수집 방식과 다양한 손목 자세·독립 holdout을 설계하는 것이다. 추가 모터 동작은 새 현장 준비·명시 승인 전까지 하지 않는다.
