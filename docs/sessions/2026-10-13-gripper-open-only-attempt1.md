# 2026-10-13 GRIPPER OPEN ONLY 실기 1 — 시작 자세 불일치로 송신 전 차단

## 승인 범위

사용자가 현장에서 팔 정지, finger opening sweep 비접촉, 주변 clear를 확인한 뒤 다음 단일 동작을 승인했다.

```text
RUN GRIPPER OPEN ONLY
```

승인 범위는 gripper를 `35%`까지 여는 한 축 명령 1회뿐이었다. arm target, 자동 재시도, CURRENT→C 경로 실행은 포함하지 않았다.

## preflight

```text
LeLab health      = OK
teleoperation     = inactive
recording         = inactive
inference         = inactive
leader            = /dev/ttyACM0, 5AE6085272
follower          = /dev/ttyACM1, 5AE6058306
privileged fuser  = no owner output
```

## 실행 결과

runner가 첫 target을 보내기 전에 fresh arm feedback과 저장된 시작 기준을 비교했고 다음 불일치로 fail-closed 차단했다.

```text
staged_reference_start_mismatch:
Pan   +0.088 deg
Lift  +1.143 deg
Elbow +1.055 deg
Flex  -4.659 deg
Roll  +0.000 deg
```

Wrist Flex가 전용 시작 tolerance `0.5 deg`를 초과했다. tolerance를 넓히지 않았고 target을 보내지 않았다.

```text
GRIPPER_OPEN_LIVE = BLOCKED_BEFORE_SEND
arm target send   = 0
gripper target send = 0
automatic retry   = 0
```

## 종료 후 read-only fresh telemetry

모터 명령 없이 `scripts/read_follower_pose_telemetry.py`의 로컬/Jetson SHA `7c440b81...f3c56` 일치를 먼저 확인하고 follower를 `0.2 s` 간격으로 정확히 3회 읽었다. 세 표본은 모두 동일했다.

```text
Present raw:
Pan 2236 / Lift 1715 / Elbow 2805 / Flex 1720 / Roll 1703 / Gripper 777

Present degree/percent:
Pan      +11.824176 deg
Lift     -21.054945 deg
Elbow    +72.219780 deg
Flex     -31.692308 deg
Roll     -14.197802 deg
Gripper  +22.276622 %

Goal raw:
Pan 2232 / Lift 1710 / Elbow 2795 / Flex 1706 / Roll 1703 / Gripper 785

Goal degree/percent:
Pan      +11.472527 deg
Lift     -21.494505 deg
Elbow    +71.340659 deg
Flex     -32.923077 deg
Roll     -14.197802 deg
Gripper  +22.766218 %

Goal-Present:
Pan -0.351648 / Lift -0.439560 / Elbow -0.879121 / Flex -1.230769 / Roll 0.000000 deg
Gripper +0.489596 pp

Moving          = all 0
Load diagnostic = [28,32,52,68,0,-44]
Temperature C   = [35,35,35,37,34,39]
Torque_Enable   = all 1
```

fresh arm pose로 계산한 새 GRASP TCP는 다음과 같다.

```text
GRASP TCP = [-46.465817,-292.231151,+93.372621] mm
```

이 값은 read-only FK 결과이며 full mesh/environment collision은 계속 `NOT_VERIFIED`다.

중요하게도 gripper target raw `985`는 기록되지 않았다. 종료 후 Goal raw는 `785`였으므로 이번 승인으로 gripper-open target이 송신됐다고 분류하지 않는다. 현재 gripper가 저장 기준 `2.264382%`와 다른 이유는 이번 실기로 확정하지 않는다.

## 종료 상태

read-only 도구는 `motor_write_calls=0`, `torque_change_calls=0`, `port_released_on_exit=true`를 보고했다. 이어서 privileged `fuser` owner output이 없음을 확인했고 teleoperation/recording/inference도 모두 inactive였다. SSH session은 종료했다.

```text
physical_stop       = 이전 사용자 현장 확인 유지; fresh Moving all 0
follower port       = free
hardware command    = 0
GRIPPER_OPEN_PASS   = false
CURRENT_TO_C        = NOT_RUN
APPROACH/GRASP/LIFT = NOT_RUN
```

자동 재시도는 금지한다. 다음 실기는 위 fresh pose와 현재 gripper를 기준으로 one-shot gripper-only 시작 gate를 오프라인 재생성한 뒤, 사용자가 정지·finger opening sweep 비접촉·주변 clear를 다시 확인하고 새로 승인해야 한다.
