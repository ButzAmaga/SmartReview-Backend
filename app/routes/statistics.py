from fastapi import APIRouter, Depends
from sqlalchemy import func, select, cast, Date, desc
from sqlalchemy.orm import Session # Use standard Session
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Dict
from app.database import  Base, get_db
from app.models import ReviewSession, Topic
from app.schemas import DailyReviewResponse, DailyStatsResponse, DailyStatsResponse2
 
from sqlalchemy import func, select, cast, Date, desc
from datetime import date, timedelta

router = APIRouter(prefix="/stats", tags=["Stats"])

def _start_of_day(d: date) -> datetime:
    return datetime.combine(d, time.min)

def _end_of_day(d: date) -> datetime:
    return datetime.combine(d, time.max)

def get_daily_stats(db: Session) -> DailyStatsResponse:
    today = datetime.now(timezone.utc).date()
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

@router.get("/daily/part_2", response_model=DailyReviewResponse)
def get_today_review_summary(db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).date()

    # Step 1 — Cast start_review to Date for filtering (SQLite datetime strings
    # func.date() extracts the date portion from SQLite's datetime string
    # today.isoformat() converts Python date → "YYYY-MM-DD" string to match
    today_filter = func.date(ReviewSession.start_review) == today.isoformat()

    # Step 2 — Query with aggregations grouped by topic
    results = (
        db.query(
            Topic.id.label("topic_id"),
            Topic.name.label("topic_name"),

            # Step 3 — Compute duration per session in seconds using SQLite's
            # strftime('%s', ...) which converts datetime → Unix epoch seconds.
            # Summing across all sessions in the group gives total seconds,
            # then dividing by 60.0 converts to minutes (float division).
            func.sum(
                (
                    func.strftime("%s", ReviewSession.end_review) * 1
                    - func.strftime("%s", ReviewSession.start_review) * 1
                ) / 60.0
            ).label("total_duration_minutes"),

            # Step 4 — Sum graduated cards across all sessions for this topic
            func.sum(ReviewSession.graduated_cards).label("total_graduated_cards"),
        )
        # Step 5 — Join to Topic to access the name field
        .join(Topic, ReviewSession.topic_id == Topic.id)

        # Step 6 — Only include sessions that started today
        .filter(today_filter)

        # Step 7 — Group by topic so each row = one topic's aggregated stats
        .group_by(Topic.id, Topic.name)
        .all()
    )

    print("Raw DB results for today's review sessions:")
    for row in results:
        print(row)

    # Step 8 — Convert each Row to a dict and validate into the Pydantic model
    summaries = [DailyStatsResponse2.model_validate(row._asdict()) for row in results]

    return DailyReviewResponse(date=today, summaries=summaries)

@router.get("/review-sessions/debug")
def debug_review_sessions(db: Session = Depends(get_db)):
    from sqlalchemy import cast, Date, func
    from datetime import date

    today = date.today()

    # Step 1 — Check ALL sessions raw (no filter)
    all_sessions = db.query(ReviewSession).all()

    # Step 2 — Check what start_review values actually look like
    raw_dates = db.query(
        ReviewSession.id,
        ReviewSession.start_review,
        ReviewSession.end_review,
        ReviewSession.topic_id,
    ).all()

    # Step 3 — Check what cast produces
    cast_check = db.query(
        ReviewSession.id,
        cast(ReviewSession.start_review, Date).label("casted_date"),
    ).all()

    return {
        "today": str(today),
        "total_sessions": len(all_sessions),
        "raw_dates": [
            {
                "id": r.id,
                "start_review": str(r.start_review),
                "end_review": str(r.end_review),
                "topic_id": r.topic_id,
            }
            for r in raw_dates
        ],
        "cast_check": [
            {
                "id": r.id,
                "casted_date": str(r.casted_date),
            }
            for r in cast_check
        ],
    }