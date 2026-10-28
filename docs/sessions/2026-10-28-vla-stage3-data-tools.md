# VLA 3단계 데이터 도구 작업 기록

2026-10-28. 시작 HEAD d5136c0c50e454ab26bc52bbe313b05b2c5155f2, branch vla/main.
원본 dataset/calibration/log/checkpoint는 읽기 전용. 별도 설치·서비스·USB·모터 작업 없음.

## 변경과 검증

- scripts/vla_record.py에 내부 counter commit 전 sidecar hook과 CLI session 옵션만 추가.
  실제 execute의 unconditional BLOCKED는 유지한다.
- 결합 API는 `vla_sessions.commit_with_session`이며 stage2 `commit_saved_episode`를 호출한다.
  SessionsTests의 test_second_append_same_session, test_sidecar_failure_counter_unchanged,
  test_counter_failure_after_sidecar_fail_closed_retry에서 결합경로를 시험한다.
  마지막 시험은 counter 실패 뒤 sidecar를 확정 세션으로 읽는 것도 거부함을 확인한다.
  CLI 옵션만으로 실녹화 연동 완료라고 보고하지 않는다.
- vla_sessions/data/audit_dataset/review_episode/build_derived/split_sessions/official_worker 추가.
- tests/vla_fixture.py 실제 synthetic shared MP4/Parquet, test_vla_stage3.py35 tests,
  run_vla_nohardware.py에 장치/network/미검토 subprocess 금지 및 상세결과 저장.
- source v0.6.0 commit30da8e687a6dfc617fcd94afc367ac7071c376ce,
  설치Python3.12.13/LeRobot0.6.1 그대로. 공식 edit_dataset --help exit0(307줄).
- VLA 전용104 tests PASS, 실패/오류/skip0. synthetic 공식reload+derivedreload와
  source tree SHA/decoded sample checksum, 실제 세션/원본 인덱스 보존 검사 포함.
- 검수 contact_sheet와 trajectory PNG를 생성해 확인. 실제 A-v1 ep0도 별도 결과 폴더에 생성.

재현: 저장소 루트에서 `VLA_OFFICIAL_SOURCE=/path/to/lerobot-v0.6.0 python3 -B tests/run_vla_nohardware.py 'test_vla_*.py'`.
실제 확인한 Python은 `/home/chosun/miniconda3/envs/lerobot-3060/bin/python`이다.
VLA_OFFICIAL_SOURCE 미지정 시 공식 통합2개는 skip되므로 완료 검증과 동일하지 않다.

## 실패도 기록

- 최초 전체 guarded regression: 688개 실행, failures6/errors24/skips15.
  오류1개는 guard가 기존 순수 import subprocess 시험까지 막은 것으로, 해당 정확한
  import-only 명령만 허용하도록 runner를 보완했다. 로봇 제어 명령을 허용하지 않았다.
- 보완 후 중간 전체:688개 실행, failures6/errors23/skips15.
- 수정 전 HEAD를 git archive로 `/tmp/vla-stage3-baseline-vSHVAe`에 추출 후 동일 guard:
  656개 실행, failures6/errors23/skips15. 실패·오류·skip test ID 모두 동일.
- errors는 `.local/c-red-pivot-tcp-table-20261011-s01`의 URDF/JSON 현장 fixture 누락.
  failures는 위 fixture 의존5개와 ArUco reference center 기준 불일치1개.
  기존보정·제어코드와fixture를 변경해 통과시키지 않았다. 전체회귀 PASS 아님.
- 최종 전체691개 실행도 failure6/error23/skip15이고 baseline과 ID 모두 동일하다.
  결과는 `.local/stage3/full-regression-final.json` 및 `baseline-comparison-final.json`.
  이후 확정counter 검증을 보강한 세션 코드까지 VLA104개를 다시 실행해 모두 통과했고,
  최종 전용 결과는 `.local/stage3/vla-tests-committed-ledger.json`이다.
  setUpClass error는 testsRun과 계수가 달라 단순 PASS 뺄셈 금지.

## 기존 ACT 읽기 전용 검사

A/B/C-v1,A-v2,trim05,48회 루트 총6개, 루트별 합348episode. 독립시연348개로 세지 않는다.
metadata/모든 state-action row/영상 컨테이너/공식샘플로더 검사, 원본 압축6개 manifest SHA 일치.
전부 FAIL0이나 단위·세션·legacy task/camera·성공확인 때문에 WARN이다.
전체 영상 디코드 NOT_RUN; 과거54 sample 검사와 이번 샘플 검사를 별도로 명시했다.
실제 ACT 선별본은 dry-run만, split은unknown348/train0/eval0. 기존자료 삭제·복사·재압축 없음.
상세 report는 `.local/stage3/act-audits/`이며 raw dataset/log/PII는 커밋하지 않는다.

## 종료/복구/다음

단계3 로컬 commit만 생성하고 push하지 않는다: NOT_PUSHED. 외부백업은 완료했다고 주장하지 않는다.
구현 commit은 `4bb48da1c6678a83335c01264c7a659ff810c82e`다.
그 후 `git bundle create .local/backups/vla-stage3-20261028.bundle vla/main`을 시도했으나 exit1.
read-only 조사에서 remote.origin.promisor=true, partialclonefilter=blob:none,
`git rev-list --objects --missing=print`의 미보유 과거객체569개가 확인됐다. 전체bundle 파일은 생성되지 않았다.
추가 다운로드/원격 push로 우회하지 않는다. 이 한계를 기록한 문서commit 후
`.local/backups/vla-stage3-20261028-incremental.bundle`을 새로 만든다.
범위는 `5f03c571e223f86f422b6eb68af94a6ff05c78db..vla/main`으로1~3단계와 문서이력을 포함한다.
**복구에는 기준5f03c571e223f86f422b6eb68af94a6ff05c78db가 있는clone이 필요하다.**
verify/SHA256 및 self_contained=false를 receipt에 기록한다.
기존stage2 bundle은 덮어쓰지 않는다. commit SHA와 bundle SHA는 로컬 receipt와 최종 보고에 남긴다.
롤백은3단계 commit revert; 원본 데이터나 서비스는 이번에 변경하지 않았다.
실제record/학습/정책모델load·추론/로봇명령0. 단계4는 시작하지 않았다.
