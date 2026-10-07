# 2026-10-07 배치 후 현장·기존 데이터셋 검수

목적: 사용자가 큰 빈 약통 A를 출발 자리에 놓고 파란 바구니를 비운 뒤, 추가 모터 조작 없이 현재 카메라 장면과 기존 A/B/C 시연 자료가 오늘의 분류 규칙에 맞는지 확인한다. 사용자 확정 규칙은 A→파란 ID6, B→초록 ID5, C→빨강 ID4다.

## 예상 밖 텔레옵 시작과 즉시 중단

- 사전 상태: Jetson LeLab 8000 health `ok`, teleoperation/recording/inference 모두 active=false. 기존 robot 설정은 leader ACM1, follower ACM0, 카메라 8/4/6이다.
- LeLab 홈의 `Teleoperation` 버튼을 녹화 화면으로 가는 탐색 버튼으로 잘못 판단해 클릭했다. 실제 UI는 텔레옵을 즉시 시작하고 `/teleoperation-status`가 active=true를 반환했다. 사용자의 이번 승인 범위에는 모터 시작이 없었다.
- 즉시 공식 `POST /stop-teleoperation` 1회 성공 응답을 받고 다시 세 상태를 조회해 모두 active=false를 확인했다. 녹화는 active=false지만 내부 `current_phase=preparing`, `session_ended=false`이므로 완결된 세션으로 보지 않는다.
- 사용자 현장 확인: 예상 밖 팔 움직임·약통/바구니 접촉 없고 현재 안전하다. 영상만으로 물리 무동작을 독립 확정하지 않는다. 오류를 숨기지 않으며 해당 버튼은 단순 페이지 탐색에 재사용하지 않는다. 이후 새 텔레옵/녹화/추론/자동 재생 `NOT_RUN`.

## 현재 배치의 읽기 전용 카메라 검사

- 기존 Mac 8030 캐시 서버 상태: 정면/사선/손목 frame age 약 59.7/60.8/58.3 ms, 오류 null, `robot_control=false`, 텔레옵 중단 후 관절값 stale. 새로운 카메라 장치를 열지 않았다.
- 정면 캐시 JPEG 한 장을 Jetson 임시 폴더로 복사해 기존 ONNX 스모크 모델에 입력했다. Jetson 설치 검출 스크립트 SHA-256 `ad800e27...f2b9f53`는 저장소 원본과 같고 설치 LeLab Python의 OpenCV는 4.13.0이다. 약통 한 후보 confidence 0.968962, bbox `[421.569,206.586,456.775,257.626]` 픽셀이다. 모델은 용기 한 클래스만 검출하며 A/B/C 신원은 사용자 확인이다.
- 정면 프레임에서 ID0–6 전부 검출. 현재 ID4/5/6은 정면 화면 왼쪽/가운데/오른쪽이고 사선 영상에서 해당 바구니가 빨강/초록/파랑임을 확인했다. 정면 RGB 색감은 강하게 변해 육안 색만으로는 분류하지 않는다.
- 현재 작업대 평면 투영의 후보 중심은 `[83.245,335.484]` mm, 현행 픽업 ROI는 x=101–273, y=251–379 mm이다. 단일 후보가 ROI 밖이라 inside count=0. 기존 경로 결정기는 A 입력에 `BLOCKED/pickup_candidate_not_unique`, target=null, robot/motion=false를 반환한다. 이는 현행 ROI와 배치 불일치의 진단이지 사용자가 잘못 놓았다는 판정이 아니며, 높이 미보정 좌표를 모터 명령에 사용하지 않는다.
- 사용자 확인 큰 A 장면의 정면 캐시 JPEG 한 장과 SHA·단일 프레임 한계를 Git 제외 `.local/medicine-class-scenes/20261007_A_source.*`에 복사했다. 이는 클래스 예시 1개일 뿐 분류기 학습/평가 자료로 충분하지 않다. 사용자에게 텔레옵이 꺼진 상태로 같은 자리에 중간 B, 이후 작은 C를 각각 바꿔 놓도록 요청해 현 장면 예시를 수집한다. 이 교체는 사람이 직접 수행하며 에이전트는 모터·USB·LeLab 설정을 건드리지 않는다.

## Jetson 기존 LeRobot 자료 검수

