# 2026-10-10 relative_start teleop 준비

- 사용자 요청에 따라 absolute 모드는 기본값으로 보존하고 `LELAB_TELEOP_MODE=relative_start` 선택 경로의 계산 모듈/worker patch를 로컬에 준비했다. Jetson SSH 출력의 설치 `teleoperate.py` SHA-256은 `042c5f76fe31517637fa056eb7508ae696ed8604091103287b16b39b75ac7c54`였다. 포트 설정은 바꾸지 않았다.
- 새 worker는 follower/leader fresh calibrated values를 읽은 뒤에만 loop target을 만들고, 첫 target은 follower origin을 그대로 쓴다. 다음 target은 `follower_origin + (leader_now - leader_origin)`이며 gripper도 0–100 calibrated action unit에서 계산한다. relative mode에서는 기존 고정 wrist/elbow offset을 적용하지 않고, 별도 elbow feedback/step guard 및 통신 예외 중단을 유지한다.
- follower calibration endpoints는 실행 LeRobot bus의 `_normalize()`로 action unit으로 환산한다. 어느 축이든 target이 범위 밖이면 전체 action SEND 없이 warning/HOLD, clipping 없음. Missing/non-finite origin/range는 fail closed.
- 설치 Python의 LeLab 0.1.0 / LeRobot 0.6.0 source와 Jetson이 일치하는지 코드는 해시 기록만으로 추정하지 않는다. Jetson 설치와 service reload는 사용자 관리 대상으로 `NOT_RUN`; LeLab process/USB port를 시작·종료·점유하지 않았다.
- 로컬 fake-input tests 7/7 PASS; patch syntax (`git apply --numstat`) 및 `git diff --check` PASS. Live validation `NOT_RUN`: deliberately different pose start, fixed leader 3 s, one small joint movement. Current worker lacks a generic tracking-error guard (`max_relative_target=None`), so no new threshold was invented; that requested safeguard must be resolved before claiming validation complete.
- 5점 capture `0/5`; relative_start deployment and physical acceptance remain `BLOCKED/NOT_RUN`. Changes `NOT_COMMITTED/NOT_PUSHED`.
