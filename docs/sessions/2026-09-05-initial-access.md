# 2026-09-05 초기 접근 기록

- 날짜/시간 및 시간대: 2026-09-05T20:52:40+09:00
- 실행 위치: Mac
- 관련 이슈: GitHub #1–#4
- 상태: `PASS` (Phase A 조사·백업·private 저장소·안전 승인 시험), `FAIL` (무카메라 녹화 회귀), `RESTORED` (실패 patch 원본 롤백)

## 실행 및 관측

1. 복구 지시서 787줄과 Mac 시작 안내 170줄을 전체 확인했다.
2. Mac 운영체제, Git 작업 트리, SSH 계산 설정, GitHub CLI 설치 여부를 읽기 전용으로 조사했다.
3. Jetson의 SSH 22번과 LeLab 8000번 TCP 응답을 확인했다.
4. SSH 접속은 기존 호스트 키가 없어 검증 단계에서 중단했다. 호스트 키 검증을 끄거나 `known_hosts`를 변경하지 않았다.
5. GitHub CLI가 없어 인증 상태 확인과 비공개 저장소 생성은 실행하지 않았다.
6. 사용자가 Jetson ED25519 지문을 확인했다. 프로젝트 전용 known-hosts 파일에 해당 공개키를 고정하고 지문 일치를 재검증했다.
7. 공식 GitHub CLI v2.100.0 arm64 바이너리를 프로젝트 내부에 설치했고 공식 체크섬 검증을 통과했다.
8. `gh auth status` 결과 로그인된 GitHub 호스트가 없었다.
9. SSH 공개키 인증은 실패했다. 대화형 SSH 터미널을 열고 사용자의 직접 비밀번호 입력을 기다린다.
10. 실제 계정 `jetson3`으로 SSH 인증을 완료하고 프로젝트 전용 제어 소켓을 만들었다.
11. Jetson 환경, LeLab/LeRobot 버전·커밋, 실행 프로세스, USB/카메라 상태, 저장 설정을 조사했다.
12. Jetson과 Mac에 Phase A 백업을 만들고 전체 SHA-256 manifest를 양쪽에서 검증했다.
13. 메타데이터 전용 `inspect_ports.py`를 실행해 현재 하나의 serial과 세 alias, 사라진 팔로워 경로를 확인했다.
14. LeLab journal과 설치 소스·선행 patch를 비교해 캘리브레이션 TX/RX 경쟁 및 패치 후 비재발을 확인했다.
15. 실제 데이터셋 `/start-recording` 호출은 journal에 없어 녹화 오류는 별도 `NOT_RUN`으로 유지했다.
16. `inspect_ports.py`와 `preflight.py`의 하드웨어 없는 단위 테스트 3개가 통과했다.
17. Jetson preflight가 팔로워와 두 카메라 누락을 검출해 `ready=false`로 안전하게 차단했다.
18. GitHub CLI 인증을 macOS Keychain에서 확인하고 비공개 저장소를 생성했다.
19. 선별한 12개 파일만 초기 커밋 `8dd6761`로 만들고 `main`에 push했다. `prompt/`, `.local/`, `backups/`는 제외했다.
20. 포트 식별, 녹화 TX/RX, 회귀·데이터 검증, 후속 로드맵 이슈 #1–#4를 생성했다.
21. 작업 브랜치 `fix/usb-recording`의 증거 문서 커밋 `48d788b`을 push하고 GitHub API에서 동일 SHA를 확인했다.
22. 현장 안전 확인과 물리 연결 완료 뒤 metadata-only preflight 7/7 `PASS`를 확인했다.
23. 21:53:19와 21:53:52의 실제 녹화 시도 traceback을 수집했다. 첫 시도는 follower id 5 torque enable, 두 번째는 follower Present_Position sync-read에서 실패했고 두 번 모두 저장 episode는 0개였다.
24. 텔레옵 중에도 follower joint-position read 오류가 반복된 사실과 camera/USB/kernel/HF 원인 분리 결과를 `RECORDING_INCIDENT_2026-09-05.md`에 기록했다.
25. follower 포트를 쓰기·토크 변경 없이 개별 `Present_Position` read와 group `sync_read`로 비교할 수 있는 `scripts/diagnose_follower_bus.py`를 추가했고, Mac 문법 검사 및 기존 단위 테스트 3개를 통과시켰다.
26. 2026-09-06 11:08 KST Jetson에서 follower serial identity를 확인한 뒤 읽기 전용 시험을 실행했다. ping 6/6, 개별 position 30/30, group sync-read 5/5가 모두 성공했으며 ID 5도 정상 응답했다.
27. 추가 20-round 시험도 개별 120/120, group 20/20 성공했다. 11:10 텔레옵 journal에서는 약 62초 동안 follower read 오류 255건과 정상 joint snapshot 48건이 혼재했고, 설치 소스의 1 ms write loop를 확인했다.
28. 카메라 없는 최소 녹화 A/B 전에 현재 설정·소스·journal을 `20260906T111830+0900_pre-ab`로 Jetson/Mac 양쪽에 보존하고 9개 파일 SHA-256을 검증했다.
29. 카메라·video·streaming encoding을 제외한 녹화도 첫 follower observation에서 즉시 같은 오류로 실패했다. 실패 직후 standalone read는 다시 전부 성공했고, 설정 hash도 변하지 않았다.
30. 현재/목표 위치 차이와 상태 register를 read-only로 확인한 뒤 torque-only 약 3초 시험을 수행했다. torque enable/disable과 position+voltage 40/40이 통과했고 12.2V가 유지됐다.
31. configure+RX-clear 시험은 calibration/register write와 torque toggle을 포함해 별도의 구체적 안전 승인이 필요하므로 실행 전 중단했다.
32. 사용자가 구체적 시험 승인과 현장 안전을 재확인했다. configure 뒤 RX clear+50ms를 적용한 40회 position+voltage read가 전부 통과했고 torque도 정상 해제됐다.
33. 원본 `record.py` 대비 configure 후 follower·leader RX clear와 50ms settle만 추가한 patch를 로컬에 준비하고 문법 검사했다. 설치·restart·회귀는 별도 승인 대기 상태다.
34. 사용자가 배포·service restart·무카메라 회귀를 승인했다. patch log까지 정상 실행됐지만 첫 follower observation이 `There is no status packet`으로 실패했고 episode는 0개였다.
35. 실패 증거를 Jetson/Mac에 보존한 뒤 live `record.py`를 pre-A/B 원본으로 롤백했다. live와 원본 SHA-256 `779fd897...`가 일치하고 service health와 inactive 상태를 확인했다.
36. leader standalone 읽기 전용 시험은 ping 6/6, 개별 read 120/120, group 20/20을 통과했다.
37. 두 serial 포트를 동시에 열어 30 Hz로 120 rounds 교차 group read한 시험도 leader/follower 각각 120/120 성공했다. 결과를 `20260906T114842+0900_dual-readonly`에 양쪽 보존했다.
38. 사용자가 dual-configure 계측과 현장 안전을 승인했다. 시험 전 설정·설치 소스·journal 10개를 `20260906T120356+0900_pre-dual-configure`로 양쪽 보존하고 hash를 검증했다.
39. 첫 계측 실행은 포트를 열기 전 존재하지 않는 내부 torque 메서드명 때문에 중단됐다. 하드웨어 호출은 없었고 service를 정상 복구한 뒤 설치 API에 맞게 도구를 수정했다.
40. follower configure 경계 trial과 전체 follower→leader configure trial을 실행했다. 각 최초 follower position group-read가 3/3 `comm=0`, register/torque call error 0건, Goal_Position write 0건이었다.
41. 두 trial 모두 leader/follower torque disable과 disconnect가 성공했다. 결과는 `20260906T121152+0900_dual-configure-result`에 양쪽 보존했다.
42. configure 전 group-read와 호출별 계측 지연을 제거한 cold full-order trial을 1회 추가했다. 최초 follower read 3/3과 leader read 1/1이 모두 `comm=0`이었다.
43. cold trial 뒤 양쪽 torque disable/disconnect와 LeLab service health를 확인했다. 설정 hash는 시험 전후 동일하고 kernel event는 없었다. 결과는 `20260906T121642+0900_dual-configure-cold`에 양쪽 보존했다.
44. 실제 녹화와 standalone cold sequence의 남은 구조적 차이를 background `recording-worker`, 선행 dataset 생성/runtime context, 간헐성으로 좁혔다.

## 보존 및 안전

- 기존 네트워크, 저장된 캘리브레이션, USB, 카메라 설정은 변경하지 않았다.
- 사용자 안전 승인 범위에서 기존 calibration/configure, torque toggle, service restart를 실행했다. 모터 목표값, baudrate, return-delay, USB 연결은 바꾸지 않았다.
- 실패한 RX-clear patch는 원본으로 롤백했다.
- 비밀번호, 토큰, 개인키, 환경 변수, 원본 로그를 수집하거나 기록하지 않았다.
- 원본 백업은 Jetson과 Mac 양쪽에 생성됐고 SHA-256 manifest 전체 검증을 통과했다. Mac 사본은 `backups/` 아래 Git 비추적으로 보존한다.

## 다음 실행 한 단계

현재 원본 서비스는 정상 복구됐고 dual-configure standalone 시험은 모두 통과했다. 반복적인 calibration EEPROM write를 멈추고 실제 `recording-worker`에 적용할 source-only 계측안을 먼저 준비한다. 실제 worker 회귀는 별도 승인 뒤 1회로 제한한다.
