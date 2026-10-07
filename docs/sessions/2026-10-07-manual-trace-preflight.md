# 2026-10-07 수동 시연·캐시 영상 관찰 사전 점검

사용자는 현장 안전과 진행을 승인했다. 이 승인은 자동 관절 재생이나 ArUco 기반 자율 투입 허가로 확대하지 않는다. 목표는 사용자가 직접 기존 LeLab 텔레옵으로 빈 약통 모형 1개를 고정 출발 슬롯에서 빨강 ID4 바구니에 옮기는 동안, Mac에서 관절 방송과 기존 8030 캐시 정면·사선 영상만 읽기 전용으로 수집하는 것이다.

## 현재 확인

- Jetson `192.168.50.20` SSH 연결 가능. 8000 user `lelab.service`는 처음 inactive/dead였으며 기존 unit 그대로 시작한 후 active, health ok다. 텔레옵·녹화·추론 모두 inactive다. 8002·8022의 세 제어 작업도 inactive다.
- canonical USB: follower serial `5AE6058306` = ACM0, leader serial `5AE6085272` = ACM1. 8000 시작 전후 root `fuser` 출력에는 두 포트 점유자가 없다. `/robots/so-101`은 이 매핑과 정면 8·사선 4·손목 6을 유지한다.
- Mac 8030을 기존 읽기 전용 캡처 서버로 재개했다. 세 카메라 오류 null, 프레임 수신 age 약 24–32 ms이며 `robot_control=false`; 비활성 텔레옵 때문에 관절 방송은 null이다.
- 처음 화면에는 약통 3개·바구니 3개가 있었다. 사용자가 한 개 배치로 정리했다고 보고한 뒤, 새 정면 영상에는 두 약통이 작업대 왼쪽 바깥에 있고 한 개가 ID3 앞쪽에 있으며 바구니 3개는 그대로 보였다. 이전 단일 물체의 고정 슬롯 위치·경로와 같다고 가정하지 않는다. 현재 LeLab 텔레옵은 inactive이며 정면·사선·손목 카메라 오류 null, 프레임 신선하다.

## 수동 관찰 결과

사용자는 현재 대상 한 개→가운데 빨강 ID4 바구니 목표, 양옆 바구니 경로 여유, 사람의 팔 이동 범위 이탈, 리더/팔로워 시작 자세와 즉시 중단 준비를 확인하고 기존 텔레옵을 직접 켰다. 에이전트는 로봇 제어 없이 `observe_teleop_trace.py --camera-evidence`로 8030 캐시 정면·사선 영상과 관절 방송을 관찰했다. 사용자가 직접 종료했고 LeLab 텔레옵·녹화·추론 active=false를 확인했다. recording 내부 `current_phase=preparing`, `session_ended=false`는 유지되므로 세션 정리 완료로 해석하지 않는다.

- 로컬 원본 폴더 `.local/teleop-traces/20261007T050941_395283Z_d2c1f385/`는 Git-ignore다. 관절 1,685개·수신 span 87.103초·최대 수신 간격 150.523 ms, 중복/역순 source 시각 0건. 관절 SHA-256 `175581a5...a9a4209`는 감사 결과와 일치한다.
- 정면 367장·사선 364장, 각 index·JPEG 무결성 검사 통과, 종료 시 두 카메라 수신 오류 null. 이는 Mac 수신시각 캐시 JPEG이며 노출시각 동기 연속 비디오가 아니다. `camera_evidence_complete=false`다.
- 종료 후 정면 화면에는 약통이 오른쪽 바구니에 보이고 가운데 ID4 바구니는 비어 보인다. 현장 실제 바구니 ID와 간섭·걸림 여부를 사용자에게 확인 요청했다. 이 관찰로는 ID4 목표 성공을 주장하지 않는다.
- 설치 URDF SHA `443d38d7...f67236` 기준 감사기는 `URDF_LIMIT_MISMATCH`(exit 2)를 반환했다. Elbow 1,465/1,685개가 상한보다 높고 최대 초과량 0.116224 rad다. 다른 다섯 관절 초과 0건. 이는 물리 하드스톱 위반을 증명하지 않지만, 자동 관절 재생·ArUco 자율 투입은 `BLOCKED`다. 원본의 `use_for_replay=false`, `robot_enabled=false`, `motion_authorized=false` 유지.
