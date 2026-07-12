from typing import Annotated

from pydantic import Secret, UrlConstraints
from pydantic_core import MultiHostUrl

from src.config.types.common import StrictModel

PostgresUrl = Annotated[
    MultiHostUrl,
    UrlConstraints(
        allowed_schemes=["postgresql", "postgres"],
        host_required=True,
    ),
]


class SessionsConfig(StrictModel):
    connect_string: Secret[PostgresUrl]
