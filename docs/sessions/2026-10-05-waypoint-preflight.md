# 2026-10-05 고정 슬롯 waypoint 재개 사전 점검

- 사용자가 다음 절차를 물어 `docs/STATUS.md`, 최신 2026-10-02 세션, `docs/FIXED_SLOT_WAYPOINTS.md` 및 Git 상태를 확인했다. 이전 M4b 구현은 정지 waypoint 증거 저장 전용이며 실제 텔레옵·캡처·재생은 아직 `NOT_RUN`이다.
- Mac `127.0.0.1:8030/api/status`는 HTTP 응답한다. 그러나 정면·사선·손목 `camera_age_ms`가 약 64,419,750 ms로 오래됐고 `joint_age_ms=null`, 관절 수신 오류는 connection refused였다. 카메라 오류 필드가 null이어도 live frame으로 해석하지 않는다.
- Jetson `192.168.50.20` ping 2/2, SSH TCP/22 접근은 통과했다. LeLab 8000 `/health`, `/teleoperation-status`, `/recording-status`, `/inference-status`는 모두 연결 거부됐다. 읽기 전용 SSH에서 사용자 서비스 `lelab.service`는 `ActiveState=inactive`, `SubState=dead`, `MainPID=0`, `Result=success`였다. 키 인증은 실패했고 기존 허가된 계정의 대화형 인증으로 상태만 읽었다. 암호·원본 로그는 파일에 기록하지 않았다.
- 서비스가 의도적으로 정지된 것인지 확인 전 임의로 시작하지 않았다. 서비스·카메라·로봇 설정 변경, 텔레옵, waypoint 저장, 모터·토크·USB 동작은 모두 `NOT_RUN`이다. 다음은 사용자에게 LeLab 서비스 시작 의사와 현장 안전 상태를 확인한 뒤, 서비스만 시작해 health/세 작업 inactive 및 카메라 신선도를 검증하는 것이다. 실제 텔레옵은 별도의 안전 확인·명시 승인 전까지 금지한다.

## 사용자 승인 후 서비스·프리뷰 복구

- 사용자가 “LeLab 서비스 시작 승인, 현장 안전 확인”이라고 명시했다. SSH에서 `lelab.service`가 inactive/dead/Result=success이고 ExecStart가 기존 `/home/jetson3/.local/share/uv/tools/lelab/bin/python -m uvicorn lelab.server:app --host 0.0.0.0 --port 8000`임을 재확인했다. `systemctl --user start lelab.service`를 한 번 실행하고 active/running/MainPID 존재를 확인했다. 서비스 설정·USB·토크·모터는 변경하지 않았다.
- Mac에서 8000 `/health`는 ok, `/teleoperation-status`, `/recording-status`, `/inference-status`의 active 값은 모두 false였다. 녹화 내부 `current_phase=preparing`, `session_ended=false`는 기존처럼 남아 있어 정리 완료라고 주장하지 않는다. LeLab 정면 `/camera-preview/8`, 사선 `/4`, 손목 `/6`은 각각 HTTP 200 MJPEG 스트림과 실제 바이트를 전송했다. 3초 수신 제한에서 curl 종료값 28은 스트림이 계속 열려 있어 발생한 예상 timeout이며 연결 실패가 아니다.
- Mac 8030은 HTTP는 살아 있었으나 오래된 frame age 약 64.9 million ms가 계속 증가했다. 정확한 PID 50106의 명령·작업 디렉터리가 프로젝트의 read-only 캡처 서버임을 확인하고, 세 제어 작업 inactive 상태에서 해당 PID만 SIGTERM 정상 종료한 뒤 동일 인자로 loopback 8030을 다시 시작했다. 새 PID 66196, 정면/사선/손목 frame age 각각 약 13.7/26.6/22.3 ms, 오류 null, 브라우저 UI에서 새 waypoint 섹션과 갱신되는 상태를 확인했다. 관절값 null은 텔레옵을 시작하지 않았기 때문이다.
- SSH 세션은 종료했다. 텔레옵 시작·waypoint 캡처·자동 재생·약통 이동은 `NOT_RUN`이다. 새 모션 승인 전까지 `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`를 유지한다.
