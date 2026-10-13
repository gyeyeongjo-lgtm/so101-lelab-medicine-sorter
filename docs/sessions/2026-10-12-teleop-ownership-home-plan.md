# 2026-10-12 teleop ownership 확인 및 HOME 기록 계획

## 범위

`SAFE_HIGH=RECORDED`를 기준선으로 유지했다. Jetson process/systemd/journal/API/serial symlink를 읽기 전용으로 검사했으며 서비스·프로세스·USB·Torque·Goal·모터 명령은 변경하지 않았다.

## TELEOP_OWNERSHIP

- canonical 8000은 user systemd unit `/home/jetson3/.config/systemd/user/lelab.service`다.
- unit은 2026-10-11 19:30:58 KST부터 active/running이고 restart count는 0이다. Main PID는 `548555`(`sg dialout`), 실제 Uvicorn/LeLab PID는 `548557`이다.
- canonical USB는 leader serial `5AE6085272 → /dev/ttyACM0`, follower serial `5AE6058306 → /dev/ttyACM1`이다. 8000의 저장 robot record도 leader ACM0/follower ACM1과 일치한다.
- systemd user-manager 환경은 `LELAB_TELEOP_MODE=relative_start`다. 현재 설치 코드의 기본값은 `absolute`지만, 20:16:22 실제 성공 세션 로그에 `relative_start origins captured from fresh calibrated values`가 남아 있으므로 해당 실행은 relative-start였음이 확인된다.
- canonical 세션 시작 요청은 Mac `192.168.50.131`에서 8000 `POST /move-arm`으로 들어왔다. 서버 access log에는 호스트/endpoint만 있어 Mac 내부의 정확한 호출 프로세스와 사람 신원은 `NOT_RECORDED`다.
- 20:16:12와 20:16:13 두 요청은 임시 8003 세션이 follower를 점유한 동안 follower open에 실패했고 즉시 cleanup됐다. 8003 해제 후 20:16:22 세 번째 요청만 양쪽 장치 연결에 성공했다. 따라서 두 세션이 동시에 leader/follower를 실제 소유한 증거는 없다.
- canonical 세션은 20:19:04 `POST /stop-teleoperation` 뒤 follower와 leader를 모두 disconnect하고 `Teleoperation stopped`를 기록했다.
- 20:30:16 KST 현재 8000/8002 `teleoperation_active=false`, 8000 recording/inference도 false, 8003/8022 listener는 없다. 8002 Uvicorn PID 3467은 서버로 남아 있으나 teleop inactive다.
- 현재 non-privileged `lsof`에는 ACM0/ACM1 owner가 보이지 않는다. 단, root process의 fd를 현재 권한으로 완전 열람할 수 없으므로 이 시점의 privileged `fuser` 재검사는 `NOT_RUN`; 대신 정상 disconnect journal과 inactive API가 현재 무소유의 직접 근거다.

판정:

```ini
CANONICAL_TELEOP_SERVER = 8000 / PID 548557 / systemd user lelab.service
LAST_SUCCESSFUL_MODE = relative_start
CURRENT_ACTIVE_TELEOP = NONE
TEMP_8003 = NOT_RUNNING
SERIAL_OVERLAP_DURING_SUCCESSFUL_SESSION = NOT_OBSERVED
EXACT_MAC_CALLER_PROCESS = NOT_RECORDED
```

## HOME_RECORD_PLAN

다음 live 승인은 `SAFE_HIGH → supervised relative-start teleop → HOME → STOP → 3-sample record` 범위로만 제한한다.

1. 사용자가 SAFE_HIGH 정지, 전체 링크 비접촉, 주변 clear를 다시 확인한다.
2. read-only preflight에서 8000 health 정상, 8000/8002 teleop inactive, recording/inference inactive, 8003 부재, canonical USB 역할을 확인한다.
3. canonical 8000 하나만 사용한다. 임시 8003을 띄우거나 8002 `/move-arm`을 호출하지 않는다.
4. `/move-arm`은 한 번만 호출하고, journal에서 `relative_start origins captured`를 확인하지 못하면 즉시 중단한다. 시작 후 3초 무입력 stillness를 확인하고 startup jump가 있으면 중단한다.
5. 사용자가 leader로 천천히 HOME을 만든다. HOME은 camera view를 심하게 가리지 않고, table/약통/바구니 clearance가 충분하며, extreme joint pose가 아니고 SAFE_HIGH와 왕복하기 쉬운 자세여야 한다.
6. 도달 후 `/stop-teleoperation`으로 먼저 양쪽 serial disconnect를 확인한다. HOME을 자동으로 이어 움직이지 않는다.
7. follower Present를 read-only로 3회 읽어 raw/degree mean/std, FK GRASP TCP, Goal/Present, Moving, Load diagnostic, Temperature를 `configs/poses.yaml`에 병합한다.
8. `HOME=RECORDED` 뒤에만 SAFE_HIGH↔HOME offline route를 생성한다. 실제 왕복 시험은 별도 승인이다.

## 현재 상태

```ini
SAFE_HIGH = RECORDED
HOME = NOT_RECORDED
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED
hardware_command = 0
service_or_process_stop = 0
```

변경은 `NOT_COMMITTED/NOT_PUSHED`다.
