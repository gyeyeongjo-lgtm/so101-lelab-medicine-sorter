# 2026-10-06 텔레옵 관찰기의 8030 캐시 카메라 재사용

## 목표와 안전 범위

2026-10-05의 5초 관찰은 관절 98개·정면 21장·사선 0장으로 부분 자료였다. 기존 관찰기가 텔레옵 중 LeLab `/camera-preview/4`를 새로 열어 사선 503을 유발하거나 악화시킬 수 있었다. 카메라 장치·LeLab 프리뷰 소유권을 더 늘리지 않도록, Mac 8030이 이미 받은 JPEG만 읽는 경로로 변경했다. 새 텔레옵·녹화·추론·모터·토크·USB·Jetson 서비스 변경은 `NOT_RUN`이다.

## 구현

- Mac 8030 `/frame/<name>.jpg`에 원래 Mac 수신시각 `X-Frame-Received-Unix-Ns` 헤더를 추가했다. 기존 JPEG 본문과 `Cache-Control: no-store`는 유지한다.
- `observe_teleop_trace.py --camera-evidence`는 loopback 8030의 `/api/status`에서 정면·사선 프레임 신선도와 `robot_control=false`를 확인한 뒤, 8030 캐시 JPEG를 약 5 Hz로 읽는다. 직접 LeLab MJPEG를 새로 열지 않는다. 원래 수신시각으로 중복 프레임을 제거하고 JPEG·index에 SHA-256을 기록한다. 8030이 없거나 낡은 영상이면 기록 폴더 생성 전에 거부한다.
- 영상은 카메라 노출시각 동기 영상이나 연속 비디오가 아니다. 그래서 `camera_video_recorded=false`, `camera_evidence_complete=false`를 유지하고 실제 프레임이 있는 채널만 `camera_channels_observed`에 적는다. 추후 두 영상·관절값이 저장돼도 `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`다. 감사기의 해시 검사와 URDF 한계 거부는 유지한다.

## 검증과 최초 실패

- 관련 단위/HTTP·비전 테스트 34개 통과. 관찰기 소스에 LeLab 카메라 프리뷰 또는 제어 경로가 없는지 검사한다.
- LeLab teleoperation·recording·inference inactive를 읽기 전용 확인했다. Mac 8030의 실제 PID 80496이 `scripts/teach_capture_web.py`임을 확인해 이 프로세스만 SIGTERM 종료하고 새 코드로 재실행했다. 재시작 직후 첫 `/api/status`는 정면 `camera stream closed`, 사선·손목 HTTP 503이었다. 자동 재시도 후 세 카메라 모두 오류 null·프레임 신선도로 회복됐다. 이 일시 오류를 숨기지 않는다.
- 실제 8030 정면·사선 `/frame/*.jpg`가 HTTP 200과 `X-Frame-Received-Unix-Ns` 헤더를 반환했다. 새 관찰기의 loopback 8030 사전 점검도 `camera_source_ready`를 반환했다. 최종 상태에서 LeLab teleoperation inactive, 8030 정면/사선/손목 frame age 5.4/12.9/13.1 ms·오류 null, `robot_control=false`였다.
- 텔레옵 inactive 상태에서 새 CLI를 `--camera-evidence --max-seconds 1`로 호출하자 exit 2 `LeLab teleoperation is inactive; no trace created`로 거부됐고 전용 임시 output-root에는 파일·폴더가 전혀 생성되지 않았다. 이는 실패-폐쇄 확인이지 실제 촬영 검증이 아니다.
- 실제 사용자 텔레옵 중 두 채널 동시 기록과 영상·관절 경로 검수는 `NOT_RUN`. 정지 waypoint를 자동 재생하지 않는다.
