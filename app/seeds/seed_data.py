from app.core.config import get_settings
from app.db.init_db import init_database
from app.db.session import create_session_factory
from app.services.seed_service import seed_database


def main() -> None:
    settings = get_settings()
    init_database(settings.database_url)
    session_factory = create_session_factory(settings.database_url)
    session = session_factory()
    try:
        print(seed_database(session))
    finally:
        session.close()


if __name__ == "__main__":
    main()

