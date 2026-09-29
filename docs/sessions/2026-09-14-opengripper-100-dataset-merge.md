# 2026-09-14 — 오픈그리퍼 100 Episode 병합·W&B 학습 준비

## 범위

- 사용자 승인: 네 private 데이터셋 업로드·병합과 100 episode 학습 준비.
- 실제 로봇 구동, 토크 변경, USB 재연결은 이 작업에서 수행하지 않았다.
- API key, token, 원본 영상·parquet 데이터는 문서나 Git에 기록하지 않았다.

## 원본 검증

| Source dataset | Episodes | Frames |
| --- | ---: | ---: |
| `Supermassive111/open100_20260914_144019` | 42 | 29,313 |
| `Supermassive111/28_20260914_153007` | 14 | 10,761 |
| `Supermassive111/14_20260914_153943` | 14 | 9,244 |
| `Supermassive111/30_20260914_155550` | 30 | 18,974 |
| **Total** | **100** | **68,292** |

- 모든 원본은 action/state 6축(`shoulder_pan`부터 `gripper`), `observation.images.312`, `observation.images.camera_2`를 공유한다.
- 두 image feature는 모두 640×480, 30 FPS였다.
- 서로 다른 feature를 가진 데이터셋, 빈 녹화 session은 병합 대상에서 제외했다.

## 병합 및 업로드

- 원본을 수정하지 않고 로컬 병합본을 생성했다.
- 병합본 task를 다음 단일 문장으로 통일했다.
  `Pick an item from the pickup area and place it in the correct basket.`
- private Hub 저장소: `Supermassive111/opengrip100_20260914_merged`.
- 원격 dry-run에서 metadata, parquet, 두 카메라 영상으로 구성된 14개 파일, 약 1.3 GB를 확인했다.

## W&B 학습 상태

- Mac의 `lerobot-train` 환경은 Hugging Face 인증과 W&B 인증이 완료된 상태다.
- 다음 학습에는 `wandb.enable=true`를 사용해 loss, learning rate, update/data 시간, sample rate를 W&B에 기록한다.
- `NOT_RUN`: 사용자 지정 step 수와 실행 컴퓨터가 확정되기 전이므로 이 병합 데이터셋의 ACT 학습은 아직 시작하지 않았다.
- `NOT_PUSHED`: GitHub 작업 저장소에는 이번 작업에 대한 커밋이나 push를 수행하지 않았다.
