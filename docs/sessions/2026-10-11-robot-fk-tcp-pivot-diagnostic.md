# 2026-10-11 robot-side FK/TCP pivot 진단

## 2026-10-12 approach timeout 뒤 자연 수렴 read-only 확인

- Pose/Goal/Torque를 변경하지 않고 controls inactive와 privileged ports unowned를 확인한 뒤 write/torque API 차단 viewer로 follower Present_Position만 5회 읽었다. 0.25초 간격 raw가 모두 `2100/2152/2164/2203/2026/446`; motor write/torque change `0/0`, viewer close 뒤 ports unowned.
- calibrated arm `[Pan -0.131868, Lift +17.362637, Elbow +15.868132, Flex +10.769231, Roll +14.197802]°`. Fixed approach target 대비 error `[-0.035382,-0.038342,+1.461058,+0.120460,-0.379376]°`다.
- Elbow는 ABORT raw `2168`에서 `2164`로 4 raw/`0.351648°` 추가 수렴해 target raw `2147` 대비 17 raw/`1.461058°`; unchanged final tolerance `1.6°` 안이다. 다섯 표본이 같아 더 움직이는 추세는 보이지 않는다.
- 요청의 조건부 endpoint-local 수정은 “여전히 약 1.8°”일 때였으나 현재 해당하지 않는다. tolerance/endpoint/pre-approach/start/calibration/C XY 전부 불변. 기존 controller run은 ABORT였으므로 user visual alignment/no-contact confirmation 전 `APPROACH_PASS`로 소급하지 않는다.

## 2026-10-12 C approach-only 실기 1 결과

- user approval `RUN C APPROACH ONLY`; preflight three controls inactive, no control worker, canonical follower `/dev/ttyACM1=5AE6058306`, privileged ports unowned, deployed SHA exact.
- fresh start arm `[-0.307692,+12.351648,+16.131868,+13.406593,+13.758242]°`, gripper `2.019584%`; required start와 max `0.087912°` 차이로 1° gate PASS. Six bounded targets were sent, gripper held unchanged; no grasp/lift transition exists or ran.
- final target arm `[-0.096486,+17.400979,+14.407074,+10.648771,+14.577178]°`. Final errors Pan/Lift/Elbow/Flex/Roll `[-0.035382,+0.049570,+1.812706,+0.208372,-0.379376]°`; Elbow only exceeded the unchanged `1.6°` tolerance by `0.212706°`.
- final Goal/Present raw Elbow `2147/2168`; 5-second verification plateaued at Present `2168`, error `1.812706°`, Moving `0`, load `96`. Controller ABORT `final_joint_target_timeout`; `APPROACH_PASS` false, auto-retry none.
- user `STOPPED` and feedback stillness produced `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. post-run teleop/recording/inference inactive and privileged both ports `fuser rc=1`.
- original log `.local/c-red-pivot-tcp-table-20261011-s01/live_c_approach_only_attempt1.jsonl`, SHA `a1d268e5274a404697bd44b69be7e40bcff5481ce4100b7de75c08052fed22ad`; 54 rows = `SEND 6 / PAUSE 47 / ABORT 1`. No tolerance/path/IK change, no retry, grasp/lift `NOT_RUN`, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 현장 복귀와 C approach-only 준비

- 사용자가 팔 완전 정지, 그리퍼/작업대와 전체 링크 비접촉, 야간 이후 자세 유지 확인을 현장에서 제공했다. 이 확인과 아래 fresh feedback으로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`로 복구했다.
- teleop/recording/inference inactive, 관련 worker 없음, canonical USB는 leader `/dev/ttyACM0=5AE6085272`, follower `/dev/ttyACM1=5AE6058306`, privileged 두 포트 `fuser rc=1`이었다.
- write/sync_write/enable_torque/disable_torque를 예외로 차단하는 read-only viewer로 follower fresh raw `2099/2095/2167/2233/2021/446`, calibrated arm `[-0.219780,+12.351648,+16.131868,+13.406593,+13.758242]°`, gripper `2.019584%`를 읽었다. motor write/torque change `0/0`; viewer 종료와 포트 release를 확인했다.
- 직전 pre-approach PASS final feedback `[-0.483516,+12.175824,+16.043956,+14.197802,+13.758242]°` 대비 delta는 `[+0.263736,+0.175824,+0.087912,-0.791209,0.000000]°`; max `0.791209°`다. 기존 final tolerance `1.6°` 안이므로 WRIST_DELAY_25나 pre-approach를 재실행하지 않고 현재 pose를 시작점으로 채택했다.
- 기존 vision/transform/IK에서 이미 계산된 C approach target `XYZ [-62.635354,-295.315566,80.0] mm`, arm `[-0.096486,+17.400979,+14.407074,+10.648771,+14.577178]°`를 변경 없이 별도 `live_c_approach_only` scope로 고정했다. fresh start gate `1.0°`, 1° bounded continuous-following, final `1.6°`, fresh gripper hold다.
- 새 하네스에는 approach stage 뒤 human alignment 확인과 `APPROACH_PASS`/stop만 있으며 gripper close와 lift transition이 없다. fake live는 6 waypoint와 gripper hold를 확인했고, start drift `1.01°`는 controller 생성 전에 차단했다. 관련 `17/17 + 8/8` tests, py_compile, local/Jetson dry-run PASS.
- Jetson dry-run 출력은 `no port opened; no send_action; grasp/lift unavailable`; 종료 뒤 두 포트 `fuser rc=1`. 배포 SHA는 `live_c_approach.py 3c20caaf…aed1`, `live_c_approach_only.py 0d288b08…21eb`, config `caa4d7e0…067f`다.
- actual C approach `NOT_RUN/NOT_AUTHORIZED`. 다음 승인 phrase는 `RUN C APPROACH ONLY`; success 뒤에도 grasp/lift 자동 연계 없음. `NOT_COMMITTED/NOT_PUSHED`.

## Directional HOLD / torque 유지 현재 설치 확인

- Python 3.14.7의 실제 설치 `lelab/teleoperate.py` SHA `e9300fc08f9225afd03a8503542fe6268474d4182077424dcb5ca9a120c77bd2`, guard SHA `1ca311d0cbf06db857992b64ed09d3ccb7230c72ef4df77137637a7a77204b09`를 읽었다. 객체 생성이나 버스 연결 없이 소스만 검사했다.
- directional guard는 import 및 호출 위치에 남아 있다. helper HOLD 경로는 return None으로 자체 send_action을 생략하고 Goal/Torque register는 변경하지 않는다.
- 실행 중 8000 PID 545264 환경의 모드는 relative_start이며 TEMP_WRIST_ALIGN은 없다. 설치 teleoperate 304행 guard 호출 후 공통 318–323행으로 이어져 raw send_action이 실행될 수 있다. 따라서 현재 설치의 HOLD guard는 존재하나 relative_start의 최종 송신 차단이 보장되지 않는 코드 결함이 보인다. 이번 범위는 진단뿐이므로 수정·실기 재현하지 않았다.
- follower config 169행 disable_torque_on_disconnect=False 확인. connect/configure는 torque_disabled context의 finally enable_torque로 토크를 켜며, teleop 종료 safe_disconnect_device→follower.disconnect→bus.disconnect(False)는 torque를 끄지 않는다. pre-approach transport와 fallback 종료도 disconnect(False)이고 command stop은 추가 송신만 차단한다.
- 새 read-only 확인: teleop inactive, privileged fuser /dev/ttyACM1 rc=1, LeLab 8000/8002 PID의 ttyACM FD 없음. 지속적인 host 연결 없이 전원이 공급된 서보가 마지막 Goal/Torque 상태를 유지하는 설명과 부합한다. 현재 6축 register는 사용자의 코드/설정만 확인하라는 범위에 따라 재측정하지 않았다. 정확한 마지막 enable 호출 시점/주체는 이 증거만으로 확정하지 않는다.
- 하드웨어 상태 변경 없음, serial open 없음. 로컬 이슈 기록만 갱신, 원격 이슈 NOT_RUN, NOT_COMMITTED/NOT_PUSHED.

## Directional HOLD fall-through 최소 수정

