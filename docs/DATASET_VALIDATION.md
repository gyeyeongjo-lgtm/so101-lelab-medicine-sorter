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