- 실제 설치 LeLab Python 3.14.7, PyArrow 25.0.1, PyAV 15.1.0을 확인하고 로컬 캐시의 `meta/info.json`, `meta/tasks.parquet`, 에피소드 인덱스와 첫 에피소드 정면 AV1 영상만 읽었다. 데이터셋·모델 파일은 수정하지 않았다.
- A v2(2026-10-02): 60 episode/32,597 frame; B v1(2026-09-28): 60/27,613; C test(2026-09-28): 60/28,966. 모두 메타상 30fps·세 영상 채널·한 task. task 문구는 각각 `Pick up medicine bottle X and place it into basket X.`이며 바구니 색·ID는 없다. 메타 숫자만으로 180회 모두 성공하거나 현재 장면과 호환된다고 보지 않는다.
- 각 dataset의 첫 episode 시작·끝 정면 프레임을 추출해 종료 시 병 위치와 `DICT_4X4_50` 바구니 마커 중심을 교차 확인했다. A 첫 시연은 오른쪽 ID6에 병이 남음. B 첫 시연은 가운데 ID6에 병이 남음. C 첫 시연은 왼쪽 ID5에 병이 남음. 해당 시연의 바구니 좌우 배치는 서로 달라 좌우 이름은 목표를 규정하지 않는다.
- 같은 설치 ONNX 약통 검출기를 이 6장에 오프라인 실행하면 A 시작·끝은 각 0개, B는 3/3개, C는 3/3개 후보를 출력한다. A 영상의 강한 자홍색 조명 등 장면 차이로 보이지만 원인을 분리 검증하지 않았고 일반 성능 수치가 아니다. 현재 A 사진은 1개(confidence 0.968962) 검출됐다. 과거 자료 전체에 현재 한 클래스 검출기를 바로 적용할 수 있다고 가정하지 않는다.
- 오늘 규칙에 A 첫 시연은 일치, B/C 첫 시연은 각각 ID6 vs 목표 ID5, ID5 vs 목표 ID4로 불일치한다. 따라서 기존 B/C 데이터셋과 대응 ACT 체크포인트의 현재 분류 경로 직접 사용은 `REJECTED`. 나머지 59회씩과 모델 행동은 `NOT_VERIFIED`. 자동 추론·모터 시험 `NOT_RUN`.

## 다음 게이트

### B 배치 보고 후 카메라 재확인

- 사용자에게서 `B 배치완료` 보고를 받았다. Jetson 8000의 teleoperation/recording/inference는 모두 active=false, Mac 8030의 세 카메라 오류 null·`robot_control=false`였다. 녹화 내부 `current_phase=preparing`, `session_ended=false`는 세션 종료 증거로 취급하지 않는다.
- 새 정면 캐시 JPEG에서 이전 A 출발 자리(화면 약 x=442,y=224)의 약통이 그대로 있고, 화면 약 x=375,y=231에 다른 약통이 추가됐다. 화면 왼쪽에도 약통이 보인다. B가 추가된 약통인지는 사용자 보고 외에 독립 확인이 없으며, A와 동일 자리의 단독 B 비교 자료가 아니다.
- 이 장면은 `.local/medicine-class-scenes/20261007_B_multibottle_unverified.jpg`에 원본 SHA-256 `85f62fe5a8600740b18fe64e98a5095a8354b6a4cdc7b8ed73407c095f99fc90` 및 제한 메타데이터와 함께 Git 제외로 보존했다. B 학습 샘플 승인·검출기 재학습·로봇 동작은 `NOT_RUN`. 사용자에게 텔레옵을 끈 채 B 하나만 기존 A 자리에 두는 재배치를 요청한다.

### B 단독 출발 자리 재배치 후 재촬영

- 사용자 `B 단독 배치 완료` 확인 후 Jetson 8000의 텔레옵·녹화·추론 active=false와 Mac 8030의 세 영상 수신 오류 null·`robot_control=false`를 읽기 전용으로 재확인했다. 녹화 내부의 `current_phase=preparing`, `session_ended=false`는 완료로 간주하지 않는다.
- 정면 캐시 한 장에서 이전 A 자리인 화면 약 x=440,y=228에 약통 하나만 보이고, 나머지 약통은 화면 왼쪽으로 치워져 있다. ID0–6은 육안으로 보이나 이번 장면의 자동 마커 재검출 및 용기 검출은 `NOT_RUN`. 한 개가 B라는 신원은 사용자 확인이고 영상만의 독립 분류 결과가 아니다.
- `.local/medicine-class-scenes/20261007_B_source.jpg` SHA-256 `571db2c17f78f3134fdfc2be1071957ae757ddb5ae3ff29d211a735d4f19b748` 및 제한 메타데이터를 Git 제외로 보존했다. A/B 각 한 장은 분류기 학습·성능 평가에 충분하지 않으며 픽업 ROI와 로봇 좌표/경로 문제도 해결하지 않는다. 로봇 동작·자동 추론·분류기 학습 `NOT_RUN`. 다음은 텔레옵을 끈 채 사용자에게 C 한 개를 같은 자리에 놓도록 요청한다.
- 후속 A/B 기존 ONNX 검출기 비교는 `NOT_RUN`: Mac 기본/번들 Python에 OpenCV가 없고, Jetson 키 기반 비대화형 SSH는 인증 거부됐다. 기존 로컬 askpass 경유 SSH도 이번 시도에서 응답을 완료하지 않아 작업자가 해당 시도를 중단했다. 비밀번호를 명령줄·출력·Git에 쓰지 않았고 원격 설정·파일·모터 작업은 수행하지 않았다. LeLab 8000과 Mac 8030 읽기 전용 상태 조회는 별도로 성공했다.

