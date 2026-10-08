# 2026-10-08 URDF 제한 불일치 오프라인 조정 검토

## 범위·근거

- 사용자께서는 C 수동 투입의 현장 간섭 여유를 직접 확인했고, URDF 제한을 무시할 수 있는지 검토해 달라고 요청했다. 이 보고는 **해당 수동 1회에서 관찰한 물체 간섭**에 관한 증거로 받아들이며, 관절의 물리 하드스톱·부하 중 여유 실측과는 구분한다.
- 설치 URDF SHA `443d38d7...f67236`의 [날짜별 제한 스냅샷](../../configs/so101_installed_urdf_limits_20261005.json), follower 캘리브레이션 파일 SHA `2f74c130...e29c2e`의 [파생 스냅샷](../../configs/so101_follower_calibration_bounds_20261008.json), 이전 승인된 follower Elbow/Wrist_Pitch 장치 레지스터 읽기, 현 C 수동 기록 1,198개를 읽기 전용으로 비교했다. 이번에는 Jetson 시리얼·모터·토크·서비스·URDF 파일을 열거나 변경하지 않았다.
- 기존 감사기를 처음 파일 경로로 직접 실행하니 `ModuleNotFoundError: scripts`였고, 동일 코드를 `.venv/bin/python -m scripts.audit_calibration_trace_envelope`로 실행해 성공했다. 아래 값은 설치 LeRobot `DEGREES` 정규화식에 따른 **캘리브레이션 파일 범위**이며 실제 안전 동작 범위가 아니다.

## 같은 단위의 대조 (도)

| 관절 | 설치 URDF | 캘리브레이션 파일 | 현 C 기록 관측 | 해석 |
| --- | ---: | ---: | ---: | --- |
| Rotation | ±110.000 | ±118.374 | −7.077…+22.813 | 현 기록은 두 범위 안 |
| Pitch | ±100.000 | ±101.846 | −98.242…+47.868 | 현 기록은 두 범위 안 |
| Elbow | −100.000…+90.000 | ±97.011 | −60.176…+96.571 | URDF 상한 +6.571 초과; 파일 상한 여유 0.440 |
| Wrist_Pitch | ±95.000 | ±100.615 | +35.824…+100.264 | URDF 상한 +5.264 초과; 파일 상한 여유 0.352 |
| Wrist_Roll | ±160.000 | ±156.352 | −17.011…−1.802 | URDF가 파일보다 오히려 3.648 넓음 |

- 이전 **장치 레지스터** 읽기에서 Elbow raw 880–3087, Wrist_Pitch raw 936–3225는 위 캘리브레이션 파일과 일치했다. 나머지 세 관절의 현재 장치 레지스터 및 모든 관절의 물리 하드스톱·동적 여유는 `NOT_VERIFIED`다. 현 기록은 파일 범위 초과 0건이지만 Elbow 856/1,198개, Wrist_Pitch 12/1,198개가 파일 경계 1° 이내다. 1°는 진단 폭이지 정해진 안전 규격이 아니다.
- 시작 관절 방송부터 Elbow는 +96.571°로 URDF 상한보다 6.571° 높고 파일 상한에 0.440° 남았다. 즉 URDF 경고가 단지 투입 중 한 프레임의 순간 오류는 아니다. 반대로 설치 URDF를 일괄 무시하면 Wrist_Roll처럼 더 느슨한 항목을 자동 경로에서 놓칠 수 있다.
- 단순한 민감도 예시로 파일 경계에서 1°를 빼면 현 관측 최대 Elbow는 그 가상 경계를 0.560°, Wrist_Pitch는 0.648° 초과한다. **1°를 새 안전 마진으로 채택한 것이 아니며**, 캘리브레이션 최대값을 그대로 URDF 목표 상한으로 복사해도 기록 경로에 검증된 여유가 생기지 않는다는 설명이다.

## 설치 실행 경로 확인 (읽기 전용)

