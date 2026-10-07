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
- `ROI LIMIT`: 현재 약통 후보는 기존 픽업 ROI 밖이다. 목적지 제안 결과에 `pickup_roi_match=false`를 명시해, UI의 route-only 판정을 자동 집기 준비 완료로 오인하지 않게 했다.

다음 현장 입력은 사용자가 현재 약통의 실제 A/B/C를 확인한 뒤 8031 화면에서 종류 선택→프레임 고정→약통 중심 클릭이다. 그 결과는 목적지 제안까지만 사용한다. 8031은 임시 서버여서 프로세스가 종료되면 재실행이 필요하다. 사람의 확인 없이 크기 라벨을 추측하지 않는다.

## 추가: A/B/C 사진 저장 실패 확인과 로컬 저장 기능

- `FIRST FAILURE`: 사용자는 A/B/C를 위치·회전을 바꿔 여러 번 촬영했다고 보고했으나, 실제 조작은 기존 8031의 프레임 고정·약통 클릭이었다. 이 화면은 판정 결과만 표시했고 파일 저장은 하지 않았다. 작업 폴더 및 Mac 다운로드·바탕화면에서 신규 사진을 찾지 못했다. 이 시도의 저장 사진 수는 0이다.
- `IMPLEMENTED`: 별도 `사진·라벨 로컬 저장` 버튼과 선택적 `--allow-manual-capture` API를 추가했다. 서버는 고정 프레임 sequence·신선도·마커·검출 상자·A/B/C 라벨을 다시 검증한 후 동일 프레임의 주석 없는 원본 JPEG와 SHA-256·클릭점·판정 메타데이터를 `.local/medicine-manual-captures/`에 저장한다. 동일 sequence 중복은 거부하고, `FOR_REVIEW`/`training_ready=false`/`robot_enabled=false`/`motion_authorized=false`를 기록한다. 브라우저 재방문 시 라벨을 빈 값으로 초기화한다.
- `PASS (tests)`: 판정 7개·웹 11개 단위 테스트 총 18개, Python 구문 검사와 `git diff --check` 통과. 한 번의 잘못된 `unittest` 모듈 호출은 `tests` 패키지가 없어 import 오류였고, `discover -s tests`로 올바르게 재실행해 통과했다.
- `PASS (temporary server health)`: 기존 Mac 8031 프로세스의 실행 명령과 PID를 확인하고 해당 임시 프로세스만 TERM 종료한 뒤 동일 카메라 입력·저장 옵션으로 재실행했다. `/health`는 `ok=true`, 정면 age 0.324초·사선 age 0.171초, `manual_capture_enabled=true`, `robot_enabled=false`였다. 실제 저장 파일 0건. 8000/8030/USB·모터는 건드리지 않았다.
- `NOT_RUN/BLOCKED (user input)`: 현재 A/B/C 라이브 저장·원본 재로딩 검수는 사용자가 실제 라벨을 확인해 새 화면에서 `종류 선택 → 프레임 고정 → 중심 클릭 → 사진·라벨 로컬 저장`을 눌러야 가능하다. 과거 클릭을 파일로 복원하거나 임의의 A/B/C 라벨로 저장하지 않는다. 브라우저의 `SAVED_FOR_REVIEW`와 실제 파일 수 확인이 다음 단계다.
- `PUSHED (feature commit 74f3307)`: 코드·기록을 기존 GitHub `fix/usb-recording` 브랜치에 올렸다. 원본 JPEG·데이터셋·인증정보는 Git 제외다.

## 8031 프레임 고정 실패와 복구

- `FIRST FAILURE`: 사용자가 새 저장 화면에서 프레임 고정이 진행되지 않는 스크린샷을 보냈다. 고정 사진은 깨졌고 상태는 `읽는 중…`이었다. 8031 서버 `/health`는 `ok=true`, 정면·사선 프레임은 신선해 카메라 중단이 아니었다.
- `ROOT CAUSE`: 저장 버튼 실패 메시지의 `\n`이 Python 삼중 문자열을 거치며 JavaScript 문자열 내부의 실제 줄바꿈으로 출력됐다. 이 구문 오류 때문에 페이지의 전체 스크립트가 실행되지 않았다. 앞선 Python/단위 테스트와 서버 health만으로 브라우저 동작을 검증한 것이 부족했다.
- `FIX/PASS`: HTML로 출력되는 문자열이 JavaScript의 이스케이프 `\n`을 유지하도록 수정하고 회귀 검사를 추가했다. 정확한 Mac 8031 프로세스만 TERM 종료 후 같은 카메라 입력·로컬 저장 옵션으로 재시작했다. 사용자 8031 탭을 새로고침해 상태 JSON 갱신, 라벨 미선택, 고정 사진 표시 및 `고정 프레임 189` 결과를 브라우저에서 확인했다. 로봇 제어 상태는 계속 false다.
- `FIRST SAVES`: 21:50 KST 시점 C 라벨 `FOR_REVIEW` 저장본 2개가 있고 두 JPEG의 SHA-256이 각 metadata와 일치한다. A/B는 촬영 진행 중이며 신원·훈련 적합성은 사용자 라벨과 후속 검수가 필요하다. 원본은 Git 제외다.
- `PUSHED (77e8d30)`: 브라우저 버그 수정·회귀 검사·세션 기록을 기존 `fix/usb-recording` 브랜치에 올렸다. 원본 사진은 Git 제외다.

## A/B/C 90장 라벨 감사 및 B→A 오라벨 제외

- `USER GROUND TRUTH`: 사용자 스크린샷 기준 왼쪽 C, 가운데 B, 오른쪽 A다. 사용자가 A 약통을 B로 저장한 사진이 있다고 보고하고 제외를 요청했다.
- `AUDIT`: 저장 원본 90장(C 22/B 45/A 23)의 JPEG/metadata SHA-256은 90/90 일치했다. C 클릭 x=309.42–327.89, 앞선 B 35장은 x=364.84–392.55, B 라벨 마지막 10장은 x=429.49–449.81, A 23장은 x=427.65–448.89이다. B 마지막 10장의 sequence는 1423, 1439, 1457, 1474, 1491, 1507, 1522, 1539, 1554, 1569이며, 대표 원본 영상도 앞선 B와 뒤따른 A 사진과 비교했다.
- `ACTION (recoverable exclusion)`: 해당 B 라벨 10개 폴더만 `.local/medicine-manual-captures/`에서 Git 제외 `.local/medicine-manual-captures-excluded/2026-10-07-b-as-a/`로 옮겼다. JPEG/metadata를 삭제·수정하거나 A로 자동 재라벨링하지 않았다. 로컬 `curation.json`에 정확한 폴더 목록·사용자 정정·복원 경로를 남겼다. 이후 보유 후보 C 22/B 35/A 23 총 80장, 제외 10장이며 양쪽 파일 SHA 검증 90/90 통과다.
- `LIMIT`: 종류별 고유 화면 위치는 라벨과 완전히 상관되어 전체 프레임 기반 모델이 크기 대신 위치를 외울 위험이 높다. 같은 촬영 세션 무작위 분할도 독립 검증이 아니다. 모든 자료는 `FOR_REVIEW`·`training_ready=false`로 유지하고, A/B/C 자동 분류·로봇 동작은 `NOT_RUN`이다. 다음 학습/검증에는 위치를 섞은 독립 자료가 필요하다.
- `GIT`: 이 감사 기록은 기존 `fix/usb-recording` 브랜치에 반영한다. 원본 JPEG·curation.json은 계속 Git 제외다.
