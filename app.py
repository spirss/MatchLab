
import math
import requests
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="MatchLab",
    page_icon="⚽",
    layout="wide"
)

API_URL = "https://api.football-data.org/v4"

LEAGUES = {
    "Premier League (Anglia)": "PL",
    "La Liga (Hiszpania)": "PD",
    "Bundesliga (Niemcy)": "BL1",
    "Serie A (Włochy)": "SA",
    "Ligue 1 (Francja)": "FL1",
    "Liga Mistrzów": "CL",
}

st.title("⚽ MatchLab")
st.caption("Analiza meczów piłkarskich oparta na wynikach i statystykach.")

def get_token():
    try:
        return st.secrets["FOOTBALL_DATA_TOKEN"]
    except Exception:
        return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_matches(competition_code, token):
    response = requests.get(
        f"{API_URL}/competitions/{competition_code}/matches",
        headers={"X-Auth-Token": token},
        timeout=20
    )
    if response.status_code == 401:
        raise ValueError("API nie zaakceptowało klucza. Sprawdź Secrets w Streamlit.")
    if response.status_code == 403:
        raise ValueError(
            "Twoje konto API nie ma dostępu do tych rozgrywek. "
            "Spróbuj wybrać inną ligę."
        )
    if response.status_code == 429:
        raise ValueError(
            "Osiągnięto limit zapytań API. Poczekaj chwilę i spróbuj ponownie."
        )
    if response.status_code != 200:
        raise ValueError(
            f"API zwróciło błąd {response.status_code}: "
            f"{response.text[:250]}"
        )
    return response.json().get("matches", [])

def poisson(mean, goals):
    if mean <= 0:
        return 1.0 if goals == 0 else 0.0
    return math.exp(-mean) * mean ** goals / math.factorial(goals)

def make_prediction(matches, home_team, away_team):
    finished = [
        m for m in matches
        if m.get("status") == "FINISHED"
        and m.get("score", {}).get("fullTime", {}).get("home") is not None
        and m.get("score", {}).get("fullTime", {}).get("away") is not None
    ]

    if len(finished) < 10:
        raise ValueError(
            "Za mało zakończonych spotkań w dostępnych danych, "
            "aby przygotować sensowną analizę."
        )

    home_goals = [
        m["score"]["fullTime"]["home"] for m in finished
    ]
    away_goals = [
        m["score"]["fullTime"]["away"] for m in finished
    ]

    avg_home = sum(home_goals) / len(home_goals)
    avg_away = sum(away_goals) / len(away_goals)

    def team_stats(team):
        home_games = [
            m for m in finished if m["homeTeam"]["name"] == team
        ]
        away_games = [
            m for m in finished if m["awayTeam"]["name"] == team
        ]

        # Mała liczba spotkań oznacza większą niepewność.
        # Wtedy model korzysta z wartości średnich ligi.
        home_scored = (
            sum(m["score"]["fullTime"]["home"] for m in home_games)
            / len(home_games) if home_games else avg_home
        )
        home_conceded = (
            sum(m["score"]["fullTime"]["away"] for m in home_games)
            / len(home_games) if home_games else avg_away
        )
        away_scored = (
            sum(m["score"]["fullTime"]["away"] for m in away_games)
            / len(away_games) if away_games else avg_away
        )
        away_conceded = (
            sum(m["score"]["fullTime"]["home"] for m in away_games)
            / len(away_games) if away_games else avg_home
        )

        return {
            "home_scored": home_scored,
            "home_conceded": home_conceded,
            "away_scored": away_scored,
            "away_conceded": away_conceded,
            "home_games": len(home_games),
            "away_games": len(away_games),
        }

    h = team_stats(home_team)
    a = team_stats(away_team)

    # Siła ataku i obrony na podstawie wyników sezonu.
    # Współczynniki są ograniczone, aby uniknąć skrajnych prognoz.
    def clamp(value, low=0.5, high=1.8):
        return max(low, min(high, value))

    home_attack = clamp(h["home_scored"] / max(avg_home, 0.1))
    home_defence = clamp(h["home_conceded"] / max(avg_away, 0.1))
    away_attack = clamp(a["away_scored"] / max(avg_away, 0.1))
    away_defence = clamp(a["away_conceded"] / max(avg_home, 0.1))

    expected_home = max(
        0.1, min(5.0, avg_home * home_attack * away_defence)
    )
    expected_away = max(
        0.1, min(5.0, avg_away * away_attack * home_defence)
    )

    home_win = draw = away_win = 0.0
    scorelines = []

    for hg in range(9):
        for ag in range(9):
            probability = poisson(expected_home, hg) * poisson(expected_away, ag)
            scorelines.append((hg, ag, probability))
            if hg > ag:
                home_win += probability
            elif hg == ag:
                draw += probability
            else:
                away_win += probability

    total = home_win + draw + away_win
    return {
        "expected_home": expected_home,
        "expected_away": expected_away,
        "home_win": home_win / total,
        "draw": draw / total,
        "away_win": away_win / total,
        "scores": sorted(scorelines, key=lambda x: x[2], reverse=True)[:5],
        "home_games": h["home_games"],
        "away_games": a["away_games"],
        "matches_used": len(finished),
    }

token = get_token()

if not token:
    st.error(
        "Brak klucza API. W Streamlit otwórz Settings → Secrets "
        "i dodaj FOOTBALL_DATA_TOKEN."
    )
    st.stop()

st.info(
    "Dane dotyczą rozgrywek dostępnych w Twoim planie API. "
    "Prognozy są szacunkami statystycznymi."
)

league_name = st.selectbox("Wybierz ligę", list(LEAGUES.keys()))
league_code = LEAGUES[league_name]

if st.button("Pobierz mecze i analizuj", type="primary"):
    try:
        with st.spinner("Pobieram dane z API..."):
            matches = fetch_matches(league_code, token)

        if not matches:
            st.warning(
                "API nie zwróciło meczów dla tych rozgrywek. "
                "Może to być ograniczenie planu lub dostępności sezonu."
            )
            st.stop()

        st.session_state["matches"] = matches
        st.session_state["league_code"] = league_code
        st.session_state["league_name"] = league_name
        st.success(f"Pobrano {len(matches)} spotkań.")

    except Exception as e:
        st.error(str(e))

if (
    "matches" in st.session_state
    and st.session_state.get("league_code") == league_code
):
    matches = st.session_state["matches"]

    teams = sorted({
        team.get("name")
        for match in matches
        for team in (match.get("homeTeam", {}), match.get("awayTeam", {}))
        if team.get("name")
    })

    st.subheader("Wybierz spotkanie do analizy")

    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Gospodarze", teams, key="home_team")
    with col2:
        away_options = [team for team in teams if team != home_team]
        away_team = st.selectbox("Goście", away_options, key="away_team")

    upcoming = [
        m for m in matches
        if m.get("status") in ("SCHEDULED", "TIMED")
    ]
    if upcoming:
        st.caption(f"W terminarzu znaleziono {len(upcoming)} przyszłych spotkań.")

    if st.button("Oblicz prawdopodobieństwa", type="primary"):
        try:
            with st.spinner("Analizuję zakończone mecze..."):
                result = make_prediction(matches, home_team, away_team)

            st.subheader(f"{home_team} — {away_team}")
            st.caption(
                f"Model wykorzystuje {result['matches_used']} zakończonych "
                f"meczów z dostępnego sezonu."
            )

            c1, c2 = st.columns(2)
            c1.metric("Oczekiwane gole gospodarzy", f"{result['expected_home']:.2f}")
            c2.metric("Oczekiwane gole gości", f"{result['expected_away']:.2f}")

            st.subheader("Prawdopodobieństwo 1X2")
            p1, px, p2 = st.columns(3)
            p1.metric("1 — wygrana gospodarzy", f"{result['home_win']:.1%}")
            px.metric("X — remis", f"{result['draw']:.1%}")
            p2.metric("2 — wygrana gości", f"{result['away_win']:.1%}")

            st.subheader("Najbardziej prawdopodobne wyniki")
            score_df = pd.DataFrame([
                {
                    "Wynik": f"{hg}:{ag}",
                    "Prawdopodobieństwo": f"{prob:.1%}"
                }
                for hg, ag, prob in result["scores"]
            ])
            st.dataframe(score_df, hide_index=True, use_container_width=True)

            st.caption(
                "To uproszczony model Poissona oparty na bramkach z bieżącego "
                "sezonu. Nie uwzględnia m.in. kontuzji, składów, xG ani siły "
                "przeciwników w pełnym zakresie. Nie jest gwarancją wyniku."
            )

        except Exception as e:
            st.error(str(e))
