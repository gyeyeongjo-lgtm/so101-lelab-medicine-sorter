# 2026-10-14 C approach teaching 준비와 untraced 텔레옵 시작 사건

## 요청 범위와 현장 확인

사용자는 LeLab 텔레옵을 종료했다. 새 기록 범위를 `PICK_READY→C` 전체가 아닌 **fresh CURRENT→C APPROACH만**으로 명시했다. 팔·손가락·링크 정지, C/테이블 비접촉, 현재 물리 finger opening 충분함, 리더 3초 정지 및 처음에는 테이블에서 멀어지도록 천천히 이동할 준비를 현장에서 확인했다. 그리퍼는 닫지 않고 GRASP/LIFT는 수행하지 않는다.

Jetson 실제 user `lelab.service`가 active이고 일반 system service는 inactive였다. 서비스의 8000 worker 하나만 존재했으며 당시 teleoperation/recording/inference inactive, privileged `fuser /dev/ttyACM0 /dev/ttyACM1` rc `1`로 두 포트 무점유였다. 설치 Python과 실제 `teleoperate.py`/`SO101Follower.send_action`을 확인했다. 그리퍼 키를 제외한 action을 전송하면 `Goal_Position` 동기 쓰기 대상에서 그리퍼가 빠진다.

설치 전 read-only follower 3회 동일: arm Present `[-6.285714,-67.384615,+81.538462,+28.000000,-22.197802]°`, 그리퍼 **encoder** `4.957160%`, Moving 전 축 `0`, Torque 전 축 `1`, Tmax `39°C`; FK GRASP TCP `[33.324887,-223.853788,59.060992] mm`. 이 encoder 수치는 실제 finger aperture의 측정치가 아니며, 현장 육안 확인과 구별한다. 같은-owner bus가 아니므로 측정은 세 제어 idle·포트 free에서 쓰기 API를 차단한 별도 read-only 스냅샷으로 수행했고 포트를 해제했다.

## 코드·배치 검증

`scripts/relative_start_teleop.py`에 arm-only target/dispatch를 추가했다. 이 모드는 fresh gripper origin을 trace용 상태로 유지하지만 guarded sender에는 arm 5축 키만 전달한다. `scripts/teleop_cycle_trace.py`는 `gripper_goal_sent=false`를 cycle row에 명시한다. LeLab 설치 `teleoperate.py`는 `empirical_relative_teaching` trace 세션에서만 arm-only를 사용하고, 일반 untraced `relative_start`는 기존 전체 6축 동작을 유지한다. 기존 arm step/range/Elbow guard와 3초 startup stillness는 유지했다.

로컬 `tests.test_relative_start_teleop`·`tests.test_teleop_cycle_trace` **28/28 PASS**. Jetson 격리 폴더 `/home/jetson3/so101-c-approach-staged-ohOG4Q/`에서 설치 Python compile 및 fake worker PASS. staged와 실제 설치본 각각 fake 7 cycle, telemetry·FK·3회 fake final sample/output 생성 PASS, empirical gripper Goal send `0`, 일반 untraced relative-start 동작 PASS, legacy full-cycle+relative-start는 전송 전 fail-closed. fake는 real serial/Goal/Torque/motor command `0`이다.

서비스 idle·포트 free에서 user `lelab.service`를 정지하고 기존 설치 3파일을 격리 폴더 `installed-backup/`에 원 SHA로 보존했다. 새 3파일을 설치하고 SHA 일치·py_compile·설치본 fake PASS 후 서비스를 active로 재시작했다. trace root/ticket 환경은 **설정하지 않았으므로 recorder는 무장되지 않았다**.

## 예기치 않은 live 시작과 종료

LeLab UI의 `Teleoperation` 버튼을 설정 화면 이동으로 오인해 눌렀다. 실제로 이 버튼은 텔레옵을 즉시 시작한다. 화면에 `Teleoperation Started`와 `Live Robot Data`가 나타나자 즉시 뒤로 가기로 종료했다. UI는 `Teleoperation stopped / The arm was disconnected cleanly`를 표시했고 API도 `teleoperation_active=false`, privileged 두 포트 `fuser` rc `1` 무점유였다. 이 세션은 trace 미무장으로 **기록되지 않았으며**, 일반 untraced `relative_start`라 그리퍼 포함 목표 전송 가능성이 있다. Goal write 수는 확인할 trace가 없어 미정; `MOTOR_COMMAND=0`이나 `GRIPPER_GOAL_SEND=0`으로 보고하지 않는다.

사용자가 현장에서 정지·비접촉을 다시 확인했다. 종료 후 read-only 3회는 arm Present `[-6.285714,-67.384615,+82.329670,+28.439560,-22.109890]°`, gripper encoder `5.018360%`, Moving 전 축 `0`, Torque 전 축 `1`, Tmax `39°C`, Goal−Present Elbow `−0.527473°`다. 이전 read 대비 Elbow `+0.791209°`, Wrist Flex `+0.439560°`, Wrist Roll `+0.087912°`, gripper encoder `+0.061200 pp`; Pan/Lift 변화 `0°`. 물리 손가락 이동 여부는 이 readback만으로 판정하지 않는다.

## 현재 상태

`physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`, `C_APPROACH_EMPIRICAL=NOT_RECORDED`, teaching trace `NOT_RECORDED`, GRASP/LIFT `NOT_RUN`. 새 명시적 사용자 승인 전 trace 무장·텔레옵 재시작 금지. 사용자 소유 ArUco SVG/PDF 삭제는 건드리지 않았다. 변경 `NOT_COMMITTED/NOT_PUSHED`; GitHub 이슈 갱신 `NOT_RUN`(대상 번호 미지정). 원본 live 로그·비밀번호는 커밋하지 않는다.
