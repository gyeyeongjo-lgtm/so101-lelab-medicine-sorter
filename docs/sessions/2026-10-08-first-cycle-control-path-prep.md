# 2026-10-08 C→빨강 첫 사이클 준비 — 기존 수동 명령 경로와 단계별 검증

## 근거 범위

- Mac 설치 `/Users/jogyeyeong/.local/share/uv/tools/lelab/lib/python3.12/site-packages/lelab/teleoperate.py` SHA-256 `2a54de453da35fb0d80bf37398ae3d2b0ed17dbbb56eea3077a71e7ab33931e2`는 앞서 2026-10-05 Jetson 설치 소스에서 기록한 SHA와 같다. 따라서 **그 시점의 동일 파일 코드 경로**를 직접 읽어 분석했다. Mac의 LeRobot `so_follower.py` SHA `d09a2e63...`, `motors_bus.py` SHA `ade55d42...`는 현재 Jetson 파일과 해시 대조 `NOT_VERIFIED`; 현재 Jetson 설치본 전체도 SSH 인증 실패로 재확인 못 했다. 이를 현재 Jetson 소스의 변경 없음으로 단정하지 않는다.
- [Jetson 파일 전용 수집 방법](../JETSON_STATIC_MODEL_COLLECTION.md)은 현재 URDF·관절 매핑·캘리브레이션과 leader/follower 명령 소스의 경로·해시/핵심 줄만 읽으며 포트·서비스·모터에 접근하지 않는다. 사용자가 출력 제공 예정이고 아직 결과 수신 전이다.

## 기존 수동 제어의 데이터·소유권 흐름

1. LeLab `handle_start_teleoperation`은 leader/follower 포트를 동기 연결하고 양쪽 calibration을 모터 메모리에 쓴 뒤 카메라와 모터를 설정한다. 그러므로 단순 시작도 하드웨어 상태 변경이며 현재 승인 범위에 없다. 기존 8000 텔레옵·녹화·추론 중복 시작은 차단한다.
2. leader `SOLeader.get_action()`은 버스 `sync_read("Present_Position")` 결과를 `<motor>.pos` 키로 반환한다. arm 다섯 축은 기본 `use_degrees=True`의 `DEGREES` 정규화 수치, gripper는 `RANGE_0_100`이다. 키는 `shoulder_pan`, `shoulder_lift`, `elbow_flex`, `wrist_flex`, `wrist_roll`, `gripper`이며 ID 1–6과 연결된다. 이 수치는 URDF rad 목표가 아니다.
3. 텔레옵 worker는 루프에서 `action = teleop_device.get_action()` 후 `robot.send_action(action)`을 호출한다. follower `SOFollower.send_action()`은 `.pos`를 벗긴 이름별 목표를 만들고, 기본 `max_relative_target=None`이므로 현재 설정상 상대 목표 clipping을 하지 않는다. 이어 `bus.sync_write("Goal_Position", goal_pos)`가 기본 normalize로 arm 도 목표를 raw step, gripper 0–100을 raw로 변환해 보낸다. `DEGREES` 역정규화는 calibration min/max clamp를 하지 않는다. sync write는 모터 응답 패킷이 없어 송신 성공만으로 실제 도달이 확인되지 않는다.
4. 별도 방송은 follower `get_observation()`의 `Present_Position`을 읽고 `shoulder_pan→Rotation`, `shoulder_lift→Pitch`, `elbow_flex→Elbow`, `wrist_flex→Wrist_Pitch`, `wrist_roll→Wrist_Roll`, `gripper→Jaw`로 변환해 `/ws/joint-data`에 약 20 Hz로 보낸다. arm 관측 도→rad 변환은 실제 명령 입력과 다른 **관측 경로**다. gripper의 0–100을 `Jaw` rad로 같은 숫자식 변환하는 부분도 모델 의미가 별도 검증되지 않았다. 기존 상태 방송만으로 leader 요청 목표·follower 송신 목표·도달 여부를 복원하지 않는다.
5. `handle_stop_teleoperation`은 `teleoperation_active=False`를 먼저 설정하고 worker를 최대 5초 join한다. worker가 그때도 살아 있으면 경고만 남기고 API는 success를 반환할 수 있다. worker `finally`가 장치를 disconnect하며 follower 기본 `disable_torque_on_disconnect=True`다. 따라서 **UI 종료 표시나 `teleoperation_active=false`, 심지어 stop API success만으로 버스 해제·토크 상태·팔 정지를 증명할 수 없다**. 종료 완료와 단독 버스 소유권을 별도로 확인하기 전 다른 제어 주체를 열지 않는다. 실제 중단 때는 현장 사용자의 팔/물체 안정 확인이 우선이다.

