# 사용자 텔레옵 관절·영상 관찰 — 재생 불가

기존 정지 캡처에는 이동 사이의 관절 경로가 없다. `scripts/observe_teleop_trace.py`는 별도 승인된 사용자 수동 텔레옵이 이미 활성일 때 LeLab `/ws/joint-data`를 읽기만 하여 기록한다. 텔레옵 시작·종료, 모터·토크·USB·카메라 설정, 자동 재생 기능은 없다. 텔레옵이 꺼져 있으면 폴더도 만들지 않는다. 과거 관절 단독·부분 영상 기록은 경로 안전을 통과하지 못했다.

```sh
python3 scripts/observe_teleop_trace.py --lelab-url http://192.168.50.20:8000 --output-root .local/teleop-traces --max-seconds 180 --camera-evidence
```

새 현장 안전 확인과 해당 수동 시험의 명시 승인을 받은 뒤에만 실행한다. `--camera-evidence`는 Mac 8030이 먼저 실행 중이고 정면·사선 프레임이 신선하며 `robot_control=false`일 때만 시작한다. 기존 8030의 캐시 JPEG를 약 5 Hz로 복사하므로 LeLab 카메라 스트림을 추가로 열지 않는다. JPEG 헤더의 원래 Mac 수신시각을 보존하고 같은 프레임은 중복 저장하지 않는다. 사선 등 채널이 끊기면 그 부분 자료를 남기되 안전 경로로 승인하지 않는다.

최대 180초 또는 텔레옵 종료 중 먼저 발생한 때 멈춘다. 상태·연결 오류도 기록하고 중단한다. `joints.jsonl`, 정면·사선 JPEG, 해시 index 및 `manifest.json`은 Git-ignore `.local/`에만 보관한다. 영상 시각은 Mac 최초 수신시각이며 실제 모터 명령이나 카메라 노출 시각이 아니다. 약 5 Hz 표본은 연속 영상이 아니므로 manifest의 `camera_video_recorded`와 `camera_evidence_complete`는 false다. 이 자료는 충돌 여유의 증명이 아니며 자동 재생을 승인할 수 없다.

관절 기록의 원본 해시·설치 URDF 범위를 오프라인 검사하려면 다음 명령을 사용한다. 기본 한계 파일은 2026-10-05 Jetson 설치 URDF SHA `443d38d7...f67236`에서 읽은 값이다. 이 검사에서 범위 초과가 없더라도 자동 재생을 허가하지 않는다.

```sh
python3 scripts/audit_teleop_trace.py --trace-dir .local/teleop-traces/기록_폴더
```
