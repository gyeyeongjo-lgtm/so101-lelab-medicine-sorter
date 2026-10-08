# 2026-10-08 고정 위치 다중 목적지 명령 — 모의 실행만

## 확정된 범위

- 사용자는 픽업 슬롯 A/B/C와 빨강 ID4·초록 ID5·파랑 ID6 바구니 위치 고정, 명령별 목적지 변경, 한 바구니에 복수 약통 순차 투입, 2026-10-17 마감을 확정했다. C→빨강은 첫 실기 검증 조합일 뿐 최종 목적지를 고정하지 않는다. 이번 지시는 실제 모터/토크/제어 서비스/안전 설정 변경 또는 구동 승인이 아니다.
- 기존 `scripts/medicine_fixed_slot_command.py`의 명령 파서·고정 슬롯/마커 미리보기를 재사용했다. 새 `scripts/simulate_fixed_slot_plan.py`는 **로봇 제어 import가 없는** 순수 모의 계획/이벤트 상태기다. 설치 LeLab·카메라·USB·모터에 접근하지 않았다. 실제 장비 배포 `NOT_RUN`.

## 추가한 실행 구조와 모의 결과

- `A, B를 빨강에 넣고 C는 파랑에 넣어라.` → 순서 `A→red/ID4`, `B→red/ID4`, `C→blue/ID6`. 첫 빨강 전 점유 0, 두 번째 빨강 전 점유 1, 파랑 전 점유 0의 **각 점유 조건**을 검사한다. 두 상태의 테두리/기존 약통 여유와 수용 가능성이 모두 검증된 동일 경로는 재사용할 수 있다. `C는 파랑에 넣어라`만 입력하면 A/B 작업은 만들지 않는다.
- 구문은 알 수 없는 라벨, 지원하지 않는 목적지, 동일 대상 중복, 동일 대상의 상충 목적지를 거부한다. 정면 snapshot의 요청 약통 누락·마커/색 매핑 불일치·오래된 프레임도 기존 미리보기 게이트에서 차단된다. 레이아웃 ID와 초기 바구니 점유가 없으면 계획을 차단한다. 경로 목록에 `validated_full_cycle=true`, 비어 있지 않은 ID·근거, 현재 점유 조건의 `clearance_verified`·`capacity_verified`와 근거가 없으면 **전체 계획**은 `BLOCKED`다.
- 현재 실제로 검증된 A/B/C×바구니 전체 경로 카탈로그는 **없다**. 빈 카탈로그 모의 실행에서 세 작업은 순서를 표시하되 모두 `BLOCKED_UNVERIFIED_ROUTE`; `motion_authorized=false`. 테스트 전용 가짜 카탈로그로 상태기를 구동하면 `READY→RUNNING→SUCCEEDED` 전이가 가능하지만 출력은 항상 `simulation_only=true`, `robot_enabled=false`, `motion_authorized=false`다.
- 모의 첫 작업 `timeout` 또는 `failure` 결과는 `FAILED`, `stop`은 `STOPPED`, 집기·놓기·퇴피 중 하나라도 완료 근거가 없는 `completed`는 `USER_CONFIRMATION_REQUIRED`/`UNVERIFIED`다. 어느 경우도 두 번째 작업을 자동 시작하지 않고 첫 이벤트 1개만 소비하며 나머지 작업은 `READY`로 남는다. 성공은 세 근거가 **합성 이벤트에서** 모두 참일 때의 모의 상태일 뿐 실제 집기 성공 주장이 아니다.
- 새 테스트 첫 호출은 괄호 오타로 SyntaxError가 났고 즉시 수정했다. `start` 합성 이벤트 뒤 `RUNNING` 상태를 별도로 관찰하고 중단할 수 있게 보강했다. 후속 요구에 따라 같은 route ID가 점유 0/1 양쪽에서 `clearance_verified`·`capacity_verified` 근거를 갖는 경우 재사용하도록 바꿨다. 고정 슬롯 파서 9개·상태기 11개·기존 약통 분류 미리보기 7개 = **27개 통과**. `git diff --check` 통과. 테스트용 가짜 경로·장면은 실기 증거가 아니다.

## 모델 정합과 첫 사이클 필수 조건

- 모델 설치 파일은 Mac의 Jetson SSH 재시도에서 `Permission denied (publickey,password)`로 현재 직접 읽지 못했다. [Jetson 터미널 파일 전용 수집 명령](../JETSON_STATIC_MODEL_COLLECTION.md)을 마련했다. URDF 절대경로/SHA/관절 원점·축·제한, 설치 LeLab/LeRobot 이름 매핑·변환 코드, calibration의 motor ID·raw 범위·`homing_offset`·`drive_mode`만 수집한다. 비밀번호·개인키·원본 calibration 전체는 요청하지 않는다. 정수 step 일치는 물리 영점·회전 방향·스케일·이름 매핑의 완전 검증이 아니다. 초과 표본 삭제·관절 한계 확대 `NOT_RUN`.
- 첫 C→빨강 자동 한 사이클에는 현재 설치 모델 정합, 베이스·고정 슬롯/바구니 배치 허용 오차, 현재 관절 자세와 **검증된 명령 경로의 시작 자세** 일치, 접근→집기→이동→놓기→퇴피 전 구간, 관절/충돌 여유와 중단·타임아웃 후 정지, 집기·놓기·퇴피의 실제 확인 수단이 필요하다. **관측 상태 방송을 명령 궤적으로 재생하지 않는다.** 현재 이 경로는 검증 카탈로그에 등록되지 않아 실행 불가다. 실기 전 성공/중단 조건과 수치 허용 범위를 제시하고 현장 확인·구체적 1회 승인 필요.
- 이후 각 요구 A/B/C×목적지 조합은 독립 경로 검증이 필요하고, 동일 바구니 두 번째 약통은 `occupancy_before=1`의 입구·기존 약통 간섭/용량/완료 확인을 따로 통과해야 한다. **경로가 반드시 달라야 한다는 뜻은 아니다.** 고정 배치는 World→Base/TCP/IK를 첫 관절 경로 방식의 필수 조건으로 만들지 않지만 베이스 상대 위치와 경로 검증을 면제하지 않는다.
- 이번 변경은 저장소 구현+모의 테스트만. Jetson 배포 `NOT_RUN`, 실제 자동/수동 동작 `NOT_RUN`, 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED`, 원격 push `NOT_PUSHED`.
