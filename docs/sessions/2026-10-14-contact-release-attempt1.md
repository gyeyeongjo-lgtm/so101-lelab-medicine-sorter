# CONTACT_RELEASE_ONLY 실기 1 — step guard ABORT, 접촉 유지

## 승인과 실행 범위

사용자 `RUN CONTACT RELEASE ONLY`와 현장 팔 지지·주변 clear·정지·즉시 중단 준비 확인을 받은 뒤, Jetson의 독립 `contact_release_only.py`를 1회 시작했다. 이는 LeLab UI 일반 텔레옵이나 C approach teaching이 아니다. recorder/teaching/inference/replay는 시작하지 않았다. 자동 재시도는 하지 않았다.

실행 전 LeLab teleoperation/recording/inference는 모두 inactive, canonical leader `/dev/ttyACM0=5AE6085272` 및 follower `/dev/ttyACM1=5AE6058306`이었다. privileged `fuser`에 두 포트 점유가 없었다. follower read-only 3회는 Present raw `[2029,1643,2755,2394,1612,489]`, Goal raw `[2032,1642,2752,2396,1612,490]`, Torque 전 축 `1`, Moving 전 축 `0`, Tmax `36°C`로 동일했다. 설치 파일 SHA `3163094e…d06721`과 기존 URDF/GRASP TCP SHA 일치를 확인했다.

전용 스크립트의 현장 확인 후 3초 정지 gate는 `STARTUP_STILLNESS_PASS`였다. fresh origin과 첫 Goal 생략 후 `CONTACT_RELEASE_ARMED`가 출력됐다. 사용자에게 리더로 위쪽 최소 이동을 안내했다. 실행은 `CONTACT_RELEASE_ABORT:RuntimeError:arm_step_exceeds_existing_guard`에서 종료됐다. **이 오류 이전에 팔 Goal은 1회 이상 전송됐다.** 종료 뒤 Goal raw가 `[2046,1642,2750,2388,1612,490]`으로 바뀐 것이 증거이며 정확한 전송 횟수는 기록되지 않았다. 이전 안내에서 “모터 명령 없이 종료”라고 말한 것은 틀려 즉시 정정했다. 그리퍼 Goal은 `490`으로 유지, Torque 전 축 ON이었다. write firewall은 gripper/torque/config write를 금지하며 실제 readback도 그리퍼 Goal·Torque 불변을 보였다.

종료 후 별도 read-only 3회는 Present raw `[2036,1643,2755,2390,1612,489]`, 위 Goal raw, Moving 전 축 `0`, Torque 전 축 `1`, Tmax `36°C`로 동일했다. 시작 대비 Pan Present `+7 raw`, Wrist Flex `-4 raw`, 나머지 Present 변화 없음. privileged `fuser`는 두 포트 무점유였고 LeLab teleoperation도 inactive였다. 사용자 현장 답변은 **`정지·아직 접촉`**이다. 물리 비접촉은 달성되지 않았다.

```ini
CONTACT_RELEASE = FAIL
PHYSICAL_NON_CONTACT = NO
MOVING = ALL_0 (post-stop read-only 3/3)
TORQUE = ALL_ON (post-stop read-only 3/3)
GRIPPER_WRITE = 0 (write firewall; Goal raw unchanged)
TORQUE_WRITE = 0 (write firewall; Torque unchanged)
ARM_GOAL_SEND = AT_LEAST_1 (exact count NOT_RECORDED)
GRASP = NOT_RUN
LIFT = NOT_RUN
AUTOMATIC_RETRY = 0
NEXT_LIVE_COMMAND = NONE
```

현장 접촉 유지 상태이므로 일반 `/move-arm`, teaching, gripper open 및 재시작은 승인하지 않는다. 원본 비밀번호·로그는 커밋하지 않는다. 이번 세션 문서와 상태 변경은 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`이다.
