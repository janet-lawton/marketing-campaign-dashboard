import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components

from metrics import compute_kpis, share_by, top_by_roi

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="Marketing Campaign Dashboard", layout="wide")

# ── Theme helpers ─────────────────────────────────────────────────────────────
# Page, sidebar, and widget colors come from .streamlit/config.toml.
# These values cover what config.toml cannot reach: card surfaces and chart series.
CARD_COLORS = {
    "light": {"card": "#ffffff", "card-border": "#d9e4df", "accent": "#488f71", "text": "#1f2d28"},
    "dark": {"card": "#16241f", "card-border": "#24362f", "accent": "#6aaa96", "text": "#e6efeb"},
}
SERIES = {
    "light": ["#3a9d7a", "#f08a3c", "#4c8dd6", "#e8c140", "#b46bc4", "#e5586e"],
    "dark": ["#3a9d7a", "#f08a3c", "#4c8dd6", "#e8c140", "#b46bc4", "#e5586e"],
}


def current_mode():
    """Return 'light' or 'dark' for the active Streamlit theme, or None if unknown."""
    try:
        theme = st.context.theme
        mode = getattr(theme, "type", None) or getattr(theme, "base", None)
    except Exception:
        return None
    return mode if mode in CARD_COLORS else None


MODE = current_mode()
COLORS = SERIES.get(MODE, SERIES["light"])
ACCENT = COLORS[0]


def inject_css():
    css = (Path(__file__).parent / "styles.css").read_text(encoding="utf-8")
    variables = ""
    if MODE:
        variables = ":root{" + "".join(f"--{k}:{v};" for k, v in CARD_COLORS[MODE].items()) + "}"
    st.markdown(f"<style>{variables}{css}</style>", unsafe_allow_html=True)


inject_css()

with st.container(key="theme_hook"):
    components.html(
        """
        <script>
        const doc = window.parent.document;
        function sync() {
          const app = doc.querySelector('.stApp');
          if (!app) return;
          const rgb = getComputedStyle(app).backgroundColor.match(/\\d+/g).map(Number);
          const brightness = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2];
          doc.documentElement.setAttribute('data-app-theme', brightness < 128 ? 'dark' : 'light');
        }
        sync();
        setInterval(sync, 300);
        </script>
        """,
        height=0,
    )

