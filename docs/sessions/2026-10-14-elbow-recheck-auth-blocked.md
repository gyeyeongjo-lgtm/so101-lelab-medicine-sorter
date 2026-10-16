# Elbow 현재값 재확인 — SSH 인증 차단

사용자가 Elbow를 다시 확인해 달라고 요청했다. 마지막 Jetson follower read-only 3회는 Elbow Present raw `3122` / `+100.087912°`, Goal raw `0`, Torque OFF, Moving `0`으로 동일했다. 기존 Elbow upper는 `+95.011°`다. 이는 **지난 측정 시점**의 증거이며 이번 요청의 fresh 측정값이 아니다.

Jetson `192.168.50.20:22`까지 연결됐지만 `jetson3` SSH 인증이 거부됐다. 따라서 기존 쓰기 차단 `scripts/read_follower_pose_telemetry.py`를 재실행하지 못했고 fresh Present/Goal/Torque/Moving은 `NOT_VERIFIED`다. 열린 LeLab 홈 화면은 Ready 및 과거 trace-pre-connect 오류를 표시하지만 현재 Elbow register는 보여 주지 않는다. Teleoperation을 시작하거나 `/joint-positions`를 호출하지 않았다.

사용자가 재확인을 다시 요청해 같은 대상에 비대화형 SSH로 2차 접속했으나 `Permission denied (publickey,password)`가 재현됐다. 설치본 실행/시리얼 접근은 여전히 `NOT_RUN`이다. 기존 `/ws/joint-data`는 텔레옵 비활성 상태에서 fresh follower register를 제공하지 않고, `/joint-positions`는 과거 버스 충돌 사례가 있어 우회 호출하지 않았다.

모터·Goal·Torque·설정 write `0`, USB/전원/서비스 조작 `0`, 현재 자세 변경 `0`. teaching/GRASP/LIFT는 `NOT_RUN`; `NEXT_LIVE_COMMAND=NONE`. Jetson의 인증된 read-only 접근 또는 현장 read-only 측정 결과가 필요하다. 원본 로그·자격증명은 저장하지 않았다. 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