- Jetson의 현재 `lelab.service`는 Python 3.14.7의 설치 LeLab 0.1.0/LeRobot 0.6.0을 `uvicorn lelab.server:app`으로 실행한다. 설치 `lelab/teleoperate.py`의 수동 worker는 `teleop_device.get_action()`→`robot.send_action(action)`을 호출한다. 그 파일의 URDF 관절명 매핑은 `robot.get_observation()` 값을 rad로 바꿔 WebSocket에 방송하는 부분이다. **검사한 수동 명령 경로에는 URDF 상·하한 검사가 없다.** 따라서 현재 수동 텔레옵이 URDF 밖에서도 동작했다는 관찰과 모순되지 않는다.
- 설치 `SOFollowerConfig.max_relative_target` 기본값은 `None`이고, LeLab 수동 시작 경로는 이를 별도 지정하지 않는다. 설치 `SOFollower.send_action()`의 상대 목표 제한은 이 값이 `None`이 아닐 때만 실행된다. 이어서 `bus.sync_write("Goal_Position", ...)`로 보낸다.
- 설치 `MotorsBus._unnormalize()`의 `DEGREES` 분기는 각도를 raw 정수로 변환하지만, 같은 함수의 `RANGE_M100_100`·`RANGE_0_100` 분기와 달리 캘리브레이션 min/max로 clamp하지 않는다. `sync_write()` 코드에도 별도 URDF·파일 상한 검사가 보이지 않는다. 이는 **검사한 Python 소프트웨어 경로**에 대한 결론이다. 모터 내부 펌웨어가 범위 밖 명령을 거부·포화하는지, 명령 손실 여부, 실제 정지 위치는 이번 읽기 전용 점검으로 확인하지 않았다.
- 이 사실은 URDF 파일을 지우거나 follower 설정을 바꾸라는 뜻이 아니다. 현재 수동 경로에는 애초 URDF 제한이 명령 게이트가 아니므로, URDF만 무시/수정해도 자동 실행의 부족한 소프트웨어 제한·좌표·경로 검증은 해결되지 않는다.
- 설치 `lelab/rollout.py`에서 `send_action`/URDF 텍스트 직접 참조는 찾지 못했다. 이것만으로 추론 내부의 제한 동작을 확정하지 않으며, 실제 추론은 `NOT_RUN`이다. 소스 조회 후 실제 8000 상태 API에서 텔레옵·추론은 모두 inactive였다.

## 판정·진행 방법

- `PASS (offline explanation)`: 설치 URDF는 실제 LeLab follower 캘리브레이션/장치 제한과 정합하지 않는다. 수동 텔레옵 성공·사용자의 현장 무간섭 보고를 오류로 취급하지 않는다. URDF 불일치를 자동 경로 설계의 **진단 경고**로 분리하여 오프라인 비전·분류·좌표 연구는 계속할 수 있다.
- `BLOCKED (automatic motion)`: 현재 제한을 전부 무시하거나 캘리브레이션 파일 끝값으로 URDF를 즉시 넓히는 것은 승인하지 않는다. 두 관절은 파일 끝까지 0.5° 미만이고 파일/장치 제한은 물리 하드스톱이나 동적 여유의 증명이 아니다. 다른 제한인 TCP/World→Base, 실제 바구니 입구·연속 경로도 해결되지 않았다. `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`; 자동 재생·새 모터 이동 `NOT_RUN`.
- 다음에는 **자동 제어 코드에만 적용할 별도 명령 제한 설계**를 오프라인으로 검토하되, 하드스톱/동적 여유가 미측정이므로 제한 수치나 안전 마진을 임의 확정하지 않는다. 물리 장치 제한을 바꾸거나 실제 이동 시험을 하려면 별도 현장 안전 확인과 구체적인 한 번의 승인 범위가 필요하다.
- GitHub 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`. 원본 관절 기록·캘리브레이션 파일·자격증명은 커밋하지 않는다.
