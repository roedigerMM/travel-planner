import requests

from .travel_data_provider import TravelDataProvider


class RapidApiSkyscannerClient(TravelDataProvider):
    def __init__(
        self,
        api_key: str,
        host: str,
        market: str = "DE",
        locale: str = "de-DE",
        timeout: int = 20,
    ):
        self.api_key = api_key
        self.host = host
        self.market = market
        self.locale = locale
        self.timeout = timeout
        self.base_url = f"https://{host}".rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("RapidAPI key is not configured.")
        if not self.host:
            raise RuntimeError("RapidAPI host is not configured.")
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
            "Accept": "application/json",
        }

    @staticmethod
    def _best_iata(item: dict) -> str | None:
        iata = (item.get("iataCode") or "").strip().upper()
        if iata:
            return iata

        sky_id = (item.get("skyId") or "").strip().upper()
        if len(sky_id) == 3 and sky_id.isalpha():
            return sky_id
        return None

    @staticmethod
    def format_error(exc: Exception) -> str:
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                payload = exc.response.json()
                message = payload.get("message")
                if message:
                    return str(message)
            except ValueError:
                pass
        return str(exc)

    def search_locations(self, keyword: str, subtypes=None, limit: int = 5) -> list[dict]:
        if subtypes is None:
            subtypes = ["AIRPORT", "CITY"]

        params = {
            "query": keyword,
            "market": self.market,
            "locale": self.locale,
        }
        resp = requests.get(
            f"{self.base_url}/flights/searchAirport",
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()

        items = []
        for item in payload.get("places", []):
            sub_type = (item.get("placeType") or "").strip().upper()
            if sub_type not in {value.upper() for value in subtypes}:
                continue

            iata = self._best_iata(item)
            if not iata:
                continue

            items.append(
                {
                    "sub_type": sub_type,
                    "name": item.get("name"),
                    "iata": iata,
                    "city_name": item.get("cityName"),
                    "city_code": (item.get("iataCode") or "").strip().upper() or None,
                    "country_code": None,
                    "provider_sky_id": item.get("skyId"),
                    "provider_entity_id": item.get("entityId"),
                }
            )

        return items[:limit]

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
        params = {}
        if origin_sky_id:
            params["originSkyId"] = origin_sky_id
        elif origin_iata:
            params["originSkyId"] = origin_iata

        if origin_entity_id:
            params["originEntityId"] = origin_entity_id

        if not params.get("originSkyId") or not params.get("originEntityId"):
            raise RuntimeError("RapidAPI destination discovery requires originSkyId and originEntityId.")

        if currency_code:
            params["currency"] = currency_code
        else:
            params["currency"] = "EUR"
        params["market"] = self.market

        resp = requests.get(
            f"{self.base_url}/flights/searchFlightEverywhere",
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()

        destinations = []
        for item in payload.get("destinations", []):
            destination_code = (item.get("skyId") or "").strip().upper()
            if not destination_code:
                continue

            preview_price = item.get("price")
            try:
                normalized_price = float(preview_price) if preview_price is not None else None
            except (TypeError, ValueError):
                normalized_price = None

            destination_iata = destination_code if len(destination_code) == 3 and destination_code.isalpha() else None
            destinations.append(
                {
                    "destination_code": destination_code,
                    "destination_iata": destination_iata,
                    "destination_entity_id": (item.get("entityId") or "").strip() or None,
                    "destination_name": (item.get("name") or "").strip() or destination_code,
                    "destination_type": "CITY",
                    "price": normalized_price,
                    "currency_code": item.get("currency") or currency_code or "EUR",
                    "departure_date": None,
                    "raw_json": item,
                }
            )

        return destinations
