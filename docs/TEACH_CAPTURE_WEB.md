# 접촉 증거 캡처 페이지 (로봇 제어 없음)

## 목적과 경계

`scripts/teach_capture_web.py`는 Mac에서 LeLab 8000의 기존 정면 Astra `/camera-preview/8`, 사선 RealSense `/camera-preview/4`, 손목 카메라 `/camera-preview/6`, `/ws/joint-data` 방송만 구독한다. 정면·사선은 저장 필수이고 손목 영상은 신선할 때만 함께 저장하는 보조 증거다. 로봇 serial, `/joint-positions`, 텔레옵 시작·정지, 토크, 캘리브레이션, USB 설정을 건드리지 않는다. 기존 8010 카메라 서버는 실제 장치를 직접 열어 Astra bridge/LeLab과 충돌할 수 있으므로 이 절차에 사용하지 않는다.

기본 주소는 Mac의 `http://127.0.0.1:8030/`이다. loopback에만 바인딩하고 외부 공개나 자동 시작을 하지 않는다. Mac 터미널의 실행 세션이 종료되면 페이지도 내려간다.

## 실행과 데이터

```sh
python3 scripts/teach_capture_web.py --lelab-url http://192.168.50.20:8000 --host 127.0.0.1 --port 8030 --output-root .local/teach-captures
```

`.local/teach-captures/`는 Git ignore 대상이다. 저장 버튼은 기존 LeLab 텔레옵이 활성이고, 현장 접촉 확인 체크가 있으며, 최근 관절 방송 15개가 안정적이고, 정면·사선 프레임이 관절 마지막 방송 수신 시점과 각각 250 ms 이내일 때만 작동한다. 손목 프레임도 같은 신선도 조건을 만족하면 선택적으로 포함하고, 불가하면 `optional_camera_omitted`에 기록해 저장을 계속한다. 각 지점의 JPEG, SHA-256, 수신 시각, 원본 관절 방송 15개, 평균·안정성, 수신 시각 차이를 로컬 폴더에 저장한다. 화면에 로봇 제어 버튼은 없다. 서버 시작 시 `websocket-client`가 없는 Python 환경이면 웹 바인딩 전에 실패한다.

카메라 센서 노출 시각이 LeLab MJPEG에 없으므로 위 시간차는 **Mac 서버의 수신 시각 근사**일 뿐 완전한 센서 동기화가 아니다. 저장된 `contact`는 사용자 현장 확인이며 영상 검수 전 접촉 성공 판정이 아니다. 모든 metadata는 `use_for_robot_world_fit=false`, `robot_enabled=false`, `motion_authorized=false`로 생성된다. 자동 좌표 적합이나 로봇 구동에 투입하지 않는다.

## 다음 teach의 현장 절차

1. ID0–3, X 표시, 두 카메라의 위치를 고정하고 약통·바구니를 작업 범위에서 치운다.
2. LeLab의 세 제어 작업 inactive, canonical leader/follower 역할과 serial 점유 상태, 사람의 이동 범위 이탈·즉시 중단 방법·시작 자세를 새로 확인한다.
3. **별도 명시 승인**이 있을 때만 기존 LeLab 텔레옵을 한 번 시작한다. 리더를 천천히 움직이는 방식이지 소프트웨어 속도 제한이 아니다.
4. 표시한 단일 손가락의 단단한 끝을 각 X에 가볍게 대고 멈춘 다음 페이지에서 지점·현장 확인을 선택해 저장한다. 화면의 정면·사선 영상을 보며 영상 접촉 QA를 별도로 수행한다. 손목 자세를 다양하게 하되 같은 물리 접촉점을 유지한다.
5. 텔레옵을 종료하고 세 작업 inactive를 확인한다. 그 뒤에만 로컬 자료를 검토해 World 좌표와 연결한다. 학습에 쓰지 않은 holdout 점의 오차를 검사하고 거부 기준을 통과하기 전 로봇 이동을 승인하지 않는다.

2026-10-01 P1·P6에서 정면·사선 640×480 JPEG와 관절 방송 15개를 실제 텔레옵 중 저장했다. 같은 날 별도 사용자 텔레옵에서 P2–P5는 정면·사선·손목 3영상과 관절 방송 15개씩을 저장했다. 전 JPEG의 SHA-256과 metadata가 일치하고 세 작업 inactive를 확인했다. 정확한 단일 손끝 접촉·독립 holdout은 아직 `NOT_VERIFIED`/`NOT_RUN`이며 robot-world 적합에 사용하지 않는다. 텔레옵 inactive일 때 저장 API는 HTTP 400으로 거부된다.
