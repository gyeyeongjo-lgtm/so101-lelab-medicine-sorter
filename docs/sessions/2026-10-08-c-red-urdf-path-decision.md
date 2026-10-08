# 2026-10-08 C→빨강 URDF 내 경로 가능성·해결책 선택 — 구동 없음

## 이번에 확정된 수치 원인

- 사용자가 Jetson `MODEL_RESOLUTION['sts3215']=4096`을 확인했다. 현재 설치 `motors_bus.py` 식과 calibration SHA/범위에 따라 arm 정규화는 `deg=(raw−(min+max)/2)×360/4095`, 방송은 LeLab의 도→rad다. Elbow raw 880–3087의 중점 1983.5, calibration 파일 상한 +97.011°; 실제 관측 최대 +96.571°/raw 약 3082는 URDF +90° 상한 밖이다. Wrist_Pitch calibration raw 936–3225의 상한 약 +100.615°와 URDF +95° 사이에도 같은 종류의 수치 불일치가 있다. 이는 **오프라인 URDF 감사 차단의 원인**이지 URDF 오류 확정, 물리 안전 증명 또는 실제 컨트롤러 거부가 아니다.
- 기존 SHA 검증된 현 배치 **C 접근 참고 관찰** 1,198개를 읽기 전용으로 구간 집계했다. Elbow 초과는 index 0–858(시작 후 0–44.346초)와 1112–1197(57.452–61.861초), 총 945개다. Wrist_Pitch 초과는 index 1060–1078(54.770–55.703초), 19개다. 전체 arm이 URDF 범위 안인 관측은 859–1059(44.479–54.769초)와 1079–1111(55.815–57.403초), 총 234/1,198개뿐이다. 43.311초 첫 자세 이탈 후에도 앞쪽 초과가 남고, 기록 마지막도 Elbow 초과다. 초과 샘플 제거·값 clipping은 하지 않는다.
- **2026-10-08 사용자 정정:** 이 기록에서 C 병은 빨강 바구니까지 이동하지 않았다. 앞서 후반 사진을 집기→투입→퇴피로 읽은 해석은 잘못됐으며 철회한다. 천장·사선 사진과 관절 방송은 C 접근의 참고로만 사용한다. 뒤 구간의 작업 단계·물체 상태를 이 자료만으로 확정하지 않는다.

## 선택한 해결책과 범위

- **우선 경로 변경, 모델 제한 유지.** 이 기록으로 전체 C→ID4 작업의 가능/불가능을 판단할 수 없다. 전체 이동·놓기·퇴피의 관측 자체가 없으며, 접근 구간의 합격 표본도 follower **관측**이지 실행 목표가 아니다. 55.8초 Wrist_Pitch 상한 여유 약 1.15°, 57.3초 Elbow 여유 약 0.55°인 점들도 강건한 시작 목표로 채택할 수 없다.
- 다음은 여유 있는 시작 자세에서 C 접근→집기→빨강 이동→놓기→퇴피 **전체**를 새 수동 시연으로 기록해야 한다. 기존 1,198개 자료는 접근 참고만 사용한다. 새 기록에서도 각 구간의 시작/끝과 통과 중 관절 한계·속도/충돌·물체/테두리 여유를 별도로 검증하며, 방송을 그대로 명령으로 재생하지 않는다.
- 제조사 조립체 사양과 실제 반복 운용 범위, 영점·방향/축 정합, 충돌·물체 여유를 통해 **현 제한으로 가능한 경로가 없고 URDF만 잘못됐음**이 입증되기 전에는 Elbow/Wrist_Pitch 상한 수정안을 내지 않는다. 수정이 필요해지면 해당 두 관절 중 입증된 축만 전후 값·시뮬레이션 영향·실기 승인 범위를 제시한다. calibration 최대를 곧바로 새 URDF 상한으로 쓰지 않는다.

## 실행 연결·첫 사람 승인형 시험 게이트

