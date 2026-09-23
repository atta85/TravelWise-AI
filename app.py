import os
import json
import re
from datetime import datetime, date, timedelta

import folium
import requests
import streamlit as st
from groq import Groq
from streamlit_folium import st_folium


# ------------------------------------------------------------
# TravelWise AI — Hackathon MVP
# Free/open data + Groq GPT-OSS 120B browser research + Streamlit
# ------------------------------------------------------------

st.set_page_config(
    page_title="TravelWise AI",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_NAME = "TravelWise AI"
OPEN_METEO_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OSRM_TRIP = "https://router.project-osrm.org/trip/v1/driving"
OSRM_ROUTE = "https://router.project-osrm.org/route/v1/driving"

st.markdown(
    """
    <style>
    .hero {
        padding: 1.2rem 1.4rem;
        border-radius: 18px;
        background: linear-gradient(135deg,#12324a,#315d73);
        color: white;
        margin-bottom: 1rem;
    }
    .small-note { color:#667085; font-size:0.88rem; }
    .score { font-size:2rem; font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------- helpers -----------------------------

def get_secret(name: str):
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name)


def geocode_city(city: str):
    """Open-Meteo geocoder; no API key required."""
    params = {"name": city, "count": 5, "language": "en", "format": "json"}
    r = requests.get(
        OPEN_METEO_GEOCODING,
        params=params,
        headers={"User-Agent": "TravelWiseAI-Hackathon/1.0"},
        timeout=15,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return None

    # Prefer an exact-ish city match, otherwise first result.
    city_l = city.strip().lower()
    best = None
    for x in results:
        if str(x.get("name", "")).lower() == city_l:
            best = x
            break
    return best or results[0]


def geocode_many(cities):
    out = {}
    for city in cities:
        if city in out:
            continue
        try:
            out[city] = geocode_city(city)
        except Exception:
            out[city] = None
    return out


def weather_forecast(lat, lon, start_date, end_date):
    """Daily forecast/current data. Open-Meteo supports forecast planning for near-term trips."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "forecast_days": 16,
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "precipitation_sum",
            "wind_speed_10m_max",
            "uv_index_max",
        ]),
    }
    r = requests.get(OPEN_METEO_FORECAST, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    daily = data.get("daily", {})
    dates = daily.get("time", [])

    rows = []
    for i, d in enumerate(dates):
        if start_date.isoformat() <= d <= end_date.isoformat():
            rows.append({
                "date": d,
                "weather_code": daily.get("weather_code", [None])[i],
                "max_c": daily.get("temperature_2m_max", [None])[i],
                "min_c": daily.get("temperature_2m_min", [None])[i],
                "rain_pct": daily.get("precipitation_probability_max", [None])[i],
                "rain_mm": daily.get("precipitation_sum", [None])[i],
                "wind_kmh": daily.get("wind_speed_10m_max", [None])[i],
                "uv": daily.get("uv_index_max", [None])[i],
            })
    return rows


def weather_label(code):
    if code is None:
        return "Unknown"
    code = int(code)
    if code == 0:
        return "Clear sky"
    if code in (1, 2, 3):
        return "Partly cloudy / cloudy"
    if code in (45, 48):
        return "Fog"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67):
        return "Rain"
    if code in (71, 73, 75, 77):
        return "Snow"
    if code in (80, 81, 82):
        return "Rain showers"
    if code in (85, 86):
        return "Snow showers"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return "Mixed"


def weather_risk(rows):
    if not rows:
        return 0, "No forecast data"
    score = 0
    for x in rows:
        rain = x.get("rain_pct") or 0
        wind = x.get("wind_kmh") or 0
        code = x.get("weather_code")
        if rain >= 70:
            score += 3
        elif rain >= 40:
            score += 1
        if wind >= 45:
            score += 2
        if code in (95, 96, 99):
            score += 4
    avg = score / max(1, len(rows))
    if avg < 1:
        return 90, "Low weather disruption risk"
    if avg < 2:
        return 70, "Moderate weather disruption risk"
    if avg < 3:
        return 50, "Elevated weather disruption risk"
    return 30, "High weather disruption risk"


def osrm_trip(points):
    """
    points = [{"name":..., "lat":..., "lon":...}, ...]
    OSRM Trip fixes the first and last point and optimizes intermediate stops.
    """
    if len(points) < 2:
        return None

    coords = ";".join(f"{p['lon']},{p['lat']}" for p in points)
    url = f"{OSRM_TRIP}/{coords}"
    params = {
        "roundtrip": "false",
        "source": "first",
        "destination": "last",
        "steps": "false",
        "geometries": "geojson",
        "overview": "full",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok" or not data.get("trips"):
        return None

    trip = data["trips"][0]
    waypoints = data.get("waypoints", [])

    ordered = [None] * len(points)
    for idx, wp in enumerate(waypoints):
        ti = wp.get("trips_index")
        wi = wp.get("waypoint_index")
        if ti == 0 and wi is not None and 0 <= wi < len(points):
            ordered[wi] = points[idx]

    # More reliable: use waypoint_index to map input point -> output order.
    ordered_pairs = []
    for input_idx, wp in enumerate(waypoints):
        if wp.get("trips_index") == 0:
            ordered_pairs.append((wp.get("waypoint_index", 999), points[input_idx]))
    ordered_pairs.sort(key=lambda x: x[0])
    ordered_points = [p for _, p in ordered_pairs]

    if len(ordered_points) != len(points):
        ordered_points = points

    return {
        "distance_km": trip.get("distance", 0) / 1000,
        "duration_h": trip.get("duration", 0) / 3600,
        "geometry": trip.get("geometry", {}),
        "ordered_points": ordered_points,
    }


def route_in_given_order(points):
    if len(points) < 2:
        return None
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in points)
    url = f"{OSRM_ROUTE}/{coords}"
    params = {"steps": "false", "geometries": "geojson", "overview": "full"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    rt = data["routes"][0]
    return {
        "distance_km": rt.get("distance", 0) / 1000,
        "duration_h": rt.get("duration", 0) / 3600,
        "geometry": rt.get("geometry", {}),
        "ordered_points": points,
    }


def draw_map(route_result, points):
    center = [points[0]["lat"], points[0]["lon"]]
    m = folium.Map(location=center, zoom_start=6, control_scale=True)

    for i, p in enumerate(points):
        folium.Marker(
            [p["lat"], p["lon"]],
            tooltip=f"{i+1}. {p['name']}",
            popup=f"{p['name']}",
            icon=folium.Icon(color="blue" if i not in (0, len(points)-1) else "red"),
        ).add_to(m)

    if route_result and route_result.get("geometry"):
        coords = route_result["geometry"].get("coordinates", [])
        latlon = [[c[1], c[0]] for c in coords]
        folium.PolyLine(latlon, weight=5, opacity=0.8).add_to(m)

    return m


def groq_client():
    key = get_secret("GROQ_API_KEY")
    if not key:
        return None
    return Groq(api_key=key)


def research_with_groq(trip, weather_summary):
    """
    Uses OpenAI GPT-OSS 120B on Groq with Groq's built-in Browser Search
    for current web research.
    """
    client = groq_client()
    if not client:
        return "GROQ_API_KEY is not configured. Add it in Streamlit Secrets."

    places = " → ".join([p["name"] for p in trip["points"]])
    stop_text = ", ".join([p["name"] for p in trip["points"][1:-1]]) or "No intermediate overnight stop"

    prompt = f"""
You are the research and travel-planning engine for {APP_NAME}.

Create a practical, concise but informative travel brief for this trip.
You have access to Groq's built-in Browser Search. Use it to research current,
relevant information before answering, especially travel conditions, attractions,
accommodation, transport, weather-related issues and local advisories.

ROUTE:
{places}

INTERMEDIATE STOPS:
{stop_text}

DEPARTURE:
{trip["departure"]}

RETURN:
{trip["return"]}

TRAVEL MODE:
{trip["mode"]}

TRAVEL PARTY:
Adults={trip["adults"]}, Children={trip["children"]}, Elderly={trip["elderly"]}, Disabled={trip["disabled"]}

WEATHER DATA FROM OPEN-METEO:
{json.dumps(weather_summary, ensure_ascii=False)}

RESEARCH REQUIREMENTS:
1. Attractions/sights worth seeing at each major stop.
2. A day-by-day visit plan that respects the trip dates and travel time.
3. Hotels/accommodation suggestions. Give a small shortlist with approximate price category,
   rating/reputation when available, family suitability, and a direct source/search link if available.
4. Local transport and public-transport advice where relevant.
5. Current local issues that a traveler should know about: road closures, protests,
   security advisories, extreme weather, congestion, seasonal issues, closures, etc.
6. Practical advice for clothing, rain/heat/cold, footwear, hydration, sun protection,
   children, elderly travelers and disabled travelers.
7. Food/water and general travel-safety precautions where relevant.
8. If the travel party includes children/elderly/disabled people, prioritize accessible,
   low-stress and family-friendly options.
9. Do not invent exact prices, opening hours, road closures, ratings, or availability.
   If uncertain, say "verify before booking".
10. Distinguish factual/current findings from general recommendations.
11. Prefer current/official sources for road, safety, tourism and travel-advisory information.
12. Use reputable travel platforms for attractions and accommodation, and use user reviews
    only as a secondary signal.
13. Include source names and clickable URLs in the Sources section when the browser-search
    results provide identifiable URLs.

SOURCE PRIORITY:
- Weather: use the supplied Open-Meteo forecast as the primary structured weather dataset;
  use current web sources to cross-check important weather/road issues.
- Attractions/reviews: Tripadvisor, GetYourGuide and reputable local tourism sources.
- Hotels: Tripadvisor, Wego, Booking.com, Agoda, Google travel/search results,
  and reputable local platforms where available.
- Local issues: official government/tourism/road authorities and reputable news.
- Transport: official operator sources where available.

IMPORTANT:
Return the answer in Markdown with these headings:
## Executive recommendation
## Route and travel strategy
## Day-by-day itinerary
## Top sights
## Hotels / stays
## Weather and what to pack
## Family / elderly / accessibility advice
## Local issues and precautions
## Booking and verification checklist
## Sources

Do not claim guaranteed availability, live traffic, exact booking prices, or confirmed closures
unless the browser-search evidence supports the claim.
"""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            reasoning_effort="low",
            max_completion_tokens=7000,
            tool_choice="required",
            tools=[
                {
                    "type": "browser_search"
                }
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        return (
            "### Groq research could not be completed\n\n"
            f"**Error:** `{type(e).__name__}: {e}`\n\n"
            "Please check the Groq API key, GPT-OSS 120B access, and Streamlit logs. "
            "Your route and weather information are still available above."
        )


# ----------------------------- UI -----------------------------

st.markdown(
    f"""
    <div class="hero">
        <h1>🧭 {APP_NAME}</h1>
        <p>AI-assisted route planning, weather-aware travel advice, sights, stays and family guidance — powered by GPT-OSS 120B + Groq Browser Search.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div style="
        padding:0.85rem 1rem;
        border-radius:12px;
        background:#fff4cc;
        border:1px solid #e5c04a;
        margin-bottom:1rem;
        text-align:center;
        font-size:1.02rem;
    ">
        <strong>⚡ MODEL UPDATE: Groq Compound was decommissioned on 21 September 2026.</strong><br>
        <strong>TravelWise AI has migrated its AI research engine to OpenAI GPT-OSS 120B on Groq with built-in Browser Search.</strong>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Trip details")
    st.caption("This MVP is designed for a hackathon: simple inputs, real routing/weather data and live web research.")

    mode = st.radio("Travel mode", ["Private vehicle", "Public transport"])
    start_city = st.text_input("Starting city", "Islamabad, Pakistan")
    destination_city = st.text_input("Main destination", "Hunza, Pakistan")

    stop_count = st.number_input(
        "Number of intermediate stops",
        min_value=0,
        max_value=6,
        value=2,
        step=1,
        help="These are places you intend to visit/stay at before the main destination.",
    )

    stops = []
    for i in range(int(stop_count)):
        s = st.text_input(f"Stop {i+1}", value=["Naran, Pakistan", "Gilgit, Pakistan", "Skardu, Pakistan", "Murree, Pakistan", "Abbottabad, Pakistan", "Chitral, Pakistan"][i])
        if s.strip():
            stops.append(s.strip())

    return_city = st.text_input("Return/end city", start_city)
    departure = st.date_input("Departure date", date.today() + timedelta(days=2))
    departure_time = st.time_input("Departure time", datetime.now().replace(second=0, microsecond=0).time())
    return_date = st.date_input("Return date", date.today() + timedelta(days=8))
    return_time = st.time_input("Return time", datetime.now().replace(second=0, microsecond=0).time())

    st.subheader("Travel party")
    adults = st.number_input("Adults", 1, 20, 2)
    children = st.number_input("Children", 0, 20, 1)
    elderly = st.number_input("Elderly", 0, 20, 0)
    disabled = st.number_input("People needing accessibility support", 0, 20, 0)

    generate = st.button("🚀 Build my travel plan", type="primary", use_container_width=True)

if generate:
    if return_date < departure:
        st.error("Return date cannot be earlier than departure date.")
        st.stop()

    all_names = [start_city] + stops + [destination_city]
    if return_city.strip() and return_city.strip() not in all_names:
        all_names.append(return_city.strip())

    with st.status("Building your travel plan...", expanded=True) as status:
        st.write("1. Finding coordinates for your cities...")
        coords = geocode_many(all_names)

        missing = [x for x in all_names if not coords.get(x)]
        if missing:
            status.update(label="Could not locate all cities", state="error")
            st.error("Please check these city names: " + ", ".join(missing))
            st.stop()

        points = [
            {
                "name": city,
                "lat": coords[city]["latitude"],
                "lon": coords[city]["longitude"],
                "country": coords[city].get("country", ""),
            }
            for city in all_names
        ]

        st.write("2. Calculating the road route...")
        route = None
        if mode == "Private vehicle":
            route = osrm_trip(points)

        st.write("3. Collecting weather forecasts...")
        # Keep API calls small: weather for each unique destination/stop.
        weather_by_city = {}
        forecast_limit = departure + timedelta(days=15)
        weather_end = min(return_date, forecast_limit)
        for p in points:
            try:
                rows = weather_forecast(
                    p["lat"], p["lon"], departure, weather_end
                )
                risk_score, risk_text = weather_risk(rows)
                weather_by_city[p["name"]] = {
                    "forecast": rows,
                    "risk_score": risk_score,
                    "risk_text": risk_text,
                }
            except Exception as e:
                weather_by_city[p["name"]] = {
                    "forecast": [],
                    "risk_score": None,
                    "risk_text": f"Weather unavailable: {e}",
                }

        st.write("4. Asking GPT-OSS 120B on Groq to research current travel information...")
        trip = {
            "points": points,
            "departure": f"{departure.isoformat()} {departure_time.strftime('%H:%M')}",
            "return": f"{return_date.isoformat()} {return_time.strftime('%H:%M')}",
            "mode": mode,
            "adults": int(adults),
            "children": int(children),
            "elderly": int(elderly),
            "disabled": int(disabled),
        }

        weather_summary = {}
        for city, obj in weather_by_city.items():
            weather_summary[city] = {
                "risk": obj["risk_text"],
                "forecast": [
                    {
                        "date": x["date"],
                        "condition": weather_label(x["weather_code"]),
                        "min_c": x["min_c"],
                        "max_c": x["max_c"],
                        "rain_pct": x["rain_pct"],
                        "rain_mm": x["rain_mm"],
                        "wind_kmh": x["wind_kmh"],
                        "uv": x["uv"],
                    }
                    for x in obj["forecast"]
                ],
            }

        research = research_with_groq(trip, weather_summary)
        status.update(label="Travel plan ready", state="complete")

    # Save in session so reruns don't erase the output.
    st.session_state["trip"] = trip
    st.session_state["route"] = route
    st.session_state["weather"] = weather_by_city
    st.session_state["research"] = research


# ----------------------------- results -----------------------------

if "trip" not in st.session_state:
    st.info("Enter your trip details in the sidebar and click **Build my travel plan**.")
    st.markdown(
        """
        ### What this MVP does
        - 📍 Geocodes cities automatically.
        - 🚗 Optimizes intermediate road stops for private-vehicle trips.
        - 🌦️ Provides structured near-term weather information.
        - 🤖 Uses OpenAI GPT-OSS 120B on Groq with built-in Browser Search for live web research.
        - 🏨 Researches hotels, sights, local issues and family/accessibility advice.
        - 🗺️ Displays the route on an interactive map.

        **Hackathon note:** This is an MVP. Hotel availability/booking, live traffic,
        public-transit ticketing and emergency services should be added in a later version.
        """
    )
    st.stop()

trip = st.session_state["trip"]
route = st.session_state["route"]
weather_by_city = st.session_state["weather"]
research = st.session_state["research"]

st.header("Your personalized travel plan")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Travel mode", trip["mode"])
c2.metric("Adults", trip["adults"])
c3.metric("Children", trip["children"])
c4.metric("Trip days", (return_date - departure).days + 1 if "return_date" in globals() else "—")

if route:
    st.subheader("🗺️ Optimized road route")
    r1, r2, r3 = st.columns(3)
    r1.metric("Road distance", f"{route['distance_km']:.0f} km")
    r2.metric("Estimated driving time", f"{route['duration_h']:.1f} h")
    r3.metric("Stops", str(len(route["ordered_points"]) - 2))

    order = " → ".join(p["name"] for p in route["ordered_points"])
    st.success(f"Suggested stop order: **{order}**")

    m = draw_map(route, route["ordered_points"])
    st_folium(m, use_container_width=True, height=500)

    st.caption(
        "Routing uses OpenStreetMap/OSRM road data. It is a planning aid, not live navigation; "
        "verify road closures and traffic before departure."
    )
else:
    st.subheader("🚌 Public-transport strategy")
    st.info(
        "For public transport the MVP uses live web research rather than pretending to have "
        "real-time train/bus schedules. Check the operator before booking."
    )

st.subheader("🌦️ Weather dashboard")
forecast_available = departure <= date.today() + timedelta(days=16)
if not forecast_available:
    st.warning(
        "The structured weather forecast is only shown for the near-term forecast window. "
        "For a trip farther in the future, use the research section for seasonal guidance "
        "and re-check the forecast shortly before departure."
    )

for city, obj in weather_by_city.items():
    with st.expander(f"{city} — {obj['risk_text']}", expanded=False):
        rows = obj["forecast"]
        if not rows:
            st.write("No structured forecast available.")
        else:
            for x in rows:
                st.write(
                    f"**{x['date']}** — {weather_label(x['weather_code'])}; "
                    f"{x['min_c']}–{x['max_c']} °C; rain probability {x['rain_pct']}%; "
                    f"rain {x['rain_mm']} mm; wind up to {x['wind_kmh']} km/h; UV {x['uv']}."
                )

st.subheader("🤖 AI travel research — GPT-OSS 120B + Groq Browser Search")
st.markdown(research)

st.divider()
st.caption(
    "TravelWise AI is a hackathon prototype. Information from web sources can change. "
    "Always verify weather warnings, road conditions, hotel availability, prices, opening hours, "
    "transport schedules and official travel advisories before traveling."
)
