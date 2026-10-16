# ATOMIC HOLD RESTORE attempt1 — FAIL after one Goal write

## 승인과 실행 전 점검

사용자는 `RUN ATOMIC HOLD RESTORE` **실기 1회**만 승인했다. 성공해도 teaching/gripper open 금지이며 자동 재시도·추가 position correction·반복 torque toggle은 금지다. 실행 전 현장 답변은 **지지·정지·전체 비접촉·다른 제어 OFF·즉시 중단 준비 확인**이었다.

배치 SHA가 직전 검증본과 같음을 확인했다:

- atomic entrypoint: `715df70744bc6e45a21bacd404edecbafbe234b0265837f7d65e5c2b74207c92`
- exclusive bus: `a578706c6de62379dd1362e56f00c06efcfaa296370d24b4f1a3aa9a83a92d37`
- 종료 후 read-only helper: `7c440b81c503735df10d62662c72e1c4b8f1fee3dcbc4ceada5f5c40065f3c56`

설치 Python은 `/home/jetson3/.local/share/uv/tools/lelab/bin/python` 3.14.7이었다. 설치 `FeetechMotorsBus` 소스의 `sync_write(normalize=False)`에서 degree→raw normalization을 하지 않는 것, `_sync_write`의 `range(1 + num_retry)`로 retry=0일 때 packet 시도가 한 번인 것, `disconnect(disable_torque=False)`가 torque를 쓰지 않고 port를 닫는 것을 읽기전용으로 확인했다.

canonical follower `/dev/ttyACM1=5AE6058306`, leader `/dev/ttyACM0=5AE6085272`. LeLab teleoperation/recording/inference inactive, 관련 독립 실행 프로세스 미발견. 최초 noninteractive privileged 포트 확인은 sudo 인증 만료로 보류했으며, 인증 후 privileged `fuser` 무출력/exit1로 양 포트 무점유를 확인했다. 인증 오류를 포트가 비었다는 근거로 쓰지 않았다.

## 실행 명령과 원본 기록 위치

cwd는 `/home/jetson3/so101-current-hold-teaching-20261014`였다. 배치 코드는 수정하지 않았다.

```text
/home/jetson3/.local/share/uv/tools/lelab/bin/python -u scripts/atomic_hold_restore.py
  --live --approval 'RUN ATOMIC HOLD RESTORE'
  --port /dev/ttyACM1 --serial 5AE6058306
  --audit /home/jetson3/so101-current-hold-teaching-20261014/atomic-hold-live-20261015-Ie8dy6/audit.json
```

위 실제 명령은 한 줄로 정확히 한 번 실행했다. 사용자의 확인 내용을 진입점 현장 확인 prompt에 전달했다. lease·tty exclusive·raw 읽기 및 Goal 복사는 **하나의 exclusive session 안**에서 실행했다. 별도 goal-sync/enable 세션이나 다른 live controller를 시작하지 않았다.

## 최초 실패 — 예상 밖 Torque 전환

축 순서: Pan / Lift / Elbow / Wrist Flex / Roll / Gripper. 아래 값은 raw다.

| phase | Present | Goal | Torque | Moving |
| --- | --- | --- | --- | --- |
| FRESH_OFF_PRESENT | `[2066,1098,2902,2502,1612,490]` | `[0,0,0,0,0,0]` | ALL OFF | ALL 0 |
| PRE_SYNC_RECHECK | 위와 동일 | ALL 0 | ALL OFF | ALL 0 |
| GOAL_READBACK_TORQUE_OFF | 위와 동일 | `[2066,1098,2902,2502,1612,490]` | **ALL ON** | ALL 0 |

세 관측의 monotonic 시각은 각각 `1987812.694672224`, `1987812.778642342`, `1987812.901766573`이다. 온도는 당시 최대 37°C였다. fresh raw 그대로 6축 Goal을 1회 복사했고, 그리퍼도 raw490 그대로였다.

Goal readback은 intended raw와 같고 Present도 변하지 않았지만, **Torque OFF를 유지해야 하는 단계에서 이미 ON**이었다. 따라서 `RuntimeError:unexpected_torque:expected_all_0`로 즉시 중단했다. audit의 ABORT 시각은 `1987812.942977674`, write attempts는 다음과 같다.

