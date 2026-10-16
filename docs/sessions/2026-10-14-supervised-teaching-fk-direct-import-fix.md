# Supervised teaching FK direct-execution import — 비실기 수정·검증

직전 `TEACHING=ABORT_BEFORE_ARMING`, `PRE_ARM_SETTLE=NOT_RUN`, `RECORDER=NOT_ARMED` 기준을 유지했다. 실제 teaching의 `--live` 명령은 재실행하지 않았다. 원인 재현은 같은 Jetson 격리 폴더·설치 Python·직접 스크립트 import 문맥에서 **FK 호출까지만** 한 serial 없는 명령이다.

```text
cwd=/home/jetson3/so101-current-hold-teaching-20261014
PYTHONPATH=<unset>
Python=/home/jetson3/.local/share/uv/tools/lelab/bin/python (3.14.7)
command=/home/jetson3/.local/share/uv/tools/lelab/bin/python -c 'import sys; from pathlib import Path; sys.path.insert(0,"scripts"); from teleop_cycle_trace import load_grasp_fk; load_grasp_fk(Path("/home/jetson3/so101-c-empirical-trace-20261014/so101_new_calib.urdf"), Path("/home/jetson3/so101-c-empirical-trace-20261014/c_pick_grasp_tcp_candidate_20261012.json"))'
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import sys; from pathlib import Path; sys.path.insert(0,"scripts"); from teleop_cycle_trace import load_grasp_fk; load_grasp_fk(Path("/home/jetson3/so101-c-empirical-trace-20261014/so101_new_calib.urdf"), Path("/home/jetson3/so101-c-empirical-trace-20261014/c_pick_grasp_tcp_candidate_20261012.json"))
                                                                                                                      ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/jetson3/so101-current-hold-teaching-20261014/scripts/teleop_cycle_trace.py", line 112, in load_grasp_fk
    from .urdf_forward_kinematics import UrdfKinematics
ImportError: attempted relative import with no known parent package
```

원인 분류 `A: relative import / package context`. 직접 실행 시 `teleop_cycle_trace.__package__`가 비어 있는데 기존 분기가 상대 import를 선택했다. FK 파일은 배치되어 있어 `C`가 아니며, 설치 Python에서 직접 실행되는 teaching entrypoint는 형제 모듈을 top-level로 import한다. 원래 live 명령 전체를 그대로 재실행하면 포트 연결 위험이 있어 사용하지 않았고, 실패 지점까지의 동일 import 문맥만 재현했다.

`scripts/teleop_cycle_trace.py`의 FK import 분기만 바꿨다. 패키지 import는 기존 상대 import, 직접 실행은 형제 모듈의 top-level import를 사용한다. 임시 `sys.path` 하드코딩, FK 수식·GRASP TCP·calibration·pose·reference·safety gate 변경은 없다. Jetson **격리 폴더만** 갱신하고 이전 파일은 `.pre_direct_fk_import_20261014`로 보존했다. 설치 LeLab 서비스/worker/env는 변경하지 않았다.

수정 후 같은 cwd/PYTHONPATH/설치 Python의 직접 실행 문맥에서 기존 URDF와 TCP config를 로드한 FK zero-joint smoke XYZ `[8.582931784596205,-402.00512055359854,262.1044942735354] mm` PASS. `python scripts/supervised_teaching_from_current_hold.py` dry-run PASS, 패키지 import PASS, `py_compile` PASS. Jetson fake `39/39 PASS`는 fake leader/follower, recorder 파일, relative-start fresh-origin, PRE_ARM_SETTLE transient/abort, 첫 Goal 생략, write firewall을 포함한다. 로컬 동일 테스트 `39/39 PASS`; 배치 두 파일 SHA-256은 로컬/Jetson 일치했다.

```ini
IMPORT_ROOT_CAUSE = A (direct-execution relative import without package context)
IMPORT_FIX = direct top-level sibling import; package relative import preserved
DIRECT_EXECUTION = PASS (serial-free import and CLI dry-run)
FK_SMOKE_TEST = PASS
NO_RECONFIG_TEACHING_READY = PASS_FAKE_DRY_RUN_ONLY
SERIAL_OPEN = 0
MOTOR_COMMAND = 0
GOAL_WRITE = 0
TORQUE_WRITE = 0
CONFIG_WRITE = 0
TELEOP_ACTUAL_RUN = false
NEXT_LIVE_COMMAND = RUN SUPERVISED C APPROACH TEACHING
```

다음 live는 별도 승인과 fresh 현장·포트·상태 gate가 필요하다. 이번 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정).
