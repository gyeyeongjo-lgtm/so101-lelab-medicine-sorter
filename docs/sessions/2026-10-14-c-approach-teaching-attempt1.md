# 2026-10-14 CURRENT→C APPROACH supervised teaching 시도 1 — startup gate FAIL

사용자 승인 `RUN CURRENT TO C APPROACH TEACHING`. 현장에서 리더/follower 정지, 손가락·전체 링크와 C/테이블 비접촉, 주변 clear, 현재 물리 opening 충분함을 확인했다. 기록 범위는 저장 `PICK_READY`가 아닌 **fresh CURRENT→C APPROACH**만이다. 그리퍼를 닫지 않고 GRASP/LIFT를 하지 않는 조건을 유지했다.

실행 전 Jetson 실제 8000 user `lelab.service` active, teleoperation/recording/inference inactive, canonical leader `/dev/ttyACM0=5AE6085272`, follower `/dev/ttyACM1=5AE6058306`, privileged `fuser` rc `1` 무점유. 쓰기 API를 막은 별도 follower 3회 read-only 값은 arm `[-6.285714,-67.384615,+82.329670,+28.439560,-22.109890]°`, 그리퍼 encoder `5.018360%`, Moving 전 축 `0`, Torque 전 축 `1`, Tmax `38°C`, Elbow Goal−Present `−0.527473°`로 동일했다. 포트 해제 확인.

one-shot trace 폴더 `/home/jetson3/so101-c-approach-teaching-20261014-EhhIBa/`와 ticket을 만들고 user service manager에 `relative_start`/`empirical_relative_teaching`/검증된 URDF·GRASP TCP/trace root/ticket 환경을 설정했다. 서비스 재시작 뒤 실제 8000 프로세스의 환경값·ticket 존재, 제어 inactive, 포트 무점유를 확인했다. UI `Teleoperation` 버튼으로 이 승인 범위의 supervised session을 1회 시작했다.

LeLab은 시작 성공 알림을 띄웠으나 worker는 첫 trace cycle 전 `startup follower moving before teaching` 예외로 즉시 종료됐다. 서비스 로그에는 follower/leader connect, calibration write, configure 완료, worker 시작, gate 예외, 두 arm disconnect가 순서대로 남았다. trace ticket은 소비됐다. manifest는 `capture_kind=human_operated_relative_start_empirical_teaching`, `cycle_count=0`, `error_count=0`, `stop_reason=worker_error`, `data_complete=false`; cycles/events/errors 파일은 빈 상태다. 따라서 startup stillness `FAIL`, teaching/trajectory `NOT_RECORDED`, `C_APPROACH_EMPIRICAL=NOT_RECORDED`, GRASP/LIFT `NOT_RUN`. worker arm-action dispatch는 gate 뒤에 있으므로 trace cycle/지도 이동은 `0`; 다만 LeRobot 초기화가 calibration/config/torque를 썼으므로 전체 hardware write `0`이라고 보고하지 않는다. 원인 관절은 당시 Moving 값이 trace에 남지 않아 확정하지 않는다.

API `teleoperation_active=false`, privileged 두 포트 무점유. 사용자가 현장 정지·비접촉을 다시 확인했다. 종료 후 쓰기 차단 3회 read-only 값은 arm `[-6.285714,-67.384615,+83.648352,+28.439560,-22.197802]°`, gripper encoder `5.018360%`, Moving 전 축 `0`, Torque 전 축 `1`, Tmax `38°C`, Elbow Goal−Present `−1.846154°`로 동일했다. 실행 전 대비 Elbow `+1.318681°`, Wrist Roll `−0.087912°`; Pan/Lift/Flex/gripper encoder 변화 `0`. 물리 gripper aperture는 readback으로 판정하지 않는다.

자동 재시도와 신규 ticket 재무장 `0`. 소비된 ticket을 가진 현재 서비스는 다음 시작 시 bus open 전에 fail-closed하며 정상 텔레옵으로 자동 전환하지 않는다. 다음 실기 전에는 startup Moving의 관절·지속시간을 **모터 명령 없이** 분리하고, 정지 gate를 유지하는 수정만 검토한 뒤 사용자 새 승인을 받아야 한다. 원본 로그·비밀번호·trace 데이터는 커밋하지 않는다. 변경 `NOT_COMMITTED/NOT_PUSHED`, GitHub 이슈 `NOT_RUN`(대상 미지정).
