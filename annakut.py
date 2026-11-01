import html
import re

import pandas as pd
from streamlit_gsheets import GSheetsConnection
import streamlit as st
import streamlit.components.v1 as components
from st_keyup import st_keyup

st.set_page_config(page_title="Annakut", layout="centered", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- early white lock (runs BEFORE the PIN screen)
EARLY_CSS = """
<style>
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"] {
    background-color: #ffffff !important;
    color-scheme: light !important;
}
iframe {color-scheme: light !important; background-color: #ffffff !important;}
[data-baseweb="input"], [data-baseweb="base-input"], div[data-testid="stTextInput"] div {
    background-color: #ffffff !important;
    border-color: #e5e5ea !important;
}
input[type="text"], input[type="password"] {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    background-color: #ffffff !important;
    caret-color: #000000 !important;
}
.stButton button {background-color: #ffffff; color: #000000; border: 1px solid #e5e5ea;}
</style>
"""
st.markdown(EARLY_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------- security lock
if "authenticated" not in st.session_state:
    # Check if the URL has our secret persistent token
    if st.query_params.get("auth") == "1":
        st.session_state.authenticated = True
    else:
        st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<br><br><h3 style='text-align: center; color: #000; font-family: -apple-system, sans-serif;'>Enter PIN</h3>", unsafe_allow_html=True)
    pin = st.text_input("PIN", type="password", placeholder="Enter 4-digit PIN", label_visibility="collapsed")
    if st.button("Unlock", use_container_width=True):
        if pin == str(st.secrets.get("APP_PIN", "1008")):
            st.session_state.authenticated = True
            # Stamp the URL with the token so it survives Safari reloads
            st.query_params["auth"] = "1"
            st.rerun()
        else:
            st.error("Incorrect PIN")
    
    st.stop()

PAGES = {"MASTER": "MASTER LIST", "PENDING": "PENDING", "CALLBACK": "CALL-BACK"}
FILTERS = {"ALL": "ALL", "COMING": "COMING", "NOT COMING": "NOT_COMING",
           "DIDNT PICK UP": "DIDNT", "PENDING": "PENDING"}
STATUS_BG = {"PENDING": "#ffffff", "COMING": "#d4edda",
             "NOT COMING": "#f8d7da", "DIDNT PICK UP": "#fff3cd"}
ALIASES = {"PENDING": "PENDING", "ACCEPTED": "COMING", "COMING": "COMING",
           "REJECTED": "NOT COMING", "NOT COMING": "NOT COMING",
           "DIDNT PICK UP": "DIDNT PICK UP"}
PRINT_URL = "https://docs.google.com/spreadsheets/d/DUMMY_ID/export?format=pdf"

# ---------------------------------------------------------------- styling
CSS = """
<style>
#MainMenu, footer, header {visibility: hidden;}
*, *::before, *::after {box-sizing: border-box;}

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #ffffff !important;
    color-scheme: light;
    max-width: 100vw !important;
    overflow-x: hidden !important;
}
.block-container {
    padding: env(safe-area-inset-top, 0px) 0 0 0 !important;
    max-width: 100% !important;
    width: 100% !important;
    overflow-x: hidden !important;
}
[data-testid="stVerticalBlock"] {gap: 0 !important;}
[data-testid="stElementContainer"] {max-width: 100vw; width: 100% !important;}

/* hidden helpers */
[class*="st-key-pick_"] {display: none !important;}
[class*="st-key-pickin_"] {display: none !important;}
.st-key-injector {height: 0 !important; overflow: hidden; position: absolute;}

/* nav + filter bars: always one row, never stacked */
.st-key-nav [data-testid="stHorizontalBlock"],
.st-key-filters [data-testid="stHorizontalBlock"] {
    flex-direction: row !important; flex-wrap: nowrap !important;
    gap: 0 !important; width: 100% !important;
}
.st-key-nav [data-testid="stColumn"], .st-key-filters [data-testid="stColumn"],
.st-key-nav [data-testid="column"], .st-key-filters [data-testid="column"] {
    flex: 1 1 0 !important; min-width: 0 !important; width: auto !important;
}
.st-key-nav button, .st-key-filters button {
    width: 100%; min-height: 48px; padding: 0 2px; border-radius: 0;
    border: 1px solid #e5e5ea; background: #ffffff; color: #000000;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
}
.st-key-nav button p, .st-key-filters button p {
    margin: 0; font-size: 12px; font-weight: 700; color: #000000; white-space: nowrap;
}
.st-key-nav button:disabled, .st-key-filters button:disabled {
    background: #d1d1d6 !important; opacity: 1 !important;
}
.st-key-flt_COMING button {background: #d4edda;}
.st-key-flt_NOT_COMING button {background: #f8d7da;}
.st-key-flt_DIDNT button {background: #fff3cd;}
.st-key-search {padding: 8px 16px;}

/* stats banner */
.stats {
    display: flex; 
    width: 100%; 
    border-bottom: 1px solid #e5e5ea;
    margin-bottom: 8px; /* Pushes the first guest row down */
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
}
.stat {
    flex: 1 1 0; 
    min-width: 0; 
    padding: 16px 4px; /* Thicker vertical padding */
    min-height: 72px; /* Forces the box to stay tall */
    text-align: center; 
    color: #000;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.stat-n {
    font-size: 22px; 
    font-weight: 700; 
    line-height: 1.1;
}
.stat-l {
    font-size: 11px; 
    font-weight: 700; 
    margin-top: 4px;
    white-space: normal; /* Allows long text to safely drop to a second line */
    line-height: 1.1;
}

/* rows */
a.guest-link, a.guest-link:visited, a.guest-link:hover {
    display: block; text-decoration: none !important; color: inherit !important;
    -webkit-tap-highlight-color: rgba(0, 0, 0, 0.06);
}
.guest-row {
    display: flex; align-items: center; width: 100%; padding: 14px 16px;
    background-color: #ffffff; border-bottom: 1px solid #e5e5ea;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
}
.guest-sr {
    flex: 0 0 auto; min-width: 30px; margin-right: 6px; font-size: 17px; font-weight: 400;
    color: #000000; font-variant-numeric: tabular-nums;
}
.guest-name {
    flex: 1 1 auto; min-width: 0; font-size: 17px; font-weight: 700 !important;
    line-height: 1.2; color: #000000; overflow-wrap: anywhere;
}
.guest-status {
    flex: 0 0 auto; margin-left: 12px; font-size: 13px; font-weight: 400;
    color: #8e8e93; white-space: nowrap;
}
.guest-row.master {flex-direction: column; align-items: stretch;}
.row-top {display: flex; align-items: center; width: 100%;}
.row-bottom {display: flex; justify-content: space-between; align-items: center;
             margin-top: 8px; padding-left: 36px; width: 100%;}
a.num, span.num {font-size: 15px; color: #007aff !important; text-decoration: none !important;
                 padding: 8px 0; min-width: 0; overflow-wrap: anywhere;}
.status-badge {flex: 0 0 auto; margin-left: 12px; padding: 9px 12px; font-size: 13px; font-weight: 700;
               color: #000; border: 1px solid rgba(0,0,0,0.3); border-radius: 6px; white-space: nowrap;}
.no-results {padding: 20px 16px; font-size: 15px; color: #8e8e93;
             font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;}
.list-end {height: 90px;}
.print-btn {position: fixed; right: 16px; bottom: calc(16px + env(safe-area-inset-bottom, 0px)); z-index: 50;
            padding: 12px 16px; background: #000; color: #fff !important; border-radius: 8px;
            font-size: 14px; font-weight: 700; text-decoration: none !important;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;}

/* call-back rows: big main area + rigid side button */
.guest-row.cb-row {padding: 0; align-items: stretch;}
.cb-main {
    flex: 1 1 auto; min-width: 0; padding: 14px 12px 14px 16px;
    display: flex; flex-direction: column; justify-content: center;
    -webkit-tap-highlight-color: rgba(0, 0, 0, 0.06);
}
.cb-top {display: flex; align-items: center; width: 100%;}
.cb-prompt {margin-top: 2px; padding-left: 36px; font-size: 13px; font-weight: 400;
            line-height: 1.1; color: #8e8e93;}
a.cb-side, a.cb-side:visited, a.cb-side:hover, div.cb-side {
    flex: 0 0 100px; display: flex; align-items: center; justify-content: center;
    padding: 0 8px; text-align: center; font-size: 13px; font-weight: 700; line-height: 1.2;
    color: #000000 !important; text-decoration: none !important;
    background-color: rgba(0, 0, 0, 0.08); border-left: 2px solid #000000;
    -webkit-tap-highlight-color: rgba(0, 0, 0, 0.15);
}
div.cb-side {color: #8e8e93 !important;}

/* modal */
div[role="dialog"] {width: calc(100vw - 16px) !important; max-width: calc(100vw - 16px) !important;}
.st-key-abort_call {display: flex; justify-content: flex-end;}
.st-key-abort_call button {width: 44px; min-height: 36px; padding: 0; border: none; background: #ffffff;}
.st-key-abort_call button p {font-size: 22px; color: #8e8e93; margin: 0;}
.dlg-head {font-size: 22px; font-weight: 700; color: #000; margin: 4px 0 16px; overflow-wrap: anywhere;
           font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif;}
[class*="st-key-res_"] button {width: 100%; min-height: 84px; border: 1px solid rgba(0,0,0,0.2);}
[class*="st-key-res_"] button p {font-size: 22px !important; font-weight: 800 !important; color: #000 !important; margin: 0;}
.st-key-res_coming button {background: #d4edda !important;}
.st-key-res_not button {background: #f8d7da !important;}
.st-key-res_didnt button {background: #fff3cd !important;}

/* Force PIN and Search inputs to pure white (Kill Dark Mode) */
[data-baseweb="input"], [data-baseweb="base-input"], div[data-testid="stTextInput"] div {
    background-color: #ffffff !important;
    border-color: #e5e5ea !important;
}
input[type="text"], input[type="password"] {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    background-color: #ffffff !important;
    caret-color: #000000 !important;
}


</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Click helper, injected once into the page itself: taps on a row/badge press
# that row's hidden Streamlit button, and tel: links dial inside the same tap.
JS = """
<script>
const p = window.parent, d = p.document;
if (!p.__annakutBound) {
  p.__annakutBound = true;
  const s = d.createElement('script');
  s.textContent = `document.addEventListener('click', function(e){
    var telLink = e.target.closest('a[href^="tel:"]');
    var badge = e.target.closest('.status-badge');
    var cbMain = e.target.closest('.cb-main');
    
    if (telLink) {
      var idx = telLink.getAttribute('data-idx');
      if (idx !== null) {
        var b = document.querySelector('.st-key-pick_' + idx + ' button');
        // Let the phone dial natively, then trigger the popup 150ms later
        if (b) setTimeout(() => b.click(), 150);
      }
    } 
    else if (badge) {
      var idx = badge.getAttribute('data-idx');
      if (idx !== null) {
        var b = document.querySelector('.st-key-pick_' + idx + ' button');
        if (b) b.click();
      }
    }
    else if (cbMain) {
      var idx = cbMain.getAttribute('data-idx');
      if (idx !== null) {
        var b = document.querySelector('.st-key-pickin_' + idx + ' button');
        if (b) b.click();
      }
    }
  }, true);`;
  d.head.appendChild(s);
}
</script>
"""
with st.container(key="injector"):
    components.html(JS, height=0)


# ---------------------------------------------------------------- data
def tel_number(raw):
    text = re.split(r"[,/;]", str(raw or "").strip())[0].strip()
    if text.endswith(".0"):
        text = text[:-2]
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    if text.startswith("+"):
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "+91" + digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    return digits


@st.cache_data(ttl=5)
def load_guests():
    # Connect to Google Sheets using your hidden secrets.toml
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Read the live data from the cloud
    df = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1X1vmRt3QfG_m6dANAmY7YdAlrZLKFoCU_LveOm_G1Lc/edit?gid=2030823989#gid=2030823989")
    
    df.columns = df.columns.str.strip()
    if "Status" not in df.columns:
        df["Status"] = "PENDING"
    
    df["Status"] = df["Status"].fillna("").str.strip().str.upper().map(ALIASES).fillna("PENDING")
    df["Name"] = df["Name"].fillna("").str.strip()
    df["Contact"] = df["Contact"].fillna("")
    
    df["SR No"] = df["SR No"].astype(str).str.split('.').str[0].replace('nan', '').str.strip()
    df["Contact"] = df["Contact"].astype(str).str.split('.').str[0].replace('nan', '').str.strip()
    
    return df
    


ss = st.session_state
if "df" not in ss:
    ss.df = load_guests()
df = ss.df
if "current_page" not in ss:
    ss.current_page = "PENDING"
if "filter" not in ss:
    ss.filter = "ALL"
if "active_call_index" not in ss:
    raw = st.query_params.get("call")
    ss.active_call_index = int(raw) if raw and raw.isdigit() and int(raw) in df.index else None
if "call_mode" not in ss:
    saved_mode = st.query_params.get("mode")
    ss.call_mode = saved_mode if saved_mode in ("inbound", "outbound") else "outbound"


# ---------------------------------------------------------------- callbacks
def go(page):
    ss.current_page = page


def set_filter(f):
    ss.filter = f


def set_active(idx, mode="outbound"):
    ss.active_call_index = idx
    ss.call_mode = mode
    st.query_params["call"] = str(idx)
    st.query_params["mode"] = mode


def close_call():
    ss.active_call_index = None
    ss.call_mode = "outbound"
    if "call" in st.query_params:
        del st.query_params["call"]
    if "mode" in st.query_params:
        del st.query_params["mode"]


# ---------------------------------------------------------------- modal
@st.dialog("Log Call", dismissible=False)
def call_dialog(idx, mode="outbound"):
    if st.button("\u2715", key="abort_call"):
        close_call()
        st.rerun()
        
    name = html.escape(df.at[idx, "Name"].upper())
    st.markdown(f'<div class="dlg-head">{name} is</div>', unsafe_allow_html=True)
    
    options = (("COMING", "res_coming"), ("NOT COMING", "res_not"), ("DIDNT PICK UP", "res_didnt"))
    if mode == "inbound":
        # Guest called back: "DIDNT PICK UP" makes no sense here
        options = tuple(o for o in options if o[0] != "DIDNT PICK UP")
    
    for label, key in options:
        if st.button(label, key=key, use_container_width=True):
            
            # 1. Update the app's local memory
            ss.df.at[idx, "Status"] = label
            
            # 2. Instantly push the update to Google Sheets
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(
                spreadsheet="https://docs.google.com/spreadsheets/d/1X1vmRt3QfG_m6dANAmY7YdAlrZLKFoCU_LveOm_G1Lc/edit?gid=2030823989#gid=2030823989", 
                data=ss.df
            )
            
            # 3. Clear the cache so the app pulls fresh data on the next load
            st.cache_data.clear()
            
            close_call()
            st.rerun()

# ---------------------------------------------------------------- navigation
page = ss.current_page
with st.container(key="nav"):
    for col, (pid, label) in zip(st.columns(3), PAGES.items()):
        col.button(label, key=f"nav_{pid}", disabled=(page == pid),
                   on_click=go, args=(pid,), use_container_width=True)

with st.container(key="search"):
    query = st_keyup("Search", placeholder="Search", debounce=100,
                     label_visibility="collapsed", key="q")

# ---------------------------------------------------------------- master-only controls
if page == "MASTER":
    items = list(FILTERS.items())
    with st.container(key="filters"):
        for chunk in (items[:3], items[3:]):
            for col, (label, k) in zip(st.columns(len(chunk)), chunk):
                col.button(label, key=f"flt_{k}", disabled=(ss.filter == label),
                           on_click=set_filter, args=(label,), use_container_width=True)
    counts = df["Status"].value_counts()
    cells = "".join(
        f'<div class="stat" style="background:{STATUS_BG[s]}"><div class="stat-n">{int(counts.get(s, 0))}</div>'
        f'<div class="stat-l">{s}</div></div>'
        for s in ("COMING", "NOT COMING", "DIDNT PICK UP", "PENDING"))
    st.markdown(f'<div class="stats">{cells}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- filtering
if page == "PENDING":
    view = df[df["Status"] == "PENDING"]
elif page == "CALLBACK":
    view = df[df["Status"] == "DIDNT PICK UP"]
else:
    view = df if ss.filter == "ALL" else df[df["Status"] == ss.filter]

tokens = (query or "").lower().split()
if tokens:
    names = view["Name"].str.lower()
    mask = pd.Series(True, index=view.index)
    for token in tokens:
        mask &= names.str.contains(token, regex=False)
    view = view[mask]


# ---------------------------------------------------------------- rows
def row_html(idx, row):
    sr = html.escape(str(row["SR No"]).strip())
    name = html.escape(row["Name"])
    status = row["Status"]
    bg = STATUS_BG[status]
    num = tel_number(row["Contact"])

    # 1. Master Page Logic (Returns instantly, ignores the code below)
    if page == "MASTER":
        raw = html.escape(str(row["Contact"]).strip())
        call = f'<a class="num" href="tel:{num}">{raw}</a>' if num else f'<span class="num">{raw}</span>'
        return (f'<div class="guest-row master" style="background:{bg}">'
                f'<div class="row-top"><div class="guest-sr">{sr}</div><div class="guest-name">{name}</div></div>'
                f'<div class="row-bottom">{call}<div class="status-badge" data-idx="{idx}">{status}</div></div></div>')

    # 1b. Call-back Page Logic: main area (inbound) + rigid side button (outbound dial)
    if page == "CALLBACK":
        main = (f'<div class="cb-main" data-idx="{idx}">'
                f'<div class="cb-top"><div class="guest-sr">{sr}</div><div class="guest-name">{name}</div></div>'
                f'<div class="cb-prompt">call aaya?</div></div>')
        if num:
            side = f'<a class="cb-side" href="tel:{num}" data-idx="{idx}">CALL - AGAIN</a>'
        else:
            side = '<div class="cb-side">CALL - AGAIN</div>'
        return f'<div class="guest-row cb-row" style="background:{bg}">{main}{side}</div>'

    # 2. Pending and Callback Logic 
    if page == "CALLBACK":
        label = "call aaya?"
    else:
        label = "call pending" if status == "PENDING" else "didnt pick up"
        
    inner = (f'<div class="guest-row" style="background:{bg}"><div class="guest-sr">{sr}</div>'
             f'<div class="guest-name">{name}</div><div class="guest-status">{label}</div></div>')
             
    if num:
        return f'<a class="guest-link" href="tel:{num}" data-idx="{idx}">{inner}</a>'
    return inner

if len(view):
    st.markdown("".join(row_html(i, r) for i, r in view.iterrows()) + '<div class="list-end"></div>',
                unsafe_allow_html=True)
    for i in view.index:  # hidden buttons that the tap helper presses
        st.button("pick", key=f"pick_{i}", on_click=set_active, args=(i,))
        if page == "CALLBACK":
            st.button("pickin", key=f"pickin_{i}", on_click=set_active, args=(i, "inbound"))
else:
    st.markdown('<div class="no-results">No results</div>', unsafe_allow_html=True)

if page == "MASTER":
    st.markdown(f'<a class="print-btn" href="{PRINT_URL}" target="_blank">Print to PDF</a>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------- lock
if ss.active_call_index is not None:
    call_dialog(ss.active_call_index, ss.call_mode)
