"""Streamlit entry point for the read-only HuntFlow job dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.repository import JobRepository  # noqa: E402
from dashboard.components import (  # noqa: E402
    render_activity_timeline,
    render_analytics,
    render_hero,
    render_insight_cards,
    render_job_card,
    render_navbar,
    render_recommendation,
)
from dashboard.services import DashboardService, filter_jobs, options  # noqa: E402
from dashboard.styles import apply_styles  # noqa: E402


st.set_page_config(page_title="HuntFlow | Career intelligence", page_icon=":material/radar:", layout="wide", initial_sidebar_state="expanded")
apply_styles()


@st.cache_data(ttl="5s", max_entries=1, show_spinner=False)
def _load_dashboard_jobs():
    """Cache the read-only database snapshot between live refreshes."""

    return DashboardService(JobRepository()).load_jobs()


def _sidebar_filters() -> dict[str, str]:
    """Render persisted, submit-based opportunity filters."""

    jobs = _load_dashboard_jobs()
    defaults = {"search": "", "company": "All", "role": "All", "location": "All", "experience": "All", "source_channel": "All", "work_mode": "All"}
    st.session_state.setdefault("active_filters", defaults)
    with st.sidebar:
        st.markdown("<div class='sidebar-brand'><span class='brand-mark'>H</span><div><b>HuntFlow</b><small>Job intelligence</small></div></div>", unsafe_allow_html=True)
        st.caption("WORKSPACE")
        st.markdown("<div class='side-nav active'>◈ Overview</div><div class='side-nav'>✦ Matches</div><div class='side-nav'>▱ Saved roles</div><div class='side-nav'>◌ Insights</div>", unsafe_allow_html=True)
        st.markdown("<div class='sidebar-section-title'>Opportunity filters</div>", unsafe_allow_html=True)
        with st.form("opportunity_filters", border=False):
            search = st.text_input("Search opportunities", placeholder="Role, company, skill…", key="filter_search")
            work_mode = st.pills("Work mode", ["All", "Remote", "On-site"], default="All", key="filter_mode", width="stretch")
            with st.expander("Refine feed", icon=":material/tune:"):
                company = st.selectbox("Company", options(jobs, "company"), key="filter_company")
                role = st.selectbox("Role", options(jobs, "role"), key="filter_role")
                location = st.selectbox("Location", options(jobs, "location"), key="filter_location")
                experience = st.selectbox("Experience", options(jobs, "experience"), key="filter_experience")
                source_channel = st.selectbox("Source", options(jobs, "source_channel"), key="filter_source")
            submitted = st.form_submit_button("Apply filters", icon=":material/filter_alt:", width="stretch")
        if submitted:
            st.session_state.active_filters = {"search": search, "company": company, "role": role, "location": location, "experience": experience, "source_channel": source_channel, "work_mode": work_mode or "All"}
        if st.button("Refresh intelligence", icon=":material/refresh:", width="stretch"):
            _load_dashboard_jobs.clear()
            st.rerun()
        st.markdown("<div class='profile-card'><span class='profile-avatar'>PP</span><div><b>Parth Patidar</b><small>Career builder</small></div><span>•••</span></div>", unsafe_allow_html=True)
    return st.session_state.active_filters


@st.fragment(run_every="5s")
def _live_dashboard(filters: dict[str, str]) -> None:
    """Refresh data without affecting the existing Telegram/database pipeline."""

    jobs = _load_dashboard_jobs()
    render_hero(jobs)
    render_insight_cards(jobs)
    st.markdown("<div class='section-kicker'>DISCOVER</div><h2 class='section-title'>Opportunity feed</h2>", unsafe_allow_html=True)
    main, recommendation = st.columns((1.8, 1), gap="medium")
    with main:
        filtered_jobs = filter_jobs(jobs, **filters)
        st.caption(f"{len(filtered_jobs)} roles matching your current focus")
        if not filtered_jobs:
            st.markdown("<div class='empty-state'>No opportunities match these filters yet. Try broadening your focus.</div>", unsafe_allow_html=True)
        for job in filtered_jobs:
            render_job_card(job)
    with recommendation:
        render_recommendation(filtered_jobs or jobs)
        render_activity_timeline(jobs)
    render_analytics(jobs)


render_navbar()
_live_dashboard(_sidebar_filters())
