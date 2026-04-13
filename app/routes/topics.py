from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud, schemas
from app.database import  get_db

router = APIRouter(
    prefix="/topics",
    tags=["topics"],
    responses={404: {"description": "Not found"}},
)

@router.post("/saveTopicQuestions/", response_model=schemas.TopicQuestionResponse, status_code=201)
async def saveTopicQuestions(topicQuestions: schemas.TopicQuestionCreate, db: Session = Depends(get_db)):
    return crud.createtopicQuestion(db, topicQuestions)

@router.get("/", response_model=list[schemas.TopicResponseGet])
def read_topics(skip: int = 0, limit: int | None = None, db: Session = Depends(get_db)):
    return crud.topic_repo.get_multi(db, skip=skip, limit=limit)

"""
@app.post("/items/", response_model=schemas.ItemResponse, status_code=201)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, item)
"""

