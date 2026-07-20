"""Styling loader for the HuntFlow dashboard."""

from __future__ import annotations

from pathlib import Path

import streamlit as st


def apply_styles() -> None:
    """Load the dashboard stylesheet from the local UI asset bundle."""

    stylesheet = Path(__file__).with_name("assets") / "huntflow.css"
    st.markdown(f"<style>{stylesheet.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
