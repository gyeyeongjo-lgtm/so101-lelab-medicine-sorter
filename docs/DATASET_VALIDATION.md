# 데이터셋 검증

현재 상태: `FAIL` — 무카메라 진단 녹화를 실행했지만 첫 follower observation에서
TX/RX 오류가 발생해 저장 episode는 0개다. 유효한 데이터셋 검증은 아직 시작할 수 없다.

향후 짧은 로컬 녹화가 완료되면 다음을 각각 증거와 함께 판정한다.

| 항목 | 현재 |
|---|---|
| 저장 요청 성공 응답 | 비동기 worker 시작 200, 이후 session FAIL |
| episode 수와 연속성 | FAIL — saved episode 0 |
| frame 수·timestamp 단조성 | NOT_RUN |
| leader action / follower observation shape | NOT_RUN |
| 카메라 2개 frame 존재·해상도·FPS | NOT_RUN |
| task·repo_id·장치 메타데이터 | NOT_RUN |
| LeRobot API로 재로딩 | NOT_RUN |
| 서비스 재시작 뒤 재접근 | PASS — 실패 patch 롤백 후 health 정상 |

데이터 파일은 Git에 커밋하지 않는다. 검토·비식별화한 요약만 `reports/sanitized/`에 둘 수 있다. 데이터 재로딩은 로봇 동작 재현을 뜻하지 않는다.

## 2026-10-28 VLA 사전 확인 — 과거 zero-episode 사고의 증거 구분

위 FAIL은 과거 진단 녹화 건의 결과이며 모든 후속 ACT 데이터셋이0개라는 뜻이 아니다.
이번 검토는 저장소 문서·코드만 읽었다. 원본 Jetson journal 재조회와 새 녹화는 `NOT_RUN`이다.

확인 가능한 저장소 증거:

- [기록된 incident](RECORDING_INCIDENT_2026-09-05.md): POST200 이후 비동기 worker가
  첫 follower `get_observation()` / `sync_read(Present_Position)`에서 실패하고 저장0개.
- 무카메라 A/B도 같은 지점에서 실패했다. 카메라·encoder·Hub 업로드를 이 최초 오류의
  직접 원인이라고 할 근거가 없다. 첫 action write보다 observation 실패가 먼저다.
- RX clear+50ms 패치는 실제 무카메라 회귀에서 실패해 롤백됐다. 해결책으로 재적용하지 않는다.
- standalone/dual read 및 cold dual-configure는 통과한 기록이 있어 상시 모터 고장이나
  두USB를 여는 행위 자체가 원인이라고 확정할 수 없다.
- [기존 debug 분석](RECORDING_DEBUG.md)은 calibration worker/status handler 동시 읽기와
  녹화 worker 실패를 구분한다. calibration 수정 성공을 녹화 복구 성공으로 확대하지 않는다.
- `patches/lelab-20260906/record-worker-instrumented.py`에는 worker 예외를 error/session
  종료로 전달하는 처리와 robot observation을 전달받는 loop가 있다. 보존된 코드일 뿐
  현재 Jetson 설치본과 일치하는지는 확인하지 못했다.

| 가설 | 근거와 한계 | 지금 판정 |
|---|---|---|
| serial bus 경쟁/별도 소유자 | calibration에는 교차 read 근거가 있음. 녹화는 자체 worker 실패이고 동시 소유자 당시 증거 부족 | 녹화 원인으로 미확정 |
| 서비스/worker 실행 문맥 | standalone은 통과, 실제 worker는 실패한 차이. 당시 설치본/현재 서비스 차이도 미확인 | 미확정 |
| 전원·케이블·간헐 packet 손실 | torque enable과 observation 모두 실패한 기록. kernel USB reset이 없어도 motor-side 문제는 배제 불가 | 미확정 |
| RX buffer clear만 필요 | 실제 회귀 실패 기록 | 단독 해결책으로 반증 |
| 카메라가 인식되지 않음 | 카메라 없는 재현에서도 실패 | 해당 zero-episode 오류 설명 안 됨 |

현장에서 향후 조사할 때에도 source/version·단일 bus owner를 먼저 확인하고, 모터를 여는
진단은 별도 승인 후 한 변수씩 시험한다. 이번 VLA1단계에는 serial import/open/write0,
서비스 조작0이며 실패 원인을 새로 확정하지 않았다.