- 현재 `staged_cycle_execution.py`는 가짜 전송기와 관절 피드백/단계 승인 상태 계약만 있다. 실제 LeRobot `SOFollower.send_action`/`get_observation` adapter, 검증 경로 카탈로그, 독점 follower ACM0 버스 소유·현재 시작 자세 검사, 설치 calibration 적용, 명령·피드백 시각 기록은 미구현/미검증이다. 텔레옵 UI active=false나 stop API success만으로 LeLab worker/시리얼 해제를 인정하지 않는다. 수동 worker 종료와 실제 포트 무점유 확인 후에만 프로그램 제어를 단독 연결하며 양쪽의 동시 소유를 금지한다.
- 첫 시험은 C 한 병·빈 ID4/고정 배치에서 별도 현장 안전 확인 및 **구체적 실기 승인**을 받은 뒤 한 단계씩만 진행한다: 시작 자세·배치/포트·그리퍼 비움 확인 → 접근(비접촉 정지) → 집기(병 안정/테이블 이탈) → 높은 이동(ID4 중앙/테두리·링크 여유) → 놓기(바닥 지지 후 개방/병 잔류) → 열린 그리퍼 상방 퇴피. 매 단계마다 실제 송신값, 새로운 follower 관절 피드백의 허용 오차·시간 제한 내 도달, 영상/현장 물체 결과와 다음 단계 사용자 승인을 따로 기록한다. 실패·시간 초과·통신 오류·간섭·물체 불안정 때 후속 목표를 금지한다.
- 중단은 먼저 명령 생산을 막고 진행 중 write가 끝났는지 확인한다. **명령 전송 종료와 팔 정지는 별개**이므로 fresh 관절 피드백의 시간 구간 정지와 현장 팔/물체 안정 확인까지 중단 완료로 말하지 않는다. 병을 든 채 토크 무조건 해제·맹목적 퇴피·LeLab 즉시 재점유 금지. 이때의 구체적 현장 지지/정지 절차와 관절별 허용 오차·deadline·시작/배치 오차는 실제 시험 전 합의해야 하며 현재 숫자 미확정이다. 시험 결과는 `HUMAN_GATED_PROGRAM_CONTROL`; 수동 시연/완전 자율과 구분한다.

실기 연결·구동 `NOT_RUN`; 기존 사용자 변경/원본 데이터 보존; 이슈 API `NOT_RUN`; 로컬 변경 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.

## 후속 구현: 단독 버스 연결부와 새 경로 후보 (구동 없음)

