# 2026-10-29 VLA 6단계 평가 도구

시작 HEAD `27f9c797ff8071f61bb6e81439cb4722d61c4d95`, clean `vla/main`.
5단계 이후 오프라인 6단계를 마무리한다. 7단계 웹·원격 push·장비 접속 금지 범위를 유지했다.

## 변경

- `data/vla_eval.csv`: 헤더 1행/실제 기록0.
- `scripts/vla_eval_report.py`: 스키마 검사, append-only 이력/원자 교체, checkpoint별 최신 trial 집계, N/A 보고서.
- `tests/test_vla_stage6.py`: synthetic 57 tests. 임시 CSV만 사용하고 실제 평가 원장에 합성 결과를 넣지 않는다.
- 6단계 문서·복귀 안내·상태·검증 요약. 기존 모델/데이터/로그/보정 및 제어 코드 변경0.

## 실행 명령과 결과

Python은 `/home/chosun/miniconda3/envs/lerobot-3060/bin/python` 3.12.13,
공식 캐시 source는 `/tmp/mediflow-lerobot060-help-H2dsrt/source`(LeRobot0.6.0)이다.
설치 distribution0.6.1과 소스0.6.0의 구분은 유지했다. 패키지 설치나 모델 로딩 없음.

각 unittest 명령 앞 환경:
`VLA_OFFICIAL_SOURCE=/tmp/mediflow-lerobot060-help-H2dsrt/source VLA_TEST_REPORT=<아래JSON>`.
각 명령 stdout/stderr는 해당 `.local/*-summary.log`로 보내고 콘솔에는 첫 줄 counts만 표시했다.

| 범위 | 명령(Python 경로는 위 경로 사용) | 결과 | exit | 원본 JSON |
|---|---|---|---|---|
| 6단계 신규 | `python -B tests/run_vla_nohardware.py 'test_vla_stage6.py'` | 57 / 실패0 / 오류0 / 제외0 | 0 | `.local/stage6-new-first.json` |
| 전체 VLA | `python -B tests/run_vla_nohardware.py 'test_vla_*.py'` | 260 / 실패0 / 오류0 / 제외0 | 0 | `.local/stage6-vla-final.json` |
| 전체 회귀 | `python -B tests/run_vla_nohardware.py` | 847 / 실패6 / 오류23 / 제외15 | 1 | `.local/stage6-full-final.json` |

기준 `.local/stage5-full-final.json`: 전체790/6/23/15.
각 실패·오류의 전체 trace와 제외 사유를 ID별로 대조했으며 모두 동일했다.
새 회귀 실패는 없다. 전체 PASS 또는 실행수에서 단순 차감한 PASS 수를 주장하지 않는다(setUpClass 오류 포함).
세부 ID/사유는 reports/원본 JSON에만 두고 콘솔로 출력하지 않았다.

VLA 구분: 5단계 이전144, 5단계 초기 신규57 → CLI2 보완 후 **최종 신규59**, 5단계 전체203.
6단계 신규57을 추가한 최종 VLA260이다. 초기 신규57과 6단계57은 서로 다른 시험 집합이다.

추가 검사:

- `python -B scripts/vla_eval_report.py --csv data/vla_eval.csv validate`: exit0, 실제 이력0.
- `python -B scripts/vla_eval_report.py --csv data/vla_eval.csv report --out .local/vla_eval_empty_20261029`:
  exit0, 9×5 N/A, 원본 유지. 실제 성공률 기록 없음.
- template SHA256 `7ce167126eb9f5a73b6b09d6c2a19b0d7da90a477732c5c06a0a5bb4431178c4`.
- 원자 교체 실패/fsync 전후 실패·동시 writer 경쟁·stale SHA·symlink·중복수정/행보존을 synthetic으로 검사.
- `git diff --check` exit0. 보호 경로와 5단계 commit 비교 일치.
- 최종 HEAD 재검증 결과·bundle SHA는 commit 이후 `.local/backups/` receipt에 기록한다.

## 제외15와 안전 계층 해석

제외 목록의 본문을 읽어 범위를 확인했다. 단순 이름 substring 분류는 온도/Overload/HOLD 전체
커버리지나 동작 안전성을 증명하지 않는다.

1. dependency1: 텔레옵 종료 시 read-only 추적 중단 및 replay 허가 금지 검사.
2. private fixture10: 단계 경계·원명령 보존·모의 bus 수치, 미준비 명령/URDF 차단,
   첫 오류 이후 다음 단계 금지, replay scope/확인문구, 파지 정지/사람 판정, abort 후 토크 변경 금지 등이 포함된다.
3. loopback4: 원 수신 timestamp, 비활성 텔레옵의 HTTP capture 거부, legacy touch 기본 차단,
   waypoint의 텔레옵·두 확인 조건 검사. 실제 motor HOLD 검사가 아니라 HTTP capture 권한/신선도 계층이다.

이 15개에 직접 온도/Overload 테스트는 없지만 기존 오류와 모의시험 한계가 있어
안전 전체 PASS는 아니다. 5단계 mock 온도/Overload/stop/HOLD 시험은 203 및260 집합에 포함되어 통과했다.
실모터·실온도·실토크유지 검증은 NOT_RUN이다.
상세 분류: `reports/vla-stage6-20261029/verification.json`.

## 미구현/NOT_RUN

실 streaming RobotController/HOLD 계약·physical provider·실제 단위/시작분포/소유권 증거 부재로
shadow/live BLOCKED. 5단계 UnitContract와 start_gate는 fixture 기반이며 실제 캘리브레이션 검증 완료가 아니다.
Jetson 접속, serial/camera/motor open, GPU probe, 모델 생성/실추론, 다운로드, 학습, push 모두0.
기존 로봇 코드나 보정·안전 제한을 바꾸지 않았다. NOT_PUSHED. 7단계 미시작.

## 복귀와 복구

첫 명령: `bash scripts/jetson_preflight.sh --dry-run`. 기대 LOCAL_DRY_RUN/장치open0;
실장비 확인으로 오해하지 않는다. 현장 승인과 실제 연결 검증이 별도로 필요하다.

6단계를 별도 commit한다. 되돌릴 경우 6단계 commit을 `git revert`하고, 필요하면 그 다음
5단계 `27f9c797ff8071f61bb6e81439cb4722d61c4d95`를 revert한다. 원장 실기록은 먼저 별도로 보존한다.
새 bundle은 기존 파일을 덮어쓰지 않는 `vla-stage5-6-20261029-incremental.bundle`.
base `5f03c571e223f86f422b6eb68af94a6ff05c78db`가 필요한 증분본이므로 독립 full backup이 아니다.
569개 누락 과거 객체 때문에 full-history fetch/bundle 재시도는 하지 않는다.
bundle create/verify/SHA와 최종 commit은 adjacent receipt에 저장하고 마지막 보고에서 전달한다.
