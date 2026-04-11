from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import crud, schemas
from app.database import  get_db

router = APIRouter(
    prefix="/questions",
    tags=["questions"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=list[schemas.QAResponseGet])
def get_questions(topic_id:int, skip: int = 0, limit: int | None = None, db: Session = Depends(get_db)):
    return crud.question_repo.get_multi(db, skip=skip, limit=limit, filters={"topic_id":topic_id})