- `scripts/so101_follower_transport.py`는 별도 승인 시에만 LeRobot `SOFollower.send_action({"<motor>.pos": degree_or_gripper_0_to_100})`으로 전송하고 `get_observation()`의 **새** `Present_Position` 결과로 피드백을 받도록 연결했다. `send_action` 반환 목표는 도달 증거가 아니며 기존 단계 executor가 관절별 오차/시간·안정 구간을 비교한다. raw 방향 확인용 `sync_read("Present_Position", normalize=False)`도 같은 소유 버스에서만 읽는다. `open_live`는 이번에 호출하지 않았다.
- `scripts/so101_exclusive_bus.py`는 LeLab 8000의 텔레옵/녹화/추론 비활성, follower canonical serial `5AE6058306`, ACM0 포트 무점유 및 프로그램 락을 확인한다. 8000 카메라를 보존하기 위해 LeLab 서비스 자체의 중지는 요구하지 않는다. live 연결 성공 시 kernel `TIOCEXCL`로 다른 프로세스의 후속 serial open을 막고, 매 goal/feedback 전에 LeLab 제어 상태 및 자신만의 포트 소유를 다시 확인한다. UI active=false 단독은 불충분하며 fuser 확인 실패는 차단한다. 이 메커니즘의 **실제 Jetson 동작은 NOT_RUN**이다.
- 새 `configs/c_red_waypoints_candidate_20261008.json`은 기존 방송 궤적이 아닌 수동으로 선택한 9개 희소 목표 후보다. 접근은 열린 그리퍼 자세까지, 집기는 동일 팔 자세에서 별도로 닫기, 놓기는 병 지지 확인 후 **독립 release 승인 단계**에서 열기, 퇴피는 상방 clear→새 내부 end로 분리했다. Mac의 현 설치 URDF와 SHA가 같은 모델을 사용한 `check_c_red_waypoint_candidate.py`의 오프라인 결과는 9/9 목표, 인접 선형 관절 보간 표본 모두 URDF 제한 내부이며 최소 모델 한계 여유는 전 관절 포함 23°(arm만은 30°)다. start/end는 기존 초과 대기 자세와 각각 관절 최대 약 56.6°/51.3° 다르다. 그리퍼 링크 원점의 모델 FK z는 place 약 191 mm→첫 clear 약 272 mm; TCP/실제 손가락·병·바구니 충돌 여유의 증명은 아니다. `motion_authorized=false`, `collision_verified=false`, `physical_axes_verified=false` 유지.
- fake robot/probe로 `send_action` dict·실제 `get_observation` 사용, LeLab 제어 활성·오 USB·포트 점유 차단, 실행 중 LeLab 재시작 시 추가 송신 차단, command stop과 별도 신선 관절 피드백+사람 확인 팔 정지 판정을 검증했다. LeLab 8000이 살아 있어도 포트 독점이 실제로 보장되는지, `TIOCEXCL`·fuser의 Jetson 현장 반응, 물리 영점/방향, 카메라/물체 여유는 미검증이다. 실제 연결·목표 송신 `NOT_RUN`, 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.
- 시작 자세 계약의 비정상 수치(NaN/Inf)와 재검증 실패 후 이전 합격 상태 잔류를 차단했다. 단계 사이의 실제 관절 위치를 새로 읽어 이전 도달 자세에서 벗어났다면 후속 목표를 보내지 않는다. live adapter는 설치 `dist` URDF SHA를 연결 전 확인하고, Elbow >90°·Wrist_Pitch >95° 및 나머지 arm 모델 한계/그리퍼 0–100 밖 목표를 clipping 없이 거부한다. 중단 요청은 adapter에도 영구 송신 차단 latch를 걸며, 정상 disconnect는 executor의 명령 생산·송신 종료, 새 feedback과 현장 확인에 의한 팔 정지, 물체 지지 확인을 각각 요구한다. 목표 송신이 전혀 없는 읽기 전용 연결은 현장 안정 확인 후 토크 해제 없이 해제하는 별도 경로를 만들었다. Mac 가짜 버스/파서·상태기 시험 38개 통과, 후보 9/9 목표 및 표본 관절 보간 `LIMITS_ONLY_PASS`; Jetson preflight/실제 영점·방향/충돌 검증 및 모터 명령은 계속 `NOT_RUN`이다.

## 승인된 읽기 전용 연결 시도 — 인증 실패에서 즉시 중단

- 사용자는 follower 단독 포트 확인·현재 raw/degree 읽기·해제만 승인했다. Mac의 SSH `BatchMode=yes`는 제한 환경에서 포트 22 접근 거부였고, 허용된 재시도는 `Permission denied (publickey,password)`로 끝났다. macOS에 인증된 Jetson Terminal 세션은 실행 중이 아니었다. 인증정보를 요구하거나 다른 제어 경로로 우회하지 않았다.
- Jetson 명령 실행, LeLab 상태 확인, follower serial 열기, 실제 feedback 읽기, 포트 해제 확인은 모두 `NOT_RUN`. 이 시도에서 `send_action`/목표·토크·캘리브레이션 쓰기 0회, 의도적 모터 동작 0회다. 현장 외부 움직임 여부는 관측하지 못했다. 다음은 인증된 Jetson 셸을 사용해 **같은 읽기 전용 범위**만 재개하는 것이며 최소 관절 방향 시험은 별도 승인 전 금지다.

