"""Trends page: income vs expenses, net savings, budget vs actual."""
from datetime import date

import plotly.graph_objects as go
import streamlit as st

from database import SUPPORTED_CURRENCIES, get_budget_targets, get_default_currency, get_monthly_summaries


def _style_chart(fig, **overrides):
    """Apply consistent dark theme styling to a Plotly figure."""
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#C4C9E0", family="Inter", size=13),
        xaxis=dict(
            gridcolor="rgba(45,51,80,0.5)", showgrid=False,
            tickfont=dict(color="#9BA1B8", size=12),
            linecolor="#2D3350", zeroline=False,
        ),
        yaxis=dict(
            gridcolor="rgba(45,51,80,0.4)", showgrid=True, griddash="dot",
            tickfont=dict(color="#9BA1B8", size=12),
            linecolor="#2D3350", zeroline=False,
        ),
        margin=dict(l=50, r=30, t=50, b=50),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", font=dict(color="#9BA1B8", size=12),
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        ),
        hoverlabel=dict(
            bgcolor="#1E2235", bordercolor="#7C5CFC",
            font=dict(color="#E8EAF0", family="Inter", size=13),
        ),
        bargap=0.3,
    )
    layout.update(overrides)
    fig.update_layout(**layout)
    return fig


def show_trends():
    st.title("Spending Trends")
    cur = get_default_currency()
    symbol = SUPPORTED_CURRENCIES.get(cur, "$")

    summaries = get_monthly_summaries(6)
    targets = get_budget_targets()

    month_labels = [date(s["year"], s["month"], 1).strftime("%b %Y") for s in summaries]
    expenses = [s["total_expenses"] for s in summaries]
    incomes = [s["total_income"] for s in summaries]

    # --- Chart 1: Income vs Expenses ---
    st.subheader("Income vs Expenses")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=month_labels, y=incomes, name="Income",
        line=dict(color="#34D399", width=3, shape="spline"),
        mode="lines+markers",
        marker=dict(size=9, color="#34D399", line=dict(width=2, color="#1A3328")),
        fill="tozeroy",
        fillcolor="rgba(52,211,153,0.08)",
        hovertemplate="%{x}<br>Income: " + symbol + "%{y:,.0f}<extra></extra>",
    ))
    fig2.add_trace(go.Scatter(
        x=month_labels, y=expenses, name="Expenses",
        line=dict(color="#F87171", width=3, shape="spline"),
        mode="lines+markers",
        marker=dict(size=9, color="#F87171", line=dict(width=2, color="#331A1A")),
        fill="tozeroy",
        fillcolor="rgba(248,113,113,0.08)",
        hovertemplate="%{x}<br>Expenses: " + symbol + "%{y:,.0f}<extra></extra>",
    ))
    _style_chart(fig2, yaxis_title=f"Amount ({cur})", height=380)
    st.plotly_chart(fig2, use_container_width=True)

    # --- Chart 3: Net Savings ---
    st.subheader("Net Savings")
    net_vals = [i - e for i, e in zip(incomes, expenses)]
    bar_colors = ["#34D399" if n >= 0 else "#F87171" for n in net_vals]
    fig3 = go.Figure(go.Bar(
        x=month_labels, y=net_vals,
        marker=dict(color=bar_colors, cornerradius=6, line=dict(width=0)),
        text=[f"{symbol}{abs(n):,.0f}" for n in net_vals],
        textposition="outside",
        textfont=dict(color="#9BA1B8", size=12, family="Inter"),
        hovertemplate="%{x}<br>Net: " + symbol + "%{y:,.0f}<extra></extra>",
    ))
    # Add zero line
    fig3.add_hline(y=0, line_dash="dot", line_color="#6B7094", line_width=1)
    _style_chart(fig3, yaxis_title=f"Net ({cur})", height=340)
    st.plotly_chart(fig3, use_container_width=True)

    # --- Chart 4: Budget vs Actual ---
    if targets:
        st.subheader("Budget vs Actual")
        current = summaries[-1]["by_category"]
        budget_cats = [c for c in targets if c in current or targets[c] > 0]
        if budget_cats:
            actual_vals = [current.get(c, 0) for c in budget_cats]
            budget_vals = [targets[c] for c in budget_cats]
            pct_vals = [a / b * 100 if b > 0 else 0 for a, b in zip(actual_vals, budget_vals)]
            bar_colors_budget = [
                "#F87171" if p >= 100 else "#FBBF24" if p >= 80 else "#34D399"
                for p in pct_vals
            ]
            fig4 = go.Figure()
            fig4.add_trace(go.Bar(
                x=budget_cats, y=budget_vals, name="Budget",
                marker=dict(color="rgba(45,51,80,0.6)", cornerradius=6, line=dict(width=1, color="#3B4580")),
                hovertemplate="%{x}<br>Budget: " + symbol + "%{y:,.0f}<extra></extra>",
            ))
            fig4.add_trace(go.Bar(
                x=budget_cats, y=actual_vals, name="Actual",
                marker=dict(color=bar_colors_budget, cornerradius=6, line=dict(width=0)),
                text=[f"{p:.0f}%" for p in pct_vals],
                textposition="outside",
                textfont=dict(color="#9BA1B8", size=12, family="Inter"),
                hovertemplate="%{x}<br>Spent: " + symbol + "%{y:,.0f} (%{text})<extra></extra>",
            ))
            _style_chart(fig4, barmode="group", yaxis_title=f"Amount ({cur})", height=380, bargap=0.25)
            st.plotly_chart(fig4, use_container_width=True)
