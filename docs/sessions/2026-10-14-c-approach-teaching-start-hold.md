# 2026-10-14 C approach 전체 supervised teaching 시작 보류

사용자는 canonical start pose부터 C pre-approach와 C approach까지 천천히 leader로 조작하고 follower trajectory를 전부 기록하길 요청했다. 그리퍼를 닫지 않고, 최종 `C APPROACH EMPIRICAL ALIGNED`까지 유지한 다음 teleop 종료·Present 3회 측정·approach pose 저장을 원한다. 이어 사용자는 LeLab 텔레옵을 이미 켰으며 recorder를 시작하면 움직이겠다고 알렸다.

읽기 전용 로컬 확인: 현재 `scripts/relative_start_teleop.py`의 `relative_target`은 `ACTION_KEYS` 전체(그리퍼 포함)에 leader delta를 적용한다. `scripts/teleop_cycle_trace.py`의 `CycleTrace`는 생성 시 trace 파일과 one-shot ticket을 처리한다. 2026-10-14 배치 기록에서 trace root/ticket은 무장되지 않았고, 이전 teaching 이동 trajectory도 recorder 미무장으로 `NOT_RECORDED`였다. 현재 live 세션이 실제 trace-enabled인지는 직접 확인하지 못했다. 단일 owner, 3초 startup stillness, physical clearance 역시 이번 세션에서 확인되지 않았다.

기록된 canonical runtime start `PICK_READY`와 마지막 post-stop follower 자세는 서로 다르다. 마지막 값은 현재 live feedback이 아니다. 직전 gripper-only 닫기에서 encoder raw `918→747`은 확인됐으나 사용자가 실제 손가락은 움직이지 않았다고 보고해 physical aperture는 `UNKNOWN`이다. 따라서 현재 세션에 별도 recorder를 붙이거나 이를 전체 start-to-approach trace로 분류하지 않는다. 사용자에게 리더를 멈추고 기존 텔레옵을 정상 종료하도록 요청했다. 현장 C/finger/link clearance 확인 전 추가 motion도 없다.

이번 확인의 motor command `0`, Goal write `0`, Torque write `0`, service/USB/port 조작 `0`. `SUPERVISED_TEACHING=HOLD`, `TRACE=NOT_RECORDED`, `C_APPROACH_EMPIRICAL=NOT_RECORDED`, `GRASP=NOT_RUN`, `LIFT=NOT_RUN`. 새 세션 실행 전에는 fresh 포트·owner·시작 자세, gripper Goal 차단, trace one-shot 무장, 3초 stillness 및 사용자 현장 비접촉 확인이 필요하다. 작업 변경은 `NOT_COMMITTED/NOT_PUSHED`; GitHub 이슈 갱신 `NOT_RUN`(대상 미지정). 기존 사용자 소유 ArUco SVG/PDF 삭제 상태는 건드리지 않았다.
