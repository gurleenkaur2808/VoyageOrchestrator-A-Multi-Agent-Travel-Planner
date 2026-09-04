import os
import re
import certifi
import airportsdata
import pycountry
import requests
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"]=certifi.where()
os.environ["REQUESTS_CA_BUNDLE"]=certifi.where()

API_KEY=os.getenv("AVIATIONSTACK_API_KEY")

DEFAULT_ORIGIN_IATA=os.getenv("DEFAULT_ORIGIN_IATA","DAC")

BASE_URL="https://api.aviationstack.com/v1/flights"

AIRPORTS=airportsdata.load("IATA")

COUNTRY_ALIASES={
    "usa":"US",
    "u.s.a":"US",
    "u.s.":"US",
    "america":"US",
    "united states":"US",
    "uk":"GB",
    "u.k.":"GB",
    "britain":"GB",
    "england":"GB",
    "uae":"AE",
    "dubai":"AE",
    "south korea":"KR",
    "korea":"KR",
    "russia":"RU",
    "vietnam":"VN",
    "bangladesh":"BD",
    "india":"IN",
    "japan":"JP",
    "china":"CN",
    "singapore":"SG",
    "malaysia":"MY",
    "thailand":"TH",
    "indonesia":"ID",
    "nepal":"NP",
    "qatar":"QA",
    "saudi arabia":"SA",
    "turkey":"TR",
    "canada":"CA",
    "australia":"AU",
    "germany":"DE",
    "france":"FR",
    "italy":"IT",
    "spain":"ES",
}

# Preferred main airport for country-level analysis
COUNTRY_MAIN_AIRPORT = {
    "BD": "DAC",
    "IN": "DEL",
    "JP": "NRT",
    "US": "JFK",
    "GB": "LHR",
    "AE": "DXB",
    "SG": "SIN",
    "MY": "KUL",
    "TH": "BKK",
    "ID": "CGK",
    "CN": "PEK",
    "KR": "ICN",
    "NP": "KTM",
    "QA": "DOH",
    "SA": "JED",
    "TR": "IST",
    "CA": "YYZ",
    "AU": "SYD",
    "DE": "FRA",
    "FR": "CDG",
    "IT": "FCO",
    "ES": "MAD",
}


CITY_MAIN_AIRPORT = {
    "dhaka": "DAC",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "kolkata": "CCU",
    "chennai": "MAA",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "tokyo": "NRT",
    "osaka": "KIX",
    "kyoto": "KIX",
    "new york": "JFK",
    "london": "LHR",
    "dubai": "DXB",
    "singapore": "SIN",
    "kuala lumpur": "KUL",
    "bangkok": "BKK",
    "doha": "DOH",
    "istanbul": "IST",
    "toronto": "YYZ",
    "sydney": "SYD",
    "paris": "CDG",
    "rome": "FCO",
    "madrid":"MAD",
    "frankfurt":"FRA",
}

def clean_text(text:str)->str:
    text=text.lower().strip()
    text=re.sub(r"[^a-z0-9\s]"," ",text)
    text=re.sub(r"\s+"," ",text)
    stop_words=[
        "flight","flights","ticket","tickets","trip","travel",
        "plan","complete","days","day","including","hotel",
        "hotels","sightseeing","under","budget","info","information"
    ]
    words=[w for w in text.split() if w not in stop_words]
    return " ".join(words).strip()

def country_name_to_code(text:str):
    text=clean_text(text)

    if text in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[text]

    try:
        country=pycountry.countries.lookup(text)
        return country.alpha_2
    except LookupError:
        pass

    for country in pycountry.countries:
        country_name=country.name.lower()
        if country_name in text:
            return country.alpha_2

    for alias,code in COUNTRY_ALIASES.items():
        if alias in text:
            return code

    return None

def airport_country_matches(airport:dict ,country_code:str)->bool:
    airport_country=str(airport.get("country","")).upper().strip()

    if airport_country ==country_code:
        return True
    try:
        country=pycountry.countries.get(alpha_2=country_code)
        if country and airport_country.lower()==country.name.lower():
            return True

    except Exception:
        pass

    return False

