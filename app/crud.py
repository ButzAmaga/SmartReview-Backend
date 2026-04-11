from sqlalchemy.orm import Session
from app import models, schemas, database
from sqlalchemy import select
from fastapi import HTTPException
from typing import Type, TypeVar, Generic, List
from app.database import Base

### Generic 

# Define a TypeVar that represents any SQLAlchemy model
T = TypeVar("T", bound=Base) 

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model

    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int | None = None, 
        filters: dict | None = None
    ) -> List[T]:
        query = db.query(self.model)
        
        if filters:
            for attr, value in filters.items():
                # Handle dynamic operators using a __ separator
                if "__" in attr:
                    column_name, operator = attr.split("__")
                    column = getattr(self.model, column_name)
                    
                    if operator == "gt": query = query.filter(column > value)
                    elif operator == "lt": query = query.filter(column < value)
                    elif operator == "gte": query = query.filter(column >= value)
                    elif operator == "lte": query = query.filter(column <= value)
                else:
                    # Default to equality if no operator is specified
                    query = query.filter(getattr(self.model, attr) == value)
                    
        return query.offset(skip).limit(limit).all()

def createtopicQuestion(db: Session, item: schemas.TopicQuestionBase):
    # 1. Resolve Topic (reuse or create)
    db_topic = None

    if item.topic_id:
        db_topic = db.get(models.Topic, item.topic_id)
        if not db_topic:
            raise HTTPException(status_code=404, detail="Topic not found")

    elif item.topic_name:
        # Check if topic already exists (idempotency)
        db_topic = db.execute(
            select(models.Topic).where(models.Topic.name == item.topic_name)
        ).scalar_one_or_none()

        if not db_topic:
            db_topic = models.Topic(name=item.topic_name)
            db.add(db_topic)
            db.flush()  # get id without commit

    else:
        raise HTTPException(status_code=400, detail="Provide topic_id or topic_name")

    # 2. Get existing questions (avoid duplicates)
    existing_questions = set(
        q[0] for q in db.execute(
            select(models.QAItem.question).where(models.QAItem.topic_id == db_topic.id)
        ).all()
    )

    # 3. Prepare new QAItems (bulk + dedup)
    new_items = [
        models.QAItem(
            question=qa.question,
            answer=qa.answer,
            topic_id=db_topic.id
        )
        for qa in item.qa
        if qa.question not in existing_questions
    ]

    # 4. Bulk save (fast)
    if new_items:
        db.bulk_save_objects(new_items)

    # 5. Commit once
    db.commit()

    # 6. Refresh topic with relationships
    db.refresh(db_topic)

    return db_topic


class TopicRepository(BaseRepository[models.Topic]):
    def __init__(self):
        super().__init__(models.Topic)

class QuestionRepository(BaseRepository[models.QAItem]):
    def __init__(self):
        super().__init__(models.QAItem)

# Repository Export
topic_repo = TopicRepository()
question_repo = QuestionRepository()

"""
def get_topics(db: Session, item_id: int):
    return db.query(models.Item).filter(models.Item.id == item_id).first()

def get_item(db: Session, item_id: int):
    return db.query(models.Item).filter(models.Item.id == item_id).first()

def get_items(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Item).offset(skip).limit(limit).all()

def create_item(db: Session, item: schemas.ItemCreate):
    db_item = models.Item(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)  # Loads the new id back into the object
    return db_item

def update_item(db: Session, item_id: int, item: schemas.ItemCreate):
    db_item = get_item(db, item_id)
    if db_item:
        for key, value in item.model_dump().items():
            setattr(db_item, key, value)
        db.commit()
        db.refresh(db_item)
    return db_item

def delete_item(db: Session, item_id: int):
    db_item = get_item(db, item_id)
    if db_item:
        db.delete(db_item)
        db.commit()
    return db_item
"""