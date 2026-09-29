# SO-101 LeLab medicine sorter

Jetson Orin Nano에서 LeLab·LeRobot 기반 SO-101과 고정형 Orbbec Astra RGB-D 카메라를 사용해, 빈 약통 모형을 검출하고 검증된 좌표로 분류하는 연구용 프로토타입 저장소다.

2026-09-28 기준으로 Astra RGB intrinsic, ArUco 작업대 좌표, 2.5D depth 안정성, 약통 YOLO 저장·live 스모크를 통과했다. World→Robot Base 변환은 4점 fit 오차로 거부됐고, 닫힌 fingertip TCP 6점 재수집 중이다. 검증된 `T_B_W`, grasp offset, 작업공간 한계가 없으므로 `robot_enabled=false`를 유지한다.

## Jetson 웹 화면

- `http://192.168.50.20:8020/`: Astra 약통 YOLO·ArUco 작업대 overlay와 RealSense 사선 프리뷰. POST·로봇 제어 endpoint는 없다.
- `http://192.168.50.20:8010/`: 이전 Astra·RealSense 촬영/검토 UI. 8020 배포 후에는 legacy service로 비활성화될 수 있다.
- `http://192.168.50.20:8011/`: 기존 손목/천장 3카메라 VLM 사진·동작 영상 촬영 도구. 8010의 빠른 YOLO 검토 큐와 목적이 다르며 서로 대체하지 않는다.

두 화면 모두 카메라/데이터 도구이며 로봇 명령을 보내지 않는다. LeLab 텔레오퍼레이션·녹화·추론 상태를 먼저 확인한다.

## 먼저 읽을 문서

- `docs/STATUS.md`: 현재 판정과 다음 한 단계
- `docs/PORT_MAPPING.md`: 실제 USB 식별 근거
- `docs/RECORDING_DEBUG.md`: 로그·설치 소스 기반 TX/RX 분석
- `docs/ENVIRONMENT.md`: Mac/Jetson 실행 환경
- `docs/ARUCO_STAGE1.md`: ArUco 인쇄·부착과 camera-only ID 가시성 검사
- `docs/ARUCO_TABLE.md`: 실측 marker 중심을 이용한 2D 작업대 좌표 변환
- `docs/ASTRA_RGBD_PIPELINE.md`: Astra RGB–Depth 정합과 Camera→World→Robot 좌표 통합 계획
- `docs/CURRENT_SYSTEM_AND_ARUCO.md`: 현재 3카메라·7마커 구성, 진행 결과, 다음 단계
- `docs/sessions/`: 날짜별 작업 기록

## 안전 원칙

실제 모터 동작, 토크 변경, USB 재연결은 현장 안전 확인 뒤 승인된 범위에서만 수행한다. 원시 로그, 데이터셋, 비밀번호, 키, 토큰 및 개인정보는 Git에 넣지 않는다.

## 검사

하드웨어 없이 실행 가능한 테스트:

```bash
python3 -m unittest -v tests/test_inspect_ports.py tests/test_preflight.py
python3 -m unittest -v tests/test_medicine_review_web.py
python3 -m unittest -v tests/test_urdf_forward_kinematics.py tests/test_fit_robot_world_transform.py
```

`scripts/inspect_ports.py`와 `scripts/preflight.py`는 기본 경로에서 sysfs와 파일 메타데이터만 읽으며 serial 또는 camera 장치를 열지 않는다.
