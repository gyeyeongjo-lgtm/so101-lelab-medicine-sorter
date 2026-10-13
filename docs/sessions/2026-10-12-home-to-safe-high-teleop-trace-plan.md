# 2026-10-12 supervised HOME→SAFE_HIGH teleop trajectory recording 계획

## 기준선

```ini
HOME_SAFE_HIGH_HOME_ONCE=FAIL
FAIL_WAYPOINT=1/156
FAIL_REASON=ELBOW_NO_MOVEMENT_AND_TCP_Z_DECREASE
SYNTHETIC_78_WAYPOINT_RETRY=PROHIBITED
THREE_ROUND_TRIPS=PROHIBITED
physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED
```

기존 synthetic interpolation, Elbow/tolerance gate 완화, `>2°` step, gain/torque 변경은 사용하지 않는다. 다음 경로의 근거는 사람이 실제 성공시킨 relative-start follower trace여야 한다.

## 현재 설치 상태 — read-only 확인

- Jetson `lelab.service`: `active/running`, 현재 teleoperation/recording/inference는 모두 inactive
- systemd user environment: `LELAB_TELEOP_MODE=relative_start`
- 설치 `teleoperate.py`는 `CycleTrace`, `LELAB_TELEOP_TRACE_ROOT`, `capture_cycle`, fresh relative-start origin 경로를 포함한다.
- 현재 `LELAB_TELEOP_TRACE_ROOT`와 `LELAB_TELEOP_TRACE_ONCE_TICKET`은 설정되지 않아 trace 기록은 비활성이다.
- 설치 SHA256:
  - `teleoperate.py`: `85b694146cdfcd9a54e75fa8a67b78aaaf6d802db2be4f09cfd4d28ba51d3c16`
  - `teleop_cycle_trace.py`: `8ccf8b51b694fd77c71db711fa0cf83d08717c13a7819d663fbc1ab1c916dd3d`
  - `relative_start_teleop.py`: `ff9d1a7874e680bd5e1690d09790ee36f90ae2a918d39d449d7d6725229185a5`
- 로컬 relative-start `14/14`, CycleTrace `5/5`, py_compile, diff-check PASS.

## 기존 infrastructure 재사용 원칙

- canonical LeLab 8000 relative-start worker 하나만 leader/follower 포트를 소유한다.
- 별도 follower reader를 동시에 열지 않는다.
- 기존 `CycleTrace`를 같은 worker 내부에서 재사용한다. 새 teleop/control framework를 만들지 않는다.
- 기존 trace의 leader position, sent command, fresh follower feedback을 보존한다.
- 사용자가 요구한 Moving/Load/Temperature/Goal raw/Present raw는 **같은 follower bus owner**가 register별로 읽어 동일 cycle row에 추가한다.
- FK GRASP TCP XYZ는 같은 cycle의 Present와 설치 URDF, 기존 GRASP TCP offset으로 계산한다. calibration, TCP, URDF, table transform은 수정하지 않는다.
- diagnostics read나 FK/trace write가 실패하면 해당 cycle을 complete로 기록하지 않고 teleop을 중단한다.

## Phase 1 실행 계획

### 1. code-only 준비

1. 현재 설치 SHA를 다시 확인하고 일치할 때만 기존 CycleTrace에 diagnostic callback을 연결한다.
2. row schema에 다음을 추가한다.

```text
timestamp unix/monotonic
leader_position
follower_command / Goal joints
Goal raw
Present joints / Present raw
Moving
Present_Load diagnostic
Temperature
FK GRASP TCP XYZ
```

3. 가짜 버스로 모든 필드, read 오류 fail-closed, incomplete cycle 배제, 1회용 ticket 소모를 테스트한다.
4. 설치 Python py_compile과 hardware-disconnected fake run을 통과한 뒤에만 서비스 적용을 준비한다.

### 2. live preflight

