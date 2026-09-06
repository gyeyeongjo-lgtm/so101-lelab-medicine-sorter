# 수정 및 복원

## 이번 세션의 변경 범위

- 승인 범위에서 LeLab service를 재시작하고 기존 calibration/configure 및 torque toggle
  분리 시험을 수행했다. 저장된 calibration, robot record, systemd 설정은 변경하지 않았다.
- RX-clear 실험 patch를 한 차례 설치했지만 무카메라 회귀 실패 직후 원본으로 롤백했다.
- Mac에는 진단 문서·검사 스크립트·실패 patch diff·Git 기록을 추가했다.
- 현재 Jetson 설치본에 이미 존재하던 calibration 직렬화 및 SO bus 재시도 패치는 이번 세션보다 앞선 변경이다. 이를 새로 적용한 것으로 기록하지 않는다.

## 원본 보존

- Jetson: `/home/jetson3/so101-recovery-backups/20260905T210818+0900_phase-a`
- Mac: `/Users/jogyeyeong/Documents/ChatGPT/자율설계/backups/jetson/20260905T210818+0900_phase-a`
- 두 사본의 `MANIFEST.sha256`: 전체 `PASS`

백업에는 설치본, 원본 commit 소스, 기존 patch/diff, 설정·calibration, 서비스 정의와 journal이 들어 있다. Mac 사본은 Git에서 제외된다.

## 복원 원칙

현재 설치본을 일괄 재설치하거나 덮어쓰지 않는다. 실제 회귀에서 새 결함이 확인될 때만 대상 파일, 기준 commit, 현재 hash, 패치 후 hash를 먼저 기록하고 한 파일씩 변경한다. 복원도 백업 manifest와 대상 hash를 대조한 뒤 승인 범위에서 수행한다.

현재 live `record.py`는 pre-A/B 원본과 SHA-256 `779fd897...`로 일치하고 service health가
정상이다. 새 Jetson patch가 남아 있지 않으므로 추가 롤백은 없다. 기존 선행 patch의
제거는 정상 캘리브레이션을 깨뜨릴 수 있어 별도 검증 없이 수행하지 않는다.
