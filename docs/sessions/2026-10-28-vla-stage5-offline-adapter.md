# VLA 5단계 무장치 구현

시작596ee5fabb53fb0f818769fc84170f54835d6123, clean vla/main. Jetson 접속시도 없이 진행.
기존 RobotController의 stage-only API와 상태 read의 raw 단위를 확인해 live 연결 불가를 먼저 보고했다.
robot.py/fixed_demo.py/보정/원본자료/기존checkpoint 수정0.

## 구현

- medicine_sorter/vla_policy_adapter.py: pure mock streaming 계약·관측/동작/시작/온도/stop 검사·timeout 후 늦은 출력 폐기.
- scripts/vla_run.py: default plan/BLOCKED, mock 또는 shadow-sim 합성로그만. 실shadow/live providers 미연결.
- scripts/benchmark_smolvla_jetson.py: default plan null, synthetic label, 미래 local-only measure lazy 연결. 실측NOT_RUN.
- scripts/jetson_preflight.sh/.py: 기본 LOCAL DRY RUN, 현장 --probe는 파일/metadata/symlink만 조회. device/GPUdriver open 없음.
- configs/vla_inference_source_evidence.json: cached 공식0.6 source API/rename/chunk/processor 근거·SHA.
- docs/VLA_STAGE5.md, docs/RETURN_CHECKLIST.md.

## 검증

- 기준 guarded full discovery:731 testsRun/failure6/error23/skip15, 이전과 failure/error/skip 항목·사유 동일.
- 처음 신규57개 PASS, 이후 policy-path/CLI 유효성2개 추가.
- 최종 VLA203 PASS/skip0 (기존144+신규59), exit0.
- 전체790 testsRun/failure6/error23/skip15, exit1. 기준과 항목·사유 완전동일.
- 명령: VLA_OFFICIAL_SOURCE=<cached-source> python -B tests/run_vla_nohardware.py 'test_vla_*.py'
  및 같은 환경에서 pattern 생략. failure 이름 콘솔출력은 .local summary로 리다이렉트하고 counts만 표시했다.
- bash -n scripts/jetson_preflight.sh PASS; LOCAL DRY RUN PASS, .local/jetson_preflight_dry_20261028.json.
- 모델wrapper float변환 보완은 소스검사/compile만이며 실제 모델출력 검증이 아니다.
- 로그: .local/stage5-baseline.json, stage5-vla-final.json, stage5-full-final.json.
  공개 가능한 요약: reports/vla-stage5-preflight-20261028/baseline_and_skip_classification.json, final_counts.json.
- 제외15개 재분류: websocket-client1, private recorded candidate10, loopback 권한4.
  이전 'dependency15'는 부정확했으며 이번에 정정. 상세 이름·안전 관련 정적분류는 파일에만 기록.

## 한계와 복구

실제 streaming RobotController API·unit변환·audit시작분포·fresh 장치/소유권 proof 미검증으로 live BLOCKED.
mock HOLD와 disconnect(disable_torque=False) 호출은 실모터토크유지 검증이 아니다.
timeout thread는 강제종료할 수 없으며 controller참조0/추가write0/결과폐기만 보장한다.
benchmark속도는 task성능이 아니고 power/clocks 자동수집은 미구현. first-run Enter는 현장 단계로 NOT_RUN.
Jetson/serial/camera/GPU/정책/학습/가중치다운로드/서비스변경/push0. 7단계미시작.
5단계 commit을 별도로 남기며 rollback은 그 commit revert. 기존bundle보존, 6단계 뒤 새bundle에 함께 보존한다.
