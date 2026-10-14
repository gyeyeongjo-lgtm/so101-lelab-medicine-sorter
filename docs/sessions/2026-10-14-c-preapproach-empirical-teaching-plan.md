# 2026-10-14 C empirical pre-approach teaching — code-only preparation

> 이후 trace 배치·fake 검증은 [배치 기록](2026-10-14-c-preapproach-empirical-trace-deploy.md)을 따른다. 아래 `NOT_INSTALLED`는 이 초기 계획 시점의 기록이다.

## 기준선

`PRE_APPROACH_PASS=false`. 마지막 minimum residual correction은 3 target 뒤
`final_joint_target_timeout`으로 종료했고, Elbow/Flex 실제 이동은 각각 `0°`,
GRASP TCP Z는 `85.287746→83.763771 mm`였다. 사용자 `STOPPED`와 feedback으로
`physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. sub-degree correction, tolerance
완화, calibration/C XY/GRASP TCP/ideal IK 변경 및 자동 재시도는 하지 않는다.

직전 read-only follower Present는
`[+14.549451,-16.395604,+72.835165,-36.000000,-12.879121]°`, gripper
`34.516524%/raw 977`, Moving all `0`, Torque all `1`, Tmax `40°C`였다.
이는 **이전 snapshot**이지 다음 텔레옵의 fresh start가 아니다.

## 설치본 read-only 조사

- canonical LeLab 8000은 active, teleoperation/recording/inference는 모두 inactive.
- 설치 환경은 `LELAB_TELEOP_MODE=relative_start`; canonical USB serial은
  leader `5AE6085272→/dev/ttyACM0`, follower `5AE6058306→/dev/ttyACM1`.
- 설치 `teleoperate.py` SHA-256은 `85b69414…51d3c16`, trace 모듈은
  `8ccf8b51…3c56`이다. 설치 코드에서 `relative_start`와 `CycleTrace`를
  동시에 활성화하면 명시적 `RuntimeError`로 거부한다. 기존 trace의 전송
  분기는 `robot.send_action` 절대 action이며 이번 teaching에 사용 불가다.
- 따라서 trace 환경변수만 켜고 `/move-arm`을 호출하는 것은 금지한다.
  relative-start 제어 로직을 그대로 둔 채 동일 worker/버스 소유자에서
  **전송 후 read-only observation**을 연결해야 한다.

## 이번 code-only 변경

- `scripts/teleop_cycle_trace.py`: 기존 `CycleTrace`에 relative-start
  `observe_relative_cycle` 경로를 추가했다. 이 함수는 전송 API가 없고
  실제 guarded dispatch의 `command_sent`를 명시한다. 같은 소유 버스의
  Goal/Present raw, Moving, signed Present_Load, 축별 Temperature, normalize된
  Goal/Present, FK GRASP TCP XYZ를 검증해 같은 cycle row에 쓴다.
  Temperature `>55°C`/읽기 오류는 해당 row를 incomplete로 기록하고 예외를
  전파한다. Load 절대값 gate는 없다.
- `scripts/recorded_pose_config.py`: 3회 Present의 평균/표준편차로
  `C_PREAPPROACH_EMPIRICAL`을 기록할 수 있게 하고, 기존 ideal IK의 joint와
  task-space 차이를 **비교 정보**로만 저장한다. 실제 측정 전 pose config는
  변경하지 않았다.
- 관련 단위시험 `29/29 PASS`, py_compile 및 diff-check PASS. Jetson 설치,
  service restart, serial open, Goal/torque/motor command는 모두 `0`이다.

## 다음 live 전 필수 준비와 gate

1. 설치 `teleoperate.py`의 relative-start 기존 range/step/elbow guard를
   보존하는 최소 연결을 별도 검토·테스트한다. 설치 Python/소스/SHA를 다시
   확인하고 trace 모듈과 기존 URDF FK를 같은 worker에 배치한다. 배치 후
   LeLab 서비스 재시작이 필요하면 control inactive·포트 무점유를 다시
   확인하고 변경 전후 hash/rollback 절차를 기록한다. **현재 미완료**.
2. hardware-disconnected fake worker에서 HOLD, SEND, 진단 읽기 실패,
   3초 startup stillness를 검증한다. relative-start 첫 target은 fresh
   follower origin이어야 한다. 3초간 사용자 무입력에서 startup jump,
   Present drift, Moving 또는 trace 오류가 있으면 이동을 시작하지 않는다.
3. 현장 사용자는 팔 정지·전체 링크/table/C/finger 비접촉·주변 clear를
   확인한다. teleoperation/recording/inference inactive, canonical
   USB ID, leader/follower 정확히 단일 owner, 현재 gripper opening 유지,
   fresh follower feedback/Temperature `<=55°C`를 확인한다.
4. 별도 live 승인이 있으면 canonical 8000의 **한** relative-start 세션에서
   사람이 현재 pose부터 천천히 C opening-center 정렬과 비접촉 높이를
   만든다. 자동 arm waypoint·gripper target·Torque 변경은 없다.
5. 사용자가 `C PREAPPROACH ALIGNED`와 현장 비접촉을 확인하면 teleop을
   종료·포트 해제한다. 그 뒤 read-only 3회 Present/Goal/Moving/Load/
   Temperature와 FK를 기록한다. trace 오류 0, 해시, 사용자 확인,
   세 표본 안정성을 확인한 뒤에만 `C_PREAPPROACH_EMPIRICAL=RECORDED`로 저장한다.
   ideal IK와 일치할 필요는 없다.
6. 성공 trace가 생긴 뒤에만 실제 follower movement/coordination을
   보존하며 offline replay를 단순화한다. sub-degree 무효 target을
   반복하지 않는다. dry-run/test 후 자동 replay는 별도 승인이다.

## 현재 상태

```text
C_PREAPPROACH_EMPIRICAL = NOT_RECORDED
RELATIVE_TRACE_INTEGRATION = NOT_INSTALLED / NOT_VERIFIED
SUPERVISED_TEACHING = NOT_RUN / NOT_AUTHORIZED
AUTO_REPLAY = NOT_RUN / NOT_AUTHORIZED
hardware_command = 0
full_mesh_environment = NOT_VERIFIED
git_this_turn = NOT_COMMITTED / NOT_PUSHED
github_issue_update = NOT_RUN (target issue not identified)
```

현재는 `RUN SUPERVISED ...`를 요청할 준비가 아니다. 먼저 상대 텔레옵
기록 연결을 설치본에서 검증해야 한다.
