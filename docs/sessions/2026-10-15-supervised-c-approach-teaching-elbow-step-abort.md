# Supervised C approach teaching — 실제 gate PASS 후 Elbow step guard ABORT

사용자의 새 `RUN SUPERVISED C APPROACH TEACHING` 요청으로 새 one-shot 세션을 1회 실행했다. 직전 현장 지지·정지·전체 비접촉 확인과 무조작 종료 상태에서 fresh 3회가 동일함을 다시 확인했다. LeLab 세 제어 inactive, canonical leader/follower 및 privileged 포트 무점유, 진입점 SHA `3737e249…a1c96` 일치였다. LeLab UI 버튼이 아닌 독립 no-reconfigure runner가 세션을 소유하므로 UI teleoperation 상태는 이 runner의 활성 표시가 아니다.

시작 read-only Present raw `[2065,1468,2649,2498,1612,490]`, Goal raw `[2065,1466,2649,2497,1611,490]`, Torque all ON, Moving all 0, Tmax `36°C`였다. 실제 serial PRE_ARM_SETTLE **17표본/3.051425602초 PASS**, Present drift 0·Goal 불변·잔차 최대 2 raw. fresh origin capture와 첫 Goal 생략 후 recorder/teaching 무장, 새 one-shot 소비를 확인했다.

사용자가 리더를 조작한 뒤 `arm_step_exceeds_existing_guard`로 자동 종료됐다. 중단 요청은 전송 전에 `requests.jsonl`에 기록됐다. 팔 순서는 Pan/Lift/Elbow/Flex/Roll이다.

```text
previous target deg = [-3.120879121,-42.769230769,+58.505494505,+36.791208791,-22.197802198]
requested target deg = [-1.626373626,-42.857142857,+54.549450549,+37.142857143,-22.197802198]
requested delta deg  = [+1.494505495,-0.087912088,-3.956043956,+0.351648352,0]
limited joint = Elbow
existing limit = 2.0 deg per requested step
rejected target sent = NO
```

중단 전에 완료된 6축 Goal 전송은 **2회**다. 첫 전송 Goal read-back raw `[2065,1468,2649,2498,1614,490]`, 최종 Goal raw `[2066,1468,2649,2499,1612,490]`. Gripper는 두 전송에 포함됐지만 target raw `490`이 유지됐고 closing/opening 변화는 없었다. 94개 trace cycle의 follower raw span은 전 축 `0`; 실제 follower 이동·C approach 정렬 성공은 확인되지 않았다. `FIRST_SENT_GOAL`과 guard 전 요청은 기록됐다.

사용자의 `지금 텔레옵이 안켜져있는데` 질문 시점에 runner는 이미 자동 종료돼 shell prompt로 돌아와 있었다. 원인을 알리고 자동 재시도하지 않았다. 사용자는 사후 **정지·전체 비접촉**을 확인했다. 양 포트 무점유를 확인한 뒤 기존 쓰기 차단 도구로 추가 read-only 3회 측정했다. Present raw는 시작과 동일, Goal raw `[2066,1468,2649,2499,1612,490]`, Torque all ON, Moving all 0, Tmax `37°C`; Goal–Present는 Pan/Flex 각각 +1 raw, 나머지 0. GRASP TCP는 `[23.139625640,-235.115385759,66.547496134] mm`로 변화 없었다.

원본 세션은 Jetson `/home/jetson3/so101-current-hold-teaching-20261014/run-20261015-CIHBPb/`에 보존했다. `trace/cycles.jsonl`, `requests.jsonl`, `startup.jsonl`, `startup_summary.json`, `manifest.json`, 그리고 종료 후 `post_stop.json`이 있다. abort 경로이므로 정상 완료용 `final_pose_3sample.json` 대신 별도 post-stop 3회 측정을 저장했고, `C_APPROACH_EMPIRICAL`은 등록하지 않았다. Manifest는 `cycle_count=94`, `stop_reason=worker_error`, `data_complete=false`; cycle SHA `4ce8fb329f2baa966873688a44879937650dff71ca9193c37c42680dca93bb6b`다. manifest error_count=0은 guard 오류가 없었다는 뜻이 아니다(guard는 cycle recorder 밖에서 종료).

```ini
PRE_ARM_HOLD_STABILITY = PASS_ACTUAL_SERIAL
TEACHING = ABORT_ARM_STEP_EXCEEDS_EXISTING_GUARD
FIRST_LIMITED_JOINT = ELBOW
REQUESTED_STEP = -3.956043956 deg
LIMIT = 2.0 deg
GOAL_SENDS = 2
FOLLOWER_PRESENT_SPAN = ALL_0_RAW
TORQUE_WRITE = 0
CONFIG_WRITE = 0
PHYSICAL_STOP = FEEDBACK_AND_HUMAN_CONFIRMED
PORTS = FREE
C_APPROACH_EMPIRICAL = NOT_RECORDED
GRASP = NOT_RUN
LIFT = NOT_RUN
AUTOMATIC_RETRY = 0
NEXT_LIVE_COMMAND = NONE
```

2° guard/trajectory tolerance/calibration/reference는 변경하지 않았다. 이번 턴 코드 변경 없음. 문서 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`(대상 미지정). 원본 로그/인증정보는 커밋하지 않는다.
