# 2026-10-14 C empirical teaching trace 배치·fake 검증

## 범위와 기준선

사용자 승인은 **모터를 움직이지 않는 trace 연결·배치 검증만**이다.
`PRE_APPROACH_PASS=false`, `C_PREAPPROACH_EMPIRICAL=NOT_RECORDED`,
`physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`(직전 사용자 확인)를 유지한다.
실제 teaching, `/move-arm`, serial open, Goal/Torque write는 하지 않았다.

## 충돌 원인과 최소 수정

설치본 SHA `teleoperate.py 85b69414…51d3c16`, `teleop_cycle_trace.py
8ccf8b51…3c56`을 확인했다. `LELAB_TELEOP_MODE=relative_start`에서
기존 trace가 있으면 worker가 명시적 예외를 내며, 기존 trace 분기는
leader 절대 action을 `robot.send_action`으로 직접 전송한다. 문제는
상대좌표 계산과 기록 데이터가 양립 불가능한 것이 아니라, **기존
absolute-cycle recorder의 send 경로가 relative-start guard를 우회할
수 있어 차단한 것**이다.

`patches/lelab-20261014/teleoperate-relative-empirical-trace.patch`는
기존 relative-start range/step/Elbow guard 분기를 그대로 사용한다.
`empirical_relative_teaching`일 때만 그 분기 뒤에 전송 API가 없는
`CycleTrace.observe_relative_cycle()`을 붙인다. HOLD는 `command_sent=false`로
기록하고 sent command로 오기하지 않는다. 이전 `full_cycle` +
`relative_start` 조합은 계속 fail-closed다. trace 없는 relative-start와
absolute full-cycle 경로는 유지한다.

trace는 동일 worker의 follower bus에서 Goal/Present raw, Moving,
signed Present_Load, 축별 Temperature를 읽고, 기존 URDF SHA와 별도
PICK GRASP TCP offset으로 FK XYZ를 계산한다. Load는 diagnostic only,
Temperature `<=55°C`. 명시적으로 trace가 무장된 teaching 세션에만
전송 전 3초 leader/follower stillness gate가 추가된다.

## 격리·설치 검증

- Jetson 격리 폴더: `/home/jetson3/so101-c-empirical-trace-20261014/`.
  설치 Python으로 staged `teleoperate.py`/trace/FK/pose helper compile PASS.
  원본 patch `--dry-run` PASS, 실제 patched bytes와 staged copy `cmp` PASS.
  마지막 로컬 재검증의 첫 `patch --dry-run`은 잘못된 임시 디렉터리를
  지정해 파일을 찾지 못했다. 정확한 fixture 디렉터리로 재실행한
  reverse dry-run은 PASS했고 실제 코드/Jetson 파일은 영향받지 않았다.
- 설치 Python의 fake follower/leader에서는 **실제 serial class를
  monkeypatch**했다. startup relative origin, 3초 simulated stillness,
  follower Present, Goal/Moving/Load/Temperature, GRASP TCP FK, trace JSONL,
  종료 후 3회 읽기·fake pose YAML 생성이 모두 PASS(`7` cycle).
  trace 없는 기존 relative-start의 fake guarded dispatch도 PASS.
  기존 full-cycle trace + relative-start는 fake dispatch `0`으로
  `worker_error` fail-closed. 실패가 의도된 이 조합을 PASS로 재분류하지 않는다.
- 설치본 기존 두 파일을 격리 폴더의 `installed-backup/`에 원 SHA로 백업했다.
  새 세 모듈만 LeLab package에 설치했다. 설치 SHA:
  `teleoperate.py b4ed4913…b3eaa`, `teleop_cycle_trace.py
  bd51a4a2…f65826`, `urdf_forward_kinematics.py cc2c4d5f…a51f1`.
  설치 Python compile/import와 **실제 설치 파일을 로드한 fake worker**
  재시험도 같은 결과로 PASS.
- 세 control inactive 확인 후 8000 서비스만 재시작했다. 최초 즉시 health
  조회는 startup 도중 connection refused였고, 약 8초 후 application
  startup complete, 이후 health/teleoperation/recording/inference 조회 정상이다.
  `LELAB_TELEOP_MODE=relative_start`만 유지했고 trace root/ticket은
  **설정하지 않았다**. 따라서 recorder는 설치됐지만 현재 무장되지 않았다.
- 마지막 privileged read-only `fuser /dev/ttyACM0 /dev/ttyACM1`는
  출력 없음, rc `1`; 두 포트 무점유다. teleoperation/recording/inference
  모두 inactive. 설치본 검증은 fake/dry-run이며 실제 로봇 tracking
  compatibility나 접촉 안전을 주장하지 않는다.

## 결과

```ini
TRACE_DEPLOY = PASS (installed, active LeLab loaded, recorder not armed)
RELATIVE_START_COMPAT = PASS (fake/dry-run only; physical NOT_RUN)
LEGACY_FULL_CYCLE_PLUS_RELATIVE = FAIL_CLOSED_BY_DESIGN
EMPIRICAL_POSE = NOT_RECORDED
SUPERVISED_TEACHING = NOT_RUN / NOT_AUTHORIZED
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
REAL_SERIAL_OPEN = 0
NEXT_LIVE_COMMAND = RUN SUPERVISED C PREAPPROACH EMPIRICAL TEACHING
```

다음 live 전에는 사용자 현장 비접촉·정지 확인, 한 canonical 8000 owner,
USB serial/포트 무점유, current opening 유지, trace one-shot ticket/URDF/TCP
환경 설정을 새 승인 범위에서 수행해야 한다. 실제 follower Present 3회와
`configs/poses.yaml` 저장은 teaching 성공·텔레옵 종료 후에만 한다.
원본 fake JSONL은 임시 폴더에서 삭제됐으며 Git에 포함하지 않는다.
이 작업의 코드·문서는 선택적으로 로컬 커밋했으며 원격 push는
`NOT_RUN/NOT_PUSHED`다. GitHub 이슈 번호가 지정되지 않아 이슈 갱신은
`NOT_RUN`으로 남긴다. 사용자 소유 ArUco SVG/PDF 삭제는 커밋하지 않았다.
