from sqlalchemy.orm import Session, joinedload
from app import models, schemas, database
from sqlalchemy import select, func
from fastapi import HTTPException
from typing import Type, TypeVar, Generic, List, Never
from app.database import Base
import time
from datetime import datetime, time, timezone

### Generic 

# Define a TypeVar that represents any SQLAlchemy model
from typing import Generic, TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

# T is for model
# CreateSchemaType of create input type
# UpdateSchemaType for update input type
class BaseRepository(Generic[T, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[T]):
        self.model = model

    def get(self, db: Session, id: int) -> T | None:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int | None = None,
        filters: dict | None = None,
    ) -> list[T]:
        query = db.query(self.model)

        if filters:
            for attr, value in filters.items():
                if "__" in attr:
                    column_name, operator = attr.split("__")
                    column = getattr(self.model, column_name)

                    if operator == "gt":    query = query.filter(column > value)
                    elif operator == "lt":  query = query.filter(column < value)
                    elif operator == "gte": query = query.filter(column >= value)
                    elif operator == "lte": query = query.filter(column <= value)
                else:
                    query = query.filter(getattr(self.model, attr) == value)

        return query.offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: CreateSchemaType) -> T:
        obj = self.model(**obj_in.model_dump())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, id: int, obj_in: UpdateSchemaType) -> T | None:
        obj = self.get(db, id)
        if not obj:
            return None

        for field, value in obj_in.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)

        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, id: int) -> T | None:
        obj = self.get(db, id)
        if not obj:
            return None

        db.delete(obj)
        db.commit()
        return obj
    
   
        obj = self.get(db, id)
        if not obj:
            return None

        db.delete(obj)
        db.commit()
        return obj

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


class TopicRepository(BaseRepository[models.Topic, Never, Never]):
    def __init__(self):
        super().__init__(models.Topic)

    def get_topics_with_counts(self, db: Session, skip: int = 0, limit: int | None = None):
        # 1. Get the current date and time
        current_time = datetime.now(timezone.utc)

        # 2. Reset time components to 00:00:00
        midnight = datetime.combine(current_time.date(), time.min, tzinfo=timezone.utc)

        # 3. Convert back to integer timestamp
        now = int(midnight.timestamp())
        
        # Query Topic and the count of related QAItems due for review
        results = (
            db.query(
                self.model, 
                func.count(models.QAItem.id).label("number_of_questions")
            )
            .outerjoin(models.QAItem, (self.model.id == models.QAItem.topic_id) & (models.QAItem.next_review <= now))
            .group_by(self.model.id)
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        # Merge the count into the Topic object's attributes for the schema
        for topic, count in results:
            topic.number_of_questions = count
            
        return [r[0] for r in results]

    def get_topics_with_all_questions(self, db: Session, skip: int = 0, limit: int | None = None):
        # Create a statement
        stmt = (
            select(self.model)
            .options(joinedload(self.model.qa_items))
            .offset(skip)
            .limit(limit)
        )
        
        # Execute, apply unique, and get scalars (the objects)
        result = db.execute(stmt)
        return result.unique().scalars().all()
    

class QuestionRepository(BaseRepository[models.QAItem, schemas.QACreateResponse, schemas.QAUpdateRequest]):
    def __init__(self):
        super().__init__(models.QAItem)

    def bulk_update_qa_items(self, db: Session, items: list[schemas.QAItemUpdate]) -> list[models.QAItem]:
        if not items:
            return []

        # Build a list of dicts for bulk update
        mappings = [
            {
                "id": item.id,
                "next_review": item.next_review,
                "current_step_index": item.current_step_index,
                "ease_factor": item.ease_factor,
                "interval": item.interval,
                "phase": item.phase,
            }
            for item in items
        ]

        # Single bulk UPDATE — one round trip
        db.bulk_update_mappings(models.QAItem, mappings)
        db.commit()

        # Single SELECT to return updated rows
        ids = [item.id for item in items]
        return db.query(models.QAItem).filter(models.QAItem.id.in_(ids)).all()

    def bulk_update_qa_items_advance(self, db: Session, items: list[schemas.QAItemUpdateAdvanceRequest]) -> list[models.QAItem]:
        if not items:
            return []

        # Build a list of dicts for bulk update
        mappings = [
            {
                "id": item.id,
                "next_review": item.next_review,
            }
            for item in items
        ]

        # Single bulk UPDATE — one round trip
        db.bulk_update_mappings(models.QAItem, mappings)
        db.commit()

        # Single SELECT to return updated rows
        ids = [item.id for item in items]
        return db.query(models.QAItem).filter(models.QAItem.id.in_(ids)).all()

class ReviewSessionRepository(BaseRepository[models.ReviewSession, schemas.ReviewSessionRequest, Never]):
    def __init__(self):
        super().__init__(models.ReviewSession)

    def create(self, db: Session, obj_in: CreateSchemaType) -> T:
        # 1. Create an empty instance of the model
        obj = self.model()
        
        # 2. Use setattr for each field (this triggers @property.setter) (the default repository create sees _review but not the getter so it is needed to do manually)
        for field, value in obj_in.model_dump().items():
            setattr(obj, field, value)
            
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj    
    

# Repository Export
topic_repo = TopicRepository()
question_repo = QuestionRepository()
reviewSession_repo = ReviewSessionRepository()

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