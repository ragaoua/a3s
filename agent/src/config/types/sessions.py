from typing import Annotated

from pydantic import AnyUrl, Secret, UrlConstraints
from pydantic_core import MultiHostUrl

from src.config.types.common import StrictModel

PostgresUrl = Annotated[
    MultiHostUrl,
    UrlConstraints(
        allowed_schemes=["postgresql", "postgres"],
        host_required=True,
    ),
]

SqliteUrl = Annotated[
    AnyUrl,
    UrlConstraints(allowed_schemes=["sqlite"]),
]


class SessionsConfig(StrictModel):
    connect_string: Secret[PostgresUrl | SqliteUrl]
