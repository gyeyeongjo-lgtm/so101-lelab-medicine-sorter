# 사용자 텔레옵 연속 관절 관찰 — 현장 미사용

기존 네 정지 캡처에는 이동 사이의 관절 경로가 없다. `scripts/observe_teleop_trace.py`는 다음 승인된 사용자 수동 텔레옵이 이미 활성일 때 LeLab `/ws/joint-data`를 읽기만 하여 기록한다. 텔레옵 시작·종료, 모터·토크·USB·카메라 설정, 자동 재생 기능은 없다. 텔레옵이 꺼져 있으면 폴더도 만들지 않는다.

```sh
python3 scripts/observe_teleop_trace.py --lelab-url http://192.168.50.20:8000 --output-root .local/teleop-traces --max-seconds 180
```

새 현장 안전 확인과 해당 수동 시험의 명시 승인을 받은 뒤에만 실행한다. 최대 180초 또는 텔레옵 종료 중 먼저 발생한 때 멈춘다. 상태·연결 오류도 기록하고 중단한다. `joints.jsonl`과 SHA-256을 담은 `manifest.json`은 Git-ignore `.local/`에만 보관한다. Mac 수신 시각이며 실제 모터 명령이나 카메라 노출 시각이 아니다. 영상·물체 위치·충돌 여유가 없어 이 자료만으로 경로 안전 또는 자동 재생을 승인할 수 없다.