## 실행 연결부 준비 상태와 첫 단계별 시험

- 현재 저장소의 `simulate_fixed_slot_plan.py`는 모터 비접속 계획/상태기뿐이다. **실제 명령 송신 adapter는 없고, 검증된 C→ID4 전체 경로도 없다.** 미래 adapter에는 leader 동작의 단위/이름 계약을 맞춘 *독립 검증된 목표 데이터*, 현재 자세↔경로 시작점 오차, 속도·시간 제한, 경로 각 샘플의 모델/장치 한계와 자체·환경 충돌 여유, 한 버스 한 소유자, 송신 후 follower 관측 feedback/도달 판정과 즉시 중단을 연결해야 한다. 상태 방송 원본을 그대로 재생하지 않는다. `Goal_Position`에 직접 임의 값을 쓰는 시험도 이번에는 하지 않는다.
- **시작 조건**(실기 전 수치 합격선 확정 필요): C 한 모형만 고정 슬롯, 빨강 ID4 비움, 베이스·슬롯·바구니·카메라 기준 위치/허용 오차 확인, 다른 사람·도구 이동 범위 밖, 그리퍼 비움·현재 자세와 후보 경로 시작 자세 일치, 텔레옵/녹화/추론 및 다른 버스 소유자 없음, 즉시 중단 준비. 현재 model/calibration 정합과 경로 여유가 미검증이므로 자동 시동 `NOT_RUN`.
- **첫 승인 대상은 사용자 확인을 받는 수동·단계별 C→빨강 한 사이클**이다. 각 단계에서 멈춰 영상·현장 간섭과 관절/물체 상태를 확인한 뒤 다음 단계로 간다: (1) C 상공 접근·비접촉 간격, (2) 몸통 집기·안정적 들기와 테이블 이탈, (3) 빨강 테두리보다 높은 이동·입구 중앙 상공, (4) 바구니 바닥에 가볍게 놓고 개방·C 분리/잔류, (5) 열린 그리퍼 퇴피·바구니와 분리. 사진상 겹침은 현장 3D 간격 확인으로 보완하되 수치 여유 검증으로 과장하지 않는다.
- **실패/중단 조건**: 예상 밖 팔 움직임, grip 미확인/미끄러짐, 약통·손가락/하우징의 테이블·테두리·기존 물체 접촉·걸림, 바구니 입구/높이 여유 미확인, 상태/영상 stale, 시간 초과, 통신/버스 오류 중 하나면 다음 단계 금지. 사용자는 현장 절차로 팔·물체를 안정시키고 LeLab 텔레옵을 종료한다. 종료 화면만 믿지 않고 worker 종료/버스 소유권·팔 정지를 확인한다. 물체를 잡은 채 맹목적 복귀 명령을 보내지 않는다.
- 사람 확인 수동 한 사이클의 각 단계별 확인·종료 기록은 `HUMAN_CONFIRMED_MANUAL`; 실제 시스템이 feedback으로 집기·놓기·퇴피를 판별하고 중단/복구까지 독립 수행한 경우에만 `FULLY_AUTONOMOUS`다. 수동 성공·모의 성공을 후자로 승격하지 않는다. 현 단계는 계획 작성만, 신규 현장 동작/녹화/제어 `NOT_RUN`. 다음 수동 시험도 별도 범위·현장 확인·승인이 필요하다.

## 같은 바구니 재사용 수정·회귀

- 후속 요청에 따라 `simulate_fixed_slot_plan.py`의 카탈로그는 하나의 route ID가 복수 `occupancy_conditions`를 가질 수 있다. 각 점유 상태별 `clearance_verified=true`, `capacity_verified=true`, 별도 근거가 있어야 선택되며, 같은 route ID라도 두 번째 투입의 수용 가능성이 거짓이면 차단된다. 경로가 무조건 달라야 한다는 요구는 제거했으나 **현재 실물 검증 카탈로그는 여전히 비어 있다**. 테스트용 가짜 증거로 점유 0·1 동일 route ID 허용/두 번째 상태 미검증 시 차단을 확인했다.
- 고정 슬롯 파서 9개, 상태기 11개, 기존 약통 미리보기 7개 = **27개 하드웨어 없는 테스트 통과**. 설치 소스·Jetson 설정·모터·토크·USB·서비스 변경 `NOT_RUN`; 실제 구동 승인 아님. GitHub 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.
