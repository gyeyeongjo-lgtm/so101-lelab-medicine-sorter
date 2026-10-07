# 2026-10-07 B 단독 상공 비접촉 텔레옵 관찰

## 범위와 현장 보고

- 사용자는 현장 안전을 확인하고 기존 LeLab 텔레옵을 직접 켰다. B 중간 약통 한 개를 가운데 슬롯에 남기고 리더·팔로워 시작 자세를 맞췄으며, 시작 시 이상 움직임이 없다고 확인했다.
- 이번 범위는 사용자가 직접 리더를 천천히 움직이는 **B 상공 비접촉 도달·퇴피**였다. 접촉·집기·투입·자동 재생은 포함하지 않았다.
- 사용자는 B 위에서 공기 간격을 두고 정지한 뒤 비접촉 퇴피했으며, 접촉·걸림·이상 움직임 없이 LeLab 텔레옵을 직접 종료했다고 보고했다. 이 현장 보고는 영상만으로 정량 간격을 검증했다는 뜻이 아니다.

## 읽기 전용 확인과 기록

- 시작 뒤 LeLab `teleoperation_active=true`, `recording_active=false`, `inference_active=false`를 API로 확인했다. Mac 8030의 정면·사선·손목 및 관절 수신은 신선하고 오류가 없으며 `robot_control=false`였다. Mac 8031은 신선한 정면 프레임에서 검출 상자 1개(`x≈365–396 px`, 가운데 B 슬롯), ID0–6 및 `robot_enabled=false`를 반환했다. 물체 신원 B는 사용자의 확인에 의존한다.
- 로봇을 제어하지 않는 기존 `observe_teleop_trace.py --camera-evidence --max-seconds 300`으로 Git 제외 `.local/teleop-traces/20261007T140832_015795Z_fda04185/`에 관절 방송 1,937개와 정면 JPEG 424장·사선 JPEG 425장을 보존했다. 관찰기는 텔레옵 비활성 확인으로 종료됐고, 300초 제한에 걸리지 않았다.
- 무결성 감사에서 관절·카메라 해시, 시간 순서 및 영상 인덱스가 일치했다. 관절 수신 구간은 101.325초, 최대 수신 공백 221.298 ms, 원본 source 시각 중복/역순 0건이다. 마지막 동일 관절 방송 136개는 7.028초간 이어졌다. 이는 물리적 무동작이나 충돌 여유의 증명이 아니다.
- 저장된 정면·사선 표본에는 B 위의 그리퍼와, 이후 약통과 떨어져 위에 있는 그리퍼가 보인다. 카메라 프레임은 Mac 수신시각 기반 샘플이며 노출시각 동기 연속 영상이 아니므로 전체 퇴피 경로의 실제 간격·무접촉을 독립적으로 확정하지 않는다.
- 사용자 종료 뒤 LeLab API에서 `teleoperation_active=false`, 녹화·추론도 inactive임을 재확인했다. 녹화 내부 `current_phase=preparing`, `session_ended=false`는 그대로여서 세션 정리 완료로 해석하지 않는다.

## 제한 및 후속

- 설치 URDF SHA `443d38d7...f67236`와의 감사 결과는 `URDF_LIMIT_MISMATCH`: Elbow 상한 +1.5708 rad 초과 1,020/1,937개, 최대 초과 0.036437 rad. 다른 관절 초과 0건. 이는 실제 하드스톱 위반의 증거가 아니나 자동 재생 거부 조건이다.
- `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`, `training_ready=false`를 유지한다. B 접촉·집기·바구니 투입, World→Base/TCP 검증, 연속 경로 안전 검증은 `NOT_RUN/NOT_VERIFIED`다.
- 현재 canonical USB 식별값은 SSH 키 인증 거부로 `NOT_VERIFIED`다. 과거 확인한 follower/leader 매핑을 이번 시험의 현재 매핑으로 단정하지 않는다. SSH 시도는 읽기 전용이었고 비밀번호를 저장·전송하지 않았다.
- 원본 JPEG·관절값·자격증명은 Git에 포함하지 않는다. 기존 LeLab 설정·USB·토크·모터 API는 에이전트가 변경하지 않았다.
- 이 문서와 상태 변경은 로컬 Git에만 커밋했다. 기존 원격 브랜치 push는 외부 전송 심사에서 거부돼 `NOT_PUSHED`이며, 우회하지 않았다. 관련 GitHub 이슈 갱신은 `NOT_RUN`이다.
