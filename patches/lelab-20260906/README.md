# RX-clear record patch — 실패 기록

`record-rx-clear.failed.patch`는 LeLab의 원본 `record.py`에 follower·leader configure
직후 serial RX buffer clear와 50 ms settle만 추가한 실험 diff다.

- 로컬 `py_compile`: PASS
- Jetson 배포 및 service restart: 실행됨
- 무카메라 녹화 회귀: FAIL
- 실패: 첫 follower `Present_Position` sync-read, `There is no status packet`
- 저장 episode: 0
- 현재 Jetson 설치 상태: 이 실험본을 제거하고 pre-A/B 원본으로 롤백함

이 diff를 해결 패치로 재배포하지 않는다. 실패 증거는 Git 비추적 백업
`backups/jetson/20260906T114147+0900_rxclear-regression/`에 보존했다.