### C 배치 후 카메라 확보와 8000 장애

- 사용자 `C 배치 완료` 시점에 Jetson 8000의 세 상태 API는 연결 거부이고 Mac 8030 카메라 나이는 약 622,900 ms로 신선하지 않았다. 8030의 JPEG를 새 C 사진으로 오인해 저장하지 않았다. Jetson 8002·8022 health는 정상이고 두 인스턴스의 텔레옵·녹화·추론은 모두 active=false였다. 8002의 `/robots/so-101`은 기존 leader ACM1/follower ACM0 및 카메라 8/4/6을 가리켰다.
- 기존 8002 정면 `/camera-preview/8` 스트림을 한 번 열어 JPEG 하나(640×480)를 읽고 즉시 닫았다. 사진에서 이전 A/B 출발 자리 약 x=440,y=228에 약통 한 개가 보이고 다른 약통 두 개는 화면 위쪽 왼편에 있다. 출발 자리 약통이 C라는 판정은 사용자 보고에 의존한다. 자동 검출기·ArUco 재검출은 `NOT_RUN`이다.
- 원본 `.local/medicine-class-scenes/20261007_C_source.jpg` SHA-256 `75b1fda5cf21fb98db439f53861708db14120bd393d0cbcb3147b27418c60149`와 제한 메타데이터를 Git 제외로 보존했다. 사용자 규칙 C→빨강 ID4만 기록하며 이 사진을 분류기 학습/성능평가나 로봇 좌표로 쓰지 않는다. 8000 서비스·Mac 8030 신선도 복구, 기존 데이터셋 전수 검수, ROI/World→Base/TCP 검증은 아직 남아 있다. 서비스·USB·모터·토크 설정은 변경하지 않았다.

### C 주변 약통 제거 후 재촬영

- 사용자가 다른 약통을 치우고 재촬영을 요청했다. 8000 health 연결 거부, Mac 8030의 세 영상 캐시는 약 934초 경과였으므로 사용하지 않았다. 8002 텔레옵·녹화·추론 active=false를 확인하고 기존 정면 프리뷰 8에서 JPEG 한 장을 읽어 즉시 닫았다.
- 새 640×480 화면에는 출발 자리 약 x=440,y=228의 약통 하나가 남고, 앞선 C 사진에서 위쪽 왼편에 보이던 두 약통은 사라졌다. 화면 맨 왼쪽의 보라색 용기 신원은 판정하지 않았다. `.local/medicine-class-scenes/20261007_C_source_cleared.jpg` SHA-256 `3467772b59ca8c3d682306a61749a55ccce7aa636a3aeb90506cb1481a49b9fa`와 메타데이터를 Git 제외로 저장했다. 앞선 원본은 보존하고 새 사진을 C 출발 자리의 더 깨끗한 참고 장면으로 우선한다. B와 C 신원은 사용자 보고에 따른다.
- SSH 진단 중 구 문서의 `chosun` 계정 시도는 인증 실패했으나 현재 환경 문서의 `jetson3` 계정으로는 로그인에 성공했다. 사용자가 턴을 중단해 원격 명령은 실행하지 않았으며 남은 대화형 세션은 `exit`으로 종료했다. 비밀번호는 명령줄·출력·파일·Git에 기록하지 않았다. 8000 서비스 원인 조사·재시작은 `NOT_RUN`이다.

### LeLab 재시작 보고 뒤 C 재촬영

