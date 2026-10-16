# Elbow fresh read-only 재확인

사용자 제공 SSH 인증으로 Jetson `192.168.50.20`에 접속했다. 비밀번호는 파일/로그/명령 인자에 저장하지 않았다. LeLab teleoperation/recording/inference가 모두 inactive이고 canonical follower `5AE6058306→/dev/ttyACM1`, leader `5AE6085272→/dev/ttyACM0`, privileged `fuser`에서 양 포트 점유자가 없음을 확인했다. 기존 `read_follower_pose_telemetry.py`의 Jetson SHA가 로컬 `7c440b81c503735df10d62662c72e1c4b8f1fee3dcbc4ceada5f5c40065f3c56`과 같았다. 첫 기본 `python`은 serial 모듈 부재로 진단 시작 전 실패했고, 실제 LeLab 설치 Python으로 재실행했다.

쓰기를 차단한 follower 도구로 0.2초 간격 3회 읽었다. 세 표본 Present raw `[2029,1472,2774,2658,1612,489]`와 arm degree `[-6.373626,-42.417582,+69.494505,+50.769231,-22.197802]`, gripper `4.651163%`가 동일했다. Goal raw 전 축 `0`, Torque_Enable 전 축 `0`, Moving 전 축 `0`, Present_Load diagnostic 전 축 `0`, Tmax `37°C`였다. Elbow는 기존 `+95.011°` upper 안이며 마지막 기록 `+100.087912°` 대비 `−30.593407°`다. 변화 주체/시점은 이번 read-only 측정만으로 알 수 없다.

측정 도구가 보고한 motor/torque write `0/0`, 포트 정상 해제. 종료 뒤 privileged 양 포트 무점유를 다시 확인하고 SSH를 닫았다. 현재 팔 물리 지지·비접촉은 원격에서 새로 검증하지 않았다. Goal raw 전 축 0과 Torque OFF가 유지되므로 Torque ON, Goal sync, teleop/teaching, GRASP/LIFT는 `NOT_RUN`; `NEXT_LIVE_COMMAND=NONE`. 원본 telemetry/자격증명은 커밋하지 않는다. 이번 기록 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
