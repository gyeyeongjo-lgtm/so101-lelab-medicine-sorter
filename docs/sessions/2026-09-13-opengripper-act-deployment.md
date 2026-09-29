# 2026-09-13 — 오픈그리퍼 ACT 학습·배포·1회 추론

## 범위

- 사용자 보고: 새 오픈그리퍼와 두 카메라 구도로 50개 에피소드 데이터셋을 수집했다.
- 실제 USB/모터 설정을 변경하지 않고, Mac 학습과 Hugging Face 비공개 모델 배포를 수행했다.
- 실제 추론은 사용자의 현장 안전 승인 뒤 1회만 실행했다.

## 데이터 및 학습

- 데이터셋: `Supermassive111/opengrip50_20260913_165317`.
- Hugging Face UI가 `Successfully Uploaded`를 표시했다. 비공개 데이터셋 Visualize Space의 `401`은 업로드 실패가 아니라 Space의 접근 권한 제한으로 분류했다.
- Mac MPS에서 ACT 학습이 `10000/10000` step, `1:53:29`, `End of training`으로 완료됐다.
- 최종 모델 경로:
  `/Users/jogyeyeong/lerobot-training/act_opengrip50_20260913_final/checkpoints/010000/pretrained_model`.
- 읽기 전용 확인: `config.json`, `model.safetensors`, 전·후처리 파일, `train_config.json`이 존재하며 최종 모델 디렉터리는 약 197 MB이다.
- 모델 특징: `observation.state` 6축, `observation.images.312` 640×480, `observation.images.camera_2` 640×480, `action` 6축.

## 모델 배포

- 사용자 승인: `private model 업로드 승인`.
- 비공개 모델 저장소: `Supermassive111/act-so101-opengrip50-v1`.
- 원격 읽기 전용 검증: private=`True`, commit `ddd6d2a40cbd25cfa5784ae25c95e8764854735f`, 필수 모델/전·후처리/학습 설정 파일 8개(`.gitattributes` 포함)가 확인됐다.
- LeLab UI Import 완료: 표시 이름 `ACT open gripper 50 episodes v1`.
- 학습 모델의 카메라 feature 이름은 LeLab의 현재 바인딩과 일치했다: `312`→`#0 HD Pro Webcam C920`, `camera_2`→`#2 USB Camera`.

## 1회 실제 추론

- 사용자 승인: `ACT open gripper 모델 추론 1회 안전 승인, 현장 안전 확인`.
- LeLab에서 30초 제한으로 실행했다. 모델·하드웨어 설정 후 UI가 `RUNNING` 상태(3초, 15초, 20초 관측)로 전환됐고, 이후 `Inference finished — Run completed`, 홈 `Ready`로 복귀했다.
- `PASS (UI)`: 프로세스 시작·실행·종료 경로는 통과했다.
- `NOT_VERIFIED`: 실제 집기 성공률·진동·물체 인식 품질은 UI 상태만으로 판정할 수 없으며 현장 관찰이 필요하다.

## 후속 주의

- Jetson의 CUDA PyTorch가 Orin `sm_87`을 지원하지 않아 rollout은 기존 CPU fallback을 사용한다. GPU 가속 복구는 별도 환경 호환 작업이다.
- 새 그리퍼/카메라 구도의 데이터는 이전 그리퍼·카메라 구도 데이터와 혼합하지 않는다.
- GitHub 작업 저장소에는 이번 세션 문서 외에 커밋·push를 하지 않았다 (`NOT_PUSHED`).