- 사용자는 LeLab을 켰다고 보고했으나 8000 health·세 상태 API는 연결 거부이고 Mac 8030 카메라 캐시는 약 1,366초 오래됐다. SSH로 `systemctl --user is-active lelab.service`=`inactive`, `show`는 `ActiveState=inactive`, `SubState=dead`, `MainPID=0`, `Result=success`, `ExecMainStatus=0`임을 읽기 전용 확인했다. 서비스 시작·재시작은 이번 요청에서 실행하지 않았다. 8002는 텔레옵·녹화·추론 inactive다.
- 8002의 기존 정면 프리뷰 8에서 JPEG 한 장만 읽고 닫았다. 새 사진의 출발 자리에는 이전과 같은 위치의 약통 한 개가 보이고 위쪽 다른 약통 두 개는 계속 없다. 화면 왼쪽의 보라색 용기는 신원 판정하지 않았다. 원본 `.local/medicine-class-scenes/20261007_C_source_reshoot.jpg` SHA-256 `c9af2923d7f3bcd4d4de2e8d104b92bd6d23659ceb1a31f9c51f650002acb47c`와 제한 메타데이터를 Git 제외로 보존했다. 앞선 C 사진은 원본 증거로 보존하되 새로운 분류 후보로 사용하지 않는다.
- A/B/C 신원은 사용자 보고에 따른 단일 프레임 예시다. 검출기 비교·분류기 학습·자동 경로 결정·로봇 동작은 `NOT_RUN`.

### 사용자 요청의 LeLab 8000 복구 및 C 세 카메라 촬영

- 직전 C 사진들은 정면 카메라 한 대의 사진이었다. 사용자 요청에 따라 Jetson 8000을 복구하기 전, 8002·8022 텔레옵/녹화/추론 inactive, canonical follower `5AE6058306`→`/dev/ttyACM0`, leader `5AE6085272`→`/dev/ttyACM1`, root `fuser -v` 두 포트 점유 출력 없음, 기존 `lelab.service` inactive/dead·PID 0을 확인했다. 기존 user service에 `start`만 수행했다. 이후 active/running·health ok, 8000 세 제어 작업 active=false다. 설정·USB·모터·토크 변경 `NOT_RUN`.
- Mac 8030은 8000 복구 후에도 약 2,428초 된 캐시를 반환했다. 8030 listener PID 2654의 실행 명령이 기존 `scripts/teach_capture_web.py --lelab-url http://192.168.50.20:8000 --host 127.0.0.1 --port 8030 --output-root .local/teach-captures`임과 `robot_control=false`를 확인했다. 해당 프로세스만 TERM으로 정상 종료하고 같은 명령으로 다시 시작했다. 이후 세 영상 age 약 19–37 ms·오류 null, 로봇 제어 false다.
- 새 640×480 정면·사선·손목 JPEG 각 한 장을 8030 캐시에서 병렬 요청했다. 세 원본 SHA-256은 정면 `81d2f1ecf6d325c23bf4eed6305441a1ff6da74fa3d7b476c91333efdc7b4ab1`, 사선 `2ba177a0b70761167666806263894ae9272431ba58eb6835fbf566a32c86fb99`, 손목 `df57ed8328a490dc33c25ff8d169c741d80012d066eb791d753e8145aec6ba50`이다. Git 제외 `.local/medicine-class-scenes/20261007_C_threeview_*`에 보존했다. 정면·사선에는 C로 보고된 약통이 보이나, 현재 정지 팔 자세의 손목 영상에는 그리퍼만 보인다. 세 카메라 수신 성공이지 약통이 세 각도 모두에서 보이는 촬영은 아니다. 수신시각 근사 자료이며 노출시각 동기화 `NOT_VERIFIED`.
- 촬영 후 8000 텔레옵·녹화·추론 active=false, 8030 세 영상 fresh·오류 null·`robot_control=false`를 재확인했다. 약통 A/B/C 자동 분류 학습·평가, 손목 카메라의 약통 가시성 확보를 위한 팔 이동, 자동 모터 동작은 `NOT_RUN`.

### 현장 작업 없는 기존 데이터셋 인벤토리 재검수

- 사용자에게 당장 추가 텔레옵·촬영은 필요 없다고 알리고 Jetson 기존 로컬 LeRobot 캐시를 읽기 전용으로 점검했다. 현재 사용 후보는 A v2 `...20261002_173846` 60 episode/32,597 frame, B v1 `...20260928_203749` 60/27,613, C test `...20260928_154245` 60/28,966이다. 각각 기존 MP4 파일 7/6/7개가 존재하며 총 크기는 1,237,551,079/972,342,365/992,516,968 byte다. A v2의 다른 임시 디렉터리 네 개는 메타데이터상 0 episode이므로 후보로 세지 않았다.
- 이는 파일 존재·메타데이터 일관성 확인이지 180회의 투입 성공·현재 색/ID 규칙 적합 판정이 아니다. 첫 episode에서 B→ID6, C→ID5 불일치가 이미 확인됐으므로, 다음은 각 종료 프레임의 실제 목적지 마커와 성공 여부를 오프라인으로 전수 검수하는 것이다. 이번 턴 영상 재생·추가 추출·모터 제어 `NOT_RUN`; 원본은 변경하지 않았다.

