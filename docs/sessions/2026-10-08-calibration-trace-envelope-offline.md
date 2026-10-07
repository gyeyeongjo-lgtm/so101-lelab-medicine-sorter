# 2026-10-08 follower 캘리브레이션 파일 범위와 수동 기록 대조

## 근거·범위

- 로봇을 움직이지 않고 LeLab 8000의 `/teleoperation-status`가 inactive임을 확인했다. Jetson canonical USB 메타데이터는 follower `5AE6058306`→`/dev/ttyACM0`, leader `5AE6085272`→`/dev/ttyACM1`; `lelab.service`는 active였다. 시리얼 버스는 열지 않았다.
- Jetson 설치 LeLab Python은 3.14.7이다. 설치 `SOFollower`는 arm 5관절에 `MotorNormMode.DEGREES`(설정 `use_degrees=True` 기본값), 그리퍼에는 `RANGE_0_100`을 쓴다. 설치 `MotorsBus._normalize`의 arm 계산은 `mid=(range_min+range_max)/2`, `degree=(raw-mid)*360/4095`다. 이번 감사는 Jaw를 제외한다.
- follower 캘리브레이션 파일의 SHA-256은 `2f74c1303b2fce03576eff539329e1185a652e2d551caa1ec82b026dafe29c2e`였다. 다섯 arm 범위만 날짜가 붙은 [파생 스냅샷](../../configs/so101_follower_calibration_bounds_20261008.json)에 기록했다. 원본 캘리브레이션 파일·비밀번호·원본 기록은 커밋하지 않는다. Elbow/Wrist_Pitch의 장치 레지스터와 파일 일치는 앞선 별도 읽기 전용 점검에서 확인됐지만 나머지 세 관절 레지스터는 이번에 읽지 않았다.
- 첫 일반 샌드박스 네트워크 요청은 연결 거부, 공개키 전용 SSH는 인증 거부였다. 허용된 읽기 전용 네트워크 조회와 기존 사용자 승인 계정의 대화형 SSH로 위 정보를 확인했다. SSH 세션은 정상 종료했다.

## 파일 범위와 URDF의 차이

| 관절 | 캘리브레이션 raw | 파일 기준 대칭 범위 | 설치 URDF 범위 |
| --- | ---: | ---: | ---: |
| Rotation | 755–3448 | ±118.374° | ±110.000° |
| Pitch | 796–3113 | ±101.846° | ±100.000° |
| Elbow | 880–3087 | ±97.011° | −100.000°…+90.000° |
| Wrist_Pitch | 936–3225 | ±100.615° | ±95.000° |
| Wrist_Roll | 86–3643 | ±156.352° | ±160.000° |

이 값은 설치 정규화식과 **날짜가 붙은 파일**의 수학적 결과다. 저장된 범위를 물리 하드스톱·하중 중 안전 여유 또는 자동 목표값으로 해석하지 않는다. URDF는 Elbow/Wrist_Pitch에서 더 좁고, Wrist_Roll에서는 오히려 파일보다 넓어 두 체계 중 하나만 검사하는 것은 불충분하다.

## 기록 9건 전수 대조

- Git 제외 `.local/teleop-traces/`의 manifest 9건, 관절 방송 총 16,568개를 감사했다. 각 관절 파일 SHA-256, 샘플 수, 시간 순서와 **포함된 경우에만** 카메라 인덱스/프레임 해시는 기존 감사 함수로 확인했다. 역순/중복 source·수신 시각은 9건 모두 0건이다. 하지만 9건 모두 `camera_evidence_complete=false`라 동기화된 완전 경로 영상으로 취급하지 않는다. 9건 모두 기존 설치 URDF 감사에서 `URDF_LIMIT_MISMATCH`다.
- 다섯 arm 관절의 방송값은 모두 **캘리브레이션 파일 범위 안**이었다(파일 범위 초과 0건). 전체 기록 중 가장 작은 파일 경계 간격은 Rotation 94.066°, Pitch 3.165°, Elbow **0.352°**, Wrist_Pitch **0.352°**, Wrist_Roll 126.242°다. 1° 이내 표본은 Elbow 3,547개, Wrist_Pitch 20개이며 다른 세 관절은 0개다. 1°는 **진단 표시 폭**이지 승인된 안전 마진이 아니다.
- Elbow와 Wrist_Pitch의 0.351648°는 설치 정규화식으로 약 4 raw step이다. 이는 기록된 방송값과 파일 경계의 차이이며 실제 모터 응답 지연·오차·충돌 여유·부하 중 여유를 측정한 값이 아니다. 따라서 `within file range`를 재생·자동 이동 허가로 격상하지 않는다.
- [오프라인 검사기](../../scripts/audit_calibration_trace_envelope.py)는 파일 범위, URDF 감사 상태, 경계 간격과 1° 이내 개수를 함께 내고 `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false`를 고정한다. 합성 회귀 시험 포함 관련 12개 단위 테스트, Python 구문, `git diff --check` 통과. 실제 모터·토크·USB·캘리브레이션·LeLab 설정 변경 및 재생 `NOT_RUN`.
- 전체 회귀 첫 실행은 시스템 Python에 `cv2`가 없어 167개 중 5개 import/로컬 포트 오류로 실패했다. 프로젝트 `.venv`(Python 3.13.2/OpenCV 5.0.0) 재실행은 `websocket` 패키지가 없어 163개 중 1개 import 오류로 실패했다. 첫 수동 테스트 로더 명령은 `tests` 패키지 경로를 잘못 지정해 36개 모듈 로드가 실패했으며 경로를 바로잡았다. 최종적으로 `.venv`에서 해당 관찰기 모듈을 제외한 162개 통과, 시스템 Python에서 관찰기 7개 통과했다. 이는 두 환경에 나누어 확인한 결과이지 **단일 환경 전체 169개 통과**가 아니다. Ultralytics 모듈 import가 사용자 라이브러리 아래 기본 설정 파일을 자동 생성했으며 로봇 설정은 아니다.

## 판정·다음 단계

캘리브레이션 파일과 URDF 불일치를 수치로 분리했지만, 자동 이동 게이트는 여전히 `BLOCKED`다. 다음 오프라인 단계는 기존 수동 기록의 시작 자세·연속 속도·바구니/그리퍼 간섭 후보를 같은 보수적 기준으로 재검토하고, 실제 실행 시험 전에는 현장 조건과 별도 승인을 받는 것이다. 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.
