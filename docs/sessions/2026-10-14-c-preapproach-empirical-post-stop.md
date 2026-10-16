# 2026-10-14 C empirical teaching — 종료 후 자세 기록, replay 보류

사용자는 `RUN SUPERVISED C PREAPPROACH EMPIRICAL TEACHING`을 승인했다. 첫 현장 확인은 미완료였고, 이후 확인으로 정정했다. 그때 canonical LeLab 8000은 이미 `teleoperation_active=true`였고 leader/follower 포트는 기존 LeLab 프로세스가 소유했다. 이 세션은 본 작업에서 시작한 것이 아니며 empirical recorder의 trace root/ticket은 무장되지 않았다. 사용자에게 중복 세션을 만들지 않고 기존 세션을 종료하도록 요청했다. 사용자는 C 쪽으로 접근했다고 알렸고, 최종적으로 `정렬·종료·비접촉 확인`을 보냈다.

종료 후 읽기 전용 확인: LeLab teleoperation/recording/inference 모두 inactive, privileged `fuser /dev/ttyACM0 /dev/ttyACM1` 출력 없음. Jetson의 측정 스크립트 SHA `7c440b81…65f3c56`은 로컬과 일치했다. canonical follower `/dev/ttyACM1`/serial `5AE6058306`을 해당 스크립트로 정확히 3회 읽었다(0.2초 간격). 쓰기 API는 차단됐고 결과는 `motor_write_calls=0`, `torque_change_calls=0`, `port_released_on_exit=true`다. 재확인한 privileged fuser도 무점유였다.

3회 Present는 모두 동일했다. Pan/Lift/Elbow/Flex/Roll `[+14.285714,+3.296703,+54.637363,-45.846154,-22.549451]°`, raw `[2264,1992,2605,1559,1608]`; gripper `30.905753%`/raw `918`. Goal raw는 `[2265,1983,2570,1558,1607,911]`, Moving 전 축 `0`, Torque_Enable 전 축 `1`, Tmax `42°C`. Elbow Goal−Present는 `−3.076923°`, Present_Load는 `[0,+48,+152,0,0,+40]`으로 진단값만 기록한다.

기존 URDF SHA와 GRASP TCP offset으로 계산한 TCP는 `[-67.465500,-331.309799,+100.623809] mm`, table reference 위 `+45.964809 mm`다. 기존 ideal IK endpoint의 TCP `[-62.635356,-295.315566,+100.000001] mm`와 차이는 `[-4.830144,-35.994233,+0.623808] mm`, XY `36.316870 mm`, 3D `36.322228 mm`. 이후 사용자가 `C PREAPPROACH PHYSICALLY ALIGNED`로 실제 정렬을 명시적으로 확인했다. FK/C 기준 위치와의 불일치는 그대로 기록하며 원인을 추정하거나 calibration을 변경하지 않는다. 그리퍼도 직전 `34.517%`보다 작아졌다.

측정 자세를 `configs/poses.yaml`의 `C_PREAPPROACH_EMPIRICAL`로 보존했다. 이는 **3회 측정된 endpoint**라는 의미만 가지며, 정렬의 기하학적 검증이나 trajectory replay 승인이 아니다. recorder가 무장되지 않았으므로 실제 이동 trace는 **NOT_RECORDED**. `PRE_APPROACH_PASS=false`를 유지하고 APPROACH/GRASP/LIFT 및 자동 replay는 **NOT_RUN/NOT_APPROVED**다. 이번 작업에서 agent motor/Goal/Torque command는 `0`; 실제 사용자의 기존 텔레옵 이동은 별개다. `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`(사용자 종료·비접촉 확인과 Moving=0). full-mesh/environment collision은 `NOT_VERIFIED`.

사용자는 이어 현재 `30.906%` 그리퍼 개방이 C를 비접촉으로 받아들이기에 충분하다고 확인했다. 이는 현재 측정 상태의 human clearance일 뿐 global opening 기준 변경이 아니다.

기존 URDF/GRASP TCP/servo calibration으로 empirical Present의 TCP XY와 orientation을 유지하면서 Z `100.623809→80.000001 mm`로 내리는 **오프라인 후보**를 계산했다. 관절 endpoint는 Pan/Lift/Elbow/Flex/Roll `[+14.285705,+14.593655,+53.575747,-56.081490,-22.549453]°`, 선형 bounded `12` waypoint, 최대 joint step `0.941413°`, TCP Z 상승 step `0`, 최대 XY drift `0.481473 mm`, 최소 TCP/table point proxy margin `25.341001 mm`, self centerline `64.775222 mm`, servo margin `40.373637°`다. full mesh/environment는 `NOT_VERIFIED`. 이는 실제 gripper/C 정렬을 수학적으로 증명하지 않는다. 현재 Elbow Goal−Present `−3.076923°`와 이전 sub-degree correction 무반응 때문에 tracking 위험이 있다. **실행 config/runner 배치와 live approval은 아직 NOT_RUN**; 특히 기존 `live_c_approach_only_20261012.json`은 낡은 PIN TCP와 다른 start pose를 쓰므로 재사용할 수 없다.

다음은 empirical 자세를 fresh start로 검증하고 매 waypoint 실제 TCP/접촉 관찰을 포함하는 APPROACH-only 실기 계획을 준비하는 것이다. 기존 ideal IK 시작 자세나 낡은 PIN TCP approach plan을 그대로 실행하지 않는다. 원본 로그/비밀번호는 커밋하지 않았다. 이번 문서·pose 변경은 `NOT_COMMITTED/NOT_PUSHED`; GitHub 이슈 갱신은 대상 이슈 번호가 없어 `NOT_RUN`; 기존 사용자 소유 SVG/PDF 삭제와 무관하다.
