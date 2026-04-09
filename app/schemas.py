from pydantic import BaseModel, model_validator,  Field, ConfigDict
from typing import List, Optional

class QABase(BaseModel):
    question: str
    answer: str

class TopicQuestionBase(BaseModel):
    topic_name: Optional[str] = None
    topic_id: Optional[int] = None
    qa: List[QABase]

    @model_validator(mode="after")
    def check_topic(cls, values):
        if not values.topic_name and not values.topic_id:
            raise ValueError("Either topic_name or topic_id must be provided")
        return values

class TopicQuestionCreate(TopicQuestionBase):
    pass

class TopicQuestionResponse(BaseModel):
    id: int
    topic_name: str = Field(validation_alias="name")


    model_config = ConfigDict(
        from_attributes=True
    )


# Shared base — fields used in both create & read
class ItemBase(BaseModel):
    name: str
    description: str | None = None
    is_active: bool = True

# Used for POST body — no id yet
class ItemCreate(ItemBase):
    pass

# Used for responses — includes id from DB
class ItemResponse(ItemBase):
    id: int

    class Config:
        from_attributes = True  # Lets Pydantic read SQLAlchemy objects


# QA Generation