### 오프라인 종료 프레임 180건 추출과 현재 A/B/C 사진의 단일 클래스 검출

- 새 `scripts/audit_medicine_episode_ends.py`는 원본 LeRobot v3 `meta/episodes`의 episode별 `file_index`·`to_timestamp`를 읽고 각 종료 직전 프레임을 PyAV로 seek/decode한다. 원본 카메라·serial·LeLab API는 열지 않으며 새 출력 디렉터리가 있으면 덮어쓰지 않는다. 설치 OpenCV 4.13의 `ArucoDetector` API 차이를 3건 시험에서 발견해 호환 수정한 후 A/B/C 60건씩 전부 추출했다. 5개 단위 테스트와 Jetson 실제 설치 런타임 실행 통과. 원본 파일은 변경하지 않았다.
- Git 제외 `.local/dataset-episode-audit/20261007/lelab_{A,B,C}_ends_full_20261007/`에 각 연락표 JPEG와 JSON manifest를 보존했다. 인덱스 0–59 모두 존재하고 추출 프레임 시각과 metadata 목표 시각의 보고된 최대 차이는 0.0초다(보고값은 소수 넷째 자리 반올림). ArUco ID4·ID5는 각 60/60, ID6은 A 53/60·B 60/60·C 60/60 종료 프레임에서 검출됐다. A ID6 비검출 7장은 가림/조명 가능성이 있으므로 바구니 없음으로 판정하지 않는다. 연락표 육안으로 B의 중앙 ID6, C의 왼쪽 ID5에 약통이 반복적으로 보이는 양상은 첫 episode 불일치와 일치한다. 그러나 각 시연의 실제 투입 성공·병 신원은 한 종료 프레임만으로 독립 판정하지 않았고 `task_success=NOT_VERIFIED`를 모든 manifest 행에 유지했다. 기존 B/C 모델의 오늘 규칙 직접 사용은 계속 거부한다.
- 저장된 현재 A·B·C 출발 자리 정면 JPEG 각 한 장을 Jetson 임시 위치에 복사하고 설치 LeLab Python의 OpenCV DNN에서 기존 ONNX(SHA-256 `d2f8452ed72decf38198ce5aaa8d82c81397e96b85b78c449dbb73bc2cc5c846`)와 저장소 SHA가 일치하는 `detect_medicine_onnx.py`를 오프라인 실행했다. 클래스 0 후보는 A/B/C 각각 1개, confidence 0.968962/0.954861/0.908477, bbox `[421.569,206.586,456.775,257.626]`/`[420.563,215.952,453.643,256.040]`/`[423.911,215.363,449.996,251.292]` px다. JSON은 Git 제외 `.local/medicine-class-scenes/20261007_ABC_detection_report.json`에 보존했다. 이는 1장씩의 검출 성공이지 A/B/C 크기 분류나 실시간 일반화의 성능 평가가 아니다.
- 종료 뒤 8000 HTTP가 연결 거부이고 8030 캐시가 stale였다. Jetson SSH의 `systemctl --user status lelab.service`에는 19:17:08 `Stopping`/worker `SIGKILL`/`Stopped`가 보이고 현재 inactive/dead·Result=success·ExecMainStatus=0이다. `journalctl --user -u`는 journal 파일이 없어 stop 요청 주체를 확인하지 못했다. 오프라인 검사 자체는 LeLab 서비스 제어 API를 호출하지 않았고, 이번 턴 서비스 재시작도 `NOT_RUN`. 다음 실시간 검증 전에 서비스 종료 이유와 버스 소유권을 다시 확인한다.

첫째, A/B/C 각 자료의 에피소드별 실제 목표 마커와 성공 여부를 전수 검수해 유효 부분만 분리한다. 둘째, 현재 고정 출발 슬롯과 ROI를 카메라 여러 장·높이 확인으로 다시 정의한다. 셋째, World→Base/TCP, Elbow URDF/캘리브레이션 차이, 연속 경로 여유를 별도 검증한다. 이 전에는 어떤 기존 ACT 모델도 현재 장면에 실행하지 않는다. 원본 데이터셋·영상·비밀번호는 Git에 넣지 않는다.

이번 문서 점검 관련 분류·비전 단위 테스트는 5+9개 `PASS`. 종료 전 LeLab teleoperation/recording/inference active=false를 다시 확인했다. GitHub CLI 로그인 부재로 이슈 API 갱신은 `NOT_RUN`; 코드·문서의 커밋과 push 상태는 Git 이력으로 별도 확인한다.
