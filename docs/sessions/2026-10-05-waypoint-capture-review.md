# 2026-10-05 고정 슬롯 waypoint 저장본 검수

## 8000 프리뷰 재사용 임시 비전 시험

8020 기존 unit은 Astra 브리지와 충돌하므로 시작하지 않았다. 설치 Jetson OpenCV가 LeLab 8000 정면 MJPEG 한 프레임을 HTTP로 열 수 있음을 확인하고, 저장소 비전 코드에 정면·사선 `http://` MJPEG 입력을 추가했다. 처음 `cv2.VideoCapture(URL)` 임시 시험은 정면 sequence 2에서 갱신이 멈췄는데 26.683초 지난 프레임을 health `ok=true`로 반환하는 오류가 있었다. 이 실패를 기록하고 JPEG 경계 파서와 5초 frame age 게이트로 수정했다.

수정본 두 스크립트만 Jetson `/tmp/so101-mjpeg-smoke-20261005-2010/`에 복사해 loopback 8021에서 35초 제한으로 시험했다. 정면 sequence 115, frame age 0.132초, 사선 age 0.022초에서 `ok=true`, YOLO 약통 후보 3개, ID0–3과 바구니 ID5/6을 확인했다. 이전 프레임에서는 ID4도 밝기 균등화 fallback으로 검출됐다. 저장된 테이블 투영은 높이 보정 전이고 `robot_enabled=false`, `robot_target_authorized=false`다. Mac의 새 웹/파서 단위 테스트 9개가 통과했다. 별도 `test_detect_medicine_onnx`는 Mac에 `cv2`가 없어 `NOT_RUN`이며, Jetson 임시 실행에서 설치 ONNX 모델의 실제 추론을 확인했다. 시험 종료 후 8021 listener는 없고 기존 8000 active·텔레옵/녹화/추론 inactive, 8020 inactive를 확인했다. 임시 복사본은 남아 있으나 기존 Jetson 설치 파일·service unit·카메라 장치·USB·모터·토크는 변경하지 않았다. 이 시험은 자동 투입 경로 승인이나 장시간 안정성 검증이 아니다.

## 20:09 KST LeLab 복구와 마커 ID4 안정성 검사

사용자 승인 후 기존 8000 user `lelab.service`를 시작했다. 시작 전 canonical ACM0 follower/ACM1 leader serial이 기존 설정과 일치하고 root `fuser`에 두 포트 점유가 없으며 8002·8022 제어 작업이 모두 inactive였다. 시작 후 8000 health와 기존 robot config·카메라 8/4/6을 확인했고 텔레옵·녹화·추론은 모두 inactive다. 토크 레지스터는 읽지 않았고 팔을 움직이지 않았다.

기존 8000 정면 MJPEG만 읽어 현장 마커를 진단했다. ID0–3은 안정적이지만 빨강 바구니 ID4는 13프레임에 3번, 별도 17프레임 두 배치에 2번/0번만 검출됐다. 같은 17프레임에 histogram equalization을 적용하자 12번/16번 검출됐다. 두 번째 배치의 ID0–3은 처리 전후 모두 17/17이었다. 처리 후 비예상 ID17이 1번 검출돼 새 fallback은 설정상 기대 ID에 한해 원본에서 빠진 것만 병합한다. 저장소 코드와 단위 테스트를 수정했지만 Jetson의 설치본·8020 서비스는 변경하지 않았다. 8020 unit에는 Astra 브리지와 `Conflicts=`가 있어 현재 카메라 소유권을 바꾸지 않았다. 이 비전 개선은 World→Base·Elbow 한계·경로 안전 문제를 해결하지 않으며 자동 투입 승인도 아니다.

## 19:40 KST 후속 읽기 전용 연결 점검

Mac에서 Jetson 8000과 Mac 8030 TCP 연결이 거부됐다. Jetson SSH 읽기 전용 점검에서 `lelab.service`는 `inactive/dead`, `Result=success`, `MainPID=0`, `UnitFileState=disabled`; 이번 부팅의 시작·종료 시각 `n/a`다. 8002·8022는 listen하지만 8000·8020은 listen하지 않는다. 비활성화 경위·모터 토크는 확인하지 못했다. 과거 종료 후의 teleoperation/recording/inference inactive 확인을 **현재 live 상태 확인**으로 재사용하지 않는다. 서비스 시작/재시작, 카메라 장치 열기, USB·모터·토크 변경, 새 자동 재생은 모두 `NOT_RUN`. ArUco 감지 코드와 표식 설정이 존재해도 World→Base 등록 거부, URDF/캘리브레이션 불일치, 적재 연속 영상·경로 검증 미완료라 자동 투입은 허용하지 않는다.

