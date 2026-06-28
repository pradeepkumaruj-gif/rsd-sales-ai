import streamlit as st
import requests
import pandas as pd
import sqlite3
from sqlalchemy import create_engine

# ═══════════════════════════════════════════════════
# CONFIG
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
# DATABASE
# ═══════════════════════════════════════════════════
@st.cache_resource
def get_engine():
    try:
        engine  = create_engine(DATABASE_URL)
        df_temp = load_data()
        df_temp.to_sql("sales", engine, if_exists="replace", index=False)
        return engine, "supabase"
    except Exception:
        conn    = sqlite3.connect("rsd_business.db")
        df_temp = load_data()
        df_temp.to_sql("sales", conn, if_exists="replace", index=False)
        return conn, "sqlite"

db, db_type = get_engine()

# ═══════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════
products = [
    "Barent Qty", "Royal Ace Qty", "Dennis Gold Qty",
    "BL GA Qty", "BL Pure Qty", "CNC RUM Qty"
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
                          .sort_values(ascending=False).to_dict())
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

    for party in df["Party Name"].unique():
        if party.lower() in q:
            return search_party(party)

    for tse in df["TSE Name"].unique():
        if tse.lower() in q:
            return search_tse(tse)

    summary = f"""RSD Data: Records={outputs['total_records']}, TSE={outputs['total_tse']}, Parties={outputs['total_parties']}, Best={outputs['best_product']}, TopTSE={outputs['top_tse']}, Products={outputs['product_totals']}, Months={outputs['month_wise']}"""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type"      : "application/json",
                "x-api-key"         : API_KEY,
                "anthropic-version" : "2023-06-01"
            },
            json={
                "model"      : "claude-haiku-4-5-20251001",
                "max_tokens" : 400,
                "messages"   : [{
                    "role"   : "user",
                    "content": f"{summary}\n\nSawaal: {question}\n\nChhota clear jawab do."
                }]
            }
        )
        result = response.json()
        if "content" in result:
            return result["content"][0]["text"]
        return "❌ Error aaya!"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ═══════════════════════════════════════════════════
# PROCESS QUESTION
# ═══════════════════════════════════════════════════
def process_question(question):
    if not question or not question.strip():
        return
    st.session_state.messages.append({
        "role": "user", "content": question
    })
    with st.chat_message("user", avatar="👤"):
        st.write(question)
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Soch raha hoon... 🤔"):
            response = ask_claude(question)
            st.markdown(response)
            st.session_state.messages.append({
                "role": "assistant", "content": response
            })

# ═══════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════
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

Hindi ya English — koi bhi bhasha! 😊"""
    })

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

# ── Stats ──────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("📊 Records",  outputs['total_records'])
c2.metric("👨‍💼 TSE",      outputs['total_tse'])
c3.metric("🏪 Parties",  outputs['total_parties'])
c4.metric("⭐ Top",      outputs['top_tse'].split()[0])

st.markdown("<hr>", unsafe_allow_html=True)

# ── Quick Buttons ──────────────────────────────────
st.markdown("**⚡ Quick Questions:**")
b1, b2, b3 = st.columns(3)
if b1.button("🏆 Best Product?"):
    process_question("Best product konsa hai?")
if b2.button("👑 Top TSE?"):
    process_question("Top TSE kaun hai?")
if b3.button("📅 Best Month?"):
    process_question("Best month konsa raha?")

st.markdown("<hr>", unsafe_allow_html=True)

# ── Chat History ───────────────────────────────────
for msg in st.session_state.messages:
    avatar = "🤖" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ── Single Clean Chat Input ────────────────────────
if prompt := st.chat_input("Sawaal likho... Hindi ya English mein! 🤖"):
    process_question(prompt)