- torque 정책과 분리해 relative_start control flow만 수정했다. `dispatch_guarded_relative_action()`은 guard SEND 결과일 때만 target 상태를 갱신하고, HOLD(None)면 이전 elbow/relative target 상태를 유지하며, ABORT 예외는 worker까지 전파한다. 함수 자체에는 bus, Goal, Torque register 접근이 없다.
- teleoperate의 relative 분기와 absolute/temporary-align 분기를 명시적 `if relative_mode: ... else: ...`로 분리했다. direct `robot.send_action(action)`은 relative 분기의 else 쪽에만 존재한다. absolute 분기 내부의 target 계산과 SEND 코드는 내용 변경 없이 이동했다.
- 로컬 fake tests: relative_start 14/14, directional guard 14/14 PASS. 요구 결과: HOLD `send_action=0`, SEND `=1`, ABORT `=0`, HOLD 다음 away target `=1`, HOLD register writes `=0`.
- 설치 전 원본 `teleoperate.py=e9300fc…bd2`, `relative_start_teleop.py=863350b3…a431`. 설치 후 각각 `85b69414…d3c16`, `ff9d1a78…185a5`; guard helper는 `1ca311d0…04b09`로 불변. 원본은 `/home/jetson3/lelab-source-backups/2026-10-11-hold-fallthrough/`에 SHA 이름으로 보존했다.
- Jetson 설치 Python fake test가 같은 5개 조건을 통과했고 AST는 direct send 1개가 relative_mode else에만 있음을 확인했다. `disable_torque_on_disconnect=False`는 설치본에 유지된다.
- 적용 전 teleop/recording/inference inactive 및 privileged follower fuser rc=1을 확인했다. LeLab service만 재시작해 MainPID `545262→548555`; health 정상, 새 worker 환경 `LELAB_TELEOP_MODE=relative_start`, 세 제어 작업 inactive, follower fuser rc=1이다. serial open/motor command/Goal write/torque change 0회. 실제 하드웨어 HOLD 시험은 `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## C pre-approach final convergence 재시험 준비

- 최신 54-waypoint 실패는 final Elbow error `+1.733°`가 arm tolerance `1.6°`를 `0.133°` 넘긴 final convergence timeout으로 분류했다. vision 좌표, robot XY, IK target, tolerance는 변경하지 않았다.
- 기본 waypoint timeout `3.0 s`는 유지하고 마지막 waypoint에만 `5.0 s`를 적용했다. 기존 마지막 5개 선형 joint-space 구간을 각각 2분할하므로 동일 fresh start라면 54→59 waypoint가 되며, 경로의 선과 최종 target은 그대로다. 실제 waypoint 수는 매 실행 fresh pose에서 다시 산출한다.
- controller 도달 판정 뒤 별도 fresh follower feedback을 읽어 전 축 tolerance를 다시 통과해야만 `APPROACH_REACHED`로 진행하도록 했다. 성공해도 grasp/lift로 자동 진행하지 않는다.
- `test_live_c_approach` 5/5, `test_staged_cycle_execution` 10/10, `test_so101_exclusive_transport` 10/10 PASS. 로컬 및 Jetson 설치 Python dry-run PASS. Jetson 배포 SHA: `scripts/live_c_approach.py=1e79ccf…939d0`, `scripts/staged_cycle_execution.py=e6f5fdc…dd3d`, current plan `57b33088…6197`.
- 배포 직후 teleop/recording/inference inactive, 관련 제어 프로세스 없음, unprivileged `lsof` 무점유까지 확인했다. 이어 privileged fuser/fresh-pose preflight를 하려는 시점에 Jetson `192.168.50.20`이 SSH, HTTP 8000, ICMP 모두 timeout이 됐다. live 실행 프롬프트 이전이므로 이번 변경에 의한 follower port open, motor command, Goal/torque write는 0회다.
- 실제 재시험과 `PRE_APPROACH_PASS`는 **BLOCKED/NOT_RUN**. Jetson 네트워크 복구 후 control inactive/privileged port 무점유를 다시 확인하고, live 실행 안에서 fresh follower pose를 읽어 동일 target 경로를 생성해야 한다. grasp/lift는 `NOT_RUN`. 변경 `NOT_COMMITTED/NOT_PUSHED`.
- 네트워크 복구 뒤 SHA 일치, teleop/recording/inference inactive, 관련 제어 프로세스 없음, privileged follower port 무점유를 재확인했다. 첫 live 시작은 sudo timestamp 만료 때문에 내부 `sudo -n fuser`가 `port_ownership_unknown`으로 fail-closed했고 follower port open/motor command 이전에 종료됐다.
- 사용자의 동일 pre-approach 승인과 현장 문구를 유지해 sudo timestamp를 즉시 갱신한 뒤 한 번만 재시험했다. fresh start는 `(Pan −10.857143, Lift −93.054945, Elbow +96.043956, Flex +55.604396, Roll −17.626374, Gripper 1.958384)`였고, 최대 2°의 기존 선형 경로 마지막 5구간을 2분할한 총 58 waypoint를 생성했다.
- 실행은 다시 final `joint_target_timeout`으로 중단됐다. 마지막 feedback−goal은 Pan `−0.409°`, Lift `−0.957°`, Elbow `+2.360°`, Flex `+0.204°`, Roll `−0.486°`, Gripper `0.000`; Elbow만 1.6° tolerance 밖이다. 5초 final settle과 tail refinement로도 통과하지 않았으며, 이번 Elbow 값은 사용자가 지정한 tolerance 재평가 조건 `1.6–2.0°`보다 크므로 tolerance는 변경하지 않는다.
- `PRE_APPROACH_PASS` 아님, grasp/lift `NOT_RUN`, 자동 재시도 없음. 사용자 `STOPPED`와 fresh feedback 정지 window가 모두 통과해 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. 종료 후 세 LeLab 제어 inactive, 관련 제어 프로세스 없음, privileged follower `fuser rc=1` 무점유다. 결과 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_attempt_current.json`; 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 범위

- table→robot fit, 기존 5점 재촬영, live C robot XY, IK, 자동 motion 중단.
- 사용자가 관리하는 LeLab/teleop/service/USB에는 손대지 않음.
- LeLab joint WebSocket broadcast만 읽어 로컬 URDF FK와 physical TCP consistency를 진단.

## P1 대 Repeat P1

- 현재 frame: root `base`, tool/TCP frame `gripper`, TCP offset `[0,0,0] mm`.
- P1 joints deg: Pan `+22.901099`, Lift `+20.615385`, Elbow `+39.252747`, Wrist Flex `−57.890110`, Wrist Roll `−19.032967`.
- Repeat P1 joints deg: Pan `+21.670330`, Lift `+27.912088`, Elbow `+42.153846`, Wrist Flex `−74.329670`, Wrist Roll `−18.857143`.
- Repeat−P1 joint delta deg: `(-1.230769,+7.296703,+2.901099,-16.439560,+0.175824)`.
- P1 raw FK origin: `[-68.687344,-234.435191,+128.415526] mm`.
- Repeat P1 raw FK origin: `[-60.481797,-227.134724,+114.947522] mm`.
- Repeat−P1 FK delta: `[+8.205547,+7.300467,−13.468003] mm`; XY norm `10.983070 mm`, XYZ norm `17.378577 mm`.
- tool rotation geodesic difference `6.363575°`. Wrist Roll은 거의 같아도 다른 관절과 tool orientation은 달랐다.
- 같은 physical table P1에서 raw FK가 17.38 mm 달라졌으므로 table transform fitting만 진행하지 않는다. 누락된 fixed TCP offset으로 설명 가능한지 pivot fit으로 먼저 검증한다. 아직 joint convention/URDF 오류로 확정하지 않는다.

## Pivot 준비

- 새 read-only 도구: `scripts/pivot_tcp_capture.py`.
- 15 fresh/unique broadcasts, 최신 age ≤400 ms, 모든 joint max std ≤0.01 rad 조건.
- Pose 1–8 각각 follower joints, `base→gripper` origin/rotation/RPY, 샘플 timestamp, 설치 URDF SHA 저장.
- 식 `p_fixed=t_i+R_i*tcp_offset`의 6변수 least-squares. 출력은 estimated offset XYZ/norm, fixed point, pose residual vector/norm, RMS/max, rank, condition number, singular values.
- targeted `test_pivot_tcp_capture` + 기존 `test_fit_fixed_point_tcp`: 10/10 PASS. 첫 py_compile에서 한글 bytes literal 오류 1건을 발견해 문자열 UTF-8 encode로 수정 후 재검사 통과.
- 로컬 `127.0.0.1:8034`, output `.local/c-red-pivot-tcp-20261011`; Pose 1–8 저장 완료. 각 캡처의 max joint std는 0–0.001073 rad로 capture gate 0.01 rad 이내다.
- 이 화면은 serial bus를 열거나 target/torque/motor command를 전송하지 않는다. LeLab/teleop은 사용자가 직접 관리한다.

## 8-pose 결과

- estimated `gripper`-frame TCP offset: `[-51.748354, -73.033741, -54.531737] mm`, norm `104.811879 mm`.
- estimated fixed point in `base`: `[32.443541, -300.313201, 45.010231] mm`.
- Pose 1–8 residual: `5.874750, 2.490713, 1.691086, 7.704719, 3.519684, 1.537657, 4.632405, 2.158856 mm`.
- RMS `4.239858 mm`, max `7.704719 mm`, rank 6, condition number `10.681415`. 수치 관측성은 양호하다.
- Pose 1–7만 fit한 offset은 `[-51.704695,-73.122927,-55.242910] mm`, norm `105.224128 mm`; fit RMS/max `4.444928/7.842364 mm`, Pose 8 hold-out `2.552316 mm`. Pose 8은 Pose 1과 orientation 차이가 2.590°로 가까워 강한 독립 방향 hold-out은 아니다.
- leave-one-out error Pose 1–8: `6.803,2.915,2.104,11.516,4.162,1.989,10.019,2.552 mm`; RMS/max `6.324/11.516 mm`. Pose 4와 Pose 7은 독립 재구성에서 10 mm를 넘으므로 최종 채택은 보류한다.
- 유사 orientation인 Pose 1↔8의 fitted TCP 위치 직접 차이는 `7.760 mm`로 single-digit다.

## 요청된 FK 경로 점검

- mapping은 `shoulder_pan→Rotation`, `shoulder_lift→Pitch`, `elbow_flex→Elbow`, `wrist_flex→Wrist_Pitch`, `wrist_roll→Wrist_Roll`이며 broadcast degree를 radian으로 한 번 변환한다. 로컬 pivot/FK 코드는 servo calibration을 다시 적용하지 않는다.
- 5축 sign 32조합을 같은 pivot 식으로 검사했다. 현재 mapping RMS `4.239858 mm`; 최저 조합은 Pan/Roll 동시 반전 RMS `4.235128 mm`로 개선이 0.005 mm뿐이라 sign 변경 근거가 아니다. 주요 lift/elbow/flex 반전은 RMS 9.27 mm 이상으로 악화했다.
- server 소스의 가정은 LeRobot calibrated degree zero와 URDF zero가 같다는 것이다. pivot 자료만으로 절대 zero를 독립 검증한 것은 아니다.
- 설치 SHA와 같은 URDF의 Wrist_Roll joint는 `wrist→gripper` origin `xyz=(0,-61.1,+18.1) mm`; 현재 `gripper` origin은 사용자의 오른쪽 강체점이 아니다. 104.8 mm offset의 물리적 타당성은 실물 치수/축 방향과 아직 대조하지 않았다.
- 현재 local FK에는 별도 static elbow/wrist teleop offset이 없고 calibration을 중복 적용하지 않는다. 현 Jetson 설치본의 `get_joint_positions_from_robot` exact source는 이번 fit 뒤 새로 읽지 않았으므로 설치본 수준의 중복 적용 여부는 `NOT_REVERIFIED`다.
- link length/mesh/tool origin의 실물 치수 검증도 `NOT_VERIFIED`. 따라서 fixed TCP offset이 66.9 mm table repeat 문제의 주원인이라는 증거는 강하지만 최종 model PASS는 아니다.

