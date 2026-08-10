"""테스트 공통 설정.

모든 테스트가 `tests/data/`의 표본 파일을 읽도록 환경 변수를 걸어 둔다.
수집 전에 정해져야 하므로 픽스처가 아니라 여기서 바로 설정한다. 픽스처로 두면
범위가 더 넓은 픽스처(module 단위 `dataset`)가 먼저 만들어져 값이 비어 버린다.

개별 테스트가 `monkeypatch.setenv`로 다시 덮으면 그 값이 이긴다.
"""

from __future__ import annotations

import os

from dashboard import sources
from fixture_data import MONTHLY_FILE, PROFILE_FILE

# 원본 모듈에 적어 둔 파일 이름은 실행 환경마다 다르다. 테스트가 그 값에
# 좌우되지 않도록 비우고, 읽을 파일은 환경 변수로만 정한다.
sources.monthly.FILE = ""
sources.profile.FILE = ""

os.environ[sources.monthly.FILE_ENV] = str(MONTHLY_FILE)
os.environ[sources.profile.FILE_ENV] = str(PROFILE_FILE)
