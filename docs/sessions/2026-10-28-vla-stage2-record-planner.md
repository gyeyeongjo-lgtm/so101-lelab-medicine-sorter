# VLA 2단계 구현 기록

2026-10-28 Asia/Seoul. 사용자2단계 승인, 실제 녹화/학습/추론/로봇/서비스 변경은 제외.
시작 branch vla/main, HEAD `1c420cfde68f878514d5f571b5fdaf106dbefd84`, 작업트리clean 확인.

## 변경

- configs/vla_tasks.yaml: 9조합, 각한국어2영어1, 기본한국어cycle, 10→20~30목표.
- scripts/vla_record.py: 추천/수동선택/문장/안내 dry-run, read-onlyv3자료검증,
  별도 counter의 lock/revision/atomic save, 미검증execute 차단.
- tests/test_vla_record.py: mock 파일·provider·실패/중단/원자저장·dry-run무부작용 검사.
- docs/VLA_STAGE2.md 및 STATUS·세션 기록.

## 조사로 확인한 실행 차단 조건

- 공식0.6.0 record --help에서12개 사용옵션 확인(exit0). 설치본0.6.1 변경 없음.
- 공식 CLI 최초생성 repo_id 시각추가 및 resume append를 소스로 확인. 실제 저장 NOT_RUN.
  timestamp는조합별분리가아님. 최초actual_repo_id를저장하고같은root/id로resume하도록구현.
  metadata의DatasetInfo에는id필드가없으므로기존자료에서임의복원하지않고internal provider미연결이면거부.
- raw follower 기본 disconnect 토크off, max_relative_target=None.
  기존 controller 안전계약이 보장되지 않아 모든green mock에서도 실제launch 불가.
- 기존 source/safety/web/카메라설정/데이터/보정/모델은 수정하지 않음.

## 테스트

- `python3 -B -m unittest discover -s tests -p 'test_vla_record.py' -v`:42 PASS, exit0.
- `python3 -B -m unittest discover -s tests -p 'test_vla_*.py'`:69 PASS(stage1 27+stage2 42), exit0.
- 같은명령 pattern을 `test_fixed_demo.py`(64), `test_demo_web.py`(7),
  `test_sorter_*.py`(31), `test_camera_preview_joint_ws.py`(3)로 실행:모두exit0.
  최종합계174 PASS, 실패0, skip0. 장치실행은시험범위에서제외(NOT_RUN).
- 처음통합실행에서resume계획테스트의mock이자기자신을다시호출하는fixture오류1건(exit1)이있었음.
  원본snapshot함수참조를분리해수정한뒤전체회귀재실행PASS. 운영로봇에서발생한오류가아님.
- `--dry-run`:exit0, 계획만출력. `--execute --first-motion-approved`:exit2, 정상차단.
- 성공저장검증은 temp mock 자료로만 수행. 원본 dataset 변경0.
- 메모리내Python compile, `git diff --check`, 기존제어/웹/카메라설정동일성검사:PASS/exit0.

## 미완료/이슈

Jetson접속·장치신원·실제온도·exclusive ownership·A:red물리검증은 NOT_RUN.
실제record adapter/고정repo identity 연결은 BLOCKED. 학습·추론·재촬영 NOT_RUN.
mock구현 성공을 실물촬영 성공으로 보고하지 않는다.
2단계에서 종료하며3단계 요청은 “3단계 진행”. 실구동은 별도 승인 필요.

## 커밋/복구

구현 commit: `51fba8a79dc6057b11b9333b93f2faaa22f8ddf0` (vla/main).
원본fix/usb-recording은 변경하지 않았다. 일반push요청은원격업로드의직접사용자승인이
확인되지않아승인검사에서보류됐고실제push프로세스는실행되지않았다: **NOT_PUSHED**.
다른계정/도구를사용한우회업로드는하지않는다. 사용자직접승인뒤에만다시시도한다.
복구백업: `.local/backups/vla-stage2-20261028.bundle`.
기준 `5f03c571e223f86f422b6eb68af94a6ff05c78db` 이후stage1+stage2와기록commit만포함한다.
원본repo히스토리전체/모델/데이터/인증정보는새로묶지않는다. 복구에는기준commit이있는clone이필요하다.
bundle의branch를별도branch로fetch해복구할수있으며원본branch를강제로덮어쓰지않는다.
2단계원복은문서후속commit부터역순revert한뒤구현commit을revert한다. 데이터/서비스복구는필요없다.
