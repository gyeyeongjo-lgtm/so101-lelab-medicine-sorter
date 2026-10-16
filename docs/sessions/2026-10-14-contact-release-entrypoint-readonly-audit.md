# CONTACT_RELEASE_ONLY — LeLab entrypoint·trace 환경 읽기 전용 확인

## 범위

사용자가 현재 gripper/table 접촉을 보고했다. teaching과 gripper open은 계속 보류한다. 목표는 사용자가 leader로 follower를 몇 cm 들어 contact를 해제한 직후 teleop을 종료할 수 있는 기존 relative-start 경로를 식별하는 것뿐이며, 이번 턴에 teleop을 시작하거나 설정을 변경하지 않는다.

## 실제 설치 상태

Jetson 8000 user `lelab.service`는 active/running이고 설치 Python은 `3.14.7`이다. 실제 worker `/home/jetson3/.local/share/uv/tools/lelab/bin/python -m uvicorn lelab.server:app`의 실행 환경 중 관련 항목만 읽었다.

| 설정 | 현재 값/상태 |
| --- | --- |
| `LELAB_TELEOP_MODE` | `relative_start` |
| `LELAB_TELEOP_TRACE_KIND` | `empirical_relative_teaching` |
| `LELAB_TELEOP_TRACE_ROOT` | 설정됨 (`so101-c-approach-teaching-20261014-EhhIBa/traces`) |
| `LELAB_TELEOP_TRACE_PRE_CONNECT_JSON` | 미설정 |
| `LELAB_TELEOP_TRACE_ONCE_TICKET` | 경로는 설정되어 있으나 파일 없음(기존 소비) |

`lelab.server.py`는 `POST /move-arm`을 `handle_start_teleoperation`에 연결한다. 실제 `teleoperate.py`는 trace root가 설정되면 `empirical_relative_teaching`을 준비하면서 `LELAB_TELEOP_TRACE_PRE_CONNECT_JSON` 파일을 읽는다. 따라서 이 값은 **pre-connect snapshot/logging 입력**이지 별도 teleop launcher가 아니다. 현재는 값이 미설정이어서 이 trace 경로는 connect 이전에 실패할 수 있고, one-shot ticket도 소진 상태다. 반면 recorder OFF인 일반 relative-start의 진입점은 동일한 `/move-arm`이며 trace root가 없어야 한다.

실제 설치 source에서 일반 untraced relative-start는 `relative_target`을 사용하고 그리퍼를 포함한 6축 action을 보낸다. arm-only 분기는 `empirical_relative_teaching` trace가 존재할 때만 선택된다. 또한 `handle_start_teleoperation`은 origin capture 이전에 follower/leader connect, calibration write, `robot.configure()` 및 leader configure를 실행한다. 직전 Goal/Present 동기화 시도에서 Torque OFF gate가 예상과 달리 실패했고 현재 gripper/table 접촉이 있으므로, recorder 설정만 끄고 `/move-arm`을 호출하는 것을 현 시점의 안전한 `CONTACT_RELEASE_ONLY`로 판정할 수 없다.

읽기 전용 API는 teleoperation/recording/inference 모두 inactive였고 privileged `fuser`는 leader `/dev/ttyACM0`·follower `/dev/ttyACM1` 무점유였다. replay/record/inference/teleop 관련 별도 제어 프로세스는 보이지 않았다. 설정 수정, 서비스 재시작, USB/serial open, motor/Goal/Torque write, teleop 시작은 모두 `0`/`NOT_RUN`이다. 실제 접촉·움직임은 이번 턴에 하드웨어로 재측정하지 않았다.

```makefile
CURRENT_MODE = relative_start + empirical_relative_teaching trace CONFIGURED; teleop INACTIVE
CURRENT_ENTRYPOINT = POST /move-arm -> handle_start_teleoperation (NOT_CALLED)
IS_PRECONNECT_ONLY = teleop_trace_pre_connect_json is an input file, not a launcher; CURRENTLY_UNSET
SAFE_RELATIVE_START_ENTRYPOINT = POST /move-arm with TRACE_ROOT unset, but NOT_LIVE_READY for CONTACT_RELEASE_ONLY
RECORDER = CONFIGURED / INACTIVE / ticket absent
INFERENCE = INACTIVE
REPLAY = INACTIVE (no replay process found)
MOTOR_COMMAND = 0
NEXT_LIVE_COMMAND = NONE
```

다음 검토는 현재 table contact·Torque/Goal 불일치 조건에서 그리퍼 목표를 보내지 않고 startup jump 없이 contact를 해제할 수 있는지 별도로 검증하는 것이다. 이 검토와 새 현장 승인이 있기 전에는 `/move-arm`을 호출하지 않는다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
