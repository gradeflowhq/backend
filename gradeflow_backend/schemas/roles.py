from typing import Literal

Role = Literal["owner", "editor", "viewer"]
ROLE_ORDER: dict[Role, int] = {"viewer": 1, "editor": 2, "owner": 3}
