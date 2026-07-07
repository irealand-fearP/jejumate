from app.repositories.local_store import get_home_data as get_local_home_data
from app.schemas.home import HomeResponse


def get_home_data() -> HomeResponse:
    return get_local_home_data()
