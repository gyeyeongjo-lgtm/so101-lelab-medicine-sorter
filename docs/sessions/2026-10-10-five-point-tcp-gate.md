# 2026-10-10 5점 table→robot 세션: TCP 기준점 차단과 원복

- 사용자 현장 확인 뒤 읽기 전용 리더 정렬 5축 ±2° 이내. viewer PID `541243` 종료 및 두 USB 포트 해제 확인. LeLab 서비스 PID `541137`의 시작 로그에 `LELAB_TEMP_WRIST_ALIGN=1 guard=guarded_elbow_send` 확인.
- 8034 수신기 상태: ceiling camera fresh, P1/P2/P3/P4/H1 등록, 캡처 `[]`, `tcp_ready=false`, red opening 미측정. URDF에서 `Wrist_Roll`의 child가 `gripper`이므로 그 링크 원점은 모델상 회전축 중심이다. 실제 눈으로 선택한 물리적 중심과의 일치는 독립 측정으로 확인되지 않았다.
- 사용자는 직접 텔레옵을 시작했고 이후 종료·비접촉을 확인했다. 기준점 `(0,0,0) mm`을 `physical_reference_confirmed=true`로 등록하는 로컬 요청은 안전 검토에서 거부되어 **미실행**. 안전 검토는 불확실한 축 중심을 검증 완료로 저장하면 잘못된 좌표 캘리브레이션이 될 수 있다고 지적했다. 우회하지 않았다. 점 1–5 이동 지시·캡처 0/5, SE(2) fit/hold-out, live C robot XY, IK `NOT_RUN`.
- 종료 후 서버 teleop/recording/inference 모두 inactive, 포트 대상 점유 없음. 설치 현재값 SHA `teleoperate.py=042c5f76...ac7c54`, guard `1ca311d0...04b09`를 확인하고 복구본을 별도 보존한 뒤 각각 원래 백업 SHA `e3ac7525...9028d89`/`2e5ffa30...0118362`로 원복. 서비스 환경 `PYTHONUNBUFFERED=1`만 남기고 재시작, health `ok`, teleop inactive 확인. 원본 로그·비밀번호는 저장/커밋하지 않음. `NOT_COMMITTED/NOT_PUSHED`.
- 다음: 사용자가 실제 축 중심과 URDF 원점 간 오차 가능성을 이해하고 5점 캡처용 기준점 등록을 명시적으로 승인한 경우에만 다시 준비한다. 독립 H1 hold-out이 통과하기 전 자동 IK/실제 접근 금지. 다른 기준점을 선택하면 그 물리 오프셋을 별도 측정해야 한다.
