# 2026-10-14 C pre-approach 그리퍼 단독 20% 닫기 — encoder 변화, 물리 동작 FAIL/UNVERIFIED

사용자는 현재 약 `30.906%→20%` 그리퍼 단독 닫기를 요청하고, 현장에서 closing sweep 비접촉·즉시 정지 준비를 확인한 뒤 정확한 `RUN GRIPPER CLOSE TO 20 ONLY`를 승인했다. 이후 `GRIPPER CLOSE CONFIRMED`와 `STOPPED`로 정지·비접촉을 확인했다. 사용자의 “그리퍼 움직여도 됨”은 새로운 목표의 승인으로 확대하지 않았다.

실행 전 LeLab teleoperation/recording/inference inactive, privileged leader/follower fuser 무점유. 쓰기 차단 3회 fresh Present는 arm `[+14.285714,+3.384615,+54.637363,-45.846154,-22.549451]°`, gripper encoder `30.905753%/raw 918`로 동일했고 Moving 전 축 `0`, Torque_Enable 전 축 `1`, Tmax `45°C`였다. Jetson 격리 폴더의 전용 runner/config SHA가 로컬과 일치하고 설치 Python compile·dry-run PASS였다. 기존 검증된 그리퍼 singleton transport와 보유 safety gate를 재사용했다. 실기 당시 관련 local fake/회귀 테스트 `26/26 PASS`였으나, 이 테스트는 실제 손가락 이동을 검증하지 못했다.

명령은 **gripper target 1회만** 전송: requested `20.0%`, quantized command `20.012240%/raw 740`. Arm target `0`, torque write `0`, 자동 재시도 `0`. transient gripper Present raw는 `913→777→749→747`; 최종 encoder `20.440636%/raw 747`로 기존 1 pp terminal tolerance 안이다. **모터 encoder 변화**는 `−10.465116 pp`이며 실제 finger aperture 변화로 간주하지 않는다. 명령 중 arm Present drift `0°`, arm Goal raw 전 축 불변, 최종 Moving 전 축 `0`, Tmax `46°C`. Present_Load는 signed diagnostic으로만 기록(최종 gripper `+40`, transient 최대 `+208`); 검증되지 않은 numeric Load gate는 적용하지 않았다.

현장 종료 확인과 feedback 정지 검증 뒤 torque를 유지한 채 control session을 닫았다. 종료 후 LeLab 세 control inactive, privileged fuser 무점유. read-only 3회 최종 arm `[+14.197802,+3.384615,+54.637363,-45.846154,-22.549451]°`, gripper `20.440636%/raw 747`, Goal raw `[2265,1983,2570,1558,1607,740]`, Moving 전 축 `0`, Torque_Enable 전 축 `1`, Tmax `46°C`. 명령 중 arm drift `0°`; post-stop Pan의 encoder 1 raw(`−0.087912°`) 차이는 이후 측정값으로 구별한다. `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`, follower port free.

**사후 정정:** 사용자는 “그리퍼 안 움직였는데”라고 실제 손가락 움직임이 없었다고 알렸다. 실행기의 기존 `GRIPPER_CLOSE_TO_20_PASS` 출력은 encoder readback과 비접촉/정지 문구만 확인했고 **손가락이 실제로 닫혔는지 묻지 않은 판정 오류**다. 최종 판정은 `GRIPPER_REGISTER_RESPONSE=PASS`, `PHYSICAL_FINGER_MOTION=FAIL/UNVERIFIED`, `GRIPPER_CLOSE_TO_20_PASS=false`. 원인은 아직 미확정이며 기구적 결합·전달, 외부 간섭 등은 증거 없는 가설일 뿐이다. **추가 gripper 명령·재시도·torque 변경·손으로 자세 변경 금지.**

실행기 판정을 고쳐 register target 통과 시에도 `GRIPPER_REGISTER_RESPONSE_PASS_PHYSICAL_MOTION_UNVERIFIED`를 먼저 출력하고, `FINGERS PHYSICALLY MOVED AND CONTACT FREE`라는 별도 현장 확인 없이는 `GRIPPER_CLOSE_TO_20_PASS`를 출력하지 않는다. 이 변경은 격리 runner에만 적용했고 모터 재실행은 없다. Jetson 설치 파일 SHA `7123bb76…1fc19`가 로컬과 일치, 설치 Python compile/dry-run PASS, 관련 fake/회귀 `27/27 PASS`.

현재 `C_PREAPPROACH_EMPIRICAL`의 3회 기록은 당시 encoder `30.906%`를 포함한 역사적 측정으로 보존한다. 현재 encoder는 `20.441%`지만 실제 finger aperture는 **UNKNOWN**이므로 이 pose를 정확한 현행 start snapshot으로 간주하지 않는다. APPROACH/GRASP/LIFT, teleop teaching은 이번 명령에서 `NOT_RUN/HOLD`. 다음은 현장 비접촉·정지 상태에서 실제 양쪽 손가락/링크의 기계적 상태를 육안 확인하는 읽기 전용 점검이다. 원본 로그/비밀번호는 커밋하지 않았다. 관련 변경은 `NOT_COMMITTED/NOT_PUSHED`, GitHub 이슈는 대상 번호 미지정으로 `NOT_RUN`.