1. 사용자 현장 확인: 팔 정지, 전체 링크/table/약통/바구니 비접촉, 주변 clear.
2. teleoperation/recording/inference inactive 확인.
3. canonical leader/follower USB identity와 privileged `fuser` 무점유 확인.
4. 임시 8002/8003 worker나 별도 serial reader가 없는지 확인.
5. fresh follower가 기록 HOME tolerance 안인지 확인한다. 직전 waypoint 1 종료 자세는 기록 HOME 대비 Lift `+1.319°`, Flex `+0.352°`여서 기존 tolerance 안이지만 저장값으로 대체하지 않고 live 직전 다시 읽는다.
6. trace root와 single-use ticket을 이번 세션에만 설정하고 canonical 8000 service 한 개만 사용한다.

### 3. startup stillness

1. `/move-arm` 요청은 한 번만 보낸다.
2. journal에서 `relative_start origins captured from fresh calibrated values`와 trace session 생성 하나를 확인한다.
3. 사용자는 leader를 3초간 움직이지 않는다.
4. 첫 relative target이 fresh follower origin과 일치하고, Moving all zero, command drift 없음, Present raw span이 encoder 1 count 이내인지 확인한다.
5. startup jump, duplicate teleop, trace 오류가 하나라도 있으면 즉시 stop하고 본 이동을 시작하지 않는다.

### 4. supervised HOME→SAFE_HIGH

- startup gate PASS 뒤 사용자가 leader로 천천히 다관절 coordination을 수행한다.
- 자동 waypoint나 synthetic interpolation은 없다.
- 기존 relative-start servo range와 per-cycle arm step `<=2°` guard는 유지한다.
- table/contact 위험, 예상하지 않은 움직임, feedback/trace 오류, 급격한 drift가 보이면 즉시 stop한다.
- `Present_Load`는 signed diagnostic이며 numeric PASS gate가 아니다. Temperature `<=55°C`와 communication/freshness는 유지한다.

### 5. SAFE_HIGH 도달·종료

1. 사용자가 실제 SAFE_HIGH 도달과 전체 링크 비접촉을 확인한다.
2. canonical teleop을 중지하고 leader/follower disconnect를 확인한다.
3. follower 포트 해제 뒤 fresh Present를 3회 read-only 측정한다.
4. 기존 SAFE_HIGH pose tolerance와 GRASP TCP Z 기준을 확인한다. 새 임의 tolerance는 만들지 않는다.
5. 원본 `cycles.jsonl`, `errors.jsonl`, manifest SHA를 Jetson Git 제외 경로와 Mac `.local/`에 보존한다.
6. 사용자 현장 확인, endpoint numeric verification, 오류 0, trace hash 확인이 모두 통과해야만:

```ini
HOME_TO_SAFE_HIGH_TELEOP_TRACE=PASS
```

로 기록한다. 그렇지 않으면 FAIL/INCOMPLETE로 보존하며 replay 후보로 사용하지 않는다.

## Phase 2 이후 경계

- SAFE_HIGH→HOME은 이 trace를 reverse하지 않는다.
- Phase 1 PASS 후 별도 계획·승인으로 독립 supervised trace를 기록한다.
- 두 방향이 모두 PASS하기 전 simplification/replay/왕복 성공을 주장하지 않는다.
- Phase 3 simplification은 성공 trace의 coordination을 보존하며, 원본 samples/waypoints/step/Z/servo/table/self proxy를 별도 출력한다.
- 최초 automatic 시험도 `AUTO_HOME_TO_SAFE_HIGH` 한 방향 1회만 수행한다.

## 현재 상태

```ini
HOME_TO_SAFE_HIGH_TELEOP_TRACE=NOT_RUN/NOT_AUTHORIZED
SAFE_HIGH_TO_HOME_TELEOP_TRACE=NOT_RUN
TRACE_DIAGNOSTIC_EXTENSION=PLAN_ONLY/NOT_INSTALLED
hardware_command=0
service_restart=0
Torque_change=0
full_mesh_environment=NOT_VERIFIED
git=NOT_COMMITTED/NOT_PUSHED
```
