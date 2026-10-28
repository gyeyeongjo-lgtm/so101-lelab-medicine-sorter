# 4단계 무학습 준비 기록

2026-10-28, 시작37667d53ba64eb2a833dc559aed8a79d328f9809, vla/main, 시작worktree clean.
사용자의 실제학습/로봇구동 금지를 조건부smoke보다 우선해 smoke도 NOT_RUN.

## 선행 점검

Jetson 1회 BatchMode/strict known-host/5초 timeout hostname읽기는 socket 권한거부 exit255.
주소/credential/SSH 설정을 바꾸지 않고 중단했다. torch GPU조회CUDAfalse/device0/NVML경고.
장치open·모델로드·GPU 계산0. 설치환경 변경 없음.
5f03c57/d5136c0/37667d5의 전체 safe-mock discovery는 각각587/656/691 testsRun,
failure6/error23/skip15 모두동일. 경로정규화 전체trace/skip사유도동일.
현장fixture/ArUco29, dependency15, safetycore신규0, serial필요0, 기타0.
결과를 먼저 보고한 뒤 safety원본을 보존하고 새준비코드만 작성했다.
174PASS는 VLA69+fixed_demo64+demo_web7+sorter31+camera_preview_joint_ws3 subset이며 전체discovery가 아니었다.

## 구현·소스 확인

VLA_STAGE4.md에 명시된 새config/scripts/tests만 추가. 제어기/보정/상위공식source 수정0.
공식0.6 source train help exit0/3974줄, 설치distribution0.6.1과 분리해표시.
episodes 옵션존재, eval_split은task별마지막episode분리라사용금지(0고정), train-onlystats자동재계산없음확인.
주입adapter는 explicittrain/eval과train-onlystats를fake학습모듈까지연결하고finallyhook원복시험.
실제launchentrypoint없음, 모든execute는BLOCKED. raw후보복사실행은안내하지않음.
resume는localconfig/manifest정합성만 검사. 원본checkpoint 수정/모델로드/optimizer복원0.
W&B/Hub off, 비용발생클라우드 기능없음. manifest는환경비밀값을읽지않음.
ACT원본scriptbatch8/steps100000/workers2확인. chunk/camera옵션은명시없어추정하지않음.

## 검증

- 신규초기29tests exit0. train통계불변/주입연결2개추가 후 VLA전체135tests exit0/skip0.
- dry-run exit0는 계획출력이지ready아님. execute exit2는의도된차단이며파일·subprocess생성0.
- 실제제어/학습모듈대신fake객체. 원본source/derivedfixture외실데이터쓰기0.
- 최종전용결과 `.local/stage4/vla-final-verified.json`, 전체는 `.local/stage4/full-final.json`.
  최종 VLA135 PASS/skip0, 전체722 testsRun/failure6/error23/skip15. 변경 전과 실패·오류·skip 항목 및 사유 완전 동일.
  전체는baseline과기존실패목록비교하며 setUpClass 때문에 PASS단순뺄셈하지않음.
- baseline보고서/ACTsource근거는 reports/vla-stage4-preflight-20261028/에 이름·사유만정리.
  raw trace/telemetry는 `.local`에 두고 커밋하지 않음.

## 미완료·종료

미확인: 새실데이터의session/units/physicalmapping, basecheckpointmetadata, GPUVRAM,
공식실학습에서adapter통합/normalizer/평가loader/resume동작. smoke/학습/모델평가/로봇NOT_RUN.
이 상태를학습준비완료로보고하지않음. 실제녹화장치확인이나학습은별도범위.
실제학습 실행 금지는 실행기 구현 금지를 뜻하지 않는다. 실제 `--execute` 상류 호출 연결은 미구현으로 남긴다.
로컬commit뒤새stage4incremental.bundle 생성/verify/SHA확인. stage2/3bundle유지.
기준5f03c571e223f86f422b6eb68af94a6ff05c78db필요,전체역사객체미보유로self-contained아님.
push NOT_PUSHED, 5단계 미시작. 롤백은stage4commit revert이며원본데이터/서비스는변경없음.
