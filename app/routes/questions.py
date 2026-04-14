from http.client import HTTPException
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import crud, schemas
from app.database import  get_db

router = APIRouter(
    prefix="/questions",
    tags=["questions"],
    responses={404: {"description": "Not found"}},
)

# getting the topic questions for the quiz
@router.get("/", response_model=list[schemas.QAResponseGet])
def get_questions(topic_id:int, skip: int = 0, limit: int | None = None, db: Session = Depends(get_db)):
    return crud.question_repo.get_multi(db, skip=skip, limit=limit, filters={"topic_id":topic_id})


@router.post("/create", response_model=schemas.QACreateResponse, status_code=201)
async def createQuestion(question: schemas.QACreateRequest, db: Session = Depends(get_db)):
    return crud.question_repo.create(db, question)

@router.delete("/question/{question_id}", status_code=204)
def delete_item(question_id: int, db: Session = Depends(get_db)):
    deleted = crud.question_repo.delete(db, question_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")



@router.get("/get-deck-card-questions", response_model=list[schemas.QAResponseDeckCardGet])
def get_questions_deckcard(topic_id:int, skip: int = 0, limit: int | None = None, db: Session = Depends(get_db)):
    return crud.question_repo.get_multi(db, skip=skip, limit=limit, filters={"topic_id":topic_id})

@router.put("/update/qa-items/bulk-afterQuiz", response_model=list[schemas.QAResponseGet])
def bulk_update_qa_items(
    items: list[schemas.QAItemUpdate],
    db: Session = Depends(get_db),
):
    if not items:
        raise HTTPException(status_code=400, detail="No items provided")

    updated = crud.question_repo.bulk_update_qa_items(db, items)

    if not updated:
        raise HTTPException(status_code=404, detail="No matching QA items found")


    return updated