## 기존 5점에 pivot TCP 적용

- 새 5점 촬영 없이 `.local/c-red-five-point-roll-fixed-20261011` P1/P2/P3/P4/H1 및 별도 `.local/c-red-five-point-roll-fixed-20261011-repeat` P1 joint를 재사용했다.
- 각 점은 설치 SHA와 같은 URDF의 `base→gripper`에 pivot offset `[-51.748354,-73.033741,-54.531737] mm`를 `p_tcp=t+R*offset`으로 적용했다.
- corrected robot TCP XYZ mm:
  - P1 `[-136.972,-262.027,53.841]`
  - P2 `[115.352,-231.385,47.455]`
  - P3 `[145.225,-389.054,50.135]`
  - P4 `[71.777,-344.471,49.574]`
  - H1 `[-48.343,-309.220,44.417]`
  - Repeat P1 `[-131.241,-263.343,46.627]`
- Table X reflection `[-table_x,table_y]` 뒤 P1–P4만 rigid fit했다. residual은 P1 `18.589`, P2 `6.296`, P3 `12.515`, P4 `1.696 mm`; RMS `11.669 mm`, max `18.589 mm`다.
- H1 hold-out `5.660 mm`지만 Repeat P1 독립 transform error는 `24.926 mm`다. 사용자 판정 기준 `H1 single-digit + Repeat P1 ≥10 mm`에 해당하므로 **최종 PASS하지 않는다**.
- fitted reflected-table→robot rotation은 `[[0.973779,-0.227495],[0.227495,0.973779]]` (`+13.149650°`), translation `[277.165073,-583.651305] mm`. 원래 table 좌표에 X reflection까지 합친 homogeneous transform은 `[[-0.973779,-0.227495,277.165073],[-0.227495,0.973779,-583.651305],[0,0,1]]`, determinant `−1`이다.
- corrected P1↔Repeat P1의 직접 TCP XY 거리는 `5.879 mm`다. 즉 pivot offset은 같은 physical P1의 robot-side 재현성을 크게 개선했지만, 기존 P1–P4 correspondence 전체가 하나의 accurate reflected rigid transform에 놓이지 않는다. H1의 낮은 값만으로 통과시키지 않는다.
- 교차검사: zero offset은 기존 RMS `35.399`, H1 `26.134`, Repeat `66.925 mm`를 재현해 계산 convention이 기존 결과와 일치했다. swap/flip 동치 조합도 같은 최솟값이고 비반사 조합은 훨씬 나빠 Table X reflection 선택 오류가 아니다.
- 8개 pivot leave-one-out offset 각각으로 다시 계산해도 five-point RMS `11.349–14.508 mm`, Repeat P1 `24.368–29.793 mm`다. 따라서 2–4 pivot pose 추가는 offset 안정성 향상에는 쓸 수 있지만 기존 five-point transform 실패를 single-digit으로 만들 가능성은 낮다.
- 파생 결과: `.local/c-red-five-point-roll-fixed-20261011/pivot_tcp_reflected_fit.json`. live C/IK/자동 motion `NOT_RUN`.

## 다음 판정

1. 추정 offset norm 약 104.8 mm와 방향 `[-X,-Y,-Z]`가 실제 `gripper` frame origin에서 오른쪽 강체점까지의 치수/방향과 맞는지 확인한다.
2. 기존 five-point의 P1/P3 대응 및 동일 physical point/hover 유지 자료를 검토한다. 현재 fit에서 두 점이 큰 residual이다.
3. 재측정한다면 pivot 추가보다 기존 세트와 섞지 않는 새 five-point correspondence 세트가 직접적인 해소 경로다. 단, 사용자 승인 전 재촬영하지 않는다.
4. 그 전까지 live C/IK/자동 motion은 `NOT_RUN`.

## 새 7점 세션 시작

- 사용자가 기존 세트를 보존하되 최종 calibration에서 제외하고, pivot offset을 고정한 새 세트를 요청했다.
- session ID `pivot-tcp-table-20261011-s01`, output `.local/c-red-pivot-tcp-table-20261011-s01`, 순서 `P1,P2,P3,P4,H1,Repeat_P1,Repeat_P3`.
- 기존 `registered_P1/P2/P3/P4/H1.json`의 table XY와 SHA만 manifest에 복사했다. table mark 재클릭/재정의 API가 없고 `prior_capture_imported=false`다.
- table marks mm: P1 `[347.334,416.563]`, P2 `[71.183,380.616]`, P3 `[75.505,210.519]`, P4 `[143.895,279.583]`, H1 `[258.121,345.645]`.
- TCP offset `[-51.748354,-73.033741,-54.531737] mm`, URDF SHA `443d38d…f67236` 고정. 각 capture는 15 fresh joint samples, max std ≤0.01 rad, 사용자 mark/정지/hover 확인을 요구하고 corrected physical TCP XYZ를 즉시 반환한다.
- 로컬 8034에서 joint age 87.3 ms/error 없음 확인. LeLab/teleop/USB/motor/torque 변경 없음. targeted tests 7/7 PASS.

## 새 7점 결과

- 7/7 완료. corrected TCP XYZ mm:
  - P1 `[-137.103,-262.487,54.659]`
  - P2 `[119.178,-231.607,50.504]`
  - P3 `[145.571,-387.546,50.249]`
  - P4 `[73.891,-346.931,48.528]`
  - H1 `[-47.789,-312.441,44.928]`
  - Repeat P1 `[-129.318,-266.553,47.584]`
  - Repeat P3 `[151.009,-387.833,49.252]`
- Table X reflection rigid fit(P1–P4 only): residual P1 `17.668`, P2 `4.164`, P3 `14.863`, P4 `2.606 mm`; RMS/max `11.802/17.668 mm`.
- 독립 검증: H1 `6.771 mm`; Repeat P1 직접 TCP XY `8.783 mm`, transform prediction `26.310 mm`; Repeat P3 직접 TCP XY `5.446 mm`, transform prediction `10.708 mm`.
- transform은 reflected-table rotation `+13.232333°`, translation `[279.293851,-583.914187] mm`; original table X reflection까지 합친 homogeneous matrix `[[-0.973450,-0.228900,279.293851],[-0.228900,0.973450,-583.914187],[0,0,1]]`.
- repeat 직접 재현성과 H1은 single-digit이지만 fit 자체와 repeat transformed prediction은 통과하지 못해 status `REJECTED_FIT_OR_REPEAT`. live C/IK `NOT_RUN`.
- rigid transform과 무관한 pairwise 거리도 P1–P2/P1–P3/P1–P4/P2–P3/P2–P4/P3–P4에서 robot−table `−20.346/−31.991/−17.992/−11.995/−0.581/−14.809 mm`; 동일 metric geometry가 아니다.
- 원인 분리용 similarity fit은 scale `0.9201295`, fit RMS/max `4.064/5.279 mm`, H1 `7.578`, Repeat P1/P3 transformed error `9.728/2.367 mm`로 급개선했다. 이는 약 8% scale 불일치의 증거지만 사용자가 요청한 rigid transform이 아니므로 calibration으로 채택하지 않았다. table homography/mark metric scale 또는 URDF/link metric scale을 확인해야 한다.
- 결과 파일 `.local/c-red-pivot-tcp-table-20261011-s01/reflected_table_robot_fit.json`; 기존 세트와 섞지 않았다. live C/IK/자동 motion `NOT_RUN`.

## Metric scale 1회 실측 대기

- 추가 5점 촬영은 중단했다. 가장 먼 P1↔P3 mark를 scale 판별쌍으로 선택했다.
- P1/P3 table XY는 `[347.334,416.563]` / `[75.505,210.519] mm`; table distance `341.094 mm`.
- corrected robot TCP XY는 `[-137.103,-262.487]` / `[145.571,-387.546] mm`; robot distance `309.103 mm`.
- similarity scale `0.9201295` 적용 table distance는 `313.851 mm`; robot/table 직접 비율은 `0.906210`.
- 사용자에게 실제 P1/P3 mark 중심간 물리 거리 한 번만 요청했다. 실측 전 table homography scale과 FK/link scale 중 어느 쪽도 수정하지 않는다. live C/IK/자동 motion `NOT_RUN`.

## P1↔P3 실측 및 table metric scale 보정

- 사용자가 P1↔P3 mark 중심간 실제 물리 거리를 **약 305 mm**로 측정했다. 이는 corrected robot TCP 거리 `309.103 mm`와 `4.103 mm` 차이이고, 기존 table 거리 `341.094 mm`와는 `36.094 mm` 차이다. 따라서 남은 uniform scale mismatch는 robot FK/link scale보다 table/ArUco homography metric scale 오류로 판정했다.
- 실측 기반 table scale은 `305 / 341.094026886 = 0.8941815921`이다. corrected table XY는 P1 `[310.580,372.483]`, P2 `[63.651,340.340]`, P3 `[67.515,188.242]`, P4 `[128.668,249.998]`, H1 `[230.807,309.069] mm`다.
- 위 scale과 Table X reflection을 적용하고 새 robot capture 없이 기존 session 7점만 재계산했다. P1–P4 rigid-fit residual은 `4.623/7.435/0.989/6.347 mm`, RMS/max `5.429/7.435 mm`다. H1 hold-out `9.458 mm`; Repeat P1 direct/transform `8.783/4.694 mm`; Repeat P3 direct/transform `5.446/4.853 mm`로 모두 single-digit다.
- reflected scaled-table→robot rotation은 `+13.232333°`, translation `[255.070981,-554.626715] mm`다. 원래 uncorrected table XY를 robot XY로 보내는 combined homogeneous matrix는 `[[-0.870440970,-0.204678377,255.070981],[-0.204678377,0.870440970,-554.626715],[0,0,1]]`이다.
- 결과 `.local/c-red-pivot-tcp-table-20261011-s01/scale_corrected_reflected_table_robot_fit.json`. 기준상 채택 **후보**지만, 실측이 “약 305 mm” 한 번이므로 자동 motion 승인으로 승격하지 않는다. `robot_enabled=false`, `motion_authorized=false` 유지.
- 다음은 read-only `live C → original table XY → scale-corrected table XY → robot XY → IK dry-run`. 실제 automatic motion은 계속 `NOT_RUN`.

## Camera bridge 복구 및 live C IK

- 8000/8002 camera HTTP 503에서 Astra USB와 `/dev/video8`은 존재했지만 기존 bridge에는 OpenNI source만 남고 GStreamer `/dev/video8` sink가 사라져 있었다. teleop/recording/inference OFF 확인 후 사용자가 system `astra-v4l2-bridge.service`만 재시작했다. LeLab/teleop/USB motor port/calibration은 변경하지 않았다.
- 복구된 8000 최신 frame SHA `31481ca0…fbd15`에서 ArUco ID0–3과 YOLO C 1개를 검출했다. confidence `0.772715`, center `[323.185,238.947] px`, raw table `[280.758,362.006] mm`, scale-corrected table `[251.049,323.699] mm`, candidate robot XY `[-63.407,-296.987] mm`.
- candidate Z pre-approach/approach/grasp/lift `100/80/50/100 mm` 위치 IK residual `0.003/0.006/0.450/0.003 mm`; servo calibration 후보 범위와 2° bounded interpolation 수치 검사는 PASS. 방향과 collision/swept path는 미검증이다.
- teleop OFF라 fresh `/ws/joint-data` 표본이 없고 read-only `/joint-positions`도 active teleop 없음으로 반환됐다. 따라서 현재 follower delta는 `PENDING`; 기록된 delta는 마지막 Repeat P3 capture 기준이며 실제 현재값으로 주장하지 않는다. 실제 approach/grasp/lift `NOT_RUN`, `motion_authorized=false`.
- 사용자가 직접 `relative_start` teleop을 켠 뒤 10개 fresh broadcast를 읽었다. mean follower는 `(Pan +5.618, Lift −29.820, Elbow +31.121, Flex +48.835, Roll −15.429)°`, 표본 최대 std `0.132°`다. 이 seed의 pre/approach/grasp/lift 위치 IK residual은 `0.095/0.024/0.671/0.004 mm`, servo candidate range PASS다. 현재→pre-approach 및 이후 3구간의 ≤2° interpolation은 `21/3/5/8` step으로 finite/range PASS. numerical dry-run은 PASS; orientation, collision/swept path, Z 실측은 여전히 미검증이다. 실제 모터 명령 0, approach/grasp/lift `NOT_RUN`, 사용자 승인 전 `motion_authorized=false`.

## C pre-approach 실행 실패와 follower HOLD 정정

- 사용자 승인 범위 `live_c_pre_approach_only`로 실제 pre-approach를 시도했다. 첫 실행은 transport `ValueError`, 다음 실행은 `joint_target_timeout`, transport/진단 출력을 보강한 최신 실행도 `joint_target_timeout`으로 중단됐다. 최신 마지막 오차는 `shoulder_pan +0.015°, shoulder_lift -1.038°, elbow_flex +2.830°, wrist_flex +0.404°, wrist_roll -0.458°, gripper +0.000`이다. 사용자가 팔 정지를 확인한 뒤에도 C approach/grasp/lift는 완료로 처리하지 않았고 재시작 `NOT_RUN/NOT_AUTHORIZED`다.
- timeout 후 첫 개별 진단에서 Present/Goal calibrated는 대체로 근접했으며 torque 6축이 `1`이었다. 뒤이어 group `sync_read`가 `Incorrect status packet`을 냈고, 별도 group read에서 전 축 `Goal_Position=0`, `Torque_Enable=0`이 반환됐다. 이 값으로 torque OFF와 중력 drift를 추정했으나, 이후 신뢰 가능한 축별 개별 read가 전 축 torque `1`과 현재 근처 goal을 일관되게 반환해 **그 group 0 결과와 torque-OFF 판정은 폐기**한다.
- 최종 read-only raw 표:

| joint | Present_Position | Goal_Position | Torque_Enable | Moving | Present_Load |
|---|---:|---:|---:|---:|---:|
| shoulder_pan | 1977 | 1979 | 1 | 0 | -20 |
| shoulder_lift | 861 | 871 | 1 | 0 | -52 |
| elbow_flex | 3090 | 3094 | 1 | 0 | 24 |
| wrist_flex | 2729 | 2730 | 1 | 0 | 0 |
| wrist_roll | 1655 | 1654 | 1 | 0 | 0 |
| gripper | 445 | 445 | 1 | 0 | 0 |

## Load-relieved pre-approach IK dry-run

- Fixed C robot XY, TCP, table transform, vision result, grasp point, tolerance, and installed URDF. Fresh follower read-only pose was `[-9.538,-94.725,+87.956,+71.956,-15.165] degrees`; no Goal/torque write occurred.
- Same-XY Z candidates `100/110/120/130/140/150 mm` all passed numeric position IK. Elbow solutions were `42.003/42.899/43.233/43.893/43.739/43.492 degrees`, residuals all below `0.60 mm`, and minimum servo-calibration margins all above `53.1 degrees`. Small XY adjustment was unnecessary.
- Selected candidate A: XYZ `[-62.635354,-295.315566,100.0] mm`; joints `[+5.041,+2.879,+42.003,+16.184,+84.083] degrees`; fresh-current delta `[+14.579,+97.605,-45.953,-55.772,+99.248] degrees`. Selection reason is zero Cartesian change while satisfying Elbow <=85 and retaining 55-degree minimum servo margin.
- The observed 89.927-degree failure target was an early transition waypoint, not the old endpoint IK (14.866 degrees). Candidate A is an alternative IK branch with smaller Elbow excursion; it does not yet prove physical tracking. Actual test `NOT_RUN/NOT_AUTHORIZED`, tolerance unchanged at 1.6 degrees, grasp/lift `NOT_RUN`.
- Result: `.local/c-red-pivot-tcp-table-20261011-s01/elbow_load_relief_ik_candidates_20261011.json`; changes `NOT_COMMITTED/NOT_PUSHED`.

## Current-near load-relieved IK branch search