```ini
Goal_Position = 1
Torque_Enable = 0
```

이 실패는 `ABORT_BEFORE_WRITE`가 아니다. Goal 쓰기가 실제 1회 있었으므로 `ABORT_AFTER_GOAL_SYNC_BEFORE_EXPLICIT_TORQUE_ENABLE`이다. explicit Torque ON 단계, ON 이후 3초 stability 단계는 **NOT_RUN**. 추가 쓰기·Goal correction·Torque OFF rollback·재시도는 하지 않았다. bus는 `disable_torque=False`로 종료했다.

Torque ON 주체/원인은 **UNKNOWN**이다. 시간상 Goal 복사 뒤 관측되었지만 펌웨어·SDK 부작용이나 다른 주체 중 어느 것인지 확정하지 않았다. 이번 작업을 원인 추적이나 수정으로 확대하지 않았다.

## 종료 후 read-only 3회

복구 세션이 종료되고 privileged 양 포트 무점유를 확인한 뒤, 쓰기 차단된 기존 helper를 `--samples 3 --interval 0.2`로 **한 번** 실행했다. 별도 Goal/Torque 쓰기 없이 정상 종료했다. 원본은 같은 run 폴더의 `post_readonly_3.json`에 있다.

세 표본 모두:

```text
Present raw = [2066,1098,2902,2502,1612,490]
Goal raw    = [2066,1098,2902,2502,1612,490]
Goal-Present raw = [0,0,0,0,0,0]
Torque = [1,1,1,1,1,1]
Moving = [0,0,0,0,0,0]
Present sample span = [0,0,0,0,0,0] raw
Temperature max = 38°C
```

세 표본의 unix ns는 `1792044578607366639`, `1792044578830167396`, `1792044579055623238`이다. 약 0.448초의 사후 측정이며, 이를 실행 중 요구한 3초 stability 통과로 대체하지 않는다.

정규화된 Present(deg, 마지막 gripper는 %)는 `[-3.120879121,-75.296703297,80.747252747,37.054945055,-22.197802198,4.712362301]`이었다. 이 변환은 읽기 결과 표시용이며 Goal 계산에는 사용하지 않았다.

사용자는 사후에 **지지·정지·자세 유지·전체 비접촉**이라고 확인했다. 따라서 실제 현재 상태는 정지·비접촉으로 보고하지만, 요청된 복구 순서가 성공한 것으로 바꾸지 않는다.

## 종료 상태

```ini
ATOMIC_HOLD_RESTORE = FAIL
FAILURE_PHASE = GOAL_READBACK_TORQUE_OFF
FAILURE = UNEXPECTED_ALL_ON_BEFORE_EXPLICIT_TORQUE_ENABLE
TORQUE_STATE_CHANGE_CAUSE = UNKNOWN
PRESENT = [2066,1098,2902,2502,1612,490]
GOAL = [2066,1098,2902,2502,1612,490]
GOAL_PRESENT_DIFF = [0,0,0,0,0,0] raw
TORQUE = ALL_ON
MOVING = ALL_0
PHYSICAL_NON_CONTACT = YES_USER_CONFIRMED
PHYSICAL_POSE_MAINTAINED = YES_USER_CONFIRMED
GOAL_WRITE = 1
TORQUE_WRITE = 0
CONFIG_WRITE = 0
THREE_SECOND_STABILITY_GATE = NOT_RUN
AUTOMATIC_RETRY = 0
TEACHING = NOT_RUN
GRIPPER_OPEN = NOT_RUN
GRASP = NOT_RUN
LIFT = NOT_RUN
NEXT_LIVE_COMMAND = NONE
```

최종 LeLab 세 제어 inactive, privileged 양 포트 무점유 확인 후 SSH 종료. calibration/reference/GRASP TCP/2° limit/trajectory tolerance는 변경하지 않았다. 코드 변경 없이 문서만 갱신했다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정). 원본 audit/telemetry와 비밀번호는 저장소로 복사하거나 커밋하지 않았다.
