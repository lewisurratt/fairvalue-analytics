from __future__ import annotations

import streamlit as st

from fairvalue.config import APP_NAME, DEMO_DATA_DIR, PRIVATE_DATA_DIR
from fairvalue.storage import CsvRepository
from fairvalue.ui import app_footer, inject_theme, sidebar_brand
from fairvalue.views import accounts, analytics, dashboard, journal, trades


st.set_page_config(
    page_title=APP_NAME,
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()


@st.cache_resource
def repository(data_dir: str) -> CsvRepository:
    return CsvRepository(data_dir)


sidebar_brand()

private_ready = (PRIVATE_DATA_DIR / "accounts.csv").exists()
available_datasets = ["Private", "Demo"] if private_ready else ["Demo"]
dataset = st.sidebar.selectbox(
    "Dataset",
    available_datasets,
    index=0,
    help="Private data is local and git-ignored. Demo data is safe sample content for portfolio previews.",
)
data_dir = PRIVATE_DATA_DIR if dataset == "Private" else DEMO_DATA_DIR
repo = repository(str(data_dir))

PAGES = {
    "Overview": dashboard.render,
    "Accounts": accounts.render,
    "Journal": journal.render,
    "Trades": trades.render,
    "Analytics": analytics.render,
}

page = st.sidebar.radio("Workspace", list(PAGES), label_visibility="collapsed")
st.sidebar.divider()
demo_mode = st.sidebar.toggle(
    "Public demo mode",
    value=dataset == "Demo",
    help="Anonymizes prop-firm names in presentation only. It does not alter stored data.",
)
st.sidebar.caption(f"{dataset} dataset · Local CSV repository")

PAGES[page](repo, demo_mode)
st.divider()
app_footer()
