# 2026-10-08 C→ID4 단계별 프로그램 제어 연결부 — 하드웨어 비접속

## 수신한 Jetson 정적 출력

- 사용자가 Jetson에서 실행한 설치 Python 출력: LeLab 0.1.0, LeRobot 0.6.0. follower calibration `/home/jetson3/.cache/huggingface/lerobot/calibration/robots/so_follower/so-101.json` SHA-256 `2f74c1303b2fce03576eff539329e1185a652e2d551caa1ec82b026dafe29c2e`는 저장된 파생 경계의 원본 해시와 일치한다. 여섯 모터 ID 1–6/`drive_mode=0`/range·homing_offset 요약이 제공됐다. LeLab `teleoperate.py` SHA `2a54de45...e2`와 LeRobot `motors_bus.py` SHA `ade55d42...a688`도 기존 조사본과 일치한다.
- 설치 follower의 arm ID/이름은 shoulder_pan 1, shoulder_lift 2, elbow_flex 3, wrist_flex 4, wrist_roll 5이고 gripper 6. `SOFollower.send_action`은 `Goal_Position` sync_write, `max_relative_target` 기본 None. `SOLeader.get_action`은 `Present_Position`을 읽는다. LeLab 방송 매핑은 `elbow_flex→Elbow` 등 기존 조사와 일치한다. 하지만 출력에서 `_normalize`/`_unnormalize` 함수의 실제 식 부분과 **현재 URDF 경로/해시/limit 출력이 빠졌다**. 붙여넣기 원문 중간이 뒤섞였으므로 나머지 출력을 완전한 파일 감사로 간주하지 않는다.
- [Jetson 누락분 명령](../JETSON_STATIC_MODEL_COLLECTION.md)을 Python `hashlib.sha256()` 청크 읽기 방식으로 다시 작성했다. `hashlib.file_digest` 불필요. 출력에는 URDF 모델/코드 요약만 있고 비밀번호·키·전체 calibration은 포함되지 않는다. 설치 파일/서비스/모터 변경 `NOT_RUN`.

## 기존 수동 기록으로 알 수 있는 것과 없는 것

- 기존 C 수동 작업 및 빈 C→ID4 공중 경로에는 follower **관측** 관절 방송과 영상, 일부 사람이 보고한 접촉·간섭 없음이 있다. 빈 경로 2,319개 표본은 마지막 빨강 상공에서 120초 기록이 끝나 **퇴피가 포함되지 않았다**. `SOURCE_C_HOVER`와 `BASKET4_HOVER`의 별도 재현 자세도 이번 기록과 각각 최대 13.451°/5.011° 다르다.
- leader 요청 목표, follower에 실제 `send_action`이 반환한 목표, write 완료 시각, 각 목표 대비 새 feedback의 오차, 경로의 수치 충돌/테두리 여유, 프로그램 중단 후 실제 producer·write 종료는 기록되지 않았다. C를 든 영상 및 사용자 수동 성공은 프로그램 집기/놓기 확인 센서가 아니다. 따라서 기존 상태 방송을 재생 명령으로 쓰지 않는다.
- 추가 자료가 필요한 가설: 설치 URDF/정규화 식으로 모델-명령 영점/방향을 구분; 별도 검증된 목표 경로의 시작 자세/전체 연속점/배치·충돌 여유로 빈 구간과 실제 C 작업 경로를 구분; 사람 확인을 동반한 첫 프로그램 제어 시험에서 요청/실제 송신/새 follower 관측을 시간과 함께 기록해 도달·중단을 검증한다. 이 항목이 없어 단순 추가 수동 시연만으로 자동 승인하지 않는다.

## 새 실행부 계약과 테스트

- `scripts/staged_cycle_execution.py`: 실제 LeRobot/serial/HTTP import 또는 live adapter가 없는 하드웨어 비접속 연결부. 입력은 arm 5축 `deg`·gripper `0_to_100`의 별도 검증된 목표 배열. 단계는 `approach→grasp→transfer→place→retreat`; 각 단계마다 명시적 사람 승인과 앞 단계의 독립 결과 확인이 필요하다. 한 단계 안에서도 목표별로 송신 결과(`TRANSMITTED_UNACKNOWLEDGED`), follower 피드백 도달(`GOAL_REACHED`), 사람 작업 결과(`HUMAN_CONFIRMED`)를 구분한다. 실제 송신 목표가 clipping/변경되면 차단한다. 관절별 허용 오차·feedback 최대 age·안정 시간·목표 시간 제한은 생성자 필수 입력이며 현장 수치는 아직 미확정이다.
- 중단 요청은 새 명령 생산을 막는다. `command_stop_state=COMPLETED`는 worker 종료, in-flight 전송 없음, transport의 quiescent 확인이 모두 있어야 한다. 이때도 `arm_stop_state=NOT_VERIFIED`는 그대로 남는다. 토크 해제·맹목적 퇴피/재시작 코드는 없다. 실제 bus/LeLab producer 종료 및 별도 관절 피드백·현장 팔 정지 확인은 미완성이므로 **실제 중단 성능은 NOT_VERIFIED**다.
- 가짜 전송기 회귀: 기존 파서/모의 20개와 신규 7개, 합계 27개 통과. 새 검증은 단계 승인·송신/도달/작업 결과 분리, stale/오차 초과 feedback 타임아웃, clipping 거부, 경로 중간 목표 실패 후 다음 목표 차단, 송신 도중 stop pending→완료 확인, stop 후 무송신. 실제 구동·장비 배포 `NOT_RUN`.

## 첫 프로그램 제어 시험 전 필수 조건

1. 현재 설치 URDF와 normalize 식 누락분 수집·기존 범위/영점·방향의 정합 확인. 충돌 검사를 해제하거나 범위를 관측치까지 늘리지 않는다.
2. C→빨강 고정 배치의 베이스 상대 슬롯/바구니 오차, 현재 자세↔첫 목표 오차, 완결된 접근·집기·이동·놓기·퇴피 목표와 각 구간 관절/속도/환경·자체 충돌·물체/바구니 여유 검증. 기존 방송을 그대로 재생하지 않는다.
3. LeLab 텔레옵/녹화/추론과 충돌하지 않는 단일 버스 소유 live adapter, follower fresh feedback, 실제 producer/write 정지 증명, 물체를 든 상태의 안전 중단 절차. 수치 허용 오차·deadline·현장 성공/중단 조건을 시험 전 합의.
4. 사람·물체/배치 현장 확인과 C→ID4 단계별 프로그램 제어 1회에 대한 **별도 승인**. 각 단계 후 현장 확인 없이는 다음 단계로 가지 않는다. 결과는 `HUMAN_GATED_PROGRAM_CONTROL`로 기록하고 이전 수동 성공이나 완전 자동 성공과 구별한다.

원본 데이터·캘리브레이션·서비스/USB/모터·토크 변경 `NOT_RUN`; 실제 live 송신 `NOT_RUN`; `NOT_COMMITTED`, `NOT_PUSHED`.
