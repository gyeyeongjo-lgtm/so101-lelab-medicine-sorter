# 2026-10-02 TCP 단일점 실험 사전 점검

- 사용자가 현장 안전을 보고하고 계속 진행을 요청했다. 최신 `docs/STATUS.md`, `docs/sessions/2026-10-01-teach-capture-web.md`, `docs/TEACH_CAPTURE_WEB.md`를 확인했다. 앞선 6점 적합은 조건수 4807.5와 P1 의사-holdout 17.675 mm 때문에 거부됐으며 자동 이동은 금지 상태다.
- Jetson `192.168.50.20`에 SSH로 접속했다. LeLab 8000의 기존 `lelab.service`는 inactive였고 8002·8022는 health 정상이며 teleoperation/recording/inference 모두 inactive였다. canonical serial symlink는 leader `5AE6085272`→ACM1, follower `5AE6058306`→ACM0이다. root `fuser -v /dev/ttyACM0 /dev/ttyACM1`은 점유 PID를 보고하지 않았다.
- 기존 8000 user service를 설정 변경 없이 한 번 시작했다. localhost 및 Mac에서 `/health` 정상, 8000의 teleoperation/recording/inference 모두 inactive를 확인했다. USB 재연결, 토크 변경, 모터 명령, 녹화·추론은 실행하지 않았다.
- Mac의 기존 8030 캡처 앱은 `127.0.0.1:8030`에서 계속 listen 중이었다. `/api/status`는 정면·사선·손목 프레임의 오류 null, `joint_age_ms=null`, `robot_control=false`를 보고했다. 브라우저에서 세 카메라 프리뷰를 확인하고 페이지를 후속 작업용으로 열어 두었다.
- 정면 영상에는 약통 3개와 바구니 3개가 X 접촉 영역에 있다. 따라서 다음 예정 실험인 단일 X(예: P5)의 손목 자세 다양화 접촉을 시작하지 않았다. 약통·바구니를 팔로워 작업 범위 밖으로 치우고 X·ID0–3 가시성과 손끝 표식, 사람의 범위 이탈·즉시 중단 준비, 시작 자세를 다시 확인한 뒤 **이번 텔레옵의 별도 명시 승인**이 필요하다. 지금 텔레옵·접촉 저장·TCP 추정·holdout은 `NOT_RUN`이며 `robot_enabled=false`, `motion_authorized=false`다.
