"""Dash 애플리케이션 생성과 실행 진입점.

레이아웃·데이터 로직은 `dashboard` 패키지에 있고, 여기서는 조립만 한다.
프론트엔드 리소스는 로컬에서 제공한다(내부망 실행 전제).
"""

from __future__ import annotations

import os

from dash import Dash

from dashboard import callbacks, layout
from dashboard.data import load_dashboard_data


def create_app() -> Dash:
    data = load_dashboard_data()
    app = Dash(
        __name__,
        title=layout.DOCUMENT_TITLE,
        serve_locally=True,
        update_title=None,
    )
    view = callbacks.build_initial_view(data)
    app.layout = layout.create_layout(view)
    callbacks.register_callbacks(app, data)
    return app


app = create_app()

if __name__ == "__main__":
    # 운영 코드에 debug=True를 고정하지 않는다. 필요하면 환경 변수로 켠다.
    debug = os.environ.get("DASHBOARD_DEBUG", "").lower() in {
        "1",
        "true",
        "yes",
    }
    port = int(os.environ.get("DASHBOARD_PORT", "8050"))
    # host는 Dash 기본값(로컬호스트)을 그대로 쓴다.
    app.run(port=port, debug=debug)
