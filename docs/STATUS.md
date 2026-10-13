# 현재 상태

업데이트: 2026-10-13

## 2026-10-13 human-confirmed gripper clearance·CURRENT→C PRE_APPROACH live ready

- 사용자 현장 판단으로 추가 gripper opening을 취소했다. `RUN GRIPPER OPEN TO 36 ONLY`는 `CANCELLED_BY_USER`로 fail-closed 처리했고, 이번 CURRENT→C route에서만 exact `34.577723378% / raw 978`을 `HUMAN_CONFIRMED_CURRENT_STATE`로 인정한다. global `minimum_fresh_gripper_open_percent=35.0`은 변경하지 않았고 다른 sub-35 값은 계속 차단한다.
- 실제 motor command 없이 Jetson follower를 read-only 3회 읽었다. 모두 arm `[+11.736264,-20.967033,+72.219780,-31.956044,-14.197802]°`, gripper `34.577723%/raw 978`, Moving all `0`, Torque all `1`이었고 max Temperature는 `39°C`였다. Goal raw는 `2232/1710/2795/1706/1703/985`, Present raw는 `2235/1716/2805/1717/1703/978`; write/torque change `0`, port는 정상 해제됐다.
- 이 fresh arm을 시작으로 6-waypoint `WRIST_LEAD_2DEG` route를 재검증했다. max step `1°`, joint delta `[+3.108866,+3.973679,-1.628198,-5.220847,+1.661474]°`, GRASP TCP `[-46.099790,-292.560444,93.788217]→[-62.635356,-295.315566,100.000001] mm`, TCP Z 단조 증가, C XY distance `16.763519→0.000002 mm`, table proxy `+39.129217 mm`, self-collision centerline proxy `64.775222 mm` PASS, servo margin `22.791220°`다. full mesh/environment는 `NOT_VERIFIED` 유지다.
- loader/initial/verified/pre-send 세 gate가 같은 route-local helper를 사용하며, pre-send에서는 percent와 raw `978`을 모두 검증한다. exact 현장 확인값은 PASS, `34.9%`·raw mismatch는 FAIL이고 기존 `>=35%` 경로는 유지된다.
- 로컬 targeted `61/61 PASS`, py_compile/JSON/diff-check/dry-run PASS. Jetson 격리 폴더에 runner/plan을 배치했고 local/remote SHA 일치, 설치 Python compile·CURRENT→C dry-run PASS(`no port opened; no send_action`)를 확인했다. 취소된 36% plan은 `GRIPPER_OPEN_NOT_STARTED: gripper_open_plan_cancelled_by_user`로 port 전 차단된다. 첫 원격 확인에서 gripper CLI에 없는 `--dry-run`을 명시해 argparse exit `2`가 나왔고, 기본 dry-run으로 재실행해 정상 차단을 확인했다. 두 시도 모두 hardware command `0`.
- 마지막 점검에서 LeLab teleoperation/recording/inference는 모두 inactive고, privileged `fuser /dev/ttyACM1` 출력 없음(rc `1`)으로 follower port free다. arm live motion은 `NOT_RUN/NOT_AUTHORIZED`; 상세: [세션](sessions/2026-10-13-current-to-c-human-clearance-ready.md). commit/push는 이 작업 단위로 `origin/fix/usb-recording`에 동기화한다.

## 2026-10-13 GRIPPER OPEN ONLY 실기 2 — 34.578% 정지·36% 단일 후속 준비

- fresh start 기준 `RUN GRIPPER OPEN ONLY`을 실행해 gripper 한 축 target을 1회만 보냈다. arm target `0`, gripper send `1`; `22.521420→34.516524%`, Goal raw `985`, arm drift `0 deg`, Moving all `0`, max Temperature `40 C`다. final이 `35%`보다 `0.483476 pp` 낮아 `GRIPPER_OPEN_PASS=false`; 자동 재시도와 tolerance 완화는 하지 않았다.
- 사용자 `STOPPED`·비접촉 확인 뒤 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. read-only 3회는 arm `[+11.648352,-20.967033,+72.219780,-31.956044,-14.197802] deg`, gripper `34.577723%`/raw `978`, Goal raw `985`, Moving all `0`, Torque all `1`, max Temperature `39 C`로 동일했다. follower port free, 세 control inactive다.
- post-open fresh arm 기준 CURRENT→C 경로를 `6` waypoint/max step `1 deg`로 재생성했다. TCP Z `93.788216→100.000001 mm`와 C XY distance `17.155476→0.000002 mm`가 단조 진행하지만 gripper `<35%`라 arm live gate는 계속 차단한다.
- 다음 승인 후보 `RUN GRIPPER OPEN TO 36 ONLY`는 arm target 없이 normalized `36.046512%`(Goal raw `1002`) 한 축 1회만 보내며 final PASS 기준은 기존 `>=35%`를 유지한다. targeted `59/59 PASS`, local/Jetson compile·dry-run 및 SHA 일치 PASS; 실제 36% 명령은 `NOT_RUN/NOT_AUTHORIZED`. 상세: [세션](sessions/2026-10-13-gripper-open-only-attempt2.md).

## 2026-10-13 GRIPPER OPEN ONLY 실기 1 — 시작 자세 불일치로 송신 전 차단

- 사용자 현장 확인과 `RUN GRIPPER OPEN ONLY` 승인 후 live runner를 시작했으나, 첫 target 전에 fresh arm pose가 저장 기준과 `Pan +0.088 / Lift +1.143 / Elbow +1.055 / Flex -4.659 / Roll +0.000 deg` 달라 `staged_reference_start_mismatch`로 fail-closed 차단했다. 특히 Flex가 전용 `0.5 deg` start tolerance를 초과했다. tolerance를 넓히지 않았고 자동 재시도하지 않았다.
- `GRIPPER_OPEN_LIVE=BLOCKED_BEFORE_SEND`; arm target send `0`, gripper target send `0`이다. gripper 목표 raw `985`는 기록되지 않았다.
- 종료 후 write/torque API가 차단된 도구로 follower를 0.2초 간격 3회 읽었고 모두 동일했다. fresh arm은 `[+11.824176,-21.054945,+72.219780,-31.692308,-14.197802] deg`, gripper `22.276622%`; Goal은 `[+11.472527,-21.494505,+71.340659,-32.923077,-14.197802] deg`, gripper `22.766218%`다. raw Present는 `2236/1715/2805/1720/1703/777`, Goal은 `2232/1710/2795/1706/1703/785`다.
- Moving all `0`, Torque all `1`, Load diagnostic `[28,32,52,68,0,-44]`, Temperature `[35,35,35,37,34,39] C`다. fresh GRASP TCP FK는 `[-46.465817,-292.231151,+93.372621] mm`; full mesh/environment는 `NOT_VERIFIED`다. 현재 gripper가 저장 기준 `2.264382%`와 다른 이유는 이번 실기로 확정하지 않는다.
- read-only motor/torque write `0/0`, follower port release 뒤 privileged `fuser` owner output 없음, teleoperation/recording/inference inactive, SSH 종료를 확인했다. `GRIPPER_OPEN_PASS=false`, CURRENT→C/APPROACH/GRASP/LIFT 모두 `NOT_RUN`. 상세: [세션](sessions/2026-10-13-gripper-open-only-attempt1.md). 다음 재시험은 fresh pose 기반 one-shot plan을 오프라인 재생성하고 사용자가 정지·finger sweep 비접촉·주변 clear를 다시 확인한 뒤 새로 승인해야 한다.

## 2026-10-13 CURRENT pose gripper-open-only 실기 준비 완료

- recovery/HOME/PICK_READY 추가 개발은 중단하고 C 실제 PICK을 critical path로 유지했다. 팔은 직전 STOPPED pose `[+11.736264,-22.197802,+71.164835,-27.032967,-14.197802]°`에 유지하며, 이 저장값은 live current로 가정하지 않고 실행 직전 fresh feedback으로 다시 gate한다.
- 현재 gripper `2.264382%`에서 요청 `35.0%`로만 여는 전용 runner를 추가했다. 실제 calibration `413..2047`, drive mode `0`에서 LeRobot의 `int()` 내림으로 `35.0% -> raw 984 -> 34.944920%`가 되므로, raw 직접 write 없이 최소 표현 명령 `35.0061199510404% -> Goal raw 985 -> 35.00611995104039%`를 사용한다.
- 실행기는 `{"gripper.pos": ...}` 단일 key action을 딱 1회만 전송하고 arm target은 전송하지 않는다. 전송 전 실제 설치 `so_follower.py` SHA `b7d9fcfc…08fd`, `feetech.py` SHA `0460413c…4ff2`, `motors_bus.py` SHA `ade55d42…a688`, gripper motor ID/range/drive mode, name→ID→raw 변환 key가 `{6}` 하나뿐인지를 fail-closed로 검증한다. arm Goal raw 5축은 startup, 전 settle 구간, final, port release 후 별도 read-only route gate까지 처음 baseline과 같아야 한다.
- 시작 0.5초 stillness, fresh/communication, Moving, `Temperature<=55°C`, arm Present drift `<=1°`, gripper Goal raw `985`, 최종 gripper `>=35%`를 검사한다. Present_Load는 signed diagnostic only이며 numeric PASS gate가 아니다. 하나라도 FAIL이면 후속 target은 없고 자동 재시도하지 않으며 torque/현재 Goal을 유지한 채 STOP한다. settle timeout/feedback 예외 전까지의 표본은 즉시 출력한다.
- 성공 후에도 사용자의 `GRIPPER OPEN CONFIRMED`와 `STOPPED`를 받고 command-owning session을 완전히 해제한 뒤, 별도 read-only session에서 fresh arm pose, gripper `>=35%`, Goal raw 연속성, Moving/Temperature를 다시 통과해야만 다음 문구 `RUN CURRENT TO C PRE APPROACH`를 출력한다. 팔 11-waypoint를 자동으로 연속 실행하지 않는다.
- 로컬 관련 회귀 `129/129 PASS`, gripper-only `21/21 PASS`, py_compile/JSON/diff-check/dry-run PASS다. Jetson 새 `/home/jetson3/so101-gripper-open-only-20261013/`에 12개 파일만 배치했고, 설치 Python `3.14.7`, LeRobot `0.6.0`, NumPy `2.2.6`에서 compile·dry-run과 local/remote SHA 12개 일치를 확인했다. dry-run은 `no port opened; no send_action`이다.
- 배치 후 LeLab 8000 health는 정상, teleoperation/recording/inference는 모두 inactive, canonical follower는 `/dev/ttyACM1=5AE6058306`, privileged `fuser rc=1`로 무점유다. full mesh/environment는 `NOT_VERIFIED`; gripper live motion과 CURRENT→C arm motion은 모두 `NOT_RUN/NOT_AUTHORIZED`, hardware command `0`이다. 상세: [세션](sessions/2026-10-13-gripper-open-only-ready.md). commit/push는 2026-10-13 readiness commit에 포함하여 `origin/fix/usb-recording`에 동기화한다.

## 2026-10-13 CURRENT→C PRE APPROACH 짧은 경로 OFFLINE READY·gripper blocker

- canonical PICK_READY 복귀를 중단하고, 직전 STOPPED 뒤 read-only 3회가 동일했던 current arm `[+11.736264,-22.197802,+71.164835,-27.032967,-14.197802]°`에서 기존 C PRE_APPROACH endpoint로 직접 이어지는 짧은 전용 경로를 생성했다. live runner는 이 snapshot을 현재값으로 대체하지 않고 first target 전 fresh feedback/start tolerance를 다시 검사한다.
- start→target delta는 `[+3.108866,+5.204448,-0.573253,-10.143924,+1.661474]°`다. `DIRECT_COUPLED/WRIST_LEAD_2DEG/WRIST_LEAD_3DEG`를 비교해, 직전 forward 실기의 Wrist terminal lag를 반영한 exact `WRIST_LEAD_2DEG`를 선택했다. Flex `-1°×2` 뒤 actual feedback에서 coupled remainder를 다시 생성한다.
- nominal `11` waypoint, max step `1.0°`; GRASP TCP는 `[-45.732137,-290.790629,+89.193802]→[-46.253094,-293.298410,+95.151348]→[-62.635356,-295.315566,+100.000001] mm`다. TCP Z는 전 구간 단조 증가(min `+0.537511 mm/step`), C XY distance는 `17.498394→0.000002259 mm`로 단조 감소한다.
- minimum TCP table-point margin `+34.534802 mm`, non-base link-origin margin `+40.222700 mm`, self centerline `64.775222 mm` PASS, servo margin `23.846165°`, final TCP error `0.000002570 mm`다. table 값은 TCP-point proxy이고 finger/link full mesh/environment는 계속 `NOT_VERIFIED`다.
- runner는 Wrist 두 target만 보낸 뒤 fresh direction/`±0.5°`/Moving settle/non-command drift `≤1°`/actual FK Z 증가/Temperature `≤55°C`/freshness gate를 통과해야 coupled target을 만든다. FAIL이면 no further target·현재 Goal/torque 유지·STOP이다. live FK URDF SHA 검증과 strict final tolerance(Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`)도 적용했다.
- **live blocker:** current gripper `2.264382%`는 기존 `c_grasp_open=35.0%`보다 닫힌 쪽이고 직전 실기에서 finger-tip contact가 있었다. runner는 initial/verified/pre-send fresh gripper가 `35.0%` 미만이면 arm `SEND=0`으로 차단한다. 별도 gripper-open-only 계획·finger sweep 현장 clearance·승인 전에는 `RUN CURRENT TO C PRE APPROACH`를 요청하지 않는다.
- 관련 테스트 `61/61`, py_compile/JSON/diff-check/local explicit dry-run PASS. Jetson 새 `/home/jetson3/so101-current-to-c-pre-approach-20261013/`에만 사본을 배치했고 설치 Python `3.14.7` py_compile·explicit dry-run, local/remote SHA 8개 일치를 확인했다. dry-run은 `no port opened; no send_action`; hardware command `0`이다. 상세: [세션](sessions/2026-10-13-current-to-c-pre-approach-ready.md).
- Git 사전검증에서 공용 plan loader가 기존 `live_c_approach_only` wrapper scope를 거부하는 회귀 4건을 발견했다. legacy wrapper가 정확한 문자열 scope를 요청할 때만 load-only 호환을 허용했고 generic runner/CLI scope는 넓히지 않았다. 날짜별 누적 관련 회귀는 `119/119 PASS`; 전체 discovery는 `419`개 중 변경 코드 회귀 없이 환경 의존 오류 `11`개(`cv2` 미설치 7, sandbox localhost bind 제한 4)만 남았다.
- 날짜별 Git 동기화 단위는 2026-10-12 커밋 `90bab23`과 `Record 2026-10-13 PICK_READY and C approach work`로 고정했다. 원본 `.jsonl` 로그·자격증명·데이터셋은 제외했고, 이번 범위와 무관한 ArUco SVG 3개와 ChArUco PDF 1개 삭제도 포함하지 않는다.

## 2026-10-13 C PRE APPROACH→PICK_READY 복귀 실기 2 — waypoint 9 no-progress FAIL·STOPPED

- 사용자 승인 `RUN C PRE APPROACH TO PICK READY` 범위에서 수정된 기존 stage 계약으로 복귀 실기 2를 시작했다. fresh start는 저장된 `C_PRE_APPROACH_ACTUAL_ATTEMPT1`과 정확히 일치했고 복귀 경로는 `61` waypoint였다.
- waypoint `1–9` target만 송신했다. waypoint `9/61`에서 Shoulder Lift target/present following error가 `2.633962°`였고 Moving은 all `0`이었다. controller는 `following_limit_exceeded`로 PAUSE한 뒤 약 1초 동안 진전이 없어 `following_no_progress_timeout`으로 ABORT했다. 후속 `52` target은 보내지 않았고 자동 재시도하지 않았다.
- 원본 로그는 `.local/pick-ready-20261013/c_pre_approach_to_pick_ready_attempt2.jsonl`, SHA `7e5617b7…9712`, `11`행(`SEND 9 / PAUSE 1 / ABORT 1`)이다. 원본 로그는 ignored 로컬 증거이며 커밋하지 않는다.
- 사용자 `STOPPED` 뒤 read-only 3회는 `[+11.736264,-22.197802,+71.164835,-27.032967,-14.197802]°`로 동일했다. Goal-Present는 `[-0.087912,-2.637363,-0.879121,0,-0.263736]°`, Moving all `0`, Load diagnostic `[0,132,52,0,24,0]`, max Temperature `40°C`, Torque all `1`이다.
- current GRASP TCP는 `[-45.732137,-290.790629,+89.193802] mm`, run start 대비 `[+14.909815,+2.861907,-4.414077] mm`; C XY distance `17.498394 mm`, table point proxy `+34.534802 mm`, self centerline `64.775222 mm` PASS, servo margin `23.846165°`다. full mesh/environment는 `NOT_VERIFIED`다.
- `PICK_READY_RETURN_PASS=false`, `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; follower port는 해제되어 privileged `fuser rc=1` 무점유다. tolerance/gate/gain/torque/TCP/endpoint는 변경하지 않았다. retry는 `NOT_RUN/NOT_AUTHORIZED`; 상세: [세션](sessions/2026-10-13-c-pre-approach-to-pick-ready-attempt2.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-13 C PRE APPROACH→PICK_READY 복귀 실기 1 — pre-send stage contract ABORT·STOPPED

- 사용자 승인 `RUN C PRE APPROACH TO PICK READY` 범위에서 복귀 실기 1을 시작했다. teleoperation/recording/inference inactive와 follower 단독 ownership을 확인했고, fresh start는 저장된 `C_PRE_APPROACH_ACTUAL_ATTEMPT1`과 정확히 일치했다. 이 fresh feedback으로 복귀 경로 `61` waypoint를 정상 생성했다.
- 첫 target 송신 전 `ContinuousFollowingCycle.start_stage()`에 return 전용 내부 stage 이름 `return_to_pick_ready`를 전달했다. 기존 controller 계약의 첫 stage는 `STAGES[0]=approach`이므로 `stage_order_or_cycle_complete`가 발생해 fail-closed ABORT했다.
- following log 파일은 생성되지 않았고 `SEND=0`, Goal write/motor command `0`이다. 따라서 로봇은 C PRE_APPROACH actual pose에서 움직이지 않았으며 `PICK_READY_RETURN_PASS=false`다. 이번 결과는 return path tracking 실패가 아니라 **첫 송신 전 runner↔기존 stage-machine 계약 불일치**다.
- 사용자가 `정지이고 비접촉상태임`과 `STOPPED`를 확인해 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`다. 종료 후 teleoperation/recording/inference는 모두 false이고 privileged follower `fuser rc=1`로 무점유다.
- 새 framework나 stage를 추가하지 않았다. 외부 return scope, 승인·완료 문구와 marker는 그대로 두고, fresh one-shot controller의 내부 stage만 기존 `approach`로 매핑했다. return scope가 내부 `approach`를 사용하면서도 `PICK_READY_REACHED/PICK_READY_RETURN_PASS`만 출력하는 회귀를 추가했다.
- 수정 후 live runner `27/27`, staged cycle `10/10`, continuous following `10/10` PASS다. Jetson 설치 Python py_compile과 exact dry-run도 `no port opened; no send_action`으로 PASS했고, runner local/remote SHA는 `a8bdda8e…bff13`으로 일치한다.
- actual retry는 `NOT_RUN/NOT_AUTHORIZED`, hardware command `0`이다. 상세: [세션](sessions/2026-10-13-c-pre-approach-to-pick-ready-attempt1.md). 수정본 재시도는 정지·비접촉·주변 clear를 다시 확인하고 `RUN C PRE APPROACH TO PICK READY`를 새로 승인받은 뒤에만 한다. `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-13 C PRE APPROACH→PICK_READY 복귀 경로 OFFLINE READY

- 직전 실기 종료 actual pose `[+14.549451,-16.571429,+70.725275,-35.912088,-12.879121]°`에서 canonical PICK_READY `[-4.263736,-68.703297,+68.879121,+8.131868,-23.516484]°`로만 복귀하는 전용 경로를 만들었다. 기존 성공 stage coordination을 역방향으로 사용하되 nominal endpoint가 아니라 fresh actual start에서 첫 구간을 다시 생성했다.
- 경로는 `61` waypoint, segment `14/16/16/13/2`, max step `1.0°`다. GRASP TCP Z는 `93.607879→184.960142 mm`로 매 waypoint 단조 증가하고 최저 증가량은 `+0.397176 mm`; C XY distance는 `2.596020→94.924111 mm`로 물체에서 후퇴한다.
- min TCP/table proxy `+38.948879 mm`, non-base link-origin margin `+40.222700 mm`, self centerline `64.775222 mm` PASS, servo margin `24.285725°`다. full mesh/environment는 `NOT_VERIFIED`다.
- runner는 별도 scope `live_c_return_to_pick_ready_only`, 승인 문구 `RUN C PRE APPROACH TO PICK READY`, 완료 확인 `PICK_READY CONFIRMED`, marker `PICK_READY_RETURN_PASS`를 사용한다. 독립 리뷰에서 기존 공통 arm final tolerance `1.6°`가 canonical PICK_READY 복귀 검증을 느슨하게 만드는 blocker를 발견해, return scope만 Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`, gripper `2.0 pp`로 fail-closed 분리했다. start drift/fresh feedback/ownership/servo/Temperature/following/no-progress/final Moving gate를 유지하고 Load는 diagnostic only다.
- 새 회귀 포함 live runner `26/26`, continuous following `10/10`, exclusive transport `13/13`, py_compile·JSON·exact dry-run·diff-check PASS다. Jetson 별도 `/home/jetson3/so101-c-pre-approach-return-pick-ready-20261013/`에 6개 실행 파일/config를 배치했고 설치 Python py_compile·dry-run, local/remote SHA 6개 일치를 확인했다. dry-run은 `no port opened; no send_action`; 세 control false, canonical follower `/dev/ttyACM1=5AE6058306`, privileged `fuser rc=1` 무점유다.
- 이 준비 뒤 복귀 실기 1은 첫 target 전 stage 계약 불일치로 `SEND=0` ABORT했고, 위 최신 섹션처럼 runner를 국소 수정·재검증했다. 수정본 actual retry는 `NOT_RUN/NOT_AUTHORIZED`, hardware command `0`, `PICK_READY_RETURN_PASS=false`다. 상세: [준비 세션](sessions/2026-10-13-c-pre-approach-to-pick-ready-ready.md), [실기 1 세션](sessions/2026-10-13-c-pre-approach-to-pick-ready-attempt1.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-13 PICK_READY→C PRE APPROACH 실기 1 — human geometry FAIL·STOPPED

- 사용자 승인 `RUN PICK READY TO C PRE APPROACH` 범위에서 fresh start가 canonical PICK_READY와 일치한 뒤 C PRE_APPROACH까지만 실행했다. 63/63 target을 송신했고 로그는 `SEND 63 / final PAUSE 2 / ABORT 0`, max Temperature `37°C`, max absolute following error `1.491318°`, final Moving all `0`이었다.
- final stable feedback은 `[+14.461538,-16.571429,+70.725275,-35.912088,-12.879121]°`; target 대비 오차는 `[-0.383592,+0.421925,+0.133693,+1.264803,-0.342793]°`다. controller tracking 완료와 실제 gripper geometry acceptance를 분리한다.
- 사용자는 현장에서 `FAIL — 거의 비슷했고 gripper 두 finger 끝이 C에 닿음`으로 판정했다. 두 finger 사이 opening center의 C 정렬을 실제 확인하지 못했으므로 `PRE_APPROACH_PASS=false`; APPROACH/GRASP/LIFT/PLACE는 모두 `NOT_RUN`이다. 이 관찰만으로 GRASP TCP, C XY, calibration, endpoint를 수정하지 않았고 fingertip/full mesh geometry는 `NOT_VERIFIED`다.
- 사용자 `STOPPED` 뒤 read-only 3회는 `[+14.549451,-16.571429,+70.725275,-35.912088,-12.879121]°`로 동일했다. Moving all `0`, max Temperature `37°C`, Torque all `1`; actual GRASP TCP `[-60.641952,-293.652536,+93.607879] mm`, nominal endpoint까지 `6.899170 mm`, C XY까지 `2.596020 mm`다. `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`.
- 원본 로그 `.local/pick-ready-20261013/pick_ready_to_c_pre_approach_attempt1.jsonl`, SHA `d84aa86c…935`, 65행. 원본 로그는 커밋하지 않는다. 상세: [세션](sessions/2026-10-13-pick-ready-to-c-pre-approach-attempt1.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-13 PICK_READY→C PRE_APPROACH 오프라인 경로 READY

- 기록된 PICK_READY `[-4.263736,-68.703297,+68.879121,+8.131868,-23.516484]°`에서 고정 C PREAPPROACH endpoint `[+14.845130,-16.993354,+70.591582,-37.176891,-12.536328]°`까지 새 경로를 생성했다. 과거 HOME→C 실패 경로와 HOME 절대 Lift anchor는 재사용하지 않았다.
- 상대 Lift relief `+2/+4/+6°`와 Wrist delay `25/35/45%`의 9개 후보를 비교해 가장 작은 `RELIEF_PLUS_2P0_WRIST_DELAY_25`를 선정했다. 첫 stage는 Lift만 `+2°` 움직여 예상 `23 raw`로 실측 최소 유효 `18 raw`를 넘고, 이후 Lift/Elbow 결합과 delayed Wrist를 적용한다.
- 추천 경로는 `63` waypoint, max step `1.0°`; GRASP TCP는 `[+30.308815,-276.029085,+184.960142]→[-62.635356,-295.315566,+100.000001] mm`, C XY distance `94.924111→0.000002 mm`다. TCP Z는 단조 하강하며 min table point margin `+45.341001 mm`, non-base link-origin margin `+40.222700 mm`, self centerline `64.775222 mm` PASS, servo margin `24.419418°`다. endpoint tool/jaw error는 `3.089708/0.673228°`, final target error `0.000002570 mm`; full mesh/environment는 `NOT_VERIFIED`다.
- runner는 `PICK_READY`와 전용 승인 문구, recorded start 기준 축별 tolerance(Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`)를 fail-closed로 지원한다. 독립 리뷰에서 continuous-following의 온도 read/gate와 final Moving settle 누락을 찾아 실행 전에 보완했다. 이제 모든 fresh telemetry에서 6축 `Temperature<=55°C`를 검사하고 최종 PASS에는 `Moving all 0`이 필요하다. 기존 ownership/fresh feedback/servo/following/no-progress/physical-stop gate는 유지했고 Load는 diagnostic only, PIN TCP는 calibration only다.
- 관련 테스트는 record `5/5`, planner `5/5`, live `22/22`, continuous following `10/10`, exclusive transport `13/13`, escape 회귀 `8/8`, Wrist escape 회귀 `4/4` PASS. local exact dry-run은 `no port opened; no send_action`이다. Jetson 별도 `/home/jetson3/so101-pick-ready-c-pre-approach-20261013/`에 보완본을 다시 배치했고 설치 Python py_compile·dry-run 및 local/Jetson SHA 일치를 확인했다. service/USB/Goal/Torque/motor command `0`.
- 실제 이동은 `NOT_RUN/NOT_AUTHORIZED`, APPROACH/GRASP/LIFT도 `NOT_RUN`, `NOT_COMMITTED/NOT_PUSHED`. 상세: [세션](sessions/2026-10-13-pick-ready-to-c-pre-approach-ready.md). 다음 승인 문구는 `RUN PICK READY TO C PRE APPROACH` 하나다.

## 2026-10-13 PICK_READY/VISION_READY canonical 기록 PASS

- 사용자 승인 `RUN SUPERVISED TELEOP TO PICK_READY`로 canonical 8000의 기존 `relative_start` teleoperation을 사용해 사용자가 PICK_READY를 만들었다. `PICK_READY REACHED` 뒤 teleoperation을 먼저 종료했고 API inactive와 leader `/dev/ttyACM0`, follower `/dev/ttyACM1`의 privileged 무점유를 확인했다.
- 사용자가 `STOPPED·전체 링크 비접촉·주변 clear·camera view clear`를 확인한 뒤 write·torque API가 차단된 도구로 follower를 3회 직접 읽었다. 세 Present 표본은 모두 `[-4.263736,-68.703297,+68.879121,+8.131868,-23.516484]°`, raw `[2053,1173,2767,2173,1597,447]`로 동일했고 Moving all `0`, Torque all `1`, 최고 온도 `36°C`였다.
- 새 GRASP TCP FK는 `[+30.308815,-276.029085,+184.960142] mm`다. table `Z=54.659 mm` 대비 `+130.301142 mm`, 기존 PICK_READY 기준 `Z>=154.659 mm` 대비 `+30.301142 mm`로 PASS다. Lift lower/upper calibration margin은 `33.142857/170.549451°`, Elbow는 `165.890110/28.131868°`다. 새 edge threshold는 만들지 않았다.
- record runner의 motor write/torque change는 `0/0`, 종료 뒤 port release와 세 control inactive를 재확인했다. Present_Load `[0,64,64,52,20,0]`은 diagnostic only다. `configs/poses.yaml`에 `PICK_READY=RECORDED`로 저장했고 YAML/schema·raw↔degree·FK·margin·telemetry 검산 및 관련 테스트 `5/5`, py_compile, diff-check PASS다.
- A/B/C 및 RED/GREEN/BLUE 자동 경로, 9개 조합, full mesh/environment는 계속 `NOT_VERIFIED`다. 상세: [세션](sessions/2026-10-13-pick-ready-recorded.md). 다음 작업은 과거 HOME→C 실패 경로를 재사용하지 않고 PICK_READY→C PRE_APPROACH를 새로 오프라인 생성·검증하는 것이다. `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 긴급 일정 전략 — PICK_READY/VISION_READY supervised 기록 준비 완료

- 2026-10-17 시연 성공을 최우선으로 두고 HOME→object 자동 최적화와 HOME↔SAFE_HIGH 자동 왕복을 critical path에서 제외했다. canonical runtime start는 새 `PICK_READY`, alias는 `VISION_READY`다. HOME은 storage/parking, SAFE_HIGH는 recovery/fallback/optional transport-safe pose로 보존한다.
- 현재 pose는 직전 HOME→C 실패 뒤 `[+4.879121,-40.571429,+78.461538,-5.494505,-12.615385]°`, GRASP TCP Z `68.470056 mm`인 낮은 중간 자세이므로 PICK_READY로 저장하지 않는다. `PICK_READY=NOT_RECORDED`; 사용자의 supervised relative-start teleop으로 새 자세를 만든 뒤에만 canonical 값을 기록한다.
- live 준비를 read-only 확인했다. canonical 8000 LeLab service는 active/running, `LELAB_TELEOP_MODE=relative_start`; teleoperation/recording/inference inactive다. leader `/dev/ttyACM0=5AE6085272`, follower `/dev/ttyACM1=5AE6058306`, 8002/8003 listener와 관련 제어 worker는 없다.
- 다음 live 범위는 canonical 8000 단일 ownership, `/move-arm` 1회, fresh relative origins, 사용자 무입력 3초 startup stillness 확인 뒤 사람이 leader로 PICK_READY를 만드는 것뿐이다. Torque OFF 수동 이동, 자동 waypoint, HOME/SAFE_HIGH 이동, pick은 포함하지 않는다. 시작 jump·예상 밖 movement·contact·feedback fault 시 즉시 stop한다.
- PICK_READY는 기존 table `Z=54.659 mm`와 기존 `table+100 mm` clearance 기준을 재사용해 GRASP TCP Z `>=154.659 mm`를 요구한다. Elbow/Lift의 양쪽 calibration margin은 실제 값으로 보고하고 임의의 새 numeric edge threshold는 만들지 않는다. A/B/C 접근성, 세 바구니 이동 방해 없음, camera view, 전체 링크 비접촉은 사용자가 현장에서 확인하며 9개 조합 경로는 아직 `NOT_VERIFIED`다.
- 도달 후 teleop을 먼저 stop/disconnect하고 follower Present 3회를 read-only 측정한다. joint raw/degree mean·std, FK GRASP TCP, Temperature mean/max/std, recorded_at, note를 `configs/poses.yaml`에 `PICK_READY=RECORDED`로 병합한다. Load는 diagnostic only, Temperature `<=55°C`, Moving all `0`, feedback freshness를 유지한다.
- pose helper를 `PICK_READY`와 temperature 기록에 확장하되 기존 HOME+SAFE_HIGH return-pair 계약을 보존했다. `configs/poses.yaml`에 `runtime_start_pose=PICK_READY`, 역할 metadata, `PICK_READY=NOT_RECORDED`를 추가했고 plan은 `configs/pick_ready_record_plan_20261012.json`에 고정했다. 관련 회귀 `15/15`, py_compile, JSON/YAML validation, diff-check PASS.
- 실제 teleop/motor/Goal/Torque/service/USB 변경은 `0`, `PICK_READY_RECORD=NOT_RUN/NOT_AUTHORIZED`. 기록 성공 직후 별도 지시를 기다리지 않고 PICK_READY→C PRE_APPROACH 오프라인 path/test를 시작하되 실제 command 전에 다시 승인받는다. 상세: [세션](sessions/2026-10-12-pick-ready-supervised-teleop-plan.md). 다음 승인 문구는 `RUN SUPERVISED TELEOP TO PICK_READY`다. `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 HOME→C PRE_APPROACH 실기 1 — waypoint 29 no-progress FAIL·STOPPED

- 사용자 승인 `RUN HOME TO C PRE APPROACH` 범위로 C PRE_APPROACH까지만 실행했다. 첫 원격 시작은 `sudo`가 TTY password read를 거부해 follower port open·Goal·motor command 전에 종료됐고, 같은 승인 범위에서 `sudo -S` ownership gate로 다시 시작했다.
- preflight는 LeLab health 정상, teleoperation/recording/inference inactive, follower `/dev/ttyACM1=5AE6058306`, privileged fuser 무점유, local/Jetson runner/config SHA 일치였다. fresh start `[-2.593407,-63.956044,+77.406593,+18.241758,-12.615385]°`가 기존 HOME tolerance를 통과해 `START_POSE_CONFIRMED=HOME`; fresh start 기준 경로는 `60` waypoint였다.
- first Lift-only relief는 waypoint 4에서 완료됐다. waypoint 18 `COUPLED_TRANSITION` 시 Elbow target/present error는 `+2.934522°`; `WRIST_COUPLED` 진행 중 waypoint `29/60` target `[+5.191654,-40.800604,+74.364178,-6.693373,-12.580091]°`에서 Elbow error가 `+4.097361°`로 continuous following limit `4.0°`를 넘었다.
- controller는 `following_limit_exceeded`로 PAUSE한 뒤 약 1초 동안 Elbow 진전이 없어 `following_no_progress_timeout` ABORT했다. 29개 target만 송신했고 후속 31개 target, APPROACH, grasp, lift, place는 실행하지 않았다. tolerance/gate/endpoint/TCP/calibration은 변경하지 않았고 자동 재시도하지 않았다.
- post-stop read-only 3회 Present는 `[+4.879121,-40.571429,+78.461538,-5.494505,-12.615385]°`로 동일했다. Goal-Present는 Pan/Lift/Elbow/Flex/Roll `[+0.263736,-0.263736,-4.131868,-1.230769,0]°`; Moving all `0`, Load diagnostic `[-24,+24,+200,+68,0]`, max Temperature `45°C`, Torque all `1`이다.
- actual final GRASP TCP는 `[-10.546107,-262.235242,+68.470056] mm`, C XY 잔여 `61.705733 mm`, table point proxy margin `+13.811056 mm`, self-collision centerline proxy `53.946249 mm` PASS다. waypoint 29 nominal target TCP Z `91.972426 mm`보다 실제가 낮은 것은 Elbow/Flex tracking lag와 일치한다. full mesh/environment는 `NOT_VERIFIED`다.
- 사용자의 `STOPPED`와 feedback 정지로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; post-run LeLab 세 control inactive, follower privileged fuser 무점유다. 원본 로그 `.local/home-c-pre-approach-20261012/home_to_c_pre_approach_attempt1.jsonl`, SHA `df364bd5…de1`, `31`행(`SEND 29 / PAUSE 1 / ABORT 1`). `PRE_APPROACH_PASS=false`, 다음 live command `NONE`; [세션](sessions/2026-10-12-home-to-c-pre-approach-attempt1.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 이전 전략 — HOME→C PRE_APPROACH 오프라인 준비 완료 (SUPERSEDED)

> HOME은 보관 자세로 유지하지만 더 이상 canonical runtime start가 아니다. 아래 경로는 재실행하지 않는 historical evidence다.

- canonical `START_POSE`를 기록된 HOME `[-2.593407,-65.274725,+77.406593,+17.890110,-12.615385]°`로 확정했다. SAFE_HIGH는 recovery/fallback/optional transport-safe pose로 보존하며, 직전 SAFE_HIGH→C 실패 경로와 HOME↔SAFE_HIGH 자동화는 C→RED critical path에서 제외했다.
- write/torque API를 차단한 read-only fresh 3회에서 Present는 `[-2.593407,-63.956044,+77.406593,+18.241758,-12.615385]°`로 동일했다. canonical HOME 대비 `[0,+1.318681,0,+0.351648,0]°`; 기존 HOME tolerance Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`를 통과해 `HOME_NEAR=true`다. Moving all `0`, Torque all `1`, max Temperature `43°C`, Elbow Goal-Present `-2.021978°`, Load diagnostic `104`다. viewer motor/Goal/Torque command는 `0`이고 종료 뒤 follower port를 해제했다.
- 기존 실측 `10–14 raw 정체 / 18 raw movement 시작 / 20–23 raw 반복 movement`와 성공한 Lift-first·Shoulder–Elbow coupling·delayed Wrist 로그를 사용해 `HOME→LIFT_RELIEF→COUPLED_TRANSITION→WRIST_COUPLED→C_PRE_APPROACH` 후보를 생성했다. `LIFT_NEG65P0`는 예상 `3 raw`로 evidence gate FAIL, `LIFT_NEG60P0`와 `LIFT_NEG55P0`는 각각 `60/117 raw`로 PASS다.
- 최소 유효 변화인 `LIFT_NEG60P0`를 추천한다. `62` waypoint, max step `0.983339°`, GRASP TCP Z `99.167→81.035→87.655→93.013→97.103→100.000 mm`, C XY distance `93.008→95.372→71.684→47.701→23.718→0.000002 mm`다. 최저 TCP/table proxy margin `+26.376347 mm`, non-base link-origin margin `+40.222700 mm`, self-collision centerline proxy `55.827804 mm`, servo margin `17.604407°`; full mesh/environment는 `NOT_VERIFIED`다.
- endpoint는 새 PICK GRASP TCP `[-4.748354,-12.033741,-124.531737] mm`, 기존 C XY, 기존 pre-approach 관절값을 그대로 쓴다. final GRASP TCP는 `[-62.635356,-295.315566,+100.000001] mm`, C XY error `0.000002 mm`, full/tool/jaw orientation error `3.090410/3.089708/0.673228°`다. table→robot, C XY, PIN calibration TCP, GRASP TCP는 변경하지 않았다.
- `scripts/plan_home_to_c_pre_approach.py`, planning request와 live config를 추가하고 기존 `live_c_approach.py`에 HOME 전용 승인 문구와 기존 HOME 축별 start tolerance를 추가했다. start pose와 승인 문구는 서로 일치할 때만 허용한다. SAFE_HIGH 지원은 recovery/historical 용도로 보존했다. 관련 회귀 `53/53`, py_compile, exact dry-run, diff-check PASS다.
- Jetson의 기존 실기 폴더와 서비스는 수정하지 않고 `/home/jetson3/so101-home-c-pre-approach-20261012/`에 별도 runner/config 사본을 배포했다. 설치 LeLab Python py_compile·dry-run PASS, local/Jetson SHA 일치; serial/USB/Goal/Torque/motor command `0`이다.
- actual HOME→C 이동은 `NOT_RUN/NOT_AUTHORIZED`, full mesh/environment는 `NOT_VERIFIED`, `NOT_COMMITTED/NOT_PUSHED`. 상세: [세션](sessions/2026-10-12-home-to-c-pre-approach-ready.md). 다음 live 승인 문구는 `RUN HOME TO C PRE APPROACH` 하나다.

## 2026-10-12 SAFE_HIGH→C PRE_APPROACH 실기 시도 1 — START_POSE gate 차단

- 사용자 승인 `RUN SAFE HIGH TO C PRE APPROACH`로 새 runner를 시작했다. 실행 전 LeLab teleoperation/recording/inference inactive, follower `/dev/ttyACM1=5AE6058306`, privileged `fuser rc=1` 무점유, runner/config SHA 일치를 확인했다.
- fresh feedback은 저장 SAFE_HIGH가 아니었다. SAFE_HIGH 대비 차이는 Pan/Lift/Elbow/Flex/Roll `[-3.868,-86.857,+150.681,-24.879,+2.637]°`로, 축별 `1.0°` start tolerance를 크게 초과했다. 자세는 직전 HOME-near feedback과 일치하는 방향이다.
- `staged_reference_start_mismatch`가 controller/path 생성 전에 발생해 first target, Goal write, continuous-following log가 모두 `0`이다. `START_POSE_CONFIRMED`, `PRE_APPROACH_PASS`는 발생하지 않았다. grasp/approach/lift/place도 `NOT_RUN`이다.
- 종료 뒤 LeLab 세 제어 inactive, live runner 없음, following log 부재, privileged follower `fuser rc=1` 무점유를 확인했다. motor/Torque/Goal 변경 `0`; 현장 human stop 재확인은 이번 시도에서 입력받지 않았으므로 `physical_stop=FEEDBACK_ONLY_NO_COMMAND`, full mesh/environment는 `NOT_VERIFIED`다.
- 다음 단계는 사용자가 supervised relative-start teleop으로 follower를 기록 SAFE_HIGH에 둔 뒤 teleop 종료·비접촉·정지를 확인하는 것이다. 같은 자동 명령을 현재 pose에서 재실행하지 않는다. 상세: [세션](sessions/2026-10-12-safe-high-to-c-pre-approach-attempt1.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 이전 전략 — SAFE_HIGH를 START_POSE로 사용, C pre-approach 준비 완료 (SUPERSEDED)

> 이후 canonical START_POSE가 HOME으로 정정됐다. 아래 내용은 삭제하지 않은 historical/recovery 기록이며 현재 critical path가 아니다.

- deadline critical path에서 HOME↔SAFE_HIGH 자동 왕복과 teleop trace/replay 작업을 제외했다. HOME 기록은 보존하지만 production start에는 쓰지 않는다. 직전 teleop trace 확장 시도는 Jetson에 배포되지 않았고 로컬 미완성 diff만 제거했다. 기존 trace 계획 문서는 historical record다.
- 기록된 SAFE_HIGH `[+1.274725,+22.901099,-73.274725,+43.120879,-15.252747]°`, GRASP TCP `[+2.090996,-389.902432,+364.853599] mm`를 canonical `START_POSE/VISION_READY`로 고정했다. live 시 fresh feedback이 전 축 `1.0°` 이내여야 `START_POSE_CONFIRMED=SAFE_HIGH`가 된다.
- 새 PICK GRASP TCP `[-4.748354,-12.033741,-124.531737] mm`와 기존 C XY `[-62.635354,-295.315566] mm`를 유지했다. PIN TCP는 calibration 전용이며 새 plan에는 `CALIBRATION_ONLY`로 명시했다.
- SAFE_HIGH→C PRE_APPROACH endpoint는 `[+14.845130,-16.993354,+70.591582,-37.176891,-12.536328]°`, FK GRASP TCP `[-62.635356,-295.315566,+100.000001] mm`, C pre-approach position error `0.000002570 mm`다. orientation error는 full/tool/jaw `3.090411/3.089709/0.673228°`다.
- 실행기와 동일한 3-stage bounded interpolation은 `146` waypoint, 최대 step `0.989329°`, TCP Z `364.853599→337.611770→277.731591→189.929233→100.000001 mm`로 단조 하강한다. min TCP/table proxy margin `+45.341001 mm`, min non-base link-origin/table margin `+40.222700 mm`, self-collision centerline proxy `64.775222 mm`, calibration servo margin `21.736275°`다. full mesh/environment는 `NOT_VERIFIED`다.
- `configs/live_c_pre_approach_from_safe_high_20261012.json`을 추가하고 기존 `live_c_approach.py`에 allowlisted 승인 문구와 SAFE_HIGH fresh-start 표기만 확장했다. 새 framework는 만들지 않았다. 직접 관련 unit test `19/19`, trace 회귀 포함 선택 test `38/38`, py_compile, dry-run, diff-check PASS. dry-run은 `no port opened; no send_action`; 실제 motor/Goal/Torque command `0`이다.
- Jetson의 기존 실기 폴더와 서비스는 수정하지 않고 `/home/jetson3/so101-safe-high-c-pre-approach-20261012/`에 runner/의존 모듈/config 사본만 배포했다. 설치 LeLab Python py_compile·dry-run PASS, local/Jetson SHA는 runner `664ec12c…f33`, config `efd8e294…064`로 일치한다. 원격 dry-run도 motor port/Goal/Torque write `0`이다.
- 다음 live 승인 문구는 `RUN SAFE HIGH TO C PRE APPROACH` 하나다. 실제 실행은 아직 `NOT_RUN/NOT_AUTHORIZED`; 성공 전 approach/grasp/lift/RED place는 실행하지 않는다. 상세: [세션](sessions/2026-10-12-safe-high-to-c-pre-approach-ready.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 supervised HOME→SAFE_HIGH teleop trace 계획

- `HOME_SAFE_HIGH_HOME_ONCE=FAIL`과 synthetic 78-waypoint 재실행 금지를 기준선으로 고정했다. 다음 경로는 사람이 실제 성공시킨 relative-start joint coordination에서만 추출한다.
- Jetson 설치를 read-only 확인했다. `lelab.service`는 active/running이지만 teleoperation/recording/inference는 모두 inactive다. `LELAB_TELEOP_MODE=relative_start`; 설치 `teleoperate.py`는 기존 CycleTrace·trace root·fresh relative origin 경로를 포함한다. trace root/ticket은 현재 설정되지 않아 기록은 비활성이다.
- canonical 8000 teleop worker 하나만 두 포트를 소유하고 같은 worker 안의 기존 CycleTrace를 확장한다. 별도 follower reader나 새 control framework는 만들지 않는다. 기존 leader/sent-command/fresh-feedback에 Goal/Present raw, Moving, Load diagnostic, Temperature, FK GRASP TCP XYZ를 같은 cycle row로 추가하는 계획이다.
- live 전 physical stop·전체 비접촉·단일 owner·privileged fuser 무점유·fresh HOME tolerance를 확인한다. 시작 후 leader 무입력 3초 동안 first target=follower origin, Moving=0, command drift 없음, Present raw span encoder 1 count 이내를 요구한다. 실패 시 본 이동을 시작하지 않는다.
- 사용자가 HOME→SAFE_HIGH를 supervised relative-start로 이동하고 endpoint에서 비접촉을 확인한 뒤 teleop을 종료한다. 종료 후 fresh Present 3회, 기존 SAFE_HIGH tolerance/GRASP TCP Z, trace 오류 0·SHA를 모두 통과해야 `HOME_TO_SAFE_HIGH_TELEOP_TRACE=PASS`다.
- 역방향은 trace reverse가 아니라 별도 supervised SAFE_HIGH→HOME 기록·승인을 요구한다. simplification과 automatic one-way 시험은 두 실제 trace 단계 뒤에만 진행한다.
- 기존 relative-start `14/14`, CycleTrace `5/5`, py_compile, diff-check PASS. 이번에는 code 설치/service restart/port open/motor/Goal/Torque command `0`; 계획만 작성했다. [세션](sessions/2026-10-12-home-to-safe-high-teleop-trace-plan.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 HOME→SAFE_HIGH→HOME 실기 1 — waypoint 1 FAIL·STOPPED

- 사용자 승인 `RUN HOME SAFE_HIGH HOME ONCE`로 왕복 1회를 시작했다. 첫 시도는 command 전에 `port_ownership_unknown`으로 차단됐다. 실제 follower 점유가 아니라 `sudo -n fuser` 인증 캐시 부재로 privileged scan을 완료하지 못한 것이 원인이며 Goal/Torque/serial open은 `0`이었다.
- USB `/dev/ttyACM1=5AE6058306`, LeLab 세 제어 inactive, privileged `fuser rc=1/unowned`를 확인하고 동일 승인 범위에서 ownership gate를 유지한 채 다시 시작했다.
- 156개 중 첫 `SAFE_HIGH_EXCEPT_PAN` target 하나만 보냈다. Lift `+1.160208°` 요청에 `+1.318681°`(`113.659%`), Wrist Flex `+0.331984°` 요청에 `+0.351648°`(`105.923%`) 움직였지만 Elbow `-1.982649°` 요청에는 `0°`(`0%`)로 움직이지 않았다.
- after Present는 `[-2.593407,-63.956044,+77.406593,+18.241758,-12.615385]°`, Goal/Present raw는 `[2072,1225,2841,2287,1720,446] / [2072,1227,2864,2288,1721,446]`이다. Elbow error `+1.982649°`, Moving `0`, Load diagnostic `104`; 최고 온도 `52°C`다.
- GRASP TCP는 `[20.324187,-253.265255,99.167465]→[20.241125,-251.432048,93.640789] mm`, Z `-5.526677 mm`, table margin `+38.981789 mm`로 악화됐다. self-collision centerline proxy는 `55.827804 mm`; full mesh/environment는 `NOT_VERIFIED`다.
- `movement_ok=false`와 `table_proxy_ok=false`로 waypoint 1에서 즉시 ABORT했고 후속 155개 target과 3회 반복은 실행하지 않았다. 사용자의 `STOPPED`와 feedback 정지 검증으로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; 종료 후 follower privileged `fuser rc=1`, 세 LeLab 제어 inactive다.
- HOME FK 민감도는 Lift `-3.482535`, Elbow `-5.062734`, Wrist Flex `-2.741795 mm/deg`다. 명목 coupled step은 Elbow 감소가 따라와야 Z가 증가하지만 실물 Elbow가 정체해 Lift/Wrist의 Z 감소만 나타났다. 기존 경로 재실행 금지, `NEXT_LIVE_COMMAND=NONE`; [세션](sessions/2026-10-12-home-safe-high-home-attempt1.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 HOME→SAFE_HIGH→HOME 1회 dry-run 준비 완료

- 기록된 HOME `[-2.593407,-65.274725,+77.406593,+17.890110,-12.615385]°`와 SAFE_HIGH `[+1.274725,+22.901099,-73.274725,+43.120879,-15.252747]°`를 기준으로 왕복 1회만 준비했다. 실제 왕복과 3회 반복은 `NOT_RUN/NOT_AUTHORIZED`다.
- 기존 `safe_home_return.py`를 확장하고 thin runner `live_home_safe_high_home_once.py`를 추가했다. 순서는 `SAFE_HIGH_EXCEPT_PAN→PAN_ALIGNMENT→HOME_EXCEPT_PAN→HOME_PAN_ALIGNMENT`로 양방향 arm-first/Pan-last다.
- waypoint별 fresh feedback, intended direction, 50% movement, non-commanded drift `<=1°`, settle, Temperature `<=55°C`, calibration bounds, table/self-collision proxy를 검사한다. Elbow Goal/Present/error/Moving/Load를 별도 기록하며 Present_Load는 diagnostic only다. 첫 실패 뒤 추가 target이나 자동 recovery는 없다.
- 오프라인 결과는 HOME→SAFE_HIGH `78`, SAFE_HIGH→HOME `78`, 총 `156` waypoint, max joint step `1.982648930°`, GRASP TCP Z `99.167465…364.853599 mm`, minimum table proxy `+44.508465 mm`, self-collision centerline proxy `55.827804 mm`, calibration servo margin `19.604396°`다. outbound/return Z 단조성과 exact HOME endpoint, offline constraints를 통과했다. full mesh/environment는 `NOT_VERIFIED`다.
- final HOME tolerance는 Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`, gripper `1.0 pp`다. 기록 당시 Elbow Goal-Present `-3.692308°`는 tolerance를 확대하지 않고 실제 1회에서 수렴 여부를 확인한다.
- 로컬 `unittest 10/10`, py_compile, dry-run, diff-check PASS. Jetson은 기존 시험 폴더를 수정하지 않고 `/home/jetson3/so101-home-roundtrip-20261012/`에 별도 배포했다. 첫 원격 dry-run의 누락 의존성 `safe_escape_verification` 실패를 기록하고 보완한 뒤 설치 Python/URDF dry-run PASS 및 핵심 SHA 일치를 확인했다.
- local/Jetson dry-run 모두 `hardware command=0`, serial open/Goal/Torque write `0`. 상세: [세션](sessions/2026-10-12-home-safe-high-home-once-ready.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 supervised HOME adjustment — HOME RECORDED

- 사용자가 원했던 초기 HOME 외형은 Elbow `+95.868132°`, calibration upper margin `1.142857°`로 servo edge에 너무 가까워 canonical로 저장하지 않고 `HOME_USER_DESIRED` reference로만 보존했다.
- 사용자가 LeLab supervised teleop으로 Elbow를 완화한 뒤 `STOPPED·비접촉 확인`을 보고했다. canonical 8000 teleoperation을 1회 종료하고 inactive를 확인했다. 종료 후 motor/Goal write와 Torque 변경은 `0`.
- 과거 `/dev/ttyACM0` 고정 read-only 도구는 현재 USB 매핑과 불일치해 serial identity gate에서 포트를 열기 전 중단됐다. 현재 LeLab robot record의 leader ACM0/follower ACM1과 follower serial `5AE6058306`을 재확인한 후, write/torque API를 fail-closed한 read-only 도구로 fresh follower 3회를 읽었다.
- 3회 raw는 모두 `2072/1212/2864/2284/1721/446`, calibrated arm은 `[-2.593407,-65.274725,+77.406593,+17.890110,-12.615385]°`, gripper `2.019584%`로 동일했다. 전 축 Moving=0, Torque=1, 최고 온도 `45°C`; `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`.
- Elbow upper calibration margin은 `19.604396°`로 확대됐다. GRASP TCP는 `[+20.324187,-253.265255,+99.167465] mm`, table reference 대비 `+44.508465 mm`, self-collision centerline proxy `55.827804 mm`다. full mesh/environment는 `NOT_VERIFIED`.
- Elbow Goal-Present는 `-3.692308°`, Load diagnostic은 `+180`이다. Load는 검증된 absolute threshold가 없어 PASS gate에 쓰지 않는다. 정지 전 WebSocket의 Elbow `59.296703°`는 canonical로 쓰지 않고 정지 후 direct Present를 저장했다.
- `configs/poses.yaml`은 `HOME=RECORDED`, `SAFE_HIGH=RECORDED`. HOME↔SAFE_HIGH 자동 경로/실기는 아직 `NOT_RUN/NOT_AUTHORIZED`; [세션](sessions/2026-10-12-home-adjusted-recorded.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 SAFE_HIGH→HOME supervised teleop 시도 1 — startup guard FAIL·STOPPED

- 사용자 승인으로 canonical 8000 relative-start 텔레옵을 한 번 시작했다. 사전점검은 8000/8002 teleop inactive, 8003 없음, canonical USB leader ACM0/follower ACM1, manager `LELAB_TELEOP_MODE=relative_start`였다. HOME 자동 waypoint·Torque 변경·서비스 재시작은 없었다.
- 20:35:54 양 장치 연결과 `relative_start origins captured`를 확인했으나 `/ws/joint-data`가 3초 동안 표본을 내지 않아 방송 기반 startup stillness 판정은 불가능했다. 20:36:03 Wrist Flex target `37.582418→35.560440°`, step `-2.021978°`가 2° guard를 초과해 worker가 자동 ABORT·양 장치 disconnect했다.
- 20:36:30/31 Mac에서 stop 직후 예상하지 않은 두 번째 `/move-arm` 요청이 들어와 canonical 세션이 다시 시작됐다. 열린 IAB의 LeLab `/teleoperation` 탭을 발견해 자동 재호출의 가장 직접적인 후보로 격리했지만 request trace가 없어 `PROBABLE_NOT_PROVEN`; 추가 재시작 방지를 위해 해당 LeLab 탭만 닫았다.
- 20:36:58 canonical stop을 명시적으로 호출했고 follower/leader disconnect, 8000/8002 teleop inactive를 확인했다. 8000/8002 서버 프로세스는 종료하지 않았다. 이후 사용자 `STOPPED·비접촉 확인`으로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`를 복구했다.
- 정지 확인 후 Present_Position 3회 read-only 표본은 raw `2066/918/3074/2521/1691/446`으로 모두 동일했고, calibrated `[−3.120879,−91.120879,+95.868132,+38.725275,−15.252747]°`, gripper `2.019584%`다. SAFE_HIGH 대비 최대 변화는 Elbow `+169.142857°`이며, Elbow는 calibration upper endpoint에서 13 raw밖에 떨어져 있지 않다. 현재는 `LOW_NEAR_SERVO_EDGE`; HOME의 non-extreme 조건을 통과하지 못해 `HOME=NOT_RECORDED`, 기록된 SAFE_HIGH는 현재 pose가 아니다. read-only write/torque API `0`; 새 teleop/motion은 별도 승인 전 금지. [세션](sessions/2026-10-12-home-teleop-attempt1.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 teleop ownership read-only 확인·HOME 기록 계획

- canonical 8000은 user systemd `lelab.service`, 실제 Uvicorn/LeLab PID `548557`이며 2026-10-11 19:30:58 KST부터 restart 없이 실행 중이다. canonical USB는 leader `5AE6085272→ACM0`, follower `5AE6058306→ACM1`이고 저장 robot record와 일치한다.
- systemd user-manager 환경은 `LELAB_TELEOP_MODE=relative_start`. 20:16:22 성공 세션 journal에도 `relative_start origins captured`가 있어 해당 실행 모드를 확인했다. 시작 요청은 Mac `192.168.50.131`의 8000 `POST /move-arm`; access log에는 Mac 내부 호출 프로세스/사람 신원이 없어 `NOT_RECORDED`다.
- 20:16:12/13 canonical 요청은 임시 8003이 follower를 점유한 동안 open 실패 후 cleanup됐고, 8003 해제 뒤 20:16:22 요청만 양 장치 연결에 성공했다. 성공 세션 중 동시 serial ownership 증거는 없다. 20:19:04 stop 뒤 follower/leader disconnect와 `Teleoperation stopped`가 기록됐다.
- 20:30:16 KST 현재 8000/8002 teleop inactive, 8000 recording/inference inactive, 8003/8022 listener 없음. non-privileged `lsof`에 ACM owner는 없으나 현재 privileged `fuser` 재검사는 `NOT_RUN`; 정상 disconnect journal과 inactive API가 현재 무소유 근거다. 서비스/프로세스 종료와 hardware command는 `0`.
- HOME 기록은 canonical 8000 하나만 쓰며 8002/임시 8003을 사용하지 않는다. 단일 `/move-arm`, journal의 relative-start 확인, 3초 무입력 stillness, 사용자 감독 HOME 이동, stop/disconnect 후 3회 read-only 기록 순서로 준비했다. HOME 이동은 `NOT_RUN/NOT_AUTHORIZED`; [세션](sessions/2026-10-12-teleop-ownership-home-plan.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 supervised teleop recovery — SAFE_HIGH RECORDED

- 사용자 감독하에 낮은 pose에서 SAFE_HIGH로 이동했고, 사용자의 `SAFE_HIGH REACHE`를 실행 문맥상 도달 확인으로 해석했다. 도달 직후 canonical 8000 teleop을 명시적으로 중지했다. 종료 시 8000 teleoperation inactive, 임시 8003 worker 종료, leader/follower 포트 무점유다.
- 임시 relative-start worker는 startup 3초/58표본에서 최대 변화 Pan/Lift/Elbow/Flex/Roll `0/0.087912/0/0/0.087912°`로 startup jump가 없었다. 이동 중 Elbow calibration 하한 HOLD 뒤 Shoulder Lift target이 `4.219780°` 바뀌어 기존 2° guard가 ABORT했고 20:15:06 KST에 disconnect했다.
- 이후 canonical 8000이 teleop active 상태로 포트를 소유한 것을 발견했다. 해당 세션 시작 주체는 `NOT_VERIFIED`이고 8000 프로세스 환경에 `LELAB_TELEOP_MODE`가 없었으므로, 전체 이동의 control provenance가 relative-start only였다고 확정하지 않는다. HOME 기록 전 single-owner relative-start 경로를 명시적으로 고정해야 한다.
- 최종 Present raw 3표본은 `2116/2215/1150/2571/1691/446`으로 동일했다. 관절값은 `[+1.274725,+22.901099,-73.274725,+43.120879,-15.252747]°`, gripper `2.019584%`; Goal raw `2118/2202/1117/2558/1690/446`, Torque all 1, Moving all 0이다.
- Load diagnostic은 `-20/64/144/64/0/0`, Temperature `37/39/39/36/35/39°C`; 검증된 absolute Load threshold가 없어 Load는 PASS gate에 사용하지 않았다.
- GRASP TCP는 `[+2.090996,-389.902432,+364.853599] mm`. table reference `54.659 mm`보다 `310.194599 mm`, SAFE_HIGH 요구치 `154.659 mm`보다 `210.194599 mm` 높아 Z 기준 PASS다. 사용자 현장 감독과 3회 동일 feedback으로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; full mesh/environment는 `NOT_VERIFIED`다.
- `configs/poses.yaml`에 `SAFE_HIGH=RECORDED`, `HOME=NOT_RECORDED`로 저장했다. partial measured pose 저장/병합 테스트를 추가했고 관련 `8/8 PASS`, YAML validation 및 diff-check PASS. HOME 이동은 `NOT_RUN/NOT_AUTHORIZED`; [세션](sessions/2026-10-12-supervised-teleop-safe-high.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 WRIST_ESCAPE_Z_PLUS_20 실기 1 FAIL·postmortem

- 사용자 승인으로 `CURRENT→WRIST_ESCAPE_Z_PLUS_20` 범위만 시작했고, 첫 Wrist Flex target 1개만 송신한 뒤 `TCP_Z_DID_NOT_INCREASE`로 FAIL했다. 후속 target은 `0`, +30/+40, Lift/Elbow probe, HOME/SAFE_HIGH, approach/grasp/lift는 실행하지 않았다.
- Wrist Flex는 `-2.0°` 요청 대비 `-1.758242°`(`87.912%`) 의도 방향으로 정상 추종했다. 그러나 비명령 Lift/Elbow가 각각 `+0.527473°` drift했고, GRASP TCP는 `[-1.047681,-369.737597,+55.316363]`에서 `[-0.540109,-370.872873,+54.317570] mm`로 이동해 Z가 `-0.998793 mm` 감소했다.
- exact single-axis FK Z 기여는 Wrist `+4.320115`, Lift `-2.911619`, Elbow `-2.339636`, Pan `-0.000001`, Roll `-0.014873 mm`; 비선형 interaction `-0.052778 mm`다. 즉 Wrist responsiveness 부족이 아니라 Lift/Elbow passive drift가 Z 상승분을 초과한 것이 실패 원인이다.
- 새 fresh pose `[+1.362637,+18.681319,+15.252747,+6.549451,+16.131868]°`의 Z 민감도는 Pan/Lift/Elbow/Flex/Roll 각각 `+0.000016/-5.546797/-4.454551/-2.450446/+0.170971 mm/deg`다. 종료 후 read-only 3표본 raw는 `2117/2167/2157/2155/2048/446`으로 동일했다.
- 실측 50% 이상 반응한 Pan/Flex/Roll의 가장 유리한 `±2°` 조합에도 같은 Lift/Elbow drift를 적용하면 최대 모델 Z delta가 `-0.676135 mm`다. 따라서 `RESPONSIVE_ONLY_NEXT_STEP=NOT_FOUND`, `NEXT_LIVE_COMMAND=NONE`; 추가 실기 승인을 요청하지 않는다.
- 사용자 `STOPPED`와 feedback stillness로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. Moving all 0, Temperature `39/44/41/37/37/39°C`, Load before/after `-52/104/96/32/-28/0 → 0/36/36/24/0/0`; Load는 diagnostic only다. follower port는 read-only 종료 후 해제됐고 Phase C는 `HOLD`, full mesh/environment는 `NOT_VERIFIED`다.
- pure-offline postmortem 분석기와 fixture/test를 추가했고 신규+기존 선택 test `12/12 PASS`; 하드웨어 command/port open/Goal/Torque write `0`. [세션](sessions/2026-10-12-wrist-escape-plus20-attempt1.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 staged Wrist escape +10/+20/+30/+40 비교·+20 실기 준비

- 첫 +20 live 시도는 fresh read-only raw가 기준 `2118/2161/2151/2175/2049/446`과 정확히 일치한 뒤 시작됐지만, runner가 transport의 기존 `verify_start_pose()` latch를 arm하지 않아 첫 `send_goal()` 내부에서 `start_pose_not_verified`로 차단됐다. Goal write/motor target은 `0`, 사용자 `STOPPED` 후 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; 종료 후 read-only raw도 동일했다.
- 원인을 runner wiring 한 곳으로 국소 수정했다. fresh telemetry·현장 기준 비교 뒤 `verify_start_pose()`를 호출하고 다시 Goal/Present/Load/Temperature before-sample을 읽는다. fake transport도 latch가 없으면 송신 자체를 거부하도록 강화했다. 관련 `44/44 PASS`, Jetson 설치 SHA `07ae068e…a6759`, 설치 Python py_compile/dry-run PASS. 수정본 실제 재시험은 `NOT_RUN/NOT_AUTHORIZED`이며 재승인 필요다.
- 동일 settled pose `[+1.450549,+18.153846,+14.725275,+8.307692,+16.219780]°`에서 Lift/Elbow/Pan/Roll을 고정하고 Wrist Flex endpoint를 FK Z target으로 역산해 `WRIST_ESCAPE_Z_PLUS_10/20/30/40`을 비교했다. 네 후보 모두 max step `≤2°`, TCP Z 단조 증가, commanded table proxy 단조 비감소, servo bounds PASS, centerline self-collision proxy `64.775222 mm` PASS다. full mesh/environment는 계속 `NOT_VERIFIED`다.
- +10/+20/+30/+40의 waypoint 수는 `3/4/6/8`, Flex endpoint는 `+4.303791/+0.504669/-3.132839/-6.640868°`, XY drift는 `8.259301/15.432549/21.665359/27.063709 mm`다. 검증된 XY acceptance threshold는 없어 `NOT_DEFINED`로 유지했다.
- endpoint tool-axis 변화는 `4.003901/7.803024/11.440531/14.948560°`, jaw-axis 변화는 `3.844474/7.491990/10.983738/14.350370°`, table margin은 `+10.657363/+20.657363/+30.657363/+40.657363 mm`다. +20은 +40보다 XY/orientation 변화가 명확히 작고 모든 수치 proxy를 통과하므로 첫 staged live 후보로 추천한다.
- +20 전용 runner는 live fresh feedback에서 목표 Z를 고정한 뒤 매 step을 actual pose 기준으로 다시 계산하고 Wrist Flex만 `≤2°` 송신한다. 각 step 후 intended direction·`≥50%` movement, TCP Z 증가, uncommanded drift `≤1°`, Temperature `≤55°C`, fresh/communication/settle, servo bounds, table proxy 비악화, centerline self-collision proxy를 검사한다. Load는 signed before/after/delta 진단값이며 numeric gate가 아니다.
- 첫 step FAIL이면 `stop_commands()`로 후속 target production을 latch-off하고 torque/현재 Goal을 유지한다. +30/+40 자동 continuation, Lift/Elbow probe, HOME/SAFE_HIGH 경로는 코드에 없다. +20 PASS 뒤에도 fresh state를 읽고 멈춘 후 별도 offline sensitivity/probe 계획만 수행한다.
- 관련 unit/regression `44/44 PASS`, CLI dry-run은 `no port opened; no send_action` PASS. 실제 hardware/port/Goal/Torque 명령 `0`, +20 실기 `NOT_RUN/NOT_AUTHORIZED`, Phase C `HOLD`, full mesh `NOT_VERIFIED`. [세션](sessions/2026-10-12-wrist-escape-plus20-ready.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 Load 비게이트 정책·RESPONSIVE_JOINT_ESCAPE dry-run

- `verified_abs_load_limit=NOT_DEFINED`를 유지하면서 `Present_Load`를 signed before/after/delta 진단값으로만 기록하도록 escape 판정을 수정했다. 상한이 없으면 `load_gate_enabled=false`, `load_gate_result=NOT_APPLICABLE_NOT_DEFINED`이며 PASS/FAIL에 관여하지 않는다. 향후 검증 상한이 명시되면 기존 optional absolute gate는 동작한다. Temperature `≤55°C`, fresh/communication/settle, commanded direction·50% movement, TCP Z 증가, non-commanded drift gate는 유지한다.
- 이 정책 수정은 과거 `SAFE_ESCAPE_2DEG`를 재분류하지 않는다. Lift `0%`, Elbow `8.791%`이므로 결과는 계속 `FAIL / NO_EFFECTIVE_MOVEMENT`; Phase C는 `HOLD`, `>2°` 확대 없음이다.
- 실제 종료 pose `[+1.450549,+18.153846,+14.725275,+8.307692,+16.219780]°`에서 GRASP TCP는 `[-1.047681,-369.737597,+55.316363] mm`, table reference 대비 `+0.657363 mm`다. 중앙차분 FK Z 민감도는 Pan/Lift/Elbow/Flex/Roll 각각 `+0.000016/-5.527556/-4.451049/-2.424472/+0.169191 mm/deg`다.
- 실제 2° 시험의 축별 단독 FK 기여를 before pose에서 재계산하면 Pan `+0.000017`, Lift `0`, Elbow `+0.770339`, Flex `+3.771877`, Roll `+0.260049 mm`다. 총 실제 Z 증가 `+4.820224 mm` 중 Wrist Flex가 지배적이므로 Lift/Elbow/Pan/Roll을 고정하고 Wrist Flex만 FK 목표 Z로 역산했다.
- `+20/+30/+40 mm` 후보는 각각 Flex endpoint `+0.504669/-3.132839/-6.640868°`, waypoint `4/6/8`, max step `1.950756/1.906755/1.868570°`, max XY drift `15.432549/21.665359/27.063709 mm`다. 모두 Z 단조 증가, commanded table proxy 비악화, servo PASS, centerline self-collision proxy `64.775222 mm` PASS다. full mesh/environment collision은 계속 `NOT_VERIFIED`, excessive XY drift 수용 한계도 `NOT_DEFINED`다.
- 당시 `table reference +40 mm` intermediate 비교에서는 Z+40이 기준을 만족했지만, 후속 staged 지시로 **첫 live 후보는 Z+20으로 대체**됐다. Z+40은 비교 자료일 뿐 motion 승인이나 첫 실기 후보가 아니다.
- 타깃 unit test `20/20 PASS`; hardware/port/Goal/Torque/teleop/HOME/SAFE_HIGH 명령 `0`. [세션](sessions/2026-10-12-responsive-joint-escape-offline.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 SAFE_ESCAPE_2DEG Phase-B postmortem·Phase C HOLD

- Phase C는 `HOLD`로 고정했다. 저장된 실기 전/후 feedback만 사용해 2° 단일 target의 실제 이동량을 재구성했다. Pan/Flex/Roll은 요청량의 `52.75/79.12/79.12%`를 의도 방향으로 이동했지만, Lift는 `0%`, Elbow는 `8.79%`에 그쳤다. 따라서 전체 실패는 50% 기준 바로 아래의 경계 사례가 아니라 `NO_EFFECTIVE_MOVEMENT`(지배적 병목 Lift/Elbow)이다.
- GRASP TCP는 `[+5.406137,-365.783675,+50.496139]`에서 `[-1.047681,-369.737597,+55.316363] mm`로 변해 Z가 `+4.820224 mm` 상승했다. 즉 escape 방향의 부분 효과는 있었지만 commanded 전 축의 유효 이동은 아니다.
- Jetson 실제 설치본 LeRobot `0.6.0`, `feetech-servo-sdk 1.0.0`을 read-only로 대조했다. STS3215 `Present_Load`는 address `60`, 2-byte read-only이며 driver의 sign bit `10` sign-magnitude decode 결과 표현 가능 raw 범위는 `-1023…+1023`이다. 부호는 firmware direction bit를 음/양으로 decode한 것이며 물리 CW/CCW·위험 방향은 설치 코드에 정의되지 않았다.
- 설치 LeRobot/LeLab, repository config/driver/docs에 `Present_Load`를 torque/current/백분율로 변환하는 식, nominal/allowed 범위, safety threshold는 없다. Follower configure의 gripper-only `Max_Torque_Limit=500`, `Protection_Current=250`, `Overload_Torque=25`와 SDK `ERRBIT_OVERLOAD=32`는 서로 다른 보호 설정/상태 bit이며 `Present_Load` numeric cutoff의 근거가 아니다. arm에 적용된 검증 상한도 없다.
- `verified_abs_load_limit=NOT_DEFINED`를 유지한다. 권장은 근거 없는 `Present_Load` 절대값을 PASS gate에서 빼고 진단 telemetry로만 남기는 후속 **code-only** 수정이다. 단, 이를 적용해도 이번 2° 시험은 Lift/Elbow 실제 이동 미달로 FAIL이며 Phase C는 계속 HOLD다.
- 이번 postmortem은 로컬 FK·저장 로그·SSH 소스 열람만 수행했다. follower serial open, Goal/Torque write, motor command, teleop, service restart는 모두 `0`; [세션](sessions/2026-10-12-safe-escape-phase-b-postmortem.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 SAFE_ESCAPE 실제-이동 판정·HOME 복귀 API Phase A/D

- `SAFE_ESCAPE_2DEG` 실기 1회의 종료 후 read-only 3표본은 Present raw `2118/2161/2151/2175/2049/446`, calibrated `[+1.450549,+18.153846,+14.725275,+8.307692,+16.219780]\u00B0`, gripper `2.019584%` 로 동일했다. Goal raw는 `2128/2138/2130/2170/2053/446`, Goal−Present는 `+10/-23/-21/-5/+4/0 raw`, 6축 Torque=1, Moving=0이다.
- 2° 요청 대비 실제 이동률은 Pan `52.7%`, Lift `0%`, Elbow `8.8%`, Flex `79.1%`, Roll `79.1%`다. GRASP TCP Z는 `50.496139→55.316363 mm` (`+4.820224 mm`)로 증가했지만 commanded Lift/Elbow가 50% 이동 조건을 만족하지 못해 **Phase-B `SAFE_ESCAPE_PASS=false`**다. 추가 target은 송신하지 않았다.
- 종료 텔레메트리는 Load `-52/104/96/32/-28/0`, Temperature `38/40/39/36/37/40 \u00B0C`다. 사용자 `STOPPED`와 feedback stillness로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; follower port는 read 종료 후 privileged `fuser rc=1` 무점유다.
- Phase A에서 escape PASS를 final target tolerance와 분리했다. commanded 축별 의도 방향·50% 이상 실제 이동, GRASP TCP Z 증가, non-commanded drift `≤1°`, Temperature `≤55°C`, fresh/communication/settle를 검증한다. Shoulder Lift/Elbow terminal tolerance는 `1.5°`, Pan/Flex/Roll은 기존 `0.5°`, gripper는 `1.0 pp`로 분리하되 escape PASS gate로 사용하지 않는다.
- 저장소와 문서에서 검증된 Load 상한을 찾지 못했다. production config의 `verified_abs_load_limit=null`, 판정은 `NOT_DEFINED`/fail-closed다. synthetic test의 `120`은 테스트 주입값일 뿐 production 설정이 아니다.
- `read_escape_telemetry()`는 과거 group status packet 오판을 반복하지 않도록 Goal/Present/Moving/Load/Temperature를 축별로 개별 read한다. runner는 target 1회 송신 후 0.5초 이상 settle을 관찰하고 FAIL이면 command production을 latch-off하며 torque/Goal을 변경하지 않는다.
- Phase C용 3회 raw/degree/FK 평균·표준편차 저장 helper를 추가했지만 HOME/SAFE_HIGH 실측은 **NOT_RUN**, `configs/poses.yaml`은 수치를 추정해 생성하지 않았다.
- Phase D의 offline `go_home_safe()`는 `CURRENT→(필요 시 SAFE_ESCAPE)→SAFE_HIGH(Pan 제외)→Pan alignment→HOME` 순서만 허용하고, low TCP에서 검증된 escape가 없으면 fail-closed한다. 루트는 기존 bounded interpolation(`≤2°`)을 재사용하며 gripper를 유지한다. segment 예외/실패 시 `stop_commands()` 후 뒤 segment를 실행하지 않고, `attempt_safe_recovery()`는 정상 communication/feedback·planning-only failure·별도 사용자 승인을 요구하는 함수로 분리했다.
- 타깃 테스트 `42/42 PASS`, py_compile/diff-check PASS. 전체 suite는 `385` tests 중 `380 PASS`, 본 작업과 무관한 샌드박스 socket bind 4건과 미설치 `websocket` 1건으로 `5 ERROR`; 신규 타깃 테스트 failure는 없다. [세션](sessions/2026-10-12-safe-escape-phase-a-safe-home.md). hardware command `0`, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 SAFE_ESCAPE_2DEG fresh rebase·실기 준비

- 직전 사용자 현장 확인 이후 모터/토크/USB 동작 없이 teleop/recording/inference inactive, 관련 worker 없음, canonical follower `/dev/ttyACM1=5AE6058306`, privileged pre/post `fuser rc=1` 무점유를 재확인했다.
- write/sync_write/enable_torque/disable_torque/send_action을 예외로 차단한 read-only 세션의 0.25초 간격 3표본은 동일했다. fresh arm은 `[+0.395604,+18.153846,+14.901099,+9.890110,+14.637363]°`, gripper `2.019584%`, raw `2106/2161/2153/2193/2031/446`; 6축 torque=1, moving=0, write attempt=0이다.
- 기존 escape 방향 `(+,-,-,-,+)`과 정확히 `2°`를 fresh pose에 적용한 단일 target은 `[+2.395604,+16.153846,+12.901099,+7.890110,+16.637363]°`, gripper hold `2.019584%`다. 설치 bus의 read-only `_unnormalize` 결과 target raw는 `2128/2138/2130/2170/2053/446`, current 대비 delta는 `+22/-23/-23/-23/+22/0 raw`다.
- target GRASP TCP는 `[-7.174142,-378.973903,+75.993672] mm`, commanded-point table proxy margin `+21.334672 mm`, segment centerline self-collision proxy `64.775222 mm`, servo margin `80.109901°`다. 시작 virtual GRASP point의 single-P1 proxy는 계속 음수이고 full mesh collision은 `NOT_VERIFIED`; 기존 table/GRASP TCP/C XY/endpoint 판정은 변경하지 않았다.
- runner를 `SAFE_ESCAPE_2DEG` 전용으로 제한하고 승인 문구를 `RUN SAFE ESCAPE 2DEG ONLY`로 분리했다. 단 한 target, final tolerance `0.5°`, gripper hold, start drift gate, approach/grasp/lift/automatic continuation 없음은 유지했다. fake tests `18/18 PASS`, py_compile/diff-check PASS, Jetson SHA 일치 dry-run PASS; dry-run 종료 후 follower 무점유다.
- 실제 motor command `0`, 실기 `NOT_RUN/NOT_AUTHORIZED`; 다음 단계는 별도 승인 후 first target 1개뿐이다. [세션](sessions/2026-10-12-safe-escape-2deg-ready.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 SAFE_ESCAPE static-deadband 후보 1.5/2.0/2.5° 오프라인 비교

- 하드웨어에 접근하지 않고 직전 escape 종료 후 read-only pose `[+0.307692,+18.153846,+14.813187,+9.890110,+14.637363]°`/raw `2105/2161/2152/2193/2031`에서 기존 escape 방향 `(+,-,-,-,+)`을 유지한 1.5/2.0/2.5° 단일 target만 비교했다. GRASP TCP, C XY, endpoint, table-collision 판정, tolerance, raw feed-forward는 변경하지 않았다.
- 전체 `PRE_APPROACH_PASS`를 낸 WRIST_DELAY_25 로그의 가장 근접한 coupled window waypoint 50–53에서 Elbow load `52–68`이었다. Goal−직전 Present `-18/-20/-23/-22 raw`에서 Present가 목표 방향으로 `7/6/10/12 raw` 이동했다. 반면 같은 로그의 후반 hold에서 Elbow gap `10–14 raw`, load `52–68`은 정체했다. 직전 escape의 `-12 raw/load 60/이동 0`과 일치하는 경계다.
- `SAFE_ESCAPE_1P5DEG/2DEG/2P5DEG` 예상 raw delta는 각각 Pan/Lift/Elbow/Flex/Roll `[+17,-18,-18,-18,+17]`, `[+22,-23,-23,-23,+22]`, `[+28,-29,-29,-29,+28]`이다. target P1-point proxy margin은 `+15.219524/+21.746304/+28.364475 mm`, 각 segment centerline self-collision proxy는 `64.775222 mm`, servo margin은 `80.197813°`.
- 1.5°는 Elbow 실측 성공 경계 `18 raw`에 정확히 걸려 여유가 없고, 2.0°는 `23 raw`로 실제 성공 window의 강한 추종 표본과 일치하며, 2.5°는 더 큰 변화를 정당화할 추가 실측 근거가 없다. 따라서 **최소 효과 후보는 `SAFE_ESCAPE_2DEG`**로 추천한다. Lift의 현재 방향/Load가 일치하는 성공 표본은 없어 실기 성공은 아직 `NOT_VERIFIED`.
- 세 후보 모두 현재 시작 virtual GRASP-point를 포함한 segment minimum P1 proxy는 `-3.777924 mm`; 이는 기존과 같은 frame-vs-single-plane 판정으로 되돌림 없이 유지한다. full mesh collision은 `NOT_VERIFIED`. actual motor command `0`, 실기 `NOT_RUN/NOT_AUTHORIZED`. [세션](sessions/2026-10-12-safe-escape-deadband-candidates.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 SAFE_ESCAPE_1DEG 실기 1 — 단일 target 송신 후 final tolerance ABORT

- 사용자의 `RUN SAFE ESCAPE ONLY` 명시 승인으로 fresh-relative escape target 하나만 송신했다. runtime fresh start arm은 `[-0.131868,+18.153846,+14.813187,+10.681319,+14.109890]°`, target은 `[+0.868132,+17.153846,+13.813187,+9.681319,+15.109890]°`; 축별 step은 `+1/-1/-1/-1/+1°`, gripper는 `2.019584%` hold였다.
- 송신 전 GRASP TCP는 `[+2.480205,-371.439797,+61.412228] mm`, single-P1 proxy margin `+6.753228 mm`, installed URDF SHA/servo bounds/start drift gate를 통과했다. full mesh는 여전히 `NOT_VERIFIED`.
- 단 한 target 후 final error는 Pan `-0.560°`, Lift `+1.000°`, Elbow `+1.000°`, Flex `+0.209°`, Roll `-0.473°`, gripper `0` 이었다. arm final tolerance `0.5°`를 Lift/Elbow/Pan이 통과하지 못해 `safe_escape_failed:joint_target_timeout` ABORT; `SAFE_ESCAPE_PASS` 아님. 추가 target, approach, grasp, lift는 송신하지 않았다.
- 사용자 `STOPPED`와 encoder stillness로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. 종료 후 read-only 3회 fresh pose는 `[+0.307692,+18.153846,+14.813187,+9.890110,+14.637363]°`/gripper `2.019584%`로 동일했다. Goal raw는 `2111/2149/2140/2190/2036/446`, Present raw는 `2105/2161/2152/2193/2031/446`; 6축 torque=1, moving=0, Lift/Elbow load=60이다.
- Goal register는 target으로 갱신됐지만 Lift/Elbow는 1° target에서 fresh Present가 변하지 않았다. 원인을 확정하거나 tolerance/target/path를 수정하지 않고 자동 재시도를 중단했다. 후속 세 제어 inactive, follower `fuser rc=1` 무점유. [세션](sessions/2026-10-12-safe-escape-preflight.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 SAFE_ESCAPE_1DEG 현장 preflight·escape-only 준비

- 사용자가 현장에서 팔 정지, Shoulder/upper arm/forearm/wrist/gripper와 table 비접촉, 주변 clear를 확인했다. Jetson LeLab teleop/recording/inference는 모두 inactive, 관련 worker 없음, canonical follower `/dev/ttyACM1=5AE6058306`, privileged `fuser rc=1` 무점유를 확인했다.
- write/sync_write/enable_torque/disable_torque를 예외로 차단한 read-only 세션에서 0.25초 간격 3회 fresh Present_Position이 동일했다. arm calibrated는 `[-0.043956,+18.153846,+14.813187,+10.681319,+14.109890]°`, gripper `2.019584%`; raw는 `2101/2161/2152/2202/2025/446`이다. 6축 torque=1, moving=0, motor/Goal/Torque write `0`.
- 기존 저장 snapshot과 fresh pose의 최대 차이는 Elbow `1.054945°`이다. 기존 고정 target을 바로 쓰면 fresh 기준 Lift `1.791209°`, Roll `1.087912°` step이므로 송신하지 않았다.
- 동일한 local GRASP-TCP Z-gradient 방향을 fresh pose에서 재계산한 1축 타겟은 `[+0.956044,+17.153846,+13.813187,+9.681319,+15.109890]°`, GRASP TCP `[+1.945711,-371.411292,+61.412230] mm`, commanded-point P1-plane proxy margin `+6.753230 mm`, max step `1.0°`이다. 저장 시작 sample을 포함한 minimum proxy는 여전히 음수이며 full mesh는 `NOT_VERIFIED`다.
- 현장 확인 pose의 `0.5°` drift, fresh-relative 1° step, servo bounds, installed URDF SHA, commanded-point 양수 proxy를 송신 전에 차단하고 단 한 target만 실행하는 `live_c_safe_escape_only.py`를 추가했다. approach/grasp/lift/auto-continuation 경로는 없다. targeted+transport tests `17/17 PASS`, py_compile/diff-check, Jetson SHA 일치 dry-run `PASS`; dry-run 종료 후 follower `fuser rc=1`.
- 이 준비 후 별도 승인으로 실기 1을 수행했으며, 결과는 위 섹션의 final tolerance ABORT다. 설정/토크/기존 endpoint 변경 `0`, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 PICK table-collision proxy 국소 분리

- 새 GRASP TCP, C XY, pre-approach/approach endpoint는 변경하지 않고 89-target path의 table proxy만 재검산했다. 기존 `-6.207397 mm`는 명령 waypoint가 아니라 index 0의 저장된 시작 snapshot, 그것도 link geometry가 아닌 빈 `GRASP opening-center` 점에서 발생했다. 89개 실제 target 중 최저는 waypoint 1의 `-2.907942 mm`; waypoint 3부터 P1-height proxy가 양수다.
- waypoint 1 joints는 `[+0.098547,+16.374025,+16.318246,+10.769231,+13.786508]°`, GRASP TCP는 `[+7.214374,-361.926922,+51.751058] mm`다. 비-base moving-link centerline 중 최저 origin은 `shoulder` `Z=94.881700 mm`; 최저 collision-element origin center도 `shoulder/rotation_pitch_so101_v1.stl` `Z=48.481700 mm`이지만 mesh extent 최저 Z는 삼각형 STL이 없어 `NOT_COMPUTABLE`.
- 현 proxy table Z `54.659 mm`는 P1 단일 contact의 최대 Z다. 7개 contact FK Z는 `44.928…54.659 mm`로 벌어져 있고, P1–P4 LS plane의 current-XY Z는 `51.290 mm`, 전체 7점 LS plane은 `48.670 mm`다. 따라서 단일 P1 무한 평면은 보수적이지만, 저장 FK/contact 산포만으로 실제 table plane을 PASS로 확정할 수도 없다.
- 로컬에는 URDF가 참조하는 STL이 없고, 이전 기록의 Jetson uv-cache 실제 STL 경로를 read-only SSH로 찾으려 했으나 key/password 인증에서 거부됐다. service/USB/motor/Goal/Torque에는 접근하지 않았다. full mesh-vs-table 결과는 `NOT_VERIFIED`.
- endpoint를 고정하고 첫 target만 local GRASP-TCP Z gradient 방향으로 관절당 `1°` 이하 이동한 `SAFE_ESCAPE_1DEG` offline 후보는 first target `[+0.868132,+16.362637,+14.868132,+9.769231,+15.197802]°`, GRASP TCP `[+2.514583,-369.024235,+60.845159] mm`, 명령 target만의 최소 P1-plane margin `+6.186159 mm`다. 90 targets, max step `1.0°`, self centerline `64.775222 mm`, servo margin `24.375888°`, final error/orientation은 기존과 동일하다.
- 그러나 연속 경로는 음수 proxy인 저장 시작점에서 출발하므로 full-path minimum은 여전히 `-6.207397 mm`다. 시작 geometry와 mesh를 검증하지 않고 이를 “양수 margin path”로 승격할 수 없다. `SAFE_ESCAPE_1DEG`는 추후 초기 여유/full mesh 검증을 전제로 한 단일 추천 후보이며 `motion_authorized=false`다. 세션: [PICK table proxy 분리](sessions/2026-10-12-pick-table-collision-proxy.md). actual motor command `0`, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 PICK GRASP TCP 분리·orientation-aware IK dry-run

- 기존 pivot offset `[-51.748354,-73.033741,-54.531737] mm`를 `calibration_pin_tcp_offset_gripper_mm`로 보존하고, PICK에만 nominal opening-center offset `[-4.748354,-12.033741,-124.531737] mm`를 사용하도록 TCP frame을 코드에서 분리했다. 기존 vision IK는 `--grasp-tcp-offset-mm` 명시 없이 calibration PIN을 PICK TCP로 대신하지 않는다.
- C robot XY `[-62.635354,-295.315566] mm`와 Z `100/80 mm`를 그대로 사용했다. 실제 C grasp/slight-lift가 사람에게 확인된 2026-10-09 trace `seq=60668` feedback orientation을 reference로 삼아 5-DoF pose branch를 찾은 뒤 위치를 독립 FK로 재검산했다.
- 새 pre-approach joints는 `[+14.845130,-16.993354,+70.591582,-37.176891,-12.536328]°`, approach는 `[+14.845119,-2.443040,+70.635112,-51.770491,-12.536312]°`다. 두 endpoint의 GRASP TCP 위치 잔차는 각각 `2.8e-8/2.3e-8 mm`, 실제 시연 grasp 기준 full orientation/tool-axis/jaw-X error는 approach에서 `3.090420°/3.089719°/0.673464°`다.
- 새 approach endpoint에서 C target까지 GRASP/PIN/origin 거리는 `0.000000023/104.067287/125.201883 mm`다. 저장된 마지막 follower snapshot 대비 max joint delta는 `62.539722°`(Wrist Flex), servo minimum margin은 `24.375888°`다. 해당 snapshot은 현재 fresh feedback이 아니다.
- Lift가 Elbow보다 약간 앞서고 Wrist Flex를 10% 지연하는 89-target dry-run path는 max step `0.988613°`, centerline self-collision proxy `64.775222 mm` PASS다. 그러나 nominal GRASP TCP min Z가 시작 snapshot의 `48.451603 mm`이고 과거 table-contact reference `54.659 mm`보다 `6.207397 mm` 낮아 environment proxy는 `BLOCKED`; mesh/full collision과 실물 TCP 정밀도는 `NOT_VERIFIED`다. 따라서 실기 승인은 요청하지 않는다.
- GRASP TCP Y 불확실성 `-13.034…-11.034 mm`에서도 endpoint 해는 존재했고 approach orientation error는 `3.278…2.903°`였지만, table proxy는 전 범위에서 동일하게 BLOCKED다. 세션: [PICK GRASP TCP IK dry-run](sessions/2026-10-12-pick-grasp-tcp-ik-dry-run.md). motor/port/Goal/Torque/camera/Jetson 접근 `0`, grasp/lift `NOT_RUN`, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 중간보고서 정량 근거 자료 작성

- 기존 저장 JSON/JSONL, `docs/STATUS.md`, 최신 세션 기록만 사용해 [중간보고서 정량 결과 자료](REPORT_EVIDENCE_2026-10-12.md)를 작성했다. 신규 카메라 수신, SSH/Jetson 접속, serial bus, motor/Goal/Torque, service restart는 모두 `NOT_RUN`이다.
- live C 검출·Table→Robot 후보 transform·PIN TIP pivot TCP·TCP frame mixing·coarse GRASP TCP 후보·pre-approach 경로 실기 결과를 보고서용 표, 수식, 정량 결과 10개, 설명문, 그림/표 캡션으로 정리했다. 모든 숫자에는 내부 source ID를 연결했고, 원자료에 없는 값은 `N/A`로 유지했다.
- Table→Robot은 약 305 mm 1회 실측 기반 `CANDIDATE`, GRASP TCP는 orientation/collision/최종 실측 `NOT_VERIFIED`, 새 TCP 실제 적용·grasp·lift는 `NOT_RUN`으로 명시했다. `WRIST_DELAY_25`의 `PRE_APPROACH_PASS`와 야간 종료의 `physical_stop=NOT_VERIFIED`도 분리 기록했다.
- Markdown/diff 검사 완료. 문서 변경은 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 사진 기반 PIN→opening center coarse TCP 후보

- 사용자가 불명확했던 `LEFT/UP` 설명을 첨부 사진 기준으로 정정했다. 사진 평면의 gripper longitudinal `70 mm`, 그에 수직인 사진 평면 방향 `47 mm`, PIN TIP까지의 제3축 높이 `60–62 mm`다. 하드웨어에는 접근하지 않았다.
- URDF/mesh에서 Wrist_Roll local `Z`가 공구 길이축이고 gripper/jaw는 origin에서 local `-Z`로 뻗는다. Jaw 회전축은 gripper local `-Y`이므로 사진 평면은 local `X–Z`, 사진 법선은 local `Y`다. 따라서 PIN TIP→opening center는 `+X=47`, `+Y=60–62`, `-Z=70 mm`로 대응한다.
- midpoint `+Y=61 mm` 후보는 `pin_tip_to_grasp_center_gripper_mm=[+47,+61,-70]`, 기존 pivot `[-51.748354,-73.033741,-54.531737]`와 합친 `grasp_tcp_offset_gripper_mm=[-4.748354,-12.033741,-124.531737] mm`다. 높이 범위에 따른 Y 후보는 `-13.033741…-11.033741 mm`다.
- 이 매핑은 X/Y가 각각 gripper 중심면 근처 `-4.75/-12.03 mm`에 남고 Z가 jaw 방향 `-124.53 mm`가 된다는 URDF geometry와 일치한다. 반대 부호는 opening center를 lateral/out-of-plane으로 약 100 mm 이상 보내므로 기구 형상과 맞지 않는다.
- 기존 endpoint를 이 TCP로 재해석하면 C reference와 `104.052693 mm` 떨어진다. 동일 C reference에 새 TCP를 맞춘 **position-only offline IK**의 FK residual은 `0.000275 mm`다. orientation/collision/실측 정확도는 `NOT_VERIFIED`; 실제 endpoint 채택/배포/motor command는 `NOT_RUN`, 기존 calibration/C XY 불변, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 C approach TCP frame 혼용 수치 진단

- 하드웨어/포트/서비스에 접근하지 않고 기존 URDF·endpoint·pivot/table capture 코드와 저장 관절값만 오프라인 FK로 재검산했다. motor/Goal/Torque/gripper 명령은 `NOT_RUN`이다.
- pivot fit은 `p_fixed = t_base_gripper + R_base_gripper @ tcp_offset`으로 고정 물리점을 구한다. 5점 table capture도 같은 식으로 만든 `corrected_physical_tcp_xyz_mm`를 P1–P4의 robot-side fit점으로 사용한다. 사용자의 현장 절차상 그 고정 물리점은 gripper opening center가 아니라 장착한 금속 **PIN TIP**이었다. 따라서 기존 table→robot calibration과 C robot XY는 PIN TIP 기준이며 그대로 유지한다.
- live C 위치 IK도 동일한 offset `[-51.748354,-73.033741,-54.531737] mm`를 `gripper` link에 적용해 그 점을 target XYZ에 맞췄다. 현재 approach config도 같은 offset과 target `[-62.635354,-295.315566,80.0] mm`를 사용한다. 즉 현재 PICK endpoint는 PIN TIP을 C approach reference에 맞춘 것이다.
- 계획 endpoint FK에서 PIN TIP은 `[-62.633534,-295.292436,79.999429] mm`, C approach reference와 거리는 `0.023209 mm`다. 반면 실제 opening center가 코드에 정의되지 않아 정확한 `GRASP_TCP`는 `NOT_VERIFIED/NOT_COMPUTABLE`이다. URDF `gripper` link origin proxy는 `[21.041429,-276.316864,140.198749] mm`, reference까지 `104.817194 mm`, PIN보다 base Z가 `60.199320 mm` 높다. 이는 사용자의 약 `62 mm` 수직 관찰과 가깝다.
- 마지막 read-only settled feedback FK에서도 PIN TIP `[-62.264998,-290.445675,75.063370] mm`, reference 거리 `6.944301 mm`; `gripper` origin proxy `[21.191142,-273.431467,136.146259] mm`, 거리 `103.238547 mm`, PIN 대비 Z `61.082888 mm`다. target 대비 남은 Elbow 오차가 실제 PIN 위치 차이에 반영됐다.
- 판정은 `FRAME_MIXING_CONFIRMED_FOR_CURRENT_PICK_TARGET`: calibration/PIN TCP가 PICK/grasp TCP처럼 사용됐다. 단, 정확한 opening-center 3D offset은 아직 없다. `APPROACH_CONFIRMED/APPROACH_PASS`로 처리하지 않으며 approach 재실행, grasp, lift, calibration 재작업은 모두 `NOT_RUN`이다. 다음 구현 전에는 별도 `pin_tip_offset_gripper_mm`와 물리 검증된 `grasp_tcp_offset_gripper_mm`를 분리해야 한다. 상세: [TCP frame 진단](sessions/2026-10-12-c-approach-tcp-frame-diagnostic.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 approach ABORT 후 read-only 추가 수렴 확인

- 현재 follower pose와 Goal/Torque를 그대로 보존하고 motor command 없이 fresh Present_Position을 0.25초 간격 5회 read-only 측정했다. teleop/recording/inference inactive, pre/post privileged 두 포트 `fuser rc=1`; viewer motor write/torque change `0/0`이다.
- follower raw Pan/Lift/Elbow/Flex/Roll/Gripper는 5회 모두 `2100/2152/2164/2203/2026/446`; calibrated arm `[-0.131868,+17.362637,+15.868132,+10.769231,+14.197802]°`, gripper `2.019584%`로 정지했다.
- 기존 approach target 대비 fresh arm error는 Pan `-0.035382°`, Lift `-0.038342°`, Elbow `+1.461058°`, Flex `+0.120460°`, Roll `-0.379376°`. Elbow는 ABORT 시 `+1.812706°`에서 4 raw(`0.351648°`) 추가 수렴해 **기존 1.6° tolerance 안**으로 들어왔다.
- 따라서 tolerance 확대나 endpoint-local 보정 조건에 해당하지 않는다. pre-approach/start pose/calibration/C XY/path/IK는 변경하지 않았다. controller가 이미 ABORT한 뒤의 read-only 증거이므로 아직 `APPROACH_PASS`로 소급하지 않고, 현재 C/gripper 정렬과 과도한 접촉 없음의 사용자 육안 확인만 대기한다. `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 C approach-only 실기 1 — final Elbow timeout

- 사용자의 `RUN C APPROACH ONLY` 승인으로 현재 verified pre-approach pose에서 기존 C approach endpoint로 1회만 실행했다. preflight에서 teleop/recording/inference inactive, 관련 worker 없음, canonical follower `/dev/ttyACM1=5AE6058306`, privileged 포트 무점유, 배포 SHA 일치를 확인했다.
- fresh start `[-0.307692,+12.351648,+16.131868,+13.406593,+13.758242]°`, gripper `2.019584%`; start gate를 통과했다. 6/6 bounded waypoint를 송신했고 gripper는 전 구간 고정했다. grasp/lift는 실행되지 않았다.
- final Goal/Present raw는 Elbow `2147/2168`; final error는 Pan `-0.035°`, Lift `+0.050°`, Elbow `+1.813°`, Flex `+0.208°`, Roll `-0.379°`, gripper `0`. Elbow만 final tolerance `1.6°`를 `0.213°` 초과했다.
- 5초 final verification 동안 Elbow Present raw `2168`, error `1.813°`, Moving `0`, Present_Load `96`으로 유지되어 `final_joint_target_timeout` ABORT. 따라서 `APPROACH_PASS`가 아니다. tolerance/path/IK는 변경하지 않았고 자동 재시도하지 않았다.
- 사용자가 `STOPPED`를 확인했고 feedback 정지 검증도 통과해 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. post-run 세 제어 inactive, 관련 worker 없음, 두 follower/leader 포트 privileged `fuser rc=1` 무점유다.
- 원본 로그 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_approach_only_attempt1.jsonl`, SHA `a1d268e5…22ad`, 54행(`SEND 6 / PAUSE 47 / ABORT 1`). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 현장 복귀 — physical stop 복구, C approach-only 준비

- 사용자가 실제 팔 완전 정지, 그리퍼/작업대 및 전체 링크 비접촉, 야간 이후 자세 유지를 현장에서 확인했다. `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`로 복구했다.
- motor write/torque API를 차단한 read-only viewer로 canonical follower `/dev/ttyACM1` serial `5AE6058306`의 fresh 6축을 읽었다. raw는 Pan/Lift/Elbow/Flex/Roll/Gripper `2099/2095/2167/2233/2021/446`, calibrated는 `[-0.219780,+12.351648,+16.131868,+13.406593,+13.758242]°`, gripper `2.019584%`다. viewer motor write/torque change `0/0`, 종료 뒤 두 포트 privileged `fuser rc=1` 무점유다.
- 직전 `PRE_APPROACH_PASS` final feedback 대비 arm 차이는 `[+0.263736,+0.175824,+0.087912,-0.791209,0.000000]°`; 최대 `0.791209°`로 기존 `1.6°` 안이다. pre-approach를 재실행하지 않고 현재 pose를 approach 시작점으로 채택했다.
- 기존 C XY와 기존 approach endpoint `XYZ [-62.635354,-295.315566,80.0] mm`, arm `[-0.096486,+17.400979,+14.407074,+10.648771,+14.577178]°`만 사용하는 approach-only 하네스를 추가했다. fresh start drift gate `1.0°`, max step `1.0°`, final tolerance `1.6°`, gripper fresh hold이며 grasp/lift transition은 코드에 없다.
- fake live에서 6 waypoint, approach stage만 실행, gripper hold, `APPROACH_PASS`, drift 차단을 확인했다. 관련 runner `17/17` + continuous controller `8/8`, py_compile, 로컬/Jetson dry-run PASS. dry-run은 `no port opened; no send_action; grasp/lift unavailable`; 종료 뒤 follower 무점유다.
- Jetson 임시 시험 폴더 SHA: base runner `3c20caaf…aed1`, approach-only `0d288b08…21eb`, config `caa4d7e0…067f`. 실제 approach는 `NOT_RUN/NOT_AUTHORIZED`; 다음 명시 승인은 `RUN C APPROACH ONLY`다. `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-12 무인 야간 handoff 완료

- 무인 야간 모드 전환 뒤 실제 하드웨어 작업은 `NONE`이다. motor/send_action/Goal/Torque/teleop/replay/live/service/USB/calibration/camera·robot 재배치를 수행하지 않았다.
- 전환 직전 `WRIST_DELAY_25` 실제 실기는 71/71 target과 final 전 축 `1.6°` tolerance를 통과해 `PRE_APPROACH_PASS`였다. grasp/lift는 `NOT_RUN`; 현장 종료 확인은 `physical_stop=NOT_VERIFIED`다.
- actual log 재검산, FK/skeleton collision proxy, fallback 4종, STS3215 설치 설정 조사, A/B/C identity 전략, 바구니별 marker/opening 검증표, generic PICK/PLACE 상태기, offline 9조합 parser, 현장 go/no-go 및 10/17 critical path를 단일 문서로 정리했다.
- 핵심 회귀 `55/55`, 별도 OpenCV 환경의 vision/calibration `41/41`, py_compile, `git diff --check`가 통과했다. 전체 discovery 중 `websocket` 미설치와 sandbox localhost bind 제한 항목은 `NOT_RUN`으로 남겼다.
- 다음 현장 첫 행동은 모션이 아니라 사람이 팔 정지·현재 자세·비접촉을 확인해 physical-stop 상태를 복구하는 것이다. 기존 pre-approach를 자동 재실행하지 않는다.
- 상세: [2026-10-12 무인 야간 handoff](NIGHT_HANDOFF_2026-10-12.md). `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 WRIST_DELAY_25 실기 — PRE_APPROACH_PASS, 야간 hardware freeze

- 사용자의 명시 승인 `RUN LIVE C APPROACH`로 첨부된 야간 금지 지시가 도착하기 전에 pre-approach 1회를 실행했다. fresh start가 reference와 정확히 일치했고 71/71 target을 완료했다. final fresh error는 Pan `-0.469°`, Lift `+0.668°`, Elbow `+1.177°`, Wrist Flex `+1.265°`, Roll `-0.141°`; 전 arm joint가 기존 `1.6°` tolerance를 통과했다.
- 사용자가 실제 TCP가 C 위에 있고 안전하다고 `APPROACH CONFIRMED`를 입력해 실행기가 `PRE_APPROACH_PASS`를 출력했다. grasp/lift는 시작하지 않았다.
- 그 직후 사용자가 퇴근·무인 야간 모드를 지시했다. 종료 prompt의 현장 `STOPPED`는 더 이상 확인할 수 없어 이를 거짓 입력하지 않고 `UNATTENDED_NOT_VERIFIED`로 종료했다. 결과는 `physical_stop=NOT_VERIFIED`, 프로세스 exit 1이다. 이는 pre-approach joint/tolerance PASS를 취소하지 않지만 최종 현장 정지 확인은 아니다.
- post-run read-only 점검에서 teleop/recording/inference inactive, 관련 control worker 없음, follower `/dev/ttyACM1` 무점유 `FUSER_RC=1`을 확인했다. torque/Goal/service/USB 변경은 하지 않았다. 마지막 로그 waypoint 71은 Moving 전 축 0, Elbow/Wrist load `68/72`, error `1.177/1.265°`다.
- 원본 로그 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_delayed_wrist_fresh5_attempt1.jsonl` 72행. 오늘 밤 이후 실제 하드웨어 작업은 금지하며 read-only 로그 분석, 코드/fake test/dry-run/문서만 허용한다. 다음 현장 시작은 먼저 물리 정지·자세·비접촉을 사람이 재확인한 뒤 approach 단계 승인 여부를 판단한다. `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 fresh5 delayed-Wrist coupled path — dry-run 준비 완료

- BALANCED_COUPLED ABORT 뒤 follower를 read-only로 다시 읽었다. fresh 5축은 `[-7.252747,-38.989011,+57.274725,+68.791209,-7.604396]°`, TCP FK는 `[-37.325,-86.998,98.217] mm`, C까지 XY는 `209.850 mm`다. viewer motor write/torque change 0회, 종료와 포트 release, privileged `fuser rc=1`을 확인했다.
- 기존 C XY, endpoint `[-0.014220,+11.507515,+14.866481,+12.933013,+13.899293]°`, Pan/Lift/Elbow/Roll balanced coupling, 1° max step, 중간 Elbow/other limit `4.0/2.5°`, final `1.6°`는 그대로 두었다. 유일한 path 변수는 Wrist Flex schedule이다.
- Wrist delay `25/35/45%` 세 후보를 비교했다. fresh Wrist `68.791°`를 delay 지점까지 유지하고 coupled Wrist progress를 기존 대비 `0.75`로 낮춘 뒤, Shoulder/Elbow endpoint에서 남은 Wrist만 기존 endpoint로 마무리한다. coupled Wrist step 최대는 전 후보 `0.792°`다.
- `WRIST_DELAY_25/35/45`의 target 수/min TCP Z/final Wrist-only delta는 각각 `71/83.657/17.852`, `77/80.993/22.919`, `82/79.247/27.987`. 35/45%는 해당 delay 지점을 명시 stage로 포함해 실제 선형 보간도 그 지점까지 Wrist를 고정한다. 세 후보 모두 C XY distance 단조 감소, servo bounds, 전체 max step `≤1°`, exact endpoint를 통과했다.
- 가장 작은 변경이고 TCP Z 여유가 가장 큰 `WRIST_DELAY_25`를 추천한다. waypoint 누적 schedule은 `5/21/37/53/71`; Lift/Elbow/Wrist와 C 잔여는 `-34.623/52.390/68.791 → 198.064 mm`, `-19.246/39.882/56.122 → 142.954`, `-3.869/27.374/43.454 → 86.738`, `+11.508/14.866/30.785 → 33.513`, final Wrist `12.933 → 0.010 mm`다.
- planner 4/4 + prior coupled 3/3 + runner 13/13 + continuous 8/8 + staged planner 5/5 + FK 3/3 = `36/36 PASS`, py_compile/diff-check와 local dry-run PASS. Jetson config SHA `e6763906…e69`, unchanged runner SHA `1c81214b…dc71`; 설치 Python dry-run `no port opened; no send_action` PASS. teleop/recording/inference inactive, follower 무점유다.
- config `configs/live_c_approach_candidate_20261011_delayed_wrist_fresh5.json`은 배포됐지만 실제 motion은 `NOT_RUN/NOT_AUTHORIZED`; grasp/lift `NOT_RUN`. TCP FK/joint bounds proxy만 확인했고 swept-link/environment collision은 `NOT_VERIFIED`; `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 BALANCED_COUPLED 실기 — waypoint 15 Wrist Flex ABORT

- 사용자 승인으로 coupled-final pre-approach만 1회 실행했다. fresh start는 reference와 정확히 일치했고 71개 중 waypoint 15까지 송신했다. grasp/lift는 시작하지 않았다.
- safe anchor를 통과한 뒤 Shoulder Lift 상승/Elbow 감소 coupling은 진행됐다. waypoint 15에서 Elbow error `3.315740°`는 4° envelope 안이었으나 Wrist Flex error `2.676333°`가 2.5° envelope를 초과해 PAUSE했다.
- waypoint 15 target/feedback Wrist Flex는 `68.576414/71.252747°`, load `136`, Moving `0`. 1.008초 뒤 feedback `71.076923°`, error `2.500509°`, load `128`까지 줄었으나 limit를 `0.000509°` 넘긴 채 no-progress ABORT했다. Elbow는 같은 시점 error `3.227828°`, load `160`으로 limit 안이었다.
- ABORT target/feedback TCP는 `[-37.487,-91.213,99.751] / [-38.338,-77.355,98.176] mm`; C까지 XY 잔여 `205.646 / 219.311 mm`. 이전보다 실제 C 방향으로 전진했지만 `PRE_APPROACH_PASS`는 아니다.
- 결론: Shoulder–Elbow coupled 방향은 유효했으나 Wrist Flex를 anchor `80.5°`에서 coupled-25 `63.608°`로 같은 비율로 낮춘 schedule이 새 tracking/load 병목이다. tolerance/feed-forward/gain은 변경하지 않는다; 다음 최소 path 변수는 Wrist Flex 감소를 더 늦게 coupling하는 것이다.
- 사용자 `STOPPED`, `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; post-run teleop/recording/inference inactive, 관련 worker 없음, follower 무점유(`fuser rc=1`). 자동 재시도 없음, grasp/lift `NOT_RUN`; 원본 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_coupled_final_fresh4_attempt1.jsonl`; `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 fresh4 coupled-final path — dry-run 준비 완료

- strong-unload ABORT 뒤 read-only fresh follower는 `[-8.571429,-49.714286,+64.043956,+82.769231,-11.736264]°`; viewer write/torque change 0회, 포트 release 확인. 실제 정상 추종했던 waypoint 29 target `[-8.571429,-50,+64.897959,+80.5,-11.648352]°`를 safe anchor로 사용했다.
- anchor 이후 Shoulder Lift 진행률 대비 Elbow 진행률 exponent `1.0/1.15/1.3/1.5`의 balanced/mild/medium/strong lift-lead 네 coupled schedule을 FK 비교했다. 전 후보는 C까지 XY 거리 단조 감소, servo bounds, max step `≤1°`를 통과했다.
- 후보별 target 수/min TCP Z/joint route L2는 `71/95.721/110.042`, `71/90.511/110.173`, `71/86.020/110.497`, `72/80.988/111.100`. Elbow가 Lift 진행을 앞서지 않으면서 가장 짧고 TCP 높이가 가장 높은 `BALANCED_COUPLED`를 추천한다.
- 추천 schedule TCP/C XY 잔여는 anchor `[-37.123,-49.856,104.267]/246.782`, 25% `[-38.054,-109.517,98.356]/187.418`, 50% `[-42.292,-174.127,95.828]/122.885`, 75% `[-50.532,-237.992,96.568]/58.588`, 기존 endpoint `[-62.643,-295.322,99.992]/0.010 mm`다.
- runner의 staged intermediate 개수 계약만 기존 1–2개에서 1–6개로 확장했다. interpolation/송신/limit/tolerance는 변경하지 않았다. runner 12/12 + continuous 8/8 + coupled planner 3/3 + staged planner 5/5 + FK 3/3 = `31/31 PASS`, py_compile/diff-check와 로컬 dry-run PASS.
- Jetson runner/config SHA `1c81214b…dc71` / `bd068b73…b444`, 기존 runner backup `scripts/live_c_approach.py.pre-coupled-20261011`. 설치 Python py_compile/dry-run `no port opened; no send_action` PASS; teleop/recording/inference inactive, privileged follower `fuser rc=1` 무점유.
- C endpoint는 live YOLO frame의 C bbox center를 ArUco/table XY→scale/reflection→candidate transform으로 계산한 고정 robot XY다. 현재는 이동 중 YOLO feedback을 쓰는 continuous visual servo가 아니다. endpoint/C XY/calibration/final tolerance 1.6° 불변; 실제 motion `NOT_RUN/NOT_AUTHORIZED`, grasp/lift `NOT_RUN`, swept-link/environment collision `NOT_VERIFIED`, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 LIFT_NEG50 strong-unload 실기 — waypoint 34 ABORT

- 사용자 승인으로 strong-unload pre-approach만 1회 실행했다. fresh start는 reference gate 안이었고 105개 중 waypoint 34까지 송신했다. grasp/lift는 시작하지 않았다.
- Shoulder Lift를 먼저 `-50°`까지 올린 stage 1은 통과했고, Elbow relief 초반 target `70.776→65.878°`에서 Elbow error/load는 대체로 `0.50–0.89° / 36–56`으로 A2보다 크게 개선됐다.
- 그러나 stage 2 마지막 Elbow `60°` target에서 Goal/Present `2666/2717 raw`, error `+4.483516°`, `Moving=0`, `Present_Load=216`으로 PAUSE했다. 1.61초 뒤 Present `2712 raw`, error `+4.043956°`, load `196`까지 수렴했지만 4° envelope 바로 위에서 no-progress ABORT했다.
- ABORT feedback joints `[-8.571429,-49.714286,+64.043956,+82.769231,-11.736264]°`, TCP `[-37.402,-47.332,108.230] mm`; 기존 pre-approach까지 XY 약 `249.272 mm` 남았다. 즉 Lift-first는 효과가 있었지만, Lift `-50°`에서 Elbow를 `60°`까지 낮춘 stage 2가 과했다. 로그상 Elbow target 약 `64.898°`에서는 error `1.608°`, load `88`로 정상 추종했다.
- 사용자 `STOPPED`로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. 종료 후 teleop/recording/inference inactive, 관련 worker 없음, follower 무점유(`fuser rc=1`). 자동 재시도 없음, `PRE_APPROACH_PASS` 아님, grasp/lift `NOT_RUN`; 원본 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_strong_unload_fresh3_attempt1.jsonl`; `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 fresh3 stronger-unload staged path — dry-run 준비 완료

- A2 ABORT 뒤 read-only fresh follower는 `[-8.571429,-69.318681,+73.714286,+76.000000,-11.648352]°`, TCP `[-36.109100,-56.585056,84.951255] mm`였다. viewer motor write/torque change 0회, 종료 뒤 follower 포트 무점유다.
- Elbow를 fresh 값에 고정하고 Shoulder Lift만 `-65/-60/-55/-50°`로 먼저 올리는 네 후보를 비교했다. 모두 Pan/Roll 고정, strong-unload 구간 TCP min Z `84.951255 mm`, servo bounds, pre-final C 방향 proxy, max step `≤1°`를 통과했다.
- 실패 waypoint URDF gravity-moment proxy `0.366147 N·m` 대비 Elbow-relief 구간 최대 proxy는 각각 `0.351617/0.346093/0.338250/0.328863 N·m`. 실제 servo load의 대체 측정은 아니지만, 이전의 근소한 unload 재실패를 고려해 요청 범위에서 가장 큰 약 `10.2%` proxy 감소를 주는 `LIFT_NEG50`을 추천한다.
- 추천 경로: fresh current → `[-8.571429,-50.000000,+73.714286,+76.000000,-11.648352]` → `[-8.571429,-50.000000,+60.000000,+83.000000,-11.648352]` → 기존 pre-approach endpoint. 105 bounded targets, path min TCP Z `84.951255 mm`, minimum servo margin `15.615°`; endpoint/tolerance/C XY/IK/calibration 불변이다.
- 로컬 runner 11/11 + continuous 8/8 + planner 5/5 + FK 3/3 = `27/27 PASS`, py_compile/diff-check PASS. Jetson config SHA `f4db0303…54a4`, runner SHA `e531e367…671d`; 설치 Python py_compile/dry-run `no port opened; no send_action` PASS. teleop/recording/inference inactive, follower 무점유(`fuser rc=1`).
- full swept-link/environment collision은 `NOT_VERIFIED`. 실제 pre-approach는 새 경로 승인 대기 `NOT_RUN`; grasp/lift `NOT_RUN`; `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 A2_MINIMAL staged pre-approach 실기 — waypoint 26 ABORT

- 사용자 승인으로 pre-approach만 1회 실행했다. fresh start는 offline reference와 정확히 일치했고 107개 중 waypoint 26까지 송신했다. grasp/lift는 시작하지 않았다.
- unload stage 1과 2는 진행됐으나 기존 endpoint로 향하는 첫 target에서 Elbow가 다시 정체했다. waypoint 26 target/Goal/Present는 `69.327640° / raw 2772 / raw 2822`, error `+4.386646°`, `Moving=0`, `Present_Load=212`였다. 1.013초 동안 progress가 없어 `following_no_progress_timeout`으로 ABORT했다.
- 마지막 target/feedback TCP는 `[-35.087,-66.839,92.101] / [-36.024,-56.479,84.936] mm`; 기존 pre-approach TCP까지 XY 거리는 각각 `230.139 / 240.322 mm`다. 따라서 C 근처에 가지 않은 것이 로그/FK와 일치하며, A2의 `Lift=-70°` unload가 Elbow 하중을 충분히 낮추지 못한 것이 이번 실패 지점이다.
- 사용자 `STOPPED`로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. 종료 뒤 teleop/recording/inference inactive, 관련 worker 없음, follower 포트 무점유(`fuser rc=1`). 자동 재시도 없음, `PRE_APPROACH_PASS` 아님, grasp/lift `NOT_RUN`; 원본 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_staged_fresh2_attempt1.jsonl`; `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 A2_MINIMAL staged pre-approach 배포·dry-run

- 이전 `A_MINIMAL` 실기는 fresh follower와 offline reference가 달라 첫 송신 전에 fail-closed했으며 motor command는 0회였다. read-only fresh follower `[-8.571429,-81.010989,+82.505495,+64.923077,-11.560440]°`를 기준으로 경로만 재계산했다.
- 새 `A2_MINIMAL`은 `CURRENT → [-8.571429,-70.000000,+82.505495,+76.500000,-11.560440] → [-8.571429,-70.000000,+70.000000,+76.500000,-11.560440] → EXISTING_PRE_APPROACH`이며 107개 bounded target, max step `≤1°`다. endpoint/1.6° final tolerance/vision/IK/calibration은 변경하지 않았다.
- Jetson 설정 `configs/live_c_approach_candidate_20261011_staged_fresh2.json`을 배포했고 local/Jetson SHA `ed6cda0…ff27d`, staged runner SHA `e531e367…671d`를 확인했다. 설치 Python py_compile 및 dry-run `no port opened; no send_action` PASS.
- 사전점검에서 teleop/recording/inference 모두 inactive, 관련 제어 worker 없음, follower `/dev/ttyACM1` 무점유(`fuser rc=1`)였다. 실제 pre-approach는 새 경로 승인 대기 `NOT_RUN`; grasp/lift `NOT_RUN`; `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 staged pre-approach 승인 실행 — 첫 송신 전 차단

- 사용자 승인 `RUN LIVE C APPROACH` 뒤 A_MINIMAL staged plan 1회를 시작했다. teleop/recording/inference inactive, 배포 SHA 일치, follower port 무점유를 확인했다.
- follower 연결 직후 fresh arm과 offline reference의 차이가 `Pan +0.967°, Lift +13.714°, Elbow −5.451°, Flex −7.033°, Roll +3.605°`여서 1° 시작 gate가 `staged_reference_start_mismatch`로 차단했다. 특히 실제 자세는 이전 continuous trial이 멈춘 waypoint 14 부근이며, offline planner 입력으로 사용한 더 이전 자세가 아니었다.
- 차단은 controller 생성과 첫 `send_goal` 이전이다. motor target 0회, staged motion `NOT_RUN`, grasp/lift `NOT_RUN`; `STOPPED` 입력은 필요하지 않았다. 종료 후 follower `/dev/ttyACM1` 무점유, following JSONL 미생성 확인.
- 자동 재시도와 reference gate 완화는 하지 않았다. 다음 단계는 정확한 fresh pose를 read-only로 기록하고 그 pose에서 A 방식의 staged FK path를 다시 계산·검증하는 것이다. `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 C pre-approach staged load-relief path — offline 후보 확정

- 실제 모터/포트/Goal/torque에 접근하지 않고 waypoint 14를 재구성했다. target 5축 `[-8.292,-80.826,+78.546,+64.233,-11.286]°`, feedback `[-8.835,-81.011,+82.593,+64.923,-11.648]°`; pivot TCP FK target/feedback은 `[-32.262,-86.678,72.600] / [-32.880,-76.627,63.669] mm`다. Elbow를 78.5°까지 먼저 감소시키는 동안 Lift가 아직 −80.8°였다는 가설과 일치한다.
- 기존 endpoint `[-0.014,+11.508,+14.866,+12.933,+13.899]°`는 유지했다. 세 후보 모두 stage 1에서 Elbow/Pan/Roll을 고정하고 Lift와 최소 Wrist Flex만 먼저 올린 뒤, stage 2에서 Lift를 고정하고 Elbow를 감소시킨다. servo 범위, 1° bounded step, 0.1° FK 표본 TCP Z, final 전 C 방향 proxy를 통과했다. 이는 swept-link/environment collision 검증이 아니다.
- 추천 `A_MINIMAL`: `CURRENT → [-9.538,-75.000,+87.956,+78.500,-15.165] → [-9.538,-75.000,+70.000,+78.500,-15.165] → EXISTING_PRE_APPROACH`. 각 stage TCP는 `[-37.277,-22.262,66.245]`, `[-30.665,-61.613,91.718]`, `[-62.643,-295.322,99.992] mm`; segment minimum Z `54.842/66.245/91.718 mm`. 시작보다 먼저 낮아지지 않고 두 unload stage는 C 쪽으로 조기 진입하지 않는다.
- 초기 자동 검증에서는 B/C가 final 전 C 거리 proxy를 시작보다 `1.31/4.32 mm` 줄여 실패했다. stage 2 Wrist Flex를 최소 보정해 재검증했고 최종 4개 planner test + 기존 FK 3개 = `7/7 PASS`; py_compile/diff-check PASS. tolerance/raw feed-forward/gain/calibration/vision 변경 없음.
- 추천 A를 실행기가 두 intermediate를 순서대로 통과한 뒤 기존 endpoint에 도달하도록 최소 연결했다. 총 125개 bounded target이며, fresh arm이 분석 기준 시작 자세에서 축별 `1.0°`를 넘으면 첫 송신 전에 fail-closed한다. 실행기 첫 test는 최종 float exact equality 표현 차이로 1건 실패했고 1e-9 근사 비교로 정정했다. live runner 9/9 + continuous 8/8 + planner 4/4 + FK 3/3 = `24/24 PASS`.
- Jetson `/tmp/live-c-approach-20261011`에 기존 runner를 `scripts/live_c_approach.py.pre-staged-20261011`로 백업하고 staged runner/config만 배포했다. 로컬/Jetson SHA는 runner `e531e367…671d`, config `f5864894…1653`; 설치 Python py_compile 및 dry-run `no port opened; no send_action` PASS. 서비스/USB/follower/Goal/torque 접근 0회.
- 결과 `.local/c-red-pivot-tcp-table-20261011-s01/staged_load_relief_path_20261011.json`. 실제 staged pre-approach는 `NOT_RUN/NOT_AUTHORIZED`; grasp/lift `NOT_RUN`; `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 C pre-approach continuous-following 실기 1회 — waypoint 14 ABORT

- 사용자가 승인한 `live_c_pre_approach_only` 1회만 실행했다. 기존 C robot XY/IK endpoint/calibration/final tolerance `1.6°`는 변경하지 않았고 grasp/lift는 시작하지 않았다.
- fresh start는 `(Pan -9.538462, Lift -94.725275, Elbow +88.131868, Flex +71.956044, Roll -15.076923)°`, gripper `1.958384`; 107-waypoint 경로 중 waypoint 1–14만 송신됐다.
- waypoint 14 Elbow target/Goal raw/Present raw는 `78.545743° / 2876 / 2923`, following error `+4.047664°`, `Moving=0`, `Present_Load=200`이었다. 4.0° envelope 초과로 추가 송신 없이 `PAUSE`; 1.009초 뒤에도 raw/오차/Moving/Load가 동일해 `following_no_progress_timeout`으로 `ABORT`했다.
- 따라서 `PRE_APPROACH_PASS`가 아니며 자동 재시도하지 않았다. 사용자가 `STOPPED`로 현장 정지를 확인해 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; 종료 뒤 follower `/dev/ttyACM1`은 무점유(`fuser rc=1`)다.
- 원격 로그: `/tmp/live-c-approach-20261011/results/live_c_pre_approach_continuous_attempt1.jsonl` 16행. 코드/정책/torque/service 변경 없음; `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 C pre-approach bounded continuous-following 준비

- C robot XY `[-62.635354,-295.315566] mm`, 기존 IK endpoint `[-0.014220,+11.507515,+14.866481,+12.933013,+13.899293]°`, calibration, final arm tolerance `1.6°`는 변경하지 않았다. 중간 waypoint만 stop-and-wait에서 max step `1.0°`, cadence 최소 `0.2 s`, Elbow/other-arm following envelope `4.0/2.5°`의 continuous-following으로 변경했다.
- envelope 초과 시 추가 send 없이 PAUSE, 회복 시 RESUME, 3회 연속 error 증가·1.0초 no-progress·feedback/통신·비정상 target에서 ABORT한다. deadline catch-up/waypoint skip/burst는 없다. 최종 target에서만 기존 `1.6° + 0.1 s stable` gate를 적용한다.
- 로그는 waypoint/target joints/Goal raw/Present raw/following error/Moving/Present_Load/SEND·PAUSE·RESUME·ABORT를 JSONL로 매 event flush한다. PAUSE/ABORT 중 `send_goal` fall-through는 테스트에서 0회였다.
- fake-bus 요구 사항과 실제 current→endpoint 107-waypoint 전체 경로를 포함한 continuous 8개, plan 6개, 기존 staged 10개, transport 12개 = `36/36 PASS`; py_compile/diff-check PASS. 전체 경로 테스트 첫 실행은 최종 float의 표현 차이를 exact equality로 비교해 1건 실패했고, 9자리 근사 비교로 정정 후 통과했다.
- Jetson `/tmp/live-c-approach-20261011` 임시본 SHA는 continuous `c844e3ae…28`, runner `e532f86f…00`, transport `dc9639f5…16`, plan `58ae2933…93`; 설치 Python py_compile/dry-run PASS. LeLab teleop/recording/inference inactive, 관련 프로세스 없음을 확인했다.
- 실기 전 read-only follower 3표본은 동일한 `[-9.538462,-94.725275,+87.956044,+71.956044,-15.076923]°`, gripper `1.958384`; motor write/torque change 0회, 종료 후 `/dev/ttyACM1` 무점유 `fuser rc=1`. 실제 pre-approach/grasp/lift는 `NOT_RUN`; 현장 비접촉 확인과 명시 승인 대기, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 최종 9조합 목표 재고정

- 2026-10-17까지 `A/B/C × RED/GREEN/BLUE` 9개 명령 조합을 자동 pick-and-place하는 것이 최종 목표다. `C→RED`는 첫 end-to-end validation case이지 전용 route가 아니다.
- 최종 계약을 `detect/select object → object robot XY → generic PICK(object_xy) → select basket → basket robot XY → generic PLACE(basket_xy)`로 고정했다. motion/IK/planner가 object/basket identity로 trajectory를 hard-code하지 않는다.
- 기존 `medicine_fixed_slot_command.py`는 9조합 명령을 해석하고 `staged_cycle_execution.py`는 identity 비의존적이다. 반면 `live_c_approach.py`, `prepare_c_red_phases.py`, `c_red_*` 설정은 첫 검증용 하네스/과거 후보로만 격리하며 최종 planner로 승격하지 않는다.
- 단기 우선순위는 계속 `C→RED 전체 자동 사이클 1회 성공`이다. 성공 전 A/B/다른 바구니 실기로 분산하지 않는다. 구조 계약: [2026-10-17 목표](medicine-pick-place-target-20261017.md). 이 기록은 motion 승인이 아니며 실제 모터 명령 0회, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 current-near load-relieved IK dry-run

- 실제 모터 명령 없이 current follower `[-9.538,-94.725,+87.956,+71.956,-15.165]°`를 seed/비교 기준으로 사용해 C pre-approach IK branch를 multi-start로 탐색했다. follower port open, Goal/Torque write, motion은 모두 0회이다.
- 같은 XYZ의 position-only 1,712-start 탐색에서 max joint delta `40°` 이하 해는 없었다. 가장 가까운 position-only 해도 max `94.759°`였고 기존 tool-axis와 `36.546°` 달랐다. Candidate A는 tool-axis error `21.984°`라 orientation 보존 조건에서 제외했다.
- 기존 gripper local-Z tool-axis를 유지하고 그 축 주위 roll은 자유로 둔 2,408-start 탐색을 Z `100/110/120/130 mm`에서 수행했다. 각 Z에서 2개 branch가 확인됐고, 최선 max delta는 `105.536/101.290/97.348/93.751°`로 30–40° 목표를 만족하지 못했다.
- 요청된 사전식 목적(max delta → L2 → Elbow)의 수치상 최선은 Z+30 mm: XYZ `[-62.635,-295.316,130.000] mm`, joints `[-0.014,-0.974,+41.754,-1.472,+56.754]°`, delta `[+9.524,+93.751,-46.202,-73.428,+71.919]°`, max/L2 `93.751/146.896°`, position residual `<0.001 mm`, tool-axis error `0.000°`, minimum servo calibration margin `55.257°`다. `BEST_CURRENT_NEAR_IK=Z130`으로 기록하지만 원하던 current-near 범위는 아니므로 실기는 `NOT_RUN/NOT_AUTHORIZED` 유지한다.
- 결과: `.local/c-red-pivot-tcp-table-20261011-s01/current_near_load_relief_ik_search_20261011.json`; grasp/lift `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 directional HOLD와 torque 유지 분리 확인

- 현재 Jetson 설치 `lelab/teleoperate.py` SHA `e9300fc08f9225afd03a8503542fe6268474d4182077424dcb5ca9a120c77bd2`: directional guard import(31행), relative_start 호출(304행), temporary-align 호출(319행)이 존재한다. helper SHA `1ca311d0cbf06db857992b64ed09d3ccb7230c72ef4df77137637a7a77204b09`의 160–162행은 HOLD일 때 `return None`, SEND일 때만 `robot.send_action`이며 torque register를 변경하지 않는다.
- 실제 8000 PID 545264 환경은 `LELAB_TELEOP_MODE=relative_start`, `LELAB_TEMP_WRIST_ALIGN` 미설정이다. **코드상 별도 결함**: relative branch 뒤 공통 318–323행으로 이어져 TEMP_WRIST_ALIGN 미설정이면 무조건 `robot.send_action(action)`을 실행한다. 따라서 guard 존재와 실제 HOLD 송신 차단 보장은 다르다. 런타임 재현/수정은 NOT_RUN.
- `teleoperate.py:169`의 `disable_torque_on_disconnect=False`는 현재 설치본에 유지된다. follower connect→configure→torque_disabled 컨텍스트 finally에서 enable_torque가 호출되고, 종료는 safe_disconnect_device→SOFollower.disconnect→bus.disconnect(False)로 torque-disable 없이 포트만 닫는다. 최근 pre-approach transport도 동일하게 disconnect(False)를 사용하며 stop_commands는 송신 차단 플래그만 설정한다.
- 현재 teleop inactive, privileged follower `/dev/ttyACM1` fuser rc=1(무점유), LeLab PID 545264/3467의 ttyACM FD 없음. 사용자 보고와 이전 개별 read의 6축 Torque_Enable=1은 서보에 남은 Goal/Torque 상태로 유지되는 동작과 부합한다. 현재 레지스터를 재측정하지 않았으므로 새 6축 측정값으로 주장하지 않는다. 마지막으로 torque ON을 쓴 정확한 시점/주체는 코드만으로 확정 불가하나, 유지되는 이유는 위 종료 정책으로 설명된다.
- 코드·설정·프로세스 메타데이터만 확인. serial open/Goal write/torque change/service restart 0회. 이슈는 로컬 기록, 원격 이슈 갱신 NOT_RUN; NOT_COMMITTED/NOT_PUSHED.
- 위 HOLD fall-through만 최소 수정했다. relative guarded send를 `dispatch_guarded_relative_action()`으로 분리했고 HOLD는 이전 target 상태를 보존한 채 반환한다. absolute/temporary-align 송신 블록은 `relative_mode`의 명시적 `else`로 이동해 relative cycle에서 direct `robot.send_action(action)`에 도달하지 않는다. `disable_torque_on_disconnect=False`와 torque 처리 경로는 그대로다.
- 로컬 fake tests `test_relative_start_teleop` 14/14, 기존 guard tests 14/14 PASS. 요구 다섯 조건은 HOLD send 0, SEND 1, ABORT send 0, HOLD 다음 away SEND 1, HOLD register write 0으로 확인했다. 설치본에서도 같은 fake test 및 AST 검사 `direct_send_only_in_relative_else=PASS`.
- Jetson 설치본을 백업 후 `teleoperate.py` SHA `85b694146cdfcd9a54e75fa8a67b78aaaf6d802db2be4f09cfd4d28ba51d3c16`, `relative_start_teleop.py` SHA `ff9d1a7874e680bd5e1690d09790ee36f90ae2a918d39d449d7d6725229185a5`로 교체했다. 백업은 `/home/jetson3/lelab-source-backups/2026-10-11-hold-fallthrough/`에 원본 SHA 이름으로 보존했다. LeLab service만 재시작해 PID `545262→548555`; health 정상, relative_start 환경 유지, teleop/recording/inference inactive, follower fuser rc=1 무점유. 실제 motor/Goal/torque write 0회, 실기 HOLD 검증 NOT_RUN. 패치 `patches/lelab-20261011/teleoperate-relative-hold-no-fallthrough.patch`; NOT_COMMITTED/NOT_PUSHED.

## 2026-10-11 C pre-approach 중단 후 follower HOLD 상태 정정

- 승인된 `live_c_pre_approach_only` 실행은 target 도달 전에 중단됐다. 최신 실행은 `joint_target_timeout`이며 마지막 오차는 `shoulder_pan +0.015°, shoulder_lift -1.038°, elbow_flex +2.830°, wrist_flex +0.404°, wrist_roll -0.458°, gripper +0.000`이었다. 실제 C approach/grasp/lift는 완료되지 않았고 자동 재시작은 `NOT_RUN/NOT_AUTHORIZED`다.
- 최초 group `sync_read`가 `Incorrect status packet`을 냈고, 뒤의 group read에서 `Torque_Enable=0`, `Goal_Position=0`이 반환돼 torque OFF로 오판했다. 해당 0 값은 폐기한다. 축별 개별 read로 재확인한 현재 follower raw는 `Pan 1977/1979/1/0/-20`, `Lift 861/871/1/0/-52`, `Elbow 3090/3094/1/0/+24`, `Flex 2729/2730/1/0/0`, `Roll 1655/1654/1/0/0`, `Gripper 445/445/1/0/0` (`Present/Goal/Torque/Moving/Load`)이다. 1초 동안 전 축 Present span `0`; Goal−Present는 `+2/+10/+4/+1/−1/0 raw`다. 따라서 **6축 모두 torque ON, goal≈present, 정지 HOLD**로 판정하며 `recover_follower_hold.py` 재실행은 불필요하다.
- teleop/recording/inference는 모두 inactive이고, live approach/recovery/replay/teleoperate 프로세스가 없으며 LeLab PID의 `/proc/.../fd`에는 `/dev/ttyACM1`이 없다. privileged `fuser`도 read 종료 뒤 무점유(`rc=1`)였다. 서비스나 robot object가 follower connection을 유지하는 상태가 아니라, servo에 남은 Goal/Torque register가 독립적으로 hold 중이다.
- 설치 `teleoperate.py`는 follower config에 `disable_torque_on_disconnect=False`를 준다. 연결 시 `SO101Follower.configure()`의 `torque_disabled()`가 설정 동안 disable 후 finally에서 enable하고, 종료 시 `_safe_disconnect→safe_disconnect_device→SO101Follower.disconnect→bus.disconnect(False)`로 포트만 닫아 torque를 유지한다. directional `HOLD`는 `guarded_elbow_send()`에서 `return None`으로 새 `send_action`만 생략하며 Goal/Torque를 쓰지 않는다. `recover_follower_hold.py`의 이번 재시도는 최초 torque 검사에서 중단돼 Goal write/enable/disable이 없었다.
- 이번 read-only 확인에서 service restart, torque OFF/ON, Goal write, motor command는 없었다. 변경 `NOT_COMMITTED/NOT_PUSHED`. [세션](sessions/2026-10-11-robot-fk-tcp-pivot-diagnostic.md).
- torque/recovery 분석을 종료하고 vision dry-run으로 복귀했다. 8000 health 정상, 8초 MJPEG 약 9.3 MB/240 frames가 연속 수신되어 camera bridge 재시작은 하지 않았다. 새 마지막 frame SHA `9c4eb1fd…f867e3`에서 ArUco ID0–3와 C 1개(confidence `0.797704`, center `[323.432,241.028] px`)를 검출했다. raw/corrected/reflected table XY는 `[279.490,363.628]` / `[249.915,325.149]` / `[−249.915,325.149] mm`, candidate robot XY는 `[−62.635,−295.316] mm`다. pre/approach/grasp/lift Z `100/80/50/100 mm` 위치 IK residual은 `0.013/0.023/0.677/0.568 mm`, 네 target 모두 servo candidate range PASS. motor/Goal/torque write 0회, 실제 motion `NOT_RUN`; orientation/collision/Z physical verification은 여전히 false다. 결과 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_vision_ik_dry_run_current.json`.
- 사용자가 최신 C의 `live_c_pre_approach_only`를 승인하고 현장 실행 문구를 확인했다. fresh follower `(-10.945,-96.132,+97.275,+57.011,-18.418)°`, fresh gripper `1.958%`에서 2° 이하 54-waypoint 접근을 시작했으나 `joint_target_timeout`으로 **ABORT**했다. 마지막 오차는 Pan `−0.317°`, Lift `−0.910°`, Elbow `+1.733°`, Flex `+0.226°`, Roll `−0.406°`, Gripper `0.000`; arm tolerance `1.6°`를 Elbow가 `0.133°` 초과했다. pre-approach 도달 아님, grasp/lift 미시작. 사용자 `STOPPED`와 새 feedback으로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; 종료 후 세 LeLab 작업 inactive, 접근 프로세스 없음, follower `lsof rc=1` 무점유다. 추가 재시도 `NOT_RUN/NOT_AUTHORIZED`. 결과 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_attempt_current.json`.
- 위 실패를 좌표/IK가 아닌 final convergence timeout으로 분류했다. 1.6° tolerance, C frame/robot XY, IK target, 기본 waypoint timeout 3.0초는 유지하고, 마지막 waypoint만 5.0초 및 기존 마지막 5개 선형 구간 2분할을 적용했다. 같은 joint-space 선과 target을 보존하며 fresh 시작 pose에서 경로를 다시 생성하고, 도달 뒤 별도 fresh feedback을 1.6°로 재검증한다. 관련 로컬 테스트 25/25와 Jetson 설치 Python py_compile/dry-run PASS; Jetson 배포 SHA는 `live_c_approach.py 1e79ccf…939d0`, `staged_cycle_execution.py e6f5fdc…dd3d`, plan `57b33088…6197`이다. 실제 재시험 직전 `192.168.50.20`의 SSH/8000/ping이 모두 timeout으로 바뀌어 실행 프롬프트 이전에 중단했다. 새 port open/motor/Goal/torque write는 없고, 재시험과 `PRE_APPROACH_PASS`는 **BLOCKED/NOT_RUN** until Jetson network recovery and fresh safety preflight. grasp는 계속 `NOT_RUN`이다.
- 네트워크 복구 후 SHA/세 제어 비활성/관련 프로세스 없음/privileged follower port 무점유를 다시 확인했다. 첫 live 재시작은 sudo 인증 timestamp 만료로 내부 `sudo -n fuser`가 `port_ownership_unknown`을 내 포트 개방·명령 전 fail-closed했다. 즉시 인증을 갱신한 한 번의 승인 재시험은 fresh start `(−10.857,−93.055,+96.044,+55.604,−17.626; gripper 1.958)`에서 tail-refined 58 waypoint를 생성했지만 final timeout에서 Pan `−0.409°`, Lift `−0.957°`, Elbow `+2.360°`, Flex `+0.204°`, Roll `−0.486°`, Gripper `0.000`이었다. Elbow만 1.6°를 초과했고 이번 값은 사용자가 지정한 재평가 구간 `1.6–2.0°`에도 들지 않는다. 따라서 tolerance 불변, `PRE_APPROACH_PASS` 아님, grasp/lift `NOT_RUN`, 자동 재시도 없음. 사용자 `STOPPED`와 fresh feedback window로 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`; 종료 후 세 제어 비활성, 관련 프로세스 없음, follower 포트 무점유(`fuser rc=1`)다.

## 2026-10-11 robot-side FK/TCP pivot 진단 — 8/8, offset 유력·최종 채택 보류

- table→robot fit, 5점 재촬영, live C IK, 자동 motion은 중단했다. 기존 5점 세트는 모두 분리 보존하며 섞어 쓰지 않는다.
- 동일 physical P1과 Repeat P1의 follower 차이는 `(Pan −1.231°, Lift +7.297°, Elbow +2.901°, Wrist Flex −16.440°, Wrist Roll +0.176°)`이다. 설치본과 같은 SHA `443d38d…f67236` URDF의 `base→gripper` raw FK 차이는 `(+8.206,+7.300,−13.468) mm`, XY `10.983 mm`, XYZ `17.379 mm`; tool orientation 차이는 `6.364°`다. 현재 capture 코드는 `gripper` link origin과 zero TCP offset을 사용한다. 같은 physical P1의 table→robot 최종 재현 오차 `66.924 mm`와 함께 보면 table fit만으로 설명할 수 없어 FK/physical TCP consistency를 먼저 진단한다.
- read-only `scripts/pivot_tcp_capture.py`와 targeted tests를 추가했다. LeLab `/ws/joint-data`만 구독하며 15 fresh samples, max std `0.01 rad` 조건에서 follower 5축, FK tool origin/rotation, timestamps를 Pose 1–8 별도 JSON으로 저장한다. `p_fixed=t_i+R_i*tcp_offset` least-squares가 offset, pose별 residual, RMS/max, rank, condition number를 출력한다. 로봇 bus/USB/torque/motor command 경로는 없다. targeted tests 10/10 PASS.
- 로컬 `127.0.0.1:8034` pivot 화면의 `.local/c-red-pivot-tcp-20261011`에 Pose 1–8이 저장됐다. 전체 fit은 offset `[-51.748,−73.034,−54.532] mm`, norm `104.812 mm`, residual `5.875/2.491/1.691/7.705/3.520/1.538/4.632/2.159 mm`, RMS `4.240 mm`, max `7.705 mm`, rank 6, condition `10.681`. Pose 1–7 fit→Pose 8 hold-out `2.552 mm`; 다만 leave-one-out은 Pose 4 `11.516 mm`, Pose 7 `10.019 mm`, RMS `6.324 mm`라 최종 PASS/5점 재개는 보류한다. 32개 sign 조합 검사에서 current mapping RMS `4.240 mm`보다 유의하게 좋은 sign 변경은 없었다(최저 차이 0.005 mm). LeLab/teleop/Jetson 프로세스·서비스·USB에는 변경 없음. [세션](sessions/2026-10-11-robot-fk-tcp-pivot-diagnostic.md). 변경 `NOT_COMMITTED/NOT_PUSHED`.
- 위 pivot offset을 기존 Roll-fixed P1–P4/H1과 별도 Repeat P1 joint data에 적용하고 Table X reflection 후 P1–P4 rigid fit을 재계산했다. fit residual `P1 18.589 / P2 6.296 / P3 12.515 / P4 1.696 mm`, RMS/max `11.669/18.589 mm`; H1 `5.660 mm`, Repeat P1 `24.926 mm`다. 기준상 **REJECTED**이며 live C/IK `NOT_RUN`. 다만 corrected P1↔Repeat P1 직접 TCP XY 차이는 `5.879 mm`로 pivot offset이 same-point FK 재현성을 크게 개선했다. 8개 leave-one-out pivot offset을 모두 적용해도 Repeat P1 `24.368–29.793 mm`, fit RMS `11.349–14.508 mm`라 pivot pose 추가만으로 기존 five-point rigid-fit 불일치가 해소될 가능성은 낮다. 결과는 `.local/c-red-five-point-roll-fixed-20261011/pivot_tcp_reflected_fit.json`에 보존했다.
- 기존 세트를 최종 calibration에서 제외하고 새 session `pivot-tcp-table-20261011-s01`을 `.local/c-red-pivot-tcp-table-20261011-s01`에 완전히 분리해 `P1→P2→P3→P4→H1→Repeat_P1→Repeat_P3` **7/7** 캡처했다. 기존 registration XY/hash, pivot TCP, URDF SHA만 manifest에 고정했고 과거 capture import 없음. Table X reflection rigid fit은 P1/P2/P3/P4 residual `17.668/4.164/14.863/2.606 mm`, RMS/max `11.802/17.668 mm`; H1 `6.771 mm`, Repeat P1 직접/transform `8.783/26.310 mm`, Repeat P3 직접/transform `5.446/10.708 mm`로 **REJECTED**. repeat direct와 H1은 single-digit이라 capture/TCP 재현성은 개선됐지만 rigid metric geometry가 맞지 않는다. fit point pairwise robot distance가 table보다 최대 `31.991 mm` 짧고, 진단용 similarity scale `0.92013`에서는 fit RMS/max `4.064/5.279 mm`, H1 `7.578`, Repeat transform P1/P3 `9.728/2.367 mm`로 급개선되어 약 8% metric scale 불일치(table mapping 또는 FK/link scale) 증거가 있다. similarity는 요청된 rigid calibration을 대체해 채택하지 않았다. live C/IK/자동 motion `NOT_RUN`.
- 5점 재촬영은 중단했다. 가장 먼 P1↔P3의 기존 table distance `341.094 mm`, corrected robot TCP XY distance `309.103 mm`, similarity scale 0.92013 적용 table distance `313.851 mm`다. 어느 metric이 실제와 맞는지 P1/P3 mark 중심간 물리 거리 1회 실측 대기. 측정 전 table scale/FK scale 어느 쪽도 수정하지 않으며 live C/IK `NOT_RUN`.
- 사용자가 P1↔P3 mark 중심간 실제 거리를 **약 305 mm**로 1회 측정했다. 이는 robot TCP 거리 `309.103 mm`에 가깝고 기존 table 거리 `341.094 mm`와는 달라 table/ArUco metric scale 오류로 판정했다. 실측 기반 scale `0.8941815921`를 기존 7점 table XY에 적용하고 동일한 Table X reflection rigid fit을 다시 계산했다. P1/P2/P3/P4 residual `4.623/7.435/0.989/6.347 mm`, RMS/max `5.429/7.435 mm`; H1 `9.458 mm`, Repeat P1 direct/transform `8.783/4.694 mm`, Repeat P3 direct/transform `5.446/4.853 mm`로 모두 single-digit다. transform은 회전 `+13.232333°`, translation `[255.070981,-554.626715] mm`; 원래 uncorrected table XY에 scale+X reflection을 합친 행렬은 `[[-0.870441,-0.204678,255.070981],[-0.204678,0.870441,-554.626715],[0,0,1]]`이다. 결과는 `.local/c-red-pivot-tcp-table-20261011-s01/scale_corrected_reflected_table_robot_fit.json`. 단, 자 측정이 “약 305 mm” 한 번뿐이므로 status는 **CANDIDATE**, 자동 motion 승인 아님. live C/IK는 다음 read-only 단계이며 실제 motion `NOT_RUN`.
- 천장 camera bridge의 OpenNI source만 남고 GStreamer `/dev/video8` sink가 사라져 8000/8002가 HTTP 503이었다. teleop/recording/inference가 두 서버 모두 OFF인 상태에서 사용자가 system `astra-v4l2-bridge.service`만 재시작했고 source/sink PID 546150/546151이 확인됐다. 복구된 8000 최신 frame SHA `31481ca0…fbd15`에서 ArUco ID0–3, YOLO C 1개(confidence `0.772715`, center `[323.185,238.947] px`)를 검출했다. raw/corrected table XY `[280.758,362.006]` / `[251.049,323.699] mm`, candidate robot XY `[-63.407,-296.987] mm`. Z pre/approach/grasp/lift `100/80/50/100 mm` 위치 IK는 모두 residual ≤`0.450 mm`, servo candidate range PASS, 2° bounded interpolation 수치 PASS. 다만 teleop OFF라 fresh joint broadcast가 없고 `/joint-positions`도 `No active teleoperation session`; delta는 마지막 Repeat P3 관측값 기준일 뿐이다. orientation/collision 미검증, 실제 motion `NOT_RUN`, 승인 `false`. 결과 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_vision_ik_dry_run.json`.
- 사용자가 직접 `relative_start` teleop을 켠 뒤 read-only joint broadcast 10표본을 받았다. fresh mean `(Pan +5.618, Lift −29.820, Elbow +31.121, Flex +48.835, Roll −15.429)°`, 최대 표준편차 `0.132°`. fresh seed 재계산에서 pre/approach/grasp/lift 위치 IK residual `0.095/0.024/0.671/0.004 mm`, servo candidate range 모두 PASS. 2° bounded interpolation은 구간별 `21/3/5/8` step으로 finite/range PASS. numerical dry-run은 PASS지만 orientation, collision/swept path, 후보 Z 실측은 미검증이고 자동 motion은 아직 `NOT_RUN/NOT_AUTHORIZED`. 결과 `.local/c-red-pivot-tcp-table-20261011-s01/live_c_vision_ik_dry_run_fresh.json`.

## 2026-10-10 종료 인계 — hardware/LeLab 상태 재확인 없이 종료

- 사용자가 오늘 종료를 선언했다. 이 마감 기록을 위해 SSH, LeLab, 포트, 카메라에 접속하지 않았고 프로세스 시작·종료, 서비스 재시작, motor command, teleop, calibration은 수행하지 않았다. 가장 최근 live 확인값은 오래된 시점의 관측이므로 현재 상태로 간주하지 않는다. 상세: [종료 인계](sessions/2026-10-10-end-of-day-handoff.md).
- `relative_start`는 `scripts/relative_start_teleop.py`, `tests/test_relative_start_teleop.py`, `patches/lelab-20261010/teleoperate-relative-start.patch`에 로컬 후보로만 있다. Jetson 배포·서비스 반영·실기 검증 `NOT_RUN`; absolute 기본 모드는 후보에서 보존. 기존 후보 검증은 fake-input 7/7이며 오늘 추가 시험은 하지 않았다.
- 설치본 증거가 서로 다르다: 과거 세션은 원복 SHA `teleoperate.py=e3ac7525…9028d89`, guard `2e5ffa30…0118362`를 기록했으나, 이후 20:19 KST 무렵 사용자 제공 Jetson 출력은 설치 `teleoperate.py=042c5f76…ac7c54`, guard `1ca311d0…04b09`와 `LELAB_TEMP_WRIST_ALIGN=1`을 보였다. 그 이후 설치 파일 해시와 환경변수는 다시 확인되지 않았다. 따라서 원복 여부/현재 활성 guard는 **미확인**이며, 과거의 “제거·원복” 기록만으로 현재 상태를 단정하지 않는다. 원본 복구본은 `/home/jetson3/lelab-source-backups/`에 해시 이름 파일로 보관됐다는 기록이 있으나, 이 날짜의 구체 경로·현재 존재 여부는 미확인이다.
- 마지막으로 정상 동작했다고 확인 가능한 기록은 2026-10-09 C→빨강 텔레옵 시연 세션이다. 해당 성공 실행본의 정확한 `teleoperate.py` SHA/백업 경로는 세션 기록에서 확인되지 않아 **미확인**. 오늘 마지막으로 구체화된 실패 증상은 LeLab worker `Temporary alignment blocked by shoulder_pan mismatch`로 종료된 것이다(21:25 KST 사용자 제공 로그). 같은 날 뒤의 읽기 전용 관절 화면에서는 5축 차이 `within_2_degree=true`였지만, 그것이 실제 웹 teleop 성공을 증명하지 않는다. 이후 시도 결과와 현재 teleop 상태는 **미확인**.
- 마지막으로 관측된 프로세스 구성(21시대 사용자 출력): LeLab 8000 PID 542083/542085, 별도 LeLab 8002 PID 3467, 카메라 `app.py` PID 521444:8011. 당시 `/dev/ttyACM0/1` 대상 `lsof` 출력에 소유자가 없었으나 권한/mount 경고가 있었고, 그 후 상태는 미확인이다. 현재 서비스/teleop worker/USB 소유권으로 인용하지 않는다.
- 5점 capture **0/5**. 8034의 P1/P2/P3/P4/H1 등록은 당시 5/5였으나 `tcp_ready=false`; 동일한 물리 wrist-base 기준점의 TCP 등록 gate가 미해결이다. SE(2) fit/hold-out, table→robot transform, live C robot XY, IK dry-run `NOT_RUN`.
- 카메라/비전 마지막 기록은 천장 카메라 프레임에서 ArUco ID0–6 및 `table_ready=true`; 해당 검사 프레임에서는 YOLO 물체 검출 0개였다. 이는 현재 live 상태가 아니다. 현재 YOLO/ArUco/camera 상태 **미확인**.
- 변경은 기존 working tree에 남아 있으며 커밋/푸시 `NOT_COMMITTED/NOT_PUSHED`. 그 외 사용자 변경은 그대로 보존한다. 다음 세션은 사용자가 정한 순서대로 실제 상태 read-only 확인부터 시작한다.

## 2026-10-10 relative_start teleop — 로컬 준비, Jetson 적용·실기 미실행

- `scripts/relative_start_teleop.py`와 Jetson 설치본 SHA `042c5f76...ac7c54`용 LeLab worker 패치를 준비했다. 모드는 `LELAB_TELEOP_MODE=relative_start`로만 선택하며 기본 `absolute` 동작은 유지한다. 시작 시 보정 단위의 fresh leader/follower origin을 읽고, 첫 target은 follower origin 그대로이며 이후 6축(gripper 포함)에 leader delta를 더한다. 상대 모드에서는 wrist/elbow 정적 offset을 적용하지 않는다. follower 실제 calibration raw 범위를 LeRobot `_normalize()`로 각도/percent 환산해 검사하고, 범위 밖 전체 target은 SEND 없이 HOLD한다.
- 순수 계산 fake-input 시험 7/7 PASS, patch syntax/diff check PASS. 현재 Jetson 소스에는 Elbow fresh-feedback/2° command-step guard와 통신 예외 중단이 보이나, 일반 6축 tracking-error guard는 확인되지 않았고 `max_relative_target=None`이다. 새 tracking 임계값은 임의 추가하지 않았다.
- helper/worker patch의 Jetson 설치, LeLab 재시작, leader/follower 포트 변경, 텔레옵 시작, 3초 정지·소각도 실기 검증은 `NOT_RUN`. 현재 실행 중인 서비스·프로세스는 건드리지 않았다. 실기 검증과 5점 캡처 `BLOCKED` until installed-mode review and user-managed validation. `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 5점 세션 시도 — 정렬 확인, TCP 등록 차단 후 원복

- 읽기 전용 정렬 화면에서 리더−팔로워 5축 차이 모두 ±2° 이내를 확인했다. 화면 PID `541243`만 종료하고 USB 두 포트 해제를 확인했다. LeLab 텔레옵은 시작 전 OFF였고, 실행 프로세스 시작 로그에 `LELAB_TEMP_WRIST_ALIGN=1 guard=guarded_elbow_send`가 있었다.
- 사용자가 현장 안전·손목 회전축 중심을 확인하고 직접 텔레옵을 켰으나, 5점 수신기 `tcp_ready=false`에서 축 중심을 URDF `gripper` 링크 원점 `(0,0,0) mm`으로 **검증 완료 등록**하는 요청이 안전 검토에서 거부됐다. 우회하거나 등록하지 않았다. 점 이동·캡처 **0/5**, table→robot fit/hold-out `NOT_RUN`; 실제 모터 이동을 지시하지 않았다.
- 사용자 종료·비접촉 확인, 서버 teleop/recording/inference OFF 및 포트 무점유 뒤 한시 설치 파일을 정확한 백업으로 원복했다. `teleoperate.py` SHA `e3ac7525...9028d89`, guard SHA `2e5ffa30...0118362`; `LELAB_TEMP_WRIST_ALIGN`은 서비스 환경에서 제거된 상태다. LeLab 재시작 뒤 health `ok`, teleop OFF. 기준점의 물리·URDF 일치 위험을 설명하고 이번 캡처용 명시 승인을 요청했다. 재시도·실제 접근 `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 servo calibration / URDF 역할 분리 — 5점 캡처 대기

- LeLab OFF에서 읽기 전용 fresh follower `(Pan −7.604, Lift −100.000, Elbow +96.308, Flex +50.066, Roll −20.000)°`를 재측정했다. 모터 송신·토크 변경 0회, viewer는 종료. Elbow는 URDF 모델 +90° 밖이지만 실제 설치 follower calibration SHA `2f74c130...e29c2e`의 raw 880–3087(약 ±97.011°) 안이다. 이 사실은 물리 안전 여유의 증명은 아니다.
- 5점 수신기는 URDF 밖 feedback도 FK와 함께 캡처하고 모델 불일치 경고만 기록하도록 했다. 천장 MJPEG 직접 수신은 정상이나 기존 8034 수신기가 LeLab 재시작 뒤 stale라 정확한 수신기만 재시작했다. 기존 P1–P4/H1 등록을 백업 후 새 live 프레임에 재등록했으며 camera age 1.6 ms, 등록 5/5, 캡처 **0/5**, rigid TCP `tcp_ready=false`. 로봇 제어 0회.
- 수동 Elbow guard 후보는 현재 설치 서보 calibration에서 범위를 읽고 상한 방향 HOLD·안쪽 SEND·2° 대점프 ABORT를 적용한다. Jetson 기존 모듈을 백업하고 후보 SHA `1ca311d0...7204b09`를 설치, 설치 Python fake test PASS, LeLab health ok/teleop inactive/포트 해제. 하지만 서비스 환경에 `LELAB_TEMP_WRIST_ALIGN=1`이 없어 **새 guard는 아직 실행 경로에서 비활성**. 환경 설정·서비스 재시작 요청은 auto-review가 지속 설정 위험으로 거부했다. 우회하지 않고 사용자 정확 승인 대기. 현장 리더 Pan/Flex/Roll 차이도 크므로 텔레옵·5점 이동은 `NOT_RUN`.
- 비전 IK는 `safe_start` 고정 seed를 제거하고 관측 시작 5축을 요구한다. URDF 모델 범위와 별개인 자율 planning limit 입력을 만들었으나 현재 2° reserve 후보는 `PENDING_PHYSICAL_VALIDATION`이므로 자동 IK에 사용할 수 없다. 로컬 관련 33/33 테스트 PASS, 실제 5점 fit/live C robot XY/IK/자동 접근 `NOT_RUN`. 기존 trajectory replay/URDF/servo calibration 불변. 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 현장 5점 캘리브레이션 준비 — 모터 이동 차단

- 읽기 전용 live 카메라 수신기는 신선한 천장 프레임을 받고 작업대 X 표시 P1–P4/H1을 등록했다. 실제 대응점 캡처는 **0/5**이며 TCP 기준점 offset과 빨강 바구니 입구는 미검증이다. C와 바구니는 사용자가 작업대 밖으로 치웠다.
- 사용자가 집게 몸체와 손목이 만나는 둥근 축 중심을 식별할 수 있을 것 같다고 답했지만, 동일 물리 기준점·URDF offset의 검증으로 간주하지 않는다.
- LeLab OFF 상태의 읽기 전용 fresh follower에서 Elbow `+90.330°`가 재확인되어 URDF 상한 `+90°`를 `0.330°` 초과한다. 리더와 팔 관절 차이도 크다. 따라서 LeLab 시작, 5점 teleop 및 실제 접근은 **BLOCKED**. 읽기 전용 Jetson viewer는 종료했고 `ports_released=True`를 확인했다. 모터/토크 명령 0회. 5점 fit, hold-out, live robot XY/IK는 `NOT_RUN`; 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.
- 텔레옵 복구 요청 뒤 사용자가 현장 정지·비접촉을 재확인했다. LeLab 8000 health는 `ok`, teleop/recording/inference는 모두 inactive. 기존 설치 guard의 `feedback_outside_urdf` 차단을 재검토했고 로컬 가짜 입력 시험 10/10 PASS. 서비스 정상/worker 시작 차단이므로 동일 조건 재시작은 하지 않았다. 현장 모터·토크·USB·설치 코드 변경 `NOT_RUN`; 안전 복구 방법과 별도 승인 전 텔레옵 복구는 `BLOCKED`.
- 한시 manual-recovery 후보는 정상 guard를 그대로 두고, 현재 +90…+91°에서 내부 +88.8…+89.2° 한 번만 송신하도록 로컬에서 준비했다. 다른 다섯 축은 fresh feedback으로 고정하며 follower 설정·토크 toggle을 복구 모드에서 건너뛰게 하는 설치 패치가 원본 SHA에 `--fuzz=0`로 맞는다. 로컬 guard 시험 13/13 PASS. **Jetson 설치본에는 미적용**.
- 그러나 현장 정지·비접촉 확인 뒤 두 번의 읽기 전용 follower 측정이 raw Elbow `3079`/`+96.308°`, Shoulder Lift `−100.000°`로 동일했다. 사용자 답변으로 이전 +90.330° 측정 후 팔로워를 직접 움직인 사실을 확인했다. follower torque register는 여섯 축 모두 `1`(ON), 진단 중 모터 write/torque 변경 0회. 현재 +96.308°에서 URDF 내부 최대 +90°까지 최소 6.308°이므로 **내부 목표만 사용 + 2° 이내 step**이라는 동시 조건으로는 송신 가능한 첫 목표가 없다. recovery 배포·LeLab 시작·5점 캡처 `BLOCKED/NOT_RUN`; 별도 물리 안전 복구 없이는 진행하지 않는다.

## 2026-10-10 비전 좌표 blocker 재점검 — 천장 영상 복구, 실측 XY 차단 유지

- Jetson Astra USB `2bc5:0401`, `/dev/astra`, `/dev/video8` 존재. `astra-v4l2-bridge.service`와 OpenNI RGB pipe/GStreamer는 실행 중이었지만 LeLab 8000·8002의 정면 `/camera-preview/8`은 HTTP 200 뒤 6초간 각각 0 byte, 8000 로그에는 `/dev/video8` V4L2 `select() timeout`이 반복됐다. 8002 PID 3467이 장치를 열고 있었고, 브리지 GStreamer도 writer로 열었다. 정확한 최초 정지 시각과 하위 OpenNI 원인은 `NOT_VERIFIED`다.
- 두 LeLab의 텔레옵·녹화·추론 `active=false` 확인 뒤 카메라 브리지 **한 서비스만** 재시작했다. 새 브리지 PID 539090/539097/539098로 active; 같은 정면 endpoint 6초 수신량이 8000 8,513,759 byte, 8002 8,420,139 byte로 복구됐다. LeLab/USB/토크/모터/카메라 설정은 변경하지 않았다. 기존 Mac 8030 관찰기는 약 26.6시간 stale여서 현재 live 근거로 쓰지 않았다.
- 복구된 640×480 정면 JPEG 두 장에 기존 YOLO+ArUco 코드를 적용해 ID0–6, `table_ready=true`를 확인했다. 두 장 모두 약통 검출 0개여서 live C pixel/table XY는 `BLOCKED_OBJECT_ABSENT`; 세 번째 별도 MJPEG 연결은 frame 전에 종료됐다. 저장 C 프레임의 이전 수치는 live C 관찰로 대체하지 않는다.
- 저장소·기존 teach/hand-eye/외부 파라미터를 재검색했으나 승인된 table→robot/TCP 변환이나 robot-base ArUco 대응점은 없다. 기존 6점 적합의 조건수 5555.7, 독립 P6 오차 9.932 mm 및 손목 영상 marker 0/25 때문에 기존 값을 재사용할 수 없다. 빨강 ID4 대비 `(-2.269,+98.737) mm`는 영상 후보일 뿐 독립 입구 중심 자료가 없다. 따라서 실제 C/빨강 robot XY, 위치 IK/URDF 일괄 dry-run은 `NOT_RUN/BLOCKED`; 마지막 Elbow +90.330°는 과거값이며 이번에 fresh robot feedback은 읽지 않았다. 실제 접근 `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 vision-guided C→빨강 blocker 4개 — 슬롯 PASS, 실기 좌표/카메라 BLOCKED

- 기존 81개 보존된 검수 프레임의 YOLO bbox 중심을 ID0–3 homography로 재투영해 A/B/C 작업대 슬롯 중심 `(76.557,351.317)/(179.722,336.457)/(289.600,327.939) mm`를 만들었다. runtime에는 사람 라벨을 넣지 않고 `nearest table slot`으로 신원을 정한다. 같은 81개 프레임의 재판정은 81/81 일치하나 **in-sample**이며 독립 정확도는 미검증. 저장 C 프레임은 `(318.757,239.599) px → (289.666,331.112) mm → C`, 슬롯 중심과 거리 3.174 mm.
- 기존 2026-10-01 6점 teach는 실제 TCP 오프셋 미검증, 조건수 5555.7 및 제외한 P6 오차 9.932 mm로 거부된 상태다. 성공 텔레옵 원본에는 동일 시각의 카메라/작업대 좌표가 없어 새 robot XY 대응점으로 쓸 수 없다. 거부된 `T_B_W` 사용을 제거했다. 새 2D 게이트는 **검증된 TCP offset + 서로 떨어진 4 fit점 + 독립 1 hold-out점**을 요구하고 fit RMS ≤5 mm, fit 최대/hold-out 최대 ≤8 mm일 때만 robot XY/IK를 계산한다. 현재 실제 자료는 이를 충족하지 못해 robot XY와 IK는 `NOT_RUN`.
- 저장 C 영상의 빨강 입구 중심 육안 후보 pixel `(313,290)`과 ID4 중심 `(307.5,346)`을 기존 homography로 투영해 ID4 대비 후보 오프셋 `(-2.269,+98.737) mm`를 만들었다. 마커/입구 높이 차이 및 입구 중앙이 실측되지 않아 `opening_offset_verified=false`; 기존 place 관절값만으로는 작업대 입구 XY를 역산할 수 없다. 입구 기준 한 번의 독립 측정이 필요하다.
- 새 진단기는 검증된 XY가 들어오면 approach/grasp/lift/red-basket-hover/place 5개 위치 IK와 URDF 여유를 출력한다. 가짜 XY와 설치 SHA가 같은 URDF의 5단계 수치 시험은 통과했으나 실제 C/바구니 robot XY가 없어 실측 일괄 출력 목표는 **BLOCKED**. LeLab 8000/8002 `/camera-preview/8`은 HTTP 200 MJPEG이나 8초 동안 프레임 0바이트; read-only live 시도는 timeout으로 `NOT_RUN/BLOCKED`. 서비스·카메라·USB·토크·모터 불변. 마지막 follower Elbow +90.330°(URDF 밖)도 live approach 차단. 관련 36/36 테스트, 문법·diff 검사 PASS; `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 C 비전→작업대 좌표→IK 오프라인 통합 — 수치 PASS, 실기 차단

- 기존 단일 클래스 YOLO(`white_medicine_bottle_model`), ID0–3 ArUco 작업대 homography, 고정 슬롯 C 판정, 설치 URDF와 동일 SHA 모델 FK를 재사용하는 `scripts/c_red_vision_ik_dry_run.py`를 추가했다. YOLO는 A/B/C 자체를 분류하지 않는다. ID4는 빨강 바구니의 **마커**이지 입구 중심이 아니다. 기존 Astra 내참수 파일은 존재하지만 이 천장 프레임 경로는 기존 `TableMapper`의 원영상 평면 homography를 그대로 사용한다.
- 저장된 사람 확인 C 프레임 한 장에서 YOLO 신뢰도 0.836797, bbox 중심 `(318.757,239.599) px`, ID0–6, 작업대 `(289.666,331.112) mm`를 재검출했다. C 중심은 기존 pickup ROI 밖이다. 현재 Mac `8030` 카메라 서비스는 연결되지 않아 **live camera 검증 NOT_RUN**; 저장 프레임만 검증했다.
- 거부된 `T_B_W`/TCP와 임시 `Z_SAFE/APPROACH/GRASP/LIFT/PLACE=(100/80/50/100/80) mm`를 **명시적 진단 모드에서만** 사용한 위치 IK는 approach/grasp/lift FK 잔차 각각 `0.233/0.947/0.097 mm`, 팔 URDF 예약 여유 최소 `45.318°`로 수치 통과했다. 이 좌표·높이·그리퍼 방향·충돌 경로는 물리적으로 검증되지 않았다. 기본 실행은 joint target을 만들지 않고 exit 2로 실패 폐쇄한다. 테스트는 관련 32/32, 문법·diff 검사 PASS.
- 승인된 World→Base/TCP 변환, C 신원 자동 식별, pickup ROI 재확인, 실측 Z/그리퍼 방향, 빨강 바구니 입구 중심 및 경로/충돌 검증이 없어 실제 `approach/grasp/transport/place`는 `NOT_RUN/BLOCKED`. 마지막 실측 follower Elbow `+90.330°`는 URDF `+90°` 밖이므로 기존 현장 승인도 새 자동 접근을 허용하지 않는다. 로봇 포트·모터·토크·LeLab/Jetson 설정 변경 없음. 원본 이미지/로그/비밀정보는 Git 제외, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 safe_start 복귀 시도 — URDF 밖 fresh Elbow로 시작 전 차단

- 사용자 현장 정지·비접촉·C 제거 확인 뒤 LeLab 세 제어 상태 OFF, read-only viewer에서 follower `(Pan +20.967,Lift −42.769,Elbow +89.275,Flex −30.989,Roll +2.857°)`를 재측정했다. 리더만 조정해 팔 5축 차이를 모두 ±2° 이내(최대 Elbow 1.275°)로 확인했고 viewer를 종료해 두 포트를 해제했다. 사용자 리더 고정·현장 안전을 재확인하고 기존 LeLab 시작을 한 번 시도했다.
- 사용자는 첫 3초 실제 팔 점프·접촉 없음이라고 보고했으나, 서버는 이미 `teleoperation_active=false`. 이번 시작의 첫 guard 로그는 follower Elbow `current=+90.154°`, `requested_target=+90.154°`, `action=ABORT`, `reason=feedback_outside_urdf`; +90° URDF 상한을 넘은 fresh feedback 때문에 첫 목표 송신 전 중단됐다. 기존 hard limit은 변경하지 않았다. 이전 viewer +89.275°와의 변화 원인·정확한 시점은 `NOT_VERIFIED`.
- 사용자 LeLab 종료·실제 정지·비접촉 확인 뒤 별도 read-only follower 실측 2회가 `(Pan +20.967,Lift −42.505,Elbow +90.330,Flex −30.989,Roll +2.857°,gripper 22.032%)`로 동일했다. Elbow는 URDF 상한보다 0.330° 높다. 리더는 손을 놓은 뒤 다시 큰 불일치 상태다. viewer PID `538814` 종료·8031 LISTEN 해제, LeLab inactive·두 포트 대상 점유 PID 없음(`lsof`의 무관한 mount 경고). safe_start·approach live `NOT_RUN/BLOCKED`; hard limit 유지와 추가 코드 변경 금지 범위에서는 수동 텔레옵 재시도 불가. 추가 물리 복구는 별도 현장 방법·승인이 필요하다. trajectory/calibration/URDF/replay 로직 불변, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 Elbow HOLD 최소 수정 — 설치·가짜 시험 PASS, 수동 복귀 대기

- 직전 차단 `+88.747→+88.835°`에서 상한 방향의 작은 요청 하나가 텔레옵 전체를 끝내는 문제에 한정해, 해당 목표는 `HOLD`(모터 송신 0회, 마지막 안전 목표 유지)하고 다음 감소 방향 요청에서 `SEND`하도록 수정했다. URDF 밖 목표·feedback, 연속 Elbow 목표 2° 초과, 통신·feedback 오류는 계속 중단한다. 매 판정 전에 current/target/delta/양쪽 margin/방향/action/reason을 기록한다.
- Jetson 설치본/백업 해시를 대조하고 `--fuzz=0` 패치 적용. 설치 `teleoperate.py` SHA `e3ac7525...9028d89`, guard SHA `2e5ffa30...0118362`가 예상값과 일치한다. 로컬 10/10, 설치 Python 문법 및 가짜 버스의 `HOLD→SEND→SEND`, 상·하한, 2° 대점프 검사 PASS. LeLab 세 제어 작업 inactive에서 재시작 후 health `ok`, teleop inactive 확인. 실제 텔레옵 시작·모터 송신 `NOT_RUN`.
- read-only 8031 뷰어의 fresh follower `(Pan +20.967,Lift −42.769,Elbow +89.275,Flex −30.989,Roll +2.857°,gripper 22.032%)`는 반복 안정이나 Elbow 상한 여유가 **0.725°**뿐이다. leader와 최대 73.451° 불일치라 재시작 불가. 뷰어 PID `538710`은 종료해 8031 LISTEN 해제·두 USB 포트 대상 점유 PID 없음(`lsof`의 무관한 mount 경고) 확인. 사용자 현장 리더 정렬·안전 확인을 기다린다. safe_start 도착과 approach 640/640 `NOT_RUN`; trajectory/calibration/URDF/replay 불변. 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 C→빨강 준비 — 방향 보호 작동, safe_start 복귀 중단

- Jetson 설치 `teleoperate.py` 원본/백업 SHA `a5ac255d...8102576`을 대조하고 방향별 Elbow guard만 적용했다. 설치 결과 SHA `e4f6462c...16b9bb6a`, 보호 모듈 SHA `c08806d5...2ca7ef` 일치, 설치 Python 문법·가짜 방향 입력 PASS. LeLab 세 제어 작업 비활성 상태에서 서비스 재시작·health 확인. 동일 4배 접근 640개와 grasp/transport/place 각 459/141/199개 설치 Python dry-run PASS; 실제 송신 0회.
- 리더/팔로워 fresh 정렬에서 시작 보정 Elbow `+0.219780°`, Wrist Flex `−1.362637°`를 계산했다. 읽기 화면을 종료해 두 포트를 비운 뒤 사용자 현장 확인하에 LeLab 텔레옵을 시작했고 8032 fresh 방송을 확인했다. safe_start 방향 첫 수동 이동 중 Elbow 현재 `+88.747°`에서 요청 `+88.835°`(+0.088°, URDF 상한 여유 1.253°)이 상한 쪽이라 `toward_upper_limit`로 송신 전 차단됐다. guard 완화·추가 구동 없음.
- 사용자 현장 팔·그리퍼 정지 및 비접촉 확인. LeLab `teleoperation_active=false`. 종료 뒤 읽기 전용 follower `(Pan +20.967, Lift −42.769, Elbow +89.275, Flex −30.989, Roll +2.857°, gripper 22.032%)`가 반복 안정적이나 Elbow 상한 +90°까지 **0.725°**뿐이다. 리더와 큰 불일치가 있어 재시작 정렬 상태가 아니다. 읽기 화면 PID만 종료해 두 USB 포트 해제 확인. 안전상 동일 조건 재시도 중단; `safe_start` 미도착, approach/grasp/transport/place live `NOT_RUN`, 자동 C→빨강 `NOT_RUN`. 새 trajectory/calibration/URDF/time-scale/tracking/scheduler 변경 없음. 원본 로그·비밀정보 Git 제외, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-09 현장 부재 오프라인 준비 — 실기 BLOCKED_FOR_PHYSICAL_RUN

- 사용자 현장 부재 지시를 지켰다. LeLab 시작, serial 개방, 토크 변경, Goal_Position, live replay, 자세 변경은 전부 `NOT_RUN`. 마지막 실제 follower 값은 앞선 읽기 결과 `(Pan +19.297,Lift −42.769,Elbow +86.989,Flex −31.165,Roll +3.824)°`일 뿐 현재 fresh 값이라고 주장하지 않는다.
- 한시 Elbow 방향 보호 코드를 로컬에서 정리했다. 상한 +90° 인근에서 상한 방향은 엄격 차단, 감소 방향은 허용하되 연속 요청 목표 2.0° 초과 단계는 clipping 없이 차단한다. 하한 −100° 대칭, URDF 밖 목표 차단, 차단 전 관절·현재/요청/차이·양쪽 여유·방향·이유 로그. 패치 hunk 형식은 수정했고 가짜 버스 포함 9/9 PASS. **Jetson 설치 `teleoperate.py`는 미변경**: SSH 네트워크 권한 확보 뒤에도 비대화식 인증이 실패해 배포·Jetson `patch --dry-run`·설치 Python dry-run은 `BLOCKED`. 설치 원본 SHA `a5ac255d...8102576` 대조·백업 뒤 적용해야 한다.
- 4배 접근 replay는 trajectory/calibration/URDF/tracking/scheduler를 바꾸지 않고 target별 송신 반환·feedback 읽기 시작/끝·오차·URDF 여유·guard 상태 로그만 보강했다. 로컬 관련 23/23, 독점 버스 10/10, 4배 접근 640개 dry-run/URDF 최소 여유 7.582° PASS. 로컬 기록 포함 87ms 가짜 버스 640/640 PASS(모의 324.680초). 새 로깅본 Jetson 배포·설치 Python dry-run은 `NOT_RUN/BLOCKED`.
- 기존 SHA 고정 `follower_command` 후보를 새 경로 생성 없이 5개 phase로 잘라 오프라인 검사했다: approach 640, grasp 459, transport 141, place 199, retreat 72개, 합계 1511개. 각 phase URDF 5° 여유와 인접 팔 2°/gripper 2%p 이내, 87ms 이상적 fake feedback에서 각 phase 및 전체 순차 dry-run PASS. `C를 빨강 바구니에 옮겨`를 C→red route로 해석해 이 dry-run에 연결했다. 이는 물리 추종·충돌·물체 잡힘 검증이 아니며 후속 phase live 실행기는 없음(`DRY_RUN_ONLY`). 역할별 포트 pure preflight는 follower-only/leader-only/teleop 양쪽 및 permission/busy 구분을 3/3 가짜 검사로 확인; 현장 포트 실제 점유는 재검증 필요.
- 정확한 다음 리더 목표는 내일 세션 시작 시 측정되는 Elbow/Wrist 오프셋에 따라 달라진다. 과거 Elbow +2.945°는 당시 실측이고 +3.5°는 cap일 뿐, 내일 고정 보정값이 아니다. 정렬·fresh 시작 전 확정 leader-side 숫자는 `NOT_VERIFIED`; 새 입력용 오프라인 목표 계산기 2/2 PASS. 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`, 원본 실기 로그·비밀정보·데이터셋은 Git 제외. [상세 및 내일 절차](sessions/2026-10-09-c-red-complete-teleop-demo.md).
- 전체 로컬 suite는 257개 중 5개 환경 오류로 완료되지 않았다: `websocket` Python 모듈 없음 1개, sandbox의 localhost bind 금지로 웹 캡처 테스트 4개. 관련 목표 시험 56/56은 별도로 PASS; 이 5개를 코드 회귀 통과로 둔갑시키지 않는다.

## 2026-10-09 LeLab 정상 시작 복구, safe_start 복귀 중 Elbow 한시 보호 차단

- canonical `/dev/ttyACM0` follower `5AE6058306`, `/dev/ttyACM1` leader `5AE6085272` 모두 `root:dialout 660`, 사용자 `dialout` 구성원·두 장치 `rw` 확인. 사용자 인증 `sudo fuser`는 두 포트 PID 없음/exit 1; 읽기 뷰어 종료 뒤 `lsof` 대상 PID 없음(무관한 mount 경고). 포트 검사 구조·서비스·calibration·URDF·trajectory·guard 변경 없음.
- LeLab UI 시작 성공 알림 직후 worker가 종료된 실제 첫 오류는 `Temporary alignment blocked by shoulder_lift mismatch`(21:11:45 KST). LeLab OFF에서 기존 읽기 전용 8033으로 리더/팔로워를 다시 맞췄고, 그리퍼는 손을 놓으면 값이 올라가므로 시작 전 유지했다. 정렬 뒤 기존 UI 시작은 실제 `teleoperation_active=true`, 8032 fresh stream `error=null`로 확인했으며 사용자는 3초 정지·급격한 움직임 없음·현장 여유를 확인했다. **LeLab 정상 시작 복구 PASS**.
- safe_start 수동 이동은 두 번 모두 설치 한시 guard `Temporary elbow target exceeds starting position by 0.5 degree`로 종료(21:26:03, 21:34:04 KST). 이는 시작 실패가 아니라 이동 중 새 목표 차단이다. 첫 종료 뒤 현장 정지·비접촉, 두 번째 종료 뒤 현장 안전을 사용자가 확인했고 서버 inactive. 최근 read-only follower `(Pan +19.297,Lift −42.769,Elbow +86.989,Flex −31.165,Roll +3.824°)`는 URDF Elbow +90°까지 3.011° 여유다. 마지막 leader는 Lift/Flex 등과 크게 달라 재시작 정렬 상태가 아니며, 현재 8031 뷰어 종료·두 포트 해제. `+0.5°`는 이전 한계 인근 출발용 한시 장치이며 임의 해제/완화 `NOT_RUN`; 현장 비접촉만으로 관절 한계 위험을 배제하지 않는다. safe_start 도착·자동 approach live `NOT_RUN/BLOCKED`. 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-09 safe_start 수동 복귀 시작 보류 — LeLab UI/서버 상태 불일치

- 리더 팔 5축과 그리퍼를 기존 읽기 전용 화면에서 follower에 맞춘 뒤 화면을 종료했다. 사용자의 향후 요청인 **리더 관절 읽기 화면의 그리퍼 값 표시**는 이번 재시험 중 코드 변경 금지에 따라 `NOT_IMPLEMENTED`로 남긴다.
- 사용자가 현장 여유·C 제거를 확인하고 LeLab 시작을 두 차례 시도했으며 팔은 정지했다고 보고했다. 그러나 두 시도 후 8000 `/teleoperation-status`는 반복해서 `teleoperation_active=false`, Mac 8032 관절 방송의 마지막 수신은 11:06:46 UTC로 오래됐고 `WebSocketTimeoutException`이었다. 원래 LeLab 탭의 녹색 `Live Robot Data`와 시작 성공 알림은 실제 활성 증거가 아니다. 별도 `lsof`에서 두 USB 포트 대상 PID는 표시되지 않았다(무관한 mount 경고로 전체 가시성은 제한).
- 방송 신선도와 제어 소유권을 확인할 수 없어 리더 이동·safe_start 도착·새 follower 측정·자동 approach live 모두 `NOT_RUN/BLOCKED`. 추가 시작 시도와 설정/trajectory/guard 변경도 하지 않았다. 원인은 아직 `NOT_VERIFIED`; 서버 실제 활성과 새 방송 확인 전 로봇을 움직이지 않는다. 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-09 scheduler_overrun 단일 원인 수정 — 모의 640/640·Jetson dry-run PASS, live NOT_RUN

- `CAUSE CONFIRMED (code/log)`: 마지막 live는 105번째 `seq 34182`까지 송신했고 106번째 `seq 34184`의 사전 deadline에서 중단됐다. target 95–105에는 settle 추가 읽기가 **0회**다. 이 구간 4배 계획 간격은 16–64ms, 실제 fresh feedback 간격은 약 84–89ms여서 계획 대비 상대 지연이 0.472초 증가했다. 앞선 8개 settle의 feedback-span 합은 0.758초지만 기존 `hold_extension`은 settle만 반영하고 일반 send/read/검사 시간을 누적 일정에서 누락했다. 실제 send_action 호출시각·정확한 settle 소요시간은 구 로그에 없어 추정값으로 채우지 않는다. 관찰된 버벅임과 간격 불일치는 연관 가능성이 있으나 물리적 원인 단정은 `NOT_VERIFIED`.
- `ONE SCHEDULER CHANGE`: 매 목표의 fresh feedback 및 기존 안전 검사를 끝낸 시각으로 다음 원래 4배 간격을 재기준화한다. 0.5초 overrun 차단, URDF·tracking·feedback timeout과 모든 목표/순서는 유지하며 건너뛰기·catch-up burst 없음. 다음 live 진단을 위해 계획/재기준화 deadline, send_action 호출, feedback 읽기, settle, 누적 지연 시각을 별도 timing 로그에 기록한다. trajectory/calibration/time-scale/URDF/tracking guard 변경 없음.
- `OFFLINE PASS`: 목표 95–105의 실제 4배 간격과 87ms 가짜 버스 왕복을 사용한 모의시험 및 기존 안전 회귀 포함 12/12 PASS. 실제 후보 640개를 같은 가짜 버스로 재생한 오프라인 모의 640/640 PASS; nominal 269.000초가 재기준화 때문에 324.680초로 늘어났으며 최소 목표 간격 위반 없음. Jetson 기존 코드 SHA `ae430909...a82ea7` 별도 백업 후 새 SHA `782a6cd3...a43540` 일치 배포, 설치 Python 문법·4배 dry-run 640개/nominal 269.0초/URDF 최소 여유 7.582° PASS. 포트 개방·모터 송신 `NOT_RUN`. 첫 로컬 unittest 모듈 경로 지정 오류는 discover 재실행으로 해결; 직접 scp 인증 실패 후 원격 `patch --dry-run`/적용과 SHA 대조로 배포. 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-09 수정본 4배 접근 live — 105/640에서 scheduler 중단, 정지 확인

- `SITE/PREFLIGHT PASS`: 사용자 C 제거·경로 여유·팔 정지·현장 감독 준비 재확인. LeLab teleop/recording/inference inactive, canonical follower read-only 3회가 `(Pan +14.374,Lift −23.429,Elbow +29.670,Flex +4.088,Roll −20.176,gripper 2.754%)`로 동일해 safe_start 팔 5축 ±3°·URDF 내부. 인증된 Jetson 터미널의 `fuser`는 두 포트 PID 없음/exit 1. 에이전트 별도 SSH tty의 sudo 캐시는 없으므로 그 터미널에서만 내장 포트 gate를 통과시켰다.
- `FIRST PROMPT ERROR / NO MOTION`: 동일 명령의 첫 시작은 확인 문자열 오타 `RUN APPRACH`로 `NOT_RUN`; 목표 0회. 그 로그를 보존하고 포트·현장·LeLab을 다시 확인한 뒤 정확한 `RUN APPROACH`로 새 시도를 시작했다.
- `LIVE PARTIAL / ABORTED`: 승인된 `safe_start→approach` 4배 한 구간만 실제 실행. **105/640 목표, 마지막 `seq 34182`** 뒤 `TrialAbort: scheduler_overrun`으로 추가 목표를 차단했다. URDF/tracking/feedback-timeout guard 발동 기록은 없으며 grasp 이후 단계 `NOT_RUN`. 송신 105개와 기록된 fresh feedback 113개를 대조한 최대 팔 command−feedback 절대오차는 Shoulder Lift 4.791°(`seq 31733`), gripper는 2.199%p. command/feedback 전체 최소 URDF margin은 Elbow feedback 7.495°(`seq 32193`). 실기 로그는 Jetson Git 제외 `approach-live-20261009-settle-retrial-2.log`, SHA-256 `5bf06f94...bc38164`.
- `STOP VERIFIED`: 프로그램 `encoder_stillness=PASS`, 사용자 실제 팔 정지·비접촉·사람 위험 없음 확인 후 `STOPPED` 입력, 로그 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. 별도 follower read-only 0.5초 간격 5회는 모두 `(Pan +18.505,Lift −32.132,Elbow +82.505,Flex −32.220,Roll −7.692,gripper 20.135%)`로 동일. 사용자는 시연과 같은 방향으로 움직였고 버벅임도 보였다고 보고했다. 그것이 4배 시간축 때문인지는 미확인. LeLab inactive·읽기 포트 해제. **640/640 미완료**, 추가 자동 송신/재시도 `NOT_RUN`; trajectory/calibration/time-scale/URDF/guard 변경 없음. 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-09 수정본 4배 접근 재시험 최종 게이트 — PASS, live 미실행

- `PORT OWNER PASS`: 사용자 Jetson 터미널에서 승인된 `sudo fuser /dev/ttyACM0 /dev/ttyACM1`은 PID 출력 없이 `fuser_exit=1`; follower 읽기 연결을 닫은 뒤 `sudo -n fuser` 재확인도 동일했다. 별도 `lsof` 역시 대상 장치 PID는 표시하지 않았으나 무관한 mount 경고가 있었다. sudo는 포트 점유 확인에만 사용했고 기타 root 작업 없음.
- `FRESH POSE PASS`: canonical follower serial `5AE6058306`을 읽기 전용으로 0.5초 간격 4회 읽어 모두 동일한 `(Pan +14.374,Lift −23.429,Elbow +29.670,Flex +4.088,Roll −20.264,gripper 2.754%)`를 확인했다. write/sync_write 차단, `disconnect(disable_torque=False)`. safe_start 팔 5축 차이 `(+2.638,−1.099,−2.770,−1.450,+0.132)°`, 모두 ±3° 및 URDF 내부(최소 arm limit margin Elbow 60.330°).
- `SITE/SERVICE PASS`: LeLab teleop/recording/inference active=false를 새로 확인했고, 사용자가 C 범위 밖·접근 경로 사람/장애물/접촉 우려 없음·팔 정지를 현장에서 재확인했다. 현재 자세·현장 조건의 실행 직전 게이트는 통과했으나, **이번 턴에서 자동 `send_action`/live는 `NOT_RUN`**. 실행 시 동일 Jetson 터미널의 sudo 인증 캐시와 새 현장 확인이 필요하며, 명령 중단은 물리적 즉시 정지를 보장하지 않는다. trajectory/calibration/time-scale/URDF/guard 변경 없음. 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-09 수정본 4배 자동 접근 재시험 준비 — 수동 복귀 완료, 내부 포트 게이트 차단

- `MANUAL RETURN PASS`: LeLab OFF에서 읽기 전용 8033으로 리더/팔로워 5축 차이 최대 1.099°를 확인하고 viewer를 닫아 두 포트를 해제했다. 사용자가 C 제거·빈 gripper·주변 여유를 확인한 뒤 LeLab을 직접 시작, 3초 정지·점프/간섭 없음. 실시간 방송이 새 시각으로 갱신되는 것을 확인하며 safe_start 근처로 사람 감독 수동 이동, 리더를 유지한 채 종료. LeLab teleop/recording/inference inactive, 현장 팔 정지·비접촉 확인.
- `FRESH FOLLOWER PASS`: 종료 후 canonical follower `/dev/ttyACM0`(serial `5AE6058306`)만 읽기 전용 연결해 0.5초 간격 4회 측정. raw `(2265,1688,2321,2127,1635,458)` 및 degree `(Pan +14.374,Lift −23.429,Elbow +29.670,Flex +4.088,Roll −20.176,gripper 2.754%)`가 모두 동일. 팔 5축 safe_start 차이는 `(+2.637,−1.099,−2.769,−1.451,+0.220)°`, 전 축 ±3°·URDF 내부(최소 arm limit margin Elbow 60.330°). 읽기 코드의 write/torque API 차단, `disconnect(disable_torque=False)` 후 포트 해제.
- `ALTERNATE OWNER CHECK PASS / PROGRAM PREFLIGHT BLOCKED`: 권한 없는 `lsof -nP -- /dev/ttyACM0 /dev/ttyACM1`이 읽기 viewer PID `533997`의 두 포트 점유를 표시했고, viewer 종료 및 follower 읽기 종료 뒤에는 대상 장치 사용 프로세스를 표시하지 않았다. 무관한 mount 경고가 있어 전체 시스템 가시성의 절대 증거는 아니나 해당 동일 사용자 장치 점유 검출은 실증됐다. 반면 설치 프로그램의 `SystemBusProbe.owner_pids()`는 일반 `fuser`의 `/proc Permission denied`에서 `sudo -n fuser`로 넘어가며, 현재 sudo 인증이 없어 live 내장 게이트는 `port_ownership_unknown`으로 차단될 전망이다. sudo 인증 캐시 갱신은 검토 단계에서 거절돼 우회하지 않았다. **live ready 아님**, 사용자 지시의 추가 로직 변경 금지에 따라 preflight 코드는 그대로 둔다.
- `UNCHANGED`: Jetson replay SHA `ae430909...a82ea7`, adapter `4c1872a1...e071f2d71`, 후보 `684d90e6...f265fa`, calibration `2f74c130...e29c2e`, 설치 URDF 검증 일치. trajectory/time-scale/URDF/guard 변경 없음. 자동 `send_action`/4배 live `NOT_RUN`; 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`. 다음은 내장 포트 게이트를 유지하면서 인증 문제를 해결할지, 읽기 전용 `lsof` 대안을 코드에 최소 반영할지에 대한 사용자 지시가 필요하다.

## 2026-10-09 접근 replay settle 판정 한 곳 수정 — dry-run PASS, live NOT_RUN

- `ONE LOGIC CHANGE`: `scripts/replay_c_red_approach.py`의 settle 루프에서 매 fresh feedback을 어떤 차단 판정보다 먼저 기록한다. 관절별 별도 증가 횟수를 사용하고 arm 오차 <1.5°(gripper <4%p)에는 growth 판정을 적용하지 않는다. 의미 있는 오차에서 연속 2표본이 각 +0.5°(+1%p)를 넘게 증가할 때만 `tracking_error_growing_during_settle`로 차단한다. 사용자 확인에 따라 기존 4° tracking 기준은 즉시 중단선이 아니라 최대 2초 수렴 대기 진입선으로 유지한다. 기존 URDF 5° 여유·절대오차 기준·2초 timeout 유지, 큰 오차 far guard는 모든 settle 표본에서 재확인한다. trajectory/calibration/time-scale·LeLab/torque 변경 없음.
- `FAKE BUS PASS`: 실제 target 20–35의 Lift/Elbow/Wrist goal과 target 20–28의 기존 4배 피드백을 모의 입력으로 사용했다. target 29의 Elbow 0.044°→0.75° 일시 변화는 허용하고 35까지 진행; 의미 있는 오차의 연속 발산, 4° 오차 미회복, 큰 절대오차, URDF 위반은 다음 목표 전 차단하며 차단 표본을 기록하는 관련 시험 10/10 PASS. 독점 버스 관련 시험 10/10 PASS.
- `JETSON DRY RUN PASS`: Jetson 시험 폴더에서 기존 replay 원본 SHA `9a1015be...d1201456`를 별도 백업하고 수정본 SHA `ae43090978de7d267cfd236a7bf3e480ebb99fb2d982d441362492f8f1a82ea7`만 배포했다. adapter/candidate SHA는 기존과 일치. 설치 Python `--time-scale 4` dry-run은 640개/269.0초, 순서·시각·URDF PASS(최소 arm margin 7.582°), 포트 개방·`send_action` 0회. 실제 모터 명령 `NOT_RUN`. dry-run 뒤 `sudo -n fuser`는 비밀번호 필요로 점유 재확인을 완료하지 못했으므로 **실기 직전 포트 독점 재검사 필수**.
- `NEXT`: 현재 follower 최종 읽기 자세는 safe_start가 아니다. 사용자 감독 수동 복귀→LeLab 완전 종료→fresh ±3°·URDF·C 제거·주변 여유·follower 단독 포트 확인→사용자 최종 승인 뒤에만 같은 4배 `safe_start→approach` 한 구간을 재시험한다. 중단 뒤 실제 정지는 feedback과 현장 확인을 별도로 요구한다. 자동 C→빨강 `NOT_RUN`; 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-09 target 20–35 보정 경로 집중 점검 — 추가 구동 없음

- `DOUBLE COMPENSATION RULED OUT`: 후보 `goal`은 시연 `follower_command` 복사본이며, replay의 `point["goal"]`→adapter `send_goal()`→설치 `SO101Follower.send_action()`까지 Elbow/Wrist degree 값이 변하지 않는다. 실기 로그의 target 20–29 반환 command도 JSON과 일치했다. 한시 Elbow +2.945° 및 Wrist 보정은 LeLab `teleoperate.py`의 **리더 입력에만** 적용되며 자동 replay에는 적용되지 않는다. 설치 calibration SHA `2f74c130...e29c2e`의 DEGREES→raw 변환은 별개다. target 30–35는 미송신.
- `ABORT MECHANISM CONFIRMED / PHYSICAL CAUSE NOT_VERIFIED`: 4배 target 28→29 Elbow 목표·`send_action` 반환은 +37.890110→+38.769231°(+0.879121°, 계산 raw 2414→2424), Wrist는 −0.263736°/raw 2077 그대로다. Elbow fresh feedback은 28 마지막 +38.549451→29 첫 +38.725275°(+0.175824°), 첫 오차 0.043956°. Lift 첫 오차 4.351648°가 4° guard를 넘어 수렴 대기에 진입했고, 바로 다음 미기록 피드백에서 Elbow 오차가 첫값보다 0.5° 초과 증가해 중단됐다. 미기록 표본의 정확한 값·방향과 실제 모터 패킷/수신 여부는 `NOT_VERIFIED`; 속도 변경이나 이중 보정이 원인이라는 결론은 아니다. 기존 4배 dry-run 640개/269.0초·URDF PASS, 관련 로컬 시험 5/5. 안전 guard·trajectory·URDF·time-scale 변경 및 모터 명령 `NOT_RUN`.
- `NEXT`: 동일 설정 재실기 금지. 먼저 이 미기록 abort 표본을 보존하는 최소 진단 변경과 가짜 피드백 시험을 별도 검토하고, guard 완화는 실제 표본의 범위가 확인되기 전 하지 않는다. 현재 팔 자세는 safe_start가 아니며 새 수동/자동 실기에는 현장 재확인·별도 승인 필요. 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-09 수정본 자동 접근 2배·4배 재시험 — 같은 지점 안전 중단

- `MANUAL RETURN PASS`: LeLab 사람 감독 복귀 뒤 follower fresh 자세 `(Pan +10.418, Lift −19.912, Elbow +33.099, Flex +5.143, Roll −19.033)°`/gripper `2.754%`가 두 번 동일했다. safe_start 팔 5축 ±3°·URDF 내부, LeLab OFF·ACM0/ACM1 무점유를 확인했다.
- `DRY RUN PASS`: 설치 Python에서 수정본 640개 목표·URDF PASS. 2배 약 134.5초와 4배 약 269.0초 모두 dry-run 포트 개방·모터 송신 0회다.
- `LIVE PARTIAL / ABORTED`: 별도 현장 승인을 받은 C 없는 자동 접근은 2배와 4배 모두 **29/640번째 `seq 31743` 송신 뒤** `tracking_error_growing_during_settle:elbow_flex`로 추가 목표를 차단했다. 4배 첫 fresh feedback의 Elbow는 command +38.769°/actual +38.725°였으나, Lift 추종을 기다리는 동안 Elbow 목표 오차가 첫 값보다 0.5° 넘게 커졌다는 코드 판정이다. 그 추가 표본 자체는 로그에 남지 않아 구체 시각·값과 물리 원인은 `NOT_VERIFIED`; 2배→4배 시간축 변경만으로 해결되지 않았다. 2배 로그 `approach-live-20261009-1758.log`, 4배 로그 `approach-live-20261009-1809.log`(Jetson 시험 폴더, SHA-256 `d4c96999a2c415e0086c163e6c9a1a2853dcc3dd712f61fc19ba31b4027e96c6`), Git 제외.
- `STOP VERIFIED`: 두 시험 모두 encoder stillness PASS 뒤 사용자가 실제 팔 정지·접촉/위험 없음을 확인했다. 4배 종료 뒤 follower `/dev/ttyACM0`을 읽기 전용으로 0.5초 간격 6회 측정했으며 raw 6축 모두 동일, 자세 `(Pan +17.802, Lift −24.659, Elbow +39.516, Flex +0.835, Roll −20.440)°`/gripper `3.182%`, URDF 내부. 읽기 연결은 write/torque API를 차단했고 `disconnect(disable_torque=False)`로 닫았으며 이후 ACM0/ACM1 무점유. LeLab teleop/recording/inference 모두 inactive. 사용자 현장 비접촉 확인. 이전 방송–종료 Elbow 6.24° 차이 원인은 계속 `NOT_VERIFIED`.
- `NEXT`: 첫 자동 움직임 성공은 유지되나 approach 완주와 자동 C→빨강은 `NOT_RUN/NOT_SUCCESS`. 같은 설정 재시도·추가 모터 구동 금지. 실패 표본 미기록을 고려해 원인/단일 변경안을 정하고 새 현장 승인 전에는 live 송신하지 않는다. 이슈 API `NOT_RUN`, 원본 로그 `NOT_COMMITTED`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-09 첫 자동 safe_start→approach 실기 — 28/640 목표에서 안전 중단

- `MANUAL RETURN PASS`: 사용자가 LeLab 사람 감독으로 팔을 safe_start 근처로 이동하고 리더를 유지한 채 종료했다. 종료 뒤 새 follower 피드백 `(Pan +13.758, Lift −23.604, Elbow +34.330, Flex +4.703, Roll −21.670)°`, gripper `2.448%`로 후보 목표의 팔 5축 모두 ±3° 이내·URDF 내부. 재측정에서도 같은 raw/degree로 정지했고 6개 모터 `Torque_Enable=1`, LeLab inactive·ACM0/ACM1 무점유. 사용자는 C가 작업 범위 밖이고 현장 여유가 있다고 확인했다.
- `DRY RUN PASS`: Jetson LeLab Python 3.14.7에 시험 파일 SHA 일치 배포. `--time-scale 2`는 seq 28363→45133, 640개 송신 목표/약 134.5초, 순서·timestamp·URDF PASS, 최소 arm margin 7.582°. dry-run 포트 개방·`send_action` 0회. 첫 live 시도는 일반 권한 `fuser`의 `/proc` 접근 오류를 점유 불명으로 처리해 **포트 개방·목표 송신 전에** 중단. 다른 사용자의 프로세스를 볼 수 없는 경우에만 비대화형 권한 있는 읽기 전용 `fuser`로 재검사하도록 `so101_exclusive_bus.py`를 수정했고 관련 시험 10/10·Jetson 사전 검사 통과. 소유권 차단을 제거하지 않았다.
- `LIVE PARTIAL / ABORTED`: 별도 현장 재확인 뒤 승인된 C 없는 `safe_start→approach`만 실행. `send_action` 목표 28개까지 전송하고 seq 31733에서 `tracking_outside_demo_envelope:shoulder_lift`로 다음 목표 전송 중단. 직전 seq 31723 명령/새 feedback Lift는 `−24.791/−21.407°`; 실패 목표는 `−26.374°`이고 demo reference는 `−22.022°`. **실패 표본의 실제 feedback은 검사 뒤 출력하는 현재 코드상 미기록**이므로 초과 항목을 command 오차와 reference 오차 중 하나로 단정하지 않는다. 원격 로그 `/home/jetson3/so101-approach-trial/approach-live-20261009-1727.log` SHA `11580546...3672bff73b235aea`; Git 제외.
- `STOP VERIFIED / NOT COMPLETE`: 송신 중단 후 encoder stillness PASS와 사용자의 팔 정지·접촉/위험 없음 확인을 별도로 받아 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. 사용자는 움직임이 천천히 예상 방향이었고 이상·간섭은 없었다고 보고했다. 종료 뒤 fresh follower `(Pan +17.802, Lift −23.341, Elbow +38.637, Flex +0.835, Roll −20.791)°`/gripper `3.182%`, URDF 내부. LeLab inactive·ACM0/ACM1 무점유. 전체 approach 640/640 및 C→빨강 자동 사이클은 `NOT_RUN/NOT_SUCCESS`; 같은 시험 자동 재시도 금지. 다음은 실패 표본의 정확한 오차 확인 후 시간축/피드백 차단 방식의 최소 조정안을 정하고, 재실기는 별도 현장 승인으로만 진행한다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
- `NEXT TRIAL CODE PREPARED / NOT_RUN`: 접근 후보에서 기록 command−feedback 격차 최대 gripper 30.721%p가 기존 gripper 8%p의 목표·기록 **동시** 검사와 양립 불가함을 확인했다. 경로·URDF·최소 2배 시간축은 그대로 두고 새 목표 대비 오차만 guard로 사용, 초과 때 새 목표를 보내지 않은 채 최대 2초간 fresh feedback 수렴을 기다리며 오차 증가·URDF·통신 이상은 중단하도록 실행부를 수정했다. 차단 표본도 출력하도록 순서를 바꿨다. 관련 모의/독점 시험 15/15, Jetson 설치 Python dry-run PASS; 새 로직 실제 송신 `NOT_RUN`. 현재 팔은 safe_start가 아니므로 재실기는 리더/팔로워 재정렬→사람 감독 safe_start 복귀→현장 재확인·별도 승인 뒤에만 가능하다.
- `SECOND MANUAL RETURN STOPPED`: 재시도 준비를 위해 읽기 전용 8033에서 리더/팔로워를 팔 5축 ±1.802°로 맞추고 화면 종료·포트 해제했다. 사용자가 별도 승인 뒤 LeLab을 직접 시작해 3초 정지·이상 없음을 확인했으나, safe_start 복귀 중 8032 방송이 마지막 `(Pan +17.538,Lift −22.462,Elbow +40.044,Flex +1.011,Roll −20.352)°` 이후 갱신되지 않아 즉시 중단을 요청했다. 사용자가 직접 LeLab을 종료했고 팔 정지·접촉/위험 없음을 확인했다. 종료 후 두 fresh 읽기가 같은 follower `(Pan +17.714,Lift −20.352,Elbow +46.286,Flex +1.099,Roll −20.440)°`/gripper `2.815%`이며 URDF 내부, LeLab inactive·포트 무점유. 마지막 방송과 종료 후 실측 간 Elbow +6.242° 차이는 어느 시점의 리더 명령/방송 중단 때문인지 기록이 없어 `NOT_VERIFIED`; 방송 시간 초과가 실제 텔레옵 중 발생했는지 종료 직후 발생했는지도 `NOT_VERIFIED`. safe_start 복귀·수정 실행부 live 재시험 `NOT_RUN`; 방송 신선도와 종료 시점의 관계를 확인하고 현장 승인 전 추가 이동 금지.

## 2026-10-09 LeLab 시작 3.2초 정지 시험 — 통과, safe_start 이동 전

- `PASS (USER-STARTED TELEOP STILLNESS)`: 사용자 현장 확인 후 LeLab 시작, 리더 고정. 설치 임시 worker가 3.202초/796주기 뒤 `stillness_window_complete`로 명령 생산·전송을 종료했고 오류 0건이다. 원본 기록 Jetson `/home/jetson3/so101-approach-trial/stillness-traces/1791532404670180932/cycles.jsonl`, SHA `013a3eb6...12a70`; leader/실제 `send_action` 반환 command/fresh follower feedback 분리 저장. 첫 Elbow command +97.538°는 리더 +94.593°에 실측 오프셋 +2.945°를 더한 값이며, +3.5°는 hard cap만 맡는다. 첫 Flex command +57.714°는 리더 +55.297°에 +2.417°를 더한 값이다.
- `MEASURED`: 3초 동안 command 변화 전 축 0°. 첫 피드백 대비 최대 변화 Pan 1.407°, Lift 1.231°, Elbow 0°, Flex 0.088°, Roll 1.582°, gripper 0%p. 사용자는 큰/이상 움직임 없이 팔 정지를 육안 확인했다. 종료 뒤 16:54:54·16:55:21 KST 두 fresh 읽기가 동일하고 LeLab inactive·ACM0/ACM1 무점유; 송신 종료와 실제 팔 정지를 별도 확인했다. Elbow는 여전히 +97.538°로 URDF 상한 +90° 밖이다. `safe_start` 이동·자동 접근/재생 `NOT_RUN`. 1회 기록 티켓은 소모돼 재시작은 차단; 한시 소스/환경은 후속 안전 정리 전까지 설치 상태다.

## 2026-10-09 한시 손목 정렬 준비 — 위 시험 전 상태

- `PREPARED / NOT_RUN`: 사용자 승인 범위에서 Jetson 설치 LeLab `teleoperate.py`에 이번 수동 복귀 세션용 `LELAB_TEMP_WRIST_ALIGN=1` 손목 명령 오프셋을 적용하고 서비스만 재시작했다. 원 설치본 SHA `cfe3e942...75dd3` 백업 확인, 한시 설치본 SHA `19436c24...5d5e9`, 설치 Python 문법 통과. 가짜 버스에서 손목만 첫 현재값에 맞추는 송신 1건·다른 축 불일치/손목 차이 과대 시 송신 0건을 검증했다. 실제 텔레옵은 inactive이고 프로그램 자동 `send_action`/실제 모터 명령은 `NOT_RUN`.
- `PREPARED / NOT_RUN`: 사용자가 리더 Elbow +94.59° 최대를 확인하고 3.5° 상한의 세션 한정 팔꿈치 보정을 승인했다. 실제 적용값은 fresh 차이 +2.945°이며 고정 +3.5°가 아니다. 손목 +2.418°도 첫 목표를 현 follower에 맞춘다. 비보정 축·gripper >2.5°, 팔꿈치 보정 >3.5°, 손목 >15° 또는 팔꿈치 목표가 시작값 +0.5° 초과 시 추가 송신 차단. [패치](../patches/lelab-20261009/teleoperate-temp-wrist-elbow-align.patch)를 Jetson 시험 폴더에서 dry-run/문법·가짜 버스 5건 검증 후 설치했고 SHA `a5ac255d...102576`, LeLab 재시작 후 텔레옵 inactive. 마지막 fresh 차이는 Pan +1.758°, Lift +1.890°, Elbow −2.945°, Flex −2.418°, Roll −1.978°, gripper +0.002%p. 읽기 화면 종료와 ACM0/ACM1 무점유 확인. 현장 확인·사용자 직접 시작은 아직 별도이며 실제 송신/자동 접근 `NOT_RUN`; 세션 뒤 한시 코드는 복원한다.

## 2026-10-09 첫 자동 접근 시험 준비 — 하드웨어 비접속

- `PREPARED / NOT_RUN`: 기존 SHA 고정 C→빨강 후보의 `safe_start seq 28363 → approach seq 45133` 640개 목표만 고르는 시간축 2배 이상 시험 연결부 `scripts/replay_c_red_approach.py`를 추가했다. 기본 명령은 dry-run이고 실제 송신은 `--live`, 범위 확인, 현장 입력을 모두 요구한다. 시작 자세 fresh feedback, 기존 시연 추종 오차 기반 중단선, 새 feedback, URDF 여유 5° 하한, LeLab idle/USB 독점 게이트를 사용한다. 송신 종료와 팔 정지 확인은 별도 출력이다. 기존 adapter의 설치 LeRobot 0.6.0 클래스 이름을 실제 성공한 읽기 전용 viewer와 일치하도록 `SO101Follower`/`SO101FollowerConfig`로 바로잡았다. 모의 시험 3개와 기존 독점 adapter 시험 9개 통과, 원본·후보 변경 없음. Jetson 배포·LeLab 시작·모터 명령·실제 자동 접근은 `NOT_RUN`.
- `NEXT`: 현재 Elbow +96.571°는 URDF 밖이므로 LeLab 사람 감독으로만 safe_start 수동 복귀하고 종료 후 새 feedback·공간 여유를 확인한다. 이후 Jetson에 연결부/후보 배포 및 설치 Python 검증, C 제거, 실기 범위/중단법 별도 승인 뒤에만 첫 자동 접근 시험을 실행한다. 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-09 전체 C→빨강 trace의 수치 경로 추출 — 하드웨어 비접속

- `OFFLINE_NUMERIC_CANDIDATE_ONLY`: 원본 SHA `01a8b481...005bf18978`을 재확인하고 107,422주기 중 `seq 28363–94174`의 65,812주기를 새 후보 구간으로 골랐다. 시작 t=14:28:11.268 KST는 approach 전 249표본/약 1초 안정, 명령·피드백 최소 URDF 여유 55.407°. 종료 t=14:32:35.196 KST는 retreat 후 251표본/약 1초 안정, 그리퍼 약 33% 열림, 최소 여유 68.594°. 둘 다 **관절 수치 후보**이며 같은 시각 영상이 없어 시작 C 비접촉·종료 테두리 이탈을 영상으로 독립 확정하지 못했다.
- `EXACT CUTOFF`: Elbow 첫 URDF 상한 초과는 command `seq 94849`, 14:32:37.894 KST, 직전 +89.670°→+90.022°; fresh feedback `seq 94868`, 14:32:37.971 KST, 직전 +89.978°→+90.242°. 후보 종료 뒤 13,247주기 전체를 제외했고 limit 값으로 clipping하지 않았다. 포함 구간의 command·feedback 팔 5축은 모두 설치 URDF 범위 안이며 최소 여유는 approach `seq 32208` Elbow 7.583°다.
- `DOWNSAMPLE`: 이벤트 양쪽, 단계 완료점, 82개 뚜렷한 방향 전환, 91개 gripper 임계값 통과를 보존했다. 균형안 1,512점(원 구간 대비 43.5배 압축)은 원 command의 시간 선형 보간 오차 각 팔 축 <0.5°, gripper <1%p, 인접 목표 차이 팔 <2°/gripper <2%p다. [분석 JSON](../.local/teleop-cycle-traces/2026-10-09-c-red/analysis/analysis.json)과 [후보 JSON](../.local/teleop-cycle-traces/2026-10-09-c-red/analysis/trajectory_candidate.json)은 Git 제외·`motion_authorized=false`. 명령−피드백 원시 오차는 Lift 최대 8.659°, Elbow 최대 8.747°라 수치 압축 적합만으로 자동 재생 안전을 인정하지 않는다. [세션](sessions/2026-10-09-c-red-complete-teleop-demo.md).
- `NEXT / NOT_RUN`: 현재 실제 팔 최종 Elbow +96.571°는 여전히 URDF 밖이다. 후보 시작 자세로의 실물 복귀, 영상상 손끝·병·테두리 간격 확인, 충돌/속도/추종오차 게이트 검증 및 별도 실기 승인이 남는다. 이번 분석 중 LeLab·USB·모터·토크·`send_action` 접근 `NOT_RUN`; 원본 로그 미수정, 추출 단위 시험 2/2, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.

## 2026-10-09 C→빨강 전체 사람 감독 텔레옵 시연 — 수동 성공, 자동 재생 불가

- `USER-CONFIRMED MANUAL SUCCESS`: LeLab OFF에서 리더/팔로워 팔 5축을 읽기 전용으로 비교했다. 최초 차이는 Elbow +8.396°·Wrist Flex −30.813° 등이어서 시작을 막았다. Jetson 8031 읽기 전용 화면으로 리더만 재정렬한 최종 차이는 Pan +0.176°, Lift +0.484°, Elbow +0.484°, Wrist Flex −1.538°, Roll −1.714°. 화면 종료·두 포트 해제 후 사용자가 텔레옵을 직접 시작했다. 첫 3초 740주기에서 시작 자세 대비 최대 명령 1.714°·피드백 1.495°, 기록 오류 0건, 현장 급격한 움직임 없음. 이후 사용자가 공중 여유 자세→C 접근·집기·빨강 이동·놓기·비접촉 퇴피를 단계별로 직접 확인했다. 이는 **사람 조작 성공 보고**이며 프로그램 제어/자동 분류 성공이 아니다.
- `TRACE PRESERVED`: Jetson `/home/jetson3/lelab-teleop-cycle-traces/1791523577320343828/`의 `cycles.jsonl` 107,422주기/430.853초, `events.jsonl` 접근→집기→이동→놓기→퇴피 5개, 오류 0개. manifest `data_complete=true`, cycle SHA-256 `01a8b48183ed90d1acc34d70ce855520e9fa75f75fa6d1ffaae822005bf18978`. Git 제외 로컬 `.local/teleop-cycle-traces/2026-10-09-c-red/`에 복사하고 SHA 일치를 확인했다. manifest의 `physical_task_success_verified=false`는 자동 판정이 없다는 뜻이며, 현장 성공은 별도 사용자 확인이다. [세션](sessions/2026-10-09-c-red-complete-teleop-demo.md).
- `AUTOMATION BLOCKER`: 새 기록의 URDF 초과는 퇴피 구간 Elbow에만 있다. command 12,573주기/최대 +7.494°, feedback 12,554주기/최대 +6.571° 초과; 최종 feedback +96.571°로 상한 +90° 밖. 나머지 구간·팔 관절은 기록상 한계 안이지만 충돌·재생 안전 경로가 검증됐다는 뜻은 아니다. 이 퇴피/종료 자세를 자동 waypoint로 사용하지 않는다. 자동 `send_action`·trajectory replay `NOT_RUN`.
- `CLEANUP`: 1회 기록 티켓 소모 후 환경 설정을 해제하고 LeLab 웹 서비스만 재시작했다. 서버 teleop inactive·follower/leader 포트 무점유 확인, 추가 팔 동작 없음. 기록 모듈 5개 단위 시험 통과, 8031 읽기 전용 화면 실측 확인; 이슈 갱신 `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`. 다음은 현 Elbow 한계 밖 자세를 **움직이지 않은 채** 안전한 시작/퇴피 대안의 범위를 정하고, 별도 승인 전 실제 구동하지 않는다.

## 2026-10-08 Jetson 주기별 기록 패치 적용·시작 복귀 경유 후보 — LeLab 미실행

- `APPLIED ON DISK / NOT_ACTIVE`: Jetson LeLab 0.1.0/Python 3.14.7 설치 `.../site-packages/lelab/teleoperate.py` 원본 SHA `2a54de45...33931e2`를 확인해 `/home/jetson3/lelab-source-backups/teleoperate.py.2a54de453da35fb0d80bf37398ae3d2b0ed17dbbb56eea3077a71e7ab33931e2`로 백업했다. 첫 GNU patch dry-run의 `malformed patch` 형식 오류를 수정 후 재검사 통과했고, 기록 모듈과 패치를 설치했다. 새 SHA `teleoperate.py=211f3485...3c909`, 기록 모듈 `c47732a7...32cb2f96`; 설치 Python `py_compile` 통과. LeLab 서비스 재시작·teleop 실행·모터/토크/USB 접근 `NOT_RUN`; 기존 서버는 teleop inactive를 유지한다. 실행 중 프로세스에는 코드가 아직 로드되지 않았다.
- `CAPTURE CONTRACT`: 기록 예정 루트 `/home/jetson3/lelab-teleop-cycle-traces`를 만들었다. `LELAB_TELEOP_TRACE_ROOT`는 아직 서비스에 설정하지 않았으므로 기록은 **미활성**. 활성화 뒤에만 run별 `cycles.jsonl`의 시각·`leader_position`·`follower_command`·`follower_feedback`(각 6축·gripper 포함), `events.jsonl`의 `approach/grasp/transport/place/retreat` 마커, 오류/manifest가 저장된다. command는 sync-write 호출 반환이지 motor ack/도달이 아니다.
- `RECOVERY ROUTE NOT_VERIFIED`: 현 정지 5축 `(-4.176,-98.857,+89.011,+73.802,-13.319)°`에서 같은 장면의 첫 여유 관측 t=44.658s까지 L2 40.55°·최대 축 24.70° 차이다. 이후 t=44.806→45.000→45.118→45.217→45.427s는 실제 관측이고 최소 URDF 여유가 21.71→27.87→36.84→37.20→37.20→37.20°다. 옛 영상은 그리퍼의 C·바구니 투영 분리만 보여 현재 위치~첫 지점의 연속 swept clearance/물리 방향은 입증하지 못한다. 따라서 경유 후보는 **실행 불가**, 시작 복귀 계획 확정 `BLOCKED`; 첫 구간의 실제 주변 여유·단독 제어·미세 이동 방법/중단 기준 검증과 별도 승인이 해제 조건이다. waypoint 송신 `NOT_RUN`, 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-08 C→빨강 완전 수동 시연 재기록 준비 — 하드웨어 변경 없음

- `USER CORRECTION`: 직전 1,198표본 기록에서는 C 병이 빨강 바구니까지 이동하지 않았다. 앞선 영상 단계 추정과 전체 C→빨강 성공 해석은 채택하지 않고, 이 기록은 **C 접근 구간 참고용**으로만 쓴다. 완전한 C 집기→이동→놓기→퇴피 demonstration은 `NOT_RECORDED`다. 기존 원본과 오래된 현장 보고는 삭제하지 않지만 새 전체 경로의 검증 근거로 사용하지 않는다.
- `PREPARED OFFLINE`: 기존 LeLab 텔레옵 worker에 선택적으로 붙이는 [주기별 기록기](../scripts/teleop_cycle_trace.py)와 [설치 소스 패치](../patches/lelab-20261008/teleoperate-cycle-trace.patch)를 만들었다. 활성화 시 같은 worker/버스에서 리더 6축, `send_action` 반환 6축 명령, 매 주기 새 `Present_Position` 6축, 각 단계 시각 마커를 저장한다. 명령 반환은 sync-write 호출 완료이지 모터 수신/도달 증거가 아니다. 가짜 함수 4개 시험과 설치 소스 대상 patch dry-run 통과. Jetson 배포·LeLab 재시작·실제 녹화/이동·프로그램 자동 `send_action` 모두 `NOT_RUN`.
- `START GATE`: 시작 후보는 기존 접근 기록 t=45.427s의 URDF 내부 여유 자세이나 현재 정지 자세에서 후보까지 경로/간격이 미검증이다. Elbow/Shoulder_Lift 한계 근접 현 자세에서 LeLab을 켜거나 기록을 시작하지 않는다. 먼저 사용자 감독 하의 시작 자세 복귀 방법과 이동 범위·중단법을 별도 승인받고 검증해야 한다. 데이터 저장이 준비돼도 완전 시연이나 자동 재생 성공으로 보고하지 않는다. 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-08 다관절 이동 원인 범위·다음 시작 자세 후보 — 코드/기존 기록만, 추가 구동 없음

- `CODE CONFIRMED`: LeLab worker는 매 주기 leader `get_action()`의 6개 `.pos`를 follower `send_action()`/`Goal_Position` sync-write에 전달한다. 별도 pose alignment·homing·시작 보간 호출은 없으나 첫 주기부터 리더 전체 자세가 목표가 된다. 시작 `configure()`는 토크를 일시 해제 후 재활성화한다. 이번 조작의 leader 값/실제 Goal_Position은 저장되지 않아 세부 입력 원인은 특정 불가. 시작 뒤 안정 방송과 사용자 조작 후 큰 변화는 리더 전체자세 추종과 부합하지만 매핑 오류·시작 목표 오차를 단정하거나 완전히 배제할 수 없다. `−2.066° Elbow`, `−44.967° Shoulder_Lift`, 최종 `+73.802° Wrist_Flex`는 follower 피드백이며 송신값이 아니다.
- `OFFLINE START CANDIDATE ONLY`: 기존 C→빨강 관찰의 t=45.427 s/index 879 자세 `Rotation +22.549°, Pitch −45.055°, Elbow +34.857°, Wrist_Pitch +57.802°, Wrist_Roll −10.418°`를 다음 시험용 시작 자세 후보로 선정했다. 팔 5축 최소 URDF 여유는 Wrist_Pitch 상한 37.198°, Shoulder_Lift 하한 54.945°, Elbow 상한 55.143°다. C 접근 참조 t=46.978 s/index 909까지 팔 5축 관절공간 L2 거리는 45.925°이며 당시 천장 영상에서 그리퍼와 C가 분리돼 보인다. 그리퍼 관측 약 34.945%는 URDF Jaw rad와 동일하지 않아 Jaw 한계 검증으로 계산하지 않는다. **현재 최종 자세에서 후보까지의 안전 경로·실물 간격은 미검증**이며 이 후보로 자동 이동/재생 승인되지 않았다. LeLab 재실행·`send_action`·새 모터 명령 `NOT_RUN`; 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.

## 2026-10-08 사람 감독 LeLab Elbow 복귀 시도 — 큰 다관절 이동으로 중단

- `STOPPED / NOT_A_SINGLE_JOINT_TEST`: 사용자가 빈 그리퍼·주변 장애물 제거·리더/팔로워 정렬을 확인하고 직접 LeLab 텔레옵을 켰다. 시작 직후 방송 Elbow +96.571°, Shoulder_Lift −98.418°였고 약 0.4초 안정 표본을 확인했다. 사용자 첫 조작 중 방송 한 표본은 Elbow −2.066°, Shoulder_Lift −44.967°, Wrist_Pitch +59.560°로 큰 다관절 변화였다. 사용자는 실제로 팔이 크게 움직이고 여러 관절이 함께 움직였다고 확인했으며 접촉/위험은 없었다고 보고했다. 즉시 추가 이동을 중단하고 텔레옵 종료·팔 정지를 현장 확인했으며 서버 active=false, follower 포트 무점유를 확인했다. 물리 Elbow 회전 방향은 **미확인**이다.
- `POST_STOP_READ_ONLY`: 별도 포트 점유가 없는 상태에서 raw `Present_Position` 1회로 최종 표본을 읽었다: shoulder_pan ID1 raw2054/−4.176°, shoulder_lift ID2 raw830/−98.857°, elbow ID3 raw2996/+89.011°, wrist_flex ID4 raw2920/+73.802°, wrist_roll ID5 raw1713/−13.319°, gripper ID6 raw470/3.488%. 팔 다섯 축은 URDF 내부이나 Elbow 상한 여유 약 0.989°, Shoulder_Lift 하한 여유 약 1.143°뿐이다. 읽기 중 목표/토크/캘리브레이션 write 시도 0회, 정상 포트 해제 확인. **+89° 도달은 사실이나 안전한 단일 관절 복귀 성공으로 판정하지 않는다.** 프로그램 `send_action`, C waypoint, 전체 사이클 `NOT_RUN`; 추가 동작 금지 상태.

## 2026-10-08 URDF 내부 복귀 방법 설계 — 실제 명령 없음

- `DESIGN_ONLY`: 사용자가 직전 읽기 전용 연결 중 예상 밖 팔 움직임이 없었음을 현장에서 확인했다. 현 Elbow +96.571429°/raw 3082에서 URDF 내부 임시 보유 자세 +89°(설치 변환으로 예상 raw 2995, 약 −87 step/−7.65° 실제 격자 변화)를 비교 기준으로 계산했다. +90° 목표는 정수화 후 URDF 상한 여유가 약 0.022°뿐이어서 선택하지 않았다. +89°는 한계 내부 **임시 자세 후보**이지 C 경로의 검증된 start가 아니다.
- `CHOICE / GATE`: 사람 감독의 LeLab 수동 복귀가 우선 후보지만 기존 수동 제어는 모든 축을 추종하고 속도·단계 크기를 강제하지 않아 시작 자세 일치, 전완/손끝 전체 이동 여유, 실제 elbow 수치 감소 방향을 작은 수동 움직임에서 확인해야 한다. 프로그램의 첫 한계 내부 목표는 현재에서 최소 약 6.57° 떨어져 있어 한계 밖 중간 waypoint 없이 0.5° 단위 프로그램 복귀가 불가능하고, 설치 목표 속도·물리 회전 방향도 미검증이다. 따라서 프로그램 복귀는 준비 미완료. 어느 복귀도 실행하지 않았고 최소 방향 시험·C waypoint `NOT_RUN`; 실제 송신 전 별도 승인 필요.

## 2026-10-08 승인된 follower 읽기 전용 연결 — 완료, Elbow URDF 범위 밖에서 중단

- `READ_ONLY_CONNECTED / NO_MOTION_COMMAND`: 사용자 승인 후 Jetson SSH 셸에서 LeLab 텔레옵·녹화·추론 inactive, follower `/dev/ttyACM0` canonical ID `5AE6058306`, root 권한 `fuser` 무점유를 확인했다. 설치 LeRobot의 `SOFollower` 객체에서 `robot.connect()`/configure를 호출하지 않고 `bus.connect()`만 사용했다. 연결 중 `TIOCEXCL`과 `fuser`에서 점유 PID가 실행 프로세스 하나뿐이었고, calibration 파일/모터 레지스터 일치 `True`였다. raw `Present_Position` 1회와 설치 `_normalize`로 6축 값을 산출했다. 쓰기·토크·`send_action` 관련 함수는 호출 차단 guard로 감쌌으며 시도 수 0; `bus.disconnect(disable_torque=False)` 뒤 포트 무점유를 확인했다.
- `STOPPED ON MODEL LIMIT`: 현재 Elbow ID3 raw 3082 = +96.571429°로 설치 URDF 상한 +1.5708 rad(약 +90.000210°)보다 약 6.571° 높다. 다른 arm 관절은 URDF 범위 안이고 gripper 0–100 값은 Jaw rad와 직접 비교하지 않았다. 이 측정만으로 연결 중 실제 팔 이동 0을 독립 입증할 수 없으므로 현장 확인은 미수집이다. Elbow 자세 불일치 발견 즉시 추가 연결/최소 방향 시험/목표 송신을 중단했다. [세부](sessions/2026-10-08-c-red-urdf-path-decision.md). 경로·URDF·calibration 변경 `NOT_RUN`, 방향 시험 `NOT_RUN`, 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.

## 2026-10-08 승인된 follower 읽기 전용 연결 — 앞선 SSH 인증에서 중단(후속 해결)

- `BLOCKED BEFORE BUS OPEN`: 사용자 승인 범위는 현재 raw/degree 피드백 읽기와 포트 해제까지였다. Mac→Jetson SSH는 제한 환경 밖 재시도에서 호스트에 도달했으나 `Permission denied (publickey,password)`로 인증 실패했다. 이미 인증된 Jetson 터미널도 열려 있지 않았다. 따라서 LeLab 제어 상태·포트 점유·현재 관절값은 이번 시도에서 확인하지 못했고 follower 포트 연결·raw 읽기·정상 해제 확인은 `NOT_RUN`이다. `send_action`/목표·토크·캘리브레이션 쓰기·모터 동작 `NOT_RUN`.
- `NEXT`: 사용자가 인증된 Jetson 셸을 열어 주거나 읽기 전용 출력만 전달하면 동일 범위의 사전점검부터 재개한다. 비밀번호·개인키는 받지 않는다. 관절 방향 시험과 waypoint 동작은 이 승인에 포함되지 않는다.

## 2026-10-08 C→빨강 실행 연결부·희소 경로 후보 — 실기 연결/구동 없음

- `IMPLEMENTED (repo only)`: LeRobot follower `send_action`·새 `get_observation`/raw 위치 읽기의 실제 함수 형태를 단계 executor에 잇는 [adapter](../scripts/so101_follower_transport.py)를 추가했다. LeLab 8000 텔레옵·녹화·추론 모두 idle, canonical follower ID `5AE6058306`/ACM0, 포트 무점유, 프로그램 락을 요구하는 [독점 preflight](../scripts/so101_exclusive_bus.py)도 추가했다. 8000 카메라를 유지하고 수동 worker/포트가 완전히 해제된 뒤에만 연결하도록 설계했으며 `TIOCEXCL` 후 매 전송 전에 상태를 재검사한다. 설치 URDF SHA가 바뀌면 연결 전 차단하고, Elbow 90°/Wrist_Pitch 95° 초과 및 다른 모델 관절 범위 초과는 clipping 없이 송신 전 거부한다. 시작 자세 재검증 실패와 단계 간 새 피드백 자세 불일치도 다음 송신을 차단한다. 중단 요청은 adapter에 영구 송신 차단 latch를 건다. 명령 종료·팔 정지·물체 지지 확인 전에는 정상 연결 해제를 허용하지 않는다. 실제 Jetson 연결/배포/구동 `NOT_RUN`.
- `LIMITS_ONLY_PASS`: 새 [C→ID4 희소 waypoint 후보](../configs/c_red_waypoints_candidate_20261008.json) 9개와 인접 관절 선형 보간 표본은 현 URDF 제한 안이다(전체 최소 여유 23°, arm 최소 30°). 기존 방송 궤적을 재생하지 않고, 시작·끝은 초과했던 수동 자세 대신 새 내부 자세다. 접근·집기·이동·놓기·**별도 개방 승인**·상방 퇴피로 구분했다. 이것은 FK/한계 검사만 통과한 **비실행 후보**로 TCP·실제 영점/방향·병/손가락/바구니·환경/자체 충돌과 속도 여유는 `NOT_VERIFIED`, `motion_authorized=false`다. [상세](sessions/2026-10-08-c-red-urdf-path-decision.md).
- `NEXT`: 승인 전에는 실제 연결 없이, 첫 현장 최소 관절 방향/영점 시험의 현재 자세·안전 여유·예상 raw/degree 명령을 구체적으로 제시한다. 이후 후보 각 구간의 물체/충돌·시작 일치 검증, 단독 버스 preflight의 Jetson 실측, 단계별 수치 조건/현장 중단 절차 확정 후 사용자에게 **범위별 별도 승인** 요청. 목표를 전혀 송신하지 않은 읽기 전용 연결은 현장 안정 확인 후 토크 해제 없이 닫는 경로도 준비했다. fake/파서·상태기 관련 테스트 **38개 통과**, waypoint 9/9 `LIMITS_ONLY_PASS`; 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.

## 2026-10-08 C→빨강 현 URDF 경로 판단 — 경로 변경 우선, 실기 없음

- `RESOLUTION CONFIRMED`: 사용자가 현재 Jetson `MODEL_RESOLUTION['sts3215']=4096`을 확인했다. 설치 정규화의 분모 4095와 Elbow calibration 상한 약 +97.011°, Wrist_Pitch 약 +100.615°가 현재 값으로 확정됐다. URDF 상한은 각각 +90°/+95°. 이 차이가 관측값의 **오프라인 감사 차단**을 설명하나 URDF 오류·실제 안전성·드라이버 거부는 증명하지 않는다.
- `PATH REVIEW / CORRECTED`: 기존 C 접근 참고 기록 1,198개에서 Elbow 초과는 0–44.346초 및 57.452–61.861초, Wrist_Pitch 초과는 54.770–55.703초다. 사용자 정정에 따라 이 기록의 후반을 실제 놓기/퇴피로 해석하지 않으며 **완결된 C→빨강 시연과 URDF 내 연속 안전 경로 모두 미확보**다. [상세](sessions/2026-10-08-c-red-urdf-path-decision.md).
- `SOLUTION / NEXT`: URDF/충돌 검사 변경 없이 여유 있는 내부 시작→C 접근과 놓기 후 열린 그리퍼 퇴피→내부 종료를 우선 새로 구성·검증한다. 중앙 구간도 기존 follower 방송은 후보로만 쓰고 독립 목표·그리퍼/물체·충돌 여유를 확인한다. live adapter·단일 버스 소유권·별도 팔 정지 확인 및 단계별 수치 조건을 완료한 다음, 시험 범위/중단 방법을 설명하고 사용자 승인받아 C→빨강 사람 단계별 **프로그램 제어** 시험. 실제 연결·구동 `NOT_RUN`, 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.

## 2026-10-08 설치 모델 수치 불일치 확인 — 실기 미실행

- `CONFIRMED (offline gate)`: 새 Jetson 출력의 `motors_bus.py` 정규화 식과 설치 URDF 두 사본 SHA를 확인했다. `frontend/dist`·`frontend/public` URDF는 같은 SHA `443d38d7...f67236`; 기본 웹 서빙 경로는 설치 서버 소스상 `dist`이며 수동 `Goal_Position` 제어에는 URDF가 없다. Elbow URDF 상한 1.5708 rad(90°)과 follower calibration 약 +97.011° 상한(기존 sts3215 4096-step 근거) 사이 수치 불일치가 기존 관찰 +96.571°의 오프라인 감사 차단 원인이다. 실제 드라이버 거부·물리 안전 범위 확정은 아니다.
- `UNKNOWN / NO LIMIT CHANGE`: 현재 해상도는 후속 사용자 출력으로 4096 확인. 물리 영점·방향/충돌 여유는 정적 파일로 확정 불가. URDF 범위 확대·초과 표본 삭제·검사 해제 없음. 실행부의 `command_stop_state=COMPLETED`는 송신 종료만 뜻하고 팔 정지는 계속 `NOT_VERIFIED`; LeLab 수동 worker와 향후 프로그램 제어의 단일 버스 소유권을 별도로 확인해야 한다. [상세](sessions/2026-10-08-installed-urdf-normalization-reconciliation.md).
- `NEXT`: 위 최신 경로 변경/실기 준비 항목을 따른다. 장비 연결·구동 `NOT_RUN`, 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.

## 2026-10-08 C→빨강 단계별 프로그램 제어 게이트 — 모터 비접속

- `JETSON PARTIAL MATCH`: 사용자 Jetson 출력에서 LeLab 0.1.0/LeRobot 0.6.0, follower calibration SHA `2f74c130...e29c2e`, LeLab `teleoperate.py` 및 LeRobot `motors_bus.py`의 이전 조사 SHA 일치를 확인했다. `send_action→Goal_Position`과 ID 1–6 매핑은 현재 출력에서도 보였다. 붙여넣기 출력이 뒤섞여 **현재 URDF 파일/제한과 normalize 식 본문은 미수집**; 정합 최종 판정 `NOT_VERIFIED`. 누락분만 수집하는 Python 구버전 호환 [읽기 전용 명령](JETSON_STATIC_MODEL_COLLECTION.md)을 준비했다.
- `IMPLEMENTED / OFFLINE 27 TESTS PASS`: [단계별 실행 게이트](../scripts/staged_cycle_execution.py)를 추가했다. 승인된 단계의 목표별 송신·fresh follower 피드백/관절별 오차/안정 시간·시간 제한 도달·독립 작업 확인·중단 요청/실제 worker 및 전송 종료를 분리한다. 미도달/미확인/중단 후 다음 목표·단계 진행을 막는다. 가짜 전송기 테스트만 통과했으며 LeRobot live adapter, 실제 bus 소유권·stop 검증, 수치 경로/안전 여유는 없다. 토크 해제 명령 없음. 장비 배포·모터 구동 `NOT_RUN`.
- `NEXT`: 누락된 설치 URDF/정규화 출력 대조 → C→ID4 완결 경로·시작/배치/충돌·중단 조건 검증 및 단일 소유 live adapter 준비 → 별도 현장 안전 확인/승인 하에 사람 단계별 확인 **프로그램 제어** 시험. 기존 수동 성공·모의 성공과 구별. [상세](sessions/2026-10-08-staged-program-cycle-gate.md). 이슈 API `NOT_RUN`, `NOT_COMMITTED`, `NOT_PUSHED`.

## 2026-10-08 첫 C→빨강 단계별 실기 준비 — 구동 없음

- `SOURCE PATH REVIEW (dated matched source)`: Mac 설치 LeLab `teleoperate.py` SHA는 이전 Jetson 점검 SHA와 같아 그 시점 수동 경로를 직접 추적했다. leader `Present_Position` 정규화(arm 도, gripper 0–100)→`get_action`→follower `send_action`→`Goal_Position` sync write이며 follower 방송 URDF rad는 별도 관측 경로다. sync write 응답은 도달 확인이 아니고 기본 `max_relative_target=None`. stop은 active 플래그를 먼저 내리고 worker 최대 5초만 기다린 뒤 살아 있어도 success를 반환할 수 있어 버스 해제/팔 정지는 별도 확인해야 한다. 현재 Jetson 설치본 전체와 물리 영점/부호는 `NOT_VERIFIED`. [상세](sessions/2026-10-08-first-cycle-control-path-prep.md).
- `SIMULATOR CORRECTED / 27 TESTS PASS`: 같은 route ID가 점유 0·1에서 각각 테두리/기존 물체 여유와 수용 가능성 근거가 있으면 재사용 가능하다. 둘째 상태 근거가 없으면 차단. 실제 검증 카탈로그는 비어 있고 모터 adapter 미구현, 장비 배포·구동 `NOT_RUN`.
- `NEXT`: 사용자가 [Jetson 파일 전용 정적 수집 명령](JETSON_STATIC_MODEL_COLLECTION.md) 출력 제공 → 현 설치 URDF/매핑/calibration 재대조 → 수치 시작/경로/배치·중단 조건을 확정한 C→ID4 단계별 사용자 확인 시험을 **별도 승인**받아 시행. 모의/수동/완전 자동 결과는 분리 기록. 이슈 API `NOT_RUN`, 로컬 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.

## 2026-10-08 고정 슬롯 다중 목적지 순차 명령 — 저장소 모의 실행

- `USER SCOPE`: 픽업 A/B/C와 빨강 ID4·초록 ID5·파랑 ID6 고정, 명령별 목적지 변경, 동일 바구니 복수 약통 순차 투입. 마감 2026-10-17. C→빨강은 첫 검증 사이클이지 최종 목적지 고정이 아니다.
- `IMPLEMENTED (repo only)`: 기존 명령 파서가 `A, B를 빨강에 넣고 C는 파랑에 넣어라.`를 A→ID4, B→ID4, C→ID6 순서로 해석한다. 새 모터 비접속 상태기는 바구니 점유 0→1의 여유·수용 가능성을 각각 요구하되 두 점유 상태가 모두 검증되면 같은 경로 재사용을 허용한다. 없는·중복·상충 대상/목적지, 미검증 경로, 실패·시간 초과·중단, 집기/놓기/퇴피 근거 누락을 차단한다. 빈 실제 경로 목록으로 예시는 세 작업 모두 `BLOCKED_UNVERIFIED_ROUTE`; 테스트용 가짜 경로로만 상태 전이를 검증했다. 실물 성공 추정·다음 작업 자동 진행 없음. [상세](sessions/2026-10-08-fixed-command-sequence-simulation.md).
- `MODEL SOURCE NEXT`: Jetson SSH 인증 거부로 현 설치 정합 `NOT_VERIFIED`. [파일 전용 읽기 명령](JETSON_STATIC_MODEL_COLLECTION.md)으로 경로/SHA·URDF 축/제한·관절 매핑·calibration 영점/방향 필드를 한 번에 수집 요청. 실제 물리 방향은 정적 파일만으로 최종 확정 불가. 첫 C→ID4 자동 접근·집기·이동·놓기·퇴피 경로/시작 자세/배치 오차/충돌·완료 확인은 미검증이며 자동 실행 `NOT_RUN`; 장비 배포·이슈 API `NOT_RUN`, 로컬 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.

## 2026-10-08 URDF 불일치 구간 진단 — 시작 자세만의 문제는 아님

- `IMPLEMENTED (repo only) / 24 TESTS PASS`: 오프라인 감사기가 기존 차단과 원본 전체 표본을 유지한 채 첫 자세 이탈 전/후 URDF 초과를 분리한다. 저장된 C 상공 2,298개는 Elbow 초과 777개가 첫 이탈 전, 15개가 이탈 후 약 0.726초에 있었다. 최신 빈 경로는 399+4개였다. 그러나 실제 C 투입 경로는 Elbow 838+107개(끝 표본도 초과), Wrist_Pitch 이탈 후 19개여서 ‘시작 부분만 제외하면 전체 경로 적합’ 가설은 기각됐다.
- `NUMERIC CONVERSION CONSISTENT / PHYSICAL MAP NOT_VERIFIED`: 세 원본의 팔 5축 rad 방송을 설치 `DEGREES` 식으로 역산한 raw 정수 격자 잔차는 모두 0.0 step. 단순 도↔rad 오류의 증거는 없지만 영점/회전 방향·URDF axis·실제 명령/응답은 미확인. 수동 경로의 제어기 거부가 아니라 오프라인 감사 차단이다. 현재 Jetson 설치 재확인은 SSH 인증 문제로 `NOT_VERIFIED`; 한계 변경·샘플 삭제·자동 재생 `NOT_RUN`.
- `FIRST-DEMO RECOMMENDATION`: 고정 배치 C→빨강 ID4 한 종류에는 World→Base/TCP/IK가 필수가 아닌 A(검증된 전체 관절 경로 선택)가 B(영상 좌표+IK)보다 작은 작업이다. 하지만 기존 상태 방송은 제어 명령·검증된 전체 경로가 아니며 시작·접근·집기·이동·놓기·퇴피와 충돌·배치 재현성 검증이 남는다. 다음은 현재 설치 URDF/매핑/영점·방향 자료 확보. [상세](sessions/2026-10-08-urdf-origin-phase-diagnostic.md). 장비 배포·실기 `NOT_RUN`, 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 관절 제한 출처·모델 정합 조사

- `PASS (offline diagnosis) / MODEL CHANGE NOT_RUN`: 최신 빈 C→ID4 수동 경로의 follower 방송 `Elbow` 최대 +1.633321 rad(+93.582°)가 설치 URDF 스냅샷 상한 +1.5708 rad(+90°)보다 0.062521 rad 높았고 403/2,319개가 초과했다. `URDF_LIMIT_MISMATCH`는 로컬 감사기 문자열·exit 2이지 실제 드라이버 거부 오류가 아니다. 앞선 C 투입에는 Elbow +96.571°와 Wrist_Pitch +100.264° 관측치도 있었다. 명령 목표 자체는 기록되지 않았다.
- `SOURCE DISTINCTION`: 이전 설치 소스에서 확인한 LeLab 수동 `get_action→send_action→Goal_Position`에는 URDF/MoveIt·충돌·IK 검사가 없다. URDF/Xacro/MoveIt 전체 설치와 모든 관절 영점/부호 매핑은 현재 Jetson SSH 인증 거부로 재검증하지 못했다. 파일·장치 raw 제한과 방송값은 설치 도↔rad 식에 수치상 맞지만 물리 안전 범위 증거는 아니다. 제조사 조립체 사양과 검증 운용 범위가 없어 숫자 변경안은 보류하고 현행 한계·검사는 유지한다.
- `NEXT`: 설치 모델·매핑과 제조사 근거를 읽기 전용 확보한 후 개별 관절 수정안의 전후 값/영향을 제시하고, 사본의 충돌·IK 포함 하드웨어 없는 시뮬레이션을 먼저 수행한다. 실제 구동은 새 현장 확인·구체적 승인 전 `NOT_RUN`. 관련 테스트 첫 ImportError 뒤 discover 15/15 통과. [상세](sessions/2026-10-08-joint-limit-origin-review.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 빈 C→빨강 ID4 수동 공중 경로 — 부분 관찰

- `PASS (user-operated empty manual route) / PARTIAL TRACE`: 사용자가 C를 작업 범위 밖에 둔 채 출발 상공→높은 중간 공중→빨강 ID4 상공→퇴피를 비접촉으로 직접 조작했고 접촉·이상 없음 및 종료를 보고했다. 첫 UI 시작 보고 때 서버는 inactive여서 실제 active 확인 뒤 관찰을 시작했다. `.venv` 관찰기 실행은 `websocket` 누락으로 시작 전 실패, 확인된 시스템 Python으로 재실행. 관절 2,319개·3시야 492/491/493장 SHA/시각 감사 통과. 120초 제한으로 빨강 상공 도달 직후 기록이 끝나 퇴피는 기록되지 않았다.
- `TRANSFER_HOVER CANDIDATE / REPLAY BLOCKED`: 중간 공중 정지 한 건 3시야·관절 저장, 마커 배치 안정. 사선상 손끝과 빨강 뒤 테두리가 겹쳐 보여 사용자 현장 실제 공기 간격 확인을 받았으나 최소 간격은 측정되지 않았다. 두 과거 빈 정지값과 이번 경로의 최근접 관절 차이는 C 출발 최대 13.451°, 빨강 상공 최대 5.011°로 반복 자세 일치가 아니다. URDF Elbow 초과 403개는 초기 0–20.773초에 한정(최대 약 3.582°), 캘리브레이션 파일 범위는 모두 포함(최소 여유 약 3.429°). 자동 이동·집기·재생 `NOT_RUN/BLOCKED`.
- `STOP VERIFIED`: 사용자 종료 뒤 서버 `teleoperation_active=false`; 이번에는 별도 종료 API를 호출하지 않았다. [상세](sessions/2026-10-08-empty-c-id4-manual-path-observation.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 빈 장면 C 출발·빨강 ID4 상공 후보 두 자세

- `PASS (manual noncontact observations) / REPLAY BLOCKED`: 사용자가 C를 작업 범위 밖으로 치우고 빈 그리퍼로 빨강 ID4 상공, 이어 빈 C 고정 출발 자리 상공을 각각 별도 현장 승인·기존 LeLab 텔레옵으로 비접촉 정지했다. Mac 8030에 `BASKET4_HOVER`·새 `SOURCE_C_HOVER` 각 1건을 Git 제외 로컬 저장. 3시야 SHA·15개 안정 관절값·수신시각 간격 확인. 앞선 실제 C 집기 포함 `SOURCE_C_HOVER`는 계속 채택 거부다.
- `SCENE MATCH / PATH NOT VERIFIED`: 두 정지 사진 간 마커 최대 이동 작업대 0.228 px·바구니 0.089 px. 저장된 파일 범위 안의 끝점이지만 Elbow 차이는 약 69.890°다. 바구니 상공 화면상 중앙·실제 높이·연속 경로·충돌 여유는 독립 검증되지 않았으므로 자동 재생/집기 `NOT_RUN/BLOCKED`다.
- `STOP VERIFIED`: 두 번 모두 사용자 화면 종료 표시 후 서버에는 active가 남아, 안전 퇴피·팔 정지 현장 보고 뒤 공식 종료 API 각 1회로 `teleoperation_active=false`를 확인했다. LeLab 녹화·추론도 inactive. [상세](sessions/2026-10-08-empty-scene-c-id4-waypoints.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 C 비접촉 teach 시도 — 라벨 채택 거부

- `LIVE OBSERVER UPDATED`: 사용자의 C 배치 뒤 Mac 8030 관찰기만 새 라벨 코드로 재시작했다. 첫 detached 시작은 실패했고 foreground 세션에서 복구했다. 일시적 사선·손목 503 뒤 세 카메라 및 8031 판정 입력 정상, 로봇 제어 없음. Jetson LeLab 서비스·모터·USB는 변경하지 않았다.
- `REJECTED_FOR_USE`: 사용자 현장 승인과 비접촉 보고에 따라 `SOURCE_C_HOVER` 1건을 Git 제외 로컬에 저장했으나, 이어진 별도 비접촉 이동 중 영상에 C가 그리퍼에 들려 출발 위치 밖으로 이동했고 사용자도 잡거나 이동했다고 확인했다. 따라서 첫 저장본의 비접촉 의미·출발 위치 불변은 독립 검증되지 않아 경로에 채택하지 않는다. `BASKET4_HOVER` 저장 `NOT_RUN`; 자동 재생 금지. 첫 종료 보고 뒤 서버는 여전히 active였고 재종료 후 inactive를 확인했다. [상세](sessions/2026-10-08-c-noncontact-teach-attempt.md). 다음은 C를 치운 빈 장면의 ID4 상공 비접촉 시험이다. 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 현 고정 배치용 경유 자세 캡처 준비

- `OLD WAYPOINTS REJECTED FOR CURRENT LAYOUT`: 보유 35개(PARK 7·SOURCE1_HOVER 2·BASKET4_HOVER 26)를 현 배치 기준과 오프라인 대조하니 25개는 필수 마커 부족, 10개는 마커 배치 변경으로 일치 확인 0개다. 옛 경로 재생 금지 유지.
- `PREPARED (at that stage, repo only)`: 접촉점 기반 TCP가 미검증이므로 고정 슬롯의 비접촉 teach 대안을 준비했다. 읽기 전용 캡처기에 A/B/C 출발·ID5/6 바구니 상공 라벨을 추가하고 기존 라벨·제어 차단을 보존했다. 회귀 시험 14/14 통과; 첫 제한 환경 시험의 로컬 포트 권한 오류 4건은 허용된 동일 시험에서 해소했다. 이 준비 당시 Mac 8030/8031은 재시작하지 않았으며, 이후 라이브 적용·시험 결과는 위 최신 항목에 기록했다. [상세](sessions/2026-10-08-fixed-slot-teach-prep.md). 자동 재생 `NOT_RUN`, 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 URDF 제한과 follower 범위 재대조

- `PASS (offline reconciliation) / AUTO MOTION BLOCKED`: 현 C 수동 기록의 Elbow 최대 +96.571°는 URDF +90°를 6.571° 넘지만 캘리브레이션 파일 끝까지 0.440°만 남고, Wrist_Pitch 최대 +100.264°는 URDF +95°를 5.264° 넘지만 파일 끝까지 0.352°만 남는다. Wrist_Roll은 반대로 URDF ±160°가 파일 ±156.352°보다 넓다. 이전 Elbow/Wrist_Pitch 장치 레지스터는 파일과 일치했다. 사용자의 수동 무간섭 보고는 유지하되 URDF 전체 무시·캘리브레이션 끝값을 자동 목표로 복사하지 않는다. 오프라인 설계는 계속 가능하다. [대조 기록](sessions/2026-10-08-urdf-limit-reconciliation.md). 모터·설정 변경 `NOT_RUN`, 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.
- `INSTALLED PATH VERIFIED (read-only)`: Jetson 설치 LeLab 0.1.0/LeRobot 0.6.0의 수동 텔레옵 `get_action()`→`send_action()` 경로에 URDF 한계 검사가 없고, 기본 `max_relative_target=None`이다. 설치 `MotorsBus._unnormalize()`의 `DEGREES` 분기는 캘리브레이션 min/max clamp 없이 raw 목표를 계산한다. 모터 펌웨어가 범위 밖 목표를 어떻게 처리하는지는 미검증. 따라서 URDF만 무시·수정해도 자동 명령 제한 문제가 해결되지 않는다. [소스 근거](sessions/2026-10-08-urdf-limit-reconciliation.md).

## 2026-10-08 C 투입 후 YOLO 완료 판정 실패 — 두 시연 교차 확인

- `PASS (offline 3-view phase review) / REPLAY BLOCKED`: 현 C 시연의 정면·사선·손목 대표 사진에서 접근→들어 올림→빨강 ID4 진입→그리퍼 벌림→퇴피와 C 잔류를 확인했다. 병은 비스듬히 놓였으며 바닥 접촉 시점·테두리 최소 간격은 측정할 수 없다. 영상과 관절은 Mac 수신시각 근접 표본일 뿐 동기 waypoint가 아니다. 추가 8000 API 읽기 전용 재조회는 첫 셸 TCP 실패·브라우저 URL 차단 후 접근을 재시도해 `teleoperation_active=false` 확인. [단계별 검토](sessions/2026-10-08-c-transfer-phase-review.md). 새 동작 `NOT_RUN`, 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.
- `CAMERA STATUS PASS`: 8030 실제 `/api/status`의 정면/사선/손목 age는 20.2/16.1/23.6 ms, 오류 null, `robot_control=false`다. 첫 잘못된 `/status` 경로는 404였고 재조회로 바로잡았다. 관절 데이터는 텔레옵 종료 뒤 오래돼 현 자세 증거가 아니다.
- `LIVE FINAL CHECK`: 8000 health `ok`, 텔레옵·녹화·추론 active=false. 녹화 내부 `preparing`·`session_ended=false`는 정리 완료의 증거가 아니다. 제어 API·새 모터 동작 `NOT_RUN`.

- `PASS (offline) / FAIL (YOLO-only verification)`: 현 C 시연 정면 251장 중 227장에 약통 후보가 있었지만 마지막 C가 빨강 바구니 안에 보이는 사진은 검출 0개다. 이전 C 시연도 첫 20/20장 검출, 마지막 20/20장 검출 0개였다. 현재 모델의 검출 0개는 빈 바구니·투입 실패의 증거가 아니다.
- `MARKER COVERAGE`: 현 시연 ID0/1/3/4/5/6은 251/251, ID2는 249/251장으로 동작 중 2장에 네 기준점 homography가 불가했다. 시작/끝 픽셀 변화는 사후 진단일 뿐 완료 판정기로 채택하지 않는다. [상세](sessions/2026-10-08-c-transfer-vision-qa.md). 로봇 동작·자동 재생 `NOT_RUN`, 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.
- `PREPARED (offline cap candidate only)`: ID4 상대 흰 뚜껑 후보 진단을 추가했다. C 종료 2건은 각 20/20, 빨강이 빈 A/B 종료 2건은 각 0/20이지만, 사후 선택한 네 장면이라 독립 성능은 미검증이다. `completion_verified=false`·`motion_authorized=false` 고정, 관련 감사 시험 39개 통과. 첫 `.venv` 단위 시험 지정 경로 오류 뒤 discover 재실행 통과.
- `FAIL (candidate as completion signal)`: 네 기존 시연의 모든 정면 프레임을 재검사하니 A/B 빨강 빈 장면은 0/367·0/594, 이전/현 C는 157/578·45/251 후보였다. **현 C index 206은 그리퍼가 아직 C를 잡은 상태인데도 후보가 참**이다. 이 신호를 투입 완료·그리퍼 퇴피 판정으로 쓰지 않는다. [전체 구간 결과](sessions/2026-10-08-c-transfer-vision-qa.md).

## 2026-10-08 현 배치 C→빨강 수동 1회 — 3시야 기록·자동 재생 차단

- `PASS (user-operated manual)`: 이전 성공 장면과 현 배치를 대조하니 빨강 ID4 마커가 약 9.467px 이동해 옛 경로 재사용이 부적절했다. 사용자가 새 배치에서 안전·수동 1회를 승인하고 직접 C를 빨강 ID4에 넣어 퇴피·종료했다. 시작/끝 정면 영상과 현장 보고가 부합하며 종료 API는 텔레옵 inactive다.
- `PASS (passive trace integrity) / REPLAY BLOCKED`: 관절 1,198개·정면/사선/손목 각 251장 해시·시각 순서 통과. 실제 활동 잠정 구간 18.551초다. URDF Elbow/Wrist_Pitch 초과 945/19개, 캘리브레이션 파일 최소 여유 각 0.440°/0.352°이고 동기 연속 영상·입구 여유는 미검증이다. 자동 재생·집기 `NOT_RUN`; [상세](sessions/2026-10-08-c-red-current-layout-manual.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 C 고정 슬롯 배치 재촬영

- `PASS (camera-only)`: 사용자 C 배치 보고 뒤 8031에서 천장 프레임 148058을 C로 클릭·로컬 저장했다. 사진에는 C 후보 한 개와 ID0–6이 보였고, C→빨강 ID4는 `DRY_RUN_ROUTE_ONLY`였다. 저장 자료는 Git 제외이며 `training_ready=false`다.
- `PASS (marker diagnostic) / BODY CANDIDATE UNSTABLE`: 고정 바구니 기준 대비 마커 최대 이동은 작업대 0.088px·바구니 0.073px, 몸체 색 상자 최대 크기 차이는 9px다. `pickup_roi_match=false`이고 입구·로봇 좌표·경로는 미검증이다. 자동 모션 `NOT_RUN`. 첫 시스템 Python에는 `cv2`가 없어 감사 실패 후 기존 `.venv`에서 성공했다. [상세](sessions/2026-10-08-c-fixed-slot-capture.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.
- `PASS (dry-run only)`: 현재 C 한 병에 `C를 빨강` 명령 미리보기를 실행해 C 슬롯→ID4 판정을 확인했다. 픽업 ROI는 불일치하고 `grasp_authorized=false`다. 명령 저장·모터 동작 `NOT_RUN`.

## 2026-10-08 고정 바구니 20프레임 감사 — 마커 안정·색 상자 실패

- `PASS (read-only marker sequence)`: 조명 조정 후 기존 Mac 8030 캐시에서 0.5초 간격 정면 20장을 Git 제외 `.local/basket-opening-captures/20261008-stability-V43cES/`에 저장했다. 20개 모두 새 프레임, ID0–6 검출, 기준 대비 작업대/바구니 마커 최대 이동 0.985/0.220 px, 밝기 중앙값 232–233이다.
- `FIRST FAILURE / CORRECTED CLASSIFICATION`: 최초 비교는 20/20 `VISUAL_LAYOUT_CHANGED`였으나 실제 불일치는 몸체 HSV 상자 최대 중심 8.139 px·크기 18 px 변화다. 마커 일치 상태에서 이를 바구니 이동으로 단정하지 않도록 `BODY_CANDIDATE_UNSTABLE`로 분리했고 재감사 20/20이 이 상태다. 색 상자를 입구 중심·로봇 목표로 사용하지 않는다. 관련 감사 테스트 36개 통과.
- `BLOCKED`: 입구 안쪽 네 모서리·높이, TCP/World→Base와 실제 여유는 `NOT_VERIFIED`; 자동 모션 `NOT_RUN`. [상세](sessions/2026-10-08-fixed-baskets-short-sequence.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.
- `MULTI-VIEW LIMIT`: 추가 사선 사진에서는 ID0–3 중 ID2만 검출됐고 손목 사진에는 바구니가 보이지 않는다. 현 사진들만으로 입구의 독립 3D 좌표를 계산하지 않는다.
- `PREPARED/NOT_RUN`: 별도 승인 수동 시험에서 손목 캐시도 남길 수 있게 관찰기 `--include-wrist` 옵션을 추가했다. 기존 정면·사선 기본값과 모션 차단은 유지, 실제 런타임의 관련 테스트 9개 통과(첫 가짜 시계 조건 오류 1건 수정). 세 캐시 fresh/읽기 전용 사전 점검 통과. 새 텔레옵·연속 기록은 아직 `NOT_RUN`이다.

## 2026-10-08 조명 복구 후 고정 배치 재확인

- `PASS (read-only, two frames)`: 사용자 조명 조정 후 기존 Mac 8030 캐시에서 정면 JPEG 두 장을 Git 제외 `.local/basket-opening-captures/20261008-light-check-IXdKBV/`에 저장했다. 밝기 중앙값 235/234(기준 233), 두 장 모두 ID0–6과 세 바구니 몸체 색 후보 검출. 기준 대비 ID0–3 최대 이동 0.210/0.221 px, ID4/5/6 최대 0.075/0.099 px로 두 장 모두 `VISUAL_LAYOUT_MATCH_DIAGNOSTIC`다.
- `LIVE READ-ONLY`: LeLab 8000 텔레옵 inactive, 8030 세 카메라 캐시 fresh/오류 null/`robot_control=false`, 8031 `robot_enabled=false`를 확인했다. 카메라·로봇 서비스/USB/모터/토크 변경과 자동 이동 `NOT_RUN`. 이 화면 일치는 바구니 입구·3D 좌표·경로 승인이 아니다. [상세](sessions/2026-10-08-fixed-baskets-ceiling-reference.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 사용자 고정 바구니 배치 — 새 천장 기준·조명 실패 기록

- `USER REPORTED`: 모든 바구니 자세는 현재 배치로 고정한다. 움직이는 바구니의 동적 pose 추적은 보류하고, 현 사진을 화면상 기준으로 삼되 배치가 달라지면 재검증한다.
- `SUPERSEDED`: 02:22 사진(`20261008T022151_4I2Q82`)은 ID4/6이 왼쪽에서 겹친 이전 배치다. 운영 기준으로 재사용하지 않는다.
- `PASS (read-only capture)`: 새 배치의 Git 제외 `.local/basket-opening-captures/20261008T022818_PV95dh/ceiling.jpg`(SHA `ed744692...a94324`)에서 ID0–6 검출, 왼쪽 ID4·가운데 ID5·오른쪽 ID6과 세 몸체 색 성분 상자 후보를 기록했다. 이는 입구 중심이나 로봇 목표가 아니다.
- `PARTIAL/INDETERMINATE`: 직후 두 사진의 밝기 중앙값이 233→53/52로 떨어져 색상 몸체 후보 3개가 모두 사라졌다. 첫 어두운 사진은 마커만 대체로 일치해 `MARKERS_MATCH_BODY_UNVERIFIED`; 두 번째는 ID3 누락으로 `INDETERMINATE`다. 이전 배치 대비 ID4/6 마커 이동 227/353 px도 확인했다. 짧은 입구 약 85 mm 대비 모델 B 그리퍼 X 폭 83.7 mm는 양옆 명목 0.65 mm, C 개방 폭 91.6 mm는 입구보다 6.6 mm 크다. 실제 손목 방향·높이별 간섭 여유는 `NOT_VERIFIED`.
- `MOTION BLOCKED`: 모든 입구 내부·높이·마커 강성·충돌 여유·TCP/World→Base는 `NOT_VERIFIED`; 자동 모션 `NOT_RUN`. [고정 장면 기록](sessions/2026-10-08-fixed-baskets-ceiling-reference.md). 감사 코드·문서 로컬 커밋 완료, 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 바구니 몸체 후보 — 입구 중심 아님

- `PASS (offline candidate audit)`: 기존 SHA 검증된 정면 영상 6기록·2,711장에서 갈색 바구니 몸체의 색 성분 상자 후보를 2,641장(97.4%)에서 찾았다. B 투입의 가림 구간 70장은 후보가 없고 부분 가림 때 상자가 좁아지거나 이동한다. 현재 회전 장면 한 장의 후보는 `(320,259,106,76)` px로 이전 세로 배치의 중간 크기 약 72×104 px와 방향이 달랐다.
- `NOT_VERIFIED`: 고정 ROI/HSV가 같은 배치·조명에서 찾은 **몸체 외접 상자**일 뿐 실제 입구 네 모서리·중심·높이·yaw·간섭 여유가 아니다. 바구니 pose 승인·로봇 제어 false, 자동 모션 `NOT_RUN`. 상세: [바구니 몸체 후보](sessions/2026-10-08-basket-body-bbox-offline.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 수동 관절 방송 변화량 — 무결성 통과·자동 재생 차단

- `PASS (offline broadcast profile)`: 기존 기록 9건·관절 방송 16,568개에서 인접 source/수신 시각은 모두 증가했고 source 간격 200ms 초과는 0건이었다. B→초록/C→빨강의 Elbow 최대 인접 방송 변화는 6.154°/7.736°(유한차분 119.311°/s·143.428°/s)다. 이는 실제 모터 속도·표본 사이 경로 측정이 아니다. 빈 작업대 소폭 이동 기록의 Elbow는 전 표본이 동일 자세라 이동 증거가 아니다.
- `REPLAY BLOCKED`: 설치 URDF 불일치, 파일 경계 0.352° 근접, 동기 연속 영상·실제 간섭 여유·표준 시작 자세 미검증이 남는다. 오프라인 검사기/관련 테스트 24개 통과, 로봇 이동·서비스/USB/토크 변경 `NOT_RUN`. 상세: [수동 방송 시간·변화량](sessions/2026-10-08-teleop-broadcast-motion-profile.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 회전 바구니 ID5 마커 의미 — 8031 읽기 전용 표시 반영

- `PASS (camera-only before/after)`: 바구니 회전 전후 ID5 마커 중심의 테이블 평면 투영값은 `[192.966,133.179]`→`[111.030,230.299]` mm, 차이 벡터 길이 약 127.1 mm다. 바구니 입구 중심 이동이 아니며 마커 높이도 미보정이다. ID5만으로 목적지 중심·자세를 정의하지 않는다.
- `IMPLEMENTED/LIVE (read-only 8031)`: 마커 좌표는 바구니 중심이 아님을 상태·명령 미리보기에 명시하고 바구니 중심/자세 승인 false를 추가했다. Mac 8031만 기존 카메라·저장 옵션으로 재시작했고 health 신선·ID0–3/5·`robot_enabled=false`를 확인했다. 최초 백그라운드 재시작 실패 후 전경 세션으로 복구했다. 새 합성/관련 시험 20개 통과. 로봇 좌표·경로 `NOT_VERIFIED`, 자동 모션 `NOT_RUN`. 상세: [마커 의미 점검](sessions/2026-10-08-basket-marker-semantics.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 캘리브레이션 파일·수동 궤적 대조 — 자동 재생 차단 유지

- `PASS (read-only installed-source audit)`: Jetson follower 캘리브레이션 파일 SHA를 확인하고 설치 LeRobot `DEGREES` 정규화식으로 다섯 arm 관절의 파일 경계를 계산했다. canonical follower/leader USB 메타데이터와 LeLab active·텔레옵 inactive를 읽었다. 시리얼 버스·모터·토크·서비스 설정은 건드리지 않았다.
- `PASS (offline trace audit) / MOTION BLOCKED`: 보유 연속 기록 9건·관절 방송 16,568개는 모두 캘리브레이션 **파일** 범위 안이었다. 그러나 9건 전부 설치 URDF와 불일치하며, 파일 경계까지 최솟값이 Elbow/Wrist_Pitch 각각 0.352°에 불과하다. 1° 이내 표본은 Elbow 3,547개·Wrist_Pitch 20개다. 1°는 진단 폭이지 안전 마진이 아니다. 카메라 완전 경로 증거는 9건 모두 false다. 다른 세 arm 모터 레지스터, 실제 하드스톱·동적 여유·연속 경로는 `NOT_VERIFIED`; 자동 이동·재생 `BLOCKED/NOT_RUN`. 파생 범위 스냅샷·재현용 오프라인 검사기를 추가했고 관련 시험 12개 통과. 상세: [캘리브레이션 궤적 대조](sessions/2026-10-08-calibration-trace-envelope-offline.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 초록 바구니 비접촉 정렬 — 방향 확인 완료·삽입 미검증

- `PASS (reoriented basket camera check)`: 사용자 재배치 후 정면 영상에서 초록 바구니 긴 축이 좌우이고 ID5가 검출된다. 이는 이전 손가락 벌림 좌우 방향과 화면상 일치한다. 8031은 `ROBOT DISABLED`, LeLab 메인 UI는 `Ready`였다. 당시 실제 텔레옵 서버 상태·3D 간섭 여유는 `NOT_VERIFIED`였고 이후 별도 수동 비접촉 1회를 승인받았다.
- `PASS (user-operated non-contact direction check)`: 사용자가 새 현장 안전 확인·비접촉 1회 승인을 하고 기존 LeLab 텔레옵으로 빈 그리퍼를 초록 바구니 상공에서 정지시켰다. 정면 영상에서 손가락 벌림 방향과 바구니 긴 축은 좌우로 일치한다. 손끝은 뒤쪽 테두리 근처에 투영돼 입구 중앙과 실제 공기 간격은 카메라만으로 `NOT_VERIFIED`. 사용자는 비접촉 퇴피·텔레옵 종료·간섭 없음이라고 보고했고 영상상 그리퍼가 바구니에서 떨어져 있다. 서버 종료 API는 접속 제한으로 재확인하지 못했다. 안쪽 진입·자동 이동·재생 `NOT_RUN`.
- `PASS (read-only visual preflight)`: 사용자 배치 보고 후 LeLab은 `Ready`, Mac 8031은 `ROBOT DISABLED`이며 기준 ID0–3·초록 바구니 ID5를 검출했다. 정면·사선 화면에 초록 바구니 1개가 보인다.
- `USER APPROVED (manual non-contact one-shot)`: 사용자가 물체를 이동 범위 밖으로 치우고 빈 그리퍼·사람 범위 밖·즉시 중단 준비를 확인했다. 새 영상 가장자리에는 물체와 가위가 남아 보여 영상만으로 범위 밖 여부를 확정하지 않는다. 사용자가 기존 LeLab 텔레옵을 직접 켜고 리더를 움직이지 않은 상태에서 이상 움직임을 확인하도록 요청했다. 실제 간섭 여유 `NOT_VERIFIED`, 자동 이동·재생 `BLOCKED/NOT_RUN`. 상세: [초록 바구니 사전 점검](sessions/2026-10-08-green-basket-noncontact-preflight.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.
- `INCOMPLETE (manual overhead alignment)`: 사용자는 바구니 상공 비접촉 정지를 보고했다. 정면 영상의 손가락 벌림 방향은 화면 좌우, 바구니 긴 축은 상하라 긴 축 정렬은 확인되지 않았다. 추가 하강 없이 먼저 테두리 위로 충분히 퇴피하도록 요청했고 결과 대기 중이다. 실제 여유 `NOT_VERIFIED`.
- `STOPPED (direction not verified)`: 사용자는 공중 퇴피와 손목 방향 변경을 보고했지만 갱신된 정면 영상에서 벌림 방향은 계속 좌우로 보인다. 바구니 안으로 진입하지 않았고 사용자는 비접촉 퇴피·텔레옵 직접 종료, 이상 없음을 보고했다. 종료 후 영상에는 그리퍼가 바구니에서 떨어져 있다. 서버 측 `/teleoperation-status` 재조회는 네트워크 차단으로 `NOT_VERIFIED`; 자동 이동·재생 `BLOCKED/NOT_RUN`.

## 2026-10-08 그리퍼 메쉬 외접 폭 — 모델 여유 부족, 실제 검증 미완료

- `PASS (read-only installed model audit)`: 설치 URDF SHA 일치 확인. 설치 STL은 실제 형상이 아닌 Git LFS 포인터였고, Jetson 기존 uv 캐시에서 포인터 SHA와 맞는 바이너리 STL을 찾았다. URDF visual/joint 변환을 적용한 모델 외접 폭은 B 입구 부근 Jaw 0.43259 rad에서 X 83.7·Y 52.0 mm, C 집은 상태 Jaw 0.21469에서 X 71.7·Y 52.0 mm, C 개방 후 Jaw 0.54582에서 X 91.6·Y 52.0 mm다.
- `NOT_VERIFIED (physical clearance)`: 사용자가 짧은 안쪽 입구를 약 85 mm로 보고했다. 모델 X축을 이 방향에 맞춘 가정에서 B의 양옆 여유는 각 약 0.7 mm, C 개방 후 모델 폭은 입구보다 6.6 mm 크다. 실제 손목 방향·장착물·바구니별 편차·양손가락 연동은 모델에 완전히 반영되지 않았다. 사용자의 수동 무간섭 보고를 부정하지 않지만 이를 자동 통과/개방 안전 증거로 쓰지 않는다. 로봇 이동·재생 `NOT_RUN`, 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`. 상세: [그리퍼 외접 폭 점검](sessions/2026-10-08-gripper-envelope-offline.md).
- `OFFLINE DESIGN CANDIDATE ONLY`: 모델 X 폭을 바구니 명목 긴 128 mm 방향으로 둔 가정에서는 B 자세의 계산상 여유가 긴 방향 각 약 22.2 mm·짧은 약 85 mm 방향 각 16.5 mm다. C 개방 자세도 각 약 18.2/16.5 mm다. 실제 긴 내부 폭·손목 방향과 양손가락·장착물은 미검증이며 **회전/이동 명령이 아니다**. 기존 B/C Jaw 개방 시각에 가까운 사선 프레임에는 손가락이 바구니 입구 부근에 보여, 테두리 위로 완전 퇴피한 후 열었다고 단정하지 않는다.

## 2026-10-08 약통·바구니 치수 — 바깥 치수와 명목 입구 계산

- `USER REPORTED`: A 높이 98·밑지름 38·뚜껑지름 48 mm, B 70/38/48 mm, C 70/30/35 mm다. 세 바구니 바깥 치수는 각각 세로 138·가로 98·높이 58 mm, 테두리 두께 5 mm다. 사용자의 `0.5센치` 답변을 근거로 원래 수치도 cm로 해석했다.
- `OFFLINE ONLY`: 네 변의 테두리가 균일하다면 명목 안쪽 입구는 128×88 mm이나, 사용자 실측 짧은 안쪽 폭은 **약 85 mm**다. 병만 중앙에 놓을 때 짧은 방향의 계산상 양옆 간격은 A/B 각 약 18.5 mm, C 각 약 25 mm다. 실제 긴 안쪽 폭·바구니별 편차·열린 그리퍼 외접 폭·기울기·연속 경로는 미확인이다. 바구니와 출발 면이 같은 높이라면 수평 이송 전에 병 바닥이 테두리 58 mm보다 위에 있어야 하지만 안전 여유는 미정이다. 자동 집기·이동은 `BLOCKED/NOT_RUN`. 상세: [치수 검토](sessions/2026-10-08-object-dimensions.md). 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.
- `PASS (saved-video review only)`: 기존 A/B/C 수동 사선 표본에서 A는 파랑 바구니 안에 기울어져 남고 B/C는 손가락이 병을 잡은 채 입구 부근에 있다. 이는 현장 수동 성공 보고와 부합하지만 프레임의 원근·가림으로 실제 그리퍼 외접 폭·테두리 최소 간격은 측정할 수 없다. 이 영상 검토를 자동 경로 승인으로 승격하지 않는다.

## 2026-10-08 8022 카메라 점유 정리 — 8000 세 영상 복구

- `PASS (approved service stop)`: 사용자 승인 후 8022의 정확한 `lelab-jetson-py310.service`가 텔레옵·녹화·추론 inactive임을 확인하고 그 서비스만 중지했다. 결과 inactive/dead·PID 0·8022 listener 없음. 8000 서비스·USB·모터·토크·캘리브레이션·설치 URDF는 변경하지 않았다. 8000 정면 8·사선 4·손목 6이 모두 HTTP 200으로 실제 MJPEG 바이트를 보냈고 `/health` ok, 텔레옵 inactive였다.
- `PASS (read-only observer restore)`: 중지된 8022를 바라보던 정확한 Mac 8030 관찰기만 종료 후 8000 세 카메라 입력으로 재시작했다. 반복 상태 조회에서 세 프레임 나이 수십 ms 이하·오류 null·`robot_control=false`; 8031 정면/사선 입력도 fresh, `robot_enabled=false`. 8011 촬영 서비스는 8022 입력을 사용하므로 그 기능은 현재 `NOT_VERIFIED`다. 8022는 여전히 `enabled`여서 재부팅 시 충돌이 재발할 수 있으며, 영구 비활성화는 수행하지 않았다.
- `CALIBRATION LIMIT POLICY`: 사용자가 요청한 캘리브레이션 최대값은 실제 제한 레지스터와 일치하는 Elbow 약 +97.011°·Wrist_Pitch 약 +100.615°의 **읽기 전용 장치 범위 대조**에 사용한다. 이전 수동 최고 자세는 각각 상한에서 약 0.35° 아래였으므로 이를 자동 목표값이나 여유 있는 안전 경로로 간주하지 않는다. 설치 URDF +90°/+95°를 수정하지 않았다. 자동 이동·집기 `BLOCKED/NOT_RUN`, 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`. 상세: [8022 카메라 점유 정리](sessions/2026-10-08-8022-camera-ownership-recovery.md).

## 2026-10-08 빈 작업대 소폭 이동 사전 점검 — 한 관절 검증 미완료

- `PASS (camera receiver recovery)`: 8000은 텔레옵 inactive에서 정면 `/camera-preview/8`만 신선했고 사선 4·손목 6은 HTTP 503이었다. Jetson root `lsof`에서 기존 8022 LeLab PID 518962가 `/dev/video4`·`/dev/video6`을 점유하고, 그 인스턴스의 두 프리뷰는 HTTP 200임을 확인했다. 8000·8022·USB·카메라 장치 설정을 바꾸지 않고 Mac 읽기 전용 8030 관찰기에 카메라별 대체 MJPEG URL 옵션과 짧은 정상 스트림 재연결을 추가했다. 정확한 기존 8030 프로세스만 종료·동일 포트로 재시작한 뒤 정면·사선·손목 수신을 확인했다. 다만 8022의 짧은 스트림 종료가 반복돼 사선/손목은 간헐적으로 0.75초 신선도 기준을 넘었다. 실시간 안전 영상으로 연속성을 보증하지 않는다.
- `INCOMPLETE (user-operated free-space micro-motion)`: 사용자는 빈 그리퍼·빈 작업대·사람 범위 밖·즉시 중단 준비를 확인하고 기존 8000 텔레옵을 직접 시작했다. 에이전트는 모터 API·토크·설정·URDF를 변경하지 않았다. 초기 관절 방송 Elbow 1.677818 rad, Rotation 0.071348 rad, Wrist_Pitch 0.863075 rad. 공중에서 팔꿈치만 상한에서 멀어지는 작은 수동 이동을 요청했으나 뒤이은 두 번째 관절 스냅샷은 Elbow 1.6855 rad(상한 쪽 +0.0077), Rotation −0.1082 rad(−0.1795), Wrist_Pitch 0.7618 rad(−0.1013)였다. 사용자는 작은 이동·정지와 접촉/이상 없음이라고 보고했다. 현장 보고와 관절 스냅샷은 양립할 수 있지만 **한 관절·한 변수 시험은 성립하지 않는다**. 즉시 추가 이동 중단을 요청했고 종료 후 8000 텔레옵·녹화·추론 inactive를 확인했다.
- `FIRST FAILURE / LIMIT`: 읽기 전용 60초 관찰기가 실제 이동 전에 시간 초과돼 관절 1,156개가 모두 동일 자세다. JPEG 정면 245·사선 170장과 SHA 무결성은 통과했지만 이 파일은 이동의 연속 궤적 증거가 아니다. 설치 URDF Elbow 상한 초과 1,156/1,156은 시작 정지 자세에서 이미 존재했다. 새 두 관절 스냅샷 사이의 경로·실제 이동량/속도·충돌 여유는 `NOT_VERIFIED`, 자동 모션 `NOT_RUN`. 자세한 기록: [빈 작업대 이동 사전 점검](sessions/2026-10-08-empty-space-micro-motion.md). GitHub 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.

## 2026-10-08 follower 위치 제한 레지스터 읽기 — LeLab 복구 완료

- `PASS (approved read-only hardware check)`: 사용자 현장 안전 확인·읽기 전용 점검 승인 후 중지돼 있던 기존 `lelab.service`를 유지한 상태에서 canonical USB follower `5AE6058306`→`/dev/ttyACM0`, leader `5AE6085272`→`/dev/ttyACM1`, 서비스 inactive/dead·PID 0, root `fuser` 두 포트 점유 출력 없음을 확인했다. 설치 LeLab Python 3.14.7과 Feetech 제어표/`connect`·`read`·`disconnect` 실제 소스를 검사한 뒤 follower 버스 하나만 열어 Elbow(id 3) 제한 880–3087, Wrist_Pitch(id 4) 제한 936–3225 raw를 읽었다. `handshake=False`, `normalize=False`, 재시도 0이며 닫을 때 `disable_torque=False`를 명시했다. 모터 목표·토크·캘리브레이션·USB 설정 변경 및 로봇 동작 `NOT_RUN`.
- `PASS (restore)`: 진단 종료 후 기존 `lelab.service`만 시작했다. active/running·8000 health `ok`, 텔레옵·녹화·추론 active=false를 확인했다. follower 캘리브레이션 파일의 두 관절 `range_min/range_max`는 읽힌 레지스터와 각각 같다. 그러나 설치 URDF의 Elbow/Wrist_Pitch 범위와 기존 관절 방송의 불일치는 해소되지 않았고, 레지스터 값만으로 물리 하드스톱·하중 중 여유·연속 경로 안전을 증명할 수 없다. 자동 재생·집기 `BLOCKED/NOT_RUN`. 상세: [제한 레지스터 점검](sessions/2026-10-08-follower-limit-read.md).
- `LIMIT`: 레지스터 읽은 뒤 root `fuser` 재확인은 완료되지 않아 중단했다. 버스 API의 `disconnect(disable_torque=False)` 호출 이후 서비스 재시작·health는 성공했다. GitHub 이슈 API 갱신 `NOT_RUN`, 문서 원격 push `NOT_PUSHED`.

## 2026-10-07 수동 클릭 분류 경로 — Mac 8031 읽기 전용 라이브

- `PASS (A/B/C common-pose offline audit) / MOTION BLOCKED`: 기존 수동 A/B/C 투입 관절 방송의 처음/끝 값을 비교했다. B 끝과 C 시작의 여섯 관절 최대 차이는 0.006137 rad로 작지만, 양쪽 Elbow는 설치 URDF +1.5708 rad 상한을 약 0.046–0.047 rad 넘는다. A/B/C 처음 자세도 최대 0.822–1.286 rad 다르다. 세 시연은 표준 시작 자세의 반복 자료가 아니며 근접한 B→C 자세를 자동 PARK/재생 후보로 승인하지 않는다. 실제 follower의 canonical USB·버스 소유권·모터 제한 레지스터는 이번 감사에서 `NOT_VERIFIED`; 별도 단독 버스 읽기·로봇 동작 `NOT_RUN`. 상세: [공통 자세 감사](sessions/2026-10-07-manual-trace-common-pose-audit.md).
- `PASS (C→red ID4 user-operated one-shot) / REPLAY BLOCKED`: 사용자의 C 단독·빨강 바구니 비움·현장 안전·수동 1회 승인 아래 기존 LeLab 텔레옵으로 C를 잡아 들어 올리고 빨강 ID4 바구니에 바닥 접촉·개방·퇴피했다. 현장 보고는 간섭·걸림 없음이며 마지막 정면·사선 표본에는 빨강 바구니 안 약통과 위로 분리된 그리퍼가 보여 수동 성공과 부합한다. 종료 후 텔레옵·녹화·추론 inactive. 제어 없는 관찰 원본 관절 2,686개·정면 578장·사선 577장 무결성 통과, 하지만 Elbow 329개·Wrist_Pitch 17개 설치 URDF 상한 초과로 `URDF_LIMIT_MISMATCH`. 실제 하드스톱 위반 증명은 아니며 자동 재생·집기 `NOT_RUN`, 문서 `NOT_PUSHED`; 상세: [C→빨강 수동 투입](sessions/2026-10-07-c-red-manual-placement.md).
- `PASS (B/C trace limit interval audit, offline)`: B 투입의 Elbow 55개·Wrist_Pitch 13개 URDF 초과는 기록 끝 142–147초 구간에 있고, C 투입의 Elbow 초과 329개는 시작 0–12.19초·끝 135.71–140.57초, Wrist_Pitch 17개는 끝 132.76–133.61초에 모여 있다. 이는 방송값의 시간 분포일 뿐 물리적 하드스톱 위반이나 중간 경로의 자동 안전 승인 근거가 아니다. 원본·설정 변경 및 새 로봇 동작 `NOT_RUN`.
- `PASS (B→green ID5 user-operated one-shot) / REPLAY BLOCKED`: 사용자의 현장 안전·B 단독·초록 바구니 비움·수동 1회 승인 아래 기존 LeLab 텔레옵을 사용자가 직접 조작했다. 사용자는 B를 잡아 들어 올리고 초록 ID5에 바닥 접촉·개방·퇴피했으며 간섭·걸림이 없다고 보고했다. 마지막 정면·사선 표본에는 초록 바구니 안 약통과 위로 분리된 그리퍼가 보여 수동 성공과 부합한다. 중간 사선 표본이 병의 바구니 진입을 시사해 추가 하강·개방을 멈추고 현장 바닥 지지·간섭 없음 확인 후 진행했다. 종료 후 텔레옵·녹화·추론 inactive. 제어 없는 원본 관절 2,813개·정면 594장·사선 592장 무결성 통과, 하지만 Elbow 55개·Wrist_Pitch 13개의 설치 URDF 상한 초과로 `URDF_LIMIT_MISMATCH`. 실제 하드스톱 위반 증명은 아니며 자동 재생·집기 `NOT_RUN`, 문서 `NOT_PUSHED`; 상세: [B→초록 수동 투입](sessions/2026-10-07-b-green-manual-placement.md).
- `PASS (A-only user-operated non-contact reach) / REPLAY BLOCKED`: 사용자가 A 단독 오른쪽 슬롯·현장 안전·시작 자세를 확인하고 LeLab 텔레옵으로 A 상공 비접촉 정지·퇴피를 직접 수행했다. 제어 없는 관찰 기록 1,191개 관절·정면 256장·사선 255장의 해시/시간 무결성은 확인됐다. A 검출 중심은 기존 픽업 ROI 밖이다. 사진에는 A 뚜껑 근처로 접근한 그리퍼와 퇴피한 그리퍼가 보이나 실제 공기 간격·전체 경로 무접촉은 독립 확정할 수 없다. **첫 종료 보고 뒤** API가 여전히 active였고 재종료 뒤에야 inactive를 확인했다. URDF 감사 `URDF_LIMIT_MISMATCH`: Elbow 상한 초과 875/1,191개(최대 0.047178 rad). 자동 재생·집기·투입 `NOT_RUN`, 문서 `NOT_PUSHED`; 상세: [A 비접촉 관찰](sessions/2026-10-07-a-hover-manual-trace.md).
- `PASS (B-only user-operated non-contact reach) / REPLAY BLOCKED`: 사용자가 현장 안전·B 단독 가운데 슬롯·시작 자세를 확인하고 기존 LeLab 텔레옵으로 B 상공 비접촉 정지·퇴피를 직접 수행했다. 시작 API는 텔레옵 active, 종료 API는 inactive이며 녹화·추론도 inactive였다. 제어 없는 관찰 기록 1,937개 관절·정면 424장·사선 425장의 해시/시간 무결성을 확인했다. 사진에는 B 위와 이후 분리된 그리퍼가 보이나 전체 경로의 실제 간격은 정량 검증되지 않았다. 설치 URDF 감사는 Elbow 상한 초과 1,020/1,937개(최대 0.036437 rad)로 `URDF_LIMIT_MISMATCH`; 이는 물리 하드스톱 위반 증명이 아니며 자동 재생은 계속 금지한다. 현재 canonical USB는 SSH 인증 거부로 `NOT_VERIFIED`. 접촉·집기·투입·자동 동작 `NOT_RUN`. 상세: [B 비접촉 관찰](sessions/2026-10-07-b-hover-manual-trace.md).
- `NOT_PUSHED (B observation record)`: 위 B 시험 문서·상태 변경은 로컬 커밋에만 있다. 기존 원격 브랜치로의 push는 외부 전송 위험 심사에서 거부됐으며 우회하지 않았다. 원본 자료는 Git 제외 로컬 보존이다. 관련 GitHub 이슈 갱신도 `NOT_RUN`.
- `PASS (C 접근 기록 오프라인 구간 감사)`: Git 제외 C 단독 관찰 기록 2,298개를 무결성 감사 뒤 분석했다. 첫 0.01 rad 이상 자세 이탈은 index 777/시작 후 40.601초, 기록 끝까지 잠정 활동 구간은 79.384초다. Elbow의 설치 URDF 상한 초과 792개는 index 0–791/시작 후 약 41.322초까지 **연속**이며, 활동 시작 직후 약 0.72초와 겹친다. 마지막 144개 관절 방송은 7.412초간 동일한 값이고 마지막 정면 JPEG에 C 위 그리퍼가 보인다. 이것은 수신·방송 자료일 뿐 실제 손끝 공기 간격·퇴피 전체·안전 경로 증명은 아니다. 읽기 전용 요약기에 마지막 동일 자세 방송 구간 표시를 추가해 단위 테스트 3개와 기존 감사 6개 통과. `use_for_replay=false`, 자동 모션 `NOT_RUN`. 상세: [C 기록 오프라인 감사](sessions/2026-10-07-c-hover-offline-audit.md).
- `PASS (C-only manual non-contact reach) / REPLAY BLOCKED`: 사용자의 현장 안전 확인과 C 한 병 비접촉 상공 도달 시험 승인을 받은 뒤 A/B가 치워지고 C 상자 하나(x≈309 px)·ID0–6을 확인했다. Jetson SSH에서 `lelab.service` active/running, canonical follower `5AE6058306`→ACM0·leader `5AE6085272`→ACM1, root `fuser -v` 두 포트 점유 출력 없음을 확인했다. 사용자가 기존 LeLab 텔레옵을 직접 켰고, 정면·사선 영상에 C 위 그리퍼가 보였으며 사용자가 공기 간격·비접촉 정지를 확인했다. 로봇 제어 없는 관찰기는 120초 제한까지 관절 2,298개·정면 492장·사선 493장을 Git 제외 로컬에 기록했다. 퇴피 전 과정의 영상이 이 기록 안에 있다고 단정하지 않는다. 사용자는 비접촉 퇴피를 보고했으나 **첫 종료 보고 직후** API는 텔레옵 active=true였고 관절 수신도 신선했다. 재종료 요청 후 active=false를 직접 확인했다. 오프라인 무결성 감사는 파일·시간·영상 해시를 검증했지만 `URDF_LIMIT_MISMATCH`(Elbow 상한 초과 792/2,298, 최대 0.114689 rad)를 반환했다. 이는 물리 하드스톱 위반 증명이 아니며 자동 재생·집기 허가도 아니다. `use_for_replay=false`, `motion_authorized=false`; 접촉·집기·자동 동작 `NOT_RUN`.
- `PASS (next-stage evidence inventory, no motion)`: 기존 Git 제외 정지 waypoint 35건의 메타데이터를 읽기 전용 집계했다. `PARK` 7·`SOURCE1_HOVER` 2·`BASKET4_HOVER` 26뿐이고 35/35 모두 `use_for_replay=false`다. 현재 배치의 ID5/ID6 목적지 또는 A/B/C 각각의 연속 집기·투입 경로 증거가 이 waypoint 묶음에 없으므로, 카메라 목적지 판정을 곧바로 자동 실행으로 연결할 수 없다. 기존 A 수동 시연은 별도 관찰 자료이며 자동 재생 승인 자료가 아니다. 새 로봇 동작·설정 변경 `NOT_RUN`.
- `PASS/PUSHED (three-bottle live camera-only)`: 사용자 `배치 완료` 보고 뒤 8031 신선한 정면 프레임에서 서로 분리된 약통 검출 상자 3개(왼쪽 C·가운데 B·오른쪽 A 슬롯)와 ArUco ID0–6을 확인했다. 기본 규칙 `A를 파랑, B를 초록, C를 빨강`의 미리보기는 sequence 1317에서 각각 ID6/ID5/ID4 `DRY_RUN_ROUTE_ONLY`를 반환했다. A/B를 모두 빨강 ID4로 지정한 **시험용 예시**도 미리보기에서 두 경로를 반환했다. 두 입력 모두 저장·실행되지 않았고 `robot_enabled=false`, `motion_authorized=false`, `grasp_authorized=false`다. A/C는 `pickup_roi_match=false`, B만 true다. 8000 읽기 전용 상태의 텔레옵 active=false. 이 현장 판정 기록은 기존 `fix/usb-recording` 브랜치에 push했다. 물체 신원은 사용자의 고정 배치 보고에 의존하며 새 조명/카메라 위치 일반화·손끝 좌표·경로·실제 집기/투입은 `NOT_VERIFIED/NOT_RUN`이다.
- `PUSHED (ff57967)`: 8031 읽기 전용 명령 미리보기·ROI/집기 금지 표시·테스트·기록 7개 파일을 기존 `fix/usb-recording` 브랜치에 push했다. 관련 웹 12개·고정 슬롯 7개 시험, Python 구문 및 diff 검사 통과. 원본 사진·데이터셋·로컬 제외 목록·인증정보는 포함하지 않았다. GitHub 이슈 API 갱신은 로컬 `gh` 명령 부재로 `NOT_RUN`; 이 커밋 시점에 현장 3병 동시 배치는 아직 `NOT_RUN`이었고 실제 로봇 동작은 계속 `NOT_RUN`이다.
- `PASS (ROI audit, saved evidence only)`: Git 제외 보유 사진 80장의 저장 메타데이터를 다시 집계했다. 기존 픽업 ROI 일치는 A 0/23·B 35/35·C 0/22다. 이는 마커 평면에 투영한 **검출 상자 중심** 판정이며 약통 높이·실제 손끝 접촉 좌표 검증이 아니다. 명령 미리보기의 각 경로에 `pickup_roi_match`와 항상 false인 `grasp_authorized`를 표시한다. 8031 live health는 `ok=true`, 프레임 age 0.304초, `robot_enabled=false`였고 시험용 `A를 빨강` 요청의 응답도 `pickup_roi_match=false`, `grasp_authorized=false`, `motion_authorized=false`였다. 이 문구는 실제 사용자 명령으로 저장·실행되지 않았다. A/C 배치를 맞추려고 ROI를 단순 확대하지 않았고, 모든 종류의 자동 집기·재생은 `BLOCKED/NOT_RUN`이다.
- `PASS (8031 command-preview UI, no motion)`: 고정 슬롯 dry-run을 8031 화면의 별도 `목적지 명령` 입력·`명령 판정만` 버튼 및 `/api/command-preview`에 연결했다. 입력 명령은 저장·적용·로봇 전송하지 않는다. 8031의 정확한 임시 프로세스만 기존 카메라 입력·사진 저장 옵션 그대로 재시작했고 `/health` 신선도·`robot_enabled=false`를 확인했다. 브라우저에서 새 입력란이 보이고 실제 입력 `A를 빨간색`→A 오른쪽 슬롯/빨강 ID4 `DRY_RUN_ROUTE_ONLY`를 확인한 뒤 시험 입력을 비웠다. 기존 사진 80장·8000/8030·USB·모터는 변경하지 않았다. A/B 동시 장면·동적 명령의 실제 집기/투입 `NOT_RUN`.
- `IMPLEMENTED/PASS (fixed-layout dynamic command dry-run)`: 사용자는 `A를 빨강, B도 빨강`이 **명령 형식의 예시**라고 확인했다. 기존 A→파랑/B→초록/C→빨강 설정은 변경하지 않았다. 별도 `medicine_fixed_slot_command.py`와 provisional 640×480 슬롯 설정을 추가했다. 현재 한 클래스 YOLO 박스의 중심 x와 높이 가드로 왼쪽 C/가운데 B/오른쪽 A를 구분하고, 명령에서 A/B가 같은 빨강 ID4를 가리켜도 목적지만 제안한다. 관련 단위 테스트 7개 통과. 보유 80장 실검출+합성 마커 상태 오프라인 평가에서 C 22/B 35/A 23 모두 해당 슬롯 판정 통과. Mac 8031 라이브 health로 `A를 빨간색`→ID4 `DRY_RUN_ROUTE_ONLY`를 확인했다. 실제 A/B 동시 장면·독립 날짜/위치 검증 `NOT_RUN`; 로봇·좌표·경로는 계속 비활성이다. 상세: [수동/고정 슬롯 명령](MANUAL_PIXEL_ROUTE.md).
- `PUSHED (fixed-slot command 42170f7)`: 코드·설정·테스트·작업 기록을 기존 `fix/usb-recording` 브랜치에 올렸다. 원본 JPEG와 사용자 실제 목적지 명령은 포함하지 않았다.
- `PASS (A/B/C local curation)`: 사용자 확인 배치는 화면 왼쪽 C·가운데 B·오른쪽 A다. 저장본 90장(C 22/B 45/A 23)의 원본 SHA-256 90/90 일치를 확인했다. B 라벨 중 오른쪽 A 자리 클릭 x=429.49–449.81인 연속 10장(sequence 1423–1569)을 뒤따른 A 사진 및 앞선 B 사진과 대조했다. 사용자의 A를 B로 잘못 저장했다는 보고와 일치해 이 10개 폴더만 Git 제외 `.local/medicine-manual-captures-excluded/2026-10-07-b-as-a/`로 이동했다. 원본 JPEG·메타데이터는 수정/삭제하지 않았고 복원 가능하다. 보유 후보는 C 22/B 35/A 23 총 80장, 제외 10장이다. 양쪽 90/90 해시가 모두 일치한다.
- `PASS (offline detector QA only)`: 보유 후보 80장에 기존 한 클래스 ONNX를 오프라인 실행했다. 사용자 클릭점을 포함하는 약통 검출 상자는 A 23/23·B 35/35·C 22/22에 있었다. 검출 상자 높이 중앙값은 A 51.15 px, B 38.62 px, C 36.40 px이다. B/C 높이 범위는 겹치고 촬영 위치가 다르므로 이를 A/B/C 분류 정확도나 크기 임계값 검증으로 해석하지 않는다. 새 모델·로봇 제어 `NOT_RUN`.
- `LIMIT (classification)`: C/B/A가 각각 서로 다른 화면 x 구역에서만 찍혀 위치와 라벨이 완전히 얽혔다. 전체 화면으로 분류기를 학습하거나 같은 촬영 세션을 무작위 분할해 정확도를 주장하면 위치 암기·데이터 누출 위험이 높다. 80장은 `FOR_REVIEW` 후보이지 `training_ready`가 아니며 자동 A/B/C 분류·로봇 집기 승인에는 사용하지 않는다.
- `GIT (curation record)`: 제외 사유·수량·검증 결과를 기존 `fix/usb-recording` 브랜치에 기록한다. 원본 사진·로컬 제외 목록은 Git에 올리지 않는다.
- `INCIDENT/RESOLVED (8031 frozen UI)`: 첫 로컬 저장 화면의 브라우저 스크립트에 잘못 출력된 문자열 줄바꿈이 있어 전체 스크립트 구문 오류가 났다. 사용자의 화면은 고정 사진이 깨지고 상태가 `읽는 중…`에 멈췄다. 8031 서버·정면/사선 카메라 health 자체는 정상이었다. 문자열 이스케이프를 수정하고 정확한 Mac 8031 임시 프로세스만 재시작했다. 실제 브라우저를 새로고침해 상태 갱신·라벨 미선택 초기화·`고정 프레임 …`과 사진 표시를 확인했다. 회귀 단위 테스트를 추가했고 웹 테스트 11개 통과. 8000/8030·USB·모터는 변경하지 않았다.
- `PASS (first real saves, review only)`: 21:50 KST 읽기 전용 감사 시 C 라벨 저장 폴더 2개를 확인했다. 각 `ceiling.jpg` SHA-256이 `metadata.json`과 일치하고 `review_status=FOR_REVIEW`다. 신원은 사용자 선택에 따른 것이며 이 두 장을 자동 분류 정확도나 학습 준비 완료로 보지 않는다. A/B 수량은 촬영 진행 중 재확인 필요하다.
- `PUSHED (UI bug fix 77e8d30)`: 8031 브라우저 구문 오류 수정·회귀 검사·사고 기록을 기존 `fix/usb-recording` 브랜치에 올렸다. 원본 사진은 Git 제외다.
- `FIRST FAILURE (capture not saved)`: 사용자가 A/B/C를 위치·회전을 바꿔 여러 번 `현재 프레임 고정` 후 약통 가운데를 클릭했지만, 기존 8031 화면은 판정만 하고 파일 저장은 하지 않았다. Mac 작업 폴더와 다운로드·바탕화면을 확인했고, 새 촬영 파일은 발견되지 않았다. 사용자가 찍었다고 보고한 장수는 저장된 학습 사진 수로 계산하지 않는다.
- `IMPLEMENTED/PASS (local review capture)`: 8031에 별도의 `사진·라벨 로컬 저장` 버튼을 추가했다. 명시적 `--allow-manual-capture` 옵션에서만 활성화하며, 동일 프레임의 주석 없는 정면 JPEG와 사람 확인 A/B/C·클릭점·검출/마커 판정·SHA-256을 Git 제외 `.local/medicine-manual-captures/`에 기록한다. 같은 프레임 중복 저장은 거부한다. 결과는 `SAVED_FOR_REVIEW`이며 `training_ready=false`, `robot_enabled=false`, `motion_authorized=false`다. 브라우저 복원 시 라벨은 다시 미선택으로 초기화한다.
- `PASS (temporary live, no capture yet)`: 8031 임시 서버를 변경 코드로 다시 실행했다. `/health`에서 `ok=true`, 정면 age 0.324 s, 사선 age 0.171 s, `manual_capture_enabled=true`, `robot_enabled=false`를 확인했다. 현 시점 실제 저장 파일은 0건이다. 관련 단위 테스트 18개·Python 구문·diff 검사 통과. 실제 사람이 A/B/C를 확인해 누른 라이브 저장과 저장본 재로딩 검수는 `NOT_RUN`; 사용자 재촬영 대기다.
- `PUSHED (feature commit 74f3307)`: 코드·작업 기록 6개 파일을 기존 `fix/usb-recording` 브랜치에 올렸다. 원본 JPEG/데이터셋·인증정보는 Git에 포함하지 않았다.
- `IMPLEMENTED (repo only)`: 사용자가 정면 프레임에서 약통 중심을 클릭하고 A/B/C를 확인하면, 프레임 신선도·동일 sequence·ID0–3·목표 바구니 ID/색 매핑·약통 상자 포함 여부를 검사해 목적지 ID만 제안하는 읽기 전용 경로를 추가했다. 겹친 중복 상자는 IoU로 구분한다. 자동 A/B/C 분류나 로봇 집기 좌표·모터 명령은 없다. 상세: [수동 위치 지정](MANUAL_PIXEL_ROUTE.md), [세션 기록](sessions/2026-10-07-manual-pixel-route.md).
- `PASS (earlier tests/live read-only)`: 초기 판정 경로 단위 테스트 17개 통과. 최초 일반 샌드박스의 8000/8030 연결 거부는 네트워크 제한에 따른 잘못된 현장 진단이었다. 허용된 읽기 전용 조회에서 8000 health 200, 8002 health 200, Mac 8030 세 카메라 age 13–18 ms·오류 null을 확인했다. 당시 8000 텔레옵·녹화·추론 active=false였다.
- `PASS (temporary Mac 8031)`: 8000 MJPEG 직접 추가 구독은 503을 내어 즉시 종료했다. 기존 Mac 8030의 신선한 캐시 JPEG만 읽도록 변경해 임시 8031 읽기 전용 페이지를 실행했다. 최종 health ok, 프레임 age 0.202 s, 정면 약통 후보 1개, ArUco ID0–6 검출, 사선 수신 ok, `robot_enabled=false`. 브라우저에서 프레임 고정·라벨 미선택 차단과 약통 중심 클릭의 `DRY_RUN_ROUTE_ONLY` 표시를 확인했다. A 라벨 클릭은 **UI 시험용 가상 입력**이며 현재 약통 신원 판정이 아니다. 화면은 임시 프로세스여서 세션 종료 뒤 상시 구동 보장은 없다.
- `NOT_RUN (motion/classification)`: 실제 A/B/C 신원은 사용자가 확인해야 한다. 픽셀은 집기 좌표가 아니고 높이·World→Base/TCP·경로 검증은 차단 상태다. 8020 서비스, USB·토크·설정·모터 변경 없음. `robot_enabled=false`, `motion_authorized=false` 유지.

## 2026-10-07 LeLab 재연결·현재 약통 검출 — 자율 집기 미완료

- `PASS (service-only recovery)`: 사용자 재연결 요청 시 8000 HTTP는 연결 거부·Mac 8030 캐시는 약 5,286초 오래됐다. 8002/8022 텔레옵·녹화·추론 inactive, canonical follower `5AE6058306`→ACM0·leader `5AE6085272`→ACM1, root `fuser`의 두 장치 점유 출력 없음, 8000 user service inactive/dead·PID 0을 확인했다. 기존 `lelab.service`만 시작해 active/running·health ok와 세 제어 작업 inactive를 확인했다. Mac 8030의 기존 실행 명령·PID 12929·`robot_control=false`를 확인한 후 멈춘 수신 프로세스만 TERM 종료하고 동일 명령으로 재시작했다. 이후 세 카메라 age 5.5–15.7 ms·오류 null·`robot_control=false`다. 모터·토크·USB·설정은 변경하지 않았다.
- `PASS (one offline frame) / BLOCKED (unique grasp)`: 복구된 정면 캐시 한 장을 Git 제외 `.local/medicine-class-scenes/20261007_live_after_reconnect_ceiling.jpg`(SHA `6483b79f...433db4`)에 보존했다. 현재 영상에는 사람/기타 물체가 보이고 약통은 이전 고정 슬롯과 다른 화면 중앙 부근에 있다. 기존 한 클래스 ONNX를 이 저장 프레임에 오프라인 실행하면 겹치는 약통 후보 2개(confidence 0.894484·0.261647, bbox `[307.691,222.901,333.010,257.654]`·`[307.997,222.227,344.980,256.120]`)를 출력한다. 검출 JSON도 Git 제외 보존했다. 같은 물체의 중복 후보로 보이나 독립적인 단일 픽업 후보가 아니고 A/B/C 분류 출력도 없다. 이는 1프레임 오프라인 검출이지 실시간 폐루프 인식·집기 승인이 아니다. 팔 동작·LeLab inference `NOT_RUN`.
- `ARCHITECTURE`: 작업대 ArUco ID0–3은 영상 픽셀→작업대 평면 XY, 바구니 ID4–6은 목적지 식별용이다. 약통은 영상 검출기/깊이로 찾는 구상이며 약통 표면에 ArUco가 반드시 필요한 것은 아니다. 현재 누락된 A/B/C 구분, 신뢰할 픽업 후보·높이, World→Base/TCP 및 경로 검증 때문에 마커 좌표만으로 약통을 집고 분류하는 단계는 아직 아니다.

## 2026-10-07 A/B/C 종료 프레임 180건 추출·현재 사진 검출 비교

- `PASS (offline extraction, not success labeling)`: 새 읽기 전용 `scripts/audit_medicine_episode_ends.py`로 기존 A v2·B v1·C test 각 60회의 정면 영상에서 에피소드 시간표상 마지막 프레임을 추출했다. 연락표와 프레임 시각/마커 manifest는 Git 제외 `.local/dataset-episode-audit/20261007/`에 보존했다. ID4·ID5는 각 데이터셋 60/60 종료 프레임, ID6은 A 53/60·B 60/60·C 60/60에서 검출됐다. A의 ID6 7장 비검출은 가림 가능성이 있어 목적지 부재로 해석하지 않는다. 연락표에서 B는 중앙 ID6, C는 왼쪽 ID5 바구니 안 약통이 반복적으로 보이지만, 정지 한 장만으로 180회 성공/실패 라벨을 확정하지 않는다. 현재 규칙 B→ID5·C→ID4와 맞지 않는 기존 첫 시연 판단은 유지된다.
- `PASS (offline current-scene detector) / NOT_CLASSIFIED`: 기존 ONNX 모델 SHA `d2f8452e...5c846`과 설치 LeLab OpenCV로 저장된 A/B/C 정면 사진 각 한 장을 검사했다. 약통 후보는 각 1개, confidence A 0.968962·B 0.954861·C 0.908477이며 모두 동일한 `white_medicine_bottle_model` 클래스 0이다. 위치 bbox는 각각 `[421.569,206.586,456.775,257.626]`, `[420.563,215.952,453.643,256.040]`, `[423.911,215.363,449.996,251.292]` 픽셀이다. 이것은 세 물체 검출이지 A/B/C 분류 정확도 검증이 아니며, 단일 장면에서 크기만으로 규칙을 승인하지 않는다. 검출 JSON은 Git 제외 로컬에 보존했다. 모터·추론·녹화 `NOT_RUN`.
- `PASS (tooling)`: 종료 프레임 추출의 시간표/파일 인덱스 단위 테스트 5개 통과, Jetson 실제 LeLab Python·PyAV·PyArrow·OpenCV에서 180장 추출 통과. 원본 데이터셋·모델은 수정하지 않았다.
- `SERVICE STATUS CHANGED`: 오프라인 검사 후 8000 HTTP가 다시 연결 거부·Mac 8030 프레임이 오래된 상태임을 확인했다. Jetson `lelab.service`는 inactive/dead, Result=success·ExecMainStatus=0이다. `systemctl status`에 19:17:08의 명시적 Stopping/Stopped와 worker SIGKILL 기록이 보이나 누가 stop을 요청했는지는 `NOT_VERIFIED`다. 이번에는 재시작하지 않았다. 8000과 신선한 8030을 전제로 한 실시간 작업은 중지한다.

## 2026-10-07 현장 작업 없이 기존 A/B/C 자료 검수 재개

- `PASS (read-only inventory)`: Jetson의 기존 LeRobot 캐시에서 현재 사용 후보 A v2·B v1·C test가 각각 60 episode/32,597·27,613·28,966 frame임을 메타데이터로 재확인했다. 각 데이터셋의 기존 MP4는 A 7개, B 6개, C 7개이며 파일 크기 합계는 약 1.24/0.97/0.99 GB다. 원본 파일·LeLab 설정·로봇 제어 상태는 변경하지 않았다.
- `NOT_VERIFIED`: MP4 파일 존재와 에피소드 개수는 각 60회가 현재 사용자 규칙 A→ID6·B→ID5·C→ID4에 맞거나 성공했다는 증거가 아니다. 첫 에피소드의 B/C 목적지 불일치가 이미 확인돼 있으므로, 다음은 180회 각 종료 프레임의 목적지 마커·투입 성공 여부를 오프라인 검수하는 작업이다. 그 전 기존 B/C 모델 자동 실행은 계속 `REJECTED`다. 현장 사용자 작업은 현재 필요하지 않다.

## 2026-10-07 LeLab 8000 복구·C 세 카메라 촬영

- `PASS (service-only recovery)`: 사용자 요청에 따라 Jetson 8000의 기존 `lelab.service`만 시작했다. 시작 전 8000은 inactive/dead·PID 0, 8002/8022 텔레옵·녹화·추론 inactive였고 canonical follower `5AE6058306`→ACM0·leader `5AE6085272`→ACM1, root `fuser`의 두 장치 점유 출력이 없었다. 시작 후 8000 active/running·health ok, 텔레옵·녹화·추론 active=false다. 설정·USB·모터·토크는 바꾸지 않았다.
- `PASS (Mac receive recovery)`: 기존 Mac 8030 수신 프로세스는 8000 복구 뒤에도 40분 넘은 프레임을 반환했다. 명령·PID·loopback 바인딩·`robot_control=false`를 확인하고 해당 프로세스만 정상 종료한 뒤 동일 명령으로 재시작했다. 이후 정면/사선/손목 카메라 age 약 19–37 ms, 오류 null이다.
- `PASS (three cameras) / LIMIT (bottle views)`: 8030에서 정면·사선·손목 640×480 JPEG를 각각 한 장씩 거의 동시에 받아 Git 제외 `.local/medicine-class-scenes/20261007_C_threeview_*`와 SHA 메타데이터로 보존했다. C 약통은 정면·사선 두 영상에 보이나 손목 영상에는 그리퍼만 보인다. 세 카메라 수신 성공과 약통의 세 방향 가시성을 혼동하지 않는다. 노출시각 동기화도 `NOT_VERIFIED`; C 신원은 사용자 보고다. 촬영 뒤에도 LeLab 세 제어 작업 inactive, Mac `robot_control=false`다.

## 2026-10-07 C 재촬영·LeLab 8000 상태 확인

- `PASS (camera-only)`: 사용자 재촬영 요청 후 8002 텔레옵·녹화·추론 inactive를 확인하고 기존 정면 프리뷰에서 새 JPEG 한 장을 읽어 닫았다. 출발 자리 약 x=440,y=228에 약통 1개가 보이며, 위쪽의 다른 약통 2개는 계속 치워져 있다. 맨 왼쪽 보라색 용기는 남아 있으나 신원은 판정하지 않는다. 최신 사진·SHA·제한 메타데이터는 Git 제외 `.local/medicine-class-scenes/20261007_C_source_reshoot.*`에만 보존했다. 이전 C 사진은 원본 증거로 남기되 분류 후보에서 제외한다.
- `PASS (service diagnosis) / NOT_STARTED`: Jetson SSH의 실제 `jetson3` 계정으로 읽기 전용 조회한 결과 `lelab.service`(8000)는 `inactive/dead`, `MainPID=0`, `Result=success`, `ExecMainStatus=0`이다. Mac 8030 캐시는 약 1,366초 오래됐고 8000 HTTP는 연결 거부다. 사용자의 “켰음” 보고와 현재 서비스 상태는 일치하지 않는다. 서비스 시작·설정 변경·모터 동작은 하지 않았다.
- `LIMIT`: A/B/C 각 사진은 여전히 소수의 단일 프레임이고 C 신원은 사용자 보고에 따른다. 모델 비교·자동 분류·로봇 경로 승인은 `NOT_RUN`이다.

## 2026-10-07 C 주변 약통 제거 후 재촬영

- `PASS (camera-only)`: 사용자가 약통을 치웠다고 보고한 뒤, 8000은 여전히 연결 거부·Mac 8030 캐시는 약 934초 오래됐음을 확인했다. 8002 텔레옵·녹화·추론은 inactive였다. 8002 기존 정면 프리뷰에서 새 JPEG 한 장을 받고 닫았다. 이전 C 사진의 위쪽 약통 두 개는 사라졌고 출발 자리 약 x=440,y=228에 약통 하나가 남아 있다. 화면 맨 왼쪽 보라색 용기는 보이나 신원을 추측하지 않는다.
- `LOCAL ONLY`: 새 사진·SHA·제한 메타데이터를 Git 제외 `.local/medicine-class-scenes/20261007_C_source_cleared.*`에 보존하고, 앞선 C 사진은 수정하지 않았다. C 신원은 사용자 확인이며 단일 프레임으로 분류기 성능을 입증하지 않는다. 모델·마커 재검출·로봇 동작 `NOT_RUN`.
- `CORRECTION (SSH)`: 앞선 접속 시도는 이전 안내문의 잘못된 계정명으로 실패했다. 실제 문서의 `jetson3` 계정으로는 이번에 SSH 로그인에 성공했으나 사용자 중단 전 원격 명령은 실행하지 않았고 세션은 정상 종료했다. 8000 서비스 복구·원인 점검은 여전히 `NOT_RUN`이다.

## 2026-10-07 C 출발 자리 장면 확보 — 8000 서비스 비활성

- `PASS (camera-only)`: 사용자 `C 배치 완료` 후 Mac 8030 카메라 캐시가 약 10분 오래됐고 Jetson LeLab 8000은 연결 거부였다. Jetson 8002·8022 health는 정상이고 두 인스턴스의 텔레옵·녹화·추론은 모두 inactive였다. 8002의 `/robots/so-101`은 기존 카메라 8/4/6 설정과 일치했다. 기존 8002 정면 프리뷰 8에서 JPEG 한 장만 읽고 연결을 닫았다. 새 정면 화면의 출발 자리 약 x=440,y=228에 약통 하나가 있고 화면 위쪽 왼편에 다른 약통 두 개가 보인다. 출발 자리 약통이 C라는 신원은 사용자 보고에 따른 것이다.
- `LOCAL ONLY`: C JPEG·SHA·제한 메타데이터를 Git 제외 `.local/medicine-class-scenes/20261007_C_source.*`에 보존했다. A/B/C 각 단일 프레임은 학습·성능평가 자료로 충분하지 않다. C 검출기·마커 자동 재검출, 픽업 ROI 재검증, 자동 분류·모터 동작 `NOT_RUN`.
- `BLOCKED (service)`: 주요 LeLab 8000은 아직 연결 거부이고 Mac 8030은 오래된 프레임을 반환한다. 이 상태로 8030 화면을 현재 증거로 사용하거나 텔레옵·자동 제어를 재개하지 않는다. 8000 서비스 원인·복구와 새 프레임 검증은 별도 작업이다. 이번에는 서비스·USB·모터·토크 설정을 변경하지 않았다.

## 2026-10-07 B 단독 출발 자리 장면 확보 — 카메라 예시만

- `PASS (camera-only)`: 사용자 `B 단독 배치 완료` 후 Jetson 8000 텔레옵·녹화·추론 active=false, Mac 8030 세 카메라 오류 null·`robot_control=false`를 재확인했다. 정면 캐시 한 장에서 기존 A 출발 자리 약 x=440,y=228에 약통 1개가 보이고, 다른 약통들은 화면 왼쪽 바깥쪽에 있다. 이 한 개가 B라는 신원은 사용자 확인이며 영상에서 자동 판별한 결과가 아니다.
- `LOCAL ONLY`: 정면 원본·SHA·제한 메타데이터를 Git 제외 `.local/medicine-class-scenes/20261007_B_source.*`에 저장했다. 이전 여러 약통 장면은 별도 보류 자료로 남겼다. A/B 각 한 장은 분류기 학습·검증에 부족하고 픽업 ROI/로봇 좌표 문제도 미해결이다. 로봇 동작·자동 추론 `NOT_RUN`.
- `NEXT (user action)`: 텔레옵을 끈 채 B를 치우고 작은 C 하나만 같은 출발 자리에 놓으면 C 정면 장면을 같은 방식으로 확보한다.
- `NOT_RUN (A/B detector comparison)`: 로컬 기본·번들 Python에는 OpenCV가 없고, Jetson 비대화형 SSH는 인증 거부됐다. 기존 로컬 askpass를 통한 SSH도 이번 시도에서는 응답을 완료하지 않아 중단했다. LeLab/카메라 읽기 전용 API는 정상이며 설정·모터 상태는 변경하지 않았다. 모델 비교 결과를 추측해 기재하지 않는다.

## 2026-10-07 B 배치 장면 확인 — 단독 분류 자료 보류

- `PASS (read-only)`: 사용자 B 배치 완료 보고 후 Jetson 8000 텔레옵·녹화·추론 active=false, Mac 8030 세 카메라 수신 오류 null·`robot_control=false`를 확인했다. 모터·카메라 장치·USB 설정은 건드리지 않았다.
- `LOCAL ONLY / HOLD`: 정면 캐시 한 장에서 새 약통이 화면 약 x=375,y=231에 보이지만, 이전 A 출발 자리의 약통도 약 x=442,y=224에 남아 있고 왼쪽에 다른 약통도 보인다. B의 실제 개체 식별은 사용자 보고에만 의존하며 단독 B·동일 출발 자리 사진으로 인정하지 않는다. 원본 JPEG와 SHA·제한 메타데이터는 Git 제외 `.local/medicine-class-scenes/20261007_B_multibottle_unverified.*`에만 보존했다. 자동 분류 학습·모터 경로 결정 `NOT_RUN`.
- `NEXT (user action)`: 텔레옵을 끈 채 팔 이동 범위의 약통을 B 하나만 남기고, 기존 A가 있던 오른쪽 출발 자리로 B를 옮긴 뒤 다시 촬영한다. 현재 B로 보이는 약통과 남은 약통의 신원은 현장에서 확인해야 한다.

## 2026-10-07 배치 후 현장·기존 A/B/C 자료 점검 — 자동 실행 계속 차단

- `INCIDENT / STOPPED`: 사용자가 큰 A를 출발 자리에 두고 파란 ID6 바구니를 비운 뒤, LeLab 홈의 `Teleoperation` 버튼을 단순 이동으로 오인해 클릭했다. 실제로는 텔레옵이 즉시 시작됐다. 상태 API에서 active=true를 확인하자 즉시 공식 `/stop-teleoperation`을 호출했고 성공 응답 및 teleoperation/recording/inference active=false를 재확인했다. 사용자는 현장에서 예상 밖 움직임·접촉이 없고 안전하다고 확인했다. 이 버튼을 탐색 목적으로 다시 누르지 않는다. 별도 실제 모션 승인이나 녹화는 `NOT_RUN`.
- `PASS (camera-only, one current frame) / BLOCKED (routing)`: 기존 Mac 8030 캐시 정면/사선은 신선하고 오류 null이었다. 정면 JPEG 한 장에 ID0–6이 모두 검출되고 현재 파란 ID6은 화면 오른쪽이며 사선 영상으로 색↔ID를 교차 확인했다. 설치 파일과 SHA가 같은 기존 ONNX 검출기(OpenCV 4.13)는 약통 후보 1개(conf 0.968962)를 검출했다. 하지만 현행 `pickup_roi_table_mm` 안 후보는 0개(후보 투영 x=83.245 mm, ROI x=101–273 mm)여서 `medicine_sort_dry_run.py`는 `BLOCKED/pickup_candidate_not_unique`, 목표 ID=null을 반환했다. 영상 1장·높이 보정 전의 카메라 진단이며 로봇 좌표가 아니다. 사용자의 출발 배치를 오류로 단정하거나 ROI를 검증 없이 확장하지 않는다.
- `LOCAL ONLY (classification bootstrap)`: 사용자가 큰 A를 배치했다고 확인한 정면 캐시 JPEG 한 장과 SHA·불확실성 메타데이터를 Git 제외 `.local/medicine-class-scenes/`에 보존했다. 단일 장면은 A/B/C 분류기 학습·평가에 충분하지 않다. 후속 중간 B·작은 C를 같은 출발 자리에 각각 한 번씩 둔 카메라 장면만 안전하게 추가 수집하고, 로봇 동작은 시작하지 않는다.
- `PASS (existing dataset metadata) / REJECTED (direct B/C reuse)`: Jetson 로컬 LeRobot v3 데이터셋 A/B/C 각 60회·3카메라·30fps, 총 프레임 32,597/27,613/28,966을 확인했다. 과업 문자열은 `basket A/B/C`일 뿐 색·ID를 명시하지 않는다. 각 첫 에피소드의 시작·종료 영상과 ArUco를 읽으면 A 종료는 ID6, **B 종료는 ID6**, **C 종료는 ID5**다. 현재 사용자 규칙 B→초록 ID5·C→빨강 ID4와 첫 샘플부터 불일치하므로 기존 B/C ACT 모델을 현재 규칙에 바로 실행하지 않는다. 기존 ONNX 검출기는 A 첫 시작·끝 프레임에서 후보 0개, B/C에서 각 3개씩 검출해 과거 A 영상과 현재 장면의 인식 일관성도 보장되지 않는다. 나머지 59회씩의 라벨·성공 여부는 `NOT_VERIFIED`; 전체 데이터셋이 같은 목적지라고 일반화하지 않는다. 원본·추출 프레임은 Git 제외 임시 경로에만 두었다. 상세: `docs/sessions/2026-10-07-scene-dataset-qa.md`.

## 2026-10-07 수동 시연의 활동 구간 분리 — 학습·재생 불가 유지

- `PASS (offline, read-only)`: 새 `scripts/summarize_teleop_activity.py`가 원본 SHA-256/JPEG 감사 후 시작 자세 대비 0.01 rad 초과의 최초 시점을 찾았다. 87.103초·관절 1,685개 중 앞 62.925초는 이 기준에서 시작 자세를 벗어나지 않았고, 최초 변화(index 1216)부터 기록 끝까지 **잠정** 24.181초·469개다. 이 구간의 정면/사선 캐시 JPEG는 각 99장, 최대 프레임 간격 0.498/0.501초다. 시작·끝의 과업 의미를 자동 판정한 것은 아니다.
- `LIMIT`: 카메라는 Mac 수신시각 캐시이며 노출시각 동기 영상이 아니고 `camera_evidence_complete=false`다. 따라서 이 자료를 학습 준비 완료나 자동 재생 가능한 시연으로 승격하지 않는다. 원본 `URDF_LIMIT_MISMATCH`, World→Base/TCP 거부, 경로 간섭 미검증도 그대로다. 새 하드웨어 동작 `NOT_RUN`; `training_ready=false`, `use_for_replay=false`, `motion_authorized=false`.
- `PASS (test/live read-only)`: 신규 활동 요약 3개와 기존 원본 감사 6개 단위 테스트 통과. Jetson 8000 health는 `ok`, 텔레옵·녹화·추론 active=false다. 녹화 내부 `current_phase=preparing`, `session_ended=false`는 세션 정리 완료 증거가 아니다. 전체 테스트 묶음은 Mac Python별 누락 패키지와 sandbox loopback bind 제한으로 통과 판정을 내리지 않았다. 원본 JPEG·관절값은 Git 제외 경로에 그대로 보존. 상세: `docs/sessions/2026-10-07-teleop-activity-audit.md`.

## 2026-10-07 분류 규칙 확인 — 목적지 일부만 확정

- `USER CONFIRMED`: 큰 약통 A→파란 바구니 ID6, 중간 약통 B→초록 ID5, 작은 약통 C→빨강 ID4. 물리 좌우 순서는 움직일 수 있으므로 색상·ID를 기준으로 삼는다. 현재 YOLO 모델은 약통 단일 클래스만 검출해 A/B/C를 자동 구분하지 못한다. 규칙과 모델 능력을 혼동하거나 미분류 물체를 임의 배정하지 않는다.
- `IMPLEMENTED (offline only)`: 사람 확인 A/B/C 라벨과 저장된 비전 상태를 받는 결정 전용 `scripts/medicine_sort_dry_run.py`·규칙 JSON을 추가했다. 신선한 카메라, 작업대 기준 4개, pickup 후보 1개, 목적지 마커/색이 맞아야 마커 ID만 제안하며 좌표·모터 명령·재생 승인은 출력하지 않는다. 단위 테스트 5개 통과. 실제 카메라·로봇 연결 시험 `NOT_RUN`.
- `NO CHANGE (motion gate)`: 사용자 요청에도 실제 모터 경로의 URDF 한계·좌표 정합·충돌 차단은 삭제하지 않았다. LeLab 텔레옵은 읽기 전용 확인에서 inactive였다. 분류 규칙 정리에는 새 모터 동작이 필요하지 않다.

## 2026-10-07 수동 시연 오프라인 후속 분석 — 자동 동작 차단 유지

- `PASS (camera-only offline)`: 10월 7일 정면 캐시 JPEG 367장 전수의 원본 `DICT_4X4_50` ArUco 검출에서 바구니 ID4/5/6은 각 367/367장, 작업대 ID0/1/2는 각 367/367장, ID3은 352/367장이다. ID3 누락은 연속 15장(프레임 322–336)이며 해당 순간 네 점 homography를 구성할 수 없다. 마커 중심의 중앙값 대비 최대 편차는 ID0–6 모두 ≤1.031 px다. 기존 비전 코드는 기준 ID0–3이 모두 있을 때만 homography를 구성한다. 이 장면의 검출률을 일반 장면 성공률로 확대하지 않는다.
- `PASS (trace timeline / installed files read-only)`: 원본 관절값의 시작 자세에서 0.01 rad 이상 벗어난 첫 시점은 기록 시작 약 62.925초다. Elbow는 시작 1.687024 rad, 최대 1.687024 rad(약 96.659°), 기록 중앙값도 1.687024 rad이다. URDF +1.5708 rad 초과는 1,465/1,685개로 0–70.796초와 후반 약 4.849초 두 구간이다. Jetson 설치 URDF 네 복사본의 SHA-256이 기존 `443d38d7...f67236`과 같고 Elbow 상한 +1.5708 rad가 유지된다. 실제 follower 캘리브레이션 파일의 Elbow raw 880–3087도 변함없다. 과거 드라이버 변환식 기준 계산상 +97.01° 끝값과 이번 최대 방송값 사이 간격은 약 0.35°일 뿐이며, 물리 하드스톱·토크 한계의 실측은 아니다.
- `BLOCKED (automation)`: 수동 파란 ID6 투입 성공은 자동 안전 보증이 아니다. 사용자 현장 안전 확인은 인정하지만 URDF/캘리브레이션 불일치, World→Base/TCP 적합 거부, 연속 경로 충돌 검증 부족을 이유로 자동 관절 재생과 자율 투입의 안전 게이트를 제거하지 않는다. 텔레옵 종료 상태와 Mac 8030 `robot_control=false`를 재확인했다. 새 모터 동작 `NOT_RUN`. 상세: `docs/sessions/2026-10-07-offline-trace-analysis.md`.

## 2026-10-07 현장 승인 후 수동 시연 사전 점검

- `PASS (read-only)`: Jetson SSH 연결, canonical USB `5AE6058306`→`/dev/ttyACM0` follower·`5AE6085272`→`/dev/ttyACM1` leader를 확인했다. 시작 전후 root `fuser`에 두 포트 점유 출력이 없었다. 8002·8022의 텔레옵·녹화·추론은 모두 inactive다.
- `PASS (service-only)`: 8000 `lelab.service`가 inactive였으므로 기존 unit을 설정 변경 없이 시작했다. health `ok`, 텔레옵·녹화·추론 inactive이며 `/robots/so-101`은 leader ACM1/follower ACM0, 카메라 8/4/6을 가리킨다. 모터·토크·USB·캘리브레이션은 변경하지 않았다.
- `PASS (Mac evidence)`: 읽기 전용 Mac 8030 증거 페이지를 기존 명령으로 시작했다. 정면/사선/손목 카메라 수신 오류 null·프레임 신선도를 확인했고 `robot_control=false`다. 관절 방송 null은 텔레옵 inactive 상태와 일치한다.
- `PASS (passive capture / safe stop)`: 사용자가 경로 여유, 시작 자세·즉시 중단 준비를 확인하고 기존 텔레옵을 직접 시작·종료했다. 종료 후 LeLab 텔레옵·녹화·추론 active=false다. Mac은 모터·토크·USB를 제어하지 않고 캐시 정면 367장·사선 364장과 관절 방송 1,685개(87.103초)를 Git 제외 `.local/teleop-traces/20261007T050941_395283Z_d2c1f385/`에 저장했다. 원본·index 해시 검증 통과, 두 채널 수신 오류 null, 중복·역순 source timestamp 0건이다.
- `PASS (manual blue/ID6 placement) / LIMIT`: 사용자는 **큰 약통의 원래 목표가 파란 바구니**이고 현재 그 안에 있으며 투입·퇴피 중 걸림이나 이상 움직임이 없었다고 현장에서 확인했다. 종료 후 정면 영상에는 약통이 오른쪽 바구니 안에 보이고, 저장된 마지막 프레임의 ArUco 재판독에서 바구니 마커는 왼쪽 ID4·가운데 ID5·오른쪽 ID6이다. 저장소 설정은 ID6=blue다. 따라서 이번 파란 ID6 수동 투입을 현장 보고·종료 영상·마커가 일치하는 성공으로 기록하고, 앞선 “가운데 빨강 ID4 오투입” 판단과 가운데=ID4 가정을 철회한다. 단, 이것은 자율 분류/투입 성공이나 연속 경로의 독립 충돌 검증이 아니다. 설치 URDF 기준 Elbow 1,465/1,685개 상한 초과 최대 0.116224 rad로 `URDF_LIMIT_MISMATCH`(exit 2); 자동 재생·자율 투입은 계속 `BLOCKED`. 세부 기록: `docs/sessions/2026-10-07-manual-trace-preflight.md`.

## 2026-10-06 11:26 KST 텔레옵 영상 증거 수집 경로 보완

- `IMPLEMENTED (Mac only)`: 기존 관찰기가 텔레옵 중 LeLab 정면·사선 MJPEG를 추가로 열던 경로를 제거했다. 이제 `--camera-evidence`는 이미 실행 중인 Mac 8030의 캐시 JPEG를 읽고 원래 Mac 수신시각 헤더·신선도·중복·SHA-256을 검사한다. 8030이 없거나 정면·사선이 stale이면 기록 시작 전에 거부한다. 로봇 제어·재생 경로는 추가하지 않았다.
- `PASS (offline/runtime)`: 관련 단위/HTTP·비전 테스트 34개 통과. LeLab 세 제어 작업 inactive를 확인하고 정확한 Mac 8030 프로세스만 새 코드로 갱신했다. 첫 상태에서는 정면 stream closed·사선/손목 503이었으나 자동 재시도 후 모두 회복. 정면·사선 `/frame` 응답에 수신시각 헤더가 있고, 최종 세 카메라 age 5.4/12.9/13.1 ms·오류 null, `robot_control=false`, teleoperation inactive다. 텔레옵 inactive 상태의 실제 관찰기 CLI는 exit 2로 거부됐고 새 자료 0건이다.
- `NOT_RUN`: 새 방식으로 실제 사용자 수동 텔레옵을 촬영하거나 모션을 실행하지 않았다. World→Base 적합 거부·Elbow URDF 불일치·연속 경로 안전 미검증 때문에 자동 집기·투입·재생은 계속 차단이다. 상세 기록: `docs/sessions/2026-10-06-cached-camera-trace.md`.

## 2026-10-05 20:56 KST 사선 프리뷰 회복 확인

- `PASS (read-only live)`: 사용자 복구 보고 후 LeLab 8000 health ok, teleoperation·recording·inference active=false를 확인했다. Mac 8030이 미실행인 것을 확인하고 기존 loopback 증거 서버만 재실행했다. 두 차례 상태 조회에서 정면·사선·손목 frame age가 각각 6.5/14.3/20.9 ms 및 23.2/4.4/17.9 ms였고 세 카메라 오류가 모두 null이다. `robot_control=false`; 팔·USB·토크·Jetson 서비스를 변경하지 않았다.
- `SCENE (visual only)`: 8030 live 화면에는 인쇄된 ArUco 마커 여러 장, 약통 모형 여러 개와 빨강/초록/회색 계열 바구니 세 개가 보인다. 이는 이전 단일 빨강 바구니·약통 한 개 수동 시험 장면과 다르다. 마커 ID, 각 물체 인식 결과·정확한 좌표는 영상 육안으로 판정하지 않았다. 현재 장면에 과거 단일 슬롯 waypoint를 그대로 적용하지 않는다.
- `LIMIT`: 이번 확인은 영상 수신 신선도이며 마커·약통 인식 정확도, 텔레옵 중 동시 카메라 안정성, World→Base 정합 또는 자동 경로의 안전을 통과시킨 것이 아니다. 자동 집기·투입·관절 재생 `NOT_RUN` 유지.
- `PASS (offline current-frame vision)`: 무비밀번호 SSH는 거부됐으나 사용자가 앞서 허용한 대화형 SSH로 Jetson에 접속했다. 비밀번호를 명령줄·파일·Git에 남기지 않았다. Mac 8030의 정면 640×480 JPEG 한 장(SHA-256 `d2aee40f...0e36941`)을 Jetson `/tmp`로 복사해 해시 일치를 확인했다. Jetson OpenCV 4.12, 저장소와 해시가 일치하는 `detect_medicine_onnx.py`, 기존 ONNX 모델로 약통 후보 3개(confidence 0.968862/0.939377/0.918923)를 검출했다. 임시 Jetson 마커 코드와 실제 설치 config(SHA `40845529...ffd0`)로 ID0–6을 모두 검출했고 ID4는 equalized fallback이다. 테이블 평면 투영상 바구니 ID4/5/6과 세 약통 후보가 계산됐지만 설정된 pickup ROI 안은 가운데 후보 1개뿐이다. 단일 프레임·높이 보정 전이며 `robot_target_authorized=false`다.

## 2026-10-05 20:50 KST 텔레옵 종료 확인·프리뷰 재점검

- `PASS (read-only stop verification)`: 사용자 종료 보고 후 LeLab 8000 health `ok`, teleoperation·recording·inference active=false를 확인했다. recording 내부 `current_phase=preparing`, `session_ended=false`는 유지돼 세션 정리 완료로 해석하지 않는다. 모터·토크·USB·LeLab 제어 API는 건드리지 않았다.
- `PARTIAL (camera preview)`: 종료 직후 기존 사선 `/camera-preview/4`와 정면 `/camera-preview/8`이 각 HTTP 200으로 데이터를 보냈다. Mac 8030 증거 서버가 실행 중이지 않아 기존 읽기 전용 서버만 잠시 띄웠으나 정면·손목은 신선하고 사선은 503이었다. 별도 LeLab 원본 사선 재조회도 503이었다. 단독 조회 이후 503으로 바뀐 정확한 원인과 점유자는 `NOT_VERIFIED`; 점유를 해소하려고 LeLab·카메라 서비스를 재시작하지 않았다. 이번에 띄운 8030만 종료해 listener 없음과 제어 작업 세 가지 inactive를 재확인했다.
- `BLOCKED`: 정면·사선 동시 증거 및 World→Base/URDF 정합·경로 안전 검증이 없어 자동 투입·재생 `NOT_RUN`이다. 원본 촬영 자료와 개인 정보는 Git에 넣지 않는다.

## 2026-10-05 텔레옵 중 수동 관찰 자료 감사 — 자동 이동 계속 차단

- `USER CONFIRMED / LIVE READ-ONLY`: 사용자가 LeLab 8000 텔레옵을 직접 켜고 현장에서 안전하게 조작 중이라고 확인했다. 허용된 Mac 읽기 전용 `/teleoperation-status`가 `teleoperation_active=true`를 반환했다. 에이전트는 텔레옵 종료·재시작, 모터/토크/USB 조작 및 관절 재생을 하지 않았다. 종료 전 새 제어 작업은 시작하지 않는다.
- `PARTIAL / REJECTED`: 이전에 읽기 전용으로 수집한 5초 자료 `.local/teleop-traces/20261005T112954_740572Z_c336d33d/`를 새 감사기로 검사했다. 관절 98개와 정면 JPEG 21장의 해시·개수는 맞고 사선은 503으로 0장이다. 98개 모두 설치 URDF Elbow 상한 초과, 최대 0.114689 rad로 `URDF_LIMIT_MISMATCH`(감사 exit 2)다. 사선 영상 없는 부분 자료는 연결 경로·간섭 검증에 사용할 수 없다. 원본은 Git 제외 로컬에만 둔다.
- `PASS (offline tests)`: 관절·카메라 관찰/감사와 기존 캡처·비전 관련 31개 테스트 통과. 처음 sandbox에서 로컬 테스트 포트 생성이 거부되어 HTTP 테스트 3개가 오류였고, 로컬 테스트 실행 허가 후 31개 전부 통과했다. 영상 수신시각은 노출시각 동기화가 아니며 `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false` 유지. 자동 투입 `NOT_RUN`.

## 2026-10-05 8000 MJPEG 재사용 비전 진단 — 임시 동시 실행 확인

- `PASS (read-only concurrent smoke)`: Jetson 임시 디렉터리의 저장소 비전 코드가 기존 LeLab 8000 정면 `/camera-preview/8`과 사선 `/camera-preview/4`를 MJPEG로 받아 임시 loopback 8021에서 약통 후보 3개·ID0–3 및 바구니 마커를 표시했다. 정면 sequence 115, frame age 0.132 s, 사선 age 0.022 s, `robot_enabled=false`, `robot_target_authorized=false`를 확인했다. 35초 제한 시험 후 8021 listener 없음, 8000 active·세 제어 작업 inactive, 원래 8020 서비스 inactive다. 카메라 장치·USB·모터를 별도로 열지 않았다.
- `FIRST FAILURE / FIX`: 처음 OpenCV의 HTTP `VideoCapture`를 사용한 시험은 정면 sequence 2에서 멈추고 frame age 26.683 s인데도 health `ok=true`였다. 저장소 코드에 MJPEG JPEG 프레임 파서와 5초 신선도 게이트를 추가한 뒤 위 연속 갱신을 확인했다. 임시 코드만 Jetson에 복사했고 설치 서비스·unit은 변경하지 않았다. 지속 운영과 일반 장면 성능은 `NOT_VERIFIED`다.
- `NEXT GATE`: ArUco/YOLO 카메라 관찰은 진행됐으나 World→Base 변환 거부, Elbow URDF/캘리브레이션 불일치, 연속 적재 경로 안전 미검증 때문에 자동 집기·투입은 여전히 `NOT_RUN`이다.

## 2026-10-05 20:09 KST 8000 복구·ID4 비전 보완

- `PASS (approved service start)`: 사용자 승인 뒤 Jetson 8000의 기존 `lelab.service`만 시작했다. 시작 전 canonical USB `5AE6058306`→ACM0 follower, `5AE6085272`→ACM1 leader와 root `fuser` 두 포트 무점유, 다른 8002·8022 LeLab 인스턴스의 텔레옵·녹화·추론 비활성을 확인했다. 시작 후 8000 health 정상, 세 제어 작업 active=false, 기존 robot config·카메라 8/4/6 유지. 서비스 시작은 로봇 동작 시험이 아니다.
- `PASS (camera-only diagnosis)`: 8000 정면 MJPEG에서 ID0–3 기준 마커는 안정적으로 검출됐다. 빨강 바구니 ID4는 13프레임 중 3회, 별도 17프레임 두 배치에서 원본 2회/0회로 불안정했다. 같은 17프레임에 histogram equalization을 적용하면 ID4가 12회/16회 검출됐다. 두 번째 배치에서 기준 ID0–3은 원본·처리본 모두 17/17이다. 처리본에 비예상 ID17이 1회 나왔으므로 코드에서는 설정된 기대 ID만 보완 대상으로 취한다. 이 수치는 현 장면의 프리뷰 진단이며 일반 성능 검증이 아니다.
- `IMPLEMENTED (repo only)`: 읽기 전용 `medicine_yolo_web.py`에 원본에서 빠진 기대 마커만 밝기 균등화 결과로 보완하는 경로를 추가했다. 원본 검출 위치는 유지하고 `equalized_fallback_ids`를 상태에 표시한다. 8020 설치·실행은 `NOT_RUN`: 기존 `medicine-yolo-preview.service`는 `astra-v4l2-bridge.service`와 `Conflicts=` 관계여서 현재 8000 카메라 경로를 건드리지 않았다. ArUco 자동 투입, 로봇 좌표 등록, 모션은 계속 차단이다.

## 2026-10-05 19:40 KST Jetson 재점검 — LeLab 8000 비활성, 새 모션 없음

- `PASS (read-only SSH)`: Jetson `192.168.50.20:22`는 접속 가능하다. user `lelab.service`는 `inactive/dead`, `Result=success`, `MainPID=0`, `UnitFileState=disabled`이고 이번 부팅의 시작/종료 시각은 `n/a`다. 8000·8020은 listen하지 않고 8002·8022만 listen한다. Mac 8030도 연결되지 않았다. 비활성 원인과 현재 로봇·토크 상태는 `NOT_VERIFIED`다.
- `BLOCKED (live ArUco/robot validation)`: 저장된 코드·설정에는 작업대 ID0–3과 빨강 바구니 ID4를 읽는 비전 경로가 있지만, 현재 live 카메라/LeLab을 검증할 수 없다. 더 근본적으로 World→Base 변환·Elbow 한계 정합·적재 궤적 안전 검증이 완료되지 않아 ArUco 기반 자동 투입 및 관절 재생은 계속 `NOT_RUN`이다. 서비스·USB·모터·토크·설정을 변경하지 않았다. 새 서비스 시작과 실제 이동은 현재 현장 상태 확인 및 별도 승인 후에만 검토한다.

## 2026-10-05 설치 URDF 한계와 수동 관절 방송 불일치 — 자동 재생 거부

- `REJECTED (offline replay gate)`: Jetson 실제 설치 `so101_new_calib.urdf` SHA-256 `443d38d7...f67236`의 Elbow 상한은 1.5708 rad이다. 2회차 원본 2,704개를 SHA 검증 후 전수 대조하면 1,607개가 상한을 초과하고 최대 1.685489 rad(초과 0.114689 rad)이다. 다른 5관절의 URDF 범위 초과는 0건. `scripts/audit_teleop_trace.py`는 `URDF_LIMIT_MISMATCH`와 exit 2를 반환하며 재생/로봇/모션 승인 false를 유지한다. 19개 관련 단위/HTTP 테스트 통과.
- `PASS (installed-source read-only)`: 설치 LeLab `teleoperate.py`는 follower `elbow_flex`를 `Elbow`로 매핑하고 관측 도 값을 rad로 변환한다. 설치 LeRobot follower config의 `max_relative_target` 기본값은 None이고 `send_action`은 상대 차이 제한 옵션만 조건부로 적용하며 URDF 절대 상한은 적용하지 않는다. 이 차이는 URDF-방송 불일치의 원인 후보지만 물리적 하드스톱 초과의 증거는 아니다. 설정·캘리브레이션·모터를 변경하지 않았다.
- `PASS (calibration-file read-only)`: 실제 follower Elbow 캘리브레이션 파일의 raw 범위 880–3087과 설치 STS3215 드라이버의 4096-step·`(val-mid)*360/4095` 변환식으로 계산한 범위는 약 ±97.01°다. 방송 최대 1.685489 rad(약 96.57°)는 이 파일 상한보다 약 0.44° 낮다. **이는 저장된 캘리브레이션 파일 기준일 뿐** 실제 모터 제한 레지스터·하드스톱·동적 안전 여유는 확인하지 못했다. URDF 상한 90°와 파일 범위의 불일치도 미해결이다.
- `NOT_RUN`: URDF/캘리브레이션 정합 수정, 자동 재생, ArUco 기반 자동 투입, 새 모션. 현재 텔레옵·녹화·추론은 종료 후 inactive로 유지한다.

## 2026-10-05 빈 약통 수동 투입 2회차 — 연속 관절 관찰 성공

- `PASS (user-operated one-shot)`: 사용자가 기존 LeLab 텔레옵을 직접 켜고 이전 고정 슬롯의 빈 약통 모형 1개를 빨강 ID4 바구니에 놓은 뒤 직접 종료했다. 현장 보고는 투입 성공·간섭/걸림/이상 움직임 없음이다. 종료 후 8030 실시간 사선 화면에는 빨강 바구니 안 약통과 위로 분리된 열린 그리퍼가 보인다. 이후 읽기 전용 API에서 teleoperation·recording·inference active=false를 확인했다. 연속 관절 파일에는 카메라 영상이 없어 이동 중 간섭 여부의 독립 영상 판정은 `NOT_VERIFIED`다.
- `PASS (preflight read-only)`: SSH 대화형 인증으로 Jetson canonical serial `5AE6058306`→ACM0 follower, `5AE6085272`→ACM1 leader를 확인했다. 시작 전 root `fuser`에 두 포트 점유 출력이 없고 LeLab 8000 user service active였다. `/robots/so-101`의 leader ACM1/follower ACM0, config `so-101.json`, camera 8/4/6이 일치했다. 세 제어 작업 inactive, Mac 8030 카메라 세 대 fresh였다. 비밀번호는 저장·커밋하지 않았다.
- `PASS (local trace integrity)`: 사용자 직접 텔레옵 중 Mac에서 읽기 전용 `/ws/joint-data` 2,704개를 16:16:24–16:18:43 KST 약 139.7초 기록했다. `joints.jsonl` SHA-256이 manifest와 일치, 중복/역순 source timestamp 0건, 평균 수신율 19.35 Hz, 최대 수신 공백 389.4 ms(250 ms 초과 9건). 원본은 Git-ignore `.local/teleop-traces/`에만 보존했다. 종료 사유 `teleoperation_inactive`; `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false` 유지.
- `LIMIT`: 이 기록은 Mac 수신 시각의 관절 방송이지 실제 모터 명령·카메라 동기 영상·접촉/충돌 여유가 아니다. 자동 재생, ArUco 기반 자동 투입, 반복성 및 실제 약품 사용은 여전히 `NOT_RUN/NOT_VERIFIED`다.
- `OFFLINE COMPARISON`: 2회차 연속 기록을 1회차 정지 저장본 4개와 관절 공간에서 대조했다. 각 과거 자세의 최근접 샘플 최대 관절 차이는 0.3066/0.3744/0.4588/0.8163 rad로, 동일 자세의 재현이나 과거 waypoint 직접 재생 근거가 되지 않는다. 서로 다른 수동 시연의 사후 비교이며 영상 접촉/충돌 검증은 아니다.

## 2026-10-05 다음 수동 경로 기록 사전 점검 — 현장 확인 대기

- `USER CONFIRMED`: 같은 빈 약통 모형의 고정 슬롯 배치·현장 안전과 사용자 직접 수동 1회 시험을 명시 승인했고, 본인의 Mac 터미널에서는 Jetson SSH가 연결됐다고 보고했다. 에이전트의 별도 비대화형 SSH는 여전히 인증 거부라 해당 세션을 공유할 수 없다. 사용자 터미널에서 canonical USB·점유 출력의 읽기 전용 전달을 요청했다. 새 텔레옵은 아직 시작하지 않았다.
- `PASS (read-only)`: LeLab `/health` ok, teleoperation·recording·inference active=false. Mac 8030 정면·사선·손목 frame age 16.4/7.0/17.7 ms, 오류 null; 관절 방송 null은 텔레옵 inactive 상태와 일치한다.
- `BLOCKED (current USB mapping)`: Mac에서 `jetson3@192.168.50.20` SSH 공개키/비밀번호 인증이 거부돼 이번 시점의 canonical leader/follower USB 매핑·버스 소유권은 `NOT_VERIFIED`다. 현재 사용자 직접 텔레옵의 새 시작·연속 관절 기록·자동 재생은 `NOT_RUN`. 현장 배치·안전 및 연결 확인 뒤 별도 범위 승인 필요.

## 2026-10-05 연속 관절 관찰기 — 오프라인 준비만 완료

- `PASS (offline)`: 다음 사용자 수동 텔레옵에서 LeLab의 읽기 전용 관절 방송을 기록할 `scripts/observe_teleop_trace.py`를 준비했다. 텔레옵 inactive면 저장하지 않고, 종료 시 기록을 멈춘다. Git-ignore 로컬 기록은 재생·로봇·모션 승인 플래그가 모두 false다. 기존 8030 포함 테스트 15개 통과.
- `NOT_RUN`: 실제 연속 궤적 수집, 영상 동기화, 경로 안전 검증, ArUco 기반 자동 투입 및 자동 재생. 다음 현장 시험에는 새 안전 확인·명시 승인이 필요하다.

## 2026-10-05 8030 저장 라벨 보완 — Mac UI 반영 완료

- `PASS (offline tests)`: Mac 캡처 UI와 서버의 허용 목록에 `BASKET4_RELEASE`를 추가했다. 적재 여부·접촉은 자동 판정되지 않으며 모든 저장본의 재생·로봇·모션 승인 플래그는 계속 false다. `python3 -m unittest tests.test_teach_capture_web` 11개 통과.
- `PASS (Mac UI runtime)`: 기존 Mac 8030 PID·명령·작업 디렉터리와 LeLab teleoperation·recording·inference 비활성을 확인한 뒤, 해당 Mac 캡처 프로세스만 동일 Python·인자로 재실행했다. 페이지에 `BASKET4_RELEASE`가 표시되고 정면·사선·손목 카메라 frame age 약 7.7/29.6/29.7 ms, 오류 null이다. 재시작 직후 사선·손목의 일시적 503은 다음 조회에서 회복됐다. 텔레옵 비활성·`robot_control=false`; 팔 제어·자동 재생 `NOT_RUN`이다. 기존 1회 수동 투입 성공의 범위는 아래 기록 그대로다.

## 2026-10-05 빈 약통 모형 1개 수동 집기·투입 — 현장 1회 완료

- `PASS (user-operated one-shot)`: 사용자가 현장 안전·시작 자세·즉시 중단 준비를 확인하고 기존 LeLab 텔레옵을 직접 켜서, 고정 슬롯의 빈 약통 모형 1개를 몸통 양쪽에서 잡고 소폭 들어 올린 뒤 빨강 ID4 바구니 상공으로 이동했다. 현장에서 병 바닥·두 손가락의 테두리 여유를 확인하고 병 바닥을 바구니 바닥에 가볍게 댄 후 그리퍼를 열어 놓고 퇴피했다. 사용자는 최종적으로 접촉·걸림 없이 약통이 바구니 안에 남았다고 확인했다. 중간 질문에서 실수로 `걸림·약통 이동` 선택지를 눌렀으나 즉시 “안 걸렸음”이라고 정정했고, 최종 현장 보고·정면/사선 화면의 그리퍼 분리 모습과 일치한다. 걸림 사고로 기록하지 않는다.
- `PASS (local static evidence)`: `SOURCE1_HOVER` 2건(빈 그리퍼 접근, 약통 적재·소폭 들어올림), `BASKET4_HOVER` 2건(적재 상공, 바구니 바닥 접촉·개방 전)을 저장했다. 4건 모두 관절 샘플 15개·정면/사선/손목 JPEG 각 1장으로 총 JPEG 12장 SHA-256 일치, 최대 관절 표준편차 0.00190 rad, `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`다. 웹 메뉴에 `BASKET4_RELEASE`가 없어 마지막 저장본의 원본 라벨은 `BASKET4_HOVER`이나 의미는 **개방 전 RELEASE 후보**다. 원본 영상·관절 파일은 수정하거나 Git에 커밋하지 않았다.
- `PASS (post-check read-only)`: 사용자 직접 종료 뒤 LeLab teleoperation·recording·inference active=false, `/health` ok를 확인했다. recording 내부 `current_phase=preparing`, `session_ended=false`는 유지된다. 에이전트가 모터·토크·USB·LeLab 제어 버튼/API를 호출하지 않았다.
- `LIMIT`: 수동 1회 성공은 자동 재생 경로의 안전성, 반복성, 다른 약통/바구니, 실제 약품 취급을 증명하지 않는다. 저장본은 네 정지 순간뿐이며 개방·퇴피의 연속 궤적은 기록되지 않았다. 자동 재생·실제 투약 `NOT_RUN`. 상세: [waypoint 캡처 검수](sessions/2026-10-05-waypoint-capture-review.md).

## 2026-10-05 빈 약통 1개 수동 시험 사전 점검

- `PASS (camera-only)`: 사용자 배치 보고 뒤 Mac 8030 정면·사선 실시간 화면에 흰 뚜껑 원통형 약통 모형 1개가 빨강 바구니 뒤쪽 출발 위치에 서 있고, 작업대 기준 ID0–3과 바구니 마커가 보인다. 정면/사선/손목 frame age는 각각 0.4/8.2/30.9 ms, 수신 오류 null이다. 약통 내용물·정확한 슬롯·바구니 비움은 영상만으로 확정하지 않고 사용자 확인을 요청했다.
- `PASS (read-only controls)`: LeLab teleoperation·recording·inference 모두 inactive. recording 내부 `current_phase=preparing`, `session_ended=false`는 유지된다. 팔·토크·USB·서비스·재생은 변경하지 않았다.
- `APPROVED (user-operated trial only)`: 사용자는 빈 모형 1개·고정 출발 슬롯·빈 빨강 바구니를 확인했고, 사람·장애물 이탈, 리더·팔로워 시작 자세, 즉시 중단 준비 및 **수동 집기·투입 1회**를 명시 승인했다. LeLab 텔레옵 시작·조작·종료는 사용자가 직접 수행한다. 에이전트는 UI 시작/제어 버튼이나 모터 API를 누르지 않는다. 현재 시작 보고 대기 중이며 자동 재생은 승인되지 않았다.

## 2026-10-05 바구니 출입 후보 오프라인 정리 — 텔레옵 종료 확인

- `PASS (read-only stop)`: 사용자 종료 보고 뒤 LeLab teleoperation·recording·inference 모두 inactive를 확인했다. recording 내부 `current_phase=preparing`, `session_ended=false`는 그대로다. 새 제어·재생 `NOT_RUN`.
- `PASS (offline sequence reduction)`: 15:17:39–57의 8개 정지 캡처 중 15:17:42/43은 최대 관절 차이 0.0005 rad, 15:17:50/51은 정확히 같아 중복이다. 따라서 시간순 고유 자세는 약 6개다. 인접 캡처 간 최대 관절 차이는 0.3274 rad까지 있어, 저장 정지점만 단순 직선 보간해 자동 이동할 근거가 없다. 이 결과를 출입 경로의 **검토용 후보**로 사용한다.
- `USER_REPORTED (unloaded path)`: 사용자는 방금 빈 그리퍼로 바구니에 들어갔다 나올 때 테두리·벽 접촉이나 걸림이 없었고 약통 모형은 잡지 않았다고 확인했다. 이는 그 수동 시연의 현장 관찰로 기록하지만 연속 궤적 계측이나 적재 약통 안전성 증명으로 바꾸지 않는다.
- `NEXT PHYSICAL GATE`: 다음 한 변수는 빈 약통 모형 1개를 쥔 상태다. 고정 출발 슬롯 배치·카메라/마커 가시성·현장 안전·즉시 중단 방법을 재확인하고 **해당 수동 저속 텔레옵 시험의 명시 승인**을 받은 뒤에만 진행한다. 자동 재생은 계속 금지한다.

## 2026-10-05 바구니 출입 정지 지점 8건 — 증거 후보로 사용

- `PASS (local integrity)`: 사용자가 바구니 안팎으로 이동하며 15:17:39–57 KST에 추가 저장한 `BASKET4_HOVER` 8건의 JPEG 24장 SHA-256이 metadata와 모두 일치한다. 각 관절 샘플 15개, 최대 관절 표준편차 0.00274 rad이며 `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`다.
- `CANDIDATE (offline sequence only)`: 정면·사선 영상과 관절값에는 낮은 바구니 입구 부근 자세(15:17:39, 15:17:50/51)와 그보다 물러난 자세(15:17:42/43/48, 15:17:53/57)가 시간순으로 보인다. 15:17:42/43과 15:17:50/51은 각각 거의 중복 정지 자세다. 사용자 보고대로 출입 동작의 **정지 지점 후보**로 활용하되 원본 라벨은 바꾸지 않는다.
- `NOT_VERIFIED (path/payload)`: 이 캡처는 8개 정지점이지 그 사이 연속 관절·영상 궤적 기록이 아니다. 영상에서 약통을 쥔 상태는 확인되지 않고 Jaw 평균은 약 0.518–0.519 rad다. 그리퍼·약통과 바구니 벽의 간격, 실제 투입·퇴피 안전, 약통 놓기 성공은 입증되지 않았다. 자동 재생에 사용하지 않는다.
- `ACTION_NEEDED`: 검수 시 읽기 전용 LeLab 상태는 `teleoperation_active=true`, 녹화·추론 false였다. 촬영을 끝냈다면 사용자가 직접 종료해야 하며 종료 재확인 전 새 제어·재생 `NOT_RUN`이다.

## 2026-10-05 바구니 자세 역할 정정 — HOVER와 RELEASE 분리

- `CORRECTION`: 사용자는 낮게 저장한 바구니 자세가 약통을 실제로 놓기 위한 높이라고 설명했다. 이전의 “너무 낮아 사용하지 않는다”는 평가는 **상공 대기 HOVER 기준**에 한정한다. 15:11:23–30의 8건은 버릴 자료가 아니라 빈 바구니 `BASKET4_RELEASE` 후보 증거로 별도 검토한다. 원본의 `BASKET4_HOVER` 라벨·관절·영상은 수정하거나 재생 승인하지 않는다.
- `NEXT (offline/physical gate)`: ID4 경로에는 바구니 테두리 위에서 접근·이탈하는 HOVER와, 바구니 안에 약통을 놓는 낮은 RELEASE가 각각 필요하다. 저장된 정지 영상만으로 그리퍼 양쪽과 바구니 벽의 실제 간격, 병을 쥔 상태의 충돌, 투입·퇴피 경로는 입증되지 않았다. 같은 자세의 반복 촬영 대신 이 조건을 먼저 검증한다.
- `PASS (stop verification)`: 사용자의 종료 보고 뒤 LeLab 읽기 전용 상태에서 teleoperation·recording·inference 모두 inactive를 확인했다. 새 모션·재생 `NOT_RUN`.

## 2026-10-05 추가 `BASKET4_HOVER` 13건 검수 — 텔레옵 종료 요청

- `PASS (local integrity)`: 사용자가 저장한 추가 13건(15:11:00–15:11:30 KST)은 모두 `BASKET4_HOVER`, 각 관절 샘플 15개와 카메라 JPEG 3장이다. 새 JPEG 39장의 SHA-256이 metadata와 일치하고 최대 관절 표준편차는 0.00695 rad다. `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false` 유지. 원본은 Git-ignore 로컬에 보존했다.
- `NOT_APPROVED (visual waypoint)`: 사선·정면 영상에서 15:11:00/01 두 건은 바구니 위의 같은 자세(5개 관절 평균값 동일, 손목 롤 약 0.00113 rad 차이)로 보이나, 테두리 위 실제 수직 여유와 도달 경로는 입증되지 않았다. 15:11:16/19/20 세 건은 그리퍼가 화면 위쪽 또는 바구니 목표에서 벗어나 있다. 15:11:23–30 나머지 여덟 건은 손끝이 바구니 테두리·내부 근처까지 낮아 안전한 상공 자세로 승인하지 않는다. 13건 중 재생 승인 0건이다.
- `ACTION_NEEDED`: 읽기 전용 LeLab 상태에서 `teleoperation_active=true`, 녹화·추론 false였다. 사용자에게 중복 저장을 중단하고 LeLab에서 텔레옵을 직접 종료하도록 요청했다. 종료는 아직 `NOT_VERIFIED`; 새 제어·재생은 `NOT_RUN`이다.

## 2026-10-05 빨강 바구니 단독 배치 — 카메라 확인

- `PASS (camera-only)`: 사용자가 초록·파랑 바구니를 치웠다고 보고했다. Mac 8030의 새 정면·사선 프레임에서 바구니 한 개와 작업대 기준 ArUco 4장이 보인다. 사선 영상의 남은 바구니는 기존 빨강 ID4 배치 위치·형상과 일치한다. 정면 영상의 색감은 파랗게 보이므로 색상만으로 재식별하지 않는다. 카메라 frame age는 정면 9.7 ms, 사선 29.1 ms, 손목 1.4 ms이고 수신 오류는 없다.
- `PASS (read-only control state)`: LeLab `teleoperation_active=false`. 새 텔레옵, 촬영, 팔 동작, waypoint 재생은 `NOT_RUN`. 기존 낮은 `BASKET4_HOVER` 세 건은 계속 재생 금지다. 단일 빨강 바구니의 새 상공 자세 teach에는 별도 현장 안전 확인과 그 시험에 대한 명시 승인이 필요하다.

## 2026-10-05 의도치 않은 텔레옵 시작 후 종료 확인

- `PASS (read-only stop verification)`: 사용자가 LeLab에서 텔레옵을 직접 종료했다고 보고한 뒤, Mac의 읽기 전용 API로 `teleoperation_active=false`, `recording_active=false`, `inference_active=false`, `/health` ok를 확인했다. 이전의 `BLOCKED`는 이 확인 시점에 해소됐다. recording 내부 `current_phase=preparing`, `session_ended=false`는 여전히 남아 있어 세션 정리 완료로 해석하지 않는다.
- `NOT_RUN`: 종료 검증 과정에서 UI 버튼, 모터·토크·USB·서비스 제어, waypoint 재생·새 촬영은 실행하지 않았다. 의도치 않은 시작 자체는 아래 사고 기록으로 유지한다.

## 2026-10-05 텔레옵 의도치 않은 시작 — 즉시 현장 종료 요청

- `INCIDENT`: 사용자가 기존 텔레옵을 종료했다고 보고한 뒤, 상태 확인을 위해 LeLab 홈의 `Teleoperation` 버튼을 눌렀다. 이 버튼은 단순 화면 이동이 아니라 텔레옵 시작을 실행했고 UI에 `Teleoperation Started` 알림과 `Live Robot Data`가 표시됐다. 사전 현장 안전 확인·이번 시작 승인이 없는 상태에서 발생한 잘못된 조작이다.
- `BLOCKED (remote stop)`: 뒤로가기 모양의 레이블 없는 버튼으로 종료를 시도했으나 안전 검사가 대상·효과 불명으로 차단했다. 다른 우회 조작은 하지 않았다. 사용자에게 즉시 LeLab에서 직접 텔레옵을 종료하고 이동 범위 밖을 유지하도록 요청했다. 실제 종료 상태·물리 움직임은 아직 `NOT_VERIFIED`다. 이 상태에서 다른 제어 작업·촬영·재생을 시작하지 않는다.

## 2026-10-05 고정 슬롯 waypoint 첫 저장본 검수 — 자동 재생 금지

- `PASS (local integrity)`: `.local/fixed-slot-waypoints/`에 완성된 저장본 10개(`PARK` 7, `BASKET4_HOVER` 3)가 있다. `BASKET4_HOVER` 3건(14:52:17/19/28 KST)은 각각 관절 샘플 15개·카메라 JPEG 3장이고, 원본 9장 SHA-256이 metadata와 일치한다. 최대 관절 표준편차는 0.00831 rad 미만이다. 원본은 Git-ignore 로컬에 그대로 보존했다.
- `REJECTED (hover safety claim)`: 사선 영상에서 첫째·둘째 자세는 그리퍼가 빨강 ID4 바구니 내부까지 낮게 들어가고 반대편 손가락은 인접 초록 바구니 위에 있다. 셋째는 바구니 테두리 부근이나 정지 영상만으로 수직 여유·간섭 안전을 입증할 수 없다. 세 건 모두 안전한 `BASKET4_HOVER` 또는 자동 재생 가능한 waypoint로 승인하지 않는다. `PARK` 7건도 임의로 재라벨링하지 않았다.
- `NOT_VERIFIED (live state)`: 검수 시 Mac에서 LeLab 8000과 로컬 8030이 모두 연결 거부되어 현재 텔레옵 종료 여부와 live 카메라·관절 상태를 확인하지 못했다. 모터·토크·USB·LeLab 제어 API는 호출하지 않았다. 촬영 종료 시 사용자가 LeLab 텔레옵을 직접 끝내고, 연결 복구 뒤 세 제어 작업 inactive를 재확인해야 한다.
- `NOT_RUN`: 새 촬영, 경로 이동, 약통 집기, 자동 재생은 하지 않았다. 모든 저장본 `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false` 유지. 상세: [첫 waypoint 검수](sessions/2026-10-05-waypoint-capture-review.md).

## 2026-10-05 waypoint 현장 시작 전 연결 점검

- `PASS (approved recovery)`: 사용자가 LeLab 서비스 시작과 현장 안전을 명시 승인했다. SSH에서 `lelab.service`의 정확한 ExecStart가 기존 `uv` LeLab/uvicorn 포트 8000임을 확인하고, 서비스가 inactive/dead인 상태에서 `systemctl --user start lelab.service`를 한 번 실행했다. 이후 active/running, `/health` ok, teleoperation·recording·inference active=false를 확인했다. recording 내부 `current_phase=preparing`, `session_ended=false`는 그대로라 세션 정리 완료로 해석하지 않는다.
- `PASS (camera-only preview recovery)`: LeLab `/camera-preview/8`, `/4`, `/6`이 각각 HTTP 200 MJPEG 바이트를 실제 전송했다. Mac 8030은 서버 자체는 살아 있었지만 옛 프레임에 멈춰 있어, 세 제어 작업 inactive·정확한 Mac PID/명령/작업 디렉터리를 확인한 뒤 해당 8030 프로세스만 정상 종료하고 동일 인자로 재시작했다. 정면/사선/손목 frame age 각각 약 14/27/22 ms, 오류 null, 브라우저 waypoint 섹션 표시를 확인했다. 관절 방송 null은 텔레옵 inactive에서 예상 상태다.
- `NOT_RUN (motion)`: 이번 승인 범위는 LeLab 서비스 시작과 프리뷰 복구였다. 텔레옵·waypoint 저장·자동 재생·모터 명령·토크·USB 변경은 하지 않았다. 다음 고정 슬롯 빈 장면 teach에는 별도의 현장 안전 재확인과 명시적 텔레옵 승인이 필요하다. `robot_enabled=false`, `motion_authorized=false` 유지.
- `RESOLVED (initial LeLab outage)`: 승인 전 최초 점검에서는 Mac 8030 카메라 frame age가 약 64,420,000 ms이고 Jetson 8000이 연결 거부됐으며 `lelab.service`가 inactive/dead였다. 이때는 서비스·로봇을 변경하지 않았고, 오래된 화면을 live 증거로 사용하지 않았다. 사용자 승인 뒤 위와 같이 복구했다. 상세: [2026-10-05 사전 점검](sessions/2026-10-05-waypoint-preflight.md).

## 2026-10-02 고정 슬롯 waypoint 증거 수집 준비 — 로봇 미구동

- `PASS (offline implementation)`: Mac 8030 캡처 코드에 P1–P6 접촉 자료와 분리된 4개 고정 슬롯 경유 자세 증거 저장 모드를 추가했다. 기존 LeLab 텔레옵을 사용자가 직접 켜고 안정된 관절 방송·정면/사선 영상을 확보한 경우에만 `.local/fixed-slot-waypoints/`에 기록한다. P1–P6 접촉 API/버튼은 기본 차단했다. `capture_kind=waypoint`, `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`; 로봇 제어·재생 API는 추가하지 않았다. 설계/진입 게이트는 [고정 슬롯 waypoint](FIXED_SLOT_WAYPOINTS.md)에 있다.
- `PASS (Mac 8030 live)`: LeLab의 teleoperation·recording·inference active=false와 Mac 8030 기존 PID·명령·작업 디렉터리를 확인한 뒤 그 Mac 서버만 SIGTERM 정상 종료하고 동일 포트에서 새 코드로 시작했다. 새 페이지의 waypoint 섹션·접촉 캡처 중지 문구를 HTTP로 확인했다. 정면/사선/손목 프레임 수신 오류 null, 관절 방송은 텔레옵 inactive라 stale/null이었다. 종료 후 LeLab 세 작업 active=false를 재확인했다. recording 내부 `current_phase=preparing`, `session_ended=false`는 그대로다.
- `NOT_RUN`: Jetson/LeLab 변경, 실제 waypoint 텔레옵·캡처·경로 이동은 하지 않았다. 정지 자세 몇 개의 저장만으로 연결 경로의 충돌 안전이나 물체 집기를 증명하지 않는다. 새 현장 안전 확인·명시 승인 전까지 모션 차단 플래그 유지.
- `TEST`: 캡처 웹 단위 테스트 11개와 기존 TCP/FK 테스트 9개, 총 20개 통과. 첫 sandbox 실행은 loopback bind 권한 부족으로 기존·신규 HTTP 테스트 각 1개가 실패했고, 네트워크 권한이 허용된 같은 코드 재실행에서 당시 10개 모두 통과했다. 이후 기본 접촉 차단 테스트를 추가해 최종 20개를 재실행·통과했다.

## 2026-10-02 오픈그리퍼 양손가락 동시 이동 정정

- `PHOTO REVIEW (no motion)`: 사용자 측면·정면·후면 사진 3장에서 검은 패드가 달린 좌우 손가락은 각각 링크로 본체에 연결돼 있고, 그 뒤의 넓은 보라색 하우징은 손목에 부착된 비구동 기준 **후보**로 보인다. 사진만으로 하우징의 강성·URDF 프레임 대응을 실측 확인할 수 없고, 전방 X에 안전하게 접촉할 돌출 끝점은 확인되지 않는다. 손가락·카메라 렌즈·배선·나사를 새 접촉 기준점으로 임의 지정하지 않는다. 추가 P5 접촉 촬영은 중단한다. 고정 슬롯 시연용 사용자 teach 관절 waypoint 경로는 TCP/World→Base 적합과 별도인 설계 대안으로 검토하되 자동 재생·모션은 `NOT_RUN`이다.
- `CORRECTION (physical mechanism)`: 사용자는 오픈그리퍼의 두 손가락이 함께 움직이며 기존 촬영에서는 벌림을 최대한 유지했다고 설명했다. 앞서 “표시 반대편은 고정 손가락이므로 그 끝을 새 TCP로 사용”하라고 안내한 가정은 잘못됐다. 그 제안은 철회하고, 양손가락 어느 쪽도 실제로 고정된 접촉점이라고 가정하지 않는다. 기존 P5 수치는 URDF `jaw` 링크 기반 **오프라인 진단**일 뿐 실제 손끝 FK 검증이 아니다. 새 `gripper` 링크 재촬영·자동 모션은 `NOT_RUN`; 기존 모든 motion 차단 플래그 유지.
- `NEXT (no motion)`: 추가 P5 반복 촬영을 멈춘다. 다음은 별도 현장 승인 전에 손가락 구동부가 아닌 **비구동·강체 기준점**을 안전하게 정의할 수 있는지 또는 영상 기반 hand-eye 보정으로 전환할지 읽기 전용 설계 검토다. 임의 포인터를 붙이거나 로봇을 움직이지 않는다. `scripts/fit_fixed_point_tcp.py`의 CLI/출력도 `gripper=고정 손가락`이라는 잘못된 물리 매핑을 제거했다.
- `BLOCKED (wrist hand-eye feasibility)`: 기존 로컬 손목 JPEG 25장을 DICT_4X4_50으로 재검사했으나 25장 모두 ArUco 검출 0개였다. 저장소·로컬 캡처 범위에서 손목 카메라 intrinsic 보정값도 확인하지 못했다. 프로젝트 `.venv`의 OpenCV 5.0.0에는 `calibrateHandEye`/`calibrateRobotWorldHandEye`가 없다. 기존 자료만으로 hand-eye를 완료할 수 없고, 손목 마커 가시성·intrinsic·지원 런타임을 별도로 준비해야 한다. 또한 hand-eye는 손목 카메라 외부 파라미터를 주는 과정이지 양손가락의 접촉 TCP를 자동 검증하지 않는다. 로봇 동작 없이 수행한 예비 검토이며 TCP/World→Base `REJECTED`, `robot_enabled=false`, `motion_authorized=false` 유지.

## 2026-10-02 P5 새 저장본 3개 검수

- `PASS (local files)`: 사용자는 약 4개를 더 촬영했다고 했으나 `.local/teach-captures/`에서 새로 완성된 폴더는 16:01:31/41/49 KST의 P5 세 건이다. 사용자는 세 번만 저장에 성공했을 가능성을 인정했다. 각 폴더에 정면·사선·손목 JPEG 3장과 관절 방송 15개가 있고, 원본 이미지 hash·관절 안정성·수신 시각 간격·motion 차단 플래그 검사가 통과했다. 원본은 Git-ignore 로컬에 보존했다.
- `PARTIAL (fixed-baseline holdout)`: 기존 첫 네 P5 fit 자세를 변경하지 않고 세 새 파일을 각각 holdout으로 검사했다. 16:01:31은 Jaw 0.08118 rad/방향 차이 11.37°/오차 5.566 mm로 수치 통과, 16:01:41은 Jaw 0.08759/3.63°/9.574 mm로 자세 중복·오차 초과, 16:01:49는 Jaw 0.08759/15.29°/6.380 mm로 수치 통과했다. 사용자는 세 번 모두 같은 움직이는 손가락 플라스틱 끝을 P5에 실제 접촉시켜 완전히 멈춘 뒤 저장했다고 확인했다. 이는 현장 보고이고, 영상만으로 동일 물리 끝의 실제 접촉 높이를 독립 검증한 것은 아니다. 세 후보를 뒤늦게 일곱 자세 fit에 대입한 탐색 결과도 2/3 통과이나 원래의 독립 기준선을 대체하지 않는다.
- `HYPOTHESIS (systematic residual)`: 첫 네 P5 자세에서 추정한 TCP로, 이후 사용자 접촉 주장 15건(명백한 오저장 한 건 제외)의 예측 고정점 Z 잔차는 전부 음수, 평균 −3.835 mm(범위 −6.278…−0.992 mm)다. Jaw 0.08–0.09 rad로 가까운 일곱 건도 모두 음수(평균 −3.822 mm)이며 전체 Jaw-Z 상관계수는 0.199라 벌림 차이 하나만으로 편향을 설명하기 어렵다. 첫 fit 블록과 후속 접촉 사이에 공통 방향 편향이 있지만 원인이 접촉 높이·손가락 변형·FK인지 `NOT_VERIFIED`다. 후속 13건을 사후 fit하면 새 세 파일의 합격/불합격 조합이 달라져 입력 집합에 민감하다. 같은 방식의 P5 반복 촬영만으로 승인하지 않는다.
- `PASS (read-only post-check)`: 천장 영상의 ID0–3은 첫째·셋째 모두 검출되고 기준 프레임 대비 최대 중심 변화 1.031/0.5 px였다. 둘째에는 ID2가 그리퍼에 가려져 ID0/1/3만 검출됐다. LeLab teleoperation·recording·inference는 모두 inactive, Mac 8030 세 카메라 수신 오류 null·관절 방송 stale였다. recording 내부 `current_phase=preparing`, `session_ended=false`는 그대로다. 새 제어·토크·USB 조작은 `NOT_RUN`; TCP/World→Base 승인과 자동 이동도 `NOT_RUN`, `robot_enabled=false`, `motion_authorized=false` 유지.

## 2026-10-02 P5 후보 교차 검증·로드맵 갱신

- `PARTIAL (offline cross-check)`: 원본 변경·로봇 구동 없이 첫 네 P5 fit 자세와 수치 통과 후보 세 개를 교차 검증했다. 후보를 하나씩 holdout으로 두고 나머지 여섯 자세를 fit하면 14:57:40 KST는 holdout 2.062 mm이나 fit RMSE 5.024 mm(한도 5 mm 초과), 14:58:07은 holdout 6.221 mm/fit RMSE 4.546 mm, 14:59:04는 holdout 5.999 mm/fit RMSE 4.560 mm였다. 2/3 수치 통과이나 세 후보 자체가 앞선 수치 결과로 선별돼 **사전 지정 독립 검증은 아니다**. 과거 두 holdout을 이 일곱 자세 fit으로 다시 검사하면 오차 7.559/6.898 mm이나 각각 최소 방향 차이 8.57°/6.55°로 10° 기준 미달이다. 어떤 재적합도 모션 승인에 사용하지 않았다.
- `PASS (camera-only reference check)`: 새 천장 캡처 10장 모두 ArUco ID0–3을 검출했다. 14:58:40 프레임 대비 9장 중 8장은 네 marker 최대 중심 편차 ≤0.559 px였고, 14:58:07의 ID0 검출값만 3.182 px 달랐다. 이 한 쌍의 ID0–3 영상 템플릿 비교는 모두 정수 픽셀 이동 (0,0), 유사도 ID0 0.9982여서 해당 ID0 값은 코너 검출 이상치로 판단한다. 이 카메라 안정성은 로봇 TCP 접촉의 증거가 아니고, 현재 FK-only P5 잔차를 설명하지 않는다.
- `ROADMAP`: [로드맵](ROADMAP.md)에 M4 병목과 남은 단계, 연구용 모형 이동 시연 약 35–45%·최종 VLM/사람 승인 시스템 약 20–30%의 거친 진행률을 기록했다. 이는 일정이나 성능 보장이 아니다. 별도 안전 승인 없는 새 텔레옵·모터 시험은 `NOT_RUN`; `robot_enabled=false`, `motion_authorized=false` 유지.

## 2026-10-02 사용자 저장 P5 추가 파일 읽기 전용 검수

- `PASS (local integrity)`: 기존 P5 자료 이후 14:57:07–14:59:04 KST에 새로 저장된 P5 캡처 10개를 확인했다. 각 파일은 정면·사선·손목 JPEG 3장과 관절 방송 15개를 포함한다. 원본 30장 해시, 관절 안정성, 수신 시각 간격, motion 차단 플래그와 설치 URDF SHA-256 검사를 오프라인 진단기가 통과했다. 원본은 Git-ignore `.local/teach-captures/`에만 보존한다.
- `PARTIAL (independent holdout)`: 앞서 확보한 첫 네 P5 자세를 고정하고 새 파일을 각각 미사용 holdout으로 평가했다. 10° 이상 다른 자세와 8 mm 이하 오차를 동시에 만족한 것은 14:57:40(4.45 mm), 14:58:07(7.73 mm), 14:59:04(7.60 mm) 3개다. 나머지 7개는 오차 초과 또는 자세 중복으로 거부됐다. 14:58:40 파일은 오차 133.62 mm이며 정면 영상에서 P5 X와 손끝이 떨어져 보여 접촉 증거에서 제외한다.
- `EXCLUDED (probable mis-save)`: 사용자는 처음 “모두 접촉이었음”이라고 답했고, 14:58:40 파일에 대해 후속으로 “아마 한 파일이 잘못 저장된 건데 그거인가봐”라고 보고했다. 이 파일은 세 저장 영상에서 손끝이 P5와 떨어져 있고 오차 133.62 mm이므로 접촉 검증·적합 입력에서 제외한다. 원본은 삭제·수정하지 않는다. 수치 통과 3개에는 현장 접촉 보고가 있으나 동일 플라스틱 끝 한 점의 실제 접촉은 영상만으로 독립 검증되지 않았다. TCP 승인·robot-world 적합·자동 이동은 `NOT_RUN`; `robot_enabled=false`, `motion_authorized=false` 유지. 상세 수치는 `docs/sessions/2026-10-02-tcp-preflight.md`에 있다.

## 2026-10-02 P5 단일점 다자세 TCP 진단 — 거부

- `REJECTED (second independent posture)`: 별도 현장 안전·P5 1점 승인 뒤 사용자가 텔레옵을 직접 다시 시작해 추가 검증 자세 `20261002T052704_660698Z_4e67d851`를 저장하고 직접 종료했다. 세 영상·관절값 수신 정상, 종료 뒤 세 제어 작업 inactive다. 새 holdout의 jaw-link 오차는 8.793 mm로 기준 8 mm 초과다. Jaw 0.05875 rad는 첫 네 fit 자세 0.08331–0.08652 rad와 여전히 달라 의도한 같은 벌림 비교군은 성립하지 않았다. 두 holdout의 base 잔차 방향은 비슷했다(cos 0.9225). 이는 jaw 기구학/접촉점의 체계적 차이 가능성을 시사하지만 원인은 `NOT_VERIFIED`다. 추가 촬영을 무작정 반복하지 않는다.
- `PASS (read-only Jaw feedback)`: Mac 8030 상태에 신선한 `/ws/joint-data` 방송의 `joint_jaw_rad`를 추가했다. 오래된 값은 null로 숨기며 로봇 제어 API는 추가하지 않았다. 캡처 웹 테스트 8개 통과, 기존 Mac 8030 프로세스의 명령·텔레옵 inactive를 확인한 뒤 Mac 서버만 정상 재시작했다. 세 카메라 수신 정상과 `joint_jaw_rad` 필드, teleoperation inactive를 재확인했다. 다음 비교군은 현장 승인 시 이 숫자로 첫 네 자세의 Jaw 범위와 맞춘다.
- `PASS (user-operated teleoperation / safe stop)`: 사용자가 약통·바구니를 치운 뒤 정면 화면의 X 6개·ID0–3, 표시한 플라스틱 손끝, 사람의 범위 이탈·즉시 중단 준비, 시작 자세를 확인하고 P5 다자세 텔레옵을 승인·직접 시작했다. 8000의 다른 제어 작업 inactive, canonical leader ACM1/follower ACM0, 두 serial의 유일한 점유자 LeLab worker, Mac 8030 세 영상·관절 수신 정상 확인 후 진행했다. 사용자가 직접 종료했고 8000 health 정상, teleoperation/recording/inference 모두 inactive를 재확인했다. Mac은 모터·토크·serial 제어 API를 호출하지 않았다.
- `PASS (local evidence)`: 같은 P5 X에 대해 다른 손목 자세 5개를 순서대로 확인·저장했다. 매 자세 정면/사선/손목 JPEG 3장과 관절 방송 15개, 총 JPEG 15장·관절 방송 75개다. 모든 JPEG SHA-256이 metadata와 일치하고, 최대 영상–관절 수신 시각 차이 25.2 ms, 최대 관절 표준편차 0.00397 rad였다. 원본은 Git-ignore `.local/teach-captures/`에만 보존했다. 영상에서 손끝은 P5 부근이나 실제 한 플라스틱 끝의 접촉 높이·점은 영상만으로 `NOT_VERIFIED`다.
- `CORRECTION (finger link)`: 사용자에 따르면 표시한 손가락은 움직이는 쪽이다. 따라서 `base→gripper`가 아니라 `base→jaw` FK를 써야 한다. 초기 gripper-link 가정에서 Jaw 변화가 고정 손끝을 깬다고 본 설명은 철회했다. URDF의 `Jaw`는 `gripper→jaw` 관절이며 관절값을 포함해 다시 계산했다.
- `REJECTED (offline pivot)`: 자세 1–4를 적합하고 자세 5를 독립 holdout으로 남긴 jaw-link 진단은 rank 6, 조건수 23.11, fit RMSE 4.310 mm, 최대 fit 6.576 mm였다. holdout 오차 9.537 mm는 허용 8 mm를 넘어 거부된다. 자세 5 Jaw는 0.05875 rad로 fit 네 자세 평균과 0.02617 rad 달랐지만, 움직이는 jaw 링크 FK에서는 변화 자체가 자동 거부 사유는 아니다. 물리 jaw 기구학·단일 끝점 접촉도 `NOT_VERIFIED`다. 기존 robot-world 변환 `REJECTED`, `use_for_robot_world_fit=false`, `robot_enabled=false`, `motion_authorized=false`; 약통 이동 `NOT_RUN` 유지.
- `PASS (tooling)`: 원본을 수정하지 않는 `scripts/fit_fixed_point_tcp.py`와 5개 단위 테스트를 추가했다. 설치 URDF SHA-256을 강제하고, 캡처 JPEG hash·관절 안정성·수신 시각·motion 차단 플래그를 확인하며 마지막 자세를 holdout으로 쓴다. 관련 fit 테스트 16개가 통과했다. 숫자 기준을 통과해도 물리 QA 전 모션을 허가하지 않는다.
- 세부 기록: `docs/sessions/2026-10-02-tcp-preflight.md`. 다음 현장 선택은 같은 손가락·P5에서 **새로운 검증용 자세 1개**를 실시간 Jaw 0.083–0.087 rad 범위로 먼저 맞춰 재촬영하는 것이다. 새 모터 동작은 현장 안전 재확인·별도 승인 전 `NOT_RUN`.

## 2026-10-02 TCP 단일점 재실험 사전 점검

- `PASS (read-only/recovery)`: Jetson `192.168.50.20` SSH 접속을 확인했다. 기존 `lelab.service` 8000은 inactive였고, canonical leader `5AE6085272`→`/dev/ttyACM1`, follower `5AE6058306`→`/dev/ttyACM0`였다. root `fuser`에서 두 serial 포트 점유자는 없었고, 8002·8022의 teleoperation/recording/inference는 모두 inactive였다. 기존 설정을 변경하지 않고 8000 user service만 시작했으며 health 정상, 세 제어 작업 inactive를 확인했다.
- `PASS (camera-only)`: 기존 Mac `127.0.0.1:8030` 캡처 페이지가 살아 있고 정면 Astra, 사선 RealSense, 손목 카메라의 프레임 수신 오류가 모두 null인 것을 확인했다. 관절값은 텔레옵 inactive라 새 방송이 없다. 로봇 제어·토크·USB 변경은 실행하지 않았다.
- `BLOCKED (physical scene)`: 정면 화면에 약통 3개와 바구니 3개가 X 접촉 영역에 놓여 있다. 고정된 X 한 점에 같은 플라스틱 손끝을 다양한 손목 자세로 접촉하는 TCP 실험 전에 이 물체들을 작업 범위 밖으로 치우고, X·ID0–3 가시성 및 사람의 범위 이탈·즉시 중단 준비를 다시 확인해야 한다. 사용자의 일반 안전 보고만으로 이번 특정 모션을 시작하지 않았다. 텔레옵/접촉 저장 `NOT_RUN`, 기존 변환 `REJECTED`, `robot_enabled=false`, `motion_authorized=false` 유지.
- 자세한 근거: `docs/sessions/2026-10-02-tcp-preflight.md`.

## 2026-10-01 P1 오지정 발견·재촬영·변환 재진단

- `BLOCKED_NETWORK (late recheck)`: 기록·push 뒤 Jetson `192.168.50.20:8000`과 Mac 8030이 동시에 응답하지 않았다. Jetson은 첫 ping 2/2·SSH 22 연결 성공이었으나 8000 timeout, 직후 ping 0/2와 SSH timeout으로 연결이 불안정해졌다. 원격 서비스 재시작·전원·USB 조작은 하지 않았다. Mac 8030 읽기 전용 서버는 다시 시작해 HTTP 응답하지만 세 카메라·관절 수신은 timeout이다. 앞서 확인한 세 작업 inactive는 **마지막 성공한 확인 시점**의 값이며 현재 Jetson 제어 상태는 `NOT_VERIFIED`다. 재연결·현장 상태 확인 전 모터 작업을 재개하지 않는다.
- `REJECTED (original P1 label)`: 첫 P1 저장본 `20261001T093659_729629Z_6e598848`의 정면/사선 영상에서 ID2 바로 오른쪽 P1 X는 노출돼 있고 손끝은 안쪽 왼쪽 P5 X 근처에 있다. P1 접촉 증거로 사용할 수 없다. 원본 metadata/영상을 수정·삭제하지 않고 오지정 기록으로 남겼다. P5 반복 접촉이었다는 가설도 정확한 단일 손끝 접촉은 `NOT_VERIFIED`다.
- `PASS (correct P1 recapture / safe stop)`: 사용자가 P1과 P5의 위치를 다시 구분하고 현장 안전·같은 손끝·시작 자세를 확인해 기존 LeLab 텔레옵을 직접 시작했다. 저장 직전 정면 화면에서 손끝이 ID2 바로 오른쪽 P1에 있고 P5 X는 별도로 보임을 확인했다. 새 P1 `20261001T113908_064438Z_ba1584e0`에 정면/사선/손목 640×480 JPEG 3장과 관절 방송 15개를 저장했다. 최대 수신 시각 차이 10.4 ms, 관절 표준편차 0 rad, Jaw 평균 0.06622 rad다. 사용자 종료 뒤 LeLab health 정상, 텔레옵·녹화·추론 inactive다. 정확한 물리 한 점 접촉·높이는 여전히 `NOT_VERIFIED`다.
- `REJECTED (offline diagnostic only)`: 보정된 marker 중심·기존 X 픽셀·P1/P2/P4/P5/P6 저장 프레임의 네 마커로 World 점을 다시 투영했다. P3 접촉 프레임은 ID3이 가려져 사용하지 않았고, 다섯 프레임 사이 점별 최대 투영 편차는 1.509 mm다. 검증되지 않은 여섯 캡처를 *탐색 진단에만* 넣은 결과 RMSE 4.731 mm, 최대 6.861 mm이나 조건수 4807.5(허용 ≤1000)로 거부된다. P2–P6 적합의 새 P1 의사-holdout 오차도 17.675 mm다. 첫 잘못된 P1을 P5 반복으로 가정해도 RMSE 5.814 mm/최대 9.275 mm/조건수 3935.1로 거부된다. 독립 holdout은 `NOT_RUN`; 결과는 모션에 사용하지 않는다.
- `SAFETY/NEXT`: 저장 metadata의 `use_for_robot_world_fit=false`, `robot_enabled=false`, `motion_authorized=false`와 기존 변환 `REJECTED`를 유지한다. 다음은 같은 단단한 손끝 한 점을 하나의 X에 서로 다른 안전한 손목 자세로 접촉시켜 TCP를 World와 분리해 추정하고, 남겨 둔 자세로 검증하는 단계다. 세부 조건은 `docs/TEACH_CAPTURE_WEB.md`에 기록했다. 새 모터 동작은 별도 현장 안전·명시 승인 전 `NOT_RUN`이며 원본은 Git-ignore 로컬에만 둔다.

## 2026-10-01 P2–P5 사용자 텔레옵·3영상 접촉 캡처

- `PASS (preflight)`: LeLab 8000 health 정상, teleoperation·recording·inference inactive와 Mac 8030 정면/사선/손목 수신 정상 확인 후 시작했다. canonical leader `5AE6085272`→ACM1, follower `5AE6058306`→ACM0. root `fuser`에서 두 serial 포트의 유일한 점유자는 LeLab 8000 worker PID 394935였고 별도 제어 프로세스는 발견되지 않았다. 사용자는 약통·바구니 제거, 사람의 범위 이탈·즉시 중단 준비·같은 노출 플라스틱 끝·시작 자세 정렬을 현장에서 확인하고 직접 기존 LeLab 텔레옵을 시작·종료했다. Mac은 모터·토크·serial·LeLab 제어 API를 건드리지 않았다.
- `PASS (local evidence)`: 사용자 접촉·안정 확인 직후 P2, P3, P4, P5를 각각 한 번 8030으로 저장했다. 매 지점 640×480 정면/사선/손목 JPEG 3장과 `/ws/joint-data` 15개, 총 새 JPEG 12장·관절 방송 60개다. 전 JPEG SHA-256이 metadata와 일치하며 최대 영상–관절 수신 시각 차이는 16.8 ms, 최대 관절 표준편차는 0 rad, 네 점 Jaw 평균은 0.06622 rad다. 원본은 Git-ignore `.local/teach-captures/`에만 보존한다.
- `PARTIAL (visual QA)`: 네 지점 모두 지정 X 근처에 손끝이 보이나 640×480의 가림·원근 때문에 동일 플라스틱 끝 한 점의 실제 접촉과 높이는 `NOT_VERIFIED`다. 새 P2/P4/P5 천장 영상은 ID0–3 모두 검출됐고 기준 P1 영상 대비 marker 중심 이동 최대 0.354 px였다. P3 저장 순간에는 ID3이 가려져 ID0–2만 검출됐으며, 다른 프레임의 마커 안정성이 P3 단독 homography를 대체하지는 않는다.
- `PASS (safe stop)`: 사용자 종료 보고 후 LeLab health 정상, teleoperation·recording·inference 모두 inactive다. recording 내부 `current_phase=preparing`, `session_ended=false`, follower torque register는 `NOT_VERIFIED`다. Mac 8030 세 프리뷰는 계속 정상이고 종료 후 관절 방송은 stale다.
- `NOT_RUN`: 새 6점 robot-world 적합/독립 holdout 및 실제 약통 이동은 실행하지 않았다. P1·P6은 앞선 텔레옵의 2영상 증거, P2–P5는 이번 텔레옵의 3영상 증거라 세션과 가시성이 서로 다르고, 모든 metadata의 `use_for_robot_world_fit=false`, `robot_enabled=false`, `motion_authorized=false`를 유지한다. 기존 변환은 계속 `REJECTED`다.

## 2026-10-01 P1·P6 웹 접촉 증거 저장

- `PASS (optional wrist evidence, camera-only)`: Mac 8030 캡처 페이지에 LeLab 손목 `/camera-preview/6` 보조 프레임을 추가했다. 정면/사선 필수 게이트와 15개 관절 검사는 유지하고, 손목 프레임이 없거나 오래됐으면 `optional_camera_omitted`로 기록해 필수 저장을 막지 않는다. 실제 640×480 손목 영상에 양 그리퍼와 X가 보였고 최종 8030 상태에서 정면/사선/손목 수신 오류가 모두 null이었다. 단위 테스트 7개 통과, 텔레옵 inactive 저장은 HTTP 400 거부. 실제 텔레옵 중 3영상 동시 저장은 `NOT_RUN`이다.
- `OBSERVED (local server restart)`: 첫 `.venv` 시작은 `websocket-client` 부재로 관절 worker만 실패했다. 의존성 사전 검사를 추가하고 기존 정상 Python으로 8030만 재시작했다. 재시작 직후 일시적 카메라 503이 있었으나 다음 상태 재조회에서 세 카메라 모두 정상 수신됐다. LeLab 8000 서비스·USB·로봇 설정은 변경하지 않았고 teleoperation inactive를 확인했다.
- `PASS (offline scene consistency, no motion)`: 두 저장 정면 프레임 모두 ArUco ID0–3 검출에 성공했다. 과거 단일 손끝 기록의 X 픽셀 중심과 비교할 수 있는 비가림 8개 관측의 이동은 각각 0.087–1.097 px였다. 따라서 기준 마커·X의 화면 배치는 대체로 유지됐지만 접촉한 X 자체는 그리퍼에 가려져 직접 중심 검출할 수 없었다. 보정된 마커 중심 좌표로 과거 X 픽셀을 이번 프레임에 재투영하면 P1–P2 약 266.0 mm, P1–P4 약 167.8 mm다. 과거 로컬 pair 파일의 `world_mm`는 보정 전 축척이므로 새 관절값과 그대로 결합하지 않는다.
- `PASS (user-operated teleoperation / evidence save)`: 사용자가 기존 LeLab 텔레옵을 직접 시작·종료했다. Mac `127.0.0.1:8030`은 정면 Astra와 사선 RealSense 프레임 및 관절 방송을 정상 수신했다. 사용자 현장 접촉·정지 확인 직후 P1과 P6을 각각 한 번 저장했다. 이 작업에서 Mac 캡처 앱은 로봇 제어 API를 호출하지 않았다.
- `PASS (local integrity)`: 두 지점 각각 JPEG 2장과 관절 방송 15개를 Git-ignore `.local/teach-captures/`에 저장했고, JPEG 4장의 SHA-256이 metadata와 일치한다. 수신 시각 기준 영상·마지막 관절 방송 차이는 P1 정면/사선 6.3/7.6 ms, P6 7.4/0.1 ms이며 최대 관절 표준편차는 두 지점 모두 0 rad였다. 이는 센서 노출 시각 동기화 증거는 아니다.
- `PARTIAL (visual QA)`: 두 영상에서 손끝이 각각 지정 X 주변에 있지만 640×480 영상으로 동일한 플라스틱 끝의 정확한 단일점 접촉을 확정할 수 없다. 사용자 확인은 metadata의 주장으로 유지하고 접촉 영상 QA는 `NOT_VERIFIED`다. 기존 robot-world fit은 계속 `REJECTED`이며 새 적합과 holdout 검증은 `NOT_RUN`, `robot_enabled=false`, `motion_authorized=false`다.
- `PASS (safe post-check)`: 사용자 종료 보고 뒤 LeLab health 정상, teleoperation·recording·inference 모두 active=false였다. recording status에는 `current_phase=preparing`, `session_ended=false`가 남아 내부 세션 정리는 `NOT_VERIFIED`다. follower torque register는 `NOT_VERIFIED`다.
- `DEFERRED_BY_USER (physical help required)`: P2–P5에는 이번과 같은 동시 접촉 증거가 없어, 새 P1·P6만으로 다점 fit/holdout을 승인할 수 없다. 사용자는 이번 P2–P5 텔레옵 진행을 원하지 않는다고 답했다. 새 모터 동작·캡처는 `NOT_RUN`이며 추후 현장 안전 확인과 별도 명시 승인 뒤에만 재개한다. 이번 두 점만으로 robot-world 변환을 승인하거나 실제 약통 이동을 하지 않는다.

## 2026-10-01 접촉 증거 웹 캡처 준비

- `PASS (read-only web implementation)`: Mac loopback `127.0.0.1:8030`에 새 `scripts/teach_capture_web.py`를 구현했다. LeLab 8000의 정면 `/camera-preview/8`, 사선 `/camera-preview/4`, `/ws/joint-data`만 구독하며 로봇 제어·serial 접근 API가 없다. 프레임·관절 15개를 수신 시각 기준으로 묶되 센서 노출 시각 동기화는 `NOT_VERIFIED`다. 원본은 Git-ignore `.local/teach-captures/`에만 저장하고 metadata에 motion 차단 플래그를 기록한다.
- `PASS (camera-only live smoke)`: 페이지에서 두 640×480 JPEG가 각각 HTTP 200으로 보이고 수신 프레임 나이가 약 70 ms였다. LeLab 텔레옵 inactive 상태의 캡처 POST는 HTTP 400으로 거부됐고 로컬 저장 폴더는 비어 있다. 브라우저에서도 두 영상과 읽기 전용 경고·지점 선택 UI를 확인했다. 실제 텔레옵 중 동시 캡처는 `NOT_RUN`이다.
- `PASS (preview recovery)`: 첫 라이브 스모크에서 사선 `/camera-preview/4`가 HTTP 503이었다. root `fuser`는 LeLab 8000 Python PID 393472의 `/dev/video4` 점유를 보였다. 공식 `/camera-preview-stop` 1회로도 503이 유지돼, 8000/8002/8022의 제어 작업 inactive 및 serial 두 포트 무점유를 확인하고 기존 8000 user service만 1회 재시작했다. 새 MainPID 394934, health 정상, 세 작업 inactive, 사선 MJPEG HTTP 200으로 복구됐다. 카메라·로봇 설정, USB, 토크는 변경하지 않았다.
- `PASS (offline tests)`: 새 웹 캡처·기존 읽기 전용 관절 모니터 테스트 8개가 통과했다. 실제 접촉 영상 QA와 새 다점 robot-world fit은 `NOT_RUN`, 기존 fit `REJECTED`, `robot_enabled=false`, `motion_authorized=false` 유지다.
- `PASS (GitHub)`: 구현·테스트·사용 절차를 commit `1e5cb91`로 비공개 `origin/fix/usb-recording`에 push했다. 원본 영상·관절 방송, 로컬 캡처 폴더는 커밋하지 않았다.
- `NEXT (physical approval)`: 사용자의 현장 준비·명시 승인 뒤에만 같은 세션에서 정면/사선 영상과 P1–P6 관절값을 다시 짝지어 수집한다. 미사용 holdout 점으로 검증한다. 세부 절차는 `docs/TEACH_CAPTURE_WEB.md`에 있다.

## 2026-10-01 P6 재측정 재개 사전 점검

- `PASS (P6-only teleoperation / safe stop)`: 사용자가 남은 컵·분홍 조각 제거, 동일 표시 손가락의 노출 플라스틱 끝, 사람의 팔로워 범위 이탈·즉시 중단 준비·시작 자세 정렬, P6 1점 저속 텔레옵을 현재 시점에 확인·승인했다. 새 정면 프레임에 X 6개와 ID0–3이 보이고 두 serial 장치의 root `fuser` 점유 PID가 없었다. 저장된 leader ACM1/follower ACM0로 `/move-arm` 1회 HTTP 200을 받아 사용자 P6 안정 접촉 보고 후 `/ws/joint-data` 15개를 읽고 `/stop-teleoperation` HTTP 200으로 즉시 종료했다. 종료 후 health 정상, 세 작업 active=false. 토크 register와 접촉 순간의 영상 증거는 `NOT_VERIFIED`다.
- `REJECTED (mixed-session P6 diagnostic)`: 새 P6 방송 15개의 관절별 표준편차는 0 rad였다. 이전 P1–P5·X 좌표와 결합한 보정 ArUco 기준의 *오프라인 진단*은 6점 RMSE 3.988 mm, 최대 5.907 mm이나 조건수 5555.7(허용 ≤1000)로 거부된다. P1–P5로만 적합한 변환의 독립 새 P6 holdout 오차는 9.932 mm(최대 허용 8 mm 초과)다. 접촉점의 영상 QA와 촬영일 간 X 위치 동일성도 검증되지 않았다. `robot_enabled=false`, `motion_authorized=false` 유지; 약통 이동 `NOT_RUN`이다. 원본 관절 방송과 임시 결과는 Git 제외 로컬 파일에만 보존한다.
- `PARTIAL (follow-up scene)`: 사용자가 약통·바구니를 치운 뒤 새 Astra 정면 프레임에서 P6 포함 X 6개와 ID0–3이 다시 보였다. 다만 왼쪽에 흰 컵과 분홍 조각이 남아 있고 손가락 표식은 영상으로 식별되지 않는다. 사용자에게 두 물체 제거, 동일 손가락·노출된 플라스틱 끝 확인, 현재 현장 안전 및 P6 1점 승인을 요청했다. 답변 전 `/move-arm`은 `NOT_RUN`이다.
- `PASS (read-only LeLab recheck)`: 8000 health 정상, teleoperation·recording·inference active=false. 저장된 `so-101` record는 leader ACM1/follower ACM0, 두 config `so-101.json`, camera index 8/4/6이며 오늘 확인한 canonical USB 역할과 일치한다.
- `PASS (service-only recovery)`: Jetson `192.168.50.20`은 ping·SSH에 응답했으나 LeLab 8000은 inactive였다. 기존 `lelab.service`는 2026-09-30 22:20 KST에 `Result=success`, `ExecMainStatus=15`로 종료된 상태였다. 기존 설정을 바꾸지 않고 user service를 한 번 시작했으며 8000 health가 정상이다. 8002·8022와 복구된 8000의 teleoperation·recording·inference는 모두 inactive였다. follower torque register는 `NOT_VERIFIED`다.
- `PASS (canonical USB metadata)`: Leader `5AE6085272`→`/dev/ttyACM1`, Follower `5AE6058306`→`/dev/ttyACM0`가 유지됐다. serial bus는 열지 않았다.
- `BLOCKED (physical P6 scene)`: 새 천장 정면 프레임에 약통 3개와 바구니 3개가 다시 놓여 P6 X가 가려진다. 손목 프레임에는 두 그리퍼 안쪽이 보이지만 같은 표시 손가락의 표식·노출 플라스틱 접촉점은 확인되지 않는다. 정면 화면 왼쪽 작업대에는 분홍색 조각이 여전히 보인다. 2026-09-30의 빈 작업대 안전 확인을 현재 배치에 적용하지 않고 P6 텔레옵·joint sample 수집은 `NOT_RUN`이다.
- `SAFETY`: `robot_enabled=false`, `motion_authorized=false`와 기존 robot-world fit `REJECTED`를 유지한다. 약통·바구니를 치워 P6과 ID0–3을 노출하고 표식/접촉점 및 현장 안전을 다시 확인하기 전 로봇을 움직이지 않는다.
- `PASS (prior preflight GitHub)`: 8000 복구와 안전 중단 기록을 commit `afeb6fc`로 비공개 `origin/fix/usb-recording`에 push했다. 이번 P6 재측정 결과의 commit·push는 종료 시 별도로 검증한다. 상세 기록은 `docs/sessions/2026-10-01-p6-reteach-preflight.md`를 참조한다.

## 2026-09-30 Jetson 재연결·현장 배치 재점검

- `PASS (approved LeLab restart / preview recovery)`: 사용자 승인과 세 작업 inactive 재확인 후 systemd *user* `lelab.service` 8000을 한 번만 재시작했다. 새 MainPID 371356, health 정상, teleoperation·recording·inference active=false. Astra `/camera-preview/8`이 MJPEG 3.3 MB/3초로 복구됐고 기존 로봇 record·카메라 index·canonical USB 역할이 유지됐다. 토크 register는 직접 읽지 않아 `NOT_VERIFIED`다.
- `PASS (camera-only corrected-frame smoke)`: 재시작 후 저장한 Astra 1프레임(SHA `57e50f30...c327`)을 오프라인 판독해 ID0–3 모두 검출, X 6개 중심 추출했다. Jetson의 보정 config로 P1–P2=265.071 mm, P1–P4=167.996 mm로 사용자 약식 실측 260/160 mm와 가까웠다. 단일 프레임이며 marker/접촉의 시간 안정성은 검증하지 않았다. 새 영상은 이전 teach의 P5·P6 접촉 증거가 아니며 거부된 `T_B_W`를 승인하지 않는다.
- `PASS (GitHub latest)`: 저장소 좌표·ROI 보정과 교차검증 commit `5ccf145`, Jetson 설치/백업·승인 서비스 재시작·정면 저장 프레임 검사 commit `334caba`를 비공개 `origin/fix/usb-recording`에 push했다. 작업 트리는 clean. GitHub CLI 로그아웃으로 issue API 갱신은 `NOT_RUN`이다.
- `PASS (center-distance cross-check / repository config)`: 사용자 독립 실측 ID2–ID3≈400 mm, ID3–ID0≈346 mm와 edge-gap 보정 예측 397.667/346.758 mm의 차이는 각각 −2.333/+0.758 mm다. `configs/astra_rgbd.example.json`의 기준 중심·pickup ROI를 보정하고 과거 중심·edge-gap 원본을 보존했다. 역사적 RGB-D/바구니 XY 검증은 구 좌표계 사용으로 stale 표시했다. 관련 테스트 42개 통과. 이는 카메라 live 재검증이나 robot-world fit 통과가 아니다.
- `PASS (Jetson config-only deploy / backup)`: root 소유 `/opt/so101-rgbd/astra_rgbd.example.json`의 원본 SHA `ce43a0d0...d9e1`을 `/home/jetson3/so101-recovery-backups/20260930T192133+0900_aruco-center-correction/`에 보존·해시 확인했다. 8020 medicine YOLO 서비스 inactive에서 보정 JSON 한 파일만 설치했고 Jetson/저장소 SHA `40845529...ffd0` 일치. LeLab health 정상, 세 제어 작업 inactive. 8020 서비스는 재시작하지 않았고 새 좌표의 live 카메라 검증은 `NOT_RUN`; robot fit 거부·`robot_enabled=false` 유지.
- `HISTORICAL (preview busy owner)`: 재시작 전 root 읽기 전용 `fuser/lsof`에서 Astra bridge 외에 LeLab 8000 PID 367493이 `/dev/video8`을 여러 FD로 열고 있었다. `/camera-preview-stop` 1회 후에도 busy였고, 설치 소스·systemd user unit을 확인한 뒤 위 승인 재시작으로 프리뷰를 복구했다. 중복 FD의 최초 원인은 `NOT_VERIFIED`다.
- `ROOT_CAUSE_CONFIRMED (reference measurement semantics)`: 사용자가 ID0–3의 기존 여섯 거리값을 마커 중심 간이 아니라 검은 정사각형의 가까운 변/대각선 모서리 간 간격으로 잰 것이라고 확인했다. 이를 중심 좌표로 쓰던 과거 설정에 축척 오류가 있었다. 저장소 예시 좌표는 위와 같이 정정했지만 Jetson 설치본은 아직 구 버전이다.
- `PARTIAL (provisional offline edge-gap correction)`: 마커 폭 ID0=75 mm, ID1–3=70 mm와 축 정렬 검은 사각형 가정으로 center를 임시 적합했다. ID0=(0,0), ID1=(403.5,0), ID2≈(401.375,347.228), ID3≈(3.708,346.738) mm; 가장자리 간격 적합 RMS≈2.623 mm다. 새 X 간격 P1–P2≈265.6 mm, P1–P4≈167.6 mm로 사용자 실측 260/160 mm에 가까워졌다. 같은 관절값의 오프라인 fit은 RMSE 5.299 mm, 최대 9.218 mm, 조건수 8474.4로 여전히 거부다. 별도 읽기 전용 진단 도구·로컬 결과로 보존했고 `robot_enabled=false`, `motion_authorized=false` 유지한다.
- `PASS (GitHub)`: 단일 손끝 teach/안전 종료, ArUco 측정 기준 오류, 임시 진단 코드·테스트를 commit `84e24b8`로 비공개 `origin/fix/usb-recording`에 push했다. 원본 영상·관절 입력·거부 변환은 Git 제외 로컬 파일이다. GitHub CLI 로그아웃으로 issue API 갱신은 `NOT_RUN`이다.
- `PARTIAL (camera busy audit)`: Astra V4L2 bridge는 active이고 `/dev/video8`이 존재한다. Jetson에는 LeLab uvicorn이 8000·8002·8022로 여러 개 실행 중이다. `/camera-preview/8`은 텔레옵 종료 후에도 busy이며, 일반 사용자 `fuser/lsof`는 `/proc/*/fd` 접근 제한으로 점유 주체를 확정하지 못했다. 기존 프로세스·서비스를 중지/재시작하지 않았다.
- `PASS (single-fingertip capture / safe stop)`: 실패한 닫힌 두 손끝 데이터와 분리해, 표시한 한 손가락의 단단한 플라스틱 끝을 TCP 후보로 정했다. 새 카메라 좌표와 P1–P6 사용자 확인 접촉의 관절 방송값 각 15개를 Git-ignore 로컬 입력에 저장했다. P2 첫 15개는 미세 움직임으로 제외했다. `/stop-teleoperation` HTTP 200 뒤 health 정상, teleoperation·recording·inference 모두 inactive다. Follower torque register는 `NOT_VERIFIED`다.
- `REJECTED (single-fingertip T_B_W)`: 실제 설치 URDF와 새 6점의 오프라인 fit은 RMSE 12.665 mm(기준 ≤5), 최대 17.731 mm(≤8), 조건수 6774.9(≤1000), rank 9로 거부됐다. 어느 한 점을 제외해도 RMSE 9.080–13.625 mm로 실패한다. `robot_enabled=false`, `motion_authorized=false` 유지; 이 변환으로 이동하지 않는다. 입력·거부 결과는 각각 `configs/robot_world_pairs.20260930.single-fingertip.local.json`, `configs/robot_world_transform.20260930.single-fingertip.local.json`에 보존했고 source hash가 일치한다.
- `PARTIAL (visual QA)`: P1–P4는 정면 화면에서 표시 끝과 X 위치가 맞았다. P5부터 `/camera-preview/8`은 `Camera is unavailable or busy`를 반환했고 P5·P6 영상 접촉 QA는 `NOT_VERIFIED`다. 카메라 서비스·USB는 변경하지 않았다. 사용자의 X 중심 실측 P1–P2=260 mm, P1–P4=160 mm와 구 좌표계 219/134 mm 차이의 주된 원인은 위 marker 기준 측정 의미 오류로 좁혀졌다.
- `PASS (6-point broadcast capture / safe stop)`: 동일 정면 화면과 현장 안전 확인 후 기존 LeLab 텔레옵을 1회 재시작했다. P1 초기값은 접촉 위치 재정렬 전 후보에서 제외하고, 재정렬 P1 및 P2–P6에서 `/ws/joint-data`만 각 15개(총 90개) 수집했다. 사용자는 두 손끝의 물리 접촉을 확인했다. 최종 `/stop-teleoperation` HTTP 200, LeLab health 정상, teleoperation·recording·inference active=false다. follower torque register는 `NOT_VERIFIED`다.
- `REJECTED (2026-09-30 6-point T_B_W)`: 실제 설치 URDF SHA-256 `443d38d7...f67236`의 base→gripper FK와 6점으로 TCP offset·World→Base 동시 적합을 수행했다. RMSE 13.377 mm(기준 ≤5), 최대 19.111 mm(≤8), 조건수 6250.9(≤1000), rank 9. 어느 한 점을 제외해도 기준을 통과하지 못했다. Astra 렌즈 왜곡 보정 좌표로 재계산해도 RMSE 13.179 mm로 거부된다. `T_B_W`는 실제 이동에 쓰지 않고 `robot_enabled=false`, `motion_authorized=false` 유지한다.
- `PASS (offline reproducibility)`: 원본 관절 sample·World 점은 Git ignore된 `configs/robot_world_pairs.20260930.closed-tip.local.json`, 거부 결과는 `configs/robot_world_transform.20260930.closed-tip.local.json`에 별도 보존했다. 새 offline 진단 도구 `scripts/fit_robot_world_from_joint_samples.py`는 기존 URDF FK와 fit을 묶고 motion 차단·broadcast-only·jaw 안정성을 검증한다. 관련 테스트 4/4, 기존 fit 4/4, FK 3/3 통과. GitHub CLI 로그아웃으로 이슈 API 갱신은 `NOT_RUN`; 문서/코드 commit·push는 별도 확인한다.
- `NEXT (physical protocol revision, no motion yet)`: 현재 fingertip contact의 정확한 동일 물리점 여부가 영상만으로 모호하고, 6점 기하도 충분히 맞지 않는다. 한 개의 표시된 고정 fingertip 끝을 TCP로 선택하거나 안정적인 탈착 포인터를 고정한 뒤, 다양한 손목 자세의 독립 touch·holdout을 설계한다. 새 현장 준비·승인 전 추가 로봇 구동은 하지 않는다.
- `STOPPED_SAFE (6-point teach attempt)`: 사용자가 follower 범위 밖·즉시 중단 준비·리더/팔로워 시작 자세 정렬과 기존 텔레옵의 천천히 손으로 조작하는 방식에 동의했다. LeLab `/move-arm` 1회가 HTTP 200으로 시작되고 active 및 `/ws/joint-data` 방송을 확인했다. 리더 조작 전 P1 위치/보는 웹 주소가 혼동되어 `/stop-teleoperation` 1회로 즉시 중단했고 teleoperation·recording·inference는 모두 inactive다. P1–P6 sample은 0개, fit은 `NOT_RUN`, `robot_enabled=false`. Follower torque register는 종료 후 직접 확인하지 않아 `NOT_VERIFIED`다.
- `BLOCKED_VIEW_IDENTITY`: 천장 정면 `/camera-preview/8`(LeLab `192.168.50.20:8000`)에서 P1은 화면 왼쪽 위 X이며 바로 왼쪽의 ArUco ID2 옆이다. 사용자 화면의 ambient URL `192.168.50.22:8020`은 Mac에서 health 연결이 timeout되어 동일 현장 화면인지 확인하지 못했다. 기준 화면을 맞추기 전 텔레옵 재개는 하지 않는다.
- `USER_APPROVED / BLOCKED_SAFETY (6-point teach)`: 사용자가 "6점 저속 텔레옵 teach 승인"을 명시했다. 새 정면 영상에서 중앙 약통이 치워지고 X 6개가 보였으나, 두 차례 확인 모두 사람이 follower arm 뒤쪽 가까이에 보여 사람·손의 작업 범위 이탈을 확인할 수 없다. `/move-arm` 시작 요청은 보내지 않았고 모터·토크 변화는 `NOT_RUN`이다. 리더 조작자는 follower 이동 범위 밖에 자리하고 즉시 중단 방법이 준비됐다는 현장 확인이 필요하다.
- `PASS (teach preflight read-only)`: LeLab `/health` 정상, teleoperation·recording·inference 모두 active=false. 실제 설치 OpenAPI에서 `/move-arm`이 텔레옵 시작, `/stop-teleoperation`이 중단임을 확인했다. 저장된 `so-101` record는 leader=`/dev/ttyACM1`, follower=`/dev/ttyACM0`, 두 config=`so-101.json`이다. canonical serial↔ACM 연결은 앞선 같은 날 확인한 결과를 근거로 하며 이번 점검에서 serial bus를 열지 않았다.
- `PASS (camera-only 6 X coordinates)`: 정면 MJPEG 132프레임 중 ID0–3 네 마커가 모두 검출된 82프레임에서 검은 X 6개 중심을 추출하고, 프레임별 homography로 World 좌표를 재계산했다. P1–P6의 이전값 대비 최대 점별 차이는 약 1.98 mm, 점별 RMS 시간 변동은 0.22–0.43 mm였다. 새 좌표는 별도 로컬 `configs/robot_world_pairs.20260930.closed-tip.local.json`에 보존하고 2026-09-28 원본은 변경하지 않았다.
- `PASS (post-check read-only)`: LeLab `/health`는 정상, teleoperation·recording·inference 모두 active=false였다. recording status의 `current_phase=preparing`, `session_ended=false`는 남아 있어 세션 내부 정리는 `NOT_VERIFIED`이며 재시작하지 않았다.
- `BLOCKED_APPROVAL (physical teach)`: 닫힌 fingertip TCP와 P1–P6의 follower 관절 sample 수집은 모터·토크를 수반한다. 중앙 약통 모형을 치우고 현장 안전·중단 방법을 확인한 뒤 새 명시 승인 전까지 수행하지 않는다. 현재 `T_B_W` 거부, `robot_enabled=false`는 유지한다.
- `PASS (X visibility follow-up)`: LeLab 정면 `/camera-preview/8`의 새 640×480 프레임에서 검은 X 6개가 모두 보인다. 작업대 모서리의 ArUco 4장도 화면에 보이며, 바구니는 치워져 있고 약통 모형 1개가 중앙에 남아 있다. X는 6점 robot-world teach용 임시 접촉점이지 운영 중 바구니마다 필요한 마커가 아니다. 이 1프레임 육안 점검은 ArUco ID 판독·X world 좌표 재추출·로봇 teach 완료를 뜻하지 않는다.
- `NEXT (camera-only)`: 현 배치에서 ID0–3을 판독하고 X 6개 중심의 World 좌표를 다시 추출한다. 이후 모터·토크를 수반하는 teach는 별도 현장 안전 확인과 명시 승인 전까지 `NOT_RUN`이다. teach 완료 후 X 테이프는 제거할 수 있으나 ID0–3 작업대 기준 마커는 고정 유지하고, 바구니 ID4–6은 복귀 후 검출·색상 매핑을 재확인한다.
- `PASS (connection)`: Jetson `192.168.50.20:22` SSH와 LeLab `:8000/health`가 응답했다. 실제 로그인은 `jetson3`, Jetson 시각은 2026-09-30 15:53 KST였다.
- `PASS (control preflight)`: LeLab teleoperation·recording·inference는 모두 inactive였다. 이 점검에서는 serial 장치를 열거나 모터·토크를 변경하지 않았다. Follower torque register 값은 `NOT_VERIFIED`다.
- `PASS (USB/config identity)`: Leader stable serial `5AE6085272`→`/dev/ttyACM1`, Follower `5AE6058306`→`/dev/ttyACM0`이며 실제 `so-101.json`의 leader/follower port와 일치했다. 현재 camera record는 ceiling_vertical index 8, ceiling_oblique index 4, end_effector index 6의 3대다.
- `OBSERVED (preview ownership)`: `astra-v4l2-bridge.service`는 active이며 Astra를 `/dev/video8`에 공급한다. `medicine-yolo-preview.service` 8020은 2026-09-28 20:35부터 inactive다. LeLab `/camera-preview/8`과 `/camera-preview/4`는 HTTP 200과 실제 프레임을 반환했다. 기존 서비스 소유권을 변경하지 않았다.
- `PASS (camera-only current scene)`: Astra 정면 1프레임에서 DICT_4X4_50 ID0–6을 모두 검출했다. 기존 YOLO11n ONNX는 약통 모형 3개를 confidence 0.873/0.722/0.540으로 검출했다. 이는 단일 프레임 스모크이며 일반 성능·약품 정체성 검증이 아니다.
- `PASS (basket cross-check)`: 정면의 물리 배치는 왼쪽 ID5·가운데 ID6·오른쪽 ID4다. 사선 화면에서 왼쪽 초록·가운데 파랑·오른쪽 빨강을 확인해 기존 ID4=빨강, ID5=초록, ID6=파랑 매핑이 유지됨을 교차 검증했다. 바구니의 좌우 순서는 고정 가정으로 쓰지 않는다.
- `UNVERIFIED_TEACH_LAYOUT`: 2026-09-28의 검은 X 6점은 현재 약통·바구니에 가려져 중심 위치 유지 여부를 확인할 수 없다. `robot_world_pairs.20260928.closed-tip.local.json`의 World 좌표는 재검증 전 현재 teach에 재사용하지 않는다. 현재 `T_B_W`는 계속 거부 상태이며 `robot_enabled=false`다.
- `NEXT (physical)`: 6점 teach를 재개하려면 사용자가 빈 약통·바구니를 작업대에서 치워 X 6개와 ID0–3을 정면·사선 카메라에 노출하고, 팔 지지·작업 공간·중단 방법을 현장에서 확인해야 한다. 이후 새 World 좌표부터 다시 측정한다.
- `PASS (GitHub)`: 위 읽기 전용 점검과 다음 단계 기록을 commit `c83f537`로 비공개 `origin/fix/usb-recording`에 push했다.

## 2026-09-29 GitHub 기록 재개

- `PASS (local audit)`: `CODEX_LELAB_SO101_RECOVERY.md` 787행과 `MAC_SSH_GITHUB_START.md` 170행 전체를 다시 읽고 현재 기록 기준으로 사용했다.
- `BLOCKED_NETWORK`: 사용자가 Jetson이 offline임을 확인했고 `192.168.50.20` SSH 22, LeLab 8000, preview 8020은 모두 timeout이다. 네트워크·전원·USB는 변경하지 않았다.
- `NOT_RUN`: 2026-09-29 Jetson live USB·LeLab·torque 상태 재확인과 신규 Jetson 백업은 offline으로 실행하지 못했다. 2026-09-28까지의 근거는 실시간 재확인으로 바꾸어 쓰지 않는다.
- `PASS (Git read auth)`: 비공개 remote `gyeyeongjo-lgtm/so101-lelab-medicine-sorter` BRANCH 목록을 `git ls-remote` 로 읽었다. 다만 프로젝트 로컬 GitHub CLI는 현재 로그아웃 상태다.
- `PASS (Git push)`: 진행 기록·코드·테스트·ArUco 인쇄 자산 116개 파일을 commit `a68b39f`로 저장하고 `origin/fix/usb-recording`에 push했다.
- `DOCUMENTED`: `docs/CURRENT_SYSTEM_AND_ARUCO.md`에 물리 카메라 3대(Astra 정면, RealSense 사선, Generic USB 손목), 운영 ArUco 7개(ID0–3 작업대, ID4–6 바구니), ChArUco/검은 X의 구분, 현재 fit 거부 결과와 다음 6점 teach를 정리했다.
- `SAFETY`: 오늘 로봇 모터·토크·USB·전원·캘리브레이션을 변경하지 않았다. 오프라인 중이므로 직전 테레옵의 정상 종료나 torque 0을 오늘 확인했다고 주장하지 않는다.

아래 `상태 요약`의 초기 주소·Git 상태는 2026-09-05 시점 이력이다. 현재 값은 위 최신 섹션과 후반 날짜별 기록을 우선한다.

## 상태 요약

- `OBSERVED`: Codex는 Mac 로컬 `/Users/jogyeyeong/Documents/ChatGPT/자율설계`에서 실행 중이다.
- `OBSERVED`: 작업 루트는 커밋이 아직 없는 기존 Git 저장소이며 remote가 없다.
- `OBSERVED`: 사용자 원본인 `prompt/`는 미추적 상태로 보존되어 있다.
- `OBSERVED`: `192.168.0.10:22`와 `192.168.0.10:8000`은 TCP 연결에 응답한다.
- `OBSERVED`: 실제 SSH 대상은 `jetson3@192.168.0.10:22`이다.
- `PASS`: 사용자가 ED25519 호스트 키를 확인했고, 프로젝트 전용 known-hosts 파일의 지문도 일치했다.
- `PASS`: 실제 SSH 계정 `jetson3`으로 인증했고 프로젝트 전용 소켓을 재사용 중이다.
- `PASS`: 공식 GitHub CLI v2.100.0 arm64 바이너리를 프로젝트 로컬 `.local/bin/gh`에 설치하고 배포 체크섬을 검증했다.
- `PASS`: 프로젝트 로컬 GitHub CLI가 macOS Keychain의 `gyeyeongjo-lgtm` 계정으로 인증됐고 API 호출도 통과했다.
- `PASS`: 비공개 GitHub 저장소 `gyeyeongjo-lgtm/so101-lelab-medicine-sorter`를 만들고 초기 `main` 커밋 `8dd6761`을 push했다.
- `PASS`: 후속 작업 브랜치 `fix/usb-recording`의 증거 문서 커밋 `48d788b`을 push하고 원격 SHA를 확인했다.
- `PASS`: 이슈 #1–#4를 생성하고 API에서 open 상태를 확인했다.
- `USER_REPORTED`: 기존 리더-팔로워 텔레오퍼레이션, 캘리브레이션, 웹캠, 네트워크 설정은 성공 상태였다.
- `PASS`: Jetson Phase A 환경 조사와 설정·캘리브레이션·소스·journal 백업을 완료했고 Jetson/Mac 양쪽 해시를 검증했다.
- `HISTORICAL`: Phase A 직후에는 serial `5AE6085272` 한 대만 보였고 저장된 팔로워 `5AE6058306` 및 `/dev/video*`가 일시적으로 누락됐다. 이후 물리 재연결 뒤 아래 최신 preflight를 다시 확인했다.
- `OBSERVED`: 19:32 캘리브레이션 TX/RX 오류는 동시 bus 읽기와 일치하고, 19:35 직렬화 패치 이후 두 캘리브레이션에서 재발하지 않았다.
- `PASS`: 메타데이터 전용 포트 검사와 preflight 스크립트의 오프라인 단위 테스트 3개가 통과했다.
- `FAIL`: Jetson preflight는 팔로워 serial, `/dev/video0`, `/dev/video2` 누락을 검출해 `ready=false`로 종료했다.
- `HISTORICAL`: 이 단계에서는 실제 데이터셋 녹화, 텔레옵 회귀, 모터/토크 관련 시험을 실행하지 않았다. 이후 아래 승인 시험으로 상태가 갱신됐다.
- `OBSERVED`: 21:53:19와 21:53:52 녹화 시도는 각각 torque enable id 5, follower `Present_Position` sync-read에서 실패했고 저장 episode는 0개였다.
- `PASS`: 최신 장치 preflight 7/7; 두 serial과 두 카메라가 존재하고 서로 다른 장치다.
- `PASS`: Mac에서 읽기 전용 follower 진단 도구 `scripts/diagnose_follower_bus.py`의 문법 검사와 기존 오프라인 단위 테스트 3개를 통과했다.
- `PASS`: 2026-09-06 Jetson standalone 읽기 전용 follower 시험에서 올바른 serial identity, ping 6/6, 개별 position read 30/30, group sync-read 5/5를 확인했다. ID 5도 정상이며 torque·register·USB 설정을 변경하지 않았다.
- `PASS`: 추가 20-round 읽기 전용 시험도 개별 120/120, group 20/20 성공했고 Mac backup에 hash 검증해 보존했다.
- `OBSERVED`: 11:10 텔레옵 약 62초 동안 follower 위치 read 오류 255건과 정상 joint snapshot 48건이 섞였다. 설치된 loop는 1 ms sleep으로 follower sync-write를 반복해 bus 포화 가능성이 높다.
- `PASS`: A/B 직전 캘리브레이션·robot record·설치 소스·journal 9개 파일을 Jetson과 Mac에 백업하고 SHA-256 전체 검증을 통과했다.
- `FAIL`: 카메라·video·streaming encoding을 제외한 최소 녹화도 `Devices ready` 직후 첫 follower observation에서 같은 sync-read 오류로 실패했다. saved episode 0, kernel USB event 없음.
- `PASS`: 실패 직후 standalone read 30/30·group 5/5가 다시 성공했고 시험 전후 설정 파일 hash가 동일했다.
- `PASS`: stale goal 차이는 최대 12 raw unit이었으며 torque-only 약 3초 시험에서 enable/disable, position+voltage 40/40, 12.2V 유지가 모두 통과했다.
- `PASS`: 구체적 안전 승인 뒤 configure+RX-clear+50ms 시험을 실행해 position+voltage 40/40, torque disable 성공을 확인했다.
- `FAIL`: 승인된 RX-clear patch를 Jetson에 배포하고 service를 재시작한 뒤 카메라 없는 실제 녹화를 회귀했다. patch log와 50 ms settle은 확인됐지만 첫 follower observation이 `There is no status packet`으로 즉시 실패했고 episode는 0개였다.
- `PASS`: 실패한 patch를 pre-A/B 원본으로 롤백했다. 현재 설치본과 보존 원본의 SHA-256은 모두 `779fd897...`로 같고 `lelab.service`, `/health`, 텔레옵·녹화 inactive 상태를 다시 확인했다.
- `PASS`: leader `/dev/ttyACM1` standalone 읽기 전용 시험도 serial `5AE6058306`, ping 6/6, 개별 position 120/120, group 20/20으로 통과했다.
- `PASS`: leader와 follower 포트를 동시에 열고 30 Hz로 120 rounds 교차 group read한 시험은 양쪽 모두 120/120, 오류 0건이었다. 단순 dual-open 및 양방향 read traffic은 재현 조건에서 약해졌다.
- `PASS`: patch 실패와 dual-read 결과를 Jetson/Mac 양쪽 backup에 보존하고 체크섬을 검증했다.
- `PASS`: 승인된 dual-configure 계측 전 현재 calibration·robot record·설치 소스·journal 10개를 `20260906T120356+0900_pre-dual-configure`로 Jetson/Mac 양쪽에 보존하고 hash를 검증했다.
- `NO_EFFECT`: 첫 계측 실행은 포트를 열기 전 내부 메서드명 불일치로 종료됐다. calibration/register/torque 호출은 0건이었고 service health를 복구했다.
- `PASS`: 호출별 계측 trial에서 follower configure 직후 첫 position group-read 3/3, 전체 follower→leader configure 직후 3/3이 모두 SDK `comm=0`이었다. 양쪽 teardown torque disable/disconnect도 성공했고 Goal_Position write는 0건이었다.
- `PASS`: 사전 group-read와 호출별 계측 지연을 제거한 cold full-order trial도 첫 follower read 3/3과 leader read 1/1이 모두 `comm=0`이었다.
- `PASS`: 시험 전후 follower/leader calibration과 robot record hash가 동일하고, live `record.py`는 원본 hash `779fd897...`, kernel USB event 0건, LeLab health 정상이다.
- `OBSERVED`: 동일 hardware sequence가 standalone에서는 재현되지 않아 calibration/configure 순서 자체의 결정적 결함은 약해졌다. 실제 녹화와 남은 주요 차이는 LeLab의 background `recording-worker`, 사전 dataset 생성/runtime context, 그리고 간헐성이다.
- `READY_FOR_APPROVAL`: 설치본을 건드리지 않는 `patches/lelab-20260906/record-worker-context.instrumentation.md` 계측안을 준비했다. worker thread, dataset 생성, 장치 준비 단계와 record_loop 경계만 기록하며 hardware sequence는 변경하지 않는다.
- `BLOCKED_ENV`: 승인 직후 배포 전 SSH 재확인 단계에서 실행 환경의 원격 SSH 권한/사용량 제한이 발생했다. 이번 턴에는 Jetson 설치본·서비스·하드웨어를 변경하지 않았다.
- `INFO`: 현재까지의 확정 사실·가설·배제 사항은 `docs/PROBLEM_SUMMARY_REFERENCE_2026-09-05.md`에 참고용으로 정리했다.
- `BLOCKED`: 녹화 초기화 직후 follower read 실패가 남아 있어 데이터셋 녹화를 회귀 통과로 판정할 수 없다.
- `PASS`: Draccus의 Python 3.14 parser 호환성 최소 patch 뒤 공식 `lerobot-record --help`와 실제 CLI 진입이 가능해졌다. 이 patch는 CLI parser 단계만 해결하며 TX/RX 원인을 고치지 않는다.
- `FAIL`: 승인된 공식 LeRobot CLI 무카메라 1회 비교군에서 LeLab service를 중지해 UI/worker 경쟁을 제거했는데도, episode 0 시작 뒤 follower `Present_Position` sync-read가 IDs 1–6 전체에서 3회 실패했다. SDK 원문은 `There is no status packet!`이고 episode는 완료되지 않았다.
- `OBSERVED`: 현재 물리 매핑은 follower `5AE6058306` (`/dev/ttyACM1`), leader `5AE6085272` (`/dev/ttyACM0`)이다. 역할 설정에는 각각의 `/dev/serial/by-id/...` 경로를 사용한다.
- `HYPOTHESIS`: UI/worker 동시 접근은 이번 오류의 주원인에서 제외됐다. 실제 control/torque lifecycle 뒤에만 나타나는 follower bus 전원·connector·기계적 결속/과전류·half-duplex timing의 간헐 문제를 우선 확인한다.
- `NOT_RUN`: CLI 종료 trap 뒤 LeLab service health 및 live `record.py`의 원본/계측 hash는 아직 새로 읽기 전용 확인하지 않았다. 확인 전에는 UI 녹화나 추가 hardware trial을 실행하지 않는다.
- `PASS`: 2026-09-08 현재 LeLab의 `so-101` robot record에 leader=`/dev/ttyACM1`, follower=`/dev/ttyACM0`가 저장된 것을 UI와 파일로 확인했다. 사용자가 확정한 실제 역할과 반대였다.
- `PASS`: 원본 record를 `/home/jetson3/so101-recovery-backups/20260908T163404+0900_port-map-correction/so-101.json.before`에 보존한 뒤, 포트 두 값만 leader=`...5AE6085272-if00`, follower=`...5AE6058306-if00`의 stable by-id 경로로 원자적으로 보정했다. LeLab restart와 `/health`은 통과했다.
- `FAIL`: 안전 승인된 UI Collect data 1회는 새 dataset 생성 후 follower/leader connect까지 통과했지만 `OpenCVCamera(0)` open 실패로 종료됐다. episode 0, session 0초, Hub upload 미실행. 이 trial은 record-loop/TX-RX 전 단계에서 멈췄다.
- `OBSERVED`: recording 직전 camera discovery는 `/dev/video0`–`/dev/video9`를 모두 열지 못했고 preview API도 indices 0/2에서 503이었다. 다음 단계는 camera node/점유/권한의 읽기 전용 조사다.
- `PASS`: 사용자 승인 아래 C920 두 대를 Jetson USB hub에 한 대씩 재연결했다. 현재 `/dev/video0`과 `/dev/video2`가 UVC/V4L2로 열거되며 `lerobot-find-cameras opencv`가 두 path 모두 640×480@30 FPS의 실제 test frame capture까지 통과했다. 기존 LeLab camera index 0/2와 일치한다.
- `PASS (UI summary)`: 최신 안전 승인 뒤 `Supermassive111/camera_recovery_regression_20260908_20260908_170150`로 Collect data를 1회 실행했다. 두 live feed가 표시된 상태에서 episode를 정상 종료했고 UI가 1 episode, 135 frames, 30 FPS를 보고했다. Hub upload는 명시적으로 건너뛰어 local dataset만 보존했다.
- `PENDING (read-only)`: 위 성공은 UI summary 기준이다. `meta/info.json`, parquet/video 파일, `LeRobotDataset`의 frame decode를 읽기 전용으로 확인하기 전에는 모든 frame의 offline 유효성이나 장기 안정성까지 주장하지 않는다.

## 2026-09-13 최신 갱신

- `PASS (UI)`: 새 오픈그리퍼 데이터셋 `Supermassive111/opengrip50_20260913_165317`의 Hub 업로드 완료 화면을 확인했다. Private Visualize Space의 401은 업로드 실패가 아니라 Space 접근 권한 제한이다.
- `PASS`: Mac MPS ACT 학습이 10,000 step으로 완료됐고, 최종 checkpoint의 6축 state/action 및 `312`·`camera_2` 640×480 input feature를 읽기 전용으로 확인했다.
- `PASS`: 사용자 승인으로 비공개 모델 `Supermassive111/act-so101-opengrip50-v1`을 업로드했다. 원격 private 상태와 필수 최종 모델 파일을 읽기 전용 검증했고 LeLab Import도 완료했다.
- `PASS (UI)`: 구체적 현장 안전 승인 뒤 새 모델을 30초 제한으로 1회 추론했다. UI의 RUNNING과 `Inference finished — Run completed`, 홈 Ready 복귀를 확인했다.
- `NOT_VERIFIED`: 실제 물체 집기 성공률·진동·자율 동작 품질은 현장 관찰이 필요하다. CPU rollout은 GPU 가속 복구를 의미하지 않는다.
- `NOT_PUSHED`: 작업 GitHub 저장소에 이번 세션 관련 커밋·push는 수행하지 않았다. 자세한 근거는 `docs/sessions/2026-09-13-opengripper-act-deployment.md`에 보존했다.

## 2026-09-14 데이터셋 병합·학습 준비 갱신

- `PASS`: 2026-09-14에 수집한 private 원본 네 개를 읽기 전용으로 구조 확인했다. 각 데이터셋은 동일한 6축 state/action, `312`·`camera_2` 640×480@30 FPS feature를 사용한다.
- `PASS`: episode 수는 각각 42, 14, 14, 30으로 합계 100이며, 병합본은 68,292 frames, 30 FPS, 단일 task로 검증됐다.
- `PASS`: 원본을 수정하지 않고 새 private 병합 저장소 `Supermassive111/opengrip100_20260914_merged`를 만들었다. Hub dry-run으로 metadata, parquet, 두 카메라 video를 포함한 14개 파일(약 1.3 GB)의 존재를 확인했다.
- `PASS`: 병합본의 모든 episode task를 `Pick an item from the pickup area and place it in the correct basket.`으로 통일했다. 원본 네 데이터셋은 변경하지 않았다.
- `PASS`: Mac MPS에서 병합 데이터셋 대상 ACT 학습 30,000 step을 완료했고, 최종 checkpoint `030000/pretrained_model`의 필수 model·전/후처리·학습 설정 파일을 확인했다. W&B 그래프의 원격 표시 상태는 별도 확인 전까지 `NOT_VERIFIED`다.
- `NOT_PUSHED`: 이번 데이터셋 병합·학습 준비 관련 Git 커밋과 GitHub push는 수행하지 않았다.

## 2026-09-15 ACT 30k 배포·1회 추론

- `PASS`: 사용자 승인으로 private 모델 `Supermassive111/act-so101-opengrip100-30k-v1`을 업로드했고, 원격 필수 모델 파일과 LeLab UI Import(표시명 `ACT open gripper 100 episodes 30k v1`)를 확인했다.
- `PASS (UI)`: 현재 카메라 바인딩 `312`→`#0 HD Pro Webcam C920`, `camera_2`→`#2 USB Camera`가 checkpoint의 640×480 feature와 일치함을 확인했다.
- `FAIL (UI)`: 구체적 현장 안전 승인 아래 30초 제한 ACT 추론을 정확히 1회 시작했다. UI가 policy loading 이후 `RUNNING`(00:06/00:30)까지 전환했으나, 30초 만료 전에 `Inference finished`, exit code `1`로 종료했다. 재시도·모터 설정 변경·서비스 재시작은 하지 않았다.
- `OBSERVED`: 종료 log tail에는 id 1의 `Torque_Enable=0` cleanup이 status packet을 받지 못해 6회 재시도 뒤 실패한 사실이 남았다. 사용자는 같은 1회 추론에서 follower 대신 leader arm이 움직였다고 보고했다.
- `OBSERVED`: 후속 읽기 전용 LeLab UI 확인에서 Leader (Teleoperator) port가 `/dev/ttyACM1`로 표시됐다. 기존에 확정·저장했던 leader=`...5AE6085272`(`/dev/ttyACM0`), follower=`...5AE6058306`(`/dev/ttyACM1`) 매핑과 반대이므로, 포트 역할 역전이 최우선 원인 후보다.
- `PASS (config only)`: 사용자 승인으로 LeLab 저장 포트 역할을 leader=`/dev/ttyACM0`, follower=`/dev/ttyACM1`로 보정했고 API 재조회로 두 값 모두 확인했다. 보정 전후 텔레오퍼레이션·녹화·추론은 모두 inactive였으며, 이 작업은 모터를 구동하지 않았다.
- `FAIL (UI)`: 뒤이은 1회 시험은 Calibration 화면용 포트만 보정된 상태에서 실행됐다. UI는 `RUNNING 00:31 / 00:30` 뒤 exit code `1`로 종료했고, 이후 모든 제어 작업은 inactive였다. 이 시험은 실제 `so-101` record가 아직 반대였음을 드러냈다.
- `CORRECTION`: 위 저장 포트는 Calibration 화면용 별도 값이었고, 추론이 실제 사용하는 `so-101` robot record는 여전히 leader=`/dev/ttyACM1`, follower=`/dev/ttyACM0`로 반대였다. 이것이 보정 뒤에도 leader가 움직인 직접 원인이다.
- `PASS (config only)`: 사용자 승인 범위에서 실제 `so-101` robot record의 두 port만 leader=`/dev/ttyACM0`, follower=`/dev/ttyACM1`로 patch했고 GET 재조회로 확인했다. leader/follower config와 두 camera binding은 보존했으며 모든 제어 작업은 inactive였다.
- `PASS (read-only)`: Jetson camera discovery는 C920 index 0과 USB Camera index 2를 available로 보고했고, 두 `/camera-preview` stream은 모두 HTTP 200으로 실제 MJPEG frames를 전송했다. 비녹화 상태의 UI `No preview`는 연결 실패 증거가 아니다.
- `PASS (UI)`: 별도 현장 안전 승인으로 보정된 실제 `so-101` record와 두 camera binding을 사용해 ACT 30k 추론을 30초 제한으로 1회 실행했다. UI가 `RUNNING`에서 `00:28 / 00:30`까지 진행한 뒤 `Inference finished — Run completed`, 홈 `Ready`로 복귀했다. 이후 모든 제어 상태도 inactive였다.
- `USER_REPORTED`: 위 정상 종료 run에서 follower arm은 실제로 움직였으나 물체를 잡지는 못했다. 따라서 포트 역할·기본 실행 경로는 통과했지만, 집기·분류 성능은 아직 `FAIL`이다.
- `HYPOTHESIS`: 현 단계의 2D ACT는 depth/거리 값을 직접 추정하지 않는다. 물체 시작 위치·자세·조명 편차, 그리퍼 닫힘 타이밍/시연 품질, 데이터 양이 집기 실패에 기여할 수 있다. 추가 데이터 또는 학습 step 수의 단독 변경 전에는 검증 설계를 분리한다.
- `PASS (UI)`: 별도 추가 안전 승인으로 같은 보정 포트·모델·두 카메라 조건에서 30초 제한 ACT를 1회 더 실행했다. UI는 `RUNNING 00:24 / 00:30` 및 `00:32 / 00:30`을 표시한 뒤 홈 `Ready`로 복귀했고, 종료 뒤 모든 제어 상태는 inactive였다. 실제 집기 결과는 현장 관찰이 필요하다.
- `NOT_VERIFIED`: 종료 뒤 상태 API는 완료 상태를 반환해 최초 오류를 보존하지 않았다. Jetson의 해당 inference log를 읽기 전용으로 확인하기 전까지 원인과 실제 물체 동작 성공/실패를 판정하지 않는다.
- `NOT_PUSHED`: 이번 배포·추론 관련 Git 커밋과 GitHub push는 수행하지 않았다.

## 2026-09-17 추가 ACT 30k v1 추론

- `PASS (UI)`: 별도 현장 안전 승인으로 `Supermassive111/act-so101-opengrip100-30k-v1@root`를 30초 제한으로 1회 실행했다. `312`→C920 index 0, `camera_2`→USB Camera index 2의 640×480 binding을 확인했고 UI는 `RUNNING 00:21 / 00:30`, `00:25 / 00:30`을 표시한 뒤 자동으로 설정 화면으로 복귀했다.
- `NOT_VERIFIED`: 이번 run의 실제 집기·분류 결과 및 종료 log/API 상태는 현장 관찰·읽기 전용 log 확인 전까지 판정하지 않는다.
- `NOT_PUSHED`: 이 기록에 대한 Git 커밋·push는 수행하지 않았다.

## 2026-09-17 50-episode v1 비교 추론

- `PASS (UI)`: 별도 현장 안전 승인으로 `Supermassive111/act-so101-opengrip50-v1@root`를 30초 제한으로 1회 실행했다. camera binding은 `312`→C920 index 0, `camera_2`→USB Camera index 2로 확인됐고, UI가 `RUNNING 00:21 / 00:30`, `00:26 / 00:30` 뒤 자동으로 설정 화면으로 복귀했다.
- `OBSERVED`: 시작 직전 이전 run 상태가 잠시 active로 남아 첫 요청을 차단했으나, 완료 화면을 재조회해 상태 정리 후에만 50-episode run을 시작했다. 중복 구동은 하지 않았다.
- `NOT_VERIFIED`: 실제 집기·분류 결과와 종료 log/API 상태는 현장 관찰·읽기 전용 확인이 필요하다.
- `NOT_PUSHED`: 이 기록에 대한 Git 커밋·push는 수행하지 않았다.

## 2026-09-17 ArUco 작업대 좌표계 1단계 시작

- `PASS (read-only)`: 최신 인계 주소 `192.168.0.30:8000`의 `/health`가 정상 응답했다. 새 IP가 제시한 SSH ED25519 지문은 기존 확인 지문 `SHA256:dG9hPvs6yZcfIlZ0mPofx8lUPGYwDwW1M4UDzeSfx3o`와 일치했다. 과거 문서의 `192.168.0.10`은 이전 주소로 취급한다.
- `PASS (read-only)`: Jetson의 실제 LeLab Python은 3.14.7, OpenCV는 4.13.0이며 `cv2.aruco.ArucoDetector`를 지원한다. `/dev/video0`은 `root:video`, mode `660`인 character device다.
- `PASS (read-only)`: 작업 전 LeLab health 정상, teleoperation·recording·inference 모두 inactive를 확인했다. 카메라나 serial 장치는 열지 않았다.
- `PASS (offline)`: `DICT_4X4_50`, IDs 0–3, 70 mm 인쇄용 A4 SVG와 개별 SVG/PNG를 생성했다. 합성 640×480 영상에서 네 ID, homography, 화면 중심의 작업대 좌표 변환을 확인했고 동일 영상 30-frame 안정성 계산은 약 `1.5e-13 mm`였다. 이 값은 합성 입력 검증일 뿐 실제 카메라 안정성을 뜻하지 않는다.
- `PASS (offline)`: ArUco ID parsing·config 검증을 포함해 하드웨어 없는 단위 테스트 10개가 통과했다.
- `NOT_RUN`: 실제 인쇄 크기 확인, 작업대 부착, 마커 중심 거리 실측, C920 live 검출, 실제 좌표 jitter 측정은 수행하지 않았다.
- `NOT_VERIFIED`: 카메라 내부 파라미터 calibration과 marker pose는 아직 검증하지 않았다. calibration 파일이 없으므로 현재 도구는 이를 `pose_ready=false`로 명시한다.
- `NOT_DEPLOYED`: 새 스크립트는 Jetson의 영구 경로에 배포하지 않았다. `/tmp` 합성 검증용 전송은 후속 SSH 암호 도우미 응답 중단으로 완료 여부를 확인하지 못했고, Mac의 기존 LeRobot OpenCV 4.13.0 환경에서 대신 검증했다.
- `NOT_PUSHED`: 이번 ArUco 작업에 대한 Git commit·push는 수행하지 않았다.

## 2026-09-17 ArUco Stage 1 준비

- `READY`: marker 출력 도구 `scripts/generate_aruco_markers.py`, Jetson camera-only 검출 도구 `scripts/check_aruco_workspace.py`, 출력·부착·검증 안내 `docs/ARUCO_STAGE1.md`를 준비했다.
- `SAFETY`: 이 단계의 도구는 marker 파일 생성 또는 지정 V4L2 camera read만 수행한다. 로봇 serial, torque, teleoperation, recording, inference는 열거나 실행하지 않는다.
- `BLOCKED (physical)`: marker 4장을 100% 크기로 출력하고 천장 C920 시야에 배치해야 실제 검출·camera calibration을 시작할 수 있다.
- `NOT_PUSHED`: 이 준비 작업의 Git 커밋·push는 수행하지 않았다.

## 2026-09-20 세 카메라 매핑·ArUco 실제 검출

- `PASS (read-only)`: `192.168.0.30` LeLab health 정상, teleoperation·recording·inference 모두 inactive를 확인한 뒤 camera-only 검사를 시작했다.
- `PASS`: 세 물리 카메라와 index0 node가 canonical USB 정보로 확인됐다. 천장 사선 C920 serial `27292FAF`=`/dev/video0`, 로봇팔 Generic USB=`/dev/video2`, 천장 수직 C920 serial `07FE1FAF`=`/dev/video4`다. 사용자가 실제 화면으로 세 역할을 확정했다.
- `PASS (camera-only)`: `/dev/video0` 640×480 90-frame read는 성공했지만 ArUco는 ID 2만 88/90 검출해 기준 카메라로 부적합했다.
- `PARTIAL (camera-only)`: `/dev/video4` 640×480 90-frame read에서 ID 0=90, ID 1=89, ID 2=88, ID 3=22회 검출됐다. 네 ID를 모두 찾았으나 ID 3 검출률이 약 24%라 안정성 성공 기준은 아직 통과하지 못했다.
- `PASS (UI)`: Safari에 `/camera-preview/0`, `/camera-preview/2`, `/camera-preview/4`를 별도 탭으로 열었고 각 640×480 stream을 확인했다. `/dev/video2`는 로봇 그리퍼, `/dev/video4`는 팔로워와 네 marker가 보였다.
- `SAFETY`: 위 검사는 camera read만 수행했다. robot serial, torque, teleoperation, recording, inference를 열거나 실행하지 않았다.
- `ACTIVE_RESOURCE`: 현재 Safari preview 세 탭이 카메라를 점유할 수 있다. 다음 detector·calibration·recording 전에 세 preview 탭을 닫고 release를 확인해야 한다.
- `NOT_VERIFIED`: 세 카메라 intrinsic calibration, 천장 카메라 homography/jitter, 손목 hand-eye calibration은 아직 실행하지 않았다.
- `NOT_PUSHED`: 이번 기록에 대한 Git commit·push는 수행하지 않았다.

### 2026-09-20 ArUco 실측 좌표

- `USER_MEASURED`: marker center 거리(mm)는 0–1=343, 1–2=274, 2–3=340, 3–0=277, 0–2=440, 1–3=436이다.
- `PASS (offline)`: ID 0을 원점, ID 0→1을 +X축으로 고정해 6개 거리의 최소제곱 평면 좌표를 계산했다. 좌표는 ID 0=(0,0), ID 1=(343,0), ID 2=(345.082,273.708), ID 3=(5.446,276.666) mm이며 거리 잔차 RMS는 약 0.34 mm다.
- `PASS (config only)`: 현장 config `configs/aruco_table.local.json`을 천장 수직 `/dev/video4`, 640×480@30으로 작성하고 parser 검증을 통과했다. local config는 `.gitignore` 대상이다.
- `PASS (service recovery)`: Safari preview 탭을 닫은 뒤에도 LeLab preview 1개가 카메라를 점유했다. 공식 `/camera-preview-stop`이 종료 신호만 남기고 release하지 못해, 모든 robot 작업이 inactive임을 확인한 상태에서 `lelab.service`만 재시작했다. 재시작 뒤 `/health` 정상, teleoperation·recording·inference inactive를 다시 확인했다.
- `PARTIAL (camera-only)`: 위 좌표를 적용해 `/dev/video4` 300-frame live homography 검사를 실행했다. ID 0·1·3은 계속 검출됐으나 ID 2 때문에 homography는 일부 프레임에서만 잠깐 성립했고 지속 jitter를 계산할 수 없었다. 실행 종료 코드는 `0`(한 번 이상 homography 성립)이지만 안정성 성공으로 판정하지 않는다.
- `FAIL (camera-only)`: 이어서 300 frames를 별도 집계한 결과 ID 0=300, ID 1=300, ID 2=0, ID 3=299였다. 마지막 frame에서 ID 2는 오른쪽 아래 흰 작업면 가장자리에 붙어 있어 바깥 흰 여백이 부족했다.
- `PASS (offline)`: Jetson OpenCV가 `/dev/video4` 문자열을 V4L2 camera name으로 열지 못한 사례를 반영해 두 camera-only 도구가 Linux `/dev/videoN`을 정수 index로 정규화하도록 수정했고 단위 테스트를 추가했다.
- `RELEASED`: Safari camera preview 탭을 닫았고 LeLab 재시작 뒤 detector가 카메라를 정상적으로 열어 종료 시 release했다.
- `NOT_VERIFIED`: 네 marker가 계속 보이는 조건의 homography jitter, intrinsic calibration, marker pose는 아직 검증하지 않았다.
- `PASS (camera-only, adjusted)`: 사용자가 ID 2를 안쪽으로 조정한 뒤 `/dev/video4` 300-frame 재검사에서 ID 0·1·2·3이 모두 300/300 검출됐다.
- `PASS (camera stability)`: 이어진 300-frame homography run의 모든 30-frame 주기 표본에서 네 ID와 homography가 준비됐고, 최근 30-frame 화면 중심 jitter는 약 0.20–0.22 mm RMS였다. 이 값은 이동 전 좌표 scale을 사용한 카메라 안정성 지표이며 절대 작업대 좌표 정확도 판정은 아니다.
- `STALE_CONFIG`: ID 2의 물리 위치가 바뀌었으므로 `configs/aruco_table.local.json`의 ID 2 좌표와 기존 1–2, 2–3, 0–2 실측 거리는 더 이상 유효하지 않다. 새 거리로 좌표를 다시 계산하기 전에는 로봇 목표 좌표에 사용하지 않는다.
- `USER_MEASURED (adjusted)`: ID 2 조정 후 중심 거리 1–2=260 mm, 2–3=325 mm, 0–2=424 mm를 다시 측정했다.
- `PASS (offline coordinates)`: 움직이지 않은 ID 0·1·3은 0–1=343, 3–0=277, 1–3=436 mm로 고정하고 ID 2만 최소제곱 적합했다. 새 좌표는 ID 2=(332.181,260.854), ID 3=(6.242,276.930) mm이며 ID 2 관련 세 거리의 잔차 RMS는 약 1.37 mm다.
- `PASS (config resolved)`: `configs/aruco_table.local.json`을 새 좌표로 갱신하고 parser 검증을 통과했다. stale-config 상태는 해소됐지만 intrinsic calibration 전까지 렌즈 왜곡 보정은 적용되지 않는다.
- `PASS (camera-only final)`: 새 좌표 설정으로 `/dev/video4` 300-frame homography run을 완료했다. 모든 주기 표본에서 ID 0·1·2·3과 homography가 준비됐고 종료 코드는 0이었다. 초기 안정화 뒤 최근 30-frame jitter는 약 0.04–0.11 mm RMS, 마지막 표본은 0.087 mm였다.
- `NOT_VERIFIED`: 천장 카메라 intrinsic calibration과 렌즈 왜곡 보정, 실제 로봇 기준 좌표 등록은 아직 수행하지 않았다.
- `PASS (print artifact)`: A4 세로 ChArUco 6×8 보드를 생성했다. 규격은 `DICT_4X4_50`, square 30 mm, marker 22 mm, IDs 10–33, 실제 board 180×240 mm다. 기존 작업대 ID 0–3과 충돌하지 않는다.
- `PASS (artifact verification)`: Jetson OpenCV 4.13에서 원본 marker ID 10–33을 24/24 검출했다. PDF는 A4 595.276×841.890 pt, 내장 원본 3600×4800 px, 배치 510.236×680.315 pt(180×240 mm)로 확인했고 렌더링 시 잘림·겹침이 없었다.
- `NOT_RUN (physical)`: ChArUco 실제 인쇄 크기 확인과 `/dev/video4` calibration frame 수집은 아직 수행하지 않았다.
- `PASS (user verified)`: 사용자가 A4 ChArUco 보드를 100%로 인쇄했고 체커 한 칸이 30 mm임을 실측했다.
- `PASS (camera-only live)`: 사용자가 보드를 천장 카메라 시야에 둔 상태에서 `/dev/video4` 640×480 90-frame 검사를 완료했다. captured 90/90, marker 최대 24/24·평균 23.3, ChArUco corner 최대 35/35·평균 33.567, 12 corner 이상 87/90으로 통과했다.
- `OBSERVED`: 첫 live 검사기는 OpenCV 4.13에서 제거된 `interpolateCornersCharuco`를 호출해 frame 처리 전에 종료됐다. 설치 버전의 `CharucoDetector`로 수정했고 재검사가 통과했다. 하드웨어나 설정 변경은 없었다.
- `NOT_RUN`: 다양한 위치·거리·기울기의 calibration frame 수집과 intrinsic parameter 계산은 아직 실행하지 않았다.
- `PASS (camera-only intrinsic calibration)`: 사용자 준비 확인 뒤 `/dev/video4` 640×480에서 60초간 ChArUco 자세 25개를 수집했다. 각 view는 28–35 corners를 포함했고 총 관찰 frame은 1,793개였다.
- `PASS (calibration quality)`: OpenCV `calibrateCamera` 결과 전체 reprojection RMS는 0.428 px, view별 평균 0.379 px, 최대 0.873 px였다. 계산 결과 SHA-256은 `fbdf8c83...f9c6c3`이며 `configs/c920_video4_intrinsics.local.json`에 보존했다.
- `PASS (config/code)`: `configs/aruco_table.local.json`이 위 intrinsic 파일을 참조하도록 갱신했고, `scripts/aruco_table.py`는 calibration이 있으면 frame을 undistort한 뒤 marker·homography·pose를 계산하도록 수정했다. 단위 테스트 13개가 통과했다.
- `NOT_RUN`: ChArUco 보드를 작업대에서 치운 뒤, 왜곡 보정된 ID 0–3 homography와 pose를 live 300 frames로 재검증하는 단계가 남았다.
- `NOT_VERIFIED`: intrinsic calibration은 완료됐지만 robot-base 좌표 등록과 실제 로봇 도달 정확도는 아직 검증하지 않았다.
- `PASS (camera-only undistorted workspace)`: 사용자가 ChArUco 보드를 치운 뒤 새 intrinsic을 적용한 `/dev/video4` 300-frame homography·pose 검사를 완료했다. 주기 표본에서 `pose_ready=true`였고 안정화 후 최근 30-frame jitter는 약 0.15–0.21 mm RMS, 마지막은 0.180 mm였다.
- `PASS (camera-only exact count)`: 별도 왜곡 보정 300-frame 집계에서 ID 0=300, ID 1=300, ID 2=300, ID 3=300, captured=300/300으로 통과했다.
- `PASS (ArUco stage 1)`: 천장 카메라 intrinsic, 렌즈 왜곡 보정, 네 작업대 marker 검출, pixel→table homography와 정지 안정성까지 camera-only 기준을 통과했다.
- `NOT_VERIFIED`: table 좌표와 robot-base 좌표의 등록, 약통 slot·basket 영역 확정, 실제 로봇 도달 정확도는 아직 수행하지 않았다.
- `USER_CONFIRMED (basket mapping)`: 바구니 marker는 ID 4=빨강, ID 5=초록, ID 6=파랑 순서다. ID 4–6은 바구니 추적·검증용이며 작업대 homography는 계속 ID 0–3만 사용한다.
- `FAIL (camera-only basket visibility)`: 왜곡 보정된 `/dev/video4` 300-frame 집계에서 ID 0=29, ID 1=300, ID 2=300, ID 3=300, ID 4=0, ID 5=0, ID 6=0이었다. 현재 화면에는 개별 바구니 marker 대신 ChArUco calibration board(ID 10–33)가 바구니 위에 놓여 있고, 그 배치가 작업대 ID 0도 가렸다.
- `BLOCKED (physical adjustment)`: ChArUco 보드를 작업 영역에서 완전히 치우고, 바구니별 ID 4·5·6을 천장 카메라를 향한 수평의 단단한 면에 흰 여백과 함께 노출하며, 바구니가 작업대 ID 0–3을 가리지 않도록 조정해야 한다. 조정 후 ID 0–6 exact-count 300-frame 검사를 다시 수행한다.

## 2026-09-21 천장 카메라 RealSense D435 교체

- `USER_REPORTED`: 기존 천장 수직 C920을 Intel RealSense D435로 교체했고 작업대 ArUco marker의 물리 크기는 유지했다.
- `PASS (identity/network)`: 현재 Jetson 주소는 `192.168.50.20`이다. 이 주소의 ED25519 host key가 기존 Jetson의 고정 지문과 일치했고, LeLab health 정상 및 teleoperation·recording·inference inactive를 확인했다.
- `PASS (camera identity)`: USB `8086:0b07`, serial `236223023645`의 RealSense D435가 USB 3에 연결됐다. `/dev/video0`은 Z16 depth, `/dev/video2`는 IR 계열, `/dev/video6`은 YUYV color stream이며 현재 640×480@30으로 60/60 frame read가 성공했다.
- `OBSERVED`: Jetson에는 `rs-enumerate-devices`와 `pyrealsense2`가 설치되어 있지 않다. 이번 검사는 V4L2 color stream만 사용했으며 depth↔color alignment는 아직 실행하지 않았다.
- `PASS (code/test)`: camera-only ArUco/ChArUco 도구와 table detector에서 V4L2 FOURCC를 선택할 수 있게 했고 관련 단위 테스트 12개가 통과했다. RealSense color는 `YUYV`를 사용한다.
- `FAIL (camera-only framing)`: `/dev/video6` 90-frame ArUco 검사에서 ID 3=87, ID 0·1·2·4·5·6=0이었다. 현재 영상은 작업대 일부와 marker 한 장만 온전히 포함해 좌표계나 calibration을 시작할 수 없다.
- `STALE_CALIBRATION`: 기존 `configs/c920_video4_intrinsics.local.json`은 C920 전용이므로 RealSense 영상에 사용하지 않는다. 작업대 marker가 움직이지 않았다면 table-mm 실측 좌표는 재사용할 수 있지만, 새 color intrinsic과 live homography 검증은 다시 필요하다.
- `BLOCKED (physical framing)`: RealSense 장착 위치·각도를 먼저 고정하고 ID 0–3과 바구니 영역이 모두 완전히 보이게 조정한다. 이후 30 mm ChArUco 보드로 color intrinsic을 재계산하고, 보드를 치운 뒤 ID 0–6 exact-count와 homography jitter를 재검증한다.
- `CORRECTION (three physical cameras)`: 현재 물리 카메라는 RealSense D435, Generic USB Camera, Orbbec Astra의 세 대다. 영상 확인 결과 `/dev/video4` Generic USB Camera는 엔드이펙터이고 `/dev/video6` RealSense color는 사선 천장 시야다. 따라서 `/dev/video2`와 `/dev/video6`은 서로 다른 물리 카메라가 아니라 같은 RealSense의 IR/color stream이다.
- `FAIL (basket recheck)`: RealSense color 300-frame 재검사에서 ID2=237, ID3=63, ID0·1·4·5·6=0이었다. 현재 영상에는 세 바구니와 내부 marker가 보이지만 ID4·5·6은 바구니 바닥 안쪽에 있어 사선 시야에서 테두리에 가려진다.
- `BLOCKED (Orbbec access)`: Orbbec Astra USB `2bc5:0401`은 연결되어 있으나 V4L2 node를 만들지 않는다. 설치된 Debian `libopenni2-0`과 임시 추출한 `NiViewer2`로 조회했을 때 `no devices found`였으며, LeLab `/available-cameras`에도 Astra가 없다. Orbbec 전용 OpenNI2/SDK driver 없이는 천장 정면 영상을 확인하거나 calibration할 수 없다.
- `SAFETY`: 재검사는 camera-only였다. LeLab health 정상, teleoperation·recording·inference inactive를 전후 확인했고 시스템 package 설치와 로봇 제어는 수행하지 않았다.
- `PASS (Orbbec OpenNI2 install)`: 사용자 승인으로 Orbbec 공식 `ros2_astra_camera` commit `f7e71d9c...`의 ARM64 OpenNI2 redist를 `/opt/orbbec-openni2`에 격리 설치했다. 실행 래퍼는 `/usr/local/bin/orbbec-openni-capture`, 공식 udev rule은 `/etc/udev/rules.d/99-obsensor-libusb.rules`다. 기존 Debian OpenNI2 파일은 덮어쓰지 않았다.
- `PASS (Astra streams)`: `/dev/astra`가 USB `001/011`을 가리키고, 독립 검사기는 `Astra 2bc5:0401` 한 대를 열었다. color·IR·depth sensor와 지원 mode를 열거했고 color RGB888 640×480 30/30, IR GRAY16 640×480 30/30 frame 획득 및 저장을 통과했다.
- `PASS (source verification)`: 참고용 공식 Orbbec SDK v1.10.37 ARM64 zip은 GitHub release digest `3c269b7e...`와 일치했다. 실제 설치한 OpenNI2 library SHA-256은 `d7231df0...`, Astra driver는 `b6511b00...`, non-mirrored 검사기는 `1ac5f7b9...`, udev rule은 `04bd6ef1...`이다.
- `PARTIAL (Astra ArUco view)`: 천장 정면 color frame의 SDK mirror를 끈 뒤 ID2·3은 검출됐다. ID0·1은 화면 아래에서 일부 잘렸고, 바구니 ID4·5·6은 흰 quiet zone 없이 바구니 바닥에 놓여 검출 후보로만 남아 ID 판독은 실패했다.
- `BLOCKED (physical adjustment)`: Astra 각도를 화면 아래쪽으로 조금 옮기거나 높여 ID0–3 전체를 완전히 포함하고, ID4·5·6은 각 바구니 상단의 흰 판 위에 10–20 mm 흰 여백과 함께 수평 부착해야 한다. 이후 live 300-frame exact count와 ChArUco intrinsic을 진행한다.
- `NOT_VERIFIED`: 재부팅 또는 실제 USB 재연결 후 udev 지속성, LeLab web preview 통합, Astra intrinsic/depth calibration과 table homography는 아직 검증하지 않았다.

### 천장 정면·사선 상시 웹 프리뷰

- `PASS (camera-only service)`: 천장 정면 Orbbec Astra와 천장 사선 RealSense D435 color를 한 페이지에 표시하는 MJPEG 프리뷰를 Jetson `http://192.168.50.20:8010/`에 배포했다.
- `PASS (autostart configured)`: `so101-camera-preview.service`를 systemd에 등록하고 `enabled`·`active`를 확인했다. Astra는 non-mirrored RGB888 640×480 OpenNI pipe, RealSense는 canonical by-id가 가리키는 YUYV 640×480 color stream을 사용한다.
- `PASS (live verification)`: `/health`에서 두 stream 모두 `ok=true`였고 frame count가 증가했다. Mac에서 2초간 Astra 약 2.6 MB, RealSense 약 1.9 MB의 MJPEG 데이터를 수신했으며 인앱 브라우저에서 두 실제 영상을 확인했다.
- `RESOURCE OWNERSHIP`: 이 서비스가 두 카메라를 계속 점유한다. ChArUco/ArUco 검사·녹화처럼 같은 카메라를 직접 여는 작업 전에는 `sudo systemctl stop so101-camera-preview.service`, 종료 후에는 `sudo systemctl start so101-camera-preview.service`로 복구한다.
- `SAFETY`: 설치 전후 LeLab health 정상, teleoperation·recording·inference 모두 inactive였다. robot serial, torque, motor control은 실행하지 않았다.
- `NOT_RUN`: 실제 Jetson 재부팅을 통한 자동 시작 검증과 USB 분리·재연결 복구 시험은 수행하지 않았다. systemd unit은 boot enable 상태다.
- `NOT_PUSHED`: 상시 프리뷰 코드와 기록은 Git commit·push하지 않았다.

### Astra intrinsic 완료 / RealSense 대기

- `PASS (Astra capture)`: 상시 프리뷰를 중지한 뒤 동일한 6×8 ChArUco 보드(square 30 mm, marker 22 mm)로 Astra OpenNI RGB888 640×480의 서로 다른 자세 30개를 수집했다.
- `PASS (Astra refined calibration)`: 재투영 오차가 큰 view 2개를 제외하고 28개로 재계산했다. 전체 RMS 0.478 px, view별 평균 0.450 px, 최대 0.878 px이며 결과는 `configs/astra_color_intrinsics.local.json`에 보존했다. SHA-256은 `2be8287a...8bde73`이다.
- `FAIL (workspace exact count before board capture)`: RealSense 300 frames는 ID0=267, ID1=297, ID2=0, ID3=296, ID4–6=0이었다. Astra 300 frames는 ID0=272, ID1=25, ID2=300, ID3=300, ID4=0, ID5=57, ID6=0이었다. 이 검사는 intrinsic 적용 전이며 ChArUco 보드가 중간에 시야로 들어온 조건을 포함하므로 최종 workspace 판정으로 사용하지 않는다.
- `BLOCKED (physical)`: RealSense intrinsic 수집을 위해 ChArUco 보드를 사선 카메라 화면 중앙에 전체가 보이도록 먼저 배치해야 한다. 현재 RealSense 화면에는 보드가 없다.
- `PHYSICAL FOLLOW-UP`: 최종 homography 검사 전 ID2의 강한 사선 왜곡을 줄이고, 바구니 ID4–6을 바구니 바닥이 아니라 흰 여백이 있는 상단 수평 판에 노출해야 한다.
- `PASS (resource recovery)`: 대기 중 `so101-camera-preview.service`를 다시 시작했고 두 stream의 `/health ok=true`를 확인했다. LeLab teleoperation·recording·inference는 모두 inactive다.
- `NOT_RUN`: RealSense intrinsic, 두 카메라의 intrinsic 적용 후 ID0–6 exact-count·homography jitter는 아직 수행하지 않았다.
- `NOT_PUSHED`: calibration code와 기록은 commit·push하지 않았다.

### Astra RGB-D 좌표 파이프라인 적용

- `DIRECTION CONFIRMED`: 사용자 제공 `CODEX_ASTRA_ARUCO_ROBOT_ARM_PROMPT.md`의 Camera→World→Robot Base→dry-run 방향은 기존 YOLO/ArUco/고정좌표 로드맵과 일치한다. 기존 구현을 교체하지 않고 단계별로 확장한다.
- `PHASE 1 PASS`: camera capture는 `/opt/orbbec-openni2`, RGB는 RGB888 640×480@30, ArUco는 `DICT_4X4_50`, reference ID0–3, basket ID4=red·5=green·6=blue, RGB intrinsic은 RMS 0.478 px다. ID0 검은 사각형 실측 폭은 75 mm이며 기존 좌표 단위는 mm다.
- `MISSING`: object marker ID, 3D `T_W_C`, robot-base 등록 `T_B_W`, object→grasp offset, robot workspace limits, Cartesian robot adapter는 아직 없다. 따라서 `robot_enabled=false`, dry-run만 허용한다.
- `PASS (OpenNI capability)`: Astra/OpenNI 2.3.0.85에서 RGB888와 DEPTH_1_MM 640×480@30, depth 단위 1 mm, `IMAGE_REGISTRATION_DEPTH_TO_COLOR=true`, depth-color sync=true를 확인했다.
- `PASS (300-frame RGB-D diagnostic)`: 300 frames/10.521 s(28.515 FPS), RGB-depth timestamp delta 중앙값 465.5 µs, 화면 중앙 depth 중앙값 891 mm, 전체 유효 범위 683–2414 mm, 평균 invalid 30.895%였다.
- `PASS (aligned marker depth)`: ID0=728 mm/std 0.163(300/300), ID2=901 mm/std 1.472(300/300), ID3=905 mm/std 0.244(300/300), ID4=788 mm(205 frames), ID5=781 mm(59 frames)로 11×11 ROI median depth를 얻었다.
- `PARTIAL (visibility)`: ID1은 15/300, ID6은 0/300이었다. 진단 영상 왼쪽 가장자리에 ChArUco board 일부가 남아 ID24·27·29·30·33도 검출됐다. 최종 workspace/바구니 판정 전에 보드를 완전히 치우고 ID0–6의 가림·흰 여백을 수정해야 한다.
- `RECHECK (board removed)`: 사용자 조정 뒤 Astra RGB-D 300 frames를 다시 검사했다. ID0=300, ID1=173, ID2=300, ID3=300, ID4=266, ID5=86, ID6=0 frames였고 각 검출 frame의 11×11 depth는 모두 유효했다. 중앙 depth 중앙값 889 mm, effective 28.47 FPS, RGB-depth timestamp delta 중앙값 470.5 µs였다.
- `PASS (board removal)`: 재검사 영상에는 ChArUco board와 보드 marker ID가 남아 있지 않았다.
- `BLOCKED (marker visibility)`: ID1은 화면 하단 경계와 흰 판 가장자리에 가까워 간헐 검출되고, 바구니 ID5는 반사/가림으로 불안정하며 ID6은 영상에는 들어오지만 ArUco ID로 해독되지 않는다. 기존 실측 좌표를 보존하려면 ID1 중심은 옮기지 말고 카메라 framing 또는 불투명 흰 backing을 보정한다. ID5·6은 바구니 위의 평평한 흰 판에 투명 덮개·반사 없이 다시 노출한 뒤 exact-count를 재실행한다.
- `PASS (ID1 backing)`: ID1 중심을 옮기지 않고 불투명 흰 여백을 추가한 뒤 재검사에서 ID1이 173/300에서 300/300으로 개선됐다. ID0·3도 300/300, ID2는 297/300이었다.
- `BLOCKED (basket markers)`: 같은 run에서 ID4=139/300, ID5=26/300, ID6=0/300이었다. 진단 영상상 세 marker가 투명 바구니 안쪽 바닥에 있어 플라스틱 테두리·반사 영향을 계속 받는다. ID4–6을 바구니 밖의 카메라를 향한 평평한 불투명 흰 판에 부착하고, ID6이 계속 0이면 DICT_4X4_50 ID6 70 mm를 재인쇄한다.
- `FAIL (basket adjustment recheck)`: 추가 조정 뒤 300-frame run은 ID0=180, ID1=0, ID2=287, ID3=300, ID4=0, ID5=0, ID6=0이었다. 중앙 depth 887 mm, effective 28.517 FPS, sync delta 중앙값 450 µs였다.
- `OBSERVED`: 진단 영상에서 ID4–6은 천장을 향한 수평면이 아니라 바구니 앞쪽의 기울어진 면에 있고, 아래의 반사성 회색 판이 작업대와 ID1 주변 조건을 바꿨다. 반사판을 제거하고 ID1은 직전 300/300 상태로 복원하며, ID4–6은 무광 흰색 카드 위에 완전히 평평하게 천장 방향으로 고정해야 한다.
- `PARTIAL (flat basket tags)`: 재조정 뒤 ID4=300/300, ID6=300/300으로 바구니 tag 두 개는 통과했고 ID5=261/300으로 개선됐다. depth 중앙값은 ID4=779 mm, ID5=785 mm, ID6=788 mm였다.
- `REGRESSION (reference tags)`: 같은 run에서 ID0=122/300, ID1=0/300, ID2=0/300, ID3=300/300이었다. 진단 영상에서 ID1·2 종이가 평탄하지 않거나 인쇄면/문양이 정상적으로 노출되지 않은 상태로 보인다. ID1·2를 뒤집힘 없이 인쇄면이 카메라를 향하도록 무광 흰 바탕에 완전히 평평하게 복원하고, ID0 여백도 확인해야 한다.
- `PARTIAL (latest RGB exact count)`: RGB-D diagnostic 두 번이 각각 첫 frame 뒤 OpenNI read에서 멈춰 결과에서 제외하고 안전하게 중단했다. 상시 preview의 Astra RGB 전용 경로로 300 frames/9.978 s를 별도 집계한 결과 ID0=232, ID1=0, ID2=86, ID3=300, ID4=300, ID5=128, ID6=238이었다.
- `OBSERVED (latest image)`: ID1의 오른쪽 외곽이 어두운 반사판과 이어져 흰 quiet zone이 끊기며 검출 후보조차 되지 않는다. ID2는 사각 후보로 잡히지만 dictionary decoding에 실패한다. ID1·2는 DICT_4X4_50, 70 mm로 재인쇄해 기존 중심에 맞추고 사방 무광 흰 여백을 확보하는 것이 필요하다.
- `RESOURCE RECOVERED`: 실패한 RGB-D helper 잔류가 없음을 확인했고 상시 preview를 복구했다. Astra·RealSense `ok=true`, teleoperation·recording·inference 모두 inactive였다.
- `PARTIAL (latest physical recheck)`: 상시 Astra RGB 300 frames/9.960 s에서 ID0=189, ID1=300, ID2=274, ID3=300, ID4=300, ID5=6, ID6=300이었다. ID1은 완전히 복구됐고 ID3·4·6도 통과했다.
- `REJECTED (looser detector)`: 별도 300 frames에서 기본/강화 detector를 같은 frame에 비교했다. 강화 설정은 ID0·2를 개선하지 못했고 ID5도 9→14 frames에 그쳤으며 잘못된 ID17을 1회 만들었다. false positive 위험 때문에 적용하지 않는다.
- `BLOCKED (print/flatness)`: ID0·2·5는 화면 안에 있으나 검출이 불안정하다. 세 marker를 DICT_4X4_50, 70 mm로 재인쇄해 기존 중심에 맞추고 무광 흰 바탕에 평평하게 부착한다. ID1·3·4·6은 현재 배치를 유지한다.
- `PARTIAL (latest replacement check)`: 프레임별 중복을 분리한 Astra RGB 300-frame 재검사는 ID0=294, ID1=300, ID2=35, ID3=300, ID4=0, ID5=300, ID6=299였다.
- `FAIL (duplicate basket ID)`: ID5가 한 frame에 두 번 검출된 frame이 32/300이었다. 위치 확인 결과 왼쪽 바구니 ID6과 가운데 ID5는 정상이며, 오른쪽 바구니의 ID4 예정 marker가 ID4로는 전혀 해독되지 않고 간헐적으로 ID5로 잘못 해독됐다.
- `NEXT (two markers only)`: 현재 배치에서 다시 교체할 것은 왼쪽 위 작업대 ID2와 오른쪽 바구니 ID4 두 장이다. 둘을 DICT_4X4_50, 70 mm로 정확히 재인쇄하고 기존 중심/위치에 평평하게 부착한다. 나머지 ID0·1·3·5·6은 유지한다.
- `PASS (ID2/ID4 replacement)`: 교체 후 MJPEG 300 frames에서 ID1–6은 모두 300/300, duplicate 0으로 통과했고 ID0은 289/300이었다.
- `PASS (direct raw confirmation)`: preview를 잠시 중지하고 Astra OpenNI RGB888 원본 300 frames/10.447 s를 직접 집계했다. ID1–6은 모두 300/300, duplicate 0으로 재확인됐고 ID0은 281/300이었다.
- `PARTIAL (ID0 only)`: 남은 대상은 오른쪽 아래 작업대 ID0 한 장뿐이다. 기존 중심은 유지하고 marker 오른쪽·아래까지 포함해 사방 무광 흰 여백을 더 넓힌 뒤 최종 exact-count를 실행한다.
- `IMPLEMENTED`: `scripts/orbbec_rgbd_pipe.cpp`, `scripts/astra_depth_diagnostic.py`, `configs/astra_rgbd.example.json`, `docs/ASTRA_RGBD_PIPELINE.md`를 추가했다. OpenNI 정합 실패 시 unaligned depth 출력은 차단된다.
- `IMPLEMENTED (M3 diagnostic)`: Camera XYZ, ID0–3 중심 기반 `T_C_W`/`T_W_C`, World XYZ, 재투영 RMS, 기준점 3D 잔차, depth-vs-PnP Z 차이를 camera-only diagnostic에 추가했다.
- `IMPLEMENTED (USB2 fallback)`: RGB-only와 Depth-only 640×480은 각각 연속 수집되지만 RGB+Depth 640×480이 첫 frame 뒤 정지하는 현상을 재현했다. 상시 preview는 유지하고 RGB-D 진단에만 320×240 `--low-bandwidth`와 multi-scale ArUco 검출을 추가했다.
- `PASS (updated offline tests)`: intrinsic scaling, deprojection, rigid transform, reference center parsing을 포함한 관련 테스트 21개가 통과했다.
- `NETWORK RECOVERED (2026-09-22)`: 사용자 재연결 뒤 `192.168.50.20` SSH·preview HTTP가 정상화됐다. 시작 전 LeLab health 정상과 teleoperation·recording·inference inactive를 재확인했다.
- `PASS (low-bandwidth RGB-D live)`: 320×240 smoke 30 frames와 stability 300 frames를 모두 연속 수집했다. 300 frames/10.533 s(28.482 FPS), sync delta 중앙값 33.305 ms, 중앙 depth 813 mm, 평균 invalid 32.606%였고 ID0–6 모두 검출·유효 depth 300/300이었다.
- `FAIL (M3 geometry accuracy)`: world pose 300/300에도 재투영 RMS 중앙값 2.393 px, 기준점 3D 잔차 ID0=43.82, ID1=48.06, ID2=137.00, ID3=128.16 mm였다. depth-vs-PnP Z 차이도 38.15–136.04 mm라 현재 `T_W_C`는 로봇 좌표로 사용할 수 없다.
- `DIAGNOSED`: 640↔320 marker 중심은 약 0.5배로 대응하고 OpenNI FOV focal 285.17 px도 ChArUco 축소 focal과 가까워 단순 해상도 scaling은 주원인이 아니다. IPPE 두 해, ITERATIVE, SQPNP 교체도 문제를 해결하지 못했다.
- `PHYSICAL MEASUREMENT COMPLETE`: 사용자가 ID0의 검은 ArUco 바깥 폭은 75 mm, ID5는 70 mm이며 ID0만 75 mm일 가능성이 높다고 보고했다. config는 기본 70 mm에 ID0만 75 mm override로 고쳤고 ID1–4·6은 70 mm 가정으로 명시했다.
- `PASS (reference remeasurement fit)`: 사용자 재실측 0–1=331, 1–2=275, 2–3=325, 3–0=272, 0–2=432, 1–3=434 mm를 최소제곱 적합했다. 새 중심은 ID0=(0,0), ID1=(331,0), ID2=(326.807,277.190), ID3=(-0.861,274.244) mm이며 거리 적합 RMS 2.626 mm, 최대 잔차 3.487 mm다.
- `FAIL (remeasured 3D recheck)`: 새 중심으로 30 frames를 재검사했지만 기존 intrinsic 기준 3D 잔차가 ID0=73.11, ID1=51.62, ID2=115.22, ID3=133.55 mm였다. factory FOV/영상 중심/zero-distortion 비교도 재투영 RMS는 1.941 px로 좋아졌으나 3D 잔차 64.91–106.06 mm라 채택하지 않았다.
- `REJECTED (common 75 mm assumption)`: ID0–6 모두를 75 mm로 본 이전 PnP 비교는 ID5 실측 70 mm와 모순되어 현재 판정에 사용하지 않는다. 단일 공통 pixel offset을 위쪽 약 62 px 옮기는 보정도 작업대 depth 경사를 샘플링한 결과라 계속 기각한다.
- `PASS (RGB-depth edge alignment)`: RGB Canny 경계와 depth 불연속 경계를 ±80 px에서 비교한 최적 정렬은 `(dx,dy)=(-2,-1)` px였고 matched fraction은 0.945(무이동 0.832)였다. RGB-depth 등록 자체는 거의 맞으므로 수십 pixel 정렬 오류 가설을 기각했다.
- `PHYSICAL RANGE CHECK (corrected size)`: ID5 실측 폭 70 mm를 적용한 live 30-frame 중앙값은 depth 771 mm, single-marker PnP Z 867.696 mm였다. 실제 직선거리 약 810 mm 대비 각각 −39 mm(−4.8%), +57.7 mm(+7.1%)로 둘 다 이전보다 가까워졌지만 depth가 조금 더 가깝다.
- `NOT_APPLIED (depth scale)`: 한 지점의 약식 줄자 측정만으로 810/771=1.051 보정계수를 적용하지 않는다. PnP Z와 물리 직선거리도 완전히 같은 양은 아니므로 추가 기준점 없이 보정하지 않는다.
- `IMPLEMENTED (per-ID size)`: RGB-D diagnostic과 config가 기본 70 mm 및 ID별 override를 지원하고 frame/summary에 사용 크기, single-marker PnP Z, depth 차이를 기록한다. 전체 단위 테스트 26개가 통과했다.
- `PARTIAL (live recheck visibility)`: 크기 수정 후 30 frames에서 ID1·2·4·5·6은 30/30, ID3은 1/30, ID0은 0/30이었다. 기준 ID 네 개가 동시에 없어 world pose는 0/30이므로 3D 좌표 정확도는 재판정하지 않았다.
- `PASS (visibility retry)`: 사용자 조정 후 30-frame smoke와 300-frame stability를 다시 실행했다. 최종 300 frames에서 ID0–6 모두 검출·유효 depth 300/300, world pose 300/300, 27.628 FPS, sync delta 중앙값 12.754 ms로 가시성과 수집 안정성은 통과했다.
- `FAIL (3D accuracy retry)`: marker별 크기를 적용해도 300-frame world reprojection RMS 중앙값 2.367 px, 기준점 3D 잔차는 ID0=75.47, ID1=52.71, ID2=115.50, ID3=135.52 mm였다. 이 `T_W_C`는 로봇 좌표로 사용할 수 없다.
- `OBSERVED (single-marker ranges)`: 300-frame depth/PnP Z 중앙값은 ID0 716/811.27, ID1 728/825.73, ID2 910/1085.09, ID3 896/964.14, ID4 762/843.86, ID5 769/867.70, ID6 776/901.66 mm였다. 위치별 차이가 일정하지 않아 공통 scale 하나를 적용하지 않는다.
- `IMPLEMENTED (depth 3D fit)`: ID0–3의 registered-depth Camera XYZ와 실측 world 중심을 no-scale Kabsch 강체변환으로 맞추고, 기준점 평면성·여섯 상호거리·fit 잔차를 frame/summary에 기록한다. 전체 camera-only 단위 테스트 28개가 통과했다.
- `PASS (depth plane stability)`: 300 frames 모두 depth 기반 pose가 계산됐고 기준점 plane RMS 중앙값은 1.994 mm였다. 네 기준점은 안정적인 한 평면으로 관측된다.
- `FAIL (depth metric geometry)`: depth 기반 강체변환 RMS는 33.949 mm, 기준점별 잔차는 ID0=33.23, ID1=35.91, ID2=28.69, ID3=37.36 mm였다. 여섯 Camera XYZ 거리는 fitted world 거리보다 모두 36.87–71.36 mm 길었다.
- `REJECTED (empirical similarity scale)`: 진단용 similarity fit은 Camera/world scale 1.151915(역수 0.868119), RMS 9.387 mm였지만 물리적 calibration 근거가 없는 배율이므로 config에 적용하지 않았다.
- `DIRECTION (2.5D)`: 고정 작업대의 XY는 검증된 ArUco homography를 사용하고, Z는 depth 평면 대비 상대 높이로 구하는 2.5D 경로가 현재 full metric Camera XYZ보다 적합하다. robot-base 등록과 실제 이동은 계속 차단한다.
- `IMPLEMENTED (2.5D dry-run)`: 매 frame ID0–3 중심 homography로 pixel→table XY를 계산하고, registered-depth 기준점 plane의 카메라 방향 signed distance로 table 대비 높이를 계산한다. frame/JSONL/summary와 진단 overlay에 기록한다.
- `PASS (2.5D 300 frames)`: ID0–6, homography, depth plane 모두 300/300이었다. 기준점 높이는 약 ±1.51 mm 이내, 바구니 ID4·5·6 높이는 56.765·56.217·54.556 mm였다.
- `PASS (2.5D stability)`: 바구니 marker XY 표준편차는 축별 최대 0.358 mm, 높이 표준편차는 최대 0.624 mm였다. homography reference XY가 거의 0 오차인 것은 네 기준점을 그대로 맞춘 정의상 결과이므로 독립 정확도 증거로 과장하지 않는다.
- `PASS (camera-only deploy)`: 기존 `/opt/so101-rgbd/astra_depth_diagnostic.py`를 사용자 홈 recovery backup에 보존하고 검증된 2.5D dry-run 도구와 example config를 `/opt/so101-rgbd/`에 배포했다. script/config SHA-256은 각각 `2be2c650...804d1`, `306fcfa3...b4dc`다.
- `OBSERVED (deploy verification)`: 설치 경로 직접 bytecode compile은 root 소유 `__pycache__` write 때문에 최초 permission denied였고, `/tmp` pycache를 지정한 재검증은 통과했다. `--help` 실행과 설치 hash 일치도 통과했다.
- `SAFETY (2.5D)`: 도구는 자동 실행되지 않으며 camera-only dry-run이다. robot target 승인·`T_B_W`·motion command는 추가하지 않았다. 종료 후 preview 두 stream 정상, 모든 LeLab 제어 inactive, helper 잔류 없음이다.
- `PASS (medicine foreground bootstrap)`: 사용자가 pickup 구역에 빈 약통/모형 한 개를 배치한 뒤 RGB-D snapshot 30 frames에서 ID0–6, homography, depth plane이 모두 30/30이었고 plane RMS는 1.514 mm였다.
- `PASS (pickup ROI proposal)`: depth-plane 대비 15–180 mm foreground를 분리하고, 작업대 ROI X=80–220 mm/Y=200–300 mm를 적용하자 현재 약통 후보 C11만 선택됐다. 중심은 pixel=(178.943,123.679), table=(140.254,242.293) mm, 높이 중앙값/최대값=42.240/58.379 mm였다.
- `IMPLEMENTED (camera-only candidate tool)`: `scripts/depth_foreground_candidates.py`와 ROI config를 추가해 `/opt/so101-rgbd/`에 배포했다. 설치 script/config SHA-256은 각각 `e3c94e47...8dd95`, `d9027af4...a0fd`다. 기존 config는 `astra_rgbd.example.json.pre-pickup-roi-20260922`로 보존했다.
- `LIMIT`: 현재 결과는 단일 위치·단일 snapshot의 foreground proposal이다. YOLO 약통 분류, 약품 식별, grasp pose, robot-base 좌표, 실제 집기 성공을 검증하지 않았다. 로봇 명령으로 사용하지 않는다.
- `BLOCKED (pose 2 occlusion)`: 약통을 세운 채 두 번째 위치로 옮긴 30-frame capture는 ID0=29, ID1=30, ID2=30, ID3=0, ID4–6=30이었다. 약통이 기존 ID3 중심 `(227.75,114.5)` px에 겹쳐 reference homography가 0/30이었고 후보 선택은 의도대로 실패 폐쇄됐다. ID3 전체가 보이도록 약통을 프리뷰 기준 왼쪽으로 조금 옮긴 뒤 재수집해야 한다.
- `PASS (pose 2 retry)`: 약통만 조정한 재수집에서 ID0–6, homography, depth pose가 모두 30/30이었다. ROI가 선택한 C5는 pixel `(198.679,111.109)`, table `(81.956,286.512)` mm, 높이 중앙값/최대값 `94.752/97.453` mm였고 RGB overlay에서 실제 흰색 약통과 일치했다.
- `OBSERVED (pose diversity)`: 첫 위치 대비 table XY 이동량은 약 73.2 mm로 사용자 이동 지시와 일치했다. 첫 위치 높이 42.240 mm는 그리퍼 아래에서 약통 일부만 component로 분리된 값이고, 두 번째 위치는 약통 전체 윤곽이 분리되어 94.752 mm로 커졌다. 높이 일관성 기준에는 첫 자세를 사용하지 않는다.
- `PASS (pose 3)`: 세 번째 위치에서 ID0–6, homography, depth pose가 모두 30/30이었다. 선택 C4는 pixel `(168.506,121.397)`, table `(169.861,250.251)` mm, 높이 중앙값/최대값 `95.932/98.958` mm였고 overlay에서 실제 약통 전체와 일치했다. 두 번째 자세 높이와의 차이는 1.180 mm다.
- `IMPLEMENTED (YOLO bootstrap export)`: 리뷰를 통과한 pose 2/3만 Jetson의 비 Git 경로 `/home/jetson3/so101-medicine-bootstrap/`에 image, class-0 YOLO pseudo-label, JSON metadata로 내보냈다. 실패/부분 가림 pose는 제외했다. export label은 `review_required=true`이며 학습 준비 완료를 뜻하지 않는다.
- `PASS (export tool deploy)`: margin·clip을 포함한 YOLO bbox 변환과 export 옵션을 camera-only 후보 도구에 추가했다. 관련 로컬 검사 19개가 통과했고 설치 script SHA-256은 `4c683acb...0abe`다. 기존 도구는 `/opt/so101-rgbd/depth_foreground_candidates.py.pre-yolo-export-20260922`로 보존했다.
- `PASS (2026-09-23 immediate repeatability)`: 현재 정지 자세를 연속 재촬영한 두 결과는 table XY 차이 0.933 mm, pixel 중심 차이 0.154 px, 높이 차이 0.849 mm였다. 두 번째 run은 ID0–6/homography/depth pose 30/30, plane RMS 1.230 mm였다.
- `OBSERVED (overnight movement)`: 전날 pose 3와 첫 재촬영의 XY는 19.368 mm 달랐지만 reference ID0–3 pixel 이동은 최대 1.275 px였다. 카메라 좌표계 붕괴가 아니라 사이에 약통이 조금 이동한 것으로 판정한다.
- `SKIPPED (near duplicate)`: 즉시 반복 표본은 안정성 확인에만 사용하고 학습 데이터에는 추가하지 않았다. 위치 다양성 확보 전 거의 같은 frame을 늘리지 않는다.
- `BLOCKED (pose 4 outside ROI)`: 네 번째 배치의 실제 약통 후보 C4는 table `(232.956,240.492)` mm, 높이 94.707 mm로 보였지만 pickup ROI X 최대 220 mm를 12.956 mm 벗어났다. 바구니 ID6에도 가까워 자동 선택과 YOLO export가 안전하게 생략됐다. ROI를 임의로 넓히지 않고 약통만 프리뷰 기준 오른쪽·위쪽으로 조금 조정한다.
- `BLOCKED (pose 4 retry partial selection)`: 조정 뒤 약통 전체 C4는 table `(198.975,315.094)` mm로 ROI Y 최대 300 mm를 벗어났고, ROI 안의 작은 하단 조각 C5 `(6×7 px, area 35, height 43.765 mm)`가 선택되는 약점을 발견했다. 해당 표본은 저장하지 않았다.
- `IMPLEMENTED (whole-object fail-closed gate)`: bootstrap 선택에 area 100–500 px, median height 70–120 mm 조건을 추가했다. 같은 실패 snapshot은 `selected=null`, 기존 정상 pose 2/3은 그대로 선택됐다. 로컬 회귀검사 21개 통과 후 Jetson에 배포했다.
- `PASS (filter deploy)`: 설치 script/config SHA-256은 `af39ecc4...e189`, `ce43a0d0...d9e1`이다. 이전 설치본은 `.pre-whole-object-filter-20260923` suffix로 보존했다.
- `PASS (pose 4 final)`: 약통 전체 후보 C3가 bbox `15×15 px`, table `(204.641,263.851)` mm, 높이 중앙값/최대값 `95.672/99.035` mm로 강화 필터를 통과했다. 기존 pose 2/3과의 XY 거리는 124.760/37.344 mm이며 overlay에서 실제 약통 전체와 일치했다.
- `PASS (third positive export)`: `pose_004` image, class-0 YOLO pseudo-label, JSON metadata를 비 Git bootstrap 경로에 저장했다. label은 `0 0.48906250 0.48958333 0.05937500 0.07916667`이다. 현재 검토 통과 positive는 pose 002–004 세 건이다.
- `PASS (empty ROI negative)`: 약통을 치운 RGB-D에서 `selected=null`이었다. ROI 경계의 작은 바구니 조각 C8은 area 18 px/height 56.401 mm라 whole-object filter가 거부했다. 시각 확인 후 `empty_001` image, 0-byte label, JSON metadata로 저장했다.
- `PASS (bootstrap audit)`: images/labels/metadata stem이 모두 일치했고 normalized label 범위가 유효했다. 현재 총 4표본(positive 3, negative 1)이며 Git에는 넣지 않았다.
- `COLLECTION TARGET`: 현재 수동 1단계는 positive 8 + negative 2를 목표로 한다. 이후에는 반복 확인을 줄이는 자동 수집 흐름으로 50–100개의 서로 다른 실제 frame을 준비한다. 수동으로 수십 번 확인시키지 않는다.
- `BLOCKED (pose 5 outside ROI)`: 실제 약통 전체 C3은 bbox `15×13 px`, table `(73.479,263.292)` mm, 높이 95.914 mm였으나 ROI X 최소 80 mm보다 6.521 mm 밖이었다. ID3에 가까워 ROI를 넓히지 않고 약통을 프리뷰 기준 왼쪽으로 조금 옮긴다. 표본은 저장하지 않았다.
- `PASS (pose 5 retry)`: C4가 bbox `16×13 px`, table `(111.516,252.533)` mm, 높이 중앙값/최대값 `95.539/98.630` mm로 통과했고 overlay에서 실제 약통 전체와 일치했다. 기존 pose 002–004와의 최소 XY 거리는 45.037 mm다.
- `PASS (fourth positive export)`: `pose_005` image/label/metadata를 저장했다. label은 `0 0.58750000 0.50208333 0.06250000 0.07083333`이며 pair audit 후 현재 총 5표본(positive 4, negative 1)이다.
- `PASS (hard negative 002)`: 약통 없이 비원통형 물체가 있는 영상에서 `selected=null`이고 ROI 내 15 mm 이상 후보도 없었다. 시각 확인 후 빈 label로 저장해 현재 총 6표본(positive 4, negative 2)이다.
- `SCOPE LOCKED`: 현재 class 0은 연구용 흰 원통형 약통 모형 `white_medicine_bottle_model`이다. 약 상자·펜 등 비원통형 물체는 negative이며, 실제 약품 신원이나 모든 약품 용기를 뜻하지 않는다. `configs/medicine_bootstrap.example.json`에 기록했다.
- `BLOCKED (pose 6 outside ROI)`: 방향을 바꾼 실제 약통 전체 C3은 bbox `14×25 px`, table `(242.674,296.894)` mm, 높이 93.204 mm였으나 ROI X 최대 220 mm를 22.674 mm 벗어났다. overlay에서 방향 다양성은 유효하지만 저장은 차단했다.
- `PASS (pose 6 retry)`: 조정 뒤 C3가 bbox `16×14 px`, table `(209.179,284.667)` mm, 높이 중앙값/최대값 `95.930/97.959` mm로 통과했다. 기존 표본과 최소 XY 거리는 21.305 mm이고 overlay에서 실제 약통 전체와 일치했다.
- `PASS (fifth positive export)`: `pose_006` image/label/metadata를 저장했다. label은 `0 0.48125000 0.46250000 0.06250000 0.07500000`이며 현재 총 7표본(positive 5, negative 2)이다.
- `BLOCKED (pose 7 outside ROI)`: C3은 bbox `16×27 px`, table `(59.110,259.918)` mm, 높이 94.439 mm로 실제 약통 전체였지만 ROI X 최소 80 mm를 20.890 mm 벗어났다. overlay에서 ID3 quiet zone에도 너무 가까워 저장을 차단했다.
- `BLOCKED (pose 7 retry merged)`: 왼쪽 조정 후 약통이 로봇 그리퍼 바로 아래로 들어가 robot component C0 bbox `30×95 px`에 연결됐다. 독립 whole-object 후보가 없어 `selected=null`로 저장을 차단했다.
- `BLOCKED (pose 7 retry 2 merged)`: 오른쪽 조정 후에도 약통 상단과 그리퍼 하단이 맞닿아 C0 bbox `40×93 px`로 연결됐다. 오른쪽에는 ID3이 있어 수평 이동만으로 여유가 부족하므로 약통을 대각선 아래·왼쪽의 기존 검증 공간으로 옮긴다.
- `PASS (pose 7 final)`: C3가 bbox `15×24 px`, table `(108.202,259.417)` mm, 높이 중앙값/최대값 `95.572/99.788` mm로 독립 검출됐다. pose 005와 XY는 7.640 mm로 가깝지만 bbox가 `16×13`에서 `15×24`로 달라 방향 변화가 영상에 반영됐다.
- `PASS (sixth positive export)`: `pose_007` image/label/metadata를 저장했다. label은 `0 0.59531250 0.50416667 0.05937500 0.11666667`이며 현재 총 8표본(positive 6, negative 2)이다.
- `PASS (pose 8 rotation)`: 같은 위치에서 수직축 기준 약 90° 회전한 약통 전체 C3가 bbox `16×14 px`, table `(105.678,272.885)` mm, 높이 중앙값/최대값 `96.537/98.685` mm로 선택됐다. pose 007과 XY 차이는 13.702 mm, bbox는 `15×24 → 16×14 px`로 달라졌다.
- `PASS (seventh positive export)`: `pose_008` image/label/metadata를 저장했다. label은 `0 0.59687500 0.47916667 0.06250000 0.07500000`이며 파일 stem 검사 후 총 9표본(positive 7, negative 2)이다.
- `BLOCKED (Astra preview after pose 8)`: 마지막 30-frame RGB-D 수집과 ID0–6/homography/depth pose 30/30은 통과했지만, 15:05 프리뷰 재시작 직후 Astra OpenNI color stream 시작이 실패했다. 이후 USB device open의 control request 실패가 반복되고 `/health`는 Astra `ok=false`, RealSense `ok=true`로 503이다. 단독 preview service 재시작으로 복구되지 않았다.
- `DIAGNOSIS (USB state)`: `lsusb`에는 Astra `2bc5:0401`이 bus 001 device 006으로 남아 있지만 OpenNI가 열지 못한다. LeLab teleoperation·recording·inference는 inactive다. 원인 확정 전 USB 재연결·reset·전원 조작은 실행하지 않았다.
- `NOT_RUN (pose 9)`: positive 목표 마지막 1건은 Astra RGB-D 복구 전까지 촬영하지 않는다. `NOT_PUSHED`: 이번 코드·문서는 commit/push하지 않았다.
- `PASS (Astra USB reconnect recovery)`: 사용자가 Astra USB를 현장 재연결한 뒤 2026-09-23 15:35–15:36 KST 프리뷰 health가 HTTP 200으로 회복됐고 Astra·RealSense 모두 `ok=true`, frame count 증가를 확인했다. LeLab health 정상, teleoperation·recording·inference inactive, 별도 RGB-D helper 잔류 없음이다.
- `PENDING (pose 009 physical placement)`: 기존 dataset은 positive 7, negative 2이고 pose 009는 없다. 약통만 다른 비가림 위치로 옮기는 사용자 조치를 요청했다. 새 RGB-D 수집·export는 아직 `NOT_RUN`이다.
- `PASS (pose 009 camera capture)`: 사용자 이동 뒤 검증된 low-bandwidth helper로 RGB-D 30 frames를 수집했다. ID0–6/homography/depth pose 30/30, plane RMS 중앙값 1.266 mm였다. 일회성 추가 ID38이 있어 exact-count 통과로 보지 않는다.
- `FIXED (foreground XYZ)`: 첫 후보 추출에서 depth Z=788 mm가 계산식 안에서 33.409 mm로 변해 약통 높이가 678.8 mm로 오판된 것을 확인했다. 독립 출력 배열로 XYZ를 구성하도록 수정했고 Jetson 단위 테스트 8/8, 동일 snapshot C3 높이 95.307 mm 선택을 통과했다. 기존 설치본은 backup 후 SHA `382679e6...` 수정본으로 교체·검증했다.
- `NOT_SAVED (pose 009)`: 현재 위치는 pose 006과 3.107 mm 차이로 거의 중복이다. 깊이 후보 C3는 약통 상단만 감싸고 하단 C6과 분리됐으며, 화면 왼쪽에 미확인 흰 원통형 물체도 있다. 수동 검토 박스는 임시로 확인했지만 dataset export하지 않았다. 기존 positive 7/negative 2 유지다.
- `PENDING (physical rotation)`: 왼쪽 흰 물체를 화면 밖으로 치우고 중앙 약통만 수직축 기준 약 90° 회전하도록 요청했다. 완료 후 새 frame에서 단일 클래스 물체, 독립된 whole-object bbox, 방향 다양성을 확인한다.
- `PASS (pose 009 final)`: 사용자 회전/물체 제거 후 Astra RGB-D 30 frames에서 ID0–6/homography/depth pose 모두 30/30, 추가 ID 없음, plane RMS 중앙값 1.740 mm였다. 선택 C3 table `(212.800,282.508)` mm, 높이 95.160 mm다. 깊이상 분리된 약통 하단까지 RGB 검토 bbox `(146,105,16,25)`로 포함해 `pose_009`를 저장했고 image/label/metadata pair audit는 총 10건(positive 8, negative 2)을 통과했다.
- `PASS (positive bbox review)`: 접촉시트에서 기존 양성 6건의 하단 누락/여유 부족을 확인했다. 원본 label·metadata를 Jetson 비 Git `review-backups/20260923_whole_bottle_bbox_review_v1/`에 보존하고 전체 약통 bbox로 수정했다. 수정안 접촉시트, 10쌍 구조/값 검사, label review history 보존을 확인했다. 새 review script 단위 테스트 2/2 통과다.
- `LIMIT (full-frame negatives)`: `empty_001`·`hardneg_002`의 원본 전체 화면에는 ROI 밖에 대상 약통이 남아 있어 빈 label로 full-frame YOLO를 학습할 수 없다. 원본은 변경하지 않았다.
- `PASS (ROI-only derivative)`: 고정 pixel crop `[128,85,215,140]`의 87×55 ROI 파생본을 Jetson 비 Git `so101-medicine-bootstrap/roi-v1/`에 10쌍 생성했다. positive 8 box가 모두 crop 안에 있고 negative 2 crop에는 대상 약통이 없음을 시각 확인했다. 변환 단위 테스트 3/3과 pair audit가 통과했다.
- `NOT_TRAINING_READY`: 10장의 작은 ROI bootstrap은 실제 YOLO 학습/성능 검증에 충분하지 않다. 파생본 `training_ready=false`; 다음은 물리적으로 다양한 실제 frame 50–100개와 독립 평가 표본 수집이다.
- `BLOCKED_AUTH (GitHub issue sync)`: 비공개 저장소 이슈 #4 조회를 시도했지만 현재 Mac의 GitHub CLI 인증이 없어 로그인 안내로 종료됐다. 이슈 본문/댓글은 변경하지 않았다. 이번 코드·문서는 `NOT_PUSHED`다.
- `NOT_DEPLOYED (latest M3 changes)`: 수집 안정성은 통과했지만 3D 정확도가 실패했으므로 최신 helper/diagnostic은 Jetson 설치 경로에 배포하지 않았다.
- `PASS (preview ownership recovery)`: 별도 SSH session에서 수동 실행된 preview 인스턴스가 systemd와 충돌하던 상태를 정리했다. systemd service stop 시 server/helper가 모두 종료됨을 확인한 뒤 단독 재시작했고 Astra·RealSense `ok=true`다.
- `PASS (previous M2 deploy)`: 이전 M2 버전은 관련 테스트 17개 통과 뒤 Jetson의 `/opt/orbbec-openni2/bin/orbbec-rgbd-pipe`와 `/opt/so101-rgbd/astra_depth_diagnostic.py`에 설치했었다. 위 최신 M3 변경과는 구분한다.
- `SAFETY`: 최신 작업에서도 카메라만 열었고 robot serial, torque, teleoperation, recording, inference, motor command는 실행하지 않았다. 종료 전 세 제어 상태를 다시 확인한다.
- `NOT_VERIFIED`: ID1–4·6 marker 폭(현재 70 mm 가정), 두 번째 camera-to-marker 실측 거리, 정확한 depth Camera XYZ/multi-marker `T_W_C`, `T_B_W`, 실제 로봇 이동.
- `NOT_PUSHED`: 이번 통합 코드와 문서는 commit·push하지 않았다.

## SSH 호스트 키 후보

2026-09-05에 `192.168.0.10`이 제시한 지문이다. 사용자가 ED25519 지문을 확인했고 프로젝트 전용 known-hosts 파일에 고정했다.

- RSA: `SHA256:E8sPqGMqQByy2SlJTg1RBxe3rWTp7yQfdDg7wKpJDyM`
- ECDSA: `SHA256:IBpxmbAkhxgYKSGgcTwLkb1yp6j4siHHUhWT3w6b8Lo`
- ED25519: `SHA256:dG9hPvs6yZcfIlZ0mPofx8lUPGYwDwW1M4UDzeSfx3o`

## 원본 지시서 무결성

- `CODEX_LELAB_SO101_RECOVERY.md`: `603ea8a57a21b28a019149b8f6ff25d407e1b5fe4e25dfe85e8c8d454362fb6f`
- `MAC_SSH_GITHUB_START.md`: `1827fc1b3484e9888ae81dbf398983b468c7b0583fb48614c6318a225f4e30cd`

## 다음 실행 한 단계

MD Phase 6의 다음 유효 단계는 검증 가능한 TCP를 먼저 정의한 뒤, 작업영역 전체에 분산된
World 기준점 4–8개에 TCP를 teach하는 것이다. 관절값은 8010의 읽기 전용 모니터가
LeLab `/ws/joint-data` broadcast에서 받아야 하며 `/joint-positions` REST endpoint는 사용하지
않는다. 각 sample에 known World point와 검증된 TCP offset이 함께 있을 때만 `T_B_W` fit에
포함한다. fit 후에도 Phase 7 Robot Base 좌표 overlay/dry-run을 먼저 수행하고 실제 이동은 차단한다.
YOLO 데이터 경로에서는 현재 통합 후보와 섞이지 않는 별도 촬영 세션의 평가 양성/음성을
먼저 확보한다. 같은 장면의 무작위 frame 분할은 독립 평가로 간주하지 않는다.

### 2026-09-23 프리뷰 기반 자동 후보 수집 smoke

- `PASS (camera-only)`: 기존 Astra 프리뷰를 읽는 ROI 검토 대기 수집기를 구현해 Mac 단위 테스트 4/4와 Jetson 20초 smoke를 통과했다. 로봇 또는 카메라 직접 점유 없음.
- `PASS (fail-closed)`: 검토 frame 38개에서 ID0–3 누락 10개를 버리고 정지 중복 11개를 버렸다. 독립성을 확인하지 않은 후보 1장만 비 Git review queue에 저장했으며 YOLO label·학습 데이터에는 추가하지 않았다.
- `PARTIAL (ID2 visibility)`: Astra MJPEG에서 ID2는 3배 확대 검사 시 30 frame 중 22 frame만 검출됐다. 기준 marker 중심과 카메라는 고정하고 ID2 주변 흰 여백/가림/반사를 개선할 필요가 있다.
- `PASS (end state)`: 천장 정면·사선 프리뷰 모두 정상이고 LeLab teleoperation·recording·inference 모두 inactive. 로봇·USB·토크·전원 조작 없음.
- `NEXT (physical)`: ID2 가시성을 개선하고 약통만 ROI 내 여러 새 위치/회전으로 묶어 바꾼 뒤 수집한다. 사람 검토 없는 자동 label/학습 또는 로봇 이동은 하지 않는다. 이슈 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.
- `PASS (2-minute candidate run)`: 사용자 준비 확인 후 기존 프리뷰를 읽는 수집기를 120초 실행했다. decoded 3606/검사 228 frame 중 marker 누락 70, 불안정 99, 중복 47을 거르고 ROI/context 후보 4장만 비 Git review queue에 저장했다. 네 장의 ROI에 흰 약통이 보이는 것을 시각 확인했으나 whole-object bbox·기존 bootstrap과의 독립성은 미검증이므로 아직 학습 수에 포함하지 않는다.
- `PASS (post-run safety)`: Astra·RealSense 프리뷰 모두 `ok=true`, LeLab 세 제어 inactive. 로봇·토크·전원·USB 조작 없음. GitHub issue 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.
- `PASS (second candidate run)`: 사용자와 함께 180초 추가 수집해 검토 대기 후보 10장을 별도 비 Git queue에 저장했다. 검사 342회에서 기준 marker 누락 147회, marker shift 초과 0회였다.
- `REJECTED (ROI clipping)`: 추가 run의 candidate_001·005·007·008은 약통이 crop 경계에 잘려 전체 약통 positive로 사용할 수 없다. 나머지 6장과 첫 run 4장은 bbox·중복 검토 전이므로 학습 표본으로 **확정하지 않았다**. 두 run 총 14장 중 적어도 4장 제외; 학습 및 로봇 동작 `NOT_RUN`.
- `PASS (high-resolution candidate capture)`: 기존 수집기 파일을 보존하고 v2를 Jetson 사용자 홈에서 camera-only 검증했다. 정지 장면 12초 smoke의 후보 1장에 대해 기존 87×55 ROI/320×240 context와 174×110 ROI/640×480 context가 모두 저장됐고 shape·stem·manifest를 확인했다. smoke 장면은 학습 수에 추가하지 않는다.
- `PENDING (diverse frames)`: 이전 14장은 87×55 원본으로만 저장돼 해상도 복원이 불가능하다. 위치가 기존 8개 또는 서로 가까운 후보가 있어 독립 표본 수는 아직 미확정이다. 새 수집은 사람이 약통 배치를 바꾸는 동안만 의미가 있으며, 50–100개 실제 변화와 독립 평가 분할 전 `training_ready=false`다.
- `PASS (post-v2 safety)`: 두 프리뷰 `ok=true`, LeLab 세 제어 inactive. 로봇·USB·토크·전원 조작 없음. GitHub issue 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.
- `PASS (5-minute high-resolution capture)`: 사용자 시작 확인 후 카메라-only v2를 300초 실행했다. 9014 decoded/573 검사 frame에서 31개 검토 대기 후보를 저장했고 각 후보의 174×110 ROI 및 640×480 context 쌍을 보존했다. 기준 marker shift 초과 0회, 기준 ID 누락 182회는 fail-closed로 버렸다.
- `PASS (conservative ROI screen)`: 새 비파괴 감사 도구와 단위 테스트 3/3을 통과했다. 31장 중 몸통이 ROI 경계에 닿는 13장, 보라색 몸통 확인이 안 되는 3장을 분리했고 15장을 `needs_human_review`로 남겼다. 가까운 위치의 후보 쌍도 있어 독립 학습 표본 수는 미확정이며 새 YOLO label·평가 분할·학습은 `NOT_RUN`이다.
- `PASS (post-capture safety)`: Astra·RealSense 프리뷰 모두 `ok=true`, LeLab teleoperation·recording·inference 모두 inactive. 로봇·토크·USB·전원 조작 없음. GitHub issue 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.
- `PASS (bbox proposals only)`: 감사 통과 15장에 빨간 약통 전체 박스 overlay와 제안 JSON을 비 Git queue에 생성했다. 접촉시트 육안 확인에서 004·012는 그리퍼가 뚜껑에 닿아 보이고 근접 위치 후보 쌍도 있어 사용자 검토가 필요하다. 새 YOLO label 0개, `training_ready=false`, 학습 `NOT_RUN`.
- `PASS (provisional ROI export)`: 004·012를 제외한 13개 174×110 ROI 박스 제안을 원본과 분리해 export했다. stem/shape/normalized label/metadata safety flag/exact duplicate 검사를 통과했지만 임시 색상 기반 라벨이고 중복 검토가 남아 `training_ready=false`다.
- `PASS (full-frame recovery)`: 좁은 ROI에서 잘린 장면도 640×480 context에 남아 있어 전체 31장에서 약통 몸통 후보가 각각 하나씩 검출됐다. 004·012를 제외한 29개 full-frame 박스 overlay를 육안 확인했다. 새 도구 단위 테스트 3/3 통과다.
- `REJECTED (scope metadata)`: 최초 `provisional-fullframe-v1`은 이미지/라벨 값은 정상이지만 dataset scope를 `pickup_roi_only`로 잘못 기록해 사용 금지했다. 원인 보존을 위해 삭제하지 않았다.
- `PASS (provisional full-frame v2)`: 수정된 export 도구로 `provisional-fullframe-v2` 29장을 `scope=full_frame`으로 새로 생성했다. stem 일치, 640×480 shape, class 0 normalized 범위, review/training/identity/robot safety flag를 검증했다. 한 세션 임시 양성만 있고 진짜 full-frame negative와 독립 평가 표본이 없어 학습 `NOT_RUN`, `training_ready=false`다.
- `PASS (first true full-frame negative)`: 사용자가 약통을 화면 밖으로 치운 뒤 정지 frame을 수집했다. 자동 약통 몸통 후보 0개와 전체 화면상 약통 부재를 확인하고 `empty_fullframe_001` 640×480 이미지·빈 label·metadata를 별도 `fullframe-negatives-v1`에 저장했다. 새 export 도구 단위 테스트 2/2 및 pair/shape/safety metadata 검사가 통과했다.
- `NEXT (hard negatives)`: 같은 빈 장면 복제는 중단한다. 약통 없이 펜·작은 상자·휴대폰 등 비대상 물체를 pickup 구역에 둔 실제 hard-negative가 필요하다. 양성 29장은 임시 제안이고 전체 목표 50–100개·독립 평가 분할 전 `training_ready=false`, 학습/로봇 동작 `NOT_RUN`.
- `PASS (first hard negative)`: 사용자가 작은 흰색 직사각형 비대상 물체를 pickup 구역에 둔 뒤 640×480 정지 frame을 수집했다. 전체 화면상 약통·손 부재와 약통 몸통 후보 0개를 확인하고 `hardneg_fullframe_001` 이미지·빈 label·metadata를 별도 저장했다. 현재 진짜 full-frame 음성은 empty 1 + hard negative 1이다.
- `NEXT (second hard negative)`: 현재 비대상 물체를 치우고 형태가 다른 펜 또는 휴대폰 한 개를 배치한다. 같은 장면 반복 저장은 하지 않으며 학습/로봇 동작은 계속 `NOT_RUN`이다.
- `PASS (second hard negative)`: 약통 없이 흰 작업 영역에 놓인 펜 한 개를 확인했다. 보라색 약통 몸통 후보 0개, 640×480 image, 빈 label, `training_ready=false`, `robot_target=false`를 검증하고 Jetson 비 Git 경로 `fullframe-hardnegative-002`에 저장했다.
- `PASS (combined full-frame candidates)`: 임시 양성 29장과 검토된 음성 3장(empty 1, 흰 직사각형 1, 펜 1)을 비파괴 병합했다. `provisional-fullframe-combined-v1` 총 32장의 stem/pair/shape/count와 safety flag 검사가 통과했다.
- `NOT_TRAINING_READY`: 양성은 한 촬영 세션의 색상 기반 임시 제안이고 음성은 3장뿐이며 독립 평가 세트가 없다. 다음은 휴대폰 같은 어두운 직사각형 hard negative와 최소 21개의 추가 다양한 양성이다. 학습·추론·로봇 구동은 `NOT_RUN`이다.
- `PASS (phone hard negative)`: 약통 없이 흰 작업 영역 중앙에 놓인 어두운 직사각형 휴대폰 한 개를 640×480 전체 화면에서 확인했다. 손은 없고 ID0–6과 세 바구니가 보였다. 보라색 약통 몸통 후보 0개, 빈 label, safety flag 검사를 통과했다.
- `PASS (combined full-frame v2)`: 휴대폰 음성을 추가해 `provisional-fullframe-combined-v2`를 비파괴 생성했다. 총 33장(임시 양성 29, 검토 음성 4), stem/pair 일치, 전 이미지 640×480, `training_ready=false`, `robot_enabled=false`를 확인했다.
- `NEXT (positive diversity)`: 음성 종류를 늘리는 1차 단계는 완료했다. 휴대폰을 치우고 연구용 흰 약통 모형만 작업 영역의 새 위치·방향에 두어 최소 21개의 추가 다양한 양성을 수집한다. 독립 평가 분할과 학습·추론·로봇 구동은 여전히 `NOT_RUN`이다.
- `REJECTED (new positive 01 near-duplicate)`: 새 640×480 frame에서 약통 전체와 ID0–6을 확인하고 full-frame 박스 `[374,234,31,41]`를 제안했으나, 중심 `(389.5,254.5)` px가 기존 `candidate_027` 중심과 3.54 px밖에 다르지 않았다. 기존 장면과 사실상 같은 위치이므로 label/export 및 29개 양성 수 합산을 하지 않았다.
- `NEXT (sparse placement)`: 기존 양성 중심 분포에서 안전 후보는 대략 `(460,255)` px다. 현재 위치에서 프리뷰 기준 오른쪽으로 약통 폭 약 2개 이동하되 ID1 검은 마커와 닿지 않게 하고, 뚜껑 방향도 약 90° 바꾼다.
- `BLOCKED (2026-09-27 active teleoperation)`: 사용자 재개 요청 후 Jetson 연결과 두 preview `ok=true`를 확인했지만 LeLab `teleoperation_active=true`였다. recording/inference는 inactive다. 한 버스 제어 소유권 원칙에 따라 새 촬영·label export를 실행하지 않았고 텔레오퍼레이션도 임의 종료하지 않았다. 사용자가 LeLab에서 Stop 후 현장 정지를 확인해야 한다.
- `NOT_DEPLOYED (export v4)`: 이전 중단 시도에서 stem-prefix 지원 exporter의 Jetson 배포가 완료되지 않았고 `/home/jetson3/export_medicine_label_proposals_v4.py`도 존재하지 않았다. 텔레오퍼레이션 종료 확인 후 다시 배포·검증한다.
- `PASS (web review console)`: 8010 상시 프리뷰에 카메라-only 약통 촬영/검토 UI를 추가했다. 양성/음성 촬영, ID0–3 검사, 작업영역 보라색 몸통 박스, 기존 양성과의 중심 거리, 승인/제외, 원본 보존, `training_ready=false`, `robot_enabled=false`를 제공한다.
- `PASS (web deploy)`: 기존 server는 `/opt/so101-camera-preview/camera_preview_server.py.pre-web-review-20260927`에 백업했다. 서비스 재시작 뒤 두 preview `ok=true`, `/api/review` 정상, 브라우저에서 촬영 버튼·통계·검토 카드가 표시됐다.
- `PASS (web workflow smoke)`: 현재 중앙 약통은 기존 양성과 6.265 px 차이라 `near_duplicate`로 차단됐다. 화면 왼쪽의 두 번째 약통도 사람 검토에서 확인해 해당 건을 제외 처리했다. export 파일은 0개이며 원본/metadata는 보존됐다.
- `OBSERVED (existing 8011 app)`: `/home/jetson3/so101_vlm_capture`의 기존 3카메라 VLM 사진·동작 영상 UI가 8011에서 실행 중이다. 8010은 빠른 YOLO 박스/중복 검토, 8011은 풍부한 VLM/동작 라벨 수집으로 역할을 분리했고 기존 8011 코드는 변경하지 않았다.
- `PASS (canonical USB recheck)`: 현재 `5AE6085272`(Leader)→ACM1, `5AE6058306`(Follower)→ACM0이며 LeLab robot record도 leader ACM1/follower ACM0다. raw ACM 번호는 재열거 결과이므로 안정 ID 역할과 모순되지 않는다.
- `IMPLEMENTED (T_B_W preparation)`: 4–8개 teach pair rigid fit/residual 도구와 버스 비접속 URDF FK 도구를 추가했다. 로컬 단위 테스트는 각각 3/3 통과했고 Jetson에서 실제 SO-101 `base→gripper` 5-joint chain, zero pose gripper origin `[20.615,-277.473,266.852]` mm, rotation determinant 1.0을 확인했다.
- `BLOCKED_AUTH (physical teach)`: 다음 MD 단계는 follower TCP를 4–8개 World 기준점에 teach하는 실제 모터 작업이다. LeRobot connect는 calibration write, torque-disabled configure, motor register write를 수행한다. 현장 안전 확인과 사용자 명시 승인 전에는 시작하지 않는다. `gripper` link→실제 tip offset도 미측정이다.
- `AUTHORIZED/RUN (safe-height teleoperation dry run)`: 사용자가 현장 장애물 제거·정지 준비 조건의 짧은 캘리브레이션 준비 구동에 `진행`으로 승인했다. 시작 전 두 preview 정상, recording/inference/teleoperation inactive, stable ID 기준 Leader→ACM1·Follower→ACM0를 재확인했다.
- `OBSERVED (transient ID4 start failure)`: 첫 시작은 Follower ID4 `Lock` write의 `There is no status packet`으로 실패했다. 제어 잔류가 없음을 확인하고 read-only broadcast ping에서 ID1–6 전부 model 777 응답을 확인한 뒤, 조건을 바꾸지 않은 1회 재시도는 성공했다.
- `INCIDENT (REST joint read bus collision)`: 텔레오퍼레이션 중 `/joint-positions`를 호출하자 worker의 동시 `Goal_Position` sync write가 `Port is in use`로 실패하고 세션이 자동 종료됐다. 추가 재시도는 하지 않았다. 이후 teach 수집은 serial bus를 다시 여는 REST endpoint가 아니라 기존 `/ws/joint-data` broadcast만 구독한다.
- `PASS (joint→FK plumbing)`: 충돌 직전 얻은 URDF radian 관절값을 `configs/fk-safe-pose-20260927.json`에 `use_for_robot_world_fit=false`로 기록했다. 오프라인 FK 결과 `base→gripper` link origin은 `[12.807,-117.958,127.822]` mm였다. 실제 TCP가 아니므로 World→Base fit에는 사용하지 않는다.
- `PASS (post-run safe state)`: 두 preview는 계속 `ok=true`이며 LeLab teleoperation·recording·inference는 모두 inactive다. 실제 World teach point, TCP offset 측정, `T_B_W` fit은 아직 `NOT_RUN`이다.
- `PASS (passive joint web monitor)`: 8010 비전 콘솔에 LeLab `/ws/joint-data`를 직접 구독하는 읽기 전용 관절 패널과 JSON 복사 기능을 추가했다. `/joint-positions`, `/move-arm`, `/stop-teleoperation` 호출은 코드에 없고 copied sample은 기본 `use_for_robot_world_fit=false`다. 회귀 테스트 11개 통과 후 SHA `b1286a8a...943`로 배포했으며 기존 파일은 `.pre-joint-ws-20260927T1532`로 백업했다.
- `PASS (web UI verification)`: 브라우저에서 두 카메라 preview, `WebSocket 연결됨 · 텔레오퍼레이션 관절 방송 대기`, 읽기 전용 설명과 복사 버튼을 확인했다. 서비스 재시작 뒤 두 카메라 health `ok=true`; 로봇은 다시 움직이지 않았다.
- `PASS (web collection expanded)`: 8010 queue는 총 240건, approved 52, excluded 57, blocked 131로 늘었다. 승인 세부는 positive 32, negative 20이다. blocked는 주로 near-duplicate이며 원본은 삭제하지 않았다.
- `PASS (non-destructive candidate preparation)`: 기존 `provisional-fullframe-combined-v2` 33건과 웹 승인 52건을 새 `training-candidates-audit-v1`로 감사했다. 입력 85건에서 기존 양성 내부 12px 미만 위치 중복 14건을 별도 exclusion 목록으로 남기고 positive 47, negative 24, 총 71쌍을 생성했다. images/labels/metadata 수가 모두 71로 일치하고 exact image duplicate는 없었다.
- `PASS (candidate visual audit)`: 양성 접촉시트의 47개 빨간 bbox가 연구용 약통 모형 전체와 일치함을 확인했다. 음성은 empty·흰 직사각형·펜·휴대폰 및 웹 음성으로 구성되지만 일부 웹 음성의 장면 변화가 작아 완전히 독립적인 24장으로 과대평가하지 않는다.
- `NOT_TRAINING_READY`: prepared audit는 `training_ready=false`, `independent_evaluation_ready=false`, `robot_enabled=false`다. 같은 카메라/세션 frame을 무작위로 나눈 평가는 금지하며, 다음은 별도 세션의 독립 평가 표본이다. proximity 임시 감사의 첫 실행은 normalized label string을 float로 변환하지 않아 실패했고 변환 후 61 positive/47 position component를 확인했다.
- `PASS (end state after data audit)`: 두 preview `ok=true`, LeLab teleoperation·recording·inference 모두 inactive다. 데이터 감사 중 로봇·토크·USB·전원은 조작하지 않았다.
- `PASS (separate evaluation queue)`: 8010에 `독립 평가 표본 촬영 · 별도 큐`를 추가했다. 기본 저장 경로는 비 Git `/home/jetson3/so101-medicine-bootstrap/evaluation-web-v1`이고, `training-candidates-audit-v1`을 중복 기준으로 사용한다. 평가 양성/음성 촬영·검토·승인은 학습 후보 큐와 물리적으로 분리된다.
- `PASS (evaluation UI deploy)`: 회귀 테스트 10개 통과 후 camera server SHA `18e4da82...4171`을 설치했고 기존본은 `.pre-eval-queue-20260927T1600`으로 보존했다. 첫 restart 묶음 명령 뒤 기존 process가 남아 evaluation API가 404였고, restart를 단독 실행해 frame counter 초기화·`/api/eval/review` HTTP 200·빈 queue·브라우저 새 패널을 확인했다.
- `NEXT (independent evaluation capture)`: 학습 후보 버튼은 더 사용하지 않는다. 카메라·보드·ArUco는 고정하고, 별도 평가 큐에 학습 위치와 다른 양성 10개와 장면이 다른 음성 5개를 한 장씩 수집한다. 완료 전 학습/추론은 `NOT_RUN`이다.
- `PASS (additional training-queue salvage)`: 사용자의 추가 촬영은 독립 평가 큐가 아니라 기존 학습 후보 큐에 저장됐다. 기존 승인본 대비 positive 12개·negative 6개가 추가돼 총 approved positive 44개·negative 26개가 됐다. 원본은 삭제하지 않았다.
- `PASS (candidate audit v2)`: legacy 33건과 갱신된 web 승인 70건을 비파괴 `training-candidates-audit-v2`로 다시 감사했다. input 103, kept positive 59, negative 30, 기존 legacy 양성 위치 중복 excluded 14이며 `training_ready=false`, `independent_evaluation_ready=false`, `robot_enabled=false`를 유지했다.
- `REVIEW_REQUIRED (negative scope)`: v2 음성 접촉시트에는 현재 검출 범위인 full frame 가장자리에 손과 작은 물체가 보이는 frame이 있다. 연구용 약통 모형이 화면 안에 남은 frame이 있다면 음성으로 사용하지 않도록 개별 재검수가 필요하다.
- `PASS (evaluation-only UI)`: 추가 혼합을 막기 위해 8010의 기존 학습 양성/음성 촬영 버튼을 disabled 처리했다. Jetson 설치 SHA-256은 `5b0491f3...4cd0`, 백업은 `.pre-eval-only-20260927T1632`이다. 부브라우저에서 학습 버튼 disabled·평가 버튼 enabled·평가 total 0을 확인했다.
- `PASS (end state after v2 audit)`: Astra·RealSense preview는 모두 `ok=true`, LeLab teleoperation·recording·inference는 모두 inactive였다. 로봇·토크·USB·전원 조작은 수행하지 않았다. 독립 평가는 아직 `0/15` 이므로 다음은 아래 평가 버튼으로 양성 10개·음성 5개를 새로 수집하는 것이다.
- `OBSERVED (evaluation threshold too strict)`: 독립 평가 큐는 total 19, approved negative 5, blocked positive 14였다. positive 차단 중 11개가 중심점 12 px 기준의 `near_duplicate`, 3개가 `workspace_target_count_not_one`였다. 화면 검수에서 near-duplicate 후보들은 서로 다른 위치에 정상 bbox로 보여 12 px 정책이 과도하다.
- `PREPARED_NOT_DEPLOYED (evaluation 3 px policy)`: 기존 학습 큐 12 px 기준은 유지하고 평가 큐만 3 px로 조정하는 로컬 코드를 준비했다. 기존 near-duplicate 11개 중 거리 3 px 이상 10개를 재검토 대기로 복구하고 2.915 px 1개는 차단 유지할 예정이다.
- `BLOCKED_NETWORK`: 배포 직전 `192.168.50.20:22`와 `:8010`이 모두 timeout으로 변했고 브라우저도 `ERR_CONNECTION_TIMED_OUT`을 표시했다. 로컬 수정은 Jetson에 `NOT_DEPLOYED`, 기존 metadata 재분류도 `NOT_RUN`이다. 사용자가 Jetson Wi-Fi/전원 연결을 복구한 뒤 계속한다.
- `PASS (evaluation 3 px deploy)`: 사용자의 네트워크 복구 후 학습 큐는 12 px를 유지하고 평가 큐만 3 px를 사용하는 코드를 배포했다. server/module SHA-256은 `6c912bc7...01a0`, `f0c9160a...7689`이며 설치 전 코드와 평가 큐 전체를 `pre-eval-3px-20260927T2019`로 보존했다.
- `OBSERVED (first install command incomplete)`: 최초 복수 명령에서 백업만 실행되고 설치 두 명령이 반영되지 않아 설치 hash가 기존값으로 남았다. service를 다시 중지하고 파일을 각각 설치한 뒤 예상 hash 일치를 확인해 복구했다.
- `PASS (evaluation reclassification)`: 비파괴 queue 백업 후 추적 기록을 남기는 별도 도구로 sole `near_duplicate` 11개 중 거리 3 px 이상 10개를 `pending_review`로 복구했다. 2.915 px 1개와 target-count 실패 3개는 blocked로 남겼고 자동 승인/자동 export는 0개였다.
- `PASS (evaluation approved set)`: UI 상태와 원격 metadata/export 교차 확인 결과 approved 15 = positive 10 + negative 5, export images/labels/metadata 각 15개였다. 양성 label 10개와 빈 음성 label 5개가 일치했다.
- `REVIEW_REQUIRED (evaluation internal duplicate)`: 승인 양성 10개를 서로 비교하니 `20260927T074028_614344Z`와 `20260927T073948_405741Z`의 중심 거리가 1 px였다. 앞의 frame이 bbox crop Laplacian variance 2974.911로 뒤 frame 2776.703보다 선명하므로 선명한 한 장만 최종 평가에 사용한다. 원본/승인본은 삭제하지 않았다. 현재 유효 독립 평가는 positive 9 + negative 5이며 새 위치 positive 1개가 더 필요하다.
- `PARTIAL (angled preview ownership)`: 8010 재시작 후 Astra는 정상이지만 RealSense `/dev/video4`는 LeLab uvicorn PID 239863이 점유해 8010이 열지 못했다. LeLab을 임의 정지하지 않았고 USB도 건드리지 않았다. 평가 저장본 검수와 Astra 촬영은 가능하지만 사선 preview는 추가 조정이 필요하다.
- `BLOCKED (additional evaluation positive)`: 재연결 뒤 새 위치의 평가 양성 `20260927T112718_990769Z`를 촬영했지만 marker 0–3만 검출되고 약통 색상 본체 후보가 0개라 `workspace_target_count_not_one`으로 차단됐다. 약통이 follower gripper 바로 아래에 가려지고 색상 면이 거의 보이지 않았다. 승인/export는 하지 않았으며, 그리퍼 그림자 밖의 새 위치에서 색상 면을 천장 카메라 쪽으로 보이게 한 양성 1개가 여전히 필요하다.
- `PASS (evaluation positive target reached)`: 사용자 재배치 뒤 `20260927T112957_608824Z`에서 marker 0–3, 약통 몸통 후보 1개, bbox `[378,223,27,41]`, 기존 학습 양성 최근접 거리 12.54 px를 확인했다. overlay 육안 검수 후 승인했으며, 기존 1 px 중복 한 장을 선정에서 제외하면 유효 양성 10개가 된다.
- `REJECTED (evaluation negative scene duplicates)`: 승인 음성 5장은 5초 안에 촬영된 같은 빈 장면이며 pairwise dHash 거리가 1–6이라 한 장면 cluster로 판단했다. 첫 `evaluation-final-v1` 초안은 삭제하지 않고 `evaluation-final-v1-rejected-negative-duplicates`로 이름을 바꾸고 `independent_evaluation_ready=false`로 정정했다. 중복 감사를 추가한 v2 준비는 positive 10·negative 1로 fail-closed했고 출력 디렉터리를 만들지 않았다.
- `NEXT (four distinct evaluation negatives)`: 약통을 화면 밖으로 치운 뒤 빈 장면과 다른 비대상 배치 4종(예: 펜, 휴대폰, 작은 상자, 케이블/테이프)을 한 장면씩 평가 음성으로 촬영·승인한다. 마커 0–3을 가리지 않고, 같은 배치 연속 촬영은 하지 않는다. 학습과 로봇 구동은 계속 `NOT_RUN`이다.
- `CONCURRENT_CHANGE (Astra V4L2 bridge)`: 20:31 KST 다른 Jetson TTY 세션이 `/etc/modprobe.d/astra-v4l2loopback.conf`, `/etc/modules-load.d/astra-v4l2loopback.conf`, `astra-v4l2-bridge.service`를 설치하고 `systemctl disable --now so101-camera-preview.service`를 실행했다. 이어 `/dev/video8` 대상 OpenNI→GStreamer bridge를 enable/start했다. 8010 중지는 camera server 오류가 아니라 이 외부 변경이며, 충돌을 피하려고 재활성화하지 않았다. bridge는 active, 8000만 listen 중이고 8010/8011은 현재 내려가 있다.

## 2026-10-11 Elbow raw tracking diagnostic result

- `ROOT_CAUSE`: the Elbow servo reaches a load-dependent stationary tracking offset (deadband/holding equilibrium), not a Goal write, degree/raw conversion, calibration, or settle-time failure.
- The replacement diagnostic used the unchanged live-C pre-approach plan, IK, path, and 1.6 degree tolerance. It timed out at actually transmitted waypoint 2 of 55; grasp/lift were `NOT_RUN` and no automatic retry occurred.
- Waypoint 2 target raw/readback were both `3006`. Present moved only `3041 -> 3038 -> 3037`; after the timeout the 3-second/150-ms window stayed at 31-32 raw residual, `Moving=0`, `Present_Load=136-140`, and degree error `2.776 -> 2.688`. The 0.088 degree decrease over the extra window is a plateau, not continuing convergence.
- User `STOPPED` plus fresh feedback gave `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. Post-run teleop/recording/inference were inactive, no related process remained, and privileged follower `fuser rc=1` showed no owner.
- Raw report: `.local/c-red-pivot-tcp-table-20261011-s01/elbow-final-tracking-diagnostic-20261011-r2.json`. Tolerance/path/IK/vision/TCP/calibration remain unchanged. No corrective motor trial is authorized. Changes are `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-11 load-relieved pre-approach IK dry-run

- Reused the fixed C robot XY `[-62.635354,-295.315566] mm`, pivot TCP offset, installed URDF SHA, and a fresh read-only follower pose `[-9.538,-94.725,+87.956,+71.956,-15.165] degrees`. No motor Goal or torque command was sent.
- Position-only IK candidates at unchanged XY and Z `100/110/120/130/140/150 mm` all passed with residual below `0.60 mm`, Elbow `42.003-43.893 degrees`, and at least `53.118 degrees` servo-calibration margin. No XY adjustment was needed.
- Candidate A was selected for a future approval gate: unchanged XYZ `[-62.635354,-295.315566,100.0] mm`, joints `[+5.041,+2.879,+42.003,+16.184,+84.083] degrees`. It makes no Cartesian pose change, reduces Elbow travel versus the old 14.866-degree IK branch, and stays far from servo endpoints.
- Important: the prior `89.927 degrees` was the second transition waypoint, not the final pre-approach IK. The selected alternative branch reduces the Elbow delta from the fresh pose to `-45.953 degrees` but does not itself prove unloaded physical tracking. Actual pre-approach remains `NOT_RUN/NOT_AUTHORIZED`; tolerance stays `1.6 degrees`; grasp/lift `NOT_RUN`.
- Result: `.local/c-red-pivot-tcp-table-20261011-s01/elbow_load_relief_ik_candidates_20261011.json`. Changes `NOT_COMMITTED/NOT_PUSHED`.

## GitHub

- 저장소: <https://github.com/gyeyeongjo-lgtm/so101-lelab-medicine-sorter>
- 공개 범위: private (`PASS`)
- 기본 브랜치/초기 커밋: `main` / `8dd6761`
- 작업 브랜치/진단 결과 커밋: `fix/usb-recording` / `c670c7a`
- 이슈: #1 포트 식별, #2 녹화 TX/RX, #3 회귀·데이터 검증, #4 후속 로드맵

## 2026-09-27 약국 대상 검출 범위 정정

- `USER_SCOPE_CORRECTION`: 실제 운용 가정은 약국 작업대이며 현재 1차 목표는 연구용 약통 모형의 존재와 위치 검출이다. 손·펜·휴대폰 등 임의 비대상 물체의 종류별 성능을 이번 단계의 완료 조건으로 요구하지 않는다.
- `PASS (negative visual recheck)`: `training-candidates-audit-v2` 음성 30장을 다시 육안 확인했다. 일부 frame에 손이나 다른 물체가 있지만 작업영역에 목표 약통 모형이 남은 음성은 발견하지 않았다. 따라서 이전 `REVIEW_REQUIRED (negative scope)`의 추가 hard-negative 요구는 위 사용자 범위에서 해제한다.
- `PASS (smoke evaluation set)`: 비파괴 `/home/jetson3/so101-medicine-bootstrap/evaluation-final-v2`를 positive 10·고유 empty negative 1로 준비했다. status는 `READY_FOR_OFFLINE_DETECTION_SMOKE_EVALUATION`, profile은 `pharmacy_target_presence_smoke`다.
- `LIMITATION`: 음성 장면이 1개이므로 robust false-positive rate 또는 일반 환경 성능을 주장할 수 없다. `independent_evaluation_ready=false`, `false_positive_rate_ready=false`, `robot_enabled=false`를 유지한다.
- `NEXT (offline only)`: 감사된 training positive 59·negative 30을 capture-time block 기준 train/validation으로 분리하고 위 10+1은 test 전용으로 유지하는 YOLO 패키지를 준비한다. 설치·학습·추론과 로봇 동작은 이 기록 시점에는 아직 `NOT_RUN`이다.

## 2026-09-28 YOLO11n 약통 검출 스모크

- `PASS (dataset packaging)`: `yolo-medicine-v1`을 train 71(positive 47/negative 24), validation 18(12/6), test 11(10/1)로 준비했다. validation은 30초 capture block 단위로 분리했고 세 split 간 exact image overlap은 0이다.
- `PASS (offline training)`: Mac 격리 환경의 PyTorch 2.14.0·Ultralytics 8.4.163, Apple M3 MPS에서 YOLO11n을 학습했다. 40 epoch 중 best는 epoch 30이고 validation precision 0.995, recall 1.000, mAP50 0.995, mAP50–95 0.766이다.
- `PASS (offline test smoke)`: 별도 test 11장에서 precision 0.995, recall 1.000, mAP50 0.995, mAP50–95 0.798을 확인했다. confidence 0.25에서 positive 10/10은 각각 1 detection, empty negative 1/1은 0 detection이었다. box IoU 최소 0.8392·평균 0.8937, 최소 confidence 0.8921이다.
- `PASS (visual prediction review)`: 두 test prediction contact sheet를 육안 확인했고 박스가 약통 모형에 위치하며 empty frame에는 박스가 없었다.
- `LIMITATION`: test negative가 고유 empty scene 1개뿐이므로 `PASS_OFFLINE_TARGET_PRESENCE_SMOKE`까지만 판정한다. robust false-positive rate·일반 환경 독립 성능은 `NOT_VERIFIED`이고 `robot_enabled=false`다.
- `NEXT`: best checkpoint를 Jetson 실행 형식으로 export한 뒤 저장 frame과 live preview에서 overlay를 확인한다. 검출을 로봇 명령으로 연결하는 단계는 아직 금지한다.
- `NOT_PUSHED`: 데이터셋·checkpoint는 Git 제외 경로에 있고 이번 변경도 commit/push하지 않았다.

## 2026-09-28 ONNX Jetson 배포·live preview 장애

- `PASS (ONNX export/deploy)`: best checkpoint를 ONNX opset 17로 export하고 Jetson 새 비 Git 모델 디렉터리에 배포했다. 모델 SHA-256은 Mac/Jetson 모두 `d2f8452e...c846`이다.
- `PASS (Jetson saved-frame inference)`: Jetson OpenCV 4.12.0 DNN에서 저장 test 11장을 실행해 positive 10/10 각각 1 detection, empty negative 1/1 detection 0을 Mac 결과와 동일하게 재현했다.
- `PASS (single live snapshot)`: `/dev/video8`의 640×480 snapshot에서 약통을 confidence 0.746739로 검출했고 bbox 위치를 육안 확인했다. 다른 흰 용기는 검출하지 않았다.
- `FAIL (continuous live preview)`: read-only port 8020 web smoke는 8 frame 뒤 `frame read failed`로 정지했다. bridge journal의 최초 오류는 13:38:40 GStreamer internal data stream error이며 이후 OpenNI USB control request 실패가 반복됐다.
- `SAFETY_STOP`: 임시 YOLO web process를 종료했고, 자동 재시작이 61회 반복된 `astra-v4l2-bridge.service`를 stop했다. unit은 enabled로 보존했으며 USB·전원·설정은 변경하지 않았다. 8020 listener는 없다.
- `PASS (control end state)`: LeLab teleoperation·recording·inference는 모두 inactive다.
- `BLOCKED_USER_ACTION`: 사용자가 천장 Astra USB를 한 번 분리·재연결한 뒤 알려줘야 한다. 그 후 bridge start→stable frame→read-only 8020 preview 순으로 재검증한다.

## 2026-09-28 Astra 재연결 후 live YOLO 직접 입력 우회

- `PASS (USB reconnect)`: 사용자가 Astra USB를 재연결한 뒤 `2bc5:0401` 장치가 새 bus device로 재인식됐다. LeLab health는 정상이고 teleoperation·recording·inference는 모두 inactive였다.
- `FAIL (bridge isolated)`: 카메라 consumer가 없는 상태에서 `astra-v4l2-bridge.service`를 재기동했지만 GStreamer `v4l2sink` frame 1부터 `No free buffer found` / `failed queueing buffer 0` / `Internal data stream error`로 실패했다. Astra RGB producer는 640×480 RGB888 3 frame(2,764,800 bytes)을 정상 연속 전달했고, `videotestsrc`도 동일 `v4l2sink` 오류를 재현해 원인을 `/dev/video8` v4l2loopback 출력 버퍼 구간으로 격리했다.
- `SAFETY_STOP`: 자동 재시작 횟수가 71까지 증가한 bridge를 다시 stop했다. `enabled`와 모듈·unit 설정은 바꾸지 않았다.
- `PASS (direct Astra live YOLO)`: `medicine_yolo_web.py`에 packed RGB888 subprocess 입력을 추가해 v4l2loopback을 건너뛰다. 로컬 회귀 테스트 6개와 Jetson syntax 검사를 통과했다.
- `PASS (LAN 8020 smoke)`: Jetson `http://192.168.50.20:8020/` 임시 read-only server가 Astra RGB를 직접 소유한다. sequence 39→200→582→950으로 계속 증가했고 frame age 0.091–0.166 s, inference 147.3–156.2 ms, 약통 1개 confidence 0.748–0.785를 표시했다. Mac LAN `/health`도 성공했고 `robot_enabled=false`다.
- `PENDING (human visual)`: 자동 브라우저는 사설 IP의 새 8020 URL 이동을 보안 정책으로 차단했다. 사용자가 해당 URL을 직접 열어 live box 위치를 한 번 확인해야 한다.
- `RESOURCE OWNERSHIP`: 현재 8020 임시 process가 Astra를 소유하므로 `so101-camera-preview.service` 8010과 bridge는 inactive다. 천장 사선 RealSense preview는 이 smoke 동안 일시 정지다. 로봇 직렬·토크·모터 명령은 실행하지 않았다.
- `NOT_PERSISTENT`: 8020은 systemd로 등록하지 않은 임시 process다. 육안 검수 후 천장 정면 YOLO·사선 preview를 한 페이지로 통합한 뒤 서비스화한다. Git commit/push는 `NOT_PUSHED`다.

## 2026-09-28 통합 프리뷰·작업대 dry-run 좌표

- `PASS (user visual)`: 사용자가 8020 live 화면의 약통 YOLO 박스를 육안 확인하고 `완료`로 통과시켰다.
- `PASS (integrated cameras)`: 같은 8020 페이지에 천장 정면 Astra YOLO와 천장 사선 RealSense D435 프리뷰를 통합했다. 브라우저에서 두 실제 영상과 health `ok=true`를 확인했다.
- `PASS (persistent service)`: `medicine-yolo-preview.service`를 설치해 enabled·active, `NRestarts=0`을 확인했다. 실패한 `astra-v4l2-bridge.service`는 unit을 삭제하지 않고 boot auto-start만 disabled했다. 기존 8010 `so101-camera-preview.service`도 disabled·inactive다.
- `PASS (ArUco table projection)`: 매 frame ID0–3 homography를 계산해 `table.ready=true`, 실측 ID0–6 모두 검출, reference RMS 약 `0.000007 mm`를 확인했다. 이 RMS는 네 기준점 homography 내부 재투영값이며 실제 로봇 절대좌표 정확도가 아니다.
- `PASS (pickup ROI dry-run)`: 현재 약통 2개 중 1개는 영상 중심의 평면 투영값 약 `(193.2, 248.3) mm`로 pickup ROI X 80–220/Y 200–300 mm 내부였고, 다른 1개는 약 `(250.4, 316.0) mm`로 ROI 밖이었다.
- `PASS (basket mapping)`: ID4=red 약 `(59.7,95.1) mm`, ID5=green 약 `(245.5,93.2) mm`, ID6=blue 약 `(152.6,95.8) mm`의 현재 table-plane 투영 좌표를 표시한다.
- `SAFETY`: 약통 좌표는 bbox 영상 중심을 테이블 평면에 투영한 높이 미보정 dry-run이다. `robot_enabled=false`, `robot_target_authorized=false`고 LeLab teleoperation·recording·inference는 모두 inactive다. 로봇 직렬·토크·모터 명령은 없었다.
- `DEPLOY HASH`: web script `ae7333e2...60cd`, systemd unit `9656d7a4...34c4`다. 설치 전 web·unit은 timestamp suffix backup으로 보존했다.
- `BLOCKED_APPROVAL (next phase)`: 다음 유효 단계는 그리퍼 link에서 실제 TCP offset을 확정하고 World 기준점 4–8개에 follower TCP를 teach해 `T_B_W`를 구하는 것이다. 실제 팔 구동이 필요하므로 현장 안전 확인과 새 명시 승인 전에는 시작하지 않는다. Git commit/push는 `NOT_PUSHED`다.

## 2026-09-28 4점 World teach 시작 결과

- `PASS`: 빈 작업대의 검은 X 4개를 천장 정면·사선 프리뷰에서 확인했고, ID0–3 homography로 World 좌표 P1 `[273.493,321.191,0]`, P2 `[54.233,314.222,0]`, P3 `[60.112,183.993,0]`, P4 `[273.586,185.970,0]` mm를 확정했다.
- `AUTHORIZED`: 사용자가 4점 저속 텔레옵 teach를 승인했고 시작 전 stable ID Leader→ACM1, Follower→ACM0와 세 제어 inactive를 확인했다.
- `FAIL`: 텔레옵 시작은 첫 회 ID4, 읽기 전용 3-round 정상 확인 후 단 1회 재시도에서 ID6 `Torque_Enable=1` status packet 누락으로 각각 실패했다. 추가 재시도는 중단했다.
- `PASS (safe end state)`: Follower ID1–6 torque는 모두 0, teleoperation·recording·inference inactive, 8020 두 preview와 table homography 정상이다.
- `PASS (read-only)`: Follower ID1–6 정지 시 전압은 모두 12.2 V, 온도는 34–39°C였다. 이 정적 snapshot은 정상이지만 쓰기 시 status-packet 누락은 아직 미해결이다.
- `BLOCKED_HARDWARE`: 4점 joint sample, TCP offset 검증, FK pair, `T_B_W` fit은 `NOT_RUN`이다. 쓰기 시에만 반복되는 follower bus status-packet 누락을 해결한 뒤 재개한다.
- `NOT_PUSHED`: 이 변경은 commit·push하지 않았다.

## 2026-09-28 닫힌 tip TCP 6점 준비

- `PASS`: 새 P5·P6를 내부에 엇갈려 배치한 현재 6개 X가 ID0–3과 함께 두 preview에서 모두 보인다.
- `PASS (coordinates)`: 현재 World mm는 P1 `[276.693,299.484,0]`, P2 `[57.275,297.925,0]`, P3 `[60.137,167.664,0]`, P4 `[273.536,164.708,0]`, P5 `[212.898,252.880,0]`, P6 `[115.771,210.949,0]`이다.
- `CORRECTION`: 현재 P1–P4는 이전 teach 때보다 World Y가 약 16–22 mm 변했으므로 이전 4/8개 joint sample을 현 layout fit에 재사용하지 않는다.
- `READY_FOR_TEACH`: 새 6점 config은 `robot_world_pairs.20260928.closed-tip.local.json`이다. 다음은 리더 명령으로 닫은 그리퍼 tip을 TCP로 한 P1–P6 WebSocket teach다. 로봇 이동은 계속 차단한다.
- `NOT_PUSHED`: 이 변경은 commit·push하지 않았다.

## 2026-09-28 고정 Jaw repeat 최종 판정

- `PASS`: P1–P4 repeat sample을 Jaw 0.038–0.044 rad로 수집했고 각 세션 후 텔레옵 종료, Follower torque 0, 세 제어 inactive, 8020 preview·homography 정상을 확인했다.
- `PASS (tooling)`: TCP+`T_B_W` 동시 fit에 pair-name 선택 기능을 추가해 Jaw 조건이 다른 sample을 혼합하지 않게 했고 테스트 4/4를 통과했다.
- `REJECTED`: fixed-Jaw repeat 4건 fit은 RMSE 5.780 mm, max 6.694 mm, condition 5887.5로 RMSE·observability 기준을 통과하지 못했다. 가까운 Jaw의 원본 P1 holdout도 9.03 mm 오차였다.
- `MOTION_BLOCKED`: 현 `T_B_W`·TCP 결과는 실제 이동·pick에 사용하지 않는다. 다음 필요 조치는 명령으로 닫은 그리퍼 단일 tip TCP와 6개 이상 분산 point 재-teach이다.
- `NOT_PUSHED`: 이 변경은 commit·push하지 않았다.

## 2026-09-28 4점 teach 수집·fit 판정

- `PASS`: 사용자가 LeLab UI에서 텔레옵을 활성화한 뒤 P1–P4 각 15개 관절 sample을 `/ws/joint-data` broadcast로만 수집했다. `/joint-positions`와 추가 serial reader는 사용하지 않았다.
- `PASS (safe end state)`: P4 수집 직후 텔레옵을 정상 종료했고 Follower ID1–6 torque 0, 세 제어 inactive, 8020 두 preview·homography 정상을 확인했다.
- `IMPLEMENTED`: known World point·FK link pose에서 gripper-link TCP offset과 `T_B_W`를 동시 추정하고 residual·observability로 fail-closed 판정하는 `fit_robot_world_tcp_transform.py`를 추가했고 단위 테스트 3/3을 통과했다.
- `REJECTED`: 현재 4점 fit은 RMSE 9.572 mm, max 12.073 mm, condition number 7031.4로 모든 허용 기준을 넘었다. TCP offset 추정치는 `[22.362,-13.767,-45.344]` mm이지만 실제 명령에 사용하지 않는다.
- `MOTION_BLOCKED`: `robot_world_transform.20260928.local.json`은 `robot_enabled=false`, `motion_authorized=false`다. 다음은 현재 P4와 같은 그리퍼 벌림을 유지한 P1·P2 repeat teach로 Jaw 차이·수동 재현성을 보강한 뒤 재계산한다.
- `NOT_PUSHED`: 이 변경은 commit·push하지 않았다.
