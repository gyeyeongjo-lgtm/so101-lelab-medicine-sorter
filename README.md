# SO-101 약통 자율 분류

SO-101과 Orbbec Astra RGB-D를 이용해 알려진 빈 약통/모형 A·B·C 중 하나를
사용자가 지정한 고정 바구니로 분류하는 연구용 프로토타입입니다. 실제 약품의 종류,
처방 또는 복약 방법을 판단하지 않습니다.

현재 활성 애플리케이션 진입점은 하나입니다.

```bash
python3 -m medicine_sorter --help
```

기본 동작은 카메라·serial·모터를 열지 않습니다. 새 환경의 좌표 변환, TCP,
바구니 투입점과 전체 경로가 다시 검증되기 전에는 `live`가 장치 연결 전에
fail-closed합니다.

## 현재 지원 범위

- 한국어 단일 작업 명령: 큰/중간/작은 약통 하나와 빨강/초록/파랑 목적지
- 명시한 목적지가 기존 A→파랑, B→초록, C→빨강 기본 규칙보다 우선
- 저장된 mock scene을 이용한 전체 상태 흐름
- 설정 schema와 새 환경 보정 준비 상태 검사
- 중복 작업 차단, stale scene, RGB/depth 불일치, 후보/marker 모호성 오류
- 내부 길이 `mm`, 각도 `degree`; `T_A_B`는 `p_A = T_A_B × p_B`

현재 YOLO 모델은 `white_medicine_bottle_model` 단일 클래스입니다. A/B/C 구분은
실물 정의를 다시 확인할 때까지 human-verified known-object 범위이며, 처음 보는 약통의
물리 크기 자동 판정으로 표현하지 않습니다.

## 실행

설정 상태 확인:

```bash
python3 -m medicine_sorter --config configs/system.example.json status
```

실제 follower 상태만 한 번 읽는 명령:

```bash
python3 -m medicine_sorter \
  --config configs/system.example.json \
  robot-status
```

이 명령은 카메라 보정이나 분류 경로를 요구하지 않습니다. 설정된 follower 후보
`/dev/ttyACM1`의 USB serial이 `5AE6058306`인지 먼저 대조하고, 포트가 비어 있을 때만
`Present`, `Goal`, `Torque_Enable`, `Moving`, `Present_Temperature`를 raw로 각각 한 번
읽습니다. 일반 `SO101Follower.connect()`는 사용하지 않으며, 상태 변경 API를 차단한
뒤 `FeetechMotorsBus.connect(handshake=False)`로 연결하고
`disconnect(disable_torque=False)`로 종료합니다. read 요청 자체는 serial 패킷을
보내지만 Goal, Torque, config를 쓰지 않습니다. 이 경로의 Jetson 설치본 및 실제 장비
시험은 아직 `NOT_RUN`입니다.

저장 mock scene 전체 흐름:

```bash
python3 -m medicine_sorter \
  --config configs/system.example.json \
  mock-run \
  --scene configs/mock_scene.example.json \
  --command "큰 약통 하나를 빨간 바구니에 넣어"
```

설정 schema 검사:

```bash
python3 -m medicine_sorter --config configs/system.example.json validate-config
```

`live` 명령은 존재하지만 현재 예제 설정에서는 의도적으로 차단됩니다. 출력은 실패
항목, 관측값, 필요한 조건과 다음 조치를 함께 제공합니다. 기존의 실험별 승인 문자열,
one-shot ticket, recovery entrypoint는 새 애플리케이션에서 사용하지 않습니다.

## 테스트

새 활성 코어:

```bash
python3 -m unittest discover -s tests -p 'test_sorter_*.py' -v
```

전체 hardware-free 발견 시험:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

mock 통과는 실제 카메라나 실제 로봇 성공을 의미하지 않습니다.

## 구조

- `medicine_sorter/command.py`: 규칙 기반 한국어 명령 해석
- `medicine_sorter/vision.py`: 저장 scene 검증, 대상·바구니 선택
- `medicine_sorter/geometry.py`: 좌표 방향과 mm 단위 변환
- `medicine_sorter/robot.py`: 상태 변경의 유일한 애플리케이션 제어 계층
- `medicine_sorter/workflow.py`: 한 번에 한 작업의 단계 흐름
- `medicine_sorter/cli.py`: 단일 CLI
- `configs/system.example.json`: 새 환경에서 채울 설정과 보정 상태

카메라 보정, 데이터 수집, 모델 평가 도구와 일부 과거 경로 재현용 스크립트는
`scripts/`에 남아 있지만 지원되는 분류 실행기가 아닙니다. 새 오류에 이 파일들을
연결하거나 새 recovery entrypoint를 추가하지 않습니다. 이번에 제거한 live/recovery
실행기는 Git 이력과 로컬 ref `refs/backup/pre-refactor-20261016`에서 복구할 수 있습니다.

## 새 환경에서 필요한 실측

1. follower 관절 calibration과 장비 식별
2. 현재 해상도의 camera intrinsic
3. ID0–3 실제 크기·배치와 camera↔table
4. table↔robot-base 독립 검증점
5. 실제 finger 접촉점 TCP와 A/B/C 파지 높이
6. ID4/5/6 실제 부착 상태와 바구니 opening·테두리
7. 약통을 포함한 전체 중간 경로와 대기 복귀 경로

자세한 현재 판정은 `docs/STATUS.md`, 구조와 이전 실행기 분류는
`docs/SYSTEM_ARCHITECTURE.md`를 확인해 주세요.

## 안전 경계

- 실제 모터, Torque, USB 재연결은 별도의 구체적인 현장 시험 승인 전에는 실행하지 않습니다.
- UI·명령 파서·비전 모듈은 serial에 직접 쓰지 않습니다.
- Stop, 현재 위치 유지, Torque OFF, disconnect, 전원 차단은 서로 다른 동작입니다.
- 데이터셋, 모델, 보정 원본, 원시 로그와 인증정보는 Git 정리 대상이 아닙니다.
