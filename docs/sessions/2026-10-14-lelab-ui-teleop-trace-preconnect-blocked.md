# LeLab UI 텔레옵 시작 오류 — stale empirical trace 설정 확인, 접촉 상태로 변경 보류

사용자는 LeLab에서 직접 텔레옵을 활성화하려 했고 화면 오류 `LELABTELEOP TRACE PRE CONNECT JSON`을 보고했다. 현장 그리퍼–테이블 접촉은 **아직 유지**된다. 이번 턴은 읽기 전용 진단만 수행했고 텔레옵·모터·Goal·Torque write, 서비스 설정 변경/재시작은 하지 않았다.

Jetson 8000 `lelab.service`의 실행 중 worker 환경에는 `LELAB_TELEOP_MODE=relative_start`, `LELAB_TELEOP_TRACE_KIND=empirical_relative_teaching`, `LELAB_TELEOP_TRACE_ROOT`와 `LELAB_TELEOP_TRACE_ONCE_TICKET` 경로가 있다. 그러나 `LELAB_TELEOP_TRACE_PRE_CONNECT_JSON`은 없고 one-shot ticket 파일도 존재하지 않는다. 설치 `teleoperate.py`는 UI `/move-arm` 처리에서 trace root가 있으면 empirical branch로 들어가 `os.environ["LELAB_TELEOP_TRACE_PRE_CONNECT_JSON"]`을 로봇 연결 **전**에 읽는다. 따라서 보고된 오류는 이 누락 설정과 일치한다. 이 경로는 연결/명령 이전에 fail-closed한다.

trace root만 제거해 일반 relative-start로 바꾸는 것은 현재 안전한 해결책이 아니다. 동일 설치 worker는 일반 시작에서 follower/leader bus connect 후 calibration write 및 `configure()`를 호출하고, 일반 relative-start 루프는 그리퍼를 포함한 6축 action을 보낸다. 그리퍼–테이블 접촉과 직전 contact-release 실패가 확인된 상태에서 이를 UI에 열면 예상치 못한 접촉력/그리퍼 이동 위험이 있다. 설정을 그대로 두고 LeLab UI 시작을 요청하지 않았다.

읽기 전용 API에서 teleoperation/recording/inference 모두 inactive였고 privileged leader `/dev/ttyACM0`·follower `/dev/ttyACM1` 포트는 무점유였다. `CONTACT_RELEASE_ATTEMPT1=FAIL`, `PHYSICAL_NON_CONTACT=NO`, 자동 재시도 `0`을 유지한다. 원인 확인은 **UI 텔레옵 사용 가능 판정이 아니다**. 다음 작업은 현장 접촉 해제 상태와 안전한 UI arm-only entrypoint를 별도로 확보한 뒤에만 수행한다. `MOTOR_COMMAND=0`, `SERVICE_CHANGE=0`, `NEXT_LIVE_COMMAND=NONE`. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
