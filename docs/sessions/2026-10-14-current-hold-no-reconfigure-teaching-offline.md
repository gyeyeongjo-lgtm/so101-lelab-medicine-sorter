# CURRENT HOLD 재확인과 no-reconfigure teaching 오프라인 준비

사용자는 이전 Goal sync 절차 FAIL과 Torque ON 주체 `UNKNOWN`을 유지하되, Goal/Present 근접·Torque ON·Moving 0·현장 지지·정지·비접촉의 현재 상태를 보존하며 read-only 3회+3초 안정성을 다시 확인하도록 요청했다. 실제 teaching, Goal sync, Torque toggle은 승인하지 않았다. 현장 지지·정지·전체 비접촉 유지 답변을 받았다.

Jetson LeLab 제어 세 작업 inactive, canonical follower `/dev/ttyACM1=5AE6058306`, privileged 양 포트 무점유에서 기존 쓰기 차단 도구로 두 세트(첫 3회 1.0초 간격, 다음 3회 0.2초 간격)를 측정했다. 첫 표본과 마지막 표본 시각은 `1791978108761751630`과 `1791978130554868283` unix ns로 약 `21.79 s` 차이다. 여섯 표본 모두 Present raw `[2065,1467,2649,2497,1612,490]`, Goal raw `[2065,1466,2649,2497,1611,490]`, Torque 전 축 `1`, Moving 전 축 `0`, Tmax `36°C`였다. Present·Goal 자체 drift는 없지만 Lift와 Roll 각각 Goal−Present `−1 raw`다. 요청 기준선은 직전 측정 `0 raw`였으므로 tolerance를 늘리지 않고 `CURRENT_HOLD_STABLE=false`다. read-only 후 두 포트 무점유, SSH 종료; hardware write `0`.

기존 상대제어 변환/2° arm guard/Elbow guard와 `CycleTrace`를 결합한 독립 `scripts/supervised_teaching_from_current_hold.py`를 추가했다. 기본 CLI는 serial 없이 dry-run 출력만 한다. 향후 별도 승인된 live 모드도 `/move-arm`, robot/leader configure, calibration write, Torque write를 호출하지 않고 follower/leader canonical 포트 단독 lease·write firewall을 적용한다. 현 기준 raw Goal/Present 정확 일치와 Torque all ON/Moving all 0, leader Torque OFF를 검사하고, 3초 no-send stillness 뒤 fresh origins를 캡처한다. 첫 origin Goal은 보내지 않는다. 실제 leader 변화 이후만 그리퍼 포함 6축 relative target을 기존 range/step/Elbow guard로 보낸다. `CycleTrace`는 startup·pre-guard request·첫 Goal·cycle·최종 3회 가짜 표본 파일을 만든다. gripper close, cycle당 2 pp 초과 open, prior human-confirmed `34.577723%` 초과는 송신 전 차단한다. fresh one-shot ticket은 teaching armed 이후에만 소비한다.

로컬 관련 회귀 `49/49 PASS`, py_compile/기본 dry-run/diff-check PASS. Jetson `/home/jetson3/so101-current-hold-teaching-20261014/` **격리 폴더**에 소스·fake test 사본만 배치했고 실제 설치 Python에서 compile, fake `7/7 PASS`, 기본 dry-run PASS(출력 serial_open/Goal/Torque/config write `0`); local/Jetson 최신 스크립트 SHA `79c147ae…2baa81`, 테스트 SHA `6ac91ed2…711c` 일치. 설치 LeLab worker/service/env는 변경·재시작하지 않았다. 실제 leader/follower 포트 연결, recorder live, teaching, GRASP/LIFT는 `NOT_RUN`. 추가 hardware command `0`.

```ini
CURRENT_HOLD_STABLE = false (strict baseline 0 raw; observed max diff 1 raw)
NO_RECONFIG_TEACHING_READY = PASS_OFFLINE_ONLY / LIVE_BLOCKED_BY_HOLD_GATE
TORQUE_WRITE = 0
CONFIG_WRITE = 0
FIRST_GOAL_SKIPPED = PASS_FAKE / LIVE_NOT_RUN
RECORDER = ON_IN_FAKE / LIVE_NOT_RUN
NEXT_LIVE_COMMAND = NONE
```

비밀번호·원본 telemetry·데이터셋은 커밋하지 않는다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
