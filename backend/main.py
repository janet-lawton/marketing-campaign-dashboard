from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from data_loader import load_data, get_filter_options
from typing import Optional, List
from contextlib import asynccontextmanager
import pandas as pd

df = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global df
    df = load_data()
    yield

app = FastAPI(title="Marketing Campaign API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/filters")
def get_filters():
    return get_filter_options(df)

@app.get("/data")
def get_data(
    company: Optional[List[str]] = Query(None),
    campaign_type: Optional[List[str]] = Query(None),
    target_audience: Optional[List[str]] = Query(None),
    channel_used: Optional[List[str]] = Query(None),
    location: Optional[List[str]] = Query(None),
    language: Optional[List[str]] = Query(None),
    customer_segment: Optional[List[str]] = Query(None),
    duration: Optional[List[str]] = Query(None),
):
    filtered = df.copy()
    if company:
        filtered = filtered[filtered["Company"].isin(company)]
    if campaign_type:
        filtered = filtered[filtered["Campaign_Type"].isin(campaign_type)]
    if target_audience:
        filtered = filtered[filtered["Target_Audience"].isin(target_audience)]
    if channel_used:
        filtered = filtered[filtered["Channel_Used"].isin(channel_used)]
    if location:
        filtered = filtered[filtered["Location"].isin(location)]
    if language:
        filtered = filtered[filtered["Language"].isin(language)]
    if customer_segment:
        filtered = filtered[filtered["Customer_Segment"].isin(customer_segment)]
    if duration:
        filtered = filtered[filtered["Duration"].isin(duration)]
    filtered["Date"] = filtered["Date"].astype(str)
    return filtered.to_dict(orient="records")

@app.get("/summary")
def get_summary():
    return {
        "total_campaigns": len(df),
        "avg_roi": round(df["ROI"].mean(), 2),
        "avg_conversion_rate": round(df["Conversion_Rate"].mean(), 4),
        "avg_acquisition_cost": round(df["Acquisition_Cost"].mean(), 2),
        "total_clicks": int(df["Clicks"].sum()),
        "total_impressions": int(df["Impressions"].sum()),
        "avg_engagement_score": round(df["Engagement_Score"].mean(), 2),
    }