## 설치 URDF-관절 방송 한계 대조 (오프라인)

Jetson의 실제 설치 `frontend/dist/so-101-urdf/urdf/so101_new_calib.urdf` SHA-256 `443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236`에서 Elbow 허용 범위는 −1.74533~1.5708 rad다. 2회차 원본 JSONL SHA-256을 manifest와 대조한 뒤 2,704개 전수 검사 결과 Elbow 1,607개가 상한을 초과했고 최대 1.685489 rad(초과 0.114689 rad)였다. 나머지 다섯 관절의 범위 초과는 없다. `scripts/audit_teleop_trace.py`와 설치 URDF 해시 기반 한계 JSON을 추가해 이 검사를 재현 가능하게 했다. 실제 기록 audit exit 2, 상태 `URDF_LIMIT_MISMATCH`; 관련 테스트 19개 통과. 감사기는 로봇 제어 기능이 없고 어떤 결과에도 재생을 승인하지 않는다.

설치 LeLab `teleoperate.py` SHA-256 `2a54de45...ab33931e2`의 `get_joint_positions_from_robot`은 follower `elbow_flex`를 `Elbow`로 매핑해 도→rad 변환한다. 설치 LeRobot `so_follower.py`의 `send_action`은 `max_relative_target`이 있을 때만 상대 차이를 제한하며, config 기본값은 None이다. 설치 코드에서 URDF 절대 상한을 적용하는 경로는 확인되지 않았다. 수치 불일치는 정적 URDF와 방송 관절값 사이의 모델 정합 문제이지 실제 기계적 하드스톱/충돌 발생의 증명이 아니다. 캘리브레이션·설정·모터·토크는 변경하지 않았다. 원인과 안전 여유의 현장 검증 전 자동 재생 `NOT_RUN`.

추가 읽기 전용 대조: 실제 follower 캘리브레이션 파일에서 Elbow `range_min=880`, `range_max=3087`; 설치 STS3215 드라이버는 4096-step 분해능과 `(val-mid)*360/4095`의 raw→도 변환을 사용한다. 파일 범위의 양 끝은 약 ±97.01°로 계산된다. 방송 최대 1.685489 rad≈96.57°는 이 파일 상한까지 약 0.44° 남는다. 이는 **캘리브레이션 파일의 수치적 비교**이며 실제 모터 제한 레지스터, 하드스톱, 부하 중 여유를 측정한 결과가 아니다. URDF의 +90° 상한과 캘리브레이션 파일의 약 +97.01°가 어긋나는 원인은 미확인이다. 원본 캘리브레이션은 Git에 넣지 않고 수정하지 않았다.

## 사용자 수동 2회차와 연속 관절 기록

사용자가 동일 고정 슬롯·현장 안전과 빈 약통 모형 1개 수동 투입 1회를 승인했다. Jetson SSH 대화형 읽기 전용 점검에서 canonical follower `5AE6058306`→`/dev/ttyACM0`, leader `5AE6085272`→`/dev/ttyACM1`; root `fuser` 점유 출력 없음, LeLab 8000 user service active를 확인했다. `/robots/so-101`의 leader ACM1/follower ACM0·양 config `so-101.json`·카메라 8/4/6과 일치했다. LeLab 세 제어 작업 inactive·Mac 8030 세 카메라 fresh 상태에서 사용자가 직접 기존 텔레옵을 켰고 시작 이상 움직임이 없다고 보고했다. 에이전트는 `/ws/joint-data`만 읽었다.

`.local/teleop-traces/20261005T071624_105838Z_4f7c1a2f/`에 관절 방송 2,704개를 16:16:24–16:18:43 KST 약 139.7초 저장했다. 원본 JSONL SHA-256 `dcc81f9ab75eec80b61c8b5ed27d50d19e8a3eda0b94c6de8903e3b0b8e80108`은 manifest와 일치하고 중복/역순 source timestamp는 없다. 평균 수신율 약 19.35 Hz, 최대 수신 간격 389.4 ms, 250 ms 초과 9건이다. 사용자는 약통의 빨강 바구니 투입 성공, 간섭·걸림 없음, 텔레옵 직접 종료를 보고했다. 종료 후 8030 실시간 사선 화면에는 약통이 빨강 바구니 안에 있고 열린 그리퍼가 위로 분리된 모습이 보였다. 종료 뒤 LeLab teleoperation·recording·inference active=false; recording 내부 `current_phase=preparing`, `session_ended=false`는 남았다.

