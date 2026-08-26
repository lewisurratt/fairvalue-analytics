from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from fairvalue.config import DATA_ROOT, JOURNAL_SESSIONS
from fairvalue.storage.base import DataRepository
from fairvalue.ui import empty_state, money, page_header, safe, save_uploads, section, tags


def _add_entry(repo: DataRepository) -> None:
    with st.form("add_journal", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        entry_date = col1.date_input("Date", value=date.today())
        session = col2.selectbox("Session", JOURNAL_SESSIONS, index=1)
        pnl = col3.number_input("Session P&L", step=50.0)
        what_happened = st.text_area("What happened?", placeholder="Describe the session and your decision sequence.")
        col4, col5 = st.columns(2)
        worked = col4.text_area("What worked?", placeholder="Process, patience, execution…")
        wrong = col5.text_area("What went wrong?", placeholder="Mistakes, rule breaks, missed context…")
        lesson = st.text_area("Main lesson", placeholder="The one thing to carry into the next session.")
        col6, col7 = st.columns(2)
        strategy = col6.text_input("Strategy tags", placeholder="ORB, trend continuation")
        setup = col7.text_input("Setup tags", placeholder="retest, liquidity sweep")
        screenshots = st.file_uploader(
            "Screenshots", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True
        )
        submitted = st.form_submit_button("Save journal entry", type="primary", width="stretch")
        if submitted:
            if not what_happened.strip() and not lesson.strip():
                st.error("Add what happened or a main lesson before saving.")
            else:
                record_id = str(uuid.uuid4())
                upload_dir = Path(getattr(repo, "data_dir", DATA_ROOT)) / "uploads"
                paths = save_uploads(screenshots, upload_dir, record_id)
                repo.add(
                    "journals",
                    {
                        "id": record_id,
                        "date": entry_date.isoformat(),
                        "session": session,
                        "pnl": pnl,
                        "what_happened": what_happened.strip(),
                        "what_worked": worked.strip(),
                        "what_went_wrong": wrong.strip(),
                        "main_lesson": lesson.strip(),
                        "strategy_tags": strategy.strip(),
                        "setup_tags": setup.strip(),
                        "screenshot_paths": "|".join(paths),
                    },
                )
                st.success("Journal entry saved.")
                st.rerun()


def _manage_entry(repo: DataRepository, journals: pd.DataFrame) -> None:
    options = {
        str(row["id"]): f"{row['date']} · {row['session']} · {money(float(row['pnl']), signed=True)}"
        for _, row in journals.iterrows()
    }
    selected_id = st.selectbox("Choose entry", options, format_func=lambda value: options[value])
    current = journals.loc[journals["id"].astype(str).eq(selected_id)].iloc[0]
    session_index = JOURNAL_SESSIONS.index(current["session"]) if current["session"] in JOURNAL_SESSIONS else 0
    with st.form("edit_journal"):
        col1, col2, col3 = st.columns(3)
        entry_date = col1.date_input("Date", value=pd.to_datetime(current["date"]).date())
        session = col2.selectbox("Session", JOURNAL_SESSIONS, index=session_index)
        pnl = col3.number_input("Session P&L", value=float(current["pnl"]), step=50.0)
        happened = st.text_area("What happened?", value=str(current["what_happened"]))
        col4, col5 = st.columns(2)
        worked = col4.text_area("What worked?", value=str(current["what_worked"]))
        wrong = col5.text_area("What went wrong?", value=str(current["what_went_wrong"]))
        lesson = st.text_area("Main lesson", value=str(current["main_lesson"]))
        col6, col7 = st.columns(2)
        strategy = col6.text_input("Strategy tags", value=str(current["strategy_tags"]))
        setup = col7.text_input("Setup tags", value=str(current["setup_tags"]))
        if st.form_submit_button("Save changes", type="primary"):
            repo.update(
                "journals",
                selected_id,
                {
                    "date": entry_date.isoformat(),
                    "session": session,
                    "pnl": pnl,
                    "what_happened": happened.strip(),
                    "what_worked": worked.strip(),
                    "what_went_wrong": wrong.strip(),
                    "main_lesson": lesson.strip(),
                    "strategy_tags": strategy.strip(),
                    "setup_tags": setup.strip(),
                },
            )
            st.success("Entry updated.")
            st.rerun()
    confirm = st.checkbox("I understand this removes the journal record", key=f"journal_confirm_{selected_id}")
    if st.button("Delete journal entry", disabled=not confirm):
        repo.delete("journals", selected_id)
        st.rerun()


def render(repo: DataRepository, demo_mode: bool) -> None:
    journals = repo.list("journals")
    page_header(
        "Decision journal",
        "Turn each session into evidence.",
        "Capture the story behind the P&L, then surface the patterns worth repeating—or removing.",
    )
    with st.expander("Add journal entry", expanded=journals.empty):
        _add_entry(repo)

    section("Timeline")
    if journals.empty:
        empty_state("No entries yet. Your first debrief starts the timeline.")
        return
    col1, col2 = st.columns([1, 2])
    session_filter = col1.multiselect("Session", sorted(journals["session"].dropna().unique()))
    tag_query = col2.text_input("Filter tags", placeholder="Type a strategy or setup tag")
    filtered = journals.copy()
    if session_filter:
        filtered = filtered[filtered["session"].isin(session_filter)]
    if tag_query.strip():
        haystack = filtered["strategy_tags"].astype(str) + "," + filtered["setup_tags"].astype(str)
        filtered = filtered[haystack.str.contains(tag_query.strip(), case=False, regex=False)]
    filtered = filtered.sort_values(["date", "created_at"], ascending=False)
    if filtered.empty:
        empty_state("No journal entries match these filters.")
    for _, entry in filtered.iterrows():
        pnl = float(entry["pnl"])
        pnl_class = "fv-positive" if pnl >= 0 else "fv-negative"
        st.markdown(
            f'<div class="fv-card"><div class="fv-card-top"><div>'
            f'<div class="fv-card-title">{safe(entry["date"])} · {safe(entry["session"])}</div>'
            f'<div class="fv-card-meta">{safe(entry["what_happened"])}</div></div>'
            f'<div class="{pnl_class}">{money(pnl, signed=True)}</div></div>'
            f'<div class="fv-card-copy"><strong>Lesson:</strong> {safe(entry["main_lesson"] or "—")}</div>'
            f'{tags(entry["strategy_tags"])}{tags(entry["setup_tags"])}</div>',
            unsafe_allow_html=True,
        )
        with st.expander("Open debrief"):
            a, b = st.columns(2)
            a.markdown(f"**What worked**\n\n{entry['what_worked'] or '—'}")
            b.markdown(f"**What went wrong**\n\n{entry['what_went_wrong'] or '—'}")
            paths = [Path(path) for path in str(entry["screenshot_paths"]).split("|") if path]
            existing = [path for path in paths if path.exists()]
            if existing:
                st.image([str(path) for path in existing], caption=[path.name for path in existing])
    with st.expander("Edit or remove entry"):
        _manage_entry(repo, journals)
