# 2026-10-08 관절 제한 출처·모델 정합 검토 (읽기 전용)

## 결론과 증거의 종류

- 실제 SO-101이 사용자 수동 텔레옵에서 움직인 사실과 `URDF_LIMIT_MISMATCH`는 모순되지 않는다. 후자는 `scripts/audit_teleop_trace.py`가 **follower 상태 WebSocket 방송값**을 2026-10-05에 읽은 설치 URDF 제한 스냅샷과 사후 비교해 만든 상태 문자열이며, LeLab·MoveIt·모터의 거부 예외가 아니다. 로봇에 보낸 목표값은 해당 기록에 없고, 이 값들을 요청 목표라고 부르지 않는다.
- 최신 빈 C→ID4 공중 경로 `.local/teleop-traces/20261008T101705_984660Z_307d6026/`의 해시 검증된 2,319개 중 `Elbow` 403개가 URDF 상한 `+1.5708 rad`(+90.000°) 초과. 관측 최대 `+1.6333213087894185 rad`(+93.582418°), 초과 `0.062521 rad`(+3.582418°). URDF 하한은 `−1.74533 rad`(−100°). 초과는 시작 0–20.773초의 초기 자세·동작 시작 경계에 한정된다. 다른 5축 초과는 0건. 감사기 출력 상태는 정확히 `URDF_LIMIT_MISMATCH`, 프로세스 exit 2이며 관절별 controller error message는 기록되지 않았다.
- 앞선 실제 C 수동 투입 `.local/teleop-traces/20261008T054514_308947Z_6d3884df/`에는 `Elbow` 최대 `+1.6854893919259524 rad`(+96.571429°, URDF보다 +6.571429°), `Wrist_Pitch` 최대 `+1.7499323181534354 rad`(+100.263736°, URDF +1.65806 rad/+95°보다 +5.263736°)가 방송됐다. 상한 초과는 각각 945/1,198개, 19/1,198개다. 이 역시 명령 목표/드라이버 거부가 아닌 관측치다.

## 제한의 출처와 변환

- 저장소에 Xacro·MoveIt `joint_limits.yaml`은 발견되지 않았다. 스냅샷의 출처는 Jetson 설치 `frontend/dist/so-101-urdf/urdf/so101_new_calib.urdf` (2026-10-05 SHA-256 `443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236`)다. 2026-10-08 현재 설치 파일 자체의 재해시는 SSH 인증 거부로 `NOT_VERIFIED`. MoveIt이 시스템 어디에도 없다고 단정하지 않는다.
- 기존 읽기 전용 설치 소스 조사에서 LeLab 0.1.0/LeRobot 0.6.0의 수동 경로는 leader `get_action()`→follower `send_action()`→`Goal_Position`; 조사한 경로에는 URDF/MoveIt·충돌·IK 검사 호출이 없었다. `max_relative_target=None`이고 `DEGREES` 역정규화에는 calibration min/max clamp가 없다. 따라서 **이번에 확인된 실패는 오프라인 URDF 범위 대조**이지 MoveIt planning 실패·충돌 판정·IK 실패·컨트롤러 거부가 아니다. 다른 자동 실행 경로 전체의 동작은 `NOT_VERIFIED`.
- follower 파일의 `Elbow` raw 880–3087, `Wrist_Pitch` 936–3225는 이전 현장 승인하에 읽은 각 모터 id 3/4의 위치 제한 레지스터와 일치했다. 설치 STS3215 4096-step 및 `degrees=(raw−midpoint)×360/4095`에 따르면 파일 상한은 각각 +97.010989°/+100.615385°. 최신 빈 경로 `Elbow` 최대는 같은 식의 raw 3048, 앞선 C 투입 최대는 `Elbow` raw 3082·`Wrist_Pitch` raw 3221에 정확히 대응한다. 이는 rad↔deg 수치 정합의 증거이지 기계적인 영점·회전 방향·하드스톱·부하 여유의 독립 검증은 아니다. 앞선 C 최대는 파일/장치 상한까지 raw 5/4 step뿐이다.
- 설치 LeLab 관절 방송 소스에서 follower `elbow_flex`→URDF `Elbow`와 도→rad 변환은 이전에 확인됐다. 물리 버스 표의 id 매핑은 `shoulder_pan` 1, `shoulder_lift` 2, `elbow_flex` 3, `wrist_flex` 4, `wrist_roll` 5, `gripper` 6이다. 나머지 URDF 이름과 모터 이름의 전체 연결, 각축 homing offset·drive mode·URDF axis 부호와 실제 양의 회전 방향은 **현재 설치 소스·실물 동시 확인이 없어 `NOT_VERIFIED`**. `Jaw`는 팔 5축과 다른 정규화 방식이다.

## 변경안과 검증 순서

- **이번 변경 전→후는 동일**: 설치 URDF `Elbow` −100…+90°, `Wrist_Pitch` −95…+95°, `Wrist_Roll` −160…+160°; calibration 파일 Elbow ±97.010989°, Wrist_Pitch ±100.615385°, Wrist_Roll ±156.352°(각도 반올림). URDF가 팔꿈치·손목 pitch에서는 더 좁고 손목 roll에서는 더 넓다. URDF 전부 제거하거나 calibration 끝값을 새 자동 목표로 복사하지 않는다.
- 제조사의 **SO-101 조립체 관절 허용 범위**, 현재 하드스톱/케이블/툴·하중을 포함한 검증된 운용 범위가 로컬 근거에 없어 새 숫자를 확정할 수 없다. 제조사 모터 단품 사양만으로 조립체의 충돌 없는 범위를 대체할 수도 없다. 두 근거와 전체 이름/영점/부호 매핑이 확인된 경우에만 개별 관절 URDF 및 별도 planning 설정 중 실제 오설정된 항목을 수정하는 안을 제시한다. 해당 변경은 시각화/FK/계획 가능 범위에 영향을 주지만 이미 확인한 LeLab 수동 제어 경로를 제한하지 않는다. 드라이버·장치 제한은 별도 검토 대상으로 남긴다.
- 순서: (1) 설치 URDF/설정·원본 제조사 자료를 읽기 전용 재확인, (2) 변경 전후 각각 별도 사본에서 단위·영점·방향·관절명/한계 정적 검사, (3) 실제 툴/바구니 지오메트리가 있는 하드웨어 없는 시뮬레이션에서 FK·IK·자체/환경 충돌·연속 경로 여유와 기존 정상 자세 회귀 검사, (4) 수치·영향·시험 로그를 제시해 사용자에게 **별도 현장 확인·구체적인 실제 1회 구동 승인**을 받은 뒤에만 하드웨어 시험. 현재 (1) 일부와 관측 trace 대비 정적 한계 검사만 완료; (2) 수정본 없음, (3) 완전 시뮬레이션 `NOT_RUN`, (4) 실제 이동 `NOT_RUN`.
- 첫 단위 시험 호출은 `tests`가 패키지가 아니어서 3개 ImportError로 실패했고, discover 방식으로 재실행한 감사 6·calibration 6·FK 3 = 15개 통과. Jetson SSH 읽기 전용 접속은 sandbox 기본 권한 오류 뒤 승인된 네트워크 재시도에서 `Permission denied (publickey,password)`; 비밀번호를 명령/출력에 넣지 않았다. 설치/설정/모터/토크/USB 변경 `NOT_RUN`. GitHub 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.