이번 관절 기록에는 카메라 영상이 없으므로 물체/그리퍼 위치·접촉·바구니 간격의 독립 영상 판정은 `NOT_VERIFIED`다. Mac 수신 시각의 broadcast는 실제 모터 명령이나 안전 검증 궤적이 아니다. `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`; 자동 재생·ArUco 기반 자동 투입은 `NOT_RUN`. 원본 데이터와 비밀번호는 Git에 넣지 않는다.

오프라인 사후 대조: 1회차 정지 저장본 네 자세에 대해 2회차 관절 기록 내 최근접 샘플을 찾았을 때 최대 관절 절댓값 차이는 순서대로 0.3066/0.3744/0.4588/0.8163 rad다(6관절 RMS 0.1918/0.2352/0.2308/0.3971 rad). 서로 다른 수동 시연의 자세가 동일하게 재현됐다고 볼 수 없다. 정지 사진의 점만 직접 재생하거나 관절 기록을 승인된 자동 경로로 취급하지 않는다.

## 다음 기록 사전 점검

사용자가 고정 슬롯 배치·현장 안전·수동 1회 시험을 승인했고 본인의 터미널 SSH 연결을 보고했다. 에이전트의 별도 비대화형 SSH는 계속 인증 거부여서 현재 canonical USB 매핑/버스 점유 출력 전달을 요청했다. 새 텔레옵·관절 기록은 아직 `NOT_RUN`.

LeLab health 정상, 세 제어 작업 inactive, Mac 8030 카메라 3대 frame age 16.4/7.0/17.7 ms·오류 null을 읽기 전용으로 확인했다. Mac→Jetson `jetson3@192.168.50.20` SSH는 인증 거부여서 현재 canonical USB 매핑·버스 점유를 재검증하지 못했다. 새 사용자 수동 텔레옵·연속 관절 기록·자동 재생은 실행하지 않았다. 현장 배치/안전 및 연결 확인 대기.

## 후속 오프라인 준비 — 연속 관절 관찰

정지 저장본 4개만으로 연결 구간의 관절 경로를 알 수 없어 기존 LeLab 텔레옵이 이미 활성일 때 `/ws/joint-data`만 읽는 관찰기를 준비했다. 텔레옵 시작·종료/모터 제어·재생·영상 기록은 없다. 테스트 15개 통과. 실제 촬영·반복 시험·자동 이동은 `NOT_RUN`; 현장 안전 확인·별도 승인 전 실행하지 않는다.

## 8030 라벨 보완 (후속)

수동 투입 성공 뒤 낮은 놓기 자세와 상공 대기 자세를 구별하도록 Mac 캡처 UI·서버 허용 목록에 `BASKET4_RELEASE`를 추가했다. 이전 `BASKET4_HOVER` 원본은 수정하지 않았다. 적재·접촉은 라벨로 자동 증명되지 않으며 저장 자료는 계속 `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`다. 로컬 HTTP 포함 단위 테스트 11개 통과. 기존 Mac 8030 PID·명령·작업 디렉터리와 LeLab 세 제어 작업 비활성을 확인하고 Mac 캡처 프로세스만 동일 Python·인자로 재실행했다. 실행 페이지에서 새 라벨 확인, 정면·사선·손목 카메라 7.7/29.6/29.7 ms·오류 null; 시작 직후 일시적 사선·손목 503은 회복됐다. 텔레옵 비활성, 로봇 동작·자동 재생 `NOT_RUN`.

사용자가 `BASKET4_HOVER` 여러 건을 저장했다고 보고했다. 로봇 제어 없이 `.local/fixed-slot-waypoints/`의 metadata와 정면·사선·손목 JPEG를 읽기 전용으로 확인했다.

## 저장본 및 검증

