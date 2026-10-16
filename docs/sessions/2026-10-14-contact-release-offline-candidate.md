# CONTACT_RELEASE_ONLY — fresh 3회와 arm-only relative-start 오프라인 후보

## 범위와 read-only preflight

사용자는 현재 gripper/table 접촉을 보고했다. teaching/gripper open/일반 `/move-arm`은 시작하지 않는다. Jetson user LeLab teleoperation/recording/inference API는 모두 inactive였고 canonical follower `/dev/ttyACM1`의 USB serial은 `5AE6058306`, privileged `fuser`는 무점유였다. 기존 `read_follower_pose_telemetry.py` SHA `7c440b81…f3c56`과 설치 Python `3.14.7`로 0.2초 간격 정확히 3회 read-only 측정했다. 세 표본은 모든 항목에서 동일했다.

| 축 | Present raw | Present °/% | Goal raw | Goal °/% | Goal−Present raw | Goal−Present °/pp | Torque | Moving | °C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pan | 2028 | −6.461538° | 2032 | −6.109890° | +4 | +0.351648° | 1 | 0 | 35 |
| Lift | 1643 | −27.384615° | 1642 | −27.472527° | −1 | −0.087912° | 1 | 0 | 35 |
| Elbow | 2754 | +67.736264° | 2752 | +67.560440° | −2 | −0.175824° | 1 | 0 | 34 |
| Flex | 2394 | +27.560440° | 2396 | +27.736264° | +2 | +0.175824° | 1 | 0 | 34 |
| Roll | 1612 | −22.197802° | 1612 | −22.197802° | 0 | 0° | 1 | 0 | 34 |
| Gripper | 489 | 4.651163% | 490 | 4.712362% | +1 | +0.061200 pp | 1 | 0 | 38 |

이전 read-only 표본에서는 Present raw `[2032,1642,2752,2396,1612,490]`, Goal 전 축 `0`, Torque 전 축 `0`이었다. 뒤따른 Goal-only 실행은 `torque_not_all_off` gate에서 Goal write 전에 종료했다. 현재 Goal raw가 이전 Present raw와 정확히 같고 Torque 전 축 ON이 된 시점·주체는 알 수 없다. 그 변화를 이 작업의 성공으로 귀속하지 않는다. 이번 턴의 원본 측정 로그는 커밋하지 않았으며 실제 손가락 접촉 상태는 사용자의 현장 보고다.

## 설치 경로의 contact 위험

현재 LeLab 8000은 `relative_start + empirical_relative_teaching` trace 환경이 남아 있다. `/move-arm`은 trace root가 있으면 pre-connect JSON을 요구하며 현재 JSON 미설정/소진 ticket으로 fail-closed될 수 있다. recorder를 끄고 일반 relative-start로 시작하더라도 설치 worker의 `relative_target`은 그리퍼 포함 6축 목표를 보낸다. 기존 arm-only 함수와 5축 guarded dispatch는 **empirical trace가 있을 때만** 선택된다.

더 중요하게 `handle_start_teleoperation`은 follower/leader 연결 뒤 follower calibration write와 `robot.configure()`를 실행한 후 relative origins를 캡처한다. 실제 설치 `SO101Follower.configure()`의 `bus.torque_disabled()`는 전 축 Torque OFF 후 ON을 보장하고, 그리퍼 register 설정도 쓴다. 현재 테이블 접촉 중 그 짧은 토크 해제도 의도하지 않은 자세 변화를 일으킬 수 있다. 따라서 일반 `/move-arm`은 CONTACT_RELEASE_ONLY 요구를 충족하지 않는다.

## 오프라인 최소 후보 (아직 실행 불가)

기존 `relative_start`의 `capture_origins`, `arm_only_relative_target`, `dispatch_guarded_relative_action(..., arm_only=True)`, servo range와 기존 2° step guard를 재사용한다. 로컬 `tests.test_relative_start_teleop`은 `17/17 PASS`로 arm-only dispatch에서 그리퍼 key가 빠짐을 확인했다. 단, 이는 순수 함수 테스트이며 전체 startup/hardware 검증이 아니다.

1. 별도 contact-release 선택에서 recorder/teaching/inference/replay를 OFF로 하고 singleton leader/follower bus ownership을 확보한다.
2. follower·leader를 **쓰기 없는 연결**로 열고, 기존 calibration이 메모리에 로드됐는지 확인한다. follower `write_calibration`·`configure`와 leader `configure`는 호출하지 않는다. 현재 torque/Goal/Present가 pre-connect와 일치하지 않으면 Goal 없이 ABORT한다. leader가 손으로 움직일 수 있는 상태인지 별도 확인한다.
3. leader 3초 정지와 follower Present/Goal/Torque/Moving 안정 확인 뒤 fresh relative origins를 잡는다. 기존 일반 worker의 첫 follower-origin Goal 전송은 생략한다. gripper Goal raw는 기존 값으로 유지하고 **그리퍼 key를 어떤 `send_action`에도 포함하지 않는다**. gripper Present가 변하거나 목표가 예상 외로 변하면 ABORT한다.
4. 사용자가 leader를 천천히 들어올릴 때 기존 arm-only 5축 dispatch만 사용한다. 첫 action은 상승 방향/작은 변화임을 FK·fresh feedback으로 검증하고 기존 최대 arm step을 유지한다. 실제 TCP Z 하강·contact 악화·예상 밖 관절 움직임·feedback/온도/토크 오류 시 즉시 중단한다. contact 해제 현장 확인 즉시 teleop 종료, 포트 해제, follower 3회 read-only 재측정한다.

이 순서는 **후보 설계**다. 설치 worker에 contact-release 전용 분리 분기는 아직 없고, full startup fake/dry-run·Jetson 배치·leader 상태 확인·이전 상태 전환 원인 확인도 하지 않았다. 따라서 지금 `CONTACT_RELEASE_MODE_READY=FAIL`, 현재 일반 `/move-arm`에서 `GRIPPER_FROZEN=NO`, 다음 live command `NONE`이다. 임의로 Torque OFF 수동 이동 또는 gripper command를 하지 않는다.

이번 턴 Goal/Torque/motor write, 서비스 수정/재시작, live teleop `0`. 측정 뒤 privileged leader/follower fuser 무점유, SSH 종료. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