def style_chart(fig, height=320):
    """Transparent background so the card behind the chart fades with the theme."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="top", y=-0.2, x=0, title_text=""),
    )
    return fig


def show(fig, key):
    st.plotly_chart(fig, use_container_width=True, key=key)


def card_title(text):
    st.markdown(f"#### {text}")


# ── Header ────────────────────────────────────────────────────────────────────
st.title("Marketing Campaign Dashboard")

# ── Load filters ──────────────────────────────────────────────────────────────
@st.cache_data
def fetch_filters():
    return requests.get(f"{API_BASE}/filters").json()

try:
    filters = fetch_filters()
except Exception:
    st.error("Failed to connect to the backend. Make sure the backend is running.")
    st.stop()

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header("Filters")

selected = {}
for col, options in filters.items():
    if options and col != "Date":
        key = f"filter_{col.lower()}"
        title = col.replace("_", " ").title()
        count = len(st.session_state.get(key, []))
        label = f"{title} ({count})" if count else title
        with st.sidebar.container(key=f"fbox_{col.lower()}"):
            with st.expander(label):
                selected[col] = st.multiselect(
                    label=title,
                    options=options,
                    default=[],
                    key=key,
                    label_visibility="collapsed",
                )
                date_options = filters.get("Date", [])
if date_options:
    min_d = pd.to_datetime(min(date_options)).date()
    max_d = pd.to_datetime(max(date_options)).date()
    with st.sidebar.container(key="fbox_date"):
        with st.expander("Date"):
            picked = st.date_input(
                "Date range",
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
                key="filter_date_range",
                label_visibility="collapsed",
            )
    if isinstance(picked, tuple) and len(picked) == 2 and picked != (min_d, max_d):
        valid = set(date_options)
        days = pd.date_range(picked[0], picked[1]).strftime("%Y-%m-%d")
        selected["Date"] = [d for d in days if d in valid]

# ── Fetch filtered data ───────────────────────────────────────────────────────
@st.cache_data
def fetch_data(params_dict):
    response = requests.get(f"{API_BASE}/data", params=params_dict)
    return response.json()

params = {}
for col, values in selected.items():
    if values:
        params[col.lower()] = values

df = pd.DataFrame(fetch_data(params))

# ── KPI cards (respond to the sidebar filters) ────────────────────────────────
kpis = [k for k in compute_kpis(df) if k["label"] != "Total Clicks"]

with st.container(key="kpi_row"):
    for column, kpi in zip(st.columns(len(kpis)), kpis):
        with column:
            with st.container(key=f"card_kpi_{kpi['label'].lower().replace(' ', '_')}"):
                st.metric(kpi["label"], kpi["value"], delta=kpi["delta"], delta_color=kpi["delta_color"])

if df.empty:
    st.warning("No data matches the current filters. Try adjusting your selections.")
    st.stop()

# ── Ranked bars and donuts ────────────────────────────────────────────────────
def ranked_bar(group_col):
    data = top_by_roi(df, group_col)
    fig = px.bar(data, x="ROI", y=group_col, orientation="h", text="ROI")
    fig.update_traces(
        marker=dict(color="rgba(0,0,0,0)"),
        texttemplate="%{x:.2f}x",
        textposition="inside",
        insidetextanchor="start",
                textfont=dict(size=16, color="#e6efeb" if MODE == "dark" else "#1f2d28"),
        cliponaxis=False,
        hovertemplate="%{y}: %{x:.2f}x<extra></extra>",
    )
    fig.update_yaxes(autorange="reversed", title=None, automargin=True)
    fig.update_xaxes(visible=False, range=[0, max(data["ROI"].max() * 1.25, 1)])
    fig.update_layout(showlegend=False)
    return style_chart(fig, 280)


def donut(group_col):
    data = share_by(df, group_col)
    fig = px.pie(data, names=group_col, values="Campaigns", hole=0.62, color_discrete_sequence=COLORS)
    fig.update_traces(textinfo="none", sort=False, marker=dict(line=dict(width=0)),
                      hovertemplate="%{label}: %{value:,} campaigns (%{percent})<extra></extra>")
    fig.add_annotation(text=f"{int(data['Campaigns'].sum()):,}", x=0.5, y=0.5, showarrow=False, font=dict(size=18))
    return style_chart(fig, 280)


with st.container(key="insight_row"):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        with st.container(key="card_companies"):
            card_title("Top Companies by Avg ROI")
            if "Company" in df.columns:
                show(ranked_bar("Company"), "rank_company")
    with c2:
        with st.container(key="card_channels"):
            card_title("Top Channels by Avg ROI")
            if "Channel_Used" in df.columns:
                show(ranked_bar("Channel_Used"), "rank_channel")
    with c3:
        with st.container(key="card_locations"):
            card_title("Campaigns by Location")
            if "Location" in df.columns:
                show(donut("Location"), "donut_location")
    with c4:
        with st.container(key="card_segments"):
            card_title("Campaigns by Segment")
            if "Customer_Segment" in df.columns:
                show(donut("Customer_Segment"), "donut_segment")

# ── Charts ────────────────────────────────────────────────────────────────────
LABELS = {
    "Acquisition_Cost": "Acquisition Cost", "Conversion_Rate": "Conversion Rate",
    "Channel_Used": "Channel", "Customer_Segment": "Customer Segment",
    "Campaign_Type": "Campaign Type",
}


def scatter_with_trend(x, y, color, sample_size):
    sample = df.sample(n=min(sample_size, len(df)), random_state=42)
    fig = px.scatter(
        sample, x=x, y=y, color=color if color in sample.columns else None,
        trendline="ols", color_discrete_sequence=COLORS, labels=LABELS,
    )
    # Hide the points, keep the fitted lines, and move the legend entries to the lines
    fig.update_traces(visible=False, showlegend=False, selector=dict(mode="markers"))
    fig.update_traces(line=dict(width=2.5), showlegend=True, selector=dict(mode="lines"))
    return style_chart(fig)


def box_by(x, y):
    fig = px.box(df, x=x, y=y, color=x, color_discrete_sequence=COLORS, labels=LABELS)
    fig.update_layout(showlegend=False)
    return style_chart(fig)


with st.container(key="chart_row_1"):
    left, right = st.columns(2)
    with left:
        with st.container(key="card_roi_cost"):
            card_title("ROI vs Acquisition cost")
            if "Acquisition_Cost" in df.columns and "ROI" in df.columns:
                show(scatter_with_trend("Acquisition_Cost", "ROI", "Campaign_Type", 5000), "chart_roi_cost")
    with right:
        with st.container(key="card_conversion"):
            card_title("Conversion Rate by Channel")
            if "Channel_Used" in df.columns and "Conversion_Rate" in df.columns:
                show(box_by("Channel_Used", "Conversion_Rate"), "chart_conversion")

with st.container(key="chart_row_2"):
    left, right = st.columns(2)
    with left:
        with st.container(key="card_clicks"):
            card_title("Clicks vs Impressions")
            if "Clicks" in df.columns and "Impressions" in df.columns:
                show(scatter_with_trend("Impressions", "Clicks", "Channel_Used", 3000), "chart_clicks")
    with right:
        with st.container(key="card_segment_cost"):
            card_title("Acquisition cost by Customer Segment")
            if "Customer_Segment" in df.columns and "Acquisition_Cost" in df.columns:
                show(box_by("Customer_Segment", "Acquisition_Cost"), "chart_segment_cost")

# ── Data table ────────────────────────────────────────────────────────────────
with st.container(key="card_table"):
    title_col, button_col = st.columns([4, 1])
    with title_col:
        card_title("Filtered Data")
    with button_col:
        st.download_button("Download CSV", df.to_csv(index=False), "filtered_campaigns.csv", "text/csv")
    st.dataframe(df, use_container_width=True)
    with st.container(key="table_hint"):
        st.caption("↔ Scroll left or right to see more columns")