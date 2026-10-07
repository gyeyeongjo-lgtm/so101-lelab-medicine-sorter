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
- `PASS (offline detector QA)`: 기존 한 클래스 ONNX를 보유 후보 80장에만 오프라인 적용했을 때 저장된 클릭점이 약통 검출 상자에 들어간 비율은 A 23/23·B 35/35·C 22/22였다. 상자 높이 중앙값은 A 51.15/B 38.62/C 36.40 px, 범위는 각각 47.32–54.28/35.94–39.97/35.29–37.79 px다. B/C 범위가 겹쳐 단순 높이 임계값은 승인하지 않는다. 이것은 검출 QA일 뿐 A/B/C 예측 평가가 아니다.
- `GIT`: 이 감사 기록은 기존 `fix/usb-recording` 브랜치에 반영한다. 원본 JPEG·curation.json은 계속 Git 제외다.

## 고정 배치 인식 + 유연한 목적지 명령 시제품

- `USER REQUIREMENT`: A/B/C를 늘 오른쪽/가운데/왼쪽에 배치하며, `A를 빨강, B도 빨강`은 목적지 명령 **예시**다. 지금 실제 바구니 배치를 바꾸라는 지시가 아니다.
- `IMPLEMENTED`: 기존 한 클래스 YOLO를 그대로 두고, 640×480 이미지의 검출 박스 중심 x와 넉넉한 높이 가드로 C/B/A 고정 슬롯을 찾는 별도 dry-run 도구와 provisional 설정을 추가했다. Korean 색 명령을 엄격하게 해석하고, 여러 종류가 동일 바구니 ID를 목적지로 갖는 것은 허용한다. 기본 1:1 정렬 규칙 파일과 8031 저장 화면은 변경하지 않았다. 모터·USB·LeLab 제어 호출은 없다.
- `PASS (tests/offline)`: 단위 테스트 7개, Python 구문·diff 검사 통과. 기존 ONNX를 보유 80장에 다시 실행하고 **합성 마커 정상 상태**를 넣은 고정 슬롯 판정은 C 22/B 35/A 23 모두 통과했다. 이는 같은 촬영 세션의 슬롯 적합성 검사이지 독립 분류 정확도가 아니다.
- `PASS (one live dry-run)`: Mac 8031 `/health`의 실제 신선한 카메라/마커 상태에서 예시 `A를 빨간색`은 A 오른쪽 슬롯을 찾아 빨강 ID4 `DRY_RUN_ROUTE_ONLY`를 반환했다. `robot_enabled=false`, `motion_authorized=false`, `robot_coordinates_included=false`다.
- `NOT_RUN/BLOCKED`: A/B 동시 배치 명령의 실제 화면 검증, 위치/카메라 변화 검증, 바구니 다중 투입 용량·경로·충돌, 로봇 집기·재생은 하지 않았다. 이 시제품은 목적지 후보만 내며 자동 분류/운용 완료가 아니다.
- `PUSHED (42170f7)`: 이 dry-run 코드·설정·테스트·기록을 기존 GitHub `fix/usb-recording` 브랜치에 올렸다. 실제 목적지 변경 명령이 아니므로 기본 매핑은 보존했다.

## 8031 명령 미리보기 UI 연결

