
import math
import streamlit as st

st.set_page_config(
    page_title="MatchLab",
    page_icon="⚽",
    layout="centered"
)

st.title("🏆 MatchLab")
st.caption("Analiza meczów i prawdopodobieństw")

st.info(
    "Wersja testowa. Wyniki zależą od ręcznie "
    "wprowadzonych przewidywań goli."
)

st.header("⚽ Analiza meczu")

gospodarze = st.text_input(
    "Drużyna gospodarzy",
    "Gospodarze"
)

goscie = st.text_input(
    "Drużyna gości",
    "Goście"
)

col1, col2 = st.columns(2)

with col1:
    gole_gospodarzy = st.number_input(
        "Oczekiwane gole gospodarzy",
        min_value=0.1,
        max_value=6.0,
        value=1.5,
        step=0.1
    )

with col2:
    gole_gosci = st.number_input(
        "Oczekiwane gole gości",
        min_value=0.1,
        max_value=6.0,
        value=1.0,
        step=0.1
    )


def poisson(lam, k):
    return math.exp(-lam) * lam**k / math.factorial(k)


def analizuj(lam_home, lam_away):
    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0
    wyniki = []

    for h in range(11):
        for a in range(11):
            p = poisson(lam_home, h) * poisson(lam_away, a)
            wyniki.append((p, h, a))

            if h > a:
                p_home += p
            elif h == a:
                p_draw += p
            else:
                p_away += p

    suma = p_home + p_draw + p_away

    return (
        p_home / suma,
        p_draw / suma,
        p_away / suma,
        wyniki
    )


if st.button("🔍 Analizuj mecz", type="primary"):
    ph, px, pa, wyniki = analizuj(
        gole_gospodarzy,
        gole_gosci
    )

    st.header("Prawdopodobieństwa")

    c1, c2, c3 = st.columns(3)

    c1.metric("1 — Gospodarze", f"{ph:.1%}")
    c2.metric("X — Remis", f"{px:.1%}")
    c3.metric("2 — Goście", f"{pa:.1%}")

    st.subheader("Kursy uczciwe")

    c1, c2, c3 = st.columns(3)

    c1.metric("Kurs 1", f"{1 / ph:.2f}")
    c2.metric("Kurs X", f"{1 / px:.2f}")
    c3.metric("Kurs 2", f"{1 / pa:.2f}")

    st.subheader("Najbardziej prawdopodobne wyniki")

    wyniki.sort(reverse=True)

    for p, h, a in wyniki[:5]:
        st.write(f"**{h}:{a}** — prawdopodobieństwo {p:.1%}")

    st.caption(
        "Model Poissona jest uproszczeniem. "
        "Nie uwzględnia jeszcze aktualnej formy, "
        "składów, kontuzji ani jakości przeciwników. "
        "Nie gwarantuje trafnych prognoz."
    )
