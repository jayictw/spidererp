from app.core.config import get_settings
from app.db.base import Base
from app.db.session import create_sqlalchemy_engine
import app.models  # noqa: F401


def init_database(database_url: str | None = None) -> None:
    settings = get_settings()
    engine = create_sqlalchemy_engine(database_url or settings.database_url)
    Base.metadata.create_all(bind=engine)


def main() -> None:
    init_database()


if __name__ == "__main__":
    main()

