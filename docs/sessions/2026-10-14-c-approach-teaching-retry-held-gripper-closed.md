# C approach teaching retry — gripper opening 미충족, 시작 전 HOLD

사용자가 `RUN SUPERVISED C APPROACH TEACHING RETRY`를 승인하고 현장 팔·리더 정지, 링크/C/테이블 비접촉, 주변 clear, 시작 3초 정지 준비를 확인했다. fresh snapshot과 새 one-shot ticket을 준비하기 전에 사용자가 **그리퍼는 벌어져 있지 않다**고 정정했다. 최종 C가 두 finger 사이에 있어야 하고 이번 세션에서 그리퍼 opening을 유지해야 하므로, 물리적 전제조건이 깨졌다. 현장 확인을 우선하여 retry를 시작하지 않았다.

Jetson에서는 SSH 로그인과 LeLab `teleoperation_active=false`, `recording_active=false`, `inference_active=false` 조회만 했다. follower/leader serial open `0`; fresh follower snapshot `NOT_RUN`; 새 ticket 생성 `0`; 서비스 설정·재시작 `0`; 실제 teleop session `0`; motor/Goal/Torque write `0`. 기존 소진 ticket과 pre-connect 미설정 상태를 그대로 두었다. `PRE_ARM_SETTLE` 실제 연결 검증, trajectory, empirical endpoint 기록은 모두 `NOT_RUN`. `TEACHING_ATTEMPT2=NOT_STARTED/HOLD`; GRASP/LIFT `NOT_RUN`. 자동 재시도하지 않는다.

재개 전에는 사용자가 손가락 opening sweep과 C/테이블 비접촉을 확인하고, 별도 gripper-only opening 목표·실행을 승인하거나 현재 실제 벌어짐으로 C가 안전하게 들어간다고 현장에서 재확인해야 한다. 과거 encoder readback과 실제 손가락 움직임이 불일치했으므로 register 퍼센트만으로 opening을 인정하지 않는다. 새 승인 없이 teaching ticket을 무장하지 않는다.

원본 로그·비밀번호·키는 저장/커밋하지 않았다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정).
