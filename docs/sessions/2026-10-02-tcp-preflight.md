# 2026-10-02 TCP 단일점 실험 사전 점검

- 사용자가 현장 안전을 보고하고 계속 진행을 요청했다. 최신 `docs/STATUS.md`, `docs/sessions/2026-10-01-teach-capture-web.md`, `docs/TEACH_CAPTURE_WEB.md`를 확인했다. 앞선 6점 적합은 조건수 4807.5와 P1 의사-holdout 17.675 mm 때문에 거부됐으며 자동 이동은 금지 상태다.
- Jetson `192.168.50.20`에 SSH로 접속했다. LeLab 8000의 기존 `lelab.service`는 inactive였고 8002·8022는 health 정상이며 teleoperation/recording/inference 모두 inactive였다. canonical serial symlink는 leader `5AE6085272`→ACM1, follower `5AE6058306`→ACM0이다. root `fuser -v /dev/ttyACM0 /dev/ttyACM1`은 점유 PID를 보고하지 않았다.
- 기존 8000 user service를 설정 변경 없이 한 번 시작했다. localhost 및 Mac에서 `/health` 정상, 8000의 teleoperation/recording/inference 모두 inactive를 확인했다. USB 재연결, 토크 변경, 모터 명령, 녹화·추론은 실행하지 않았다.
- Mac의 기존 8030 캡처 앱은 `127.0.0.1:8030`에서 계속 listen 중이었다. `/api/status`는 정면·사선·손목 프레임의 오류 null, `joint_age_ms=null`, `robot_control=false`를 보고했다. 브라우저에서 세 카메라 프리뷰를 확인하고 페이지를 후속 작업용으로 열어 두었다.
- 정면 영상에는 약통 3개와 바구니 3개가 X 접촉 영역에 있다. 따라서 다음 예정 실험인 단일 X(예: P5)의 손목 자세 다양화 접촉을 시작하지 않았다. 약통·바구니를 팔로워 작업 범위 밖으로 치우고 X·ID0–3 가시성과 손끝 표식, 사람의 범위 이탈·즉시 중단 준비, 시작 자세를 다시 확인한 뒤 **이번 텔레옵의 별도 명시 승인**이 필요하다. 지금 텔레옵·접촉 저장·TCP 추정·holdout은 `NOT_RUN`이며 `robot_enabled=false`, `motion_authorized=false`다.

## P5 다자세 접촉 수집 및 종료

- 이후 사용자가 약통·바구니를 치웠다. 정면 프리뷰에서 X 6개와 ID0–3, 빈 작업대를 확인했다. 8000의 세 제어 작업 inactive, `/robots/so-101` leader ACM1/follower ACM0, camera index 8/4/6, root `fuser`의 유일한 serial 점유 PID 413558이 LeLab uvicorn worker임을 확인했다. 8030의 세 프레임·관절 수신 정상도 확인했다.
- 사용자가 표시한 동일 플라스틱 끝 노출, 리더·팔로워 시작 자세 정렬, 사람의 팔로워 이동 범위 이탈·즉시 중단 준비를 현장에서 확인하고 P5 한 점·여러 손목 자세 텔레옵을 승인해 기존 LeLab UI에서 직접 시작했다. LeLab teleoperation active=true와 8030 관절 방송 신선도를 읽기 전용으로 확인했다. Mac은 LeLab 로봇 제어 API를 호출하지 않았다.
- 사용자의 각 P5 접촉·완전 정지 확인 직후 순서대로 자세 1 `20261002T045051_720031Z_eabc5733`, 자세 2 `20261002T045836_451189Z_c694d7be`, 자세 3 `20261002T045947_093828Z_6cd8133a`, 자세 4 `20261002T050239_477244Z_b154bcae`, holdout 자세 5 `20261002T050440_694034Z_81294177`을 8030에 저장했다. 각 폴더에 정면/사선/손목 640×480 JPEG 3장과 관절 방송 15개가 있다. 모든 JPEG SHA-256이 metadata와 일치한다. 최대 영상–관절 *수신 시각* 차이는 25.2 ms, 관절 최대 표준편차는 0.00397 rad다. 노출 시각 동기화는 아니다. 원본은 Git-ignore `.local/teach-captures/`에만 있다.
- 자세 1 손목 영상의 X가 두 손가락 사이에 보여 한 점 접촉을 영상만으로 단정할 수 없었다. 사용자는 표시한 한 손가락의 노출 플라스틱 끝이 직접 P5에 닿았음을 재확인했다. 이후 영상들도 손끝이 P5 근처에 보이나 가림·해상도 때문에 같은 단단한 끝의 정확한 물리점·높이는 `NOT_VERIFIED`다. 접촉 사실은 사용자 현장 보고와 영상 `PARTIAL`을 분리해 기록한다.
- 사용자가 손끝을 들고 기존 LeLab 텔레옵을 직접 종료했다. 종료 후 health 정상, teleoperation/recording/inference active=false를 확인했다. recording 내부 `current_phase=preparing`, `session_ended=false`, follower torque register는 `NOT_VERIFIED`다.

## 오프라인 jaw-link 고정점 진단

- 설치본과 일치하는 URDF SHA-256 `443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236`의 로컬 사본으로 FK를 계산했다. 처음에는 `gripper` 링크를 가정했으나 사용자가 표시한 손가락이 움직이는 쪽이라고 알려줬고, URDF에서 `Jaw`가 `gripper→jaw`를 연결함을 확인했다. 따라서 **최종 진단은 `base→jaw` 링크**를 사용한다. Jaw 값 변화를 고정 손끝 위반으로 단정한 초기 설명은 정정한다.
- 새 `scripts/fit_fixed_point_tcp.py`는 캡처 원본의 이미지 해시, 필수 프레임·관절 15개, 수신 간격·안정성, motion 차단 플래그와 URDF SHA-256을 검사한다. 네 자세 적합 + 마지막 자세 holdout의 jaw-link 결과는 rank 6, 조건수 23.113, fit RMSE 4.310 mm, fit 최대 6.576 mm, holdout 9.537 mm다. threshold 8 mm를 넘어 `REJECTED_DIAGNOSTIC`이다. TCP offset norm 119.540 mm는 승인된 TCP가 아니라 진단 추정치다.
- 네 fit 자세 Jaw 범위는 0.00320 rad, holdout Jaw와 fit 평균 차이는 0.02617 rad다. 움직이는 손가락에서는 jaw-link FK가 Jaw 변화를 모델링하므로 변화만으로 기각하지 않지만, 실제 오픈그리퍼 기구학 정확도와 접촉점은 검증되지 않았다. 기존 변환과 자동 이동은 계속 금지한다. 새 코드의 단위 테스트 5개, 관련 fit 테스트 총 16개 통과; 실제 로봇으로 재생·이동하는 시험은 `NOT_RUN`이다.
- 다음은 사용자의 새로운 현장 안전 확인과 별도 텔레옵 승인 뒤, 표시한 같은 손가락으로 P5에 검증용 *새 자세 한 개*를 접촉하고 Jaw 벌림을 앞의 네 자세와 비슷하게 유지해 저장하는 비교군이다. 반복 holdout도 실패하면 무작정 표본을 늘리지 않고 접촉점 영상 QA·jaw 기구학과 URDF 모델을 재검토한다. 현재 `use_for_robot_world_fit=false`, `robot_enabled=false`, `motion_authorized=false`다.
- 시험 기록: fit 관련 16개와 FK 3개 통과. 기존 캡처 웹 7개 시험은 첫 sandbox 실행에서 loopback bind `PermissionError`로 1개가 실패했으며, 같은 코드·조건을 네트워크 권한이 허용된 환경에서 재실행해 7개 모두 통과했다. 첫 실패는 제품 동작 실패가 아니라 시험 환경의 포트 권한 제한으로 남긴다.

## 추가 holdout 1점과 Jaw 수치 피드백

- 사용자가 별도 P5 한 점 촬영의 현장 안전과 명시 승인을 확인했다. LeLab 8000에서 teleoperation이 이미 active인 것을 읽었고, 사용자께서 직접 시작·이상 동작 없음·시작 자세 정렬·같은 손가락 플라스틱 끝의 P5 접촉·정지를 확인했다. 이전에 serial 유일 점유자로 확인한 LeLab worker PID 413558을 root `fuser`로 다시 확인했고 recording/inference inactive, 8030 세 영상·관절 수신 정상이었다. 정면 화면에 X 6개·ID0–3이 보이고 중앙 작업대는 비어 있었다. 왼쪽 아래 주변에 물체가 일부 보였으나 사용자는 작업 범위 밖이라고 현장 확인했다.
- 추가 holdout `20261002T052704_660698Z_4e67d851`에 640×480 JPEG 3장과 관절 방송 15개를 저장했다. 최대 영상–관절 수신 간격 14.6 ms, 관절 표준편차 0 rad였다. 사용자가 텔레옵을 직접 종료했고 8000의 teleoperation/recording/inference 모두 inactive를 확인했다. 정면·사선·손목 영상의 P5 주변에 손끝은 보이지만 같은 단일 플라스틱 끝의 정확한 물리 접촉점·높이는 `NOT_VERIFIED`다.
- 처음 네 fit 자세를 고정한 `base→jaw` 재진단에서 새 holdout 오차 8.793 mm로 8 mm 기준을 넘었다. 앞선 holdout 9.537 mm보다 낮지만 여전히 `REJECTED_DIAGNOSTIC`다. 새 Jaw 0.05875 rad는 앞선 네 fit Jaw 0.08331–0.08652 rad와 다르다. 움직이는 jaw-link FK가 Jaw 변화를 포함하므로 그 자체는 거부 사유가 아니지만, 의도한 '같은 Jaw 조건의 비교군'은 아니다. 두 holdout의 base 잔차 벡터는 각각 약 [7.96, 2.53, -4.60] / [6.15, -0.20, -6.28] mm로 방향 cosine 0.9225다. 공통 방향의 편차는 체계적 모델/접촉 차이의 가설이며 원인은 확정하지 않는다. 두 holdout 모두 robot-world fit·모션에 사용하지 않는다.
- 원인 분리를 위해 Mac 8030의 `/api/status`에 최근 관절 방송의 `joint_jaw_rad`를 추가했다. 400 ms보다 오래된 방송은 null을 반환한다. 단위 테스트 8개 통과. 정확한 Mac PID 37775의 기존 캡처 서버 명령을 확인한 뒤, 사용자 텔레옵 inactive에서 그 프로세스만 SIGTERM으로 종료하고 동일 인자·경로로 다시 시작했다. 8030의 세 카메라 오류 null, 새 Jaw 필드, 8000 teleoperation inactive를 확인했다. Jetson 8000·serial·torque·USB 설정은 변경하지 않았다.
- 후속 한 변수 비교는 사용자가 별도 현장 안전·텔레옵 승인을 주는 경우에만, P5에 접촉하기 **전** 8030 화면의 신선한 Jaw 방송을 보고 처음 네 자세 범위 0.083–0.087 rad 근처로 맞추는 것이다. 무리한 손가락 조작이나 토크 변경은 하지 않는다. 그 후 안전한 새 손목 자세에서 같은 움직이는 손가락 끝으로 P5 한 점을 저장하고, 미사용 자세의 오차를 다시 평가한다. 그 전까지 `robot_enabled=false`, `motion_authorized=false`다.
