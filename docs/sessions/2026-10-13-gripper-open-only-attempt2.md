# 2026-10-13 GRIPPER OPEN ONLY 실기 2 — 34.578%에서 정지

## 결과

fresh pose 기준으로 재생성한 gripper-only gate를 사용해 사용자 승인 `RUN GRIPPER OPEN ONLY` 범위에서 gripper 한 축 target을 1회만 전송했다.

```text
arm target send       = 0
gripper target send   = 1
Goal raw              = 985
Gripper before        = 22.521420%
Gripper final in run  = 34.516524%
arm drift             = 0 deg
Moving final          = all 0
Temperature max       = 40 C
automatic retry       = 0
```

Goal raw와 arm Goal raw 보존, 정지, 온도, arm drift gate는 통과했으나 final gripper가 `35%`보다 `0.483476 pp` 낮아 `gripper_open_verification_failed`로 FAIL 처리했다. 기준을 낮추거나 자동 재시도하지 않았다.

사용자가 `STOPPED`와 링크/finger 비접촉을 확인해 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`로 종료했다.

## 종료 후 fresh feedback

command-owning port 해제 후 read-only 3회가 동일했다.

```text
Present arm deg =
[+11.648352,-20.967033,+72.219780,-31.956044,-14.197802]

Gripper Present = 34.577723% / raw 978
Gripper Goal    = 35.006120% / raw 985
Moving          = all 0
Load diagnostic = [20,36,52,56,0,-40]
Temperature C   = [35,36,35,37,34,39]
Torque_Enable   = all 1
```

follower port는 privileged `fuser` owner output 없이 해제됐고 teleoperation/recording/inference는 inactive다.

## 다음 단계 오프라인 준비

post-open fresh arm에서 고정 C PRE_APPROACH endpoint까지 경로를 다시 만들었다. 선택된 `WRIST_LEAD_2DEG`는 `6` waypoint, max step `1 deg`, GRASP TCP Z `93.788216→100.000001 mm` 단조 증가, C XY distance `17.155476→0.000002 mm` 단조 감소다. gripper가 아직 `<35%`라 arm live gate는 계속 차단한다.

같은 runner/safety gate를 재사용하는 다음 단일 후보를 준비했다.

```text
RUN GRIPPER OPEN TO 36 ONLY
requested target       = 36.0%
normalized command     = 36.04651162790698%
expected Goal raw      = 1002
minimum PASS Present   = 35.0%
arm target allowed     = false
automatic retry        = false
```

이는 normalized high-level gripper command이며 raw 직접 write를 사용하지 않는다. 관련 targeted test `59/59 PASS`, local/Jetson compile·dry-run PASS, dry-run port/send `0`이다. 실제 36% 명령은 `NOT_RUN/NOT_AUTHORIZED`다.
