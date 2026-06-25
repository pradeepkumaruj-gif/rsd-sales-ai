import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import sqlite3
from sqlalchemy import create_engine

# ═══════════════════════════════════════════════════
# CONFIG — Secrets se lo!
# ═══════════════════════════════════════════════════
API_KEY      = st.secrets["API_KEY"]
DATABASE_URL = st.secrets["DATABASE_URL"]

# ═══════════════════════════════════════════════════
# DATA LOAD
# ═══════════════════════════════════════════════════
@st.cache_data
def load_data():
    df = pd.read_csv("RSD 3.csv")
    df.columns       = df.columns.str.strip()
    df["TSE Name"]   = df["TSE Name"].str.strip()
    df["Party Name"] = df["Party Name"].str.strip()
    df["Dept."]      = df["Dept."].str.strip()
    return df

df = load_data()

# ═══════════════════════════════════════════════════
# DATABASE — SUPABASE YA SQLITE
# ═══════════════════════════════════════════════════
@st.cache_resource
def get_engine():
    try:
        engine  = create_engine(DATABASE_URL)
        df_temp = load_data()
        df_temp.to_sql("sales", engine,
                       if_exists="replace",
                       index=False)
        return engine, "supabase"
    except Exception:
        conn    = sqlite3.connect("rsd_business.db")
        df_temp = load_data()
        df_temp.to_sql("sales", conn,
                       if_exists="replace",
                       index=False)
        return conn, "sqlite"

db, db_type = get_engine()

# ═══════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════
products = [
    "Barent Qty",
    "Royal Ace Qty",
    "Dennis Gold Qty",
    "BL GA Qty",
    "BL Pure Qty",
    "CNC RUM Qty"
]

# ═══════════════════════════════════════════════════
# OUTPUTS
# ═══════════════════════════════════════════════════
_prod_totals = {p: int(df[p].sum()) for p in products}
_tse_series  = (df.groupby("TSE Name")[products]
                  .sum().sum(axis=1)
                  .sort_values(ascending=False))

outputs = {
    "total_records"  : len(df),
    "total_tse"      : df["TSE Name"].nunique(),
    "total_parties"  : df["Party Name"].nunique(),
    "months"         : df["Month"].unique().tolist(),
    "dept_list"      : df["Dept."].unique().tolist(),
    "best_product"   : max(_prod_totals, key=_prod_totals.get),
    "top_tse"        : _tse_series.index[0],
    "product_totals" : _prod_totals,
    "month_wise"     : (df.groupby("Month")[products]
                          .sum().sum(axis=1).to_dict()),
    "tse_wise"       : _tse_series.to_dict(),
    "dept_wise"      : (df.groupby("Dept.")[products]
                          .sum().sum(axis=1)
                          .sort_values(ascending=False)
                          .to_dict())
}

# ═══════════════════════════════════════════════════
# SEARCH FUNCTIONS
# ═══════════════════════════════════════════════════
def search_party(party_name):
    result = df[df["Party Name"].str.contains(
        party_name, case=False, na=False)]
    if result.empty:
        return f"❌ '{party_name}' nahi mila!"
    result = result.copy()
    result["Total"] = result[products].sum(axis=1)
    resp  = f"🏪 **{party_name.upper()}**\n\n"
    resp += f"- **TSE:** {', '.join(result['TSE Name'].unique())}\n"
    resp += f"- **Dept:** {', '.join(result['Dept.'].unique())}\n"
    resp += f"- **Months:** {', '.join(result['Month'].unique())}\n\n"
    resp += "**📦 Product Wise:**\n"
    for p in products:
        t = int(result[p].sum())
        if t > 0:
            resp += f"- {p}: **{t}**\n"
    resp += f"\n**Total Supply: {int(result['Total'].sum())}**"
    return resp

def search_tse(tse_name):
    result = df[df["TSE Name"].str.contains(
        tse_name, case=False, na=False)]
    if result.empty:
        return f"❌ '{tse_name}' nahi mila!"
    result = result.copy()
    result["Total"] = result[products].sum(axis=1)
    resp  = f"👨‍💼 **{tse_name.upper()}**\n\n"
    resp += f"- **Total Records:** {len(result)}\n"
    resp += f"- **Total Parties:** {result['Party Name'].nunique()}\n"
    resp += f"- **Months:** {', '.join(result['Month'].unique())}\n\n"
    resp += "**📦 Product Wise:**\n"
    for p in products:
        t = int(result[p].sum())
        if t > 0:
            resp += f"- {p}: **{t}**\n"
    resp += "\n**📅 Month Wise:**\n"
    for m, v in result.groupby("Month")["Total"].sum().items():
        resp += f"- {m}: **{int(v)}**\n"
    resp += f"\n**Grand Total: {int(result['Total'].sum())}**"
    return resp

# ═══════════════════════════════════════════════════
# CLAUDE FUNCTION
# ═══════════════════════════════════════════════════
def ask_claude(question):
    q = question.lower()

    # Smart routing — party search
    for party in df["Party Name"].unique():
        if party.lower() in q:
            return search_party(party)

    # Smart routing — TSE search
    for tse in df["TSE Name"].unique():
        if tse.lower() in q:
            return search_tse(tse)

    # Claude ko do
    summary = f"""
Mera RSD Sales Distribution Data:

OVERALL:
- Total Records  : {outputs['total_records']}
- Total TSE      : {outputs['total_tse']}
- Total Parties  : {outputs['total_parties']}
- Months         : {outputs['months']}
- Departments    : {outputs['dept_list']}

PRODUCT WISE TOTAL:
{outputs['product_totals']}

BEST PRODUCT : {outputs['best_product']}
TOP TSE      : {outputs['top_tse']}

MONTH WISE:
{outputs['month_wise']}

TSE WISE:
{outputs['tse_wise']}

DEPT WISE:
{outputs['dept_wise']}
"""
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type"      : "application/json",
                "x-api-key"         : API_KEY,
                "anthropic-version" : "2023-06-01"
            },
            json={
                "model"      : "claude-sonnet-4-6",
                "max_tokens" : 1000,
                "messages"   : [{
                    "role"   : "user",
                    "content": f"{summary}\n\nSawaal: {question}"
                }]
            }
        )
        result = response.json()
        if "content" in result:
            return result["content"][0]["text"]
        return "❌ Error aaya — dobara try karo!"
    except Exception:
        return "❌ Network error — check karo!"

# ═══════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════
st.set_page_config(
    page_title = "RSD Sales AI",
    page_icon  = "🤖",
    layout     = "centered"
)

st.markdown("""
    <h1 style='text-align:center; color:#6C63FF;'>
        🤖 RSD Sales AI Assistant
    </h1>
    <p style='text-align:center; color:gray;'>
        Koi bhi sawaal poochho — Hindi ya English mein!
    </p>
    <hr>
""", unsafe_allow_html=True)

# ── Stats ─────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("📊 Records",  outputs['total_records'])
c2.metric("👨‍💼 TSE",      outputs['total_tse'])
c3.metric("🏪 Parties",  outputs['total_parties'])
c4.metric("⭐ Top",      outputs['top_tse'].split()[0])

st.markdown("<hr>", unsafe_allow_html=True)

# ── Quick Buttons ─────────────────────────────────
st.markdown("**⚡ Quick Questions:**")
b1, b2, b3 = st.columns(3)

if b1.button("🏆 Best Product?"):
    st.info(f"**{outputs['best_product']}** — {outputs['product_totals'][outputs['best_product']]} units")

if b2.button("👑 Top TSE?"):
    st.info(f"**{outputs['top_tse']}** — {int(list(outputs['tse_wise'].values())[0])} units")

if b3.button("📅 Best Month?"):
    bm = max(outputs['month_wise'], key=outputs['month_wise'].get)
    st.info(f"**{bm}** — {outputs['month_wise'][bm]} units")

st.markdown("<hr>", unsafe_allow_html=True)

# ── Voice Input ───────────────────────────────────
st.markdown("**🎤 Voice Input:** *(Chrome mein best kaam karta hai!)*")

components.html("""
<script>
function startVoice() {
    if (!('webkitSpeechRecognition' in window)) {
        alert('Voice sirf Chrome mein kaam karta hai!');
        return;
    }
    var recognition = new webkitSpeechRecognition();
    recognition.lang = 'hi-IN';
    recognition.continuous = false;
    recognition.interimResults = false;

    var btn = document.getElementById('voiceBtn');
    btn.innerHTML = '🔴 Sun raha hoon...';
    btn.style.background = '#ff4444';

    recognition.onresult = function(event) {
        var text = event.results[0][0].transcript;
        document.getElementById('voiceText').value = text;
        btn.innerHTML = '🎤 Bolo';
        btn.style.background = '#6C63FF';

        var inputs = window.parent.document.querySelectorAll('input');
        inputs.forEach(function(input) {
            if (input.placeholder && input.placeholder.includes('Sawaal')) {
                var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.parent.HTMLInputElement.prototype, 'value').set;
                nativeInputValueSetter.call(input, text);
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        });
    };

    recognition.onerror = function() {
        btn.innerHTML = '🎤 Bolo';
        btn.style.background = '#6C63FF';
    };

    recognition.start();
}
</script>

<div style="display:flex; gap:12px; align-items:center; padding:5px;">
    <button id="voiceBtn" onclick="startVoice()" style="
        background:#6C63FF;
        color:white;
        border:none;
        padding:10px 22px;
        border-radius:25px;
        cursor:pointer;
        font-size:15px;
        font-weight:bold;
        box-shadow: 0 4px 10px rgba(108,99,255,0.3);
    ">🎤 Bolo</button>

    <input id="voiceText" type="text"
        placeholder="Voice text yahan dikhega..."
        style="
            padding:9px 14px;
            border-radius:20px;
            border:1px solid #ddd;
            width:280px;
            font-size:14px;
        " readonly/>
</div>
""", height=70)

st.markdown("<hr>", unsafe_allow_html=True)

# ── Chat ──────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role"   : "assistant",
        "content": """Namaste! 🙏 Main RSD Sales AI hoon!

Mujhse pooch sakte hain:
- 🏪 **Party/Location** — *"Mayur Vihar kaun supply karta hai?"*
- 👨‍💼 **TSE Performance** — *"Sunil Sharma ki performance?"*
- 📦 **Product** — *"Best product konsa hai?"*
- 📅 **Month** — *"Best month konsa raha?"*
- 🏢 **Department** — *"DTTDC ki total supply?"*
- 📊 **Strategy** — *"Next month kya karna chahiye?"*

Hindi ya English — koi bhi bhasha mein poochho! 😊"""
    })

for msg in st.session_state.messages:
    avatar = "🤖" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

if prompt := st.chat_input("Sawaal likho... (e.g. Mayur Vihar kaun supply karta hai?)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.write(prompt)
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Soch raha hoon... 🤔"):
            response = ask_claude(prompt)
            st.markdown(response)
            st.session_state.messages.append({
                "role": "assistant", "content": response
            })