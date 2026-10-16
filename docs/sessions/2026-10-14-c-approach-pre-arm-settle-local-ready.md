# C approach teaching PRE_ARM_SETTLE — 로컬 fake 검증

기준선: `TEACHING_ATTEMPT1=FAIL_AT_STARTUP_GATE`, trajectory cycles `0`, 시작 직후 `Moving=1`, 종료 후 Elbow drift `+1.318681°`. GRASP/LIFT `NOT_RUN`. gate 완화나 즉시 재시도는 없다.

## 변경

- `scripts/teleop_cycle_trace.py`: write-blocked 독립 pre-connect snapshot의 마지막 sample을 60초 이내로 제한해 읽는다. first post-connect 및 pre-arm 각 표본의 raw/degree Goal·Present, Moving, signed Load diagnostic, Temperature와 arm drift를 `startup.jsonl`에 남긴다. settle 통과 시 `startup_summary.json`에 `PRE_CONNECT_PRESENT`, `FIRST_POST_CONNECT_PRESENT`, `FIRST_POST_CONNECT_GOAL`, `FIRST_MOVING_STATE`, `SETTLED_PRESENT`, `SETTLED_GOAL`, 축별 drift를 저장한다.
- `PRE_ARM_SETTLE`: 최초 1–2 cycle의 Moving=1은 아직 teaching이 아니므로 즉시 ticket 소비로 연결하지 않는다. 이후 전 축 Moving=0과 Present raw 1 count 이내가 연속 1.0초여야 한다. Goal 변화, pre-connect 대비 arm 1° 이상 drift, 온도 >55°C/통신 오류, 5초 timeout은 ABORT한다. 이 동안 target send는 없다.
- `patches/lelab-20261014/teleoperate-pre-arm-settle.patch`: 기존 empirical arm-only worker 위에 적용할 최소 패치. follower bus 연결 직후, calibration/configure 이전 first read; configure 이후 settle; 그다음 fresh relative-start origins와 기존 3초 stillness; `TEACHING_ARMED` 후 첫 실제 teleop loop 진입 직전에 ticket 소비. 일반 relative-start 분기는 변경하지 않는다.
- `CycleTrace` 생성 시 empirical ticket은 존재 검사만 한다. pre-arm 및 armed-before-start 실패 시 보존하고 start 전 absolute send/relative observation은 fail-closed한다. 실제 start 시 ticket을 consumed 이름으로 이동한다.

## 비하드웨어 검증

- `python3 -m unittest tests.test_teleop_cycle_trace tests.test_relative_start_teleop`: `34/34 PASS` (순간 Moving=1 뒤 안정 PASS, 1° 이상 drift ABORT, Goal 변경 ABORT, ticket 보존/소비 포함).
- Mac bundled Python, LeLab/serial stub 및 fake leader/follower로 실제 worker 소스 흐름 실행: pre-arm 로그·settle summary·fresh origin 순서·armed 전 follower send `0`·empirical gripper Goal 제외·3회 final fake read·출력 파일 생성·기존 untraced relative-start·legacy full-cycle 충돌 fail-closed PASS.
- 패치 dry-run 및 Python compile, `git diff --check` PASS.
- 실제 serial open/Goal write/Torque write/motor command `0`. fake guarded dispatch 7회는 하드웨어 명령이 아니다.

## 미검증과 다음 조건

Jetson 접속은 batch SSH 인증 실패. 설치본 적용, Jetson 실제 Python fake, 서비스 재시작, 실제 초기화 뒤 register 읽기는 `NOT_RUN`. 사용자의 이번 요청 범위에서 실제 teaching을 시작하지 않았다. Jetson 적용 전에 기존 파일 백업·SHA 확인, canonical port 무점유·세 control idle, 정확한 설치 버전/worker 소스·옵션 재확인이 필요하다. pre-connect snapshot은 기존 쓰기 차단 read-only 도구에서 **세 control idle 중**, teleop 연결 직전 새로 획득해야 한다. 그 후 설치본 fake 검증이 통과하고 현장 정지·비접촉 및 새 승인까지 확인되기 전에는 `RUN SUPERVISED C APPROACH TEACHING RETRY`를 요청하지 않는다.

원본 로그·비밀번호·키는 저장/커밋하지 않았다. 현재 변경 `NOT_COMMITTED/NOT_PUSHED`; GitHub 이슈 갱신 `NOT_RUN`(대상 없음).
