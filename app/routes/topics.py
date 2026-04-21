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

@router.get("/", response_model=list[schemas.TopicWithQuestionCountResponseGet])
def read_topics(skip: int = 0, limit: int | None = None, db: Session = Depends(get_db)):
    return crud.topic_repo.get_topics_with_counts(db, skip=skip, limit=limit)

@router.delete("/topic/{topic_id}", status_code=204)
def delete_item(topic_id: int, db: Session = Depends(get_db)):
    deleted = crud.topic_repo.delete(db, topic_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")