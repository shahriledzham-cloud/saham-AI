import streamlit as st
import yfinance as yf
import mplfinance as mpf
import google.generativeai as genai
from PIL import Image
import io
import pandas as pd
from fpdf import FPDF
import tempfile
from datetime import datetime # <--- KIT TOOL BARU (Untuk masa)

# --- SETUP HALAMAN ---
st.set_page_config(page_title="Smart Chart AI by SEJ", layout="wide")

# ==========================================
# 🔒 SISTEM LOGIN (GATEKEEPER)
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def check_login():
    st.title("🔒 Login Diperlukan")
    st.markdown("Sila masukkan ID Pengguna untuk akses sistem.")

    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Masuk Sistem 🚀"):
            users_db = st.secrets.get("passwords", {})
            if username in users_db and users_db[username] == password:
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.rerun()
            else:
                st.error("❌ Username atau Password salah!")

if not st.session_state.logged_in:
    check_login()
    st.stop()

# ==========================================
# 🔓 APLIKASI UTAMA
# ==========================================

# --- FUNGSI BUAT PDF (UPDATED) ---
def create_pdf(ticker, company_name, price, analysis_text, chart_image):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Header (Tajuk)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=f"Laporan Analisis Saham: {ticker}", ln=True, align='C')
    
    # 2. Sub-Header (Info Syarikat & Harga)
    pdf.set_font("Arial", 'I', 12)
    pdf.cell(0, 8, txt=f"Syarikat: {company_name} | Harga Terkini: RM {price}", ln=True, align='C')
    
    # 3. TARIKH & MASA (BARU!) 🕒
    current_time = datetime.now().strftime("%d/%m/%Y %I:%M %p") # Format: 24/12/2025 02:30 PM
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(100, 100, 100) # Warna kelabu sikit
    pdf.cell(0, 8, txt=f"Dijana pada: {current_time}", ln=True, align='C')
    pdf.set_text_color(0, 0, 0) # Reset warna hitam
    pdf.ln(5)
    
    # 4. Masukkan Gambar Chart
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
        chart_image.save(tmp_file.name)
        # Center image: (A4 width 210mm - image width 180mm) / 2 = 15mm margin
        pdf.image(tmp_file.name, x=15, y=pdf.get_y(), w=180)
    
    # Pindah cursor ke bawah gambar (agak-agak tinggi gambar)
    pdf.ln(105) 
    
    # 5. Masukkan Teks Analisis
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="Ulasan & Strategi AI:", ln=True, align='L')
    pdf.set_font("Arial", size=11)
    
    # Bersihkan teks untuk PDF
    clean_text = analysis_text.replace("*", "").replace("#", "")
    clean_text = clean_text.encode('latin-1', 'replace').decode('latin-1')
    
    pdf.multi_cell(0, 6, txt=clean_text)
    
    return pdf.output(dest='S').encode('latin-1')

# --- HEADER & SIDEBAR ---
current_user = st.session_state.get("current_user", "Tetamu")
st.sidebar.markdown(f"## 👤 Pengguna: **{current_user.upper()}**")
if st.sidebar.button("Log Keluar"):
    st.session_state.logged_in = False
    st.rerun()

st.sidebar.divider()
st.sidebar.title("⚙️ Tetapan")

# --- LOGIC AUTO-LOGIN ---
api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("✅ API Key Dikesan")
else:
    api_key = st.sidebar.text_input("Masukkan Google Gemini API Key", type="password")

# --- AUTO-DETECT MODEL ---
available_models = []
if api_key:
    try:
        genai.configure(api_key=api_key)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'vision' in m.name or 'flash' in m.name or 'pro' in m.name:
                    available_models.append(m.name)
    except Exception:
        pass
if not available_models: available_models = ["models/gemini-1.5-flash"]
selected_model = st.sidebar.selectbox("Pilih Model AI", available_models, index=0)

# --- PILIHAN PASARAN ---
st.sidebar.divider()
market_type = st.sidebar.radio("Pilih Pasaran:", ["🇺🇸 US Market", "🇲🇾 Bursa Malaysia", "🇮🇩 Indonesia"])
st.title("📈 Smart Chart AI (Pro)")
st.caption(f"Model: {selected_model} | Powered by SEJ")

# --- INPUT ---
col1, col2 = st.columns([1, 3])
bursa_mapping = {
    "MAYBANK": "1155", "PBBANK": "1295", "CIMB": "1023", "TENAGA": "5347",
    "PCHEM": "5183", "IHH": "5225", "CELCOMDIGI": "6947", "DIGI": "6947",
    "TOPGLOV": "7113", "GENTING": "3182", "SIME": "4197", "TM": "4863",
    "RHBBANK": "1066", "HONGLEONG": "1082", "MISC": "3816", "NESTLE": "4707",
    "MAXIS": "6012", "YINSON": "7293", "GAMUDA": "5398", "MRDIY": "5296",
    "INARI": "0166", "MYEG": "0138", "AIRASIA": "5099", "CAPITALA": "5099"
}

