# CONTACT_RELEASE_ONLY attempt1 — 단일 상승 후보 오프라인 검토

범위는 저장된 attempt1 기록과 동일 URDF/GRASP TCP의 오프라인 FK뿐이다. Jetson/serial 재접속, 모터·Goal·Torque·configuration write, LeLab UI/teaching/recorder 작업은 모두 `0`/`NOT_RUN`. 현장 마지막 확인은 `정지·아직 gripper-table 접촉`이다.

관절 순서 Pan/Lift/Elbow/Wrist Flex/Roll/Gripper. start Present raw `[2029,1643,2755,2394,1612,489]`, final Present raw `[2036,1643,2755,2390,1612,489]`. actual delta raw `[+7,0,0,-4,0,0]`; arm ° `[+0.615385,0,0,-0.351648,0]`. start Goal raw `[2032,1642,2752,2396,1612,490]`, post-stop 마지막 Goal raw `[2046,1642,2750,2388,1612,490]`. 마지막 Goal은 첫 송신값으로 볼 수 없다. 코드가 최초 Goal, 리더 cycle, 실패 직전 target/위반 축을 출력하거나 저장하지 않았고 예외 시 `follower_writes`도 출력되지 않았다. `FIRST_SENT_GOAL`, `FIRST_LIMITED_JOINT`, 실패 target의 `REQUESTED_DELTA_PER_JOINT`, 첫 Goal의 예측 Z 및 요청 Z 변화는 `NOT_RECORDED`다.

동일 FK 계산: start GRASP TCP Z `2.906663 mm`, final Present Z `3.285876 mm`, 실제 변화 `+0.379213 mm`. 참고로 **마지막 관측 Goal**의 예측 Z는 `5.002420 mm`로 start Present 대비 `+2.095757 mm`지만 첫 송신 Goal 또는 실제 도달량이 아니다. 송신된 target은 코드의 상승 gate를 통과했고 final Present도 상승했다. 실제 stop trigger는 `arm_step_exceeds_existing_guard`이며 기존 관절별 `2.0°` cap 초과다. 따라서 분류 `B`를 **실행 중단 원인**으로 채택한다. 이는 위반 축/미송신 target의 방향이나 접촉 해제에 필요한 물리 상승량을 증명하지 않는다. C(추종 부족)도 마지막 Goal과 Present 차이로 의심되지만 독립적으로 접촉 실패의 단일 원인이라 확정할 수 없다.

오프라인 단일 가설 후보는 반응이 실제 관측된 Wrist Flex만 사용한다. final Present raw `2390`에서 Wrist Flex Goal raw `2384`(현재 저장 Goal raw `2388` 대비 `-4 raw`), 즉 target `+26.681319°`; 다른 arm Goal/그리퍼 Goal은 **write하지 않는** 1 waypoint다. `-6 raw=-0.527473°`의 Present→target 폭은 attempt1의 start Wrist Present `2394`→post-stop Wrist Goal `2388`과 동일한 마지막 관측 수요 폭이다. 이보다 작은 수요가 loaded wrist를 움직였는지는 trace가 없어 알 수 없으므로 전역 최소·물리 해제 최소라고 주장하지 않는다. 기존 `2.0°` step cap보다 작고, 현 servo 범위 안이다. FK GRASP TCP Z는 `3.285876→3.867049 mm`, `+0.581173 mm`; 100분할 선형 관절 보간에서 Z가 매 구간 증가했다. 이 검사는 fingertip–table 실제 간극, 비동기 관절 응답, 접촉력, loaded tracking을 검증하지 않는다. 현재 독립 entrypoint write firewall은 5축 동시 Goal만 허용하므로 **이 1축 후보는 실행 준비가 아니다**. 이를 실행하도록 코드나 limit을 이번 턴에 수정하지 않았다.

```ini
CONTACT_RELEASE_ROOT_CAUSE = B (confirmed 2.0° step-guard abort; physical clearance threshold UNKNOWN)
RELEASE_CANDIDATE = OFFLINE_ONLY: Wrist Flex raw 2390→2384, 1 waypoint, other joints/gripper no Goal write
PREDICTED_TCP_Z_INCREASE = +0.581173 mm (FK only, contact release NOT_VERIFIED)
MAX_JOINT_STEP = 0.527473° from final Present; 0.351648° change from stored Flex Goal
MOTOR_COMMAND = 0
NEXT_LIVE_COMMAND = NONE
```

`CONTACT_RELEASE_ATTEMPT1=FAIL`, 자동 재시도 `0` 유지. 문서 변경 `NOT_COMMITTED/NOT_PUSHED`; 이슈 갱신 `NOT_RUN`.