## 후속: 승인된 읽기 전용 연결 성공, Elbow 한계에서 중단

- 사용자가 SSH 인증 방법을 제공해 별도 Jetson 셸에 접속했다. LeLab `/teleoperation-status`, `/recording-status`, `/inference-status`가 모두 inactive, `udevadm`의 `/dev/ttyACM0` ID `5AE6058306`, `sudo fuser` 무점유를 확인한 뒤 설치 `SOFollower` 객체의 `bus.connect()`만 호출했다. `robot.connect()`는 configure/토크 변경을 수반하므로 호출하지 않았다. `TIOCEXCL` 후 root `fuser` 소유 PID는 해당 읽기 프로세스 하나였고 `bus.is_calibrated=True`였다.
- 설치 버스 `sync_read('Present_Position', normalize=False)` 1회와 설치 `_normalize`를 사용했다. `shoulder_pan` ID1 raw 2108 → +0.571429° (range 755–3448, offset 873), `shoulder_lift` ID2 raw 852 → −96.923077° (796–3113, −2013), `elbow_flex` ID3 raw 3082 → +96.571429° (880–3087, −1374), `wrist_flex` ID4 raw 2569 → +42.945055° (936–3225, 1429), `wrist_roll` ID5 raw 1717 → −12.967033° (86–3643, 568), `gripper` ID6 raw 472 → 3.610771% (413–2047, −804). 모든 drive_mode=0. Arm 중 Elbow만 설치 URDF +1.5708 rad 상한보다 약 6.571° 높다. Gripper percent는 Jaw rad 한계에 직접 대입하지 않았다.
- `send_action`, `robot.connect/configure/calibrate`, bus `sync_write/write/write_calibration/enable_torque/disable_torque/configure_motors`와 내부 쓰기를 예외 guard로 막았고 시도 횟수 0이었다. 목표 송신 0회, 토크 설정 변경 0회. `bus.disconnect(disable_torque=False)` 후 root `fuser`는 무점유(`PORT_RELEASED True`), SSH도 종료했다. 연결 전후 위치를 연속 측정하거나 영상을 실시간 판독하지 않았으므로 실제 팔 이동 0/예상 밖 움직임 없음은 **독립 검증 불가**다.
- `STOP`: 현재 Elbow 모델 범위 초과를 발견해 추가 연결·방향 시험·waypoint 실행을 하지 않았다. 이 값은 기존 수동 종료 자세와 수치상 일치하나, 지금 자세에서 경로 start로 옮기는 것은 별도 이동/승인이다. URDF 상한 확대·clip·calibration 수정 없음. 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.

## 후속: 한계 내부 복귀 설계만 수행

- 사용자가 읽기 전용 연결 당시 예상 밖 움직임 없었음을 현장에서 확인했다. Elbow raw 3082/current +96.571429°, calibration mid 1983.5, 4095 분모. 제안 임시 보유값 +89°의 정수 송신 예상 raw는 `int(89×4095/360+1983.5)=2995`; 새 raw가 정확히 2995이면 실제 정규화 +88.923077°, raw −87, 현재에서 −7.648352°, 설치 URDF 상한까지 약 +1.077° 여유다. +90°/raw 3007은 상한 여유 0.022°만 남아 부적절하다. +89°는 C 후보 start `[0,−60,40,30,0,...]`와 전혀 같지 않다.
- 모델 FK에서 다른 팔 값 고정 시 gripper 링크 원점은 Elbow +96.571°→+89°에 약 +24 mm z, −3 mm y 변한다. 이는 **실제 손끝이나 모든 링크의 swept clearance가 아니며** 물리 축 방향이 확인되지 않았다. 사람 감독 수동 복귀는 작은 수치 감소를 관찰·정지하며 진행하는 우선 후보이나, LeLab 수동은 모든 축을 추종하고 소프트웨어상 단계 크기 제한이 보장되지 않는다. 특히 Shoulder_Lift 현재 −96.923°는 URDF 하한에 약 3.077°밖에 남지 않아 다른 축 drift를 막아야 한다.
- 프로그램 한 관절 복귀는 첫 내부 목표 +89°에 곧장 약 7.65° 이동해야 하며, +96→+95→…의 작은 프로그램 중간 목표는 모두 현재 URDF 범위 밖이라 사용할 수 없다. 현재 live adapter는 전체 6축 목표/이미 검증된 시작 자세를 요구하고, 실제 속도 제한과 elbow 물리 방향이 검증되지 않았다. 따라서 프로그램 송신 `NOT_READY/NOT_RUN`. 두 방안 모두 실제 이동 전 새 현장 간격·현재값·포트 소유·중단 조건과 별도 사용자 승인 필요. 이번에는 목표 송신/LeLab 시작/모터 동작 0회.

