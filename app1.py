import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from googleapiclient.discovery import build
import datetime

# API Key
API_KEY = "AIzaSyAWJf-FFAm5PgDLcWeilNdOgpZU9uCpMXI"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# ---------- Function to Load CSV ----------
@st.cache_data
def load_csv():
    df = pd.read_csv("youtube_data.csv")

    df = df[df['viewCount'].astype(str).str.replace(',', '').str.isnumeric()]
    df['viewCount'] = df['viewCount'].astype(str).str.replace(',', '').astype(int)

    def parse_duration(duration):
        try:
            if isinstance(duration, str) and ':' in duration:
                time_parts = duration.split(':')
                if len(time_parts) == 3:
                    h, m, s = map(int, time_parts)
                    return h * 60 + m + s / 60
                elif len(time_parts) == 2:
                    m, s = map(int, time_parts)
                    return m + s / 60
            return None
        except:
            return None

    df['duration_minutes'] = df['duration'].apply(parse_duration)
    df['pub_date'] = pd.to_datetime(df['pub_date'], errors='coerce').dt.tz_localize(None)
    df['date_ref'] = pd.to_datetime(df['date_ref'], errors='coerce')
    df['publishedTime'] = pd.to_datetime(df['publishedTime'], errors='coerce')

    return df.dropna(subset=['pub_date', 'duration_minutes'])

# ---------- Function to Fetch Live YouTube Data ----------
def get_trending_videos():
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)

    request = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        chart="mostPopular",
        regionCode="IN",
        maxResults=50
    )
    response = request.execute()

    rows = []
    for item in response['items']:
        snippet = item['snippet']
        stats = item.get('statistics', {})
        content = item.get('contentDetails', {})

        view_count = int(stats.get('viewCount', 0))
        tags = snippet.get('tags', [])
        duration_iso = content.get('duration', 'PT0M0S')

        # Convert ISO 8601 Duration
        import isodate
        try:
            duration_timedelta = isodate.parse_duration(duration_iso)
            duration_minutes = duration_timedelta.total_seconds() / 60
        except:
            duration_minutes = None

        rows.append({
            'title': snippet['title'],
            'publishedTime': snippet['publishedAt'],
            'pub_date': snippet['publishedAt'],
            'duration_minutes': duration_minutes,
            'viewCount': view_count,
            'hashtag': ' '.join(tags) if tags else None,
            'category': snippet.get('categoryId', 'Unknown'),
            'date_ref': datetime.datetime.today()
        })

    df_live = pd.DataFrame(rows)
    df_live['pub_date'] = pd.to_datetime(df_live['pub_date'], errors='coerce').dt.tz_localize(None)
    df_live['publishedTime'] = pd.to_datetime(df_live['publishedTime'], errors='coerce')
    return df_live

# ----------------- Dashboard -----------------

st.set_page_config(page_title="YouTube Trend Analyzer", layout="wide")
st.title("📊 YouTube Trend Analyzer")
st.markdown("Analyze static or live YouTube trending data. Powered by CSV + YouTube API.")

# Data Source Toggle
data_source = st.radio("Choose Data Source", ['📁 Uploaded CSV', '🌐 Live Trending Videos (API)'])

# Load data accordingly
if data_source == '📁 Uploaded CSV':
    df = load_csv()
else:
    st.warning("Fetching live data... this may take a few seconds.")
    df = get_trending_videos()

# Sidebar filters
st.sidebar.header("Filters")
categories = df['category'].dropna().unique().tolist()
selected_categories = st.sidebar.multiselect("Select Categories", categories, default=categories)

date_min = df['pub_date'].min().date()
date_max = df['pub_date'].max().date()
date_range = st.sidebar.date_input("Publication Date Range", [date_min, date_max])

# Apply filters
filtered_df = df[
    (df['category'].isin(selected_categories)) &
    (df['pub_date'] >= pd.to_datetime(date_range[0])) &
    (df['pub_date'] <= pd.to_datetime(date_range[1]))
]

# KPIs
col1, col2, col3 = st.columns(3)
col1.metric("Total Videos", len(filtered_df))
col2.metric("Average Views", f"{filtered_df['viewCount'].mean():,.0f}")
col3.metric("Avg Duration (min)", f"{filtered_df['duration_minutes'].mean():.2f}")

# Line Chart - Views over time
st.subheader("📈 Views Over Time")
if 'date_ref' in filtered_df.columns:
    views_by_date = filtered_df.groupby('date_ref')['viewCount'].sum().reset_index()
    fig1 = px.line(views_by_date, x='date_ref', y='viewCount', title='Total Views by Trending Date')
    st.plotly_chart(fig1, use_container_width=True)

# Top Videos Table
st.subheader("🔥 Top 10 Videos")
top_videos = filtered_df.sort_values(by='viewCount', ascending=False).head(10)
st.dataframe(top_videos[['title', 'category', 'viewCount', 'duration_minutes', 'pub_date']])

# Category Bar Chart
st.subheader("📂 Views by Category")
views_by_cat = filtered_df.groupby('category')['viewCount'].sum().sort_values(ascending=False).reset_index()
fig2 = px.bar(views_by_cat, x='category', y='viewCount', title='Total Views by Category', color='viewCount')
st.plotly_chart(fig2, use_container_width=True)

# Duration vs Views Scatter
st.subheader("⏱️ Duration vs Views")
fig3 = px.scatter(filtered_df, x='duration_minutes', y='viewCount', color='category',
                  hover_data=['title'], title='Duration vs Views', trendline='ols')
st.plotly_chart(fig3, use_container_width=True)

# Word Cloud
st.subheader("🌐 Hashtag Cloud")
all_tags = ' '.join(filtered_df['hashtag'].dropna().astype(str))
if all_tags:
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(all_tags)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis("off")
    st.pyplot(fig)
else:
    st.info("No hashtags available.")

# Optional Full Data
with st.expander("🔍 View Full Data"):
    st.dataframe(filtered_df, use_container_width=True)
