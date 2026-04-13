DEMO_DESTINATIONS = {
    "BER": [
        {
            "destination_iata": "LIS",
            "price": "189.00",
            "currency_code": "EUR",
            "departure_date": "2026-07-01",
            "raw_json": {"source": "demo", "origin": "BER", "destination": "LIS"},
        },
        {
            "destination_iata": "ATH",
            "price": "209.00",
            "currency_code": "EUR",
            "departure_date": "2026-07-03",
            "raw_json": {"source": "demo", "origin": "BER", "destination": "ATH"},
        },
        {
            "destination_iata": "BCN",
            "price": "155.00",
            "currency_code": "EUR",
            "departure_date": "2026-07-05",
            "raw_json": {"source": "demo", "origin": "BER", "destination": "BCN"},
        },
    ],
    "MUC": [
        {
            "destination_iata": "LIS",
            "price": "219.00",
            "currency_code": "EUR",
            "departure_date": "2026-07-02",
            "raw_json": {"source": "demo", "origin": "MUC", "destination": "LIS"},
        },
        {
            "destination_iata": "NAP",
            "price": "176.00",
            "currency_code": "EUR",
            "departure_date": "2026-07-04",
            "raw_json": {"source": "demo", "origin": "MUC", "destination": "NAP"},
        },
    ],
    "BOS": [
        {
            "destination_iata": "YUL",
            "price": "142.00",
            "currency_code": "USD",
            "departure_date": "2026-07-01",
            "raw_json": {"source": "demo", "origin": "BOS", "destination": "YUL"},
        },
        {
            "destination_iata": "DUB",
            "price": "488.00",
            "currency_code": "USD",
            "departure_date": "2026-07-06",
            "raw_json": {"source": "demo", "origin": "BOS", "destination": "DUB"},
        },
    ],
}


DEMO_LOCATIONS = [
    {
        "sub_type": "AIRPORT",
        "name": "Berlin Brandenburg",
        "iata": "BER",
        "city_name": "Berlin",
        "city_code": "BER",
        "country_code": "DE",
    },
    {
        "sub_type": "AIRPORT",
        "name": "Munich Airport",
        "iata": "MUC",
        "city_name": "Munich",
        "city_code": "MUC",
        "country_code": "DE",
    },
    {
        "sub_type": "AIRPORT",
        "name": "Boston Logan",
        "iata": "BOS",
        "city_name": "Boston",
        "city_code": "BOS",
        "country_code": "US",
    },
    {
        "sub_type": "CITY",
        "name": "Berlin",
        "iata": "BER",
        "city_name": "Berlin",
        "city_code": "BER",
        "country_code": "DE",
    },
    {
        "sub_type": "CITY",
        "name": "Munich",
        "iata": "MUC",
        "city_name": "Munich",
        "city_code": "MUC",
        "country_code": "DE",
    },
    {
        "sub_type": "CITY",
        "name": "Boston",
        "iata": "BOS",
        "city_name": "Boston",
        "city_code": "BOS",
        "country_code": "US",
    },
]


def get_demo_destinations(origin_iata: str) -> list[dict]:
    return [dict(item) for item in DEMO_DESTINATIONS.get(origin_iata, [])]


def get_demo_locations(keyword: str, subtypes=None, limit: int = 5) -> list[dict]:
    query = (keyword or "").strip().lower()
    normalized_subtypes = {item.upper() for item in (subtypes or ["AIRPORT", "CITY"])}

    matches = []
    for item in DEMO_LOCATIONS:
        if item["sub_type"].upper() not in normalized_subtypes:
            continue

        haystack = " ".join(
            [
                item.get("iata") or "",
                item.get("name") or "",
                item.get("city_name") or "",
                item.get("city_code") or "",
            ]
        ).lower()
        if query in haystack:
            matches.append(dict(item))

    return matches[:limit]