- Candidate A 실기는 시작하지 않았다. follower port, Goal_Position, Torque_Enable에 접근하지 않고 로컬 FK/IK dry-run만 수행했다.
- Fresh current `[-9.538,-94.725,+87.956,+71.956,-15.165]°`에서 같은 XYZ의 position-only 1,712 multi-start 결과 max delta `40°` 이하 해는 없었다. 가장 가까운 해의 max/L2도 `94.759/153.970°`였고 reference tool-axis error가 `36.546°`였다. Candidate A의 tool-axis error도 `21.984°`이므로 본 orientation-preserving 비교에서 제외했다.
- Reference pre-approach FK의 gripper local-Z `[-0.0001997,0.7737667,0.6334706]`를 유지하고 그 축 주위 roll은 자유로 둔 2,408-start multi-start를 Z `100/110/120/130 mm`에서 수행했다. 각 Z에서 서로 다른 2개 branch를 확인했지만, 최선 max delta는 순서대로 `105.536/101.290/97.348/93.751°`였다.
- `BEST_CURRENT_NEAR_IK=Z130`: XYZ `[-62.635354,-295.315566,130.0] mm`, q `[-0.014219,-0.974479,+41.753632,-1.472144,+56.753749]°`, current delta `[+9.524242,+93.750796,-46.202412,-73.428188,+71.918584]°`, max/L2 `93.750796/146.896451°`, Cartesian residual `<0.001 mm`, tool-axis error `0.000°`, servo margin `55.257°`. Candidate A보다 max/L2가 작고 orientation을 보존하지만 요청한 max `30–40°` current-near 조건은 불충족이다.
- 실제 pre-approach/grasp/lift는 `NOT_RUN/NOT_AUTHORIZED`; tolerance/path/vision/TCP/calibration은 변경하지 않았다. Result: `.local/c-red-pivot-tcp-table-20261011-s01/current_near_load_relief_ik_search_20261011.json`; changes `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-17 final-system scope lock

- 최종 목표는 `A/B/C × RED/GREEN/BLUE` 9조합 자동 pick-and-place이며 `C→RED`는 첫 end-to-end validation case로만 사용한다.
- 생산 구조는 `detect/select → object robot XY → generic PICK(object_xy) → basket select → basket robot XY → generic PLACE(basket_xy)`로 고정했다. identity를 motion 함수 내의 관절값/경로 분기로 사용하지 않는다.
- 현재 `live_c_approach.py`, `prepare_c_red_phases.py`, `c_red_*`는 검증 하네스/과거 후보이며 최종 planner API가 아니다. 현재 코드 점검에서 9조합 명령 파서와 identity 비의존 stage executor는 이미 존재하지만 generic PICK/PLACE plan schema와 basket pose 연결은 아직 `NOT_IMPLEMENTED/NOT_RUN`이다.
- 단기 실기 목표는 계속 C→RED 1회 성공이며 성공 전에 A/B/다른 바구니로 분산하지 않는다. 문서: `docs/medicine-pick-place-target-20261017.md`. 이 수정 중 모터/Goal/Torque/teleop/service 변경은 0회; `NOT_COMMITTED/NOT_PUSHED`.

## C pre-approach bounded continuous-following readiness

- 기존 C XY/IK endpoint/calibration/final `1.6°` tolerance를 그대로 두고 중간 실행만 `1.0°` bounded continuous-following으로 분리했다. 0.2초 cadence 이전 추가 send를 금지하고, Elbow/other arm `4.0/2.5°` envelope 안이면 다음 target, 초과하면 no-send PAUSE, 회복 시 RESUME한다. 3회 연속 증가·1.0초 no-progress·feedback 오류·경로 step 위반은 ABORT한다.
- `scripts/continuous_following_execution.py`를 추가하고 `SO101FollowerTransport.read_following_telemetry()`로 Goal/Present raw, Moving, Present_Load, calibrated feedback을 신규 명령 없이 읽도록 했다. runner는 실기 continuous mode에서 새 JSONL output을 필수로 하고 event를 매번 flush하며 성공 시만 `PRE_APPROACH_PASS`를 출력한다. 기존 stop-and-wait 경로는 보존했다.
- fake-bus에서 2–3° lag 연속, Elbow >4° PAUSE, 회복 RESUME, no-progress/increasing/communication 오류 ABORT, final 1.6° fail, abnormal step reject, PAUSE/ABORT send 0, 실제 107-waypoint 전체 순서를 확인했다. 관련 36/36 tests·py_compile·diff-check PASS. 최초 전체 경로 test 1건은 float exact-equality 때문에 실패했고 근사 비교로 수정 후 통과했다.
- Jetson `/tmp/live-c-approach-20261011` 임시 배포본의 SHA를 로컬과 대조했고 설치 Python py_compile/dry-run을 통과했다. teleop/recording/inference inactive, 관련 worker 없음. read-only follower 3표본은 `[-9.538462,-94.725275,+87.956044,+71.956044,-15.076923]°`, gripper `1.958384`로 정지했고 motor/Goal/torque write 0회, 종료 후 follower port 무점유다.
- 실제 pre-approach는 `NOT_RUN/NOT_AUTHORIZED`; grasp/lift는 계속 금지. 다음 gate는 사용자의 현장 비접촉 확인과 pre-approach 1회 명시 승인이다. changes `NOT_COMMITTED/NOT_PUSHED`.

## Elbow raw tracking diagnostic result

- `ROOT_CAUSE`: Elbow reaches a load-dependent stationary tracking offset (deadband/holding equilibrium). This is not a Goal write, degree/raw conversion, calibration, or settle-time failure.
- The unchanged 1.6-degree pre-approach trial started from `[-7.429,-86.813,+93.055,+52.967,-16.044] degrees`, planned 55 waypoints, and timed out at actually transmitted waypoint 2. Grasp/lift were not started; no automatic retry occurred.
- Waypoint raw rows: index 1 target/readback/present `3024/3024/3042`, error `+1.564 degrees`, Moving `0`, Load `44`; index 2 `3006/3006/3041`, error `+3.040 degrees`, Moving `1`, Load `188`.
- The final read-only settle window contained 21 samples over 3.0 seconds. Goal remained `3006`; Present was `3038` for 11 samples then `3037` for 10. Residual was `-32` then `-31` raw, error `+2.776` then `+2.688 degrees`, Moving was always `0`, and Load was `140` then `136`. This is a plateau rather than meaningful continued convergence.
- User `STOPPED` and fresh feedback confirmed `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. Post-run teleop/recording/inference inactive; no related process; follower unowned (`fuser rc=1`). Report: `.local/c-red-pivot-tcp-table-20261011-s01/elbow-final-tracking-diagnostic-20261011-r2.json`.
- Tolerance/path/IK/vision/TCP/calibration unchanged. Corrective motion is `NOT_RUN/NOT_AUTHORIZED`; changes `NOT_COMMITTED/NOT_PUSHED`.

- Goal−Present raw는 `+2/+10/+4/+1/−1/0`; 1초 10표본 동안 Present raw span은 전 축 `0`, Moving은 전 축 `0`이다. 그러므로 현재는 **6축 모두 torque ON, goal≈present, 실제 stationary HOLD**다. `recover_follower_hold.py`의 `torque_not_all_off_before_recovery`는 특정 한 축이 아니라 현재 전 6축 값 `1` 때문에 발생했다. 검사는 함수 첫 줄의 torque read 직후라 이번 중단 전에 Goal write, `enable_torque()`, `disable_torque()`는 호출되지 않았다. 재실행하지 않는다.
- read-only API에서 teleop/recording/inference 모두 inactive였다. live approach/recovery/replay/teleoperate 실행 프로세스 없음, LeLab PID의 fd에는 `/dev/ttyACM1` 없음, privileged `fuser`는 진단 종료 후 무점유(`rc=1`)였다. 즉 LeLab 서비스의 robot object가 follower serial connection을 계속 소유해 torque를 유지하는 상태가 아니다. 포트가 닫혀도 servo register의 torque와 goal은 남아 독립적으로 hold할 수 있다.
- 설치 코드 경로:
  - `SO101Follower.connect()`는 `configure()`를 호출하고, `configure()`의 `with bus.torque_disabled()`는 설정 중 `disable_torque()`, finally에서 `enable_torque()`를 실행한다. 따라서 정상 연결/configure가 torque를 ON으로 만든다.
  - LeLab `teleoperate.py`는 follower config에 `disable_torque_on_disconnect=False`를 사용한다. 종료는 `_safe_disconnect→safe_disconnect_device→SO101Follower.disconnect()→bus.disconnect(False)`이며 serial port만 닫고 torque를 끄지 않는다.
  - directional `HOLD`는 `temporary_elbow_direction_guard.py`의 `guarded_elbow_send()`에서 `decision.action == "HOLD"`이면 바로 `return None`이다. 새 Goal을 쓰거나 torque를 변경하지 않고 `send_action`을 생략하므로, servo가 기존 last goal을 유지한다.
  - `live_c_approach.py`와 `so101_follower_transport.py`도 종료에서 명시적으로 `disconnect(disable_torque=False)`를 사용한다. `recover_follower_hold.py`에만 승인 복구용 enable/실패 rollback disable 경로가 있으나 이번에는 그 앞에서 중단됐다.
- 상태 확인 동안 service restart, torque 변경, Goal write, motor command는 수행하지 않았다. 비밀번호나 인증정보는 파일/로그/Git에 기록하지 않았다. 관련 로컬 변경과 문서는 `NOT_COMMITTED/NOT_PUSHED`다.

## HOLD 확인 뒤 live C vision/IK dry-run 복귀

- 8000 health는 정상이고 `/camera-preview/8` MJPEG를 8초 동안 약 9.3 MB, 240개 완전 JPEG로 연속 수신했다. 카메라가 살아 있어 camera bridge나 LeLab service를 재시작하지 않았다.
- 가장 최신 완전 frame SHA `9c4eb1fd…f867e3`에서 ArUco ID0–3 모두 검출, table homography ready, 기준점 reprojection RMS `0.000004 mm`였다. YOLO C는 confidence `0.797704`, bbox center `[323.432,241.028] px`; nearest-slot C 거리 `37.093 mm`, runner-up gap `66.308 mm`로 `PROVISIONAL_SLOT_MATCH`다.
- C raw table XY `[279.490,363.628] mm`에 scale `0.8941815921`를 적용한 corrected XY는 `[249.914813,325.149464] mm`, Table X reflection은 `[−249.914813,325.149464] mm`, candidate transform 결과 robot XY는 `[−62.635354,−295.315566] mm`다.
- latest confirmed read-only follower 5축은 `Rotation −10.945055°, Pitch −96.131868°, Elbow +97.274725°, Wrist_Pitch +57.010989°, Wrist_Roll −18.417582°`다. 이 표본 뒤 motor/Goal/torque change가 없었다. no-torque-change 범위를 유지하기 위해 이번 vision 계산 중 follower bus를 다시 열지 않았다.
- candidate Z pre-approach/approach/grasp/lift `100/80/50/100 mm`의 위치 IK:
  - pre-approach `[-0.014220,+11.507515,+14.866481,+12.933013,+13.899293]°`, residual `0.012960 mm`
  - approach `[-0.096486,+17.400979,+14.407074,+10.648771,+14.577178]°`, residual `0.023209 mm`
  - grasp `[-0.230992,+26.760294,+13.182270,+6.261467,+15.755456]°`, residual `0.676696 mm`
  - lift `[-0.030915,+11.785466,+13.796035,+14.812512,+14.012906]°`, residual `0.567544 mm`
- 네 IK target 모두 finite이고 servo candidate range 안이다. 이는 **position-only numeric dry-run PASS**이며 orientation, collision/swept path, Z physical height 검증은 아니다. 실제 motor motion은 `NOT_RUN`, `robot_enabled=false`, `motion_authorized=false`. 결과 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_vision_ik_dry_run_current.json`; 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 최신 C pre-approach 실기 시도 — timeout 중단

- 새 계획 `configs/live_c_approach_candidate_20261011_current.json`은 frame SHA `9c4eb1fd…f867e3`, C robot XYZ `[−62.635354,−295.315566,100.0] mm`, target arm `[-0.014220,+11.507515,+14.866481,+12.933013,+13.899293]°`를 고정한다. 로컬 py_compile, targeted discover tests `4/4 + 10/10`, local/Jetson dry-run을 통과했다. 첫 unittest module-name 호출은 tests package import 오류 2건으로 실행되지 않았고 discover 방식으로 바로잡았다. Jetson script/config SHA는 로컬과 일치했다.
- 사용자가 실제 pre-approach와 `RUN LIVE C APPROACH`를 명시 승인했다. teleop/recording/inference inactive에서 fresh start `(Pan −10.945055, Lift −96.131868, Elbow +97.274725, Flex +57.010989, Roll −18.417582, Gripper 1.958384)`를 읽고 gripper hold, 최대 2°의 54 waypoint 실행을 시작했다.
- 실행은 `joint_target_timeout`으로 중단됐다. 마지막 feedback−goal은 `Pan −0.317°, Lift −0.910°, Elbow +1.733°, Flex +0.226°, Roll −0.406°, Gripper +0.000`; arm reach tolerance `1.6°`를 Elbow만 `0.133°` 초과했다. 따라서 pre-approach `NOT_REACHED`, grasp/lift `NOT_STARTED`; 성공으로 승격하지 않는다.
- 추가 command production을 stop한 뒤 사용자가 현장 정지·안전을 `STOPPED`로 확인했고, fresh feedback window도 통과해 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`였다. 종료 후 teleop/recording/inference inactive, 접근/recovery/replay/teleoperate 프로세스 없음, `lsof /dev/ttyACM1` 무점유(`rc=1`). torque disable/recovery/service restart는 수행하지 않았다.
- 결과 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_attempt_current.json`. 동일 조건 자동 재시도나 tolerance/timeout 변경은 `NOT_RUN/NOT_AUTHORIZED`; 변경 `NOT_COMMITTED/NOT_PUSHED`.

Git 상태: `NOT_COMMITTED/NOT_PUSHED`.

## fresh5 delayed-Wrist coupled path dry-run

- BALANCED_COUPLED 종료 자세를 read-only viewer로 다시 읽었다. follower raw/degree는 Pan `2019/-7.252747`, Lift `1511/-38.989011`, Elbow `2635/+57.274725`, Flex `2863/+68.791209`, Roll `1778/-7.604396`, Gripper `449/2.203182`; motor write와 torque change는 각각 0회였고 `ports_released=True`, privileged follower `fuser rc=1`이다.
- fresh pivot TCP FK `[-37.324727,-86.997920,98.216701] mm`, C까지 XY `209.849636 mm`다. 이전 실행 feedback FK/C 잔여와 약 9.5 mm 차이는 종료 뒤 fresh servo settle/drift를 다시 읽은 결과이며 이 값을 새 start gate로 사용한다.
- Shoulder–Elbow/Pan/Roll은 기존 balanced anchor→endpoint 선형 coupling을 유지한다. Wrist만 delay `25/35/45%`까지 fresh `68.791209°`를 유지하고 coupled progress rate를 기존의 `0.75`로 낮춰 각 coupled waypoint Wrist step을 최대 `0.791801°`로 제한한다. 다른 joints가 endpoint에 도달한 뒤 남은 Wrist를 exact endpoint `12.933013°`로 마무리한다.
- 후보 비교:
  - `WRIST_DELAY_25`: 71 targets, max joint step `0.991765°`, min TCP Z `83.656690 mm`, final Wrist-only `17.851766°`, C residual schedule `198.064→142.954→86.738→33.513→0.010 mm`.
  - `WRIST_DELAY_35`: 77 targets, max joint step `0.996491°`, min TCP Z `80.992573 mm`, final Wrist-only `22.919290°`, C residual `198.064→186.739(delay 35%)→153.610→97.476→43.798→0.010 mm`.
  - `WRIST_DELAY_45`: 82 targets, max joint step `0.999529°`, min TCP Z `79.247340 mm`, final Wrist-only `27.986814°`, C residual `198.064→175.063(delay 45%)→164.038→108.209→54.278→0.010 mm`.
- 35/45% 후보의 첫 구현은 delay 지점이 명시 waypoint가 아니어서 stage 사이 선형 보간이 25% 직후 Wrist를 줄이는 결함이 있었다. 실제 실행 전 발견해 각 delay fraction을 schedule에 삽입했고, 해당 지점 존재·그 지점까지 Wrist 고정·balanced Shoulder/Elbow geometry 보존을 테스트했다. 선택된 25% config는 원래 25% stage를 이미 포함하므로 배포값/SHA/waypoint 수에 변화가 없다.
- 전 후보는 dense FK상 C distance 단조 감소, servo range, max step, endpoint exact를 통과했다. 가장 작은 delay/final Wrist-only 변화이면서 min Z가 가장 높은 `WRIST_DELAY_25`를 선택했다.
- 선택 schedule `(Lift, Elbow, Wrist; TCP XYZ; C XY residual)`:
  - fresh `(-38.989,57.275,68.791; [-37.325,-86.998,98.217]; 209.850)`
  - waypoint 5 / coupled 25% `(-34.623,52.390,68.791; [-39.281,-98.634,102.494]; 198.064)`
  - waypoint 21 / 50% `(-19.246,39.882,56.122; [-43.833,-153.604,97.833]; 142.954)`
  - waypoint 37 / 75% `(-3.869,27.374,43.454; [-51.612,-209.280,91.501]; 86.738)`
  - waypoint 53 / coupled 100% `(+11.508,14.866,30.785; [-62.652,-261.802,83.657]; 33.513)`
  - waypoint 71 / existing endpoint `(+11.508,14.866,12.933; [-62.643,-295.322,99.992]; 0.010)`
- 새 planner tests 4개, 기존 coupled 3개, runner 13개, continuous 8개, staged planner 5개, FK 3개 총 `36/36 PASS`; py_compile, diff-check, local dry-run PASS. config `configs/live_c_approach_candidate_20261011_delayed_wrist_fresh5.json`을 Jetson 임시 폴더에 배포했다. local/Jetson SHA `e6763906c93f70784e6b7eef1d48ab481c76bf114124c7f9a91736382ca89e69`, unchanged runner SHA `1c81214bda770fa2890f12c1488eb1b90988ca2bec669bc0f8e78bfe792edc71`.
- Jetson 설치 Python py_compile과 dry-run `DRY_RUN: no port opened; no send_action` PASS. teleop/recording/inference inactive, 관련 제어 worker 없음, follower 무점유 `FUSER_RC=1`이다.
- 기존 C XY/endpoint/calibration/tolerance/following limits/Shoulder–Elbow coupling은 변경하지 않았다. calibration/alternate IK/tolerance/feed-forward/gain/torque도 변경하지 않았다. swept-link/environment collision은 `NOT_VERIFIED`; 실제 pre-approach `NOT_RUN/NOT_AUTHORIZED`, grasp/lift `NOT_RUN`, `NOT_COMMITTED/NOT_PUSHED`.

## WRIST_DELAY_25 승인 실기 — PRE_APPROACH_PASS 후 야간 freeze

- 사용자의 `RUN LIVE C APPROACH` 승인 뒤 SHA/세 제어 비활성/follower 무점유 gate를 통과했다. fresh start는 config reference `[-7.252747,-38.989011,+57.274725,+68.791209,-7.604396]°`, gripper `2.203182`와 정확히 일치했다.
- 71/71 target을 완료했다. final feedback은 `[-0.483516,+12.175824,+16.043956,+14.197802,+13.758242]°`, final feedback−goal은 `[-0.469296,+0.668309,+1.177475,+1.264789,-0.141051]°`, gripper delta `-0.183599 pp`; 기존 final arm tolerance `1.6°`를 모두 통과했다.
- 사용자가 TCP가 C 위에 있고 현장이 안전하다고 `APPROACH CONFIRMED`를 입력했고 실행기가 `APPROACH_REACHED waypoints=71` 및 `PRE_APPROACH_PASS`를 출력했다. grasp/lift는 `NOT_RUN`이다.
- 이후 종료의 `STOPPED` prompt를 기다리는 동안 사용자가 퇴근·무인 야간 모드를 지시했다. 현장 부재 상태에서 `STOPPED`를 거짓 확인하지 않고 `UNATTENDED_NOT_VERIFIED`를 입력해 `physical_stop=NOT_VERIFIED`, exit 1로 fail-closed 종료했다. pre-approach 도달/tolerance PASS와 최종 현장 정지 확인 상태를 분리해 기록한다.
- post-run read-only API는 teleop/recording/inference inactive, 관련 worker 없음, follower port 무점유 `FUSER_RC=1`이었다. 로그는 72행이며 마지막 waypoint Goal/Present raw Elbow `2152/2166`, Wrist `2227/2242`, error `1.177/1.265°`, Moving `0/0`, load `68/72`다.
- 원본 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_delayed_wrist_fresh5_attempt1.jsonl`. 첨부된 야간 계획의 “PRE_APPROACH_PASS 아님/실기 NOT_RUN”은 작성 시점이 실행 전이므로 이 실제 증거가 최신 상태로 우선한다.
- 이 시점 이후 hardware freeze: motor send, Goal/Torque, teleop/replay/live, service restart, USB write, calibration capture, camera/robot reposition 전부 금지. 야간 작업은 로컬 로그/코드/fake test/dry-run/문서에 한정한다. `NOT_COMMITTED/NOT_PUSHED`.

## BALANCED_COUPLED pre-approach 실기 결과

- approved pre-approach 1회. fresh start `[-8.571429,-49.714286,+64.043956,+82.769231,-11.736264]°`, 71 targets 중 waypoint 15까지 송신. grasp/lift `NOT_RUN`.
- anchor waypoint 3에서 Elbow error/load `0.025°/0`, Wrist Flex error/load `0.335°/28`. 이후 coupled final에서 Shoulder Lift는 정상 추종했고, Elbow error/load는 waypoint 4→15에서 `0.761/48 → 3.316/164`로 증가했지만 4° limit 안이었다.
- Wrist Flex error/load가 `0.274/28 → 2.676/136`으로 먼저 증가했다. waypoint 15 target joints `[-7.061333,-39.145732,+56.068875,+68.576414,-7.139943]°`; Wrist target/feedback `68.576414/71.252747°`, error `2.676333°`, load `136`, Moving `0` 때문에 2.5° envelope PAUSE.
- 1.008초 뒤 Wrist feedback `71.076923°`, error `2.500509°`, load `128`; Elbow error/load `3.227828°/160`. Wrist가 limit를 `0.000509°` 초과한 채 no-progress timeout ABORT.
- target TCP/C residual `[-37.487490,-91.212606,99.750623] / 205.646379 mm`; feedback TCP/C residual `[-38.337528,-77.354694,98.175790] / 219.311026 mm`. C 방향으로 실제 전진했으나 endpoint 미도달.
- root of this run: coupled Shoulder/Elbow path itself was not the first envelope failure; linearly coupled Wrist Flex reduction became the new bottleneck. Next single path variable is delaying Wrist Flex reduction while retaining Shoulder/Elbow coupling. No tolerance/feed-forward/gain/calibration/vision changes.
- user `STOPPED`, physical stop confirmed; three controls inactive, related workers absent, follower unowned `fuser rc=1`. No auto retry, no grasp/lift. Original `live_c_pre_approach_coupled_final_fresh4_attempt1.jsonl`; `NOT_COMMITTED/NOT_PUSHED`.

## fresh4 coupled-final path dry-run

- latest read-only follower `[-8.571429,-49.714286,+64.043956,+82.769231,-11.736264]°`; motor write/torque change 0, ports released. Empirically safe waypoint-29 target `[-8.571429,-50,+64.897959,+80.5,-11.648352]°`를 anchor로 사용했다.
- coupled candidates는 anchor→endpoint의 Pan/Lift/Flex/Roll을 25/50/75%로 보간하고 Elbow progress를 Lift progress의 exponent `1.0/1.15/1.3/1.5`로 늦춘다. 따라서 어떤 후보도 Elbow가 Shoulder Lift 진행을 앞서지 않는다.
- 모든 후보가 dense FK에서 C XY distance monotonic, servo bounds, bounded step을 통과했다. balanced/mild/medium/strong의 target count `71/71/71/72`, min TCP Z `95.721/90.511/86.020/80.988 mm`, route L2 `110.042/110.173/110.497/111.100°`, 공통 min servo margin `15.944°`.
- `BALANCED_COUPLED` 선택: anchor → `[-6.432126,-34.623121,+52.390090,+63.608253,-5.261440]` → `[-4.292824,-19.246243,+39.882220,+46.716507,+1.125471]` → `[-2.153522,-3.869364,+27.374351,+29.824760,+7.512382]` → unchanged endpoint. TCP Z/C XY distance는 `104.267/246.782 → 98.356/187.418 → 95.828/122.885 → 96.568/58.588 → 99.992/0.010 mm`.
- runner contract를 1–6 intermediate로만 확장했다; interpolation and control policy unchanged. 관련 31/31 tests, py_compile/diff-check/local dry-run PASS.
- Jetson에 기존 runner를 `.pre-coupled-20261011`로 백업하고 runner/config를 배포했다. SHA `1c81214bda770fa2890f12c1488eb1b90988ca2bec669bc0f8e78bfe792edc71` / `bd068b7355423a0472e8185d0b02d26842b47b8cbae14eaa77e321a1f681b444`; installed-Python py_compile/dry-run PASS. 첫 fuser는 sudo timestamp 만료로 불확실했고 인증 갱신 뒤 privileged `fuser rc=1` 무점유를 확정했다.
- C robot XY는 live YOLO detection의 bbox center를 ArUco/table transform으로 변환해 계산한 고정 endpoint다. motion 중 YOLO closed-loop correction은 없다. endpoint/C XY/calibration/final 1.6° tolerance unchanged. actual motion `NOT_RUN/NOT_AUTHORIZED`, grasp/lift `NOT_RUN`, swept-link/environment collision `NOT_VERIFIED`, `NOT_COMMITTED/NOT_PUSHED`.

## LIFT_NEG50 strong-unload pre-approach 실기 결과

- user-approved pre-approach 1회. fresh start `[-8.659341,-69.318681,+73.626374,+76.000000,-11.648352]°`, 105-target 경로 시작. grasp/lift `NOT_RUN`.
- stage 1 Shoulder Lift `-50°` 도달 뒤 Elbow-relief 초기 구간은 효과가 있었다. waypoint 23–28 Elbow target `70.776→65.878°`, following error `0.50–0.89°`, Present_Load `36–56`.
- waypoint 29 target `64.897959°`에서도 error `1.607535°`, load `88`로 envelope 안이었다. 이후 target을 `63.918/62.939/61.959/60.980°`로 내리며 error/load가 `2.323/120`, `2.688/136`, `3.140/156`, `3.768/184`로 증가했다.
- stage 2 endpoint waypoint 34 target joints `[-8.571429,-50,+60,+83,-11.648352]°`; Elbow Goal/Present raw `2666/2717`, error `4.483516°`, Moving `0`, load `216`으로 PAUSE. 1.611초 뒤 Present `2712`, error `4.043956°`, load `196`까지 감소했으나 no-progress timeout으로 ABORT.
- final feedback `[-8.571429,-49.714286,+64.043956,+82.769231,-11.736264]°`, TCP `[-37.402252,-47.331548,108.230247] mm`, endpoint까지 XY `249.271902 mm`. Lift-first는 검증됐지만 Elbow `60°` relief endpoint가 과도했다. 다음 최소 변경 근거는 실제로 안정 추종한 약 `65°`에서 stage 2를 끝내고 Shoulder Lift가 더 올라가는 final segment로 전환하는 것이다.
- 사용자 `STOPPED`, `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; post-run 세 control inactive, 관련 worker 없음, follower unowned `fuser rc=1`. tolerance/endpoint/C XY/IK/calibration/gain/torque/feed-forward 불변. 원본 `live_c_pre_approach_strong_unload_fresh3_attempt1.jsonl`; `PRE_APPROACH_PASS` 아님, `NOT_COMMITTED/NOT_PUSHED`.

## fresh3 stronger-unload staged path dry-run

- A2 종료 자세를 read-only viewer로 다시 읽었다: follower `[-8.571429,-69.318681,+73.714286,+76.000000,-11.648352]°`, gripper `1.958384`; motor write/torque change 0회, viewer 종료와 포트 release 확인.
- Shoulder Lift strong-unload 후보 `-65/-60/-55/-50°`를 비교했다. 전 후보는 strong-unload 도달 전 Elbow `73.714286°`, Pan `-8.571429°`, Roll `-11.648352°`를 고정한다. Wrist Flex는 strong-unload에서 `76°`를 유지하고 Elbow-relief에서만 C 방향 사전 진입을 막도록 최소 조정했다.
- strong-unload TCP는 각각 `[-36.826,-51.826,85.566]`, `[-37.646,-46.392,86.728]`, `[-38.446,-41.078,88.364]`, `[-39.223,-35.926,90.462] mm`; 각 첫 구간 min Z는 fresh `84.951255 mm` 이상이다.
- Elbow-relief target은 Elbow `60°`; 해당 Wrist Flex/TCP/min Z는 `87.5°/[-36.152,-56.300,115.787]/85.566`, `86.0°/[-36.116,-56.538,114.901]/86.728`, `84.75°/[-36.182,-56.099,114.091]/88.364`, `83.0°/[-36.128,-56.458,112.536]/90.462`이다.
- 실패 waypoint URDF gravity-moment proxy `0.366147 N·m`; 네 Elbow-relief segment max proxy `0.351617/0.346093/0.338250/0.328863 N·m`. 실제 servo load는 아니지만 A2의 margin 부족 재발을 줄이기 위해 `LIFT_NEG50`을 추천했다.
- 추천 3-stage 경로는 fresh → strong unload `[-8.571429,-50,+73.714286,+76,-11.648352]` → elbow relief `[-8.571429,-50,+60,+83,-11.648352]` → 기존 endpoint `[-0.014220,+11.507515,+14.866481,+12.933013,+13.899293]`. 105 targets, step `≤1°`, full path min TCP Z `84.951255 mm`, min servo margin `15.615°`.
- 로컬 27/27 tests, py_compile, diff-check, dry-run PASS. Jetson runner/config SHA `e531e367…671d` / `f4db0303…54a4`; 설치 Python py_compile 및 `no port opened; no send_action` PASS. 세 LeLab control inactive, follower unowned `fuser rc=1`.
- endpoint, final 1.6° tolerance, C robot XY, IK, calibration, gain/torque/feed-forward는 변경하지 않았다. swept-link/environment collision `NOT_VERIFIED`; 실제 motion `NOT_RUN/NOT_AUTHORIZED`, grasp/lift `NOT_RUN`, `NOT_COMMITTED/NOT_PUSHED`.

## A2_MINIMAL staged pre-approach 실기 결과

- 사용자 승인 후 SHA/세 제어 비활성/follower 무점유 사전점검을 통과했다. fresh start `[-8.571429,-81.010989,+82.505495,+64.923077,-11.560440]°`가 reference gate와 정확히 일치해 107-target 경로를 시작했다.
- stage 1과 stage 2 이후 waypoint 25의 Elbow target/error/load는 `70.000° / +3.802° / 188`. 아직 4° envelope 안이라 다음 target을 보냈다.
- final endpoint 방향 첫 waypoint 26은 target joints `[-8.467072,-69.006006,+69.327640,+75.724793,-11.249955]°`; Goal/Present Elbow raw `2772/2822`, following error `+4.386646°`, `Moving=0`, `Present_Load=212`였다. PAUSE 후 1.013초간 불변해 `following_no_progress_timeout` ABORT.
- waypoint 26 target TCP `[-35.086510,-66.839150,92.101495] mm`, feedback joints `[-8.571429,-69.318681,+73.714286,+76.000000,-11.736264]°`, feedback TCP `[-36.023522,-56.478782,84.935630] mm`. 기존 endpoint TCP와 XY 거리 `230.139/240.322 mm`라 C 근처에 도달하지 못했다.
- 결론: A2의 `Lift≈-70°`에서 Elbow를 `70°`까지 낮추는 구간도 하중 완화가 충분하지 않았다. coordinate/IK endpoint 문제가 아니라 final segment 진입 직전 Elbow load stall 재현이다. tolerance/feed-forward/gain/calibration/vision은 변경하지 않았고 자동 재시도하지 않았다.
- 사용자 `STOPPED`; `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. 종료 후 teleop/recording/inference inactive, 관련 worker 없음, follower `/dev/ttyACM1` 무점유(`fuser rc=1`). `PRE_APPROACH_PASS` 아님, grasp/lift `NOT_RUN`; 원본 `live_c_pre_approach_staged_fresh2_attempt1.jsonl`; `NOT_COMMITTED/NOT_PUSHED`.

