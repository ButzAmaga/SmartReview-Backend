from fastapi import APIRouter, Depends
from sqlalchemy import func, select, cast, Date, desc
from sqlalchemy.orm import Session # Use standard Session
from datetime import date, datetime, time, timedelta
from typing import Annotated, Dict
from app.database import  Base, get_db
from app.models import ReviewSession
from app.schemas import DailyStatsResponse
 
from sqlalchemy import func, select, cast, Date, desc
from datetime import date, timedelta

router = APIRouter(prefix="/stats", tags=["Stats"])

def _start_of_day(d: date) -> datetime:
    return datetime.combine(d, time.min)

def _end_of_day(d: date) -> datetime:
    return datetime.combine(d, time.max)

def get_daily_stats(db: Session) -> DailyStatsResponse:
    today = date.today()
    day_start = _start_of_day(today)
    day_end = _end_of_day(today)

    # 1, 2, & 3: Stats for Today using range comparison (no casting)
    stats_stmt = (
        select(
            func.count(ReviewSession.topic_id.distinct()).label("total_reviews"),
            func.sum(ReviewSession.graduated_cards).label("total_graduated"),
            func.sum(
                func.julianday(ReviewSession.end_review) - 
                func.julianday(ReviewSession.start_review)
            ).label("total_days")
        )
        .where(ReviewSession.start_review >= day_start)
        .where(ReviewSession.start_review <= day_end)
        .where(ReviewSession.end_review.is_not(None))
    )
    
    res = db.execute(stats_stmt).one()
    
    # 4. Streak (Fetching raw datetimes and converting in Python to avoid DB-side TypeErrors)
    streak_stmt = (
        select(ReviewSession.start_review)
        .where(ReviewSession.start_review >= _start_of_day(today - timedelta(days=30)))
        .order_by(desc(ReviewSession.start_review))
    )
    
    # Pull results and convert to dates in Python safely
    results = db.execute(streak_stmt).scalars().all()
    review_dates = sorted({r.date() for r in results if r}, reverse=True)
    
    streak = 0
    if review_dates:
        latest = review_dates[0]
        if latest >= today - timedelta(days=1):
            check_date = latest
            for d in review_dates:
                if d == check_date:
                    streak += 1
                    check_date -= timedelta(days=1)
                else:
                    break

    return DailyStatsResponse(
        total_topic_reviews_today=res.total_reviews or 0,
        total_graduated_cards_today=int(res.total_graduated or 0),
        total_study_time_minutes_today= int((res.total_days or 0) * 1440), # Convert days to minutes
        streak_days=streak,
    )

@router.get("/daily", response_model=DailyStatsResponse)
def daily_stats(db: Annotated[Session, Depends(get_db)]):
    return get_daily_stats(db)