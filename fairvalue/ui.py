from __future__ import annotations

import html
import re
from pathlib import Path

import streamlit as st

from fairvalue.config import APP_NAME, APP_TAGLINE


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root { --mint:#45E0A8; --ink:#0A0F14; --panel:#111923; --muted:#8EA3AF; }
        .stApp { background:
            radial-gradient(circle at 78% -8%, rgba(69,224,168,.09), transparent 30rem),
            linear-gradient(180deg, #0A0F14 0%, #0C1219 100%); }
        [data-testid="stSidebar"] { background: rgba(13,20,28,.96); border-right:1px solid #1B2A35; }
        [data-testid="stMetric"] { background:linear-gradient(145deg,#111A23,#0E151D); border:1px solid #1C2B35;
            padding:1rem 1.05rem; border-radius:14px; box-shadow:0 8px 28px rgba(0,0,0,.14); }
        [data-testid="stMetricLabel"] { color:#8EA3AF; }
        [data-testid="stMetricValue"] { color:#F1F7FA; letter-spacing:-.03em; }
        div[data-testid="stForm"] { border:1px solid #1C2B35; border-radius:16px; padding:1.2rem; background:#0F171F; }
        .fv-brand { display:flex; align-items:center; gap:.7rem; margin:.35rem 0 1.6rem; }
        .fv-mark { width:34px; height:34px; border-radius:10px; display:grid; place-items:center; color:#07100D;
            font-weight:900; background:linear-gradient(135deg,#45E0A8,#83F1CB); box-shadow:0 0 24px rgba(69,224,168,.25); }
        .fv-brand-name { font-weight:750; color:#F1F7FA; line-height:1.05; }
        .fv-brand-sub { color:#6F8591; font-size:.72rem; margin-top:.2rem; }
        .fv-kicker { color:#45E0A8; font-size:.74rem; letter-spacing:.16em; font-weight:700; text-transform:uppercase; }
        .fv-hero { font-size:clamp(2rem,4vw,3.4rem); line-height:1.02; letter-spacing:-.055em;
            max-width:760px; margin:.4rem 0 .7rem; font-weight:760; color:#F3F8FA; }
        .fv-subtitle { color:#8EA3AF; font-size:1.02rem; max-width:720px; margin-bottom:1.7rem; }
        .fv-section { color:#EAF2F6; font-size:1.1rem; font-weight:700; margin:1.8rem 0 .75rem; }
        .fv-card { border:1px solid #1C2B35; border-radius:14px; padding:1rem 1.05rem; background:#0F171F; margin-bottom:.7rem; }
        .fv-card-top { display:flex; justify-content:space-between; gap:1rem; align-items:center; }
        .fv-card-title { color:#EFF6F8; font-weight:700; }
        .fv-card-meta { color:#718793; font-size:.78rem; }
        .fv-card-copy { color:#A7B8C1; font-size:.9rem; margin-top:.65rem; line-height:1.5; }
        .fv-pill { display:inline-block; color:#87EEC9; background:rgba(69,224,168,.09); border:1px solid rgba(69,224,168,.22);
            border-radius:999px; padding:.18rem .52rem; font-size:.7rem; margin:.55rem .25rem 0 0; }
        .fv-positive { color:#45E0A8; } .fv-negative { color:#FF6F7D; }
        .fv-empty { border:1px dashed #263642; border-radius:14px; padding:2.2rem; text-align:center; color:#718793; }
        .stButton > button, .stDownloadButton > button { border-radius:10px; font-weight:650; }
        hr { border-color:#1C2B35 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    st.sidebar.markdown(
        f"""
        <div class="fv-brand">
          <div class="fv-mark">FV</div>
          <div><div class="fv-brand-name">{APP_NAME}</div><div class="fv-brand-sub">Trading intelligence</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="fv-kicker">{html.escape(kicker)}</div>'
        f'<div class="fv-hero">{html.escape(title)}</div>'
        f'<div class="fv-subtitle">{html.escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(f'<div class="fv-section">{html.escape(title)}</div>', unsafe_allow_html=True)


def money(value: float, signed: bool = False) -> str:
    if value < 0:
        return f"-${abs(value):,.2f}"
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}${value:,.2f}"


def safe(value: object) -> str:
    return html.escape(str(value or ""))


def tags(value: object) -> str:
    items = [item.strip() for item in re.split(r"[,;]", str(value or "")) if item.strip()]
    return "".join(f'<span class="fv-pill">{safe(item)}</span>' for item in items)


def empty_state(message: str) -> None:
    st.markdown(f'<div class="fv-empty">{safe(message)}</div>', unsafe_allow_html=True)


def save_uploads(files: list[object], upload_dir: Path, record_id: str) -> list[str]:
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for index, uploaded in enumerate(files):
        suffix = Path(getattr(uploaded, "name", "image.png")).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        destination = upload_dir / f"{record_id}_{index}{suffix}"
        destination.write_bytes(uploaded.getvalue())
        saved.append(str(destination))
    return saved


def app_footer() -> None:
    st.caption(f"{APP_NAME} · {APP_TAGLINE} · Local-first V1")
