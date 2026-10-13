# 2026-10-12 SAFE_HIGH→C PRE_APPROACH 실기 시도 1 — start gate 차단

## 승인 범위

```text
RUN SAFE HIGH TO C PRE APPROACH
```

허용 범위는 기록된 SAFE_HIGH에서 새 GRASP TCP 기반 C PRE_APPROACH까지 한 번 이동하는 것이었다. approach, gripper close, lift, RED place는 포함하지 않았다.

## 실행 전 확인

```text
teleoperation_active = false
recording_active = false
inference_active = false
follower = /dev/ttyACM1
ID_SERIAL_SHORT = 5AE6058306
privileged fuser = rc 1 / unowned
runner SHA = 664ec12cb11c5b17f76531e921b3dde00c839618ef7f2cf9837e4f5c8870ef33
config SHA = efd8e2945b41892d0be4109ccd132fcfc8ee7eeefeb01c79333d383a678f2064
```

## fresh start gate

runner는 follower bus를 연 뒤 fresh Present를 읽었지만 저장 SAFE_HIGH와 일치하지 않아 path 생성과 target 송신 전에 차단했다.

```text
fresh minus SAFE_HIGH:
Pan   = -3.868 deg
Lift  = -86.857 deg
Elbow = +150.681 deg
Flex  = -24.879 deg
Roll  = +2.637 deg

allowed start tolerance = 1.0 deg per arm joint
failure = staged_reference_start_mismatch
```

이 차이는 직전 HOME-near 자세와 일치한다. 저장 pose를 current로 가정하지 않은 fresh gate가 의도대로 동작했다.

## 명령·종료 상태

```text
START_POSE_CONFIRMED = false
first target sent = 0
Goal write = 0
motor command = 0
Torque change = 0
following log exists = false
PRE_APPROACH_PASS = false
approach/grasp/lift/place = NOT_RUN
```

종료 뒤 세 LeLab control은 계속 inactive이고 live runner는 없다. privileged follower `fuser rc=1`로 포트 해제를 확인했다. 실제 이동 명령이 없었으므로 자동 STOP prompt는 발생하지 않았다. 이번 시도 뒤 사용자의 새 현장 stop/noncontact 입력은 아직 없으므로:

```text
physical_stop = FEEDBACK_ONLY_NO_COMMAND
full_mesh_environment = NOT_VERIFIED
```

## 다음 단계

현재 pose에서 동일 명령을 재실행하지 않는다. 사용자가 현장에서 supervised relative-start teleop으로 follower를 기록 SAFE_HIGH에 둔 다음:

```text
teleop 종료
전체 링크 비접촉 확인
실제 정지 확인
follower port release
```

를 완료해야 자동 pre-approach를 다시 승인할 수 있다.