def get_best_airport_for_country(country_code:str):
    preferred=COUNTRY_MAIN_AIRPORT.get(country_code)

    if preferred and preferred in AIRPORTS:
        return preferred
    candidates=[]
    for iata,airport in AIRPORTS.items():
        if not iata:
            continue

        if airport_country_matches(airport,country_code):
            name=str(airport.get("name","")).lower()
            city=str(airport.get("city","")).lower()

            score=0

            if "international" in name:
                score += 50

            if "intl" in name:
                score +=40

            if "capital" in name:
                score +=20

            if city:
                score +=5

            candidates.append((score,iata))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]    

def resolve_location_to_iata(location:str):
    """
    converts country/city/airport/IATA into iata code.
    example
    japan->NRT
    Bangladesh->DAC
    """

    if not location:
        return None

    raw_location=location.strip()
    if re.fullmatch(r"[A-Za-z]{3}",raw_location):
        code=raw_location.upper()
        if code in AIRPORTS:
            return code

    location_clean = clean_text(
        raw_location
    )

    if not location_clean:

        return None
    if location_clean in CITY_MAIN_AIRPORT:

        return CITY_MAIN_AIRPORT[
            location_clean
        ]
    country_code = country_name_to_code(
        location_clean
    )

    if country_code:

        airport = get_best_airport_for_country(
            country_code
        )

        if airport:

            return airport

    city_matches = []

    for iata, airport in AIRPORTS.items():

        city = str(
            airport.get("city", "")
        ).lower().strip()

        name = str(
            airport.get("name", "")
        ).lower().strip()

        score = 0

        if city == location_clean:
            score += 100

        elif location_clean in city:

            score += 70

        if location_clean in name:

            score += 50

        if "international" in name:

            score += 10

        if score > 0:

            city_matches.append(
                (score, iata)
            )
        if city_matches:

            city_matches.sort(
            reverse=True
            )
            return city_matches[0][1]

    return None

def find_location_mentions(
    query: str
):

    query_lower = query.lower()

    mentions = []

    # Country aliases
    for alias in COUNTRY_ALIASES:

        pattern = (
            r"\b"
            + re.escape(alias)
            + r"\b"
        )

        if re.search(
            pattern,
            query_lower
        ):

            mentions.append(alias)

    # Countries from pycountry
    for country in pycountry.countries:

        country_name = (
            country.name.lower()
        )

        if len(country_name) < 4:
            continue

        pattern = (
            r"\b"
            + re.escape(country_name)
            + r"\b"
        )

        if re.search(
            pattern,
            query_lower
        ):

            mentions.append(
                country_name
            )

    # Cities
    for city in CITY_MAIN_AIRPORT:

        pattern = (
            r"\b"
            + re.escape(city)
            + r"\b"
        )

        if re.search(
            pattern,
            query_lower
        ):

            mentions.append(city)

    # Remove duplicates
    unique_mentions = []

    for item in mentions:

        if item not in unique_mentions:

            unique_mentions.append(item)

    return unique_mentions


# ============================================================
# 12. PARSE ORIGIN AND DESTINATION
# ============================================================

