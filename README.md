# SO-101 LeLab medicine sorter

Jetson Orin Nano에서 LeLab·LeRobot 기반 SO-101 두 팔과 C920 카메라의 녹화 경로를 복구하고, 이후 빈 약통 분류 실험으로 확장하기 위한 비공개 작업 저장소다.

현재 단계는 **부분 해결 / 현장 안전 확인 대기**다. 캘리브레이션 중 발생했던 TX/RX 오류는 동일 serial bus의 동시 읽기와 일치하며 기존 패치 뒤 재발하지 않았다. 다만 실제 데이터셋 녹화 요청은 확보된 journal에 없었고, 현재 팔로워 serial과 카메라 2대가 연결되어 있지 않아 녹화 회귀는 아직 실행하지 않았다.

## 먼저 읽을 문서

- `docs/STATUS.md`: 현재 판정과 다음 한 단계
- `docs/PORT_MAPPING.md`: 실제 USB 식별 근거
- `docs/RECORDING_DEBUG.md`: 로그·설치 소스 기반 TX/RX 분석
- `docs/ENVIRONMENT.md`: Mac/Jetson 실행 환경
- `docs/sessions/`: 날짜별 작업 기록

## 안전 원칙

실제 모터 동작, 토크 변경, USB 재연결은 현장 안전 확인 뒤 승인된 범위에서만 수행한다. 원시 로그, 데이터셋, 비밀번호, 키, 토큰 및 개인정보는 Git에 넣지 않는다.

## 검사

하드웨어 없이 실행 가능한 테스트:

```bash
python3 -m unittest -v tests/test_inspect_ports.py tests/test_preflight.py
```

`scripts/inspect_ports.py`와 `scripts/preflight.py`는 기본 경로에서 sysfs와 파일 메타데이터만 읽으며 serial 또는 camera 장치를 열지 않는다.
