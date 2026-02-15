import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
st.set_page_config(page_title="EUR/USD Pro Dashboard", layout="wide")

# --- FONCTION DE SCRAPING AVANCEE ---
@st.cache_data(ttl=12 * 3600)  # Cache 12h
def get_macro_data_robust():
    # Valeurs par défaut (si tout échoue)
    fed = 5.50
    ecb = 3.25
    us_cpi = 3.1
    eu_cpi = 2.6
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    status_log = []

    try:
        # TENTATIVE 1 : Scraper Global-Rates (souvent plus facile que Trading Economics)
        # On ne peut pas scraper TradingEconomics facilement car ils ont des protections Cloudflare.
        # On va utiliser une méthode hybride : Yahoo Finance pour les taux 10 ans (Sentiment) et valeurs fixes modifiables.
        
        # Pour cet exemple, on va simuler le scraping via Wikipedia avec le User-Agent (ce qui règle souvent le problème)
        url = "https://en.wikipedia.org/wiki/List_of_countries_by_central_bank_interest_rates"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            tables = pd.read_html(response.text)
            df = tables[0]
            
            # Nettoyage Fed
            us_row = df[df.iloc[:, 0].str.contains("United States", case=False, na=False)].iloc[0]
            fed = float(str(us_row.iloc[2]).replace('%', '').replace('−', '-').split('[')[0])
            
            # Nettoyage BCE
            eu_row = df[df.iloc[:, 0].str.contains("Euro area", case=False, na=False)].iloc[0]
            ecb = float(str(eu_row.iloc[2]).replace('%', '').replace('−', '-').split('[')[0])
            
            status_log.append("✅ Taux Central Bank récupérés via Wikipedia")
        else:
            status_log.append("⚠️ Echec connexion Wikipedia")

    except Exception as e:
        status_log.append(f"⚠️ Erreur Scraping Taux: {str(e)}")

    try:
        # TENTATIVE 2 : Inflation (CPI)
        url_cpi = "https://en.wikipedia.org/wiki/List_of_countries_by_inflation_rate"
        response_cpi = requests.get(url_cpi, headers=headers)
        if response_cpi.status_code == 200:
            df_cpi = pd.read_html(response_cpi.text)[0]
            
            # US CPI
            us_cpi_row = df_cpi[df_cpi.iloc[:, 0].str.contains("United States", case=False, na=False)].iloc[0]
            us_cpi = float(str(us_cpi_row.iloc[1]).replace('%', '').replace('−', '-').split('[')[0])
            
            # EU CPI
            eu_cpi_row = df_cpi[df_cpi.iloc[:, 0].str.contains("Euro area", case=False, na=False)].iloc[0]
            eu_cpi = float(str(eu_cpi_row.iloc[1]).replace('%', '').replace('−', '-').split('[')[0])
            
            status_log.append("✅ Inflation récupérée")
    except Exception as e:
        status_log.append(f"⚠️ Erreur Scraping Inflation: {str(e)}")

    return fed, ecb, us_cpi, eu_cpi, status_log

# --- RECUPERATION DES DONNEES ---

# 1. Macro (Scraping ou Défaut)
fed_rate, ecb_rate, us_cpi, eu_cpi, logs = get_macro_data_robust()

# 2. Yields (Obligations) via Yahoo (Très fiable)
try:
    bond_tickers = yf.Tickers("^TNX ^FVX") # TNX = 10 ans, FVX = 5 ans
    tnx_hist = bond_tickers.tickers["^TNX"].history(period="5d")
    us_10y = tnx_hist['Close'].iloc[-1]
    us_10y_prev = tnx_hist['Close'].iloc[-2]
    yield_delta = us_10y - us_10y_prev
except:
    us_10y = 4.0
    yield_delta = 0

# --- SIDEBAR INTELLIGENTE (MODE MANUEL SI BESOIN) ---
st.sidebar.title("🎛️ Panneau de Contrôle")
st.sidebar.markdown("Si le scraping échoue, corrige les valeurs ici.")

# On pré-remplit les inputs avec les valeurs scrapées
input_fed = st.sidebar.number_input("Taux FED (%)", value=fed_rate, step=0.25)
input_ecb = st.sidebar.number_input("Taux BCE (%)", value=ecb_rate, step=0.25)
input_us_cpi = st.sidebar.number_input("CPI US (%)", value=us_cpi, step=0.1)
input_eu_cpi = st.sidebar.number_input("CPI EU (%)", value=eu_cpi, step=0.1)

