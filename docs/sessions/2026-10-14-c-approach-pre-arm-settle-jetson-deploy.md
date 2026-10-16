# C approach PRE_ARM_SETTLE Jetson 설치·fake 검증

## 기준선과 범위

`TEACHING_ATTEMPT1=FAIL_AT_STARTUP_GATE`, trace cycle `0`, 종료 후 Elbow `+1.318681°` drift, GRASP/LIFT `NOT_RUN`을 유지한다. 이번 승인 범위는 패치 설치와 motor/Goal/Torque write 없는 검증뿐이다. 실제 teleop 시작이나 teaching 재시도는 하지 않았다.

## 설치

- Jetson 8000 user `lelab.service` active, LeLab 설치 Python `3.14.7`; 설치 경로 `/home/jetson3/.local/share/uv/tools/lelab/lib/python3.14/site-packages/lelab/` 확인.
- 시작 전과 재시작 직전 teleoperation/recording/inference 모두 inactive, privileged `fuser /dev/ttyACM0 /dev/ttyACM1` 출력 없음.
- 설치 전 `teleoperate.py` SHA `3235370bcd39867011a6b338f00e6e502bcfcc108ee94265dcd8da97dc912bb6`, `teleop_cycle_trace.py` SHA `032bc9e92bd9d88a1dabad0d28ecc8e4a06799e53b4f3f323c1544248cb65684`를 `/home/jetson3/so101-prearm-20261014-1LuthP/installed-backup/`에 보존했다. 다른 설치 파일은 변경하지 않았다.
- 새 두 파일을 설치하고 local/stage/installed SHA 일치: worker `3a8d6a13dc5537d61f28eae149b7f2075d13e53cf8a1594b86d3134289d3122f`, trace `5e19e1727b3e27c4aa5c915a4de4710dc48896b697f327bb70b2c3a267594fdb`. 설치 Python compile/import PASS.

## Jetson fake 검증

기존 설치 LeLab Python과 **실제 설치본 worker 소스**에 fake leader/follower를 주입해 serial을 열지 않고 아래를 검증했다. 같은 스크립트를 먼저 격리 stage에서 통과시킨 후 설치본에도 적용했다.

1. `PRE_ARM_SETTLE` 진입, 연결 직후 `Moving=1` 2 cycle 뒤 안정 → PASS.
2. 예상 외 Goal 변경 → ABORT, one-shot ticket 보존.
3. arm Present drift `≥1°` → ABORT, one-shot ticket 보존.
4. settle 뒤에만 fresh leader/follower origin 캡처; 3초 stillness 뒤 `TEACHING_ARMED`, 첫 실제 fake loop 진입에서만 ticket 소비.
5. teaching start 전 follower target send `0`; empirical gripper Goal 제외. trace 없는 기존 relative-start fake dispatch 보존, legacy full-cycle+relative 조합은 전송 전 fail-closed.
6. `startup.jsonl`의 PRE_CONNECT/FIRST_POST_CONNECT/PRE_ARM_SETTLE/SETTLED, `startup_summary.json`의 첫 Goal/Present/Moving·settled Goal/Present·축별 drift, cycle별 Goal/Present/Moving/signed Load/Temperature/FK, fake final 3회 sample 파일 생성 PASS.

fake guarded dispatch는 격리된 FakeFollower에만 발생했다. 실제 serial open `0`, motor command `0`, Goal write `0`, Torque write `0`이다. 실제 연결 직후 register 동작은 아직 `NOT_VERIFIED`이며 fake PASS를 물리 안전 증거로 취급하지 않는다.

## 서비스와 잔여 gate

세 제어 idle·포트 무점유 상태에서 `lelab.service`만 재시작했다. 새 프로세스 PID `573171`, health `ok`; `server.py`가 `teleoperate`를 import하고 설치본 import 확인에서 새 함수가 확인됐다. 재시작 뒤 teleoperation/recording/inference inactive, 두 포트 무점유. 기존 서비스 환경에는 과거 소진된 ticket 경로가 남아 있고 `LELAB_TELEOP_TRACE_PRE_CONNECT_JSON`은 미설정이다. 따라서 지금 UI에서 실수로 teleop을 시작해도 새 teaching이 정상 동작하지 않는 fail-closed 상태이며, 새 ticket이나 fresh snapshot을 이번 작업에서 만들지 않았다.

다음 별도 승인 전에는 현장 정지·비접촉·그리퍼 opening 확인, 세 제어 idle 및 단일 포트 owner, 쓰기차단 read-only pre-connect snapshot(60초 이내), 새 one-shot ticket 설정이 필요하다. 실제 teaching 재시도는 `NOT_RUN`; 이후 승인 문구는 `RUN SUPERVISED C APPROACH TEACHING RETRY` 하나다.

원본 로그·비밀번호·키·데이터셋은 커밋하지 않았다. 이번 변경 `NOT_COMMITTED/NOT_PUSHED`. GitHub 이슈 갱신 `NOT_RUN`(대상 번호 미지정); 기존 사용자 소유 SVG/PDF 삭제는 건드리지 않았다.
