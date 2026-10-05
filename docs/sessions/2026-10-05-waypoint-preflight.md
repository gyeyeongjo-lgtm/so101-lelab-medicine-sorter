# 2026-10-05 고정 슬롯 waypoint 재개 사전 점검

- 사용자가 다음 절차를 물어 `docs/STATUS.md`, 최신 2026-10-02 세션, `docs/FIXED_SLOT_WAYPOINTS.md` 및 Git 상태를 확인했다. 이전 M4b 구현은 정지 waypoint 증거 저장 전용이며 실제 텔레옵·캡처·재생은 아직 `NOT_RUN`이다.
- Mac `127.0.0.1:8030/api/status`는 HTTP 응답한다. 그러나 정면·사선·손목 `camera_age_ms`가 약 64,419,750 ms로 오래됐고 `joint_age_ms=null`, 관절 수신 오류는 connection refused였다. 카메라 오류 필드가 null이어도 live frame으로 해석하지 않는다.
- Jetson `192.168.50.20` ping 2/2, SSH TCP/22 접근은 통과했다. LeLab 8000 `/health`, `/teleoperation-status`, `/recording-status`, `/inference-status`는 모두 연결 거부됐다. 읽기 전용 SSH에서 사용자 서비스 `lelab.service`는 `ActiveState=inactive`, `SubState=dead`, `MainPID=0`, `Result=success`였다. 키 인증은 실패했고 기존 허가된 계정의 대화형 인증으로 상태만 읽었다. 암호·원본 로그는 파일에 기록하지 않았다.
- 서비스가 의도적으로 정지된 것인지 확인 전 임의로 시작하지 않았다. 서비스·카메라·로봇 설정 변경, 텔레옵, waypoint 저장, 모터·토크·USB 동작은 모두 `NOT_RUN`이다. 다음은 사용자에게 LeLab 서비스 시작 의사와 현장 안전 상태를 확인한 뒤, 서비스만 시작해 health/세 작업 inactive 및 카메라 신선도를 검증하는 것이다. 실제 텔레옵은 별도의 안전 확인·명시 승인 전까지 금지한다.
