# 2026-10-14 CURRENT→C minimum residual correction READY

## 최신 live 결과

`DIRECT_COUPLED` 5 waypoint를 모두 전송했지만 final target tolerance를 통과하지 못했다.

```text
Target  = [+14.845130,-16.993354,+70.591582,-37.176891,-12.536328] deg
Present = [+14.549451,-16.571429,+72.659341,-36.000000,-12.879121] deg
Error   = [-0.295679,+0.421925,+2.067759,+1.176891,-0.342793] deg

SEND=5 / PAUSE=49 / ABORT=1
failure=final_joint_target_timeout
```

사용자 `STOPPED` 후 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`다. Moving all `0`, final Load diagnostic `[-24,32,108,68,-24,0]`, final temperature max `52°C`다. runner가 해제된 후 follower port는 free고 teleoperation/recording/inference는 inactive다. 원본 JSONL은 Jetson에만 보존하며 SHA-256은 `d4e5b9c03b0a7b0448aaccf50aa5368644ab3e4ae15009fd9ed5e62c0af168b1`이다.

## task-space residual

기존 URDF, GRASP TCP, C XY, endpoint를 변경하지 않았다.

```text
current GRASP TCP = [-59.179670,-288.018120,+85.287746] mm
desired GRASP TCP = [-62.635356,-295.315566,+100.000001] mm
error current-desired = [+3.455686,+7.297446,-14.712256] mm
position error norm = 16.782281 mm

current tool axis = [-0.235924,-0.909054,-0.343455]
desired tool axis = [-0.245747,-0.927197,-0.282692]
tool-axis error = 3.677307 deg
jaw-axis error = 3.647106 deg
full orientation error = 3.685802 deg

current table proxy clearance = +30.628746 mm
C XY error = 8.074309 mm
self-collision centerline = 64.051544 mm / PASS
servo margin = 22.351659 deg
full mesh/environment = NOT_VERIFIED
```

C 약통은 현장 보고 치수상 body `30 mm`, cap `35 mm`이다. 단순 반경을 임의 acceptance tolerance로 사용하지 않았다. 더 강한 기존 실기 근거는 task-space error `6.899170 mm`, C XY error `2.596020 mm`에서도 사용자가 두 finger tip contact로 FAIL한 것이다. 현재는 그보다 position error가 크고 Z가 desired보다 `14.712256 mm` 낮으므로 `TASK_SPACE_PRE_APPROACH_CANDIDATE=false`다.

## correction 비교

| candidate | waypoints | max step | TCP Z mm | min table proxy | self centerline | servo margin |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| C1 Wrist→Elbow→other | 6 | 0.689253° | 85.288→87.056→88.832→91.886→94.965→98.069→100.000 | +30.629 mm | 64.052 mm | 22.352° |
| C2 Lift/Wrist→Elbow+Pan/Roll | 5 | 0.689253° | 85.288→87.966→90.656→93.746→96.861→100.000 | +30.629 mm | 64.052 mm | 22.352° |
| C3 all-axis direct-coupled | 3 | 0.689253° | 85.288→90.140→95.045→100.000 | +30.629 mm | 64.052 mm | 22.352° |

C1은 실기에서 이미 실패한 Wrist-only 선행을 반복하고, C2는 더 긴 경로다. C3는 동일 endpoint에 도달하는 가장 짧은 경로이며 Elbow/Wrist를 분리하지 않는다. 따라서 `MINIMUM_RESIDUAL_DIRECT_COUPLED` 3 waypoint만 선택했다.

```text
waypoint 1 = [+14.648010,-16.712070,+71.970088,-36.392297,-12.764857] deg
waypoint 2 = [+14.746570,-16.852712,+71.280835,-36.784594,-12.650592] deg
waypoint 3 = [+14.845130,-16.993354,+70.591582,-37.176891,-12.536328] deg
```

## runner 검증·배치

기존 `live_c_approach.py`/bounded continuous following/safety gate를 재사용했다. calibration, C XY, GRASP TCP, endpoint, final tolerance, following limit, gain, torque는 변경하지 않았다.

```text
related tests = 59/59 PASS
py_compile = PASS
JSON validation = PASS
git diff --check = PASS
local dry-run = PASS / no port opened / no send_action

Jetson folder = /home/jetson3/so101-c-minimum-residual-correction-20261014/
runner SHA = 8ec9d84103b7c28befd5224f75c5abfe90861f9bbc9b17b1c62f73b725ca183e
config SHA = 7a0c4bd9a95d8c6f1968bb2145215e4951400c2479d8054897cdce3e37f5c97e
local/Jetson SHA = MATCH
Jetson installed Python compile/dry-run = PASS
hardware command = 0
live = NOT_RUN / NOT_AUTHORIZED
```

다음 actual motor command는 fresh start/gripper/ownership/controls gate를 다시 통과한 뒤 사용자가 `RUN MINIMUM RESIDUAL CORRECTION ONLY`를 신규 승인해야만 실행한다.