- `IMPLEMENTED`: 기존 로컬 8031에 명령 입력칸과 `명령 판정만` 버튼, 별도 `/api/command-preview`를 추가했다. 실제 작업 지정으로 저장하지 않고 현재 읽기 전용 worker snapshot에서 고정 슬롯 dry-run 함수만 호출한다. 수동 사진 저장 기능과 기존 기본 A/B/C→바구니 규칙은 유지한다. 로봇 제어 endpoint는 없다.
- `PASS (tests/live)`: 웹 단위 테스트 12개(명령 API의 robot-disabled 응답 포함)·고정 슬롯 테스트 7개, Python 구문·diff 검사 통과. 정확한 8031 PID/실행 명령·저장 폴더 80개를 확인한 뒤 그 임시 프로세스만 TERM 종료하고 같은 입력으로 재시작했다. `/health ok=true`, 신선한 정면 1개 검출·사진 저장 활성·robot_enabled=false. 실제 브라우저 새 UI에서 `A를 빨간색` 입력·버튼 클릭 시 A 오른쪽 슬롯→빨강 ID4 `DRY_RUN_ROUTE_ONLY`가 보였다. 시험 입력은 새로고침해 비웠다.
- `FIRST UI TEST MISREAD`: 첫 UI 자동화의 접근성 값은 A 명령을 표시했지만 실제 DOM 입력값은 빈 문자열이라 버튼 결과가 바뀌지 않았다. DOM 입력 상태를 확인해 실제 텍스트 입력으로 다시 시험했고 위 판정이 표시됐다. 서버·명령 해석 오류는 아니며 사용자 명령이 적용된 적도 없다.
- `NOT_RUN`: A/B 동시 현장 장면, 다른 촬영일/카메라 위치 변화, 실제 명령 지속·예약, 목적지 다중 투입 경로·용량, 모터 동작은 검증하지 않았다. 기존 World→Base/TCP 및 경로 승인은 여전히 거부 상태다.
- `PASS (saved ROI evidence)`: Git 제외 보유 메타데이터 80개를 읽기 전용으로 재집계해 A 0/23·B 35/35·C 0/22만 기존 픽업 ROI에 들어감을 확인했다. 이는 약통 높이를 보정하지 않은 검출 상자 중심의 작업대 평면 투영이며 물리 집기 가능률이 아니다. 반환 경로에 `pickup_roi_match`와 `grasp_authorized=false`를 추가했다. 8031 live health는 `ok=true`, 프레임 age 0.304초, `robot_enabled=false`; 시험용 `A를 빨강`의 읽기 전용 미리보기는 `pickup_roi_match=false`, `grasp_authorized=false`, `motion_authorized=false`였다. 명령 저장·실행, ROI 확장·모터 제어는 하지 않았다.
- `INITIAL NEXT/BLOCKED`: 세 약통 동시 고정 배치에 대한 실제 한 프레임 검증은 사용자 물리 배치를 기다렸다. 이후 아래의 카메라-only 동시 배치 검증으로 이 게이트는 해소됐다. 실제 로봇 동작은 별개이며 자동 집기·재생 `NOT_RUN`이다.
- `PUSHED (ff57967)`: 이번 읽기 전용 UI·ROI 판정·테스트·문서 7개 파일을 기존 비공개 `fix/usb-recording` 브랜치에 push했다. 원본 사진·데이터셋·인증정보는 Git 제외. 웹 12개·고정 슬롯 7개 시험, Python 구문·diff 검사 통과. `gh` CLI가 Mac에 없어 GitHub 이슈 API 갱신은 `NOT_RUN`; 미해결 항목은 이 세션과 `docs/STATUS.md`에 유지한다.

## 세 약통 동시 배치의 실제 읽기 전용 검사

- `USER INPUT`: 사용자가 텔레옵 종료·팔 정지 상태에서 왼쪽 C·가운데 B·오른쪽 A를 동시에 놓았다고 보고했다. 물체 신원 자체는 그 보고에 의존한다.
- `PASS (live vision)`: 8031 `/health`는 `ok=true`, frame age 0.013초, 검출 상자 3개, ArUco ID0–6, `robot_enabled=false`였다. 상자 중심 x는 약 C 308.7·B 381.1·A 444.1 px다. 기존 평면 픽업 ROI(101–273, 251–379 mm)에 B만 들어왔고 A/C는 밖이다. 이는 영상 평면 투영이지 실제 약통 높이·로봇 손끝 집기 위치가 아니다.
- `PASS (read-only route)`: 기본 명령 `A를 파랑, B를 초록, C를 빨강`은 sequence 1317에서 ID6/ID5/ID4 경로 3개를 `DRY_RUN_ROUTE_ONLY`로 반환했다. 시험용 예시 `A를 빨간색, B도 빨간색 박스`는 A/B→ID4 경로 2개를 반환했다. 각 경로 `grasp_authorized=false`, 전체 `robot_enabled=false`, `motion_authorized=false`, `robot_coordinates_included=false`; 명령을 저장·예약·실행하지 않았다. LeLab 8000 텔레옵 읽기 전용 조회는 `teleoperation_active=false`였다.
- `LIMIT`: 하나의 현장 배치·카메라 각도에서만 통과했다. 물체 종류를 상자 모양으로 독립 확인한 시험도, 다른 날짜/조명·카메라 이동 일반화도 아니다. ROI를 넓히거나 기존 World→Base/TCP 거부를 해제하지 않았다. 다중 투입 용량·경로·간섭과 실제 집기/투입은 `NOT_RUN`이다.
- `GIT`: 이 세 약통 라이브 판정과 한계는 기존 `fix/usb-recording` 브랜치에 커밋·push했다. 원본 카메라 프레임과 개인 자료는 커밋하지 않았고 GitHub 이슈 API 갱신은 `NOT_RUN`이다.

## 다음 동작 단계의 기존 증거 점검

