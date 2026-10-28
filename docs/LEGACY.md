# 기존 기능 보존 (VLA 경로와 구분)

2026-10-28. 여기서 legacy는 삭제·중단되었다는 뜻이 아니라 새 VLA 구현과 구분하는 표기다.

- 기존 ArUco/YOLO 인식·좌표·고정 시연 코드와 파일 위치는 유지한다.
- `medicine_sorter/robot.py`, `medicine_sorter/web.py`와 기존 RobotController 제어 경로를
  이번 단계에서 수정하지 않는다. 새 카메라 점검기는 로봇 제어기에 연결되지 않는다.
- 기존 ACT/VLM 모델·데이터·calibration은 비교/복구용으로 보존한다.
- 기존 프리뷰 서버 `scripts/camera_preview_server.py`는 그대로 둔다. 새
  `scripts/check_vla_cameras.py`는 일회성 검사 도구이며 웹사이트 대체 서비스가 아니다.
- 기존55°C stop, 시작50°C 미만, Overload HOLD, Ctrl+C/web HOLD,
  disconnect 토크 유지, 명령당2° 제한을 변경하지 않았다.
- 공식 LeRobot0.6.0을 사용할 예정이며 mediflow vendored SmolVLA 파일을 공식 설치본에
  덮어쓰거나 혼용하지 않는다. 설치/모델 다운로드는 이번 단계에 없다.

새 경로와 미검증 항목: [VLA 1단계](VLA_STAGE1.md).
