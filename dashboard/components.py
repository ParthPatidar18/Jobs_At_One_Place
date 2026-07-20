"""Reusable presentation components for the HuntFlow dashboard."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape

import plotly.graph_objects as go
import streamlit as st

from dashboard.services import DashboardJob, display_match_score, is_remote, relative_time


def render_navbar() -> None:
    """Render the premium product header."""

    st.markdown(
        """
        <section class="topbar">
          <div class="brand-lockup"><span class="brand-mark">H</span><div><b>HuntFlow</b><small>Career intelligence</small></div></div>
          <div class="topbar-status"><span class="pulse-dot"></span> Intelligence engine live</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_hero(jobs: list[DashboardJob]) -> None:
    today = datetime.now(timezone.utc).date()
    new_today = sum(job.received_at.date() == today for job in jobs)
    recommendation = max(jobs, key=display_match_score, default=None)
    recommendation_text = (
        f"AI recommends exploring {escape(recommendation.company)}."
        if recommendation else "Your intelligence feed is ready for its first opportunity."
    )
    st.markdown(
        f"""
        <section class="hero-panel">
          <div class="hero-orb hero-orb-one"></div><div class="hero-orb hero-orb-two"></div>
          <div class="eyebrow">✦ AI-powered opportunity radar</div>
          <h1>Good evening, Parth <span>👋</span></h1>
          <p>{new_today} new opportunities found today. {recommendation_text}</p>
          <div class="hero-signals"><span><b>{new_today}</b> new today</span><span><b>{len({job.company for job in jobs if job.company != 'Unknown'})}</b> companies in view</span><span><b>24/7</b> signal monitoring</span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_insight_cards(jobs: list[DashboardJob]) -> None:
    today = datetime.now(timezone.utc).date()
    fresh = [job for job in jobs if job.received_at.date() == today]
    high_match = [job for job in jobs if display_match_score(job) >= 85]
    referrals = [job for job in jobs if "referral" in job.message_text.casefold()]
    cards = (
        ("🔥", "New jobs today", str(len(fresh)), "Live feed", "violet"),
        ("🎯", "High-match jobs", str(len(high_match)), "Score 85%+", "cyan"),
        ("💬", "Follow-ups due", "03", "Keep momentum", "blue"),
        ("🤝", "Referral signals", str(len(referrals)), "Network-led roles", "pink"),
        ("🏆", "Resume match", "86%", "Above average", "amber"),
    )
    columns = st.columns(5, gap="small")
    for column, (icon, label, value, helper, accent) in zip(columns, cards, strict=True):
        with column:
            st.markdown(
                f"""<section class="insight-card {accent}"><div class="insight-icon">{icon}</div><div class="insight-value">{value}</div><div class="insight-label">{label}</div><div class="insight-helper">{helper}</div></section>""",
                unsafe_allow_html=True,
            )


def render_recommendation(jobs: list[DashboardJob]) -> None:
    job = max(jobs, key=display_match_score, default=None)
    if not job:
        st.markdown('<section class="recommendation-card"><p class="eyebrow">AI recommendation</p><h3>Waiting for opportunities</h3><p>New roles will be scored as they arrive.</p></section>', unsafe_allow_html=True)
        return
    skills = list(job.skills[:3]) or ["Role alignment", "Recent signal"]
    missing = ("Redis", "Kafka") if len(skills) < 3 else ("System design", "Cloud depth")
    st.markdown(
        f"""
        <section class="recommendation-card">
          <div class="recommendation-heading"><span class="sparkle">✦</span><span>AI recommendation</span></div>
          <div class="company-line"><span class="company-avatar">{escape(_initials(job.company))}</span><div><h3>{escape(job.company)}</h3><p>{escape(job.role)}</p></div><strong>{display_match_score(job)}%</strong></div>
          <p class="why-label">Why it stands out</p>
          <div class="skill-row">{''.join(f'<span>{escape(skill)}</span>' for skill in skills)}</div>
          <p class="missing-label">Growth edge <span>{', '.join(escape(item) for item in missing)}</span></p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_job_card(job: DashboardJob) -> None:
    """Render one job with display-only AI metadata and existing Apply behavior."""

    score = display_match_score(job)
    key = f"job-{job.message_id}"
    expanded_key = f"{key}-expanded"
    saved_key = f"{key}-saved"
    skills = job.skills[:5] or ("Details pending",)
    remote_badge = "<span class='badge badge-remote'>Remote</span>" if is_remote(job) else "<span class='badge'>On-site</span>"
    with st.container(border=True, key=key):
        st.markdown(
            f"""
            <section class="job-card">
              <div class="job-card-top"><span class="company-avatar large">{escape(_initials(job.company))}</span><div class="job-primary"><div class="job-title-line"><h3>{escape(job.role)}</h3><span class="match-score">{score}% match</span></div><p>{escape(job.company)} <span>•</span> {escape(relative_time(job.received_at))}</p></div></div>
              <div class="job-meta"><span>⌖ {escape(job.location)}</span><span>▣ {escape(job.experience)}</span><span>₹ {escape(job.salary)}</span>{remote_badge}</div>
              <div class="skill-row job-skills">{''.join(f'<span>{escape(skill)}</span>' for skill in skills)}</div>
              <div class="source-line">↗ {escape(job.source_channel)}</div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        actions = st.columns((1.5, 1, 1), gap="small")
        with actions[0]:
            if job.apply_url:
                st.link_button("Apply now", job.apply_url, icon=":material/arrow_outward:", width="stretch")
            else:
                st.button("Apply unavailable", disabled=True, key=f"apply-{job.message_id}", width="stretch")
        with actions[1]:
            if st.button("Saved" if st.session_state.get(saved_key) else "Save", icon=":material/bookmark:", key=f"save-{job.message_id}", width="stretch"):
                st.session_state[saved_key] = not st.session_state.get(saved_key, False)
        with actions[2]:
            if st.button("Details", icon=":material/expand_more:", key=f"expand-{job.message_id}", width="stretch"):
                st.session_state[expanded_key] = not st.session_state.get(expanded_key, False)
        if st.session_state.get(expanded_key):
            st.caption(job.message_text[:600] or "No additional job description was captured.")


def render_analytics(jobs: list[DashboardJob]) -> None:
    st.markdown("#### Intelligence overview")
    left, right = st.columns((1.35, 1), gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("**Hiring trends**  ")
            st.caption("New opportunities indexed across the past week")
            st.plotly_chart(_hiring_trends(jobs), width="stretch", config={"displayModeBar": False})
    with right:
        with st.container(border=True):
            st.markdown("**Top companies**")
            st.caption("Most active in your current feed")
            st.plotly_chart(_top_companies(jobs), width="stretch", config={"displayModeBar": False})


def render_activity_timeline(jobs: list[DashboardJob]) -> None:
    st.markdown("#### Recent activity")
    if not jobs:
        st.caption("Your timeline will appear when the feed receives its first role.")
        return
    items = jobs[:4]
    timeline = "".join(
        f"<div class='timeline-item'><span class='timeline-dot'></span><div><b>Opportunity indexed</b><p>{escape(job.role)} at {escape(job.company)} · {escape(relative_time(job.received_at))}</p></div></div>"
        for job in items
    )
    st.markdown(f"<section class='timeline'>{timeline}</section>", unsafe_allow_html=True)


def _hiring_trends(jobs: list[DashboardJob]) -> go.Figure:
    today = datetime.now(timezone.utc).date()
    dates = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    counts = [sum(job.received_at.date() == date for job in jobs) for date in dates]
    figure = go.Figure(go.Scatter(x=dates, y=counts, mode="lines+markers", line={"color": "#8b5cf6", "width": 3}, marker={"size": 7, "color": "#22d3ee"}, fill="tozeroy", fillcolor="rgba(139, 92, 246, .12)"))
    return _chart_layout(figure, height=240)


def _top_companies(jobs: list[DashboardJob]) -> go.Figure:
    companies = Counter(job.company for job in jobs if job.company != "Unknown").most_common(5)
    names, counts = zip(*companies) if companies else (("No company data",), (0,))
    figure = go.Figure(go.Bar(x=list(counts), y=list(names), orientation="h", marker={"color": "#2563eb", "cornerradius": 6}))
    figure.update_yaxes(autorange="reversed")
    return _chart_layout(figure, height=240)


def _chart_layout(figure: go.Figure, *, height: int) -> go.Figure:
    figure.update_layout(height=height, margin={"l": 0, "r": 10, "t": 8, "b": 0}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#9ca3af", "size": 11}, showlegend=False)
    figure.update_xaxes(showgrid=True, gridcolor="rgba(148,163,184,.12)", zeroline=False, showline=False)
    figure.update_yaxes(showgrid=False, zeroline=False, showline=False)
    return figure


def _initials(value: str) -> str:
    return "".join(part[0] for part in value.split()[:2]).upper() or "HF"
