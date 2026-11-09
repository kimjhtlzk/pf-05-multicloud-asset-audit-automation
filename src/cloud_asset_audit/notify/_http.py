from __future__ import annotations

import json
from urllib.request import Request, urlopen


def post_json(url: str, payload: dict[str, object], timeout: float = 10) -> None:
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS endpoints are allowed")
    request = Request(  # noqa: S310 - the scheme is checked above
        url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}
    )
    with urlopen(request, timeout=timeout):  # noqa: S310 - the scheme is checked above
        pass
