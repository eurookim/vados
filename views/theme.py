"""Color palette: the single source of truth for theme colors.

style.css and inline HTML use these as CSS variables (e.g. var(--accent));
Plotly charts, which need literal values, import the constants directly.
"""
from pathlib import Path

import streamlit as st

ACCENT = "#7C5CFC"
ACCENT_LIGHT = "#A78BFA"
BORDER = "#2D3350"
BORDER_ACCENT = "#3B4580"
CARD = "#1E2235"
CARD_END = "#252A40"
INPUT_BG = "#1A1D29"
TEXT_PRIMARY = "#E8EAF0"
TEXT_HEADING = "#C4C9E0"
TEXT_SECONDARY = "#9BA1B8"
TEXT_MUTED = "#6B7094"
POSITIVE = "#34D399"
POSITIVE_BG = "#1A3328"
NEGATIVE = "#F87171"
NEGATIVE_BG = "#331A1A"
WARNING = "#FBBF24"
INFO_BG = "#1A2340"

CSS_VARIABLES = {
    "accent": ACCENT,
    "accent-light": ACCENT_LIGHT,
    "border": BORDER,
    "border-accent": BORDER_ACCENT,
    "card": CARD,
    "card-end": CARD_END,
    "input-bg": INPUT_BG,
    "text-primary": TEXT_PRIMARY,
    "text-heading": TEXT_HEADING,
    "text-secondary": TEXT_SECONDARY,
    "text-muted": TEXT_MUTED,
    "positive": POSITIVE,
    "positive-bg": POSITIVE_BG,
    "negative": NEGATIVE,
    "negative-bg": NEGATIVE_BG,
    "warning": WARNING,
    "info-bg": INFO_BG,
}

_STYLESHEET = Path(__file__).resolve().parent.parent / "style.css"


def apply_theme():
    variables = "".join(f"--{name}: {value}; " for name, value in CSS_VARIABLES.items())
    css = _STYLESHEET.read_text()
    # Appended, not prepended: style.css opens with an @import, which the
    # browser ignores unless it comes before every other rule.
    st.markdown(f"<style>{css}\n:root {{ {variables}}}</style>", unsafe_allow_html=True)