- `15:32–15:39 KST loaded one-shot`: 사용자가 기존 LeLab 텔레옵을 직접 켜고 저속으로 빈 약통 모형 1개를 고정 슬롯에서 잡아 빨강 ID4 바구니에 놓고 그리퍼를 빼냈다. 에이전트는 로봇 제어 없이 8030 증거 API로 정지 자세 4건만 저장했다: `20261005T063218_402671Z_e94cb801`(빈 그리퍼 SOURCE1_HOVER), `20261005T063513_158256Z_de61305d`(적재·소폭 들어올린 SOURCE1_HOVER), `20261005T063806_779019Z_68db9ca5`(적재 BASKET4_HOVER), `20261005T063948_405866Z_9d57cad9`(병 바닥이 바구니 바닥에 닿고 그리퍼 개방 전, 원본 라벨은 BASKET4_HOVER이나 검토 역할은 RELEASE 후보).
- 각 파일 관절 15개·카메라 3장, JPEG 12장 hash 일치, 최대 관절 표준편차 0.0018973 rad, 모든 `use_for_replay`/`robot_enabled`/`motion_authorized` false다. Jaw 평균은 순서대로 0.51804/0.32898/0.32898/0.32258 rad다. 수신시각 근접은 capture API 게이트를 통과했다. 원본은 Git-ignore 로컬에 보존한다.
- 현장 순서는 비접촉 접근→몸통 양면 그립→2–3 cm 시험 들어올림→바구니 테두리 위 높이 확보→입구 중앙 위 이동→바구니 바닥에 가볍게 접촉→그리퍼 개방→빈 그리퍼 퇴피였다. 사용자가 각 정지·간섭 없음·약통 안정성을 보고했고 정면/사선 live 화면에서 약통의 이동·바구니 안 잔류와 열린 그리퍼의 분리가 보였다. 단, 실제 높이·접촉력·간격은 영상만으로 정량 검증되지 않았다.
- 퇴피 질문에서 사용자가 처음 `걸림·약통 이동이 있어 중단` 선택지를 눌렀으나 즉시 “이거 안걸렸음”이라고 명시 정정했다. 이후 읽기 전용 화면에는 열린 그리퍼가 바구니 위로 빠져 있고 병은 내부에 남았으며, 사용자는 최종 `접촉·걸림 없이 완료, 텔레옵 종료`를 확인했다. 따라서 실제 걸림 발생으로 보고하지 않는다. 정정 과정 자체는 기록한다.
- 종료 뒤 LeLab `/teleoperation-status`, `/recording-status`, `/inference-status` 모두 inactive, `/health` ok다. recording 내부 `current_phase=preparing`, `session_ended=false`는 그대로다. 이번 성공은 사용자 수동 1회로 한정; 자동 재생·연속 궤적 안전·반복성·실제 약품 사용은 `NOT_RUN/NOT_VERIFIED`다.

- `15:17 KST user in/out demonstration`: 새 8개 폴더 `20261005T061739_009592Z_b31dd021`, `20261005T061742_817582Z_52af8874`, `20261005T061743_487107Z_042cbbb4`, `20261005T061748_065605Z_ec6794ba`, `20261005T061750_690970Z_95861600`, `20261005T061751_494210Z_821a36cb`, `20261005T061753_523867Z_29c8cae6`, `20261005T061757_507709Z_21f5c8d6`. JPEG 24장 hash 일치, 각 관절 샘플 15개, 최대 표준편차 0.00274 rad, 모든 모션/재생 차단 플래그 false.
- 영상상 39초와 50/51초 자세는 바구니 입구 안쪽에 낮게 접근하고, 42/43/48초 및 53/57초는 상대적으로 물러난 모습이다. 42/43초와 50/51초는 각각 거의 같은 관절·영상의 중복 저장본이다. 이는 사용자의 출입 시연에서 나온 **정지 지점들**이지 연결 궤적의 연속 기록이나 경로 안전 통과 판정이 아니다. 약통이 그리퍼에 잡힌 모습은 확인되지 않고 Jaw 평균은 0.518–0.519 rad 부근이다. 물체를 잡았을 때의 형상·벽 간격·놓기 성공 `NOT_VERIFIED`.
- 검수 당시 LeLab 읽기 전용 API에서 teleoperation active, recording/inference inactive. 사용자에게 촬영 종료 시 직접 텔레옵 종료를 요청했다. 원본 파일·라벨은 그대로 보존하고 재생 승인하지 않았다.

- `15:11 KST follow-up`: 새 `BASKET4_HOVER` 13건을 원본 변경 없이 검수했다. 39 JPEG hash 일치, 각 관절 샘플 15개, 최대 관절 표준편차 0.00695 rad, 재생·로봇 활성·모션 승인 플래그 모두 false다. 15:11:00/01은 정면·사선상 바구니 위 비슷한 자세이며 평균 관절 5개가 같고 Wrist_Roll만 약 0.00113 rad 다르다. 독립 후보 2개로 세지 않는다. 실제 수직 여유·도달 경로는 미검증이다. 15:11:16/19/20은 목표에서 벗어났거나 그리퍼가 사선 시야 위쪽으로 잘렸다. 15:11:23–30 여덟 건은 테두리·내부와 너무 가까워 hover로 승인하지 않는다. 재생 승인 0건.
- 검수 시 LeLab 읽기 전용 상태 `teleoperation_active=true`, recording/inference false. 사용자에게 중복 저장 중단과 직접 텔레옵 종료를 요청했다. 종료 재확인 전 새 로봇 제어·재생 `NOT_RUN`.

- 완성 폴더 10개: `PARK` 7개, `BASKET4_HOVER` 3개. 허용 라벨 외의 것으로 재라벨링하거나 원본을 수정하지 않았다.
- `BASKET4_HOVER` 세 폴더: `20261005T055217_682583Z_4c6178fe`, `20261005T055219_114617Z_f3203d53`, `20261005T055228_135683Z_caeb3ee3`. UTC 저장 시각은 각각 05:52:17, 05:52:19, 05:52:28이며 현지 시각은 약 14:52 KST다.
- 각 폴더에 관절 샘플 15개와 정면·사선·손목 JPEG 3장이 있다. 9장 모두 metadata SHA-256과 일치했다. 세 건의 최대 관절 표준편차는 각각 0, 0.0083001, 0.0068114 rad이다. 정지 샘플 품질이지 hover 안전 인증은 아니다.
- 세 건 모두 `capture_kind=waypoint`, `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`다. 원본은 Git-ignore 로컬에 보존하고 커밋하지 않는다.

## 영상 판정

- `ROLE CORRECTION`: 사용자는 바구니에 약통을 놓으려면 최근의 낮은 자세가 필요하다고 설명했다. 따라서 15:11:23–30의 낮은 8건을 **HOVER로는 부적합하지만 RELEASE 건조 시연 후보**로 재해석한다. 원본 metadata의 `BASKET4_HOVER` 오표기는 보존하고 별도 검토 기록에서만 후보 역할을 구분한다. 낮은 높이 자체를 폐기 사유로 삼지 않는다. 바구니 벽과 두 손가락의 실제 간격, 약통을 잡은 때의 형상, 투입·퇴피 연속 경로는 영상으로 확인되지 않아 재생 승인은 여전히 0건이다.
- HOVER는 테두리 위 접근·이탈 자세, RELEASE는 바구니 안에 약통을 놓는 낮은 자세로 구분한다. 같은 정지 자세를 반복 저장하는 것보다 각 역할과 충돌 여유를 검증하는 것이 다음 단계다.

- 05:52:17·05:52:19 사선 영상: 그리퍼 한쪽이 빨강 ID4 바구니 내부까지 낮게 들어가며 다른 쪽은 인접 초록 바구니 위에 있다. 이 자세를 안전한 바구니 상공 hover로 승인할 수 없다.
- 05:52:28 사선 영상: 그리퍼가 빨강 바구니 테두리 근처에 있으나 사진 한 장으로 수직 여유, 테두리·인접 바구니 간섭 여유, 그 자세까지의 연결 경로를 입증할 수 없다. 이것도 재생 후보로 승인하지 않는다.
- 이미지에서 확인되는 것은 정지 시점의 모습뿐이다. 저장 라벨 `HOVER`는 높이 보증이나 충돌 검증 결과가 아니다. 세 건 모두 증거로만 보존한다.

## 상태와 다음 게이트

- `LOADED-TRIAL PREFLIGHT`: 사용자가 약통 배치를 완료했다고 보고했다. 8030 정면·사선 영상에서 흰 뚜껑 원통형 1개가 빨강 바구니 뒤쪽에 서 있고 ID0–3 및 바구니 마커가 보인다. 세 카메라 frame age 0.4/8.2/30.9 ms, 오류 null. LeLab teleoperation/recording/inference inactive. 사용자는 빈 모형·고정 슬롯·빈 바구니, 사람·장애물 이탈, 리더·팔로워 시작 자세, 즉시 중단 준비와 수동 집기·투입 시험 1회를 명시 승인했다. 사용자가 직접 LeLab 텔레옵 시작·조작·종료한다. 에이전트 제어·자동 재생 `NOT_RUN`.