with col1:
    default_ticker = "5347" if "Malaysia" in market_type else "TSLA"
    st.info("💡 Tip: Taip NAMA atau NOMBOR.")
    raw_ticker = st.text_input("Simbol / Nama Saham", value=default_ticker).upper()
    period = st.selectbox("Tempoh Masa", ["3mo", "6mo", "1y"], index=1)
    analyze_btn = st.button("🚀 Analisa Penuh")

# --- LOGIC UTAMA ---
ticker = raw_ticker.strip()
if "Malaysia" in market_type:
    if ticker in bursa_mapping: ticker = bursa_mapping[ticker]
if "Malaysia" in market_type and not ticker.endswith(".KL"): ticker += ".KL"
elif "Indonesia" in market_type and not ticker.endswith(".JK"): ticker += ".JK"

# --- FUNGSI BANTUAN ---
def format_large_number(num):
    if num is None: return "Tiada Data"
    if num >= 1_000_000_000: return f"{num / 1_000_000_000:.2f}B"
    elif num >= 1_000_000: return f"{num / 1_000_000:.2f}M"
    return str(num)

if analyze_btn:
    if not api_key:
        st.error("⚠️ API Key tiada.")
    else:
        genai.configure(api_key=api_key)
        with st.spinner(f"Sedang mengumpul data {ticker}..."):
            try:
                ticker_obj = yf.Ticker(ticker)
                
                # 1. Fundamental
                info = ticker_obj.info
                company_name = info.get('longName', ticker)
                sector = info.get('sector', 'Tidak Diketahui')
                market_cap = format_large_number(info.get('marketCap'))
                pe_ratio = info.get('trailingPE', 'N/A')
                div_yield = info.get('dividendYield', 0)
                if div_yield: div_yield = f"{div_yield * 100:.2f}%"
                else: div_yield = "0%"
                
                st.info(f"🏢 **{company_name}** | Sektor: {sector}")
                m1, m2, m3 = st.columns(3)
                m1.metric("Market Cap", market_cap)
                m2.metric("PE Ratio", pe_ratio if pe_ratio != 'N/A' else "-")
                m3.metric("Dividend Yield", div_yield)

                # 2. Chart Data
                data = ticker_obj.history(period=period)
                if data.empty:
                    st.error(f"❌ Data Chart kosong untuk '{ticker}'.")
                else:
                    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
                    data.index.name = 'Date'
                    try: last_price = float(data['Close'].iloc[-1])
                    except: last_price = 0.0

                    # 3. Lukis Chart
                    m_style = mpf.make_mpf_style(base_mpf_style='yahoo', rc={'font.size': 10})
                    buf = io.BytesIO()
                    my_hlines = dict(hlines=[last_price], colors=['red'], linestyle='dashed', linewidths=1.0)
                    mpf.plot(data, type='candle', style=m_style, volume=True, mav=(20, 50),
                        hlines=my_hlines, savefig=dict(fname=buf, dpi=300, bbox_inches='tight'),
                        title=f"\n{ticker} - Price: {last_price:.2f}", tight_layout=True)
                    buf.seek(0)
                    image = Image.open(buf)
                    
                    with col2:
                        st.image(image, use_container_width=True, caption=f"Carta Harian: {company_name}")
                    
                    # 4. AI Analysis
                    with st.spinner(f"🤖 AI sedang menulis laporan..."):
                        model = genai.GenerativeModel(selected_model)
                        prompt = f"""
                        Bertindak sebagai Pengurus Dana Professional.
                        
                        DATA FUNDAMENTAL:
                        - Nama: {company_name} | Sektor: {sector}
                        - Market Cap: {market_cap} | PE Ratio: {pe_ratio} | Dividen: {div_yield}

                        DATA TEKNIKAL:
                        - Harga Semasa: {last_price:.2f}
                        - Biru = EMA 20, Oren = EMA 50.

                        Analisis dalam Bahasa Melayu:
                        1. **Fundamental**: Syarikat kukuh/mahal/murah?
                        2. **Teknikal**: Trend Uptrend/Downtrend?
                        3. **Plan**: Target Profit & Stop Loss.
                        4. **Keputusan**: BUY / SELL / WAIT?
                        """
                        response = model.generate_content([prompt, image])
                        
                        # Papar Analisis
                        with col2:
                            st.divider()
                            st.subheader("📊 Analisis Penuh:")
                            st.markdown(response.text)
                            
                            # --- BUTANG DOWNLOAD PDF ---
                            st.divider()
                            # Kita bagi info tarikh masa akan dijana dalam fungsi create_pdf
                            pdf_bytes = create_pdf(ticker, company_name, f"{last_price:.2f}", response.text, image)
                            
                            st.download_button(
                                label="📥 Download Laporan PDF",
                                data=pdf_bytes,
                                file_name=f"Analisis_{ticker}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf"
                            )

            except Exception as e:
                st.error(f"Ralat Sistem: {e}")