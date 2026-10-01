# 2026-10-01 접촉 증거 웹 캡처 구현·스모크

- 기존 8010 `camera_preview_server.py`는 Astra/RealSense 장치를 직접 열고 현재 bridge/LeLab 경로와 충돌할 수 있다. 이를 활성화하거나 수정하지 않았다. 대신 Mac loopback 전용 `scripts/teach_capture_web.py`를 추가했다.
- 새 앱은 기존 LeLab 8000 MJPEG 8/4와 관절 WebSocket만 구독한다. 로봇 제어 경로·serial 접근은 없고, 텔레옵 active 조회는 저장 게이트로만 사용한다. 15개 joint broadcast의 안정성, 정면·사선 프레임과 마지막 joint **수신 시각** 차이 ≤250 ms, 프레임·관절 신선도를 검사한다. 센서 노출 시각 동기화는 지원되지 않아 metadata에 근사임을 명시한다.
- 원본 JPEG·관절 방송은 Git-ignore `.local/teach-captures/`에만 저장한다. 현장 확인은 사용자 주장으로 표시하며 자료의 robot-world fit 사용과 실제 이동은 기본값 false다.
- 실카메라 첫 시험에서 정면은 정상, 사선은 503이었다. root `fuser /dev/video4`는 LeLab 8000 PID 393472가 소유했다고 보고했다. 공식 preview stop 1회 뒤에도 503이어서, 8000/8002/8022의 teleoperation·recording·inference inactive와 serial ACM0/ACM1 점유 PID 없음 확인 후 기존 LeLab 8000 user service를 한 번 재시작했다. MainPID 394934와 health 정상, 세 작업 inactive를 확인했다. 이후 사선 preview HTTP 200으로 2초간 862,128 byte가 전송됐다.
- Mac `127.0.0.1:8030` 실실행에서 정면·사선 프레임 나이는 약 68/67 ms였고 `/frame/ceiling.jpg`, `/frame/oblique.jpg` 모두 HTTP 200, 실제 640×480 JPEG였다. 브라우저에서 두 영상·지점 선택·접촉 확인·수신 상태 UI를 확인했다.
- 텔레옵 비활성 상태에서 `POST /api/capture`는 HTTP 400 `LeLab teleoperation is not active; capture refused`를 반환했고 `.local/teach-captures/`는 비어 있었다. 이 스모크에서 `/move-arm`, 모터, 토크, serial, USB, 녹화, 추론은 실행하지 않았다.
- 새 캡처 테스트 5개와 기존 읽기 전용 관절 모니터 테스트 3개, 총 8개 통과. 실제 텔레옵 중 두 영상과 관절 방송의 짝 저장은 `NOT_RUN`; 실제 접촉 QA·새 World/TCP 적합도 `NOT_RUN`이다. 기존 변환은 계속 거부하며 `robot_enabled=false`, `motion_authorized=false`다.
- 코드·테스트·문서 commit `1e5cb91`을 비공개 `origin/fix/usb-recording`에 push했다. 작업 중 원본 영상·관절 방송은 Git에 넣지 않았다.

## P1·P6 사용자 텔레옵 중 접촉 저장

- 사용자가 LeLab 텔레옵을 직접 시작했다. Mac 8030 캡처 앱의 `/api/status`는 정면·사선·관절 수신 오류가 없었고 LeLab `/teleoperation-status`는 active=true였다. Mac에서 SSH 공개키 인증은 실패했으므로 이번 세션에서는 Jetson canonical USB/serial 점유를 직접 재확인하지 못했다. 사용자가 이미 시작한 텔레옵에 대해 Mac은 `/move-arm` 또는 `/stop-teleoperation`을 호출하지 않았다.
- 사용자가 표시한 플라스틱 끝의 P1 접촉·안정을 확인한 직후 `20261001T093659_729629Z_6e598848`로 저장했다. JPEG 2장·관절 방송 15개, 정면/사선의 마지막 관절 방송과 수신 시각 차이 6.3/7.6 ms, 최대 관절 표준편차 0 rad다.
- 사용자가 같은 끝의 P6 접촉·안정을 확인한 직후 `20261001T094015_352394Z_957ff8ca`로 저장했다. JPEG 2장·관절 방송 15개, 수신 시각 차이 7.4/0.1 ms, 최대 관절 표준편차 0 rad다. JPEG 4장 모두 파일 SHA-256과 각 metadata 기록이 일치했다.
- 정면·사선 저장 영상에서 각 X 주변에 그리퍼 손끝은 보인다. 그러나 640×480 해상도와 손끝 가림 때문에 동일한 단일 플라스틱 끝의 정확한 접촉은 영상만으로 `NOT_VERIFIED`다. Mac 수신 시각은 카메라 센서 노출 동기화가 아니다. 원본 이미지·관절값은 Git-ignore `.local/teach-captures/`에만 유지한다.
- 사용자가 텔레옵 종료를 보고한 뒤 LeLab health 정상, teleoperation·recording·inference active=false를 각각 확인했다. recording 내부 `current_phase=preparing`, `session_ended=false`와 follower torque register는 `NOT_VERIFIED`다.
- 새 robot-world fit/holdout, 자동 이동, 약통 취급은 `NOT_RUN`이다. 두 metadata의 `use_for_robot_world_fit=false`, `robot_enabled=false`, `motion_authorized=false`를 유지한다. 기존 거부된 변환을 사용하지 않는다.