def parse_route(query: str):

    query = query.strip()

    query_lower = query.lower()

    # ------------------------------------------
    # Global flight query
    # ------------------------------------------

    global_keywords = [
        "all country",
        "all countries",
        "global flight",
        "global flights",
        "all flight",
        "all flights",
        "worldwide flight",
        "worldwide flights",
    ]

    if any(
        keyword in query_lower
        for keyword in global_keywords
    ):

        return None, None

    # ------------------------------------------
    # Direct IATA codes
    # Example:
    # DEL to NRT
    # ------------------------------------------

    codes = re.findall(
        r"\b[A-Z]{3}\b",
        query
    )

    if len(codes) >= 2:

        return (
            codes[0].upper(),
            codes[1].upper()
        )

    # ------------------------------------------
    # "from Delhi to Tokyo"
    # ------------------------------------------

    match = re.search(
        r"\bfrom\s+(.+?)\s+to\s+(.+?)"
        r"(?:\s+(?:on|for|under|including|"
        r"with|in|at)\b|[.!?]|$)",
        query_lower
    )

    if match:

        origin = match.group(1)

        destination = match.group(2)

        departure_iata = (
            resolve_location_to_iata(
                origin
            )
        )

        arrival_iata = (
            resolve_location_to_iata(
                destination
            )
        )

        return (
            departure_iata,
            arrival_iata
        )

    # ------------------------------------------
    # "to Tokyo from Delhi"
    # ------------------------------------------

    match = re.search(
        r"\bto\s+(.+?)\s+from\s+(.+?)"
        r"(?:\s+(?:on|for|under|including|"
        r"with|in|at)\b|[.!?]|$)",
        query_lower
    )

    if match:

        destination = match.group(1)

        origin = match.group(2)

        departure_iata = (
            resolve_location_to_iata(
                origin
            )
        )

        arrival_iata = (
            resolve_location_to_iata(
                destination
            )
        )

        return (
            departure_iata,
            arrival_iata
        )

    # ------------------------------------------
    # "flights from Delhi"
    # ------------------------------------------

    match = re.search(
        r"\bfrom\s+(.+?)(?:[.!?]|$)",
        query_lower
    )

    if match:

        origin = match.group(1)

        departure_iata = (
            resolve_location_to_iata(
                origin
            )
        )

        return departure_iata, None

    # ------------------------------------------
    # "flights to Tokyo"
    # ------------------------------------------

    match = re.search(
        r"\bto\s+(.+?)(?:[.!?]|$)",
        query_lower
    )

    if match:

        destination = match.group(1)

        arrival_iata = (
            resolve_location_to_iata(
                destination
            )
        )

        return None, arrival_iata

    # ------------------------------------------
    # Fallback
    # ------------------------------------------

    mentions = find_location_mentions(
        query
    )

    if len(mentions) >= 2:

        departure_iata = (
            resolve_location_to_iata(
                mentions[0]
            )
        )

        arrival_iata = (
            resolve_location_to_iata(
                mentions[1]
            )
        )

        return (
            departure_iata,
            arrival_iata
        )

    # Only one destination
    if len(mentions) == 1:

        arrival_iata = (
            resolve_location_to_iata(
                mentions[0]
            )
        )

        return (
            DEFAULT_ORIGIN_IATA,
            arrival_iata
        )

    return None, None


# ============================================================
# 13. FORMAT ONE FLIGHT
# ============================================================

def format_flight(
    flight: dict
):

    airline = (
        flight
        .get("airline", {})
        .get("name")
        or "Unknown airline"
    )

    flight_number = (
        flight
        .get("flight", {})
        .get("iata")
        or "Unknown flight number"
    )

    status = (
        flight.get("flight_status")
        or "Unknown"
    )

    departure = (
        flight.get("departure")
        or {}
    )

    arrival = (
        flight.get("arrival")
        or {}
    )

    departure_airport = (
        departure.get("airport")
        or "Unknown"
    )

    departure_iata = (
        departure.get("iata")
        or "Unknown"
    )

    departure_terminal = (
        departure.get("terminal")
        or "N/A"
    )

    departure_gate = (
        departure.get("gate")
        or "N/A"
    )

    departure_time = (
        departure.get("scheduled")
        or "Unknown"
    )

    departure_delay = (
        departure.get("delay")
    )

    arrival_airport = (
        arrival.get("airport")
        or "Unknown"
    )

    arrival_iata = (
        arrival.get("iata")
        or "Unknown"
    )

    arrival_terminal = (
        arrival.get("terminal")
        or "N/A"
    )

    arrival_gate = (
        arrival.get("gate")
        or "N/A"
    )

    arrival_time = (
        arrival.get("scheduled")
        or "Unknown"
    )

    arrival_delay = (
        arrival.get("delay")
    )

    if departure_delay is not None:

        departure_delay_text = (
            f"{departure_delay} minutes"
        )

    else:

        departure_delay_text = "N/A"

    if arrival_delay is not None:

        arrival_delay_text = (
            f"{arrival_delay} minutes"
        )

    else:

        arrival_delay_text = "N/A"

    return f"""
Airline: {airline}
Flight: {flight_number}
Status: {status}

Departure:
- Airport: {departure_airport}
- IATA: {departure_iata}
- Terminal: {departure_terminal}
- Gate: {departure_gate}
- Scheduled: {departure_time}
- Delay: {departure_delay_text}

Arrival:
- Airport: {arrival_airport}
- IATA: {arrival_iata}
- Terminal: {arrival_terminal}
- Gate: {arrival_gate}
- Scheduled: {arrival_time}
- Delay: {arrival_delay_text}
""".strip()