- `OFFLINE NEXT STAGE`: 종료 보고 뒤 LeLab teleoperation·recording·inference inactive를 확인했다. 15:17:39–57의 8개 정지점 중 42/43초 최대 관절 차이는 0.0005 rad, 50/51초는 0 rad로 중복이다. 인접 점 최대 관절 차이는 39→42초 0.1181, 42→43초 0.0005, 43→48초 0.1289, 48→50초 0.1043, 50→51초 0, 51→53초 0.3274, 53→57초 0.2501 rad다. 시간순 정지점의 수치 변화이지 이동 중 관절 제한·충돌·속도 검증은 아니다. 실제 설치 URDF의 관절 limit 및 연속 궤적은 이 검토에서 확인하지 못했다.
- 사용자는 실제 빈 그리퍼 출입 조작에서 바구니 테두리·벽 접촉이나 걸림은 없었고 약통 모형은 없었다고 답했다. 사용자 관찰에 근거한 **무적재 수동 경로** 경험이며 연속 로그나 적재 경로 안전 검증은 아니다. 다음 한 변수는 빈 약통 모형 1개를 잡은 상태의 저속 수동 시험이다. 출발 슬롯·시야·안전·중단 준비와 그 시험의 명시 승인 전까지 새 모션 및 자동 재생 `NOT_RUN`.

- 사용자가 텔레옵 직접 종료를 보고했다. LeLab 읽기 전용 API에서 teleoperation·recording·inference 모두 inactive를 확인했다. 추가 제어·재생 없음.

- `FOLLOW-UP (camera-only, no motion)`: 사용자가 초록·파랑 바구니를 제거했다고 보고했다. 8030 정면·사선 실시간 화면에 바구니 한 개와 기준 마커 네 장이 보인다. 사선상 남은 것은 빨강 바구니 배치와 일치하며 정면 색상은 카메라 색감 때문에 파랗게 보이므로 색상 판정에는 사용하지 않았다. 8030 status 카메라 age 9.7/29.1/1.4 ms, 오류 null; LeLab teleoperation inactive. 새 텔레옵·캡처·재생 `NOT_RUN`.

- `RESOLVED (stop verification)`: 사용자가 의도치 않게 다시 시작된 텔레옵을 직접 종료했다고 보고했다. 이어 Mac에서 읽기 전용 LeLab 상태 API가 `teleoperation_active=false`, `recording_active=false`, `inference_active=false`, `/health` ok를 반환했다. recording 내부 `current_phase=preparing`, `session_ended=false`는 유지되어 세션 정리 완료로 단정하지 않는다. 종료 검증에 UI 버튼이나 제어 API는 사용하지 않았다.

- 후속 상태 확인 중 의도치 않은 텔레옵 시작 사고가 발생했다. Mac shell에서 8000/8030 접속이 거부되어 브라우저 LeLab 홈을 읽었고, `Teleoperation` 버튼을 상태 화면으로 가는 탐색으로 오인해 눌렀다. UI는 `Teleoperation Started`와 `Live Robot Data`를 표시했다. 사용자는 직전 텔레옵 종료를 보고했지만 **이번 새 시작을 승인한 적은 없다**. 즉시 실수를 알렸고 현장 중단을 요청했다.
- 화면의 레이블 없는 뒤로가기 버튼 클릭은 안전 검사에서 거부됐다. 종료 효과를 확인할 수 없어 우회하지 않았다. 사용자 직접 종료 및 이후 inactive 검증 전까지 `BLOCKED`. 이 사고를 모션 성공이나 정상 종료로 기록하지 않는다.

- 검수 중 Mac의 `192.168.50.20:8000/teleoperation-status` 및 `127.0.0.1:8030/api/status`는 연결 거부됐다. 따라서 현재 텔레옵 활성·종료 여부는 `NOT_VERIFIED`다. 원격 제어로 중단하거나 서비스를 재시작하지 않았다. 사용자가 직접 텔레옵을 종료했는지 확인하고, 연결 복구 뒤 텔레옵·녹화·추론 inactive를 읽기 전용으로 확인해야 한다.
- 새 모션·토크·USB·서비스 변경, waypoint 자동 재생·집기 `NOT_RUN`. 향후 실제 상공 여유와 경로를 검증하려면 현장 안전 확인, 구체적인 시험 범위 승인, 장애물·중단 방법 검토가 별도로 필요하다. 이번 검수 자체는 그런 승인에 해당하지 않는다.
