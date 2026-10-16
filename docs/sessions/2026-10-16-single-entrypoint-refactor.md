# 2026-10-16 단일 진입점 재구성

## 보존

- 시작 branch: `fix/usb-recording`
- 시작 commit: `48e9380905878493b4e166c124a655aad41f3289`
- 미커밋 상태: ArUco SVG 3개와 Charuco PDF 1개 삭제, untracked 없음
- exact tracked snapshot: `refs/backup/pre-refactor-20261016`
- snapshot commit: `8d37077da631488603761dcbf2d6c3c4ef1ad52b`
- manifest: `backups/pre-refactor-20261016/README.md` (Git ignored)
- `datasets/`, `models/`, `.local/`, `.cache/`, `artifacts/`는 원위치 보존하고 복제·삭제하지 않았다.

## 구현

지원되는 분류 실행을 `python -m medicine_sorter` 하나로 통합했다.

- `command.py`: 큰/중간/작은 및 A/B/C, 색 동의어, 수량·모호성 검사
- `models.py`: 명령·관측·계획·결과 타입
- `config.py`: environment config와 live readiness
- `vision.py`: 저장 scene schema, freshness, RGB-D 정합, 대상·바구니 선택
- `geometry.py`: mm/degree와 `p_A = T_A_B × p_B`
- `robot.py`: 상태 변경의 유일한 애플리케이션 계층, mock adapter, live fail-closed adapter
- `workflow.py`: 단일 작업 lock과 16단계 mock 흐름
- `cli.py`: `status`, `validate-config`, `mock-run`, `live`

`configs/system.example.json`은 새 환경의 모든 calibration을 unverified로 명시한다.
`configs/mock_scene.example.json`은 저장 mock 경로만 검증하며 실측값이 아니다. 명시적
목적지 색은 A→파랑/B→초록/C→빨강 기본값보다 우선한다.

## 정리

오류별로 누적된 다음 독립 entrypoint를 삭제했다.

- atomic HOLD restore
- contact release only
- current HOLD UI teleop
- gripper-close-to-20 only
- single-session demo
- current-HOLD supervised teaching
- Goal-to-Present sync only
- Torque writer diagnostic

관련 전용 test 7개와 gripper-close test class, 단일 실행 config도 제거했다. 삭제 이유는
정상 분류 lifecycle과 중복되고 과거 승인 문자열·ticket·상태를 새 구조에 상속하기
때문이다. 원본 실험 기록과 실패 관측은 `docs/sessions/`에 보존했다.

## 검증

- 새 코어 tests: 초기 `21/21 PASS`, 최종 보강 후 `23/23 PASS`
- 마무리 중 README의 dotted-module 명령은 `tests/` 패키지가 없어 첫 실행에서
  import error 4건을 냈다. 코어 실패로 숨기지 않고 실제 동작하는 unittest
  discovery 명령으로 문서를 수정한 뒤 통과했다.
- 전체 hardware-free discovery: `534 PASS`, `5 SKIPPED`, `0 FAIL/ERROR`
- skip 1: 선택 의존성 `websocket-client`가 현재 `.venv`에 없음
- skip 4: sandbox가 loopback bind를 허용하지 않음
- loopback 허용 환경의 캡처 서버 별도 실행: `14/14 PASS`. 첫 module-name 실행은
  `tests`가 package가 아니어서 import ERROR였고, discover 방식으로 재실행해 통과했다.
- CLI status: serial/camera/motor write `0`
- CLI mock-run: `MOCK_COMPLETED`, `physical_motion=false`
- CLI live: 새 환경 calibration 미검증 목록을 출력하고 장치 연결 전에 exit 2
- Python compile, `git diff --check`, 신규/변경 파일 대상 trailing whitespace, 1 MiB 초과
  신규 파일, high-confidence credential pattern 검사: `PASS` / 발견 0

실제 저장 영상, YOLO 추론, 실제 카메라, Jetson 설치, serial, Torque, Goal, 모터,
grasp/place/return은 모두 `NOT_RUN/NOT_VERIFIED`다.

## 모델 자산 확인

- `models/medicine-yolo/yolo11n-smoke-v1-onnx-test/report.json`의 실제 출력은
  `class_id=0`, `class_name=white_medicine_bottle_model` 단일 클래스다.
- 로컬 보존 경로에 `best.onnx`, `best.pt`, `last.pt`가 있으며 삭제·복제·수정하지
  않았다. `models/`는 Git ignore 대상이며 weight 파일은 추적 목록에 없다.
- 따라서 새 코드는 A/B/C 크기 자동 인식을 주장하지 않고, 실물 대응을 확인할
  때까지 known-object/human-verified로 제한한다.

## 아직 필요한 현장 정보

1. A/B/C가 현재 실물에서 각각 large/medium/small이 맞는지
2. 새 환경 ID0–6의 실제 부착 상태와 marker별 실측 크기
3. follower/leader canonical 장치 식별
4. 카메라 해상도·초점 조건과 intrinsic 재사용 가능 여부
5. table↔base, TCP, 바구니 opening, 대기/전체 경로의 새 검증 데이터

다음 실제 시험은 위 입력을 반영한 뒤 **port-only connect + read-only state snapshot +
disconnect(disable_torque=False)** 한 건으로 제한한다. Goal/Torque/config write와 모터 이동은
포함하지 않는다. 해당 시험은 별도 승인 전 `NOT_RUN`이다.
