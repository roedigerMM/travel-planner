from abc import ABC, abstractmethod


class TravelDataProvider(ABC):
    @abstractmethod
    def search_locations(self, keyword: str, subtypes=None, limit: int = 5) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def search_destinations(
        self,
        origin_iata: str,
        travel_month: str | None = None,
        duration_days: int | None = None,
        max_price: float | None = None,
        currency_code: str | None = None,
        non_stop: bool | None = None,
        origin_sky_id: str | None = None,
        origin_entity_id: str | None = None,
    ) -> list[dict]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def format_error(exc: Exception) -> str:
        raise NotImplementedError
