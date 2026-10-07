# 2026-10-07 수동 시연 활동 구간 감사

사용자가 직접 완료한 큰 약통 A→파란 ID6 바구니 수동 시연의 Git 제외 원본 `.local/teleop-traces/20261007T050941_395283Z_d2c1f385/`을 **읽기만** 했다. 로봇·토크·USB·LeLab 서비스와 원본 파일은 변경하지 않았다. 이번 분석은 자동 집기·투입 시험이 아니다.

## 방법과 결과

- `scripts/summarize_teleop_activity.py`는 기존 `audit_teleop_trace.py`를 먼저 호출해 관절·JPEG·index의 SHA-256, 개수, 설치 URDF 범위와 타임스탬프를 확인한다. 검증 실패 시 활동 요약을 내지 않는다.
- 첫 관절 자세의 여섯 관절 중 하나라도 0.01 rad를 **초과**한 최초 sample부터 파일 끝까지를 잠정 활동 구간으로 정의한다. 이 임계값은 움직임 탐색용이며 집기 시작·완료 시각의 근거가 아니다.
- 원본 1,685 sample·87.103초 중 최초 이탈은 index 1216, 시작 후 62.925초. 이후 파일 끝까지 469 sample·24.181초다.
- 잠정 구간에 들어오는 Mac 수신시각 기준 정면·사선 프레임은 각각 99장이다. 최초 관절 이탈 후 첫 프레임까지 0.323/0.332초, 마지막 프레임부터 관절 기록 끝까지 0.258/0.263초. 최대 연속 프레임 간격은 0.498/0.501초, 중앙값은 두 채널 모두 0.202초다.
- 원본 감사의 `URDF_LIMIT_MISMATCH`는 그대로이며 `camera_evidence_complete=false`다. 카메라 프레임은 센서 노출시각으로 관절과 동기화되지 않았다. 실제 집기·놓기 단계 구분, 프레임별 행동 정답, 반복 성공률, 그리퍼와 물체의 연속 간섭 판정은 `NOT_VERIFIED`다.

## 판정·다음 단계

이 원본은 수동 성공의 관찰 근거로만 유지한다. 학습용 정식 에피소드나 자동 관절 재생 경로로 사용하지 않는다(`training_ready=false`, `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`). 후속 수집은 실제 설치 LeLab에서 지원하는 녹화·저장·재로딩 경로를 별도로 검증해, 노출시각/관절 동기·프레임 손실·성공 라벨을 확인해야 한다. 이 검증이나 새 로봇 동작은 이번 작업에서 `NOT_RUN`이다. A/B/C 자동 분류, World→Base/TCP 등록, Elbow URDF 불일치, 연속 경로 여유는 독립 미해결 항목이다.

신규 단위 테스트 3개, 기존 `audit_teleop_trace` 테스트 6개 `PASS`. 전체 테스트 묶음은 첫 Mac Python에 OpenCV가 없고 `.venv` Python에는 `websocket-client`가 없으며, 양쪽 모두 현재 sandbox의 loopback bind 제한으로 `teach_capture_web` HTTP 테스트 네 건이 오류라서 통과 판정을 내리지 않는다. 이는 새 요약기 실패가 아니라 시험 환경 제한이고, 전체 회귀 시험은 `NOT_VERIFIED`다.

읽기 전용 live 확인에서는 Jetson 8000 health `ok`, teleoperation/recording/inference 모두 active=false였다. 녹화 내부 `current_phase=preparing`, `session_ended=false`이므로 세션 종료 완결성은 주장하지 않는다. 이번 작업은 원격 서비스·제어 endpoint에 쓰기 요청을 보내지 않았다. 원본 로컬 자료와 비밀번호·토큰은 커밋 대상에서 제외한다.

분석 코드·테스트·상태·세션 기록은 로컬 commit `c3350e5`로 남기고 비공개 `origin/fix/usb-recording`에 push했다. GitHub CLI는 로그인 상태가 아니라 이슈 API 갱신은 `NOT_RUN`; Git push는 macOS Git 자격 증명 경로에서 별도로 성공했다.