## 후속: 사람 감독 LeLab 복귀 중 큰 다관절 이동, 즉시 중단

- 사용자가 현장 빈 그리퍼·장애물 제거·리더/팔로워 시작 정렬·즉시 중단 준비를 확인했다. Jetson LeLab 세 작업 비활성, canonical ACM0 ID `5AE6058306`, root `fuser` 무점유를 확인한 후 사용자가 직접 텔레옵을 켰다. LeLab active=true, 해당 프로세스만 ACM0 점유를 확인했다. 기존 WS 방송 기준값은 Rotation +0.484°, Pitch −98.418°, Elbow +96.571°, Wrist_Pitch +43.473°, Wrist_Roll −13.319°였으며 0.4초 동안 안정적이었다. 사용자가 Shoulder_Lift −96.923°→−98.418° 차이는 의도한 정렬이라고 확인했다.
- 미세 Elbow 이동 요청 후 첫 50초 관찰에서는 변화가 없었다. 사용자가 조작 방법을 재질문해 설명했고, 이어진 방송 표본은 Rotation +1.187°, Pitch −44.967°, Elbow −2.066°, Wrist_Pitch +59.560°, Wrist_Roll −13.319°였다. 이는 의도한 작은 단일 관절 이동이 아니므로 즉시 중단을 요청했다. 사용자는 LeLab 종료·팔 정지·접촉/위험 없음 및 실제 큰 다관절 이동을 확인했다. 서버 active=false, `sudo fuser` 포트 무점유 확인. 물리 Elbow 회전 방향은 분리해 확인할 수 없었다.
- LeLab 종료 뒤 승인 범위의 읽기 전용 follower 연결에서 `Present_Position` raw/설치 normalize 결과: shoulder_pan ID1 raw2054/−4.175824°, shoulder_lift ID2 raw830/−98.857143°, elbow_flex ID3 raw2996/+89.010989°, wrist_flex ID4 raw2920/+73.802198°, wrist_roll ID5 raw1713/−13.318681°, gripper ID6 raw470/3.488372%. 읽기 연결 중 `send_action`/write guard 시도 0, `disconnect(disable_torque=False)` 후 무점유. 최종 표본은 arm URDF 내부이나 Elbow 상한·Shoulder_Lift 하한 여유는 각각 약 0.989°/1.143°다. +89° 부근 도달은 확인되나 **단일 관절 방향 시험/안전 복귀 성공으로 간주하지 않는다.** 추가 모터 동작·C waypoint/프로그램 `send_action` `NOT_RUN`.

## 후속: 기존 코드·로그로 다관절 원인 좁힘 및 시작 후보 선택 (구동 없음)

