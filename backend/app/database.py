from collections.abc import Generator


def get_db() -> Generator[None, None, None]:
    # Placeholder dependency. SQLAlchemy session wiring will be added when
    # persistent tasks and verification runs move from memory to PostgreSQL.
    yield None