## 저장 프레임과 과거 X 배치의 오프라인 대조

- 로봇·카메라 장치를 열지 않고 P1·P6의 저장된 정면 JPEG에 `scripts/check_aruco_x_still.py`의 DICT_4X4_50 검출/검은 X 중심 추출법을 적용했다. 두 프레임에서 ID0–3이 모두 검출됐다. 과거 `20260930.single-fingertip` 기록의 픽셀 중심과 비교 가능한 비가림 X 8개는 P1 프레임의 P2/P3/P4/P6에서 각각 0.152/1.097/0.910/0.452 px, P6 프레임의 P1/P3/P4/P5에서 각각 0.402/0.872/0.807/0.087 px 이동했다. P1·P6 접촉 지점 자체는 그리퍼에 가려져 중심 재검출이 불가했다. P6 프레임의 P2도 연결 성분 판별 실패라 제외했다.
- 저장 프레임의 마커 중심과 `configs/astra_rgbd.example.json`의 **보정된** 기준 중심으로 과거 X 픽셀을 재투영했다. P1 프레임 기준 P1≈(341.342,376.867), P2≈(75.408,371.379), P6≈(148.068,263.419) mm이며 P1–P2≈265.991 mm, P1–P4≈167.832 mm다. 두 프레임 간 같은 방식의 P1/P6 좌표 차이는 0.4 mm 미만이다. 이는 단일 프레임 camera-plane 진단이며 손끝 실제 접촉·절대 정확도 검증은 아니다.
- 이전 pair 파일의 `world_mm`는 마커 중심 거리 정정 전 축척을 사용해 P1=(276.322,300.505), P6=(118.185,209.153) mm로 기록돼 있다. 픽셀 배치가 거의 같아도 숫자 좌표는 일치하지 않는다. 그 파일의 World 좌표를 이번 관절 캡처와 무보정 혼합하지 않는다. P2–P5의 이번 프로토콜 영상·관절 증거와 독립 holdout이 없어 새 적합은 `NOT_RUN`, 기존 거부 상태와 motion 차단을 유지한다.

## 손목 보조 카메라 추가 및 Mac 8030 재점검

- LeLab `/camera-preview/6` 기존 손목 프리뷰는 HTTP 200으로 약 2초 동안 891,756 byte를 전송했다. 640×480 저장 스모크 한 장에서 양쪽 그리퍼 손가락과 X가 같이 보인다. 접촉 순간은 아니므로 접촉 검증은 아니다.
- `scripts/teach_capture_web.py`에 손목 프리뷰를 보조 stream으로 추가했다. 정면·사선이 필수인 기존 선택 조건은 유지하며 손목 frame은 신선하고 마지막 관절 방송과 250 ms 이내일 때만 metadata/JPEG에 포함한다. 없거나 stale이면 `optional_camera_omitted=["wrist"]`로 표기한다. 로봇 제어 경로는 추가하지 않았다. 관련 단위 테스트 7개 통과.
- 갱신 전 Mac 8030 PID의 정확한 명령을 확인하고 사용자 제어 작업 teleoperation/recording/inference inactive를 읽은 뒤, Mac 프로세스만 정상 종료했다. 첫 `.venv` 시작은 `websocket` 모듈 부재로 joint worker가 예외를 내고 서버만 떠서 즉시 종료했다. 이를 방지하도록 서버 바인딩 전 의존성 검사를 추가했다. 누락 환경 실행은 exit 2와 명확한 오류로 거부됐고, 기존에 정상인 system `python3` 환경으로 다시 시작했다.
- 최종 8030 상태에서 정면/사선/손목 프레임 나이는 약 33/11/25 ms, 각 오류 null, LeLab health 정상·teleoperation inactive였다. 마지막 재시작 직후 한 번은 사선·손목 503과 정면 stream closed가 보였으나 다음 조회에서 모두 회복됐다. LeLab 서비스·USB·모터·토크는 건드리지 않았다. 텔레옵 inactive에서 `/api/capture`는 HTTP 400으로 거부됐다. 세 카메라와 관절값의 **실제 텔레옵 중 동시 저장은 `NOT_RUN`**이다.
- 현재 정면 프레임에 X 6개, ID0–3, 빈 작업대가 보였다. 사용자에게 P2–P5 동일 방식 텔레옵을 직접 진행할지 물었고 사용자는 “지금은 진행하지 않겠습니다”라고 답했다. 이 승인 보류를 존중해 새 모터 동작·접촉 캡처는 `NOT_RUN`; 8030 읽기 전용 프리뷰만 유지한다.