# Status Logs
with st.expander("Journal de connexion (Debug)"):
    for log in logs:
        st.write(log)

# --- LOGIQUE TRADING (LE CERVEAU) ---
# Spread Taux
spread = input_fed - input_ecb
# Spread Inflation
inf_spread = input_us_cpi - input_eu_cpi

score = 0
reasons = []

# 1. Analyse des Taux (Le plus important)
if spread > 1.25:
    score -= 3
    reasons.append("📉 L'écart de taux est énorme en faveur du Dollar (>1.25%).")
elif spread > 0.5:
    score -= 1
    reasons.append("📉 Les taux US sont supérieurs aux taux EU.")
elif spread < -0.5:
    score += 2
    reasons.append("📈 Les taux EU sont supérieurs, l'Euro devient attractif.")

# 2. Analyse des Obligations (Le sentiment immédiat)
if yield_delta > 0.03:
    score -= 2
    reasons.append("🔥 Les taux obligataires US (10 ans) montent fort aujourd'hui (Dollar Fort).")
elif yield_delta < -0.03:
    score += 2
    reasons.append("❄️ Les taux obligataires US se détendent (Dollar Faible).")

# 3. Analyse Inflation
if input_us_cpi > input_eu_cpi + 1:
    score -= 1
    reasons.append("⚠️ Inflation US plus forte : La FED gardera ses taux hauts.")

# --- INTERFACE VISUELLE ---

st.title("💶/💵 EURUSD : Techno-Fundamental Dashboard")

# Affichage du Biais
col_main, col_score = st.columns([2, 1])

with col_score:
    st.write("### Biais Actuel")
    if score <= -2:
        st.error(f"FORTEMENT VENDEUR ({score})")
    elif score < 0:
        st.warning(f"VENDEUR ({score})")
    elif score >= 2:
        st.success(f"FORTEMENT ACHETEUR (+{score})")
    elif score > 0:
        st.info(f"ACHETEUR (+{score})")
    else:
        st.write("NEUTRE / INCERTAIN")
    
    st.metric("Spread Taux (Fed-BCE)", f"{spread:.2f}%")
    st.metric("US 10Y Yield", f"{us_10y:.2f}%", f"{yield_delta:.3f}")

with col_main:
    # Graphique Technique
    data = yf.download("EURUSD=X", period="6mo", interval="1d", progress=False)
    fig = go.Figure()
    
    # Bougies
    fig.add_trace(go.Candlestick(x=data.index,
                    open=data['Open'], high=data['High'],
                    low=data['Low'], close=data['Close'], name='Prix'))
    
    # Moyenne Mobile 50 (Tendance court terme)
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'].rolling(50).mean(), line=dict(color='orange', width=1.5), name='MM 50'))
    
    # Zone de Biais
    last_price = data['Close'].iloc[-1].item()
    if score < 0:
        fig.add_hrect(y0=last_price, y1=last_price*1.02, fillcolor="red", opacity=0.1, annotation_text="Chercher Ventes")
    elif score > 0:
        fig.add_hrect(y0=last_price*0.98, y1=last_price, fillcolor="green", opacity=0.1, annotation_text="Chercher Achats")

    fig.update_layout(title="EURUSD Daily + MM50", height=400, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- PLAN D'ACTION ---
c1, c2 = st.columns(2)
with c1:
    st.subheader("🧠 Analyse Fondamentale")
    for r in reasons:
        st.write(f"- {r}")

with c2:
    st.subheader("⚔️ Exécution Technique")
    if score < 0:
        st.write("1. Attendre un rebond vers une résistance (ou la MM50).")
        st.write("2. Chercher un signal de retournement (Pinbar, Englobante) en H1/H4.")
        st.write("3. **Ne pas acheter** tant que le 10Y US Yield monte.")
    elif score > 0:
        st.write("1. Attendre un repli sur support.")
        st.write("2. Valider l'entrée si le Dollar Index (DXY) baisse.")
    else:
        st.write("Marché indécis. Privilégier le scalping sur les bornes de range (M15).")
