# 2026-10-01 접촉 증거 웹 캡처 구현·스모크

- 기존 8010 `camera_preview_server.py`는 Astra/RealSense 장치를 직접 열고 현재 bridge/LeLab 경로와 충돌할 수 있다. 이를 활성화하거나 수정하지 않았다. 대신 Mac loopback 전용 `scripts/teach_capture_web.py`를 추가했다.
- 새 앱은 기존 LeLab 8000 MJPEG 8/4와 관절 WebSocket만 구독한다. 로봇 제어 경로·serial 접근은 없고, 텔레옵 active 조회는 저장 게이트로만 사용한다. 15개 joint broadcast의 안정성, 정면·사선 프레임과 마지막 joint **수신 시각** 차이 ≤250 ms, 프레임·관절 신선도를 검사한다. 센서 노출 시각 동기화는 지원되지 않아 metadata에 근사임을 명시한다.
- 원본 JPEG·관절 방송은 Git-ignore `.local/teach-captures/`에만 저장한다. 현장 확인은 사용자 주장으로 표시하며 자료의 robot-world fit 사용과 실제 이동은 기본값 false다.
- 실카메라 첫 시험에서 정면은 정상, 사선은 503이었다. root `fuser /dev/video4`는 LeLab 8000 PID 393472가 소유했다고 보고했다. 공식 preview stop 1회 뒤에도 503이어서, 8000/8002/8022의 teleoperation·recording·inference inactive와 serial ACM0/ACM1 점유 PID 없음 확인 후 기존 LeLab 8000 user service를 한 번 재시작했다. MainPID 394934와 health 정상, 세 작업 inactive를 확인했다. 이후 사선 preview HTTP 200으로 2초간 862,128 byte가 전송됐다.
- Mac `127.0.0.1:8030` 실실행에서 정면·사선 프레임 나이는 약 68/67 ms였고 `/frame/ceiling.jpg`, `/frame/oblique.jpg` 모두 HTTP 200, 실제 640×480 JPEG였다. 브라우저에서 두 영상·지점 선택·접촉 확인·수신 상태 UI를 확인했다.
- 텔레옵 비활성 상태에서 `POST /api/capture`는 HTTP 400 `LeLab teleoperation is not active; capture refused`를 반환했고 `.local/teach-captures/`는 비어 있었다. 이 스모크에서 `/move-arm`, 모터, 토크, serial, USB, 녹화, 추론은 실행하지 않았다.
- 새 캡처 테스트 5개와 기존 읽기 전용 관절 모니터 테스트 3개, 총 8개 통과. 실제 텔레옵 중 두 영상과 관절 방송의 짝 저장은 `NOT_RUN`; 실제 접촉 QA·새 World/TCP 적합도 `NOT_RUN`이다. 기존 변환은 계속 거부하며 `robot_enabled=false`, `motion_authorized=false`다.
- 코드·테스트·문서 commit `1e5cb91`을 비공개 `origin/fix/usb-recording`에 push했다. 작업 중 원본 영상·관절 방송은 Git에 넣지 않았다.
