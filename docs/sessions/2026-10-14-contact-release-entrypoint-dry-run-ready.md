# CONTACT_RELEASE_ONLY — 독립 arm-only relative-start entrypoint 오프라인 준비

## 범위

현재 현장 상태는 arm supported/stopped, gripper-table 접촉이며 Torque 전 축 ON, Moving 전 축 0, Goal−Present 최대 4 raw, gripper Present `4.651%`이다. 이전 OFF→ON 상태 전환 주체는 `UNKNOWN`으로 유지한다. 이번 승인은 **offline/dry-run뿐**이며 실제 Goal/Torque/motor write, teleop, contact release는 금지다.

## 최소 연결

새 [entrypoint](../../scripts/contact_release_only.py)는 LeLab UI `/move-arm` 및 recorder/teaching 경로와 독립이다. 기존 `relative_start_teleop.py`의 `capture_origins`, `arm_only_relative_target`, `dispatch_guarded_relative_action(arm_only=True)`, servo range·기존 최대 2° arm step guard와 `temporary_elbow_direction_guard.py`를 재사용한다. follower/leader canonical USB·단독 ownership 확인 뒤 `bus.connect(handshake=False)`만 호출하고 설치 `write_calibration`/`configure`를 호출하지 않는다. follower/leader write firewall은 config/torque 쓰기를 거부하고, follower Goal은 **arm 5축** 키일 때만 열리며 gripper Goal은 재전송도 하지 않는다.

시작은 현 Goal raw `[2032,1642,2752,2396,1612,490]`, Present raw `[2028,1643,2754,2394,1612,489]` 기준으로 fail-closed다. Torque 전 축 ON/Moving 0, leader Torque OFF, 최고 온도 기존 `55°C` gate, 3초 정지, Goal 안정/Present 1 raw 이내, fresh leader/follower origin과 재확인을 거친다. first follower-origin Goal은 보내지 않는다. 명시적 현장 arm 확인 뒤에만 5축 상대 target을 허용한다. 현재 FK Z보다 올라가는 target만 전송하고 actual TCP Z가 시작보다 내려가거나 gripper Goal/Present가 바뀌면 ABORT한다. 정상 종료 시 추가 Goal 없이 세 번 read-only sample을 남긴다. SIGINT/SIGTERM은 즉시 명령 생산을 중단하고 torque를 변경하지 않은 채 포트를 해제한다. 이후 현장 접촉 해제 여부는 사용자가 판단한다.

## 오프라인 검증

- 로컬 `python3 -m unittest tests.test_contact_release_only tests.test_relative_start_teleop`: `24/24 PASS`. fake에서 3초/첫 Goal send `0`, 첫 arm 5축 전송에서 gripper key 제외, torque/config write 차단, leader 움직임/토크 이상/하강 target의 no-send abort, pre-arm stop과 arm 후 stop을 확인했다.
- 로컬 기본 CLI dry-run, py_compile, `git diff --check` PASS. dry-run은 LeRobot live class/serial을 열지 않고 `serial_open=0`, motor/Goal/Torque/gripper write `0`, recorder/teaching/inference/replay false를 출력한다.
- Jetson 격리 폴더 `/home/jetson3/so101-contact-release-20261014/`에 entrypoint와 필요한 기존 순수 모듈·fake test만 배치했다. 설치 Python `3.14.7`에서 fake `7/7 PASS`, 기본 dry-run PASS. 최종 entrypoint SHA는 로컬/Jetson 모두 `3163094e…d06721`이다. 기존 pinned URDF/GRASP TCP JSON을 오프라인 로드해 FK 계산이 작동함을 확인했다. LeLab 설치 소스, 서비스, env, recorder ticket은 수정하지 않았다.
- Jetson 실제 설치 `SO101Follower.send_action`는 입력 action의 `.pos` 키만 Goal로 매핑하므로 arm-only 5축 action에 gripper를 자동 추가하지 않음을 소스로 확인했다. 실제 hardware connection/serial start는 하지 않았다. 종료 뒤 LeLab teleoperation/recording/inference inactive, privileged leader/follower USB 무점유다.

```ini
CONTACT_RELEASE_ENTRYPOINT = PASS (offline/Jetson fake only)
TORQUE_WRITE = 0
GRIPPER_WRITE = 0
FIRST_GOAL_SKIPPED = PASS (fake)
ARM_ONLY_RELATIVE = PASS (fake)
MOTOR_COMMAND = 0
LIVE_CONTACT_RELEASE = NOT_RUN
NEXT_LIVE_COMMAND = RUN CONTACT RELEASE ONLY
```

실기 전에는 별도 사용자 승인과 현장 팔 지지·접촉·즉시 중단 준비 재확인이 필요하다. live 시작 시 baseline, leader passive, port ownership, 3초 stillness, FK 상승방향 중 하나라도 어긋나면 명령 없이 중단한다. 정상/실패 여부와 무관하게 자동 재시도하지 않는다. 원본 로그·비밀번호·키는 커밋하지 않는다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
