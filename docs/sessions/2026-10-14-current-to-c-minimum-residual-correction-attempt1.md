# 2026-10-14 C PRE_APPROACH minimum residual correction 실기 1

사용자는 `RUN MINIMUM RESIDUAL CORRECTION ONLY`를 승인했다. 범위는 동일 C PRE_APPROACH endpoint로 향하는 3 waypoint뿐이다. 실행 전 배치 SHA 일치, LeLab teleoperation/recording/inference inactive, canonical follower `5AE6058306`→`/dev/ttyACM1`, 포트 무점유와 runner의 fresh start/gripper gate를 확인했다.

## 실기 결과

```text
START_POSE_CONFIRMED = C_DIRECT_COUPLED_ACTUAL_ATTEMPT2
fresh arm = [+14.549451,-16.571429,+72.659341,-36.000000,-12.879121] deg
gripper = 34.516524% / raw 977
waypoints sent = 3/3
SEND 3 / PAUSE 50 / ABORT 1
failure = final_joint_target_timeout
PRE_APPROACH_PASS = false
automatic retry = 0
APPROACH/GRASP/LIFT = NOT_RUN
```

사용자 `STOPPED` 후 runner는 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`를 출력하고 제어 포트를 해제했다. 별도 읽기 전용 스크립트는 로컬 파일과 Jetson 파일 SHA `7c440b81c503735df10d62662c72e1c4b8f1fee3dcbc4ceada5f5c40065f3c56` 일치를 확인한 뒤 실행했다. 첫 검토는 해당 스크립트 내용 확인 전이라는 이유로 자동 승인 검토에서 거부됐고, 내용을 확인한 뒤 재시도해 3회 같은 값을 얻었다.

```text
Present arm deg = [+14.549451,-16.395604,+72.835165,-36.000000,-12.879121]
Gripper Present = 34.516524% / raw 977
Goal raw        = [2270,1761,2786,1657,1721,977]
Present raw     = [2267,1768,2812,1671,1718,977]
Goal-Present deg= [+0.263736,-0.615385,-2.285714,-1.230769,+0.263736]
Moving          = all 0
Load diagnostic = [-24,40,116,68,-24,0]
Temperature max = 40 C
Torque_Enable   = all 1
read-only motor/torque writes = 0/0
follower port released = true
LeLab teleoperation/recording/inference = inactive
```

이 실기에서 실제 관절 변화는 Pan `0°`, Lift `+0.175824°`, Elbow `+0.175824°`, Flex `0°`, Roll `0°`다. Elbow와 Flex는 명령 방향으로 움직이지 않았고 Lift는 반대 방향으로 움직였다. 동일 URDF·GRASP TCP의 FK는 아래와 같다.

```text
GRASP TCP before = [-59.179670,-288.018120,+85.287746] mm
GRASP TCP after  = [-58.990806,-287.290391,+83.763771] mm
delta XYZ        = [+0.188864,+0.727729,-1.523975] mm
desired TCP      = [-62.635356,-295.315566,+100.000001] mm
current target error norm = 18.474343 mm
C XY error       = 8.813976 mm
table point proxy margin = +29.104771 mm
self centerline proxy = 63.754459 mm
servo margin = 22.175835 deg
full mesh/environment = NOT_VERIFIED
```

원본 Jetson 로그 `minimum_residual_correction_attempt1.jsonl` 54행 SHA-256 `1a8bbe68d6284b611c83b6d24f015a68468e6676293f07fb07d0288bf694adfd`는 Git에 포함하지 않는다. tolerance, gain, torque, calibration, C XY, GRASP TCP 및 endpoint는 변경하지 않았다. GitHub 이슈 갱신 `NOT_RUN`; 이 세션 기록의 원격 push `NOT_PUSHED`.
