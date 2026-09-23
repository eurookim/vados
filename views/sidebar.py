"""Sidebar branding and page navigation."""
import streamlit as st


def show_sidebar(nav_icons):
    """nav_icons maps each page name to its icon, in display order."""
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding: 1.5rem 0 1rem 0;">
            <span style="font-size: 2.2rem;">💰</span>
            <h1 style="margin:0; font-size:1.8rem; background: linear-gradient(135deg, var(--accent), var(--accent-light));
                -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight:800;">
                Vados
            </h1>
            <p style="color:var(--text-muted); font-size:0.8rem; margin-top:4px;">AI Finance Assistant</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        for p in nav_icons:
            label = f"{nav_icons[p]}  {p}"
            if st.button(label, key=f"nav_{p}", use_container_width=True,
                         type="primary" if st.session_state.page == p else "secondary"):
                st.session_state.page = p
                st.rerun()
