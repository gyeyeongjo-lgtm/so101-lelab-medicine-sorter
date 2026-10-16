# HOLD_STABLE_QUANTIZED / no-reconfigure teaching Jetson 비실기 배치

범위는 독립 진입점의 Jetson 격리 폴더 배치와 설치 Python fake/dry-run뿐이다. 실제 serial, Goal, Torque, config, motor 명령과 teaching은 실행하지 않았다. 설치 LeLab 서비스·worker·설정은 수정하거나 재시작하지 않았다.

기존 `/home/jetson3/so101-current-hold-teaching-20261014/` 격리 폴더의 진입점·fake 테스트를 교체하고 원본을 `.pre_quantized_20261014` 사본으로 보존했다. 다른 의존 모듈은 배치 전 로컬 해시와 일치해 교체하지 않았다. 설치 Python `3.14.7`에서 진입점과 테스트 compile PASS, fake `17/17 PASS`, 기본 dry-run PASS (`serial_open=0`, `goal_write=0`, `torque_write=0`, `config_write=0`). 진입점 SHA-256 `6756fb2b…500753`, 테스트 `0e9c124f…8004`로 로컬·Jetson 일치. 로컬 관련 회귀 `59/59 PASS`.

fake에서 0/1 raw 안정 PASS, 2 raw·Moving·Present/Goal drift·온도 fault FAIL, 기존 exact-zero 1 raw FAIL을 확인했다. quantized 정책 fake는 3초 stillness 이후 follower origin capture, 첫 Goal 생략, recorder arm 및 one-shot ticket 소비 순서를 확인했다. write firewall fake는 torque/config/unarmed Goal을 차단했다. live 진입점의 현장 지지·정지·전체 비접촉 확인은 bus acquire보다 앞에 있고, 실제 현장 확인 입력은 이번에 수행하지 않았다.

현재 판정 자료는 이전 read-only 6회/21.79초의 동일 표본: Present `[2065,1467,2649,2497,1612,490]`, Goal `[2065,1466,2649,2497,1611,490]`, Torque 전 축 ON, Moving 전 축 0, Tmax `36°C`. 이 표본에 `HOLD_STABLE_QUANTIZED=PASS`; `CURRENT_HOLD_STABLE=false` 그대로다. **이번에는 serial을 열지 않았으므로 현재 순간의 Torque/Moving/Present drift 및 물리 비접촉은 fresh 재확인하지 않았다.** live 전 현장 비접촉, 3초 stillness, fresh pre-connect snapshot, 단독 포트, 새 one-shot ticket이 필요하다.

```ini
JETSON_DEPLOY = PASS (isolated entrypoint; installed LeLab service unchanged)
HOLD_STABLE_QUANTIZED = PASS (recorded six samples + Jetson fake)
NO_RECONFIG_TEACHING_READY = PASS (fake/dry-run only; live gates NOT_RUN)
TORQUE_WRITE = 0
CONFIG_WRITE = 0
MOTOR_COMMAND = 0
NEXT_LIVE_COMMAND = RUN SUPERVISED C APPROACH TEACHING
```

실제 teaching은 `NOT_RUN`; GRASP/LIFT도 `NOT_RUN`. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
