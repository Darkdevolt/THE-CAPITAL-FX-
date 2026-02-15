import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

# --- CONFIGURATION ---
st.set_page_config(page_title="EUR/USD TradingEconomics", layout="wide", page_icon="🇪🇺🇺🇸")

# --- FONCTION DE SCRAPING (CIBLE: TRADING ECONOMICS) ---
@st.cache_data(ttl=3600)
def get_te_data():
    # On se fait passer pour un vrai navigateur Chrome
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    data = {
        "fed": 5.50, "ecb": 4.50, "us_cpi": 3.4, "eu_cpi": 2.8, # Valeurs par défaut si blocage
        "status": "⚠️ Mode Secours (TE a bloqué le script)"
    }

    try:
        # 1. RECUPERATION DES TAUX (Interest Rate Page)
        url_rates = "https://tradingeconomics.com/country-list/interest-rate"
        r = requests.get(url_rates, headers=headers, timeout=10)
        
        if r.status_code == 200:
            dfs = pd.read_html(r.text)
            df_rates = dfs[0] # Le tableau principal
            
            # On cherche USA et Euro Area
            # Trading Economics écrit parfois "United States" ou "USA"
            us_row = df_rates[df_rates.iloc[:,0].str.contains("United States", case=False, na=False)]
            eu_row = df_rates[df_rates.iloc[:,0].str.contains("Euro Area", case=False, na=False)]
            
            if not us_row.empty:
                data["fed"] = float(us_row.iloc[0, 1]) # Colonne 1 = Last
            if not eu_row.empty:
                data["ecb"] = float(eu_row.iloc[0, 1])
                
            data["status"] = "✅ Données Trading Economics (Taux)"

        # 2. RECUPERATION INFLATION (Inflation Rate Page)
        url_cpi = "https://tradingeconomics.com/country-list/inflation-rate"
        r_cpi = requests.get(url_cpi, headers=headers, timeout=10)
        
        if r_cpi.status_code == 200:
            dfs_cpi = pd.read_html(r_cpi.text)
            df_cpi = dfs_cpi[0]
            
            us_row = df_cpi[df_cpi.iloc[:,0].str.contains("United States", case=False, na=False)]
            eu_row = df_cpi[df_cpi.iloc[:,0].str.contains("Euro Area", case=False, na=False)]
            
            if not us_row.empty:
                data["us_cpi"] = float(us_row.iloc[0, 1])
            if not eu_row.empty:
                data["eu_cpi"] = float(eu_row.iloc[0, 1])
                
            data["status"] = "✅ Données Trading Economics (Complet)"

    except Exception as e:
        data["status"] = f"Erreur: {str(e)}"
    
    return data

# --- RECUPERATION MARKET DATA (YAHOO) ---
def get_market():
    # TNX = Taux 10 ans US
    tickers = yf.Tickers("EURUSD=X ^TNX")
    tnx = tickers.tickers["^TNX"].history(period="5d")
    eur = tickers.tickers["EURUSD=X"].history(period="1mo")
    
    us10y = tnx['Close'].iloc[-1]
    us10y_chg = us10y - tnx['Close'].iloc[-2]
    
    price = eur['Close'].iloc[-1]
    
    return us10y, us10y_chg, price, eur

# --- EXECUTION ---
macro = get_te_data()
us10y, us10y_chg, price, df_eur = get_market()

# --- INTERFACE ---
st.title("🇪🇺/🇺🇸 Dashboard Pro (Source: Trading Economics)")

# Affichage du statut de la connexion
if "✅" in macro["status"]:
    st.success(macro["status"])
else:
    st.warning(f"{macro['status']} -> Valeurs par défaut utilisées. (Trading Economics bloque souvent les robots)")

# SIDEBAR DE CONTROLE
st.sidebar.header("Données Macro")
fed = st.sidebar.number_input("🇺🇸 Taux FED", value=macro["fed"])
ecb = st.sidebar.number_input("🇪🇺 Taux BCE", value=macro["ecb"])
us_cpi = st.sidebar.number_input("🇺🇸 CPI (Inflation)", value=macro["us_cpi"])
eu_cpi = st.sidebar.number_input("🇪🇺 CPI (Inflation)", value=macro["eu_cpi"])

# LOGIQUE DE BIAIS
score = 0
rate_diff = fed - ecb
cpi_diff = us_cpi - eu_cpi

# 1. Taux
if rate_diff > 1.0: score -= 3 # USD très fort
elif rate_diff > 0.25: score -= 1
elif rate_diff < -0.25: score += 1
elif rate_diff < -1.0: score += 3 # EUR très fort

# 2. Dynamique Inflation (Si inflation US > EU, la Fed garde les taux hauts -> USD fort)
if cpi_diff > 1.0: score -= 1
elif cpi_diff < -1.0: score += 1

# 3. Sentiment (Yields)
if us10y_chg > 0.05: score -= 2
elif us10y_chg < -0.05: score += 2

# AFFICHAGE KPI
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Spread Taux (Fed - BCE)", f"{rate_diff:.2f}%")
with c2:
    st.metric("Spread Inflation (US - EU)", f"{cpi_diff:.2f}%")
with c3:
    st.metric("US 10Y Yield", f"{us10y:.2f}%", f"{us10y_chg:.3f}")

st.divider()

# DECISION
col_bias, col_chart = st.columns([1, 2])

with col_bias:
    st.subheader("Biais Directionnel")
    if score < 0:
        st.markdown("## 🔴 VENDRE (Short)")
        st.write("Le fondamental favorise le **DOLLAR**.")
        st.info("Cherche des résistances pour vendre.")
    elif score > 0:
        st.markdown("## 🟢 ACHETER (Long)")
        st.write("Le fondamental favorise l'**EURO**.")
        st.info("Cherche des supports pour acheter.")
    else:
        st.markdown("## ⚪ NEUTRE")
        st.write("Pas d'avantage clair.")

with col_chart:
    fig = go.Figure(data=[go.Candlestick(x=df_eur.index, open=df_eur['Open'], high=df_eur['High'], low=df_eur['Low'], close=df_eur['Close'])])
    fig.update_layout(title="EUR/USD (Dernier mois)", height=350, margin=dict(t=30, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)