- 설치 LeLab `teleoperate.py` worker는 `SOLeader.get_action()`으로 리더 6축 위치 dict 전체를 읽어 매 주기 `SOFollower.send_action()`에 넘기고, follower는 기본 `max_relative_target=None`에서 6축 `Goal_Position`을 sync-write한다. 코드에 별도 pose alignment 확인·homing·startup interpolation은 없다. `SOFollower.configure()`는 `torque_disabled()`를 통해 설정 중 토크를 해제하고 끝에 다시 켠다. LeLab UI 시작 직후 worker 첫 6축 목표가 사실상 시작 목표다. 당시 시작 후 약 0.4초 안정·첫 요청 뒤 약 50초 변화 없음은 뒤늦은 자동 startup 동작보다 조작에 따른 전체 자세 추종에 더 부합한다. 그러나 이번 세션의 leader 각도/실제 송신 목표는 기존 방송·세션 기록에 없고 Jetson user journal에도 해당 로그가 없어서 정확한 입력을 특정할 수 없다.
- 시간순 확인 가능한 follower feedback: 시작 직전 read-only `(+0.571,−96.923,+96.571,+42.945,−12.967°, gripper 3.611%)`; 정렬 뒤 방송 `(+0.484,−98.418,+96.571,+43.473,−13.319°)`; 조작 중 단일 방송 `(+1.187,−44.967,−2.066,+59.560,−13.319°)`; 종료 후 read-only `(−4.176,−98.857,+89.011,+73.802,−13.319°, gripper 3.488%)`. 순서는 shoulder_pan/lift, elbow, wrist_flex/roll. 조작 중 표본과 최종 표본은 연속 궤적 증거가 아니며 `−2.066/−44.967/+73.802°`는 모두 follower 관측, leader 명령값 아님. 사용자 확인으로 실제 큰 다관절 움직임은 확인됐으나, 일시적 방송 오류 가능성도 해당 중간 표본에는 남는다.
- 기존 C→빨강 기록(1,198 follower 관측)에서 t=45.427s/index879의 팔 5축 `(+22.549,−45.055,+34.857,+57.802,−10.418°)`를 **오프라인 시작 후보**로 골랐다. 해당 시각 천장 영상은 그리퍼가 C와 분리된 접근 전 공중 자세를 보이며, URDF lower/upper 여유는 순서대로 `(132.549/87.450,54.945/145.055,134.857/55.143,152.802/37.198,149.583/170.418)°`. C 접근 참조 t=46.978s/index909까지 팔 5축 L2 거리 45.925°; 그리퍼 약 34.945%는 Jaw rad 검증 제외. 다른 후보 t=45.854s/index886은 접근 참조까지 25.20°이나 이미 C 쪽으로 더 다가간 자세, t=46.049s/index890은 13.46°이나 병 상공 근처다. 현재 최종 자세에서 선택 후보까지 팔 5축 L2 약 82.5°로 직접 이동 안전성은 검증되지 않았다. **후보는 관측 기반 참고값이지 검증된 목표/경로가 아니다.** LeLab 재시작·목표 송신·waypoint `NOT_RUN`; 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 후속: 사용자 정정·완전 수동 시연 기록 준비 (하드웨어 없음)

- 사용자가 직전 1,198표본에서 C가 빨강까지 이동하지 않았음을 명시했다. 따라서 이 파일의 이전 집기/투입/퇴피 영상 추정은 철회하고 접근 구간 참고로만 분류한다. 새 C 집기→이동→놓기→퇴피 전 과정의 실물 시연은 `NOT_RECORDED`.
- 저장소에 `scripts/teleop_cycle_trace.py`와 `patches/lelab-20261008/teleoperate-cycle-trace.patch`를 추가했다. 패치는 기존 LeLab worker의 같은 버스에서 리더 6축 읽기→기존 follower `send_action`→매 주기 fresh `Present_Position` 6축 읽기 순서를 기록하며, 반환 명령은 sync-write 완료 값으로 보존하고 모터 ack/도달로 오해하지 않는다. 기존 방송은 새 피드백을 재사용해 중복 읽기를 줄인다. Jetson 같은 시계의 `approach/grasp/transport/place/retreat` 마커, 주기/오류 JSONL과 SHA manifest를 둔다. 누락 축/오류/마커 순서 이상은 `data_complete=false`, 물리 작업 성공/자동 재생 승인은 항상 false.
- 가짜 리더·follower 4개 시험과 Mac 설치 LeLab 소스에 대한 patch dry-run 통과. Mac/Jetson 설치본 변경, LeLab 재시작, 실제 기록/모터 명령은 `NOT_RUN`. 현 정지 자세 Elbow/Shoulder_Lift 여유가 작으므로 시작 후보 t=45.427s로 가는 경로·물리 간격을 따로 확인하기 전에는 LeLab을 켜지 않는다. 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 후속: Jetson 기록 패치 디스크 적용과 복귀 경유 후보 (LeLab 미실행)

