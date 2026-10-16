# CONTACT_RELEASE_ONLY attempt1 — 사후 오프라인 분석

새 Jetson 접속·serial read·Goal/Torque/motor write 없이 attempt1 사전/사후 read-only 표본, stdout 오류, 설치 당시와 SHA가 일치한 로컬 코드 및 기존 pinned URDF/GRASP TCP만 사용했다. `CONTACT_RELEASE_ATTEMPT1=FAIL`, 현장 `정지·아직 접촉`, 자동 재시도 `0`을 유지한다.

관절 순서: Pan, Lift, Elbow, Wrist Flex, Roll, Gripper. start Present raw `[2029,1643,2755,2394,1612,489]`, final Present raw `[2036,1643,2755,2390,1612,489]`; actual raw delta `[+7,0,0,-4,0,0]`. normalized actual arm delta `[+0.615385,0,0,-0.351648,0]°`, gripper `0 pp`. start/final Goal raw는 `[2032,1642,2752,2396,1612,490]` 및 `[2046,1642,2750,2388,1612,490]`; 마지막 Goal 변화가 arm Goal 1회 이상을 입증하지만 첫 송신 Goal 및 총 송신 횟수는 기록되지 않았다.

기존 URDF SHA `443d38d7…f67236`와 GRASP TCP offset으로 동일 FK를 적용하면 start GRASP TCP Z `2.906663 mm`, final `3.285876 mm`, 변화 `+0.379213 mm`다. 이는 TCP 모델의 Z이며 fingertip/table 사이 실제 간극 측정이 아니다. 코드의 허용된 송신은 target Z가 initial Z 및 해당 fresh actual Z보다 높을 때만 가능하므로 **송신된 target은 상승 방향**이다. 그러나 `oversized_arm_steps()`가 target FK 계산보다 먼저 실행되므로 실패를 일으킨 미송신 target의 Z 방향은 알 수 없다.

`arm_step_exceeds_existing_guard`는 arm 어느 축이든 직전 target 대비 `abs(delta)>2.0°`일 때 발생한다. 오류 문자열에 위반 축/요청 delta가 없고, entrypoint는 최초 송신 Goal이나 리더 매-cycle 값을 남기지 않는다. 따라서 `FIRST_SENT_GOAL`, `FIRST_LIMITED_JOINT`, 실패 표본의 `REQUESTED_DELTA_PER_JOINT`는 `NOT_RECORDED`; post-stop Goal을 first-sent로 대체하지 않는다.

두 분류 중 **B (관측된 경로는 상승 방향이고 2° motion cap에서 중단)**가 지지된다. A 방향/부호 오류의 증거는 없다. 다만 실패 표본 자체의 방향은 미기록이라 B가 그 표본의 방향까지 증명하는 것은 아니다. movement limit은 유지한다.

현재 접촉은 TCP Z `+0.379213 mm` 실제 상승 후에도 지속됐다. 접촉점이 GRASP TCP와 다르고 fingertip/table 실제 간극·필요 상승량은 기록되지 않았다. 기존 Goal/Present 잔차 및 loaded-joint deadband 때문에 raw 1 count 또는 임의 몇 mm를 해제 성공 조건으로 삼을 수도 없다. **물리적으로 충분한 최소 one-shot target/waypoint 수는 attempt1만으로 결정 불가**다. FK로는 현 자세에서 Elbow를 음의 방향으로 움직일 때 Z가 올라가는 등 수학적 상승 방향을 확인했지만, 그것을 contact-release-ready 후보로 승격하지 않는다. 필요한 오프라인 보완은 최초/실패 직전 leader·target·위반 축/step·FK Z를 남기는 국소 진단과 현장 접촉 간극 근거 확보이며, 새 live command는 없다.

```ini
CONTACT_RELEASE_ROOT_CAUSE = B (observed upward motion, 2.0° step guard abort; rejected target direction NOT_RECORDED)
FIRST_LIMITED_JOINT = NOT_RECORDED
TCP_Z_CHANGE = +0.379213 mm
NEXT_OFFLINE_FIX = capture per-cycle leader/target/step/FK and obtain physical contact-clearance evidence; no limit change
NEXT_LIVE_COMMAND = NONE
```

원본 비밀번호·로그는 커밋하지 않는다. 이 분석 기록은 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`이다.
