import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="EUR/USD Sentinelle", layout="wide", page_icon="🛡️")

# --- FONCTION DE RECUPERATION ROBUSTE ---
@st.cache_data(ttl=3600*12)
def get_safe_data():
    # 1. VALEURS DE SECOURS (Mises à jour Février 2026 - ou actuelles)
    # Si tout le reste échoue, l'appli utilisera ça pour ne pas planter.
    # Tu peux modifier ces valeurs manuellement ici si besoin.
    data = {
        "fed_rate": 5.50, # Taux actuel approx
        "ecb_rate": 4.50, # Taux actuel approx
        "us_cpi": 3.4,
        "eu_cpi": 2.8,
        "source": "Backup (Mode Manuel)"
    }
    
    # 2. TENTATIVE SCRAPING INTELLIGENT (WIKIPEDIA)
    # On utilise un User-Agent pour passer pour un navigateur
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        # --- Taux Directeurs ---
        url_rates = "https://en.wikipedia.org/wiki/List_of_countries_by_central_bank_interest_rates"
        tables = pd.read_html(requests.get(url_rates, headers=headers).text)
        
        # On cherche le tableau qui contient "United States"
        for df in tables:
            if "United States" in str(df.iloc[:, 0].values):
                # On nettoie les données
                us_row = df[df.iloc[:, 0].str.contains("United States", na=False)].iloc[0]
                eu_row = df[df.iloc[:, 0].str.contains("Euro area", na=False)].iloc[0]
                
                # On cherche la première colonne qui contient un chiffre avec un %
                # C'est plus robuste que de dire "colonne 2"
                for col_idx in range(1, len(df.columns)):
                    val = str(us_row.iloc[col_idx])
                    if "%" in val:
                        data["fed_rate"] = float(val.replace('%', '').replace('−', '-').split('[')[0])
                        data["ecb_rate"] = float(str(eu_row.iloc[col_idx]).replace('%', '').replace('−', '-').split('[')[0])
                        data["source"] = "Wikipedia Live"
                        break
                break

        # --- Inflation ---
        url_cpi = "https://en.wikipedia.org/wiki/List_of_countries_by_inflation_rate"
        tables_cpi = pd.read_html(requests.get(url_cpi, headers=headers).text)
        
        for df in tables_cpi:
            if "United States" in str(df.iloc[:, 0].values):
                 us_row = df[df.iloc[:, 0].str.contains("United States", na=False)].iloc[0]
                 eu_row = df[df.iloc[:, 0].str.contains("Euro area", na=False)].iloc[0]
                 
                 # Recherche colonne inflation
                 for col_idx in range(1, len(df.columns)):
                    val = str(us_row.iloc[col_idx])
                    if "." in val or "%" in val: # Cherche un chiffre
                        try:
                            clean_val = float(val.replace('%', '').replace('−', '-').split('[')[0])
                            if 0 < clean_val < 50: # Check de cohérence
                                data["us_cpi"] = clean_val
                                data["eu_cpi"] = float(str(eu_row.iloc[col_idx]).replace('%', '').replace('−', '-').split('[')[0])
                                break
                        except:
                            continue
                 break

    except Exception as e:
        # En cas d'erreur, on ne fait RIEN. On garde les valeurs de secours.
        print(f"Erreur scraping: {e}")
        pass

    return data

# --- RECUPERATION YIELD (YAHOO - TRES ROBUSTE) ---
def get_market_sentiment():
    try:
        # TNX = 10 Year Treasury Yield
        ticker = yf.Ticker("^TNX")
        hist = ticker.history(period="5d")
        current = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        change = current - prev
        return current, change
    except:
        return 4.0, 0.0

# --- MAIN APP ---

macro_data = get_safe_data()
us_10y, us_10y_change = get_market_sentiment()

# SIDEBAR (Toujours modifiable)
st.sidebar.header("🔧 Réglages")
st.sidebar.caption(f"Source actuelle : {macro_data['source']}")
input_fed = st.sidebar.number_input("Taux FED", value=macro_data['fed_rate'])
input_ecb = st.sidebar.number_input("Taux BCE", value=macro_data['ecb_rate'])
input_us_cpi = st.sidebar.number_input("CPI US", value=macro_data['us_cpi'])
input_eu_cpi = st.sidebar.number_input("CPI EU", value=macro_data['eu_cpi'])

# LOGIQUE DE DECISION
score = 0
reasons = []

# 1. Taux
spread = input_fed - input_ecb
if spread > 1.0: 
    score -= 2
    reasons.append("Taux: Gros avantage Dollar (Spread > 1%)")
elif spread < 0: 
    score += 2
    reasons.append("Taux: Avantage Euro")

# 2. Yields (Dynamique)
if us_10y_change > 0.04:
    score -= 3 # Le marché a peur, il achète du dollar
    reasons.append("⚠️ ALERTE: Les taux US montent fort aujourd'hui (Vente EURUSD)")
elif us_10y_change < -0.04:
    score += 3
    reasons.append("✅ SIGNAL: Les taux US chutent (Achat EURUSD)")

# 3. Inflation
if input_us_cpi > input_eu_cpi:
    score -= 1
else:
    score += 1

# INTERFACE
st.title("🛡️ EUR/USD : Sentinelle Macro")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Taux FED vs BCE", f"{input_fed}% / {input_ecb}%", f"Ecart: {spread:.2f}%")
with c2:
    st.metric("US 10Y Yield (Sentiment)", f"{us_10y:.2f}%", f"{us_10y_change:.3f}")
with c3:
    if score < 0:
        st.error(f"📉 BIAIS : VENDEUR ({score})")
    elif score > 0:
        st.success(f"📈 BIAIS : ACHETEUR (+{score})")
    else:
        st.info("⚖️ BIAIS : NEUTRE")

# GRAPHIQUE
st.markdown("---")
df = yf.download("EURUSD=X", period="3mo", interval="1d", progress=False)
fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
fig.update_layout(title="EUR/USD (Daily)", height=400, template="plotly_dark")

# Ajout d'une ligne de tendance automatique (MM20)
fig.add_trace(go.Scatter(x=df.index, y=df['Close'].rolling(20).mean(), line=dict(color='orange'), name='MM 20'))

st.plotly_chart(fig, use_container_width=True)

st.subheader("📝 Pourquoi ?")
for r in reasons:
    st.write(f"- {r}")
