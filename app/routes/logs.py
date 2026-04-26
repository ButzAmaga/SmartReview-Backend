from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud, schemas
from app.database import  get_db

router = APIRouter(
    prefix="/logs",
    tags=["logs"],
    responses={404: {"description": "Not found"}},
)

@router.post("/review_session", response_model=schemas.ReviewSessionResponse, status_code=201)
def create_review_session(log: schemas.ReviewSessionRequest, db: Session = Depends(get_db)):
    return crud.reviewSession_repo.create(db, obj_in=log)