import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="EUR/USD Macro-Technical Dashboard", layout="wide")

st.title("💶/💵 EUR/USD : Analyse Techno-Fondamentale")
st.markdown("---")

# --- SIDEBAR : INPUTS FONDAMENTAUX ---
st.sidebar.header("1. Paramètres Macro-Éco")
st.sidebar.info("Mets à jour ces données chaque semaine ou lors des annonces (NFP/CPI/FOMC).")

# Taux d'intérêt (La base)
fed_rate = st.sidebar.number_input("Taux Directeur FED (%)", value=5.50, step=0.25)
ecb_rate = st.sidebar.number_input("Taux Directeur BCE (%)", value=4.00, step=0.25)

# Inflation (Le moteur)
us_cpi = st.sidebar.number_input("Inflation US (CPI) %", value=3.4, step=0.1)
eu_cpi = st.sidebar.number_input("Inflation EU (CPI) %", value=2.9, step=0.1)

# Sentiment (Le contexte)
st.sidebar.header("2. Sentiment de Marché")
market_mood = st.sidebar.selectbox(
    "Discours Banques Centrales (Sentiment)",
    ("Neutre", "FED Hawkish (Dollar Fort)", "FED Dovish (Dollar Faible)", "BCE Hawkish (Euro Fort)", "BCE Dovish (Euro Faible)")
)

# --- CALCUL DU BIAIS FONDAMENTAL ---
# Logique : L'argent va là où le taux réel est le plus élevé
rate_diff = fed_rate - ecb_rate  # Si positif, avantage USD
inflation_diff = us_cpi - eu_cpi # Si l'inflation US est plus haute, la FED risque de monter les taux (Avantage USD court terme)

# Scoring simple (-10 à +10)
# Négatif = Vente EURUSD / Positif = Achat EURUSD
macro_score = 0

# 1. Impact des Taux
if rate_diff > 1.0:
    macro_score -= 3 # Fort avantage USD
elif rate_diff > 0:
    macro_score -= 1
elif rate_diff < -1.0:
    macro_score += 3 # Fort avantage EUR
else:
    macro_score += 1

# 2. Impact Inflation (Simplifié)
if us_cpi > eu_cpi + 1:
    macro_score -= 1 # Pression sur la FED
elif eu_cpi > us_cpi + 1:
    macro_score += 1 # Pression sur la BCE

# 3. Impact Sentiment
if "FED Hawkish" in market_mood:
    macro_score -= 2
elif "FED Dovish" in market_mood:
    macro_score += 2
elif "BCE Hawkish" in market_mood:
    macro_score += 2
elif "BCE Dovish" in market_mood:
    macro_score -= 2

# --- RÉCUPÉRATION DONNÉES TECHNIQUES ---
@st.cache_data
def get_data():
    data = yf.download("EURUSD=X", period="1y", interval="1d")
    return data

df = get_data()
current_price = df['Close'].iloc[-1].item() # Correction pour extraire la valeur scalaire
prev_price = df['Close'].iloc[-2].item()
ma_200 = df['Close'].rolling(window=200).mean().iloc[-1].item()
ma_50 = df['Close'].rolling(window=50).mean().iloc[-1].item()

# --- AFFICHAGE PRINCIPAL ---

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Biais Fondamental")
    if macro_score < 0:
        st.error(f"📉 VENDEUR (Bearish) | Score: {macro_score}")
        bias_color = "red"
        bias_text = "Vente"
    elif macro_score > 0:
        st.success(f"📈 ACHETEUR (Bullish) | Score: {macro_score}")
        bias_color = "green"
        bias_text = "Achat"
    else:
        st.warning("⚖️ NEUTRE | Score: 0")
        bias_color = "gray"
        bias_text = "Neutre"

with col2:
    st.subheader("Prix Actuel")
    delta = round(current_price - prev_price, 4)
    st.metric("EUR/USD", f"{current_price:.4f}", f"{delta}")

with col3:
    st.subheader("Tendance Tech (MA200)")
    if current_price > ma_200:
        st.write("Au-dessus de la MA200 (Tendance Haussière)")
    else:
        st.write("En-dessous de la MA200 (Tendance Baissière)")

# --- LE "POURQUOI DU COMMENT" ---
st.markdown("### 🧠 L'Explication du Biais")
explanation = ""
if rate_diff > 0:
    explanation += f"- **Taux :** Les USA rémunèrent mieux ({fed_rate}%) que l'Europe ({ecb_rate}%), ce qui attire les capitaux vers le Dollar. \n"
else:
    explanation += f"- **Taux :** L'Europe rémunère mieux ({ecb_rate}%) que les USA ({fed_rate}%), avantage Euro. \n"

if "Hawkish" in market_mood:
    explanation += f"- **Sentiment :** Le discours actuel favorise des taux élevés, renforçant la monnaie concernée. \n"

st.info(explanation)

# --- GRAPHIQUE ---
st.markdown("### 📊 Analyse Graphique & Zones")
fig = go.Figure()
fig.add_trace(go.Candlestick(x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name='EUR/USD'))
fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(window=50).mean(), line=dict(color='orange', width=1), name='MA 50'))
fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(window=200).mean(), line=dict(color='blue', width=2), name='MA 200'))

fig.update_layout(height=500, xaxis_rangeslider_visible=False, template="plotly_dark")
st.plotly_chart(fig, use_container_width=True)

# --- RECOMMANDATION ACTIONNABLE ---
st.markdown("### 🎯 Plan de Trading Suggéré")
if bias_text == "Vente":
    st.write(f"⚠️ **Focus : SHORT.** Le fondamental indique un Dollar fort. Utilise ton analyse technique pour trouver des résistances ou des cassures de support. Évite d'acheter les creux.")
elif bias_text == "Achat":
    st.write(f"✅ **Focus : LONG.** Le fondamental indique un Euro fort (ou Dollar faible). Utilise ton analyse technique pour acheter les replis (Pullbacks).")
else:
    st.write("⏸️ **Focus : PRUDENCE.** Pas de direction claire. Scalping uniquement ou attendre une annonce éco.")
