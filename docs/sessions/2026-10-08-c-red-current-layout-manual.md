# 2026-10-08 현 고정 배치 C→빨강 ID4 수동 시연

## 이유와 현장 범위

- 10월 7일 성공한 C 수동 기록의 첫 장면과 10월 8일 새 배치 사진을 오프라인 대조했다. C 검출 상자 중심은 `(318.013,235.066)`→`(316.998,238.543)` px로 약 3.62 px 차이지만, 빨강 ID4 마커 중심은 약 9.467 px, 바구니 ID4–6 최대 13.531 px 이동했다. 이전 관절 궤적을 새 바구니 배치에 재생할 수 없다는 진단이다.
- 사용자는 C 단독 출발 배치·빈 빨강 바구니, 사람·도구 이탈, 즉시 중단 준비를 확인하고 **현 배치의 수동 1회**를 승인했다. 텔레옵은 사용자가 직접 켰고 리더·팔로워 시작 자세 및 초기 이상 움직임 없음을 보고했다. 에이전트는 모터·토크·USB·LeLab 제어 API를 호출하지 않았다.
- 시작 전 8000 실제 `/teleoperation-status`는 active=true, 기존 Mac 8030 정면·사선·손목 캐시는 모두 fresh/오류 null/`robot_control=false`였다. 관찰기 9개 단위 시험을 통과한 뒤 세 카메라와 `/ws/joint-data`를 읽기 전용으로 기록했다.

## 결과와 근거

- 사용자는 C→빨강 투입, 열린 그리퍼 퇴피, 간섭 없음, 텔레옵 직접 종료를 보고했다. 기록 첫 정면 장면에는 C가 출발 자리에, 마지막 정면 장면에는 C가 왼쪽 빨강 ID4 바구니 안에 있고 그리퍼는 떨어져 있다. 중간 정면·사선·손목 표본에는 바구니 입구의 C와 그리퍼가 보인다. 표본 영상만으로 전 구간 실제 최소 간격이나 무접촉을 독립 측정하지 않는다.
- 기존 LeLab 8000 `/teleoperation-status`는 종료 후 active=false이고 `/recording-status`는 `recording_active=false`다. 후자의 `current_phase=preparing`, `session_ended=false`는 녹화 세션 정리 증거로 간주하지 않는다.
- Git 제외 `.local/teleop-traces/20261008T054514_308947Z_6d3884df/`에 관절 1,198개(61.873 s), 정면·사선·손목 각 251장을 보존했다. `stop_reason=teleoperation_inactive`; 해시/인덱스·시각 순서 무결성 통과, 수신 최대 간격 170.401 ms, 역순 시각 0건이다. 0.01 rad 기준 잠정 활동 구간은 시작 후 43.311 s부터 마지막 18.551 s·관절 360개이며 각 시야의 해당 구간 표본은 74장이다. 카메라 시각은 Mac 수신시각이지 노출시각 동기가 아니다.
- 시험 시작·끝 장면의 작업대 마커 최대 변화 0.077 px, 바구니 마커 최대 0.044 px다. 색 몸체 후보는 크기 최대 5 px 변화로 `BODY_CANDIDATE_UNSTABLE`; 마커 안정이 입구 실제 여유나 충돌 안전을 보증하지 않는다.

## 자동화 게이트

- 설치 URDF 감사 결과 `URDF_LIMIT_MISMATCH`: Elbow 상한 초과 945/1,198개(최대 0.114689 rad), Wrist_Pitch 상한 초과 19개(최대 0.091872 rad). 기존 follower 캘리브레이션 **파일** 범위에는 다섯 arm 관절 모두 들어왔지만 Elbow/Wrist_Pitch 최소 파일 여유는 각 0.440°/0.352°뿐이고 1° 이내 표본은 각 856/12개다. 이는 실제 하드스톱·하중 여유·안전 경로 실측이 아니다.
- `camera_evidence_complete=false`, `training_ready=false`, `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`. 새 배치의 수동 성공을 자동 관절 재생·ArUco 좌표 투입 승인으로 승격하지 않는다. 로봇 이동 명령·서비스/USB/토크 변경 `NOT_RUN`; GitHub 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`. 사진·관절 원본은 커밋하지 않는다.
