# `recording-worker` 문맥 계측 후보 — 아직 배포하지 않음

다음 실제 회귀에서 모터 register나 torque sequence를 바꾸지 않고 LeLab 런타임 차이만
확인하기 위한 source-only 계측안이다. Jetson 설치본에는 아직 적용하지 않았다.

기록할 지점:

- `recording_worker` 시작: thread name/ident와 dataset id
- `record_with_web_events` 진입 및 `LeRobotDataset.create()` 완료: thread 문맥,
  camera 수, video/streaming 플래그
- follower/leader bus connect, calibration write, camera connect, configure 완료 시각과
  각 단계 소요 시간
- `record_loop` 진입 시각

첫 observation wrapper는 이 후보에 포함하지 않는다. `Goal_Position` write, calibration 값, torque 설정, baudrate, return-delay,
USB 연결은 이 후보에서 변경하지 않는다. 예외 문자열·소요 시간·thread 문맥 외에
비밀번호, 토큰, 데이터셋 프레임은 기록하지 않는다.

적용 전 검증:

1. pre-A/B 원본 `record.py` hash 확인
2. unified diff dry-run 및 `py_compile`
3. 서비스·설정·journal 백업
4. 별도 현장 안전 확인 뒤 무카메라 worker 회귀 1회
5. 실패 시 즉시 원본 롤백, 성공해도 카메라 회귀는 별도 승인
