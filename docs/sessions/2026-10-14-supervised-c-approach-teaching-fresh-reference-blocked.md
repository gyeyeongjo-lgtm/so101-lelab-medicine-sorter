# SUPERVISED C APPROACH TEACHING — fresh reference mismatch, 실행 보류

사용자는 `RUN SUPERVISED C APPROACH TEACHING`을 승인했고 현장에서 팔 지지·follower/leader 정지·전체 비접촉·주변 clear·3초 리더 정지·즉시 중단 준비를 확인했다. 실제 teaching 진입 전 LeLab teleoperation/recording/inference inactive, canonical follower `/dev/ttyACM1=5AE6058306`와 leader `/dev/ttyACM0=5AE6085272`, privileged 양 포트 무점유를 확인했다. Jetson 독립 진입점 SHA `6756fb2b…500753`은 배치 검증본과 같았다.

쓰기 차단 도구 SHA `7c440b81…f3c56`로 follower를 0.2초 간격 3회 read-only 측정했다. 세 표본이 동일했다: Present raw `[2065,1467,2649,2498,1612,490]`, Goal raw `[2065,1466,2649,2497,1611,490]`, Torque 전 축 ON, Moving 전 축 0, Tmax `36°C`, Goal–Present 최대 `1 raw`. 기존 quantized reference Present `[2065,1467,2649,2497,1612,490]`보다 **Wrist Flex만 +1 raw** 달라 현 진입점의 `MAX_REFERENCE_DRIFT_RAW=0` gate에서 `current_hold_reference_present_changed`로 차단될 조건이다. 이는 현재 3회 연속 표본 자체의 안정 판정과 별개의 start-reference 불일치다.

이 불일치를 조용히 허용하거나 reference를 갱신하지 않았다. fresh pre-connect JSON/ticket 생성, leader 포트 연결, teaching entrypoint 실제 시작, recorder arm, relative-start, Goal/config/Torque/motor write는 전부 `NOT_RUN/0`; 자동 재시도도 `0`. read-only follower 포트는 정상 해제됐다. 다음 live command는 `NONE`; 새 기준 pose를 쓸지 명시적으로 결정하고 offline/fake 재검증하기 전에는 재시작하지 않는다. 기존 `CURRENT_HOLD_STABLE=false`와 과거 6개 표본의 `HOLD_STABLE_QUANTIZED=PASS`는 그대로 보존한다.

변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 갱신 `NOT_RUN`.
