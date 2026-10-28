# VLA 1단계 카메라 설정

날짜: 2026-10-28 (Asia/Seoul)

## 범위

기준 fix/usb-recording `5f03c571e223f86f422b6eb68af94a6ff05c78db`의 별도 작업 사본.
원격 vla/main 부재 확인 후 로컬 vla/main 생성. 기존 정상 코드/데이터는 유지한다.
상세 설계·사전확인 a~d: [VLA_STAGE1](../VLA_STAGE1.md).

## 변경

- configs/vla_cameras.yaml: wrist/top/oblique, 640x480/30 설정, identity null.
- scripts/check_vla_cameras.py: strict YAML, by-id/중복 검증, camera-only bounded
  subprocess 1프레임 검사, JSON, 기존 결과 덮어쓰기 금지.
- tests/test_vla_cameras.py: fake backend/metadata/process로 장치 없는 검증.
- docs/LEGACY.md: 기존 코드 보존. DATASET_VALIDATION.md: 기록/가설 구분.
- docs/STATUS.md 및 본 세션 기록 갱신.

## 검사

- `python3 -B -m unittest discover -s tests -p test_vla_cameras.py -v`: 27 tests PASS, exit0.
- 기존 무장치 회귀: 같은 unittest discover 명령의 pattern을 각각
  `test_fixed_demo.py`(64), `test_demo_web.py`(7), `test_sorter_*.py`(31),
  `test_camera_preview_joint_ws.py`(3)로 실행, 모두 PASS/exit0. 합계132 tests.
- `python3 -B scripts/check_vla_cameras.py --validate-only`: exit0, schema_valid=true,
  status=NOT_RUN, hardware_verified=false. 연결된 카메라가 있다고 보고하지 않음.
- template `--capture`: exit2/NOT_RUN, 카메라 open0 (신원 null 거부).
- Python 소스 compile(메모리 내), `git diff --check`: PASS/exit0.
- 실제 카메라, Jetson 메모리/디스크/JetPack/CUDA/torch: NOT_RUN (SSH No route to host).
- LeRobot0.6.1 설치본 train/record --help: 각각 exit0.
- 공식0.6.0 tag(30da8e687a6dfc617fcd94afc367ac7071c376ce)의 임시 소스를 child
  PYTHONPATH로 지정한 train/record --help도 각각 exit0(3974/1454lines).
  import 경로는 임시0.6.0 src로 확인. 설치된 distribution은0.6.1 그대로다.
  0.6.0 격리 설치 환경/Jetson 실제 CLI는 NOT_RUN. 학습/녹화는 실행하지 않음.
- 검증용 기본 template은 정상 schema지만 capture 불가. 장치 등록 성공으로 보고하지 않는다.

## 남은 이슈

1. Jetson 네트워크 복구 및 wrist/top/oblique 실제 by-id 확인 필요.
2. Astra bridge 고유 식별이 안 되면 top은 BLOCKED; 숫자 장치 대체 금지.
3. 공식0.6.0 별도 설치 환경/Jetson 검증, model rename map 확인은 미완료.
4. 실제 FPS/연속 갱신/동시 3카메라 점검은 단일프레임 검사와 별도로 필요.

## 보존/커밋/종료

serial/robot import와 open은 새 검사 경로에 없고, 실제 로봇 제어0.
서비스/안전 제한/torque/calibration/GPU환경/원본 데이터 변경0.
커밋은 로컬 vla/main에만 남기며 원격은 NOT_PUSHED. 정확한 commit은 최종 응답과
`git log -1 --format=%H`로 확인한다(자기 commit hash를 파일에 넣지 않는다).
1단계에서 종료. 다음 단계는 사용자가 “다음”이라고 요청할 때만 진행한다.
원복은 원래 작업 사본을 계속 사용하거나 이 변경 commit을 revert한다.