- `PASS (read-only inventory)`: Git 제외 `.local/fixed-slot-waypoints/` 35건의 메타데이터에서 `PARK` 7·`SOURCE1_HOVER` 2·`BASKET4_HOVER` 26건을 확인했고 모두 `use_for_replay=false`다. 이 묶음에는 ID5/ID6 목적지 waypoint와 연속 집기·투입 궤적이 없다. 기존 A 수동 시연 관찰 자료와 정지 waypoint를 자동 재생 증거로 혼동하지 않는다.
- `BLOCKED (automatic motion)`: 세 병 고정 슬롯 시각 판정은 통과했지만 A/C는 픽업 ROI 밖이고 검증된 TCP/World→Base·연속 경로·ID5/6 투입 경로가 없다. 현장 추가 teach와 별도 안전·동작 승인 전에는 LeLab 자동 제어·관절 재생을 시작하지 않는다.

## 현장 안전 확인 보고와 동작 전 읽기 전용 상태

- `USER REPORT`: 사용자가 현장 안전 확인 완료를 보고했다. 이 보고는 특정 모터 동작·자동 제어 시험의 명시 승인과 구별한다.
- `PASS (read-only)`: LeLab 8000 health ok, `teleoperation_active=false`, `recording_active=false`, `inference_active=false`다. recording 내부 `current_phase=preparing`/`session_ended=false`는 완료 세션 증거가 아니다. 8031 `/health`는 프레임 age 0.245초, 한 클래스 검출 3개, ArUco ID0–6, `robot_enabled=false`; B만 기존 픽업 ROI 안이다.
- `USER APPROVAL / PREFLIGHT`: 사용자가 C 한 병의 기존 LeLab 수동 텔레옵 비접촉 상공 도달 시험을 승인했다. 8031 신선한 정면 영상에서 C 슬롯 상자 하나(x≈309 px)·ID0–6만 확인했고 A/B는 영상 검출에서 빠졌다. Jetson SSH에서 `lelab.service` active/running, canonical follower `5AE6058306`→ACM0·leader `5AE6085272`→ACM1, root `fuser -v`의 두 포트 점유 출력 없음 확인 후 세션을 종료했다. LeLab 텔레옵·녹화·추론은 시험 시작 전 모두 inactive였다. 사용자가 시작 자세를 맞추고 텔레옵을 직접 켰으며 API active=true, Mac 8030 정면/사선/손목·관절 수신 신선, `robot_control=false`를 확인했다. 에이전트는 버스·모터·설정·토크를 조작하지 않았다.

## C 단독 상공 비접촉 접근 결과와 종료 불일치

- `USER/VIDEO`: 사용자가 리더를 천천히 움직여 C 위에서 공기 간격을 남기고 정지했다고 보고했다. 현재 정면·사선 화면에서도 그리퍼가 C 상공에 있고 약통 검출 상자가 유지됐다. 영상만으로 실제 간격을 독립 실측한 것은 아니며 접촉·집기 시도는 하지 않았다.
- `LOCAL OBSERVATION`: `observe_teleop_trace.py --camera-evidence --max-seconds 120`이 Git 제외 `.local/teleop-traces/20261007T134310_742830Z_d309ec55/`에 관절 2,298개·정면 492장·사선 493장을 저장했다. 제한 시간으로 `stop_reason=max_duration`; 퇴피 전체가 포함됐는지는 `NOT_VERIFIED`. 카메라/관절은 Mac 수신시각 근사이며 노출시각 동기 영상·제어급 궤적이 아니다. 원본 `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`를 유지했다.
- `FIRST STOP REPORT MISMATCH / RECOVERED`: 사용자는 비접촉 퇴피·종료를 보고했으나 즉시 읽은 LeLab `/teleoperation-status`는 active=true였고 8030 관절 수신도 신선했다. 이를 사용자에게 즉시 알리고 더 움직이지 않은 채 직접 재종료하도록 요청했다. 두 번째 종료 보고 뒤 API active=false를 확인했다. 첫 종료를 성공으로 기록하지 않는다.
- `OFFLINE AUDIT`: `audit_teleop_trace.py`가 관절 파일 SHA·시간 순서·정면/사선 JPEG 492/493장의 무결성을 검증했다. `URDF_LIMIT_MISMATCH` exit 2: Elbow 상한 초과 792/2,298, 최대 0.114689 rad. 과거와 같은 URDF/방송 불일치이며 물리 하드스톱 위반 증거는 아니다. 자동 재생·ArUco 기반 집기에는 사용하지 않는다. 접촉·집기·자동 동작 `NOT_RUN`.
