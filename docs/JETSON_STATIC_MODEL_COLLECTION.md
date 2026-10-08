# Jetson 설치 모델 누락분 정적 수집 (읽기 전용)

2026-10-08 사용자가 보낸 첫 출력으로 LeLab 0.1.0, LeRobot 0.6.0, follower 캘리브레이션 SHA와 일부 설치 소스 SHA/매핑을 확인했다. 터미널 붙여넣기 중 원문 일부가 섞여 URDF 출력과 정규화 함수 본문이 빠졌다. 아래는 **Jetson 셸 `(base) jetson3@ubuntu:~$`에서** 그 누락분만 읽는다. 시리얼 포트, 모터, 서비스, 토크, 파일 내용 변경을 하지 않는다. Python 업그레이드도 필요 없다.

```sh
/home/jetson3/.local/share/uv/tools/lelab/bin/python - <<'PY'
from pathlib import Path
import hashlib
import importlib.util
import xml.etree.ElementTree as ET

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

spec = importlib.util.find_spec('lerobot')
if spec is None or not spec.submodule_search_locations:
    print('LEROBOT_NOT_FOUND')
else:
    root = Path(next(iter(spec.submodule_search_locations)))
    bus = root / 'motors' / 'motors_bus.py'
    if bus.is_file():
        print('FILE', bus, sha256_file(bus))
        lines = bus.read_text().splitlines()
        for number in range(850, min(910, len(lines)) + 1):
            print('SOURCE', number, lines[number - 1])
    else:
        print('FILE_MISSING', bus)

tool_root = Path('/home/jetson3/.local/share/uv/tools/lelab')
urdfs = sorted(tool_root.rglob('so101_new_calib.urdf'))
if not urdfs:
    print('URDF_NOT_FOUND_UNDER', tool_root)
for path in urdfs:
    print('URDF_FILE', path, sha256_file(path))
    for joint in ET.parse(path).getroot().iter('joint'):
        axis = joint.find('axis')
        origin = joint.find('origin')
        limit = joint.find('limit')
        print('URDF_JOINT', joint.get('name'), joint.get('type'),
              'axis=', axis.attrib if axis is not None else {},
              'origin=', origin.attrib if origin is not None else {},
              'limit=', limit.attrib if limit is not None else {})
PY
```

예상 출력: `FILE`(설치 정규화 코드 경로/SHA), `SOURCE 850`–`SOURCE 910`(step↔도 변환·부호·클램프), `URDF_FILE`(현재 파일 경로/SHA), 각 `URDF_JOINT`의 축·원점·제한. 파일이 없으면 `FILE_MISSING`/`URDF_NOT_FOUND_UNDER`가 나온다. **출력에 비밀번호·키·토큰·캘리브레이션 전체 JSON은 포함되지 않는다.** 출력만 전달하고 셸 프롬프트나 입력한 비밀번호는 복사하지 않는다. 정적 자료만으로 물리 회전 방향·모터 명령 도달·충돌 여유는 확정할 수 없다.