- Jetson 설치 확인: LeLab `0.1.0`, Python `3.14.7`, `/home/jetson3/.local/share/uv/tools/lelab/lib/python3.14/site-packages/lelab/teleoperate.py`, 원본 SHA `2a54de453da35fb0d80bf37398ae3d2b0ed17dbbb56eea3077a71e7ab33931e2`. teleop/녹화/추론 API 모두 inactive였다. 첫 GNU patch dry-run은 수동 작성 diff의 no-op hunk 형식 오류(`malformed patch at line 50`)로 실패했고 설치본은 변경되지 않았다. hunk를 제거해 재전송한 뒤 Jetson dry-run 성공.
- 원본은 `/home/jetson3/lelab-source-backups/teleoperate.py.2a54de453da35fb0d80bf37398ae3d2b0ed17dbbb56eea3077a71e7ab33931e2`에 SHA 일치 백업. 기록 모듈을 설치 패키지에 추가하고 `teleoperate.py`에 패치를 적용했다. 새 SHA 각각 `211f3485ceed0f82d9b135a94aee98b5b9cb0de5cf8af765e665896d0b83c909`, `c47732a7a73bdd234588c4df94251028ca949216b7d8cd6d933d1a4632cb2f96`. 설치 Python 두 파일 `py_compile` 성공. 수정 함수는 `get_joint_positions_from_robot`(fresh 피드백 재사용), `handle_start_teleoperation`의 시작/worker/finalize/응답이다. 서비스 재시작/teleop 시작/모터·토크·USB 명령 0회; 마지막 `/teleoperation-status`는 inactive, 기존 서비스 MainPID 523353/active since 00:02:47 KST였다. 따라서 새 코드 로드 `NOT_RUN`.
- 출력 루트 `/home/jetson3/lelab-teleop-cycle-traces` 생성. 서비스에 `LELAB_TELEOP_TRACE_ROOT`는 아직 설정하지 않아 기록은 미활성. 활성 후 `cycles.jsonl` 한 줄마다 `seq`, 시작/리더읽기/명령반환/피드백읽기 Unix ns 및 monotonic ns, `leader_position`, `follower_command`, `follower_feedback`(각 6축, arm degree/gripper percent)을 분리 저장한다. `events.jsonl`은 Unix/monotonic ns·phase·note, `errors.jsonl`은 실패 단계·오류, `manifest.json`은 SHA/표본수/완결 여부를 담는다. 각 단계의 반환 command는 sync-write 호출 완료이지 motor ACK/도달 증거가 아니다.
- 같은 장면 접근 참조 1,198표본에서 URDF 최소 여유 20° 이상인 관측 index 864/866/869/873/875/879(t=44.658/44.806/45.000/45.118/45.217/45.427s)를 경유 후보로 골랐다. 첫 지점은 현재 자세에서 5축 L2 40.55°, 최대 절대 축 변화 24.70°로 커서 검증된 한 스텝이 아니다. 뒤 인접 차이는 L2 11.39/15.18/15.96/6.65/8.21°. 영상상 그리퍼와 C/바구니의 투영은 분리돼 보이나 사선 영상에서 손끝 높이·팔 전체와 장애물 사이 최소 거리는 확인되지 않는다. **현재→첫 경유점 구간의 물리 방향/연속 간격이 미검증**이므로 복귀 절차 확정 및 실제 송신/LeLab 시작은 `BLOCKED/NOT_RUN`. 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.