# ============================================================
# 14. MAIN FLIGHT SEARCH FUNCTION
# ============================================================

def search_flights(
    query: str,
    limit: int = 10
):

    # ------------------------------------------
    # Check API key
    # ------------------------------------------

    if not API_KEY:

        return (
            "Flight API error: "
            "AVIATIONSTACK_API_KEY is missing.\n"
            "Add it to your .env file."
        )

    # ------------------------------------------
    # Understand user's route
    # ------------------------------------------

    departure_iata, arrival_iata = (
        parse_route(query)
    )

    # ------------------------------------------
    # Build API parameters
    # ------------------------------------------

    params = {
        "access_key": API_KEY,
        "limit": min(limit, 100),
    }

    if departure_iata:

        params["dep_iata"] = departure_iata

    if arrival_iata:

        params["arr_iata"] = arrival_iata

    # ------------------------------------------
    # Call AviationStack
    # ------------------------------------------

    try:

        response = requests.get(
            BASE_URL ,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as error:

        return (
            "Flight API request failed: "
            f"{error}"
        )

    except ValueError:

        return (
            "Flight API returned invalid JSON."
        )

    # ------------------------------------------
    # API-level error
    # ------------------------------------------

    if "error" in data:

        error = data["error"]

        return (
            "Flight API error:\n"
            f"Code: {error.get('code', 'Unknown')}\n"
            f"Message: "
            f"{error.get('message', 'Unknown error')}"
        )

    # ------------------------------------------
    # Get flight list
    # ------------------------------------------

    flight_data = data.get(
        "data",
        []
    )

    if not flight_data:

        route_text = ""

        if departure_iata and arrival_iata:

            route_text = (
                f" for route "
                f"{departure_iata} → "
                f"{arrival_iata}"
            )

        elif departure_iata:

            route_text = (
                f" from {departure_iata}"
            )

        elif arrival_iata:

            route_text = (
                f" to {arrival_iata}"
            )

        return (
            "No live flight data found"
            f"{route_text}.\n\n"
            "Note: AviationStack provides "
            "flight/status information, "
            "not ticket prices."
        )

    # ------------------------------------------
    # Create route heading
    # ------------------------------------------

    if departure_iata and arrival_iata:

        route_info = (
            f"Live flights from "
            f"{departure_iata} to "
            f"{arrival_iata}"
        )

    elif departure_iata:

        route_info = (
            f"Live flights from "
            f"{departure_iata}"
        )

    elif arrival_iata:

        route_info = (
            f"Live flights to "
            f"{arrival_iata}"
        )

    else:

        route_info = "Global live flights"

    # ------------------------------------------
    # Format results
    # ------------------------------------------

    formatted_flights = []

    for flight in flight_data[:limit]:

        formatted_flights.append(
            format_flight(flight)
        )

    return (
        route_info
        + "\n\n"
        + "\n\n---\n\n".join(
            formatted_flights
        )
    )


# ============================================================
# 15. TEST
# ============================================================

if __name__ == "__main__":

    print(
        search_flights(
            "plan a 7 days Japan trip from Bangladesh"
        )
    )

    print("\n" + "=" * 80 + "\n")

    print(
        search_flights(
            "all country flight info"
        )
    )