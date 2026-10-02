# 2026-10-02 고정 슬롯 waypoint 증거 수집 설계

- 사진 3장 검토에서 병렬 그리퍼의 두 손가락이 움직이고 안전한 하우징 접촉점은 확인되지 않았다. P5 반복 접촉을 중단하고, 고정 슬롯 1곳→빨강 바구니 ID4 한 경로의 별도 teach 후보를 준비했다. 기존 TCP/World→Base `REJECTED`를 승인으로 바꾸지 않았다.
- `scripts/teach_capture_web.py`에 별도 `/api/waypoint-capture`와 `.local/fixed-slot-waypoints/` 저장 경로를 추가했다. 4개 높은 경유 자세 라벨은 위치·높이 보증이 아니라 사용자 검수 대상이다. 현장 장면·완전 정지 확인과 LeLab 텔레옵 active, 15개 안정 관절 방송, 정면·사선 신선 영상을 모두 확인한 뒤에만 저장한다. 원본과 차단 플래그를 별도 metadata에 보존한다. P1–P6 접촉 API는 기본 거부, 웹 버튼은 비활성이다. LeLab 제어 경로는 추가하지 않았다.
- 첫 단위 테스트는 sandbox가 loopback bind를 거부해 기존 HTTP 및 새 HTTP 테스트 두 개에서 `PermissionError`가 났다. 네트워크 권한이 허용된 환경에서 동일 10개 테스트를 재실행해 모두 통과했다. 이후 접촉 캡처 기본 차단 테스트를 추가했고 최종 웹 11개+기존 TCP/FK 9개, 총 20개가 통과했다.
- Mac 8030 기존 PID 44544의 명령·작업 디렉터리를 확인하고, Jetson 8000의 teleoperation/recording/inference 모두 inactive를 읽은 뒤 해당 Mac 프로세스만 SIGTERM 종료했다. 같은 Python/경로/loopback 포트에서 새 서버 PID 50106을 실행했다. `/api/status`에서 세 카메라 오류 null, 관절 방송은 텔레옵 inactive라 null이었다. HTTP 페이지에 waypoint 섹션과 접촉 캡처 중지 버튼이 표시됨을 확인했다. LeLab 세 작업은 갱신 후에도 inactive다. recording의 내부 `preparing`/`session_ended=false`는 해결·변경하지 않았다. Jetson 서비스·USB·토크·모터는 건드리지 않았다.
- 실제 waypoint 텔레옵·저장·재생·약통 이동은 `NOT_RUN`; `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`다. 자세한 현장 게이트는 `docs/FIXED_SLOT_WAYPOINTS.md`에 있다.