## A2_MINIMAL staged pre-approach 배포·dry-run

- 이전 승인 실행은 reference mismatch로 controller 생성 및 첫 `send_goal` 전에 차단됐다. motor command 0회, motion/grasp/lift `NOT_RUN`이었다.
- read-only fresh follower `[-8.571429,-81.010989,+82.505495,+64.923077,-11.560440]°` 기준 새 경로:
  - unload 1 `[-8.571429,-70.000000,+82.505495,+76.500000,-11.560440]°`, TCP `[-39.331337,-35.881242,73.011475] mm`
  - unload 2 `[-8.571429,-70.000000,+70.000000,+76.500000,-11.560440]°`, TCP `[-35.030209,-64.415611,91.404715] mm`
  - 기존 endpoint `[-0.014220,+11.507515,+14.866481,+12.933013,+13.899293]°`, TCP `[-62.643294,-295.322215,99.992211] mm`
- 107개 target, max joint step `≤1°`, servo bounds PASS, segment minimum TCP Z `63.892499/73.011475/91.404715 mm`. full swept-link/environment collision은 `NOT_VERIFIED`다.
- 로컬 검증은 runner 10/10, continuous-following 8/8, planner 4/4, FK 3/3, 총 25/25와 py_compile PASS.
- Jetson에 fresh2 config를 배포했다. local/Jetson config SHA `ed6cda0db0a143c75bdef947b2f2cd2e9b3b78e01fe98f2b0007fed9fc8ff27d`, runner SHA `e531e367ac2640f733ca04f22dcdd743ee14101e608d5e4f484912cd78ba671d`; 설치 Python py_compile/dry-run PASS.
- teleop/recording/inference inactive, 관련 제어 worker 없음, follower port 무점유(`fuser rc=1`). 실제 새 경로는 별도 사용자 승인 대기 `NOT_RUN`; grasp/lift `NOT_RUN`; `NOT_COMMITTED/NOT_PUSHED`.

## A_MINIMAL staged live 시도 — start gate fail-closed

- 사용자 승인 뒤 세 LeLab 작업 inactive, SHA 일치, follower port 무점유를 확인하고 staged runner를 시작했다.
- fresh−reference arm 차이는 `Pan +0.967°, Lift +13.714°, Elbow −5.451°, Flex −7.033°, Roll +3.605°`. 축별 1° gate를 넘어 `staged_reference_start_mismatch`로 controller 생성과 첫 send 전에 중단됐다. 실제 follower가 offline reference가 아니라 이전 waypoint 14 근처에 남아 있음을 확인했다.
- motor target/send 0회, motion `NOT_RUN`, grasp/lift `NOT_RUN`, 자동 재시도 없음. controller가 만들어지지 않아 physical STOP 확인 prompt도 없었다. 종료 뒤 follower port 무점유이며 following log는 생성되지 않았다.
- gate/tolerance/path를 완화하지 않는다. 정확한 fresh pose 기반 offline 재계산 전 추가 live 실행은 `NOT_AUTHORIZED`; `NOT_COMMITTED/NOT_PUSHED`.

## Staged load-relief pre-approach offline plan

- 실패 waypoint 14의 실제 target/feedback 5축과 pivot TCP FK를 재구성했다. target `[-8.292,-80.826,+78.546,+64.233,-11.286]°` / `[-32.262,-86.678,72.600] mm`, feedback `[-8.835,-81.011,+82.593,+64.923,-11.648]°` / `[-32.880,-76.627,63.669] mm`다. 낮은 Lift 상태에서 Elbow가 먼저 감소하던 경로임을 확인했다.
- 기존 endpoint는 그대로 두고 3개 staged 후보를 0.1° FK 샘플과 1.0° 실행 waypoint 기준으로 비교했다. 세 후보 모두 servo bounds, 시작 TCP Z 비하강, final 전 C 방향 proxy, bounded step을 통과했다. swept-link/environment collision은 `NOT_VERIFIED`다.
- 최소 joint-route 후보 `A_MINIMAL`을 추천한다: current→`[-9.538,-75.000,+87.956,+78.500,-15.165]°`→`[-9.538,-75.000,+70.000,+78.500,-15.165]°`→기존 endpoint. stage TCP는 `[-37.277,-22.262,66.245]`, `[-30.665,-61.613,91.718]`, `[-62.643,-295.322,99.992] mm`; segment min Z는 `54.842/66.245/91.718 mm`다.
- 최초 B/C는 final 전 C 거리 proxy를 시작보다 1.31/4.32 mm 줄여 test 1건이 실패했다. stage 2 Wrist Flex를 최소량 보정하고 다시 실행해 planner 4/4, 기존 FK 3/3 PASS. 결과 `.local/c-red-pivot-tcp-table-20261011-s01/staged_load_relief_path_20261011.json`.
- `live_c_approach.py`가 선택된 두 intermediate를 이어 붙여 20+18+87=`125` bounded target을 생성하도록 연결했다. fresh arm이 기준 시작 자세에서 축별 1°를 넘으면 첫 send 전에 `staged_reference_start_mismatch`로 중단한다. endpoint, tolerance, continuous-following envelope는 변경하지 않았다.
- 실행기 test 첫 회는 endpoint float의 exact equality 표현 차이 한 건만 실패했고 1e-9 근사 비교로 정정했다. 최종 live runner 9/9, continuous 8/8, planner 4/4, FK 3/3 = 24/24 PASS; py_compile/diff-check PASS.
- Jetson 임시 시험 폴더에 runner/config를 배포했다. 최초 scp가 상위 임시 폴더에 놓였으나 실행 전에 발견했고 기존 runner를 `scripts/live_c_approach.py.pre-staged-20261011`로 백업한 후 올바른 `scripts/`·`configs/`로 이동했다. local/Jetson SHA runner `e531e367…671d`, config `f5864894…1653`; 설치 Python dry-run은 `no port opened; no send_action` PASS.
- hardware/serial/Goal/Torque/service 접근 0회. tolerance, raw feed-forward, gain, calibration, vision/TCP/table transform 변경 없음. 실제 pre-approach `NOT_RUN/NOT_AUTHORIZED`, grasp/lift `NOT_RUN`, `NOT_COMMITTED/NOT_PUSHED`.

## C pre-approach bounded continuous-following 실기 1회

- 사용자 승인 `RUN LIVE C APPROACH` 뒤 pre-approach만 실행했다. teleop/recording/inference inactive, follower port 무점유를 사전 확인했으며 C robot XY, 기존 endpoint, calibration, final `1.6°` tolerance는 그대로였다.
- fresh follower는 `[-9.538462,-94.725275,+88.131868,+71.956044,-15.076923]°`, gripper `1.958384`; 계획된 107개 중 waypoint 14까지 송신했다.
- Elbow following error/load는 waypoint 1의 `+0.685°/44`에서 waypoint 12의 `+3.909°/192`, waypoint 14의 `+4.048°/200`으로 증가했다. waypoint 14의 target/Goal raw/Present raw는 `78.545743°/2876/2923`; 다른 관절 오차는 모두 `0.690°` 이하였다.
- waypoint 14에서 4.0° limit를 넘자 새 target 송신 없이 `PAUSE`했다. 1.009초 뒤 Elbow Goal raw `2876`, Present raw `2923`, error `+4.047664°`, `Moving=0`, load `200`이 그대로여서 `following_no_progress_timeout`으로 `ABORT`했다. `PRE_APPROACH_PASS` 아님, grasp/lift 미시작, 자동 재시도 없음.
- 사용자가 `STOPPED`로 현장 안전을 확인해 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. 종료 후 follower port 무점유(`fuser rc=1`). 원격 JSONL `/tmp/live-c-approach-20261011/results/live_c_pre_approach_continuous_attempt1.jsonl` 16행.
- 이번 시도에서 코드, tolerance, 경로, IK, vision, TCP, calibration, torque 정책, service를 변경하지 않았다. `NOT_COMMITTED/NOT_PUSHED`.
