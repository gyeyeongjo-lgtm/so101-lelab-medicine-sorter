# 2026-10-07 수동 약통 위치 지정 경로

사용자가 수동으로 위치를 찍고 빠르게 분류·검증하는 방식을 제안했다. 현 한 클래스 약통 검출기는 A/B/C 신원을 구분하지 못하므로 사람이 라벨을 확인하는 형태로 범위를 제한했다. 자동 집기나 로봇 제어 기능은 추가하지 않았다.

- `IMPLEMENTED (repo only)`: `medicine_sort_dry_run.py`에 동일 비전 프레임의 클릭 픽셀·sequence, 신선도, ID0–3, 목표 ID4/5/6, 약통 상자 포함 여부를 검사하는 판정 함수를 추가했다. 겹친 두 약통 상자가 같은 물체 후보일 때는 IoU로 중복을 식별한다. 결과는 목적지 마커 ID/색만 내며 `robot_enabled=false`, `motion_authorized=false`, `robot_coordinates_included=false`다.
- `IMPLEMENTED/PASS (temporary live)`: 읽기 전용 YOLO 페이지에 원자적 JPEG+상태 프레임 고정과 A/B/C 수동 선택·클릭 판정 UI를 추가했다. 라벨 기본값은 미선택이므로 사용자 신원 확인 없이 목적지를 표시하지 않는다. 브라우저 판정은 저장·모터 명령을 하지 않는다. Mac 8031 임시 페이지에서 브라우저 클릭을 검증했다. 상시 서비스 설치는 `NOT_RUN`이다.
- `PASS (offline evidence)`: Git 제외 10월 7일 저장 정면 640×480 JPEG에 ArUco ID0–6이 모두 검출된다. 예시 픽셀 (320,240)은 기존 오프라인 한 클래스 검출의 겹친 두 상자 안에 있다. 오래된 이 프레임을 라이브 목적지 승인으로 사용하지 않았다.
- `PASS (tests)`: `test_medicine_sort_dry_run` 7개와 `test_medicine_yolo_web` 10개, 총 17개 통과. Python 구문 검사·`git diff --check` 통과. 브라우저 JavaScript 실제 실행·하드웨어 검증 `NOT_RUN`.
- `CORRECTION (network sandbox)`: 최초 기본 실행 환경에서 8000/8030 연결 거부가 났으나 이는 실제 현장 중단을 뜻하지 않았다. 허용된 읽기 전용 조회에서는 Jetson 8000·8002 health 200, Mac 8030 정면/사선/손목 수신 신선·오류 null이다. 무비밀번호 SSH는 인증 거부라 원격 설정은 읽거나 변경하지 않았다.
- `FIRST FAILURE/RECOVERY`: Mac 임시 8021 포트는 이미 listen 중이라 사용하지 않았다. 비어 있는 8031에서 8000 MJPEG를 직접 구독하는 첫 시도는 정면 `camera source ended`, 사선 HTTP 503으로 실패했다. 정확한 임시 프로세스만 TERM 종료하고 8030의 기존 캐시 JPEG 두 채널만 주기적으로 읽는 방식으로 바꿨다. 새 8031의 health ok, 정면 age 0.202 s·약통 후보 1개·ID0–6, 사선 ok다. 8030 세 영상은 계속 신선하다.
- `PASS (browser UI)`: 프레임 고정이 실제 sequence를 표시했다. 약통 중심 약 (321,242) 클릭과 **시험용 A 선택**은 `DRY_RUN_ROUTE_ONLY`/ID6/blue와 중복 상자 2개를 표시했다. 이 선택은 현재 약통의 A 신원을 검증하지 않는다. 이후 UI 기본 선택을 빈 값으로 수정해 실제 A/B/C 미선택 클릭은 차단됨을 다시 확인했다.
- `NO MOTION`: 8000 텔레옵·녹화·추론 inactive, recording 내부 `current_phase=preparing`/`session_ended=false` 유지. 8030 `robot_control=false`, 8031 `robot_enabled=false`. 8020 서비스·카메라 장치·USB·토크·모터·LeLab 설정을 변경하지 않았다.

다음 현장 입력은 사용자가 현재 약통의 실제 A/B/C를 확인한 뒤 8031 화면에서 종류 선택→프레임 고정→약통 중심 클릭이다. 그 결과는 목적지 제안까지만 사용한다. 8031은 임시 서버여서 프로세스가 종료되면 재실행이 필요하다. 사람의 확인 없이 크기 라벨을 추측하지 않는다.
