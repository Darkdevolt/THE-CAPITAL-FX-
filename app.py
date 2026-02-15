import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

# --- CONFIGURATION ---
st.set_page_config(page_title="EUR/USD Auto-Dashboard", layout="wide")

# --- FONCTION DE SCRAPING (Le Moteur) ---
@st.cache_data(ttl=3600) # Cache les données pour 1 heure pour ne pas spammer
def get_macro_data():
    try:
        # 1. Scraper les Taux d'Intérêt (Wikipedia est très stable pour ça)
        url_rates = "https://en.wikipedia.org/wiki/List_of_countries_by_central_bank_interest_rates"
        tables_rates = pd.read_html(url_rates)
        df_rates = tables_rates[0] # Le premier tableau est généralement le bon
        
        # Nettoyage et recherche
        # On cherche "United States" et "Euro area"
        us_row = df_rates[df_rates.iloc[:, 0].str.contains("United States", case=False, na=False)].iloc[0]
        eu_row = df_rates[df_rates.iloc[:, 0].str.contains("Euro area", case=False, na=False)].iloc[0]
        
        fed_rate = float(str(us_row.iloc[2]).replace('%', '').replace('−', '-'))
        ecb_rate = float(str(eu_row.iloc[2]).replace('%', '').replace('−', '-'))

        # 2. Scraper l'Inflation (CPI)
        url_cpi = "https://en.wikipedia.org/wiki/List_of_countries_by_inflation_rate"
        tables_cpi = pd.read_html(url_cpi)
        df_cpi = tables_cpi[0] # Souvent le premier tableau

        # Note: La structure de wikipedia change parfois, on essaie de trouver les colonnes
        us_cpi_row = df_cpi[df_cpi.iloc[:, 0].str.contains("United States", case=False, na=False)].iloc[0]
        eu_cpi_row = df_cpi[df_cpi.iloc[:, 0].str.contains("Euro area", case=False, na=False)].iloc[0]

        # L'index de la colonne taux change parfois, on prend souvent la colonne 1 ou 2
        us_cpi = float(str(us_cpi_row.iloc[1]).replace('%', '').replace('−', '-'))
        eu_cpi = float(str(eu_cpi_row.iloc[1]).replace('%', '').replace('−', '-'))
        
        return fed_rate, ecb_rate, us_cpi, eu_cpi, True

    except Exception as e:
        # Si le scraping échoue, on retourne des valeurs par défaut
        return 5.50, 4.00, 3.4, 2.9, False

# --- RECUPERATION DES DONNEES ---
fed_rate, ecb_rate, us_cpi, eu_cpi, scraping_success = get_macro_data()

# Récupération Yields (Obligations) pour le sentiment
tickers = yf.tickers.Tickers("^TNX ^FVX EURUSD=X") # TNX = 10 ans US
try:
    tnx_data = yf.download("^TNX", period="5d", progress=False)['Close']
    us_10y_current = tnx_data.iloc[-1].item()
    us_10y_prev = tnx_data.iloc[-2].item()
    delta_yield = us_10y_current - us_10y_prev
except:
    us_10y_current = 4.0
    delta_yield = 0

# --- INTERFACE UTILISATEUR ---

st.title("🤖 EUR/USD : Auto-Pilote Fondamental")
st.markdown("---")

if scraping_success:
    st.toast("Données Macro mises à jour automatiquement !", icon="✅")
else:
    st.warning("⚠️ Le scraping a échoué. Valeurs par défaut utilisées. Vérifie ta connexion.")

# SIDEBAR (Juste pour vérifier, mais tout est auto)
st.sidebar.header("Données en Direct")
st.sidebar.metric("Taux FED (USA)", f"{fed_rate}%")
st.sidebar.metric("Taux BCE (EU)", f"{ecb_rate}%")
st.sidebar.markdown("---")
st.sidebar.metric("Inflation USA", f"{us_cpi}%")
st.sidebar.metric("Inflation EU", f"{eu_cpi}%")

# --- ALGORITHME DE DECISION ---

# Calcul Spread
spread_rate = fed_rate - ecb_rate
spread_cpi = us_cpi - eu_cpi

# Calcul Sentiment via Bond Yields (Si le taux 10 ans monte, le Dollar monte)
sentiment_score = 0
if delta_yield > 0.05:
    sentiment_txt = "Yields US en Hausse (Pro-USD)"
    sentiment_score = -2
elif delta_yield < -0.05:
    sentiment_txt = "Yields US en Baisse (Anti-USD)"
    sentiment_score = 2
else:
    sentiment_txt = "Yields Stables"
    sentiment_score = 0

# Scoring Total
score = 0
# Taux
if spread_rate > 1.0: score -= 3
elif spread_rate > 0: score -= 1
else: score += 2
# Inflation
if us_cpi > eu_cpi: score -= 1 # Fed doit monter les taux -> USD fort
else: score += 1
# Sentiment
score += sentiment_score

# --- AFFICHAGE DU DASHBOARD ---

c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("Biais Directionnel")
    if score < 0:
        st.markdown(f"<h1 style='color: #FF4B4B;'>VENDRE (Short)</h1>", unsafe_allow_html=True)
        st.write(f"Score Macro: {score}/10")
    elif score > 0:
        st.markdown(f"<h1 style='color: #4CAF50;'>ACHETER (Long)</h1>", unsafe_allow_html=True)
        st.write(f"Score Macro: {score}/10")
    else:
        st.markdown(f"<h1 style='color: gray;'>NEUTRE</h1>", unsafe_allow_html=True)

with c2:
    st.subheader("Sentiment (Bonds US)")
    st.metric("US 10Y Yield", f"{us_10y_current:.2f}%", f"{delta_yield:.3f}")
    st.caption(sentiment_txt)

with c3:
    # Récup prix EURUSD
    df_price = yf.download("EURUSD=X", period="1y", interval="1d", progress=False)
    curr_price = df_price['Close'].iloc[-1].item()
    prev_close = df_price['Close'].iloc[-2].item()
    st.subheader("Prix EUR/USD")
    st.metric("Cours Actuel", f"{curr_price:.4f}", f"{curr_price-prev_close:.4f}")

# --- ANALYSE GRAPHIQUE ---
st.markdown("### 🔍 Analyse Croisée")

# Graphique
fig = go.Figure()
fig.add_trace(go.Candlestick(x=df_price.index,
                open=df_price['Open'], high=df_price['High'],
                low=df_price['Low'], close=df_price['Close'], name='EUR/USD'))

# Ajout d'une zone de couleur selon le biais
if score < 0:
    # Zone rouge légère en fond si biais vendeur
    fig.add_hrect(y0=curr_price, y1=curr_price*1.05, line_width=0, fillcolor="red", opacity=0.1, annotation_text="Zone de Vente (Résistance)")
elif score > 0:
    fig.add_hrect(y0=curr_price*0.95, y1=curr_price, line_width=0, fillcolor="green", opacity=0.1, annotation_text="Zone d'Achat (Support)")

fig.update_layout(height=450, template="plotly_dark", title="EUR/USD + Context Macro")
st.plotly_chart(fig, use_container_width=True)

# --- EXPLICATION LOGIQUE ---
st.info(f"""
**Pourquoi ce Biais ?**
1. **Spread de Taux :** L'écart est de {spread_rate:.2f}%. {'Avantage Dollar' if spread_rate > 0 else 'Avantage Euro'}.
2. **Sentiment (US 10Y) :** Les taux obligataires US sont à {us_10y_current:.2f}% ({sentiment_txt}).
3. **Inflation :** US ({us_cpi}%) vs EU ({eu_cpi}%).
""")
