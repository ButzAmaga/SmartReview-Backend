from pydantic import BaseModel, model_validator,  Field, ConfigDict
from typing import List, Optional

## QUESTION

# Base
class QABase(BaseModel):
    question: str
    answer: str

# Create

class QACreateRequest(QABase):
    topic_id:int

class QACreateResponse(QABase):
    id:int
    topic_id:int
    model_config = ConfigDict(from_attributes=True)

# Delete
class QADeleteRequest():
    id:int

class QADeleteResponse(QACreateResponse):
    pass

# Update

class QAUpdateRequest(QABase):
    pass

class QAUpdateResponse(QABase):
    id:int
    model_config = ConfigDict(from_attributes=True)
    pass

# Bulk Update 
class QAItemUpdate(BaseModel):
    id: int
    next_review: int
    current_step_index: int
    ease_factor: float
    interval: int
    phase: str

class QAItemUpdateAdvanceRequest(BaseModel):
    id: int
    next_review: int

# Get Question
class QAResponseGet(QABase, QAItemUpdate):
    model_config = ConfigDict(from_attributes=True)

# Get question for deck card
class QAResponseDeckCardGet(QABase):
    id: int
    next_review: int
    model_config = ConfigDict(from_attributes=True)

## TOPIC 

class TopicBase(BaseModel):
    topic_name: str = Field(validation_alias="name")

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

class TopicResponseGet(TopicBase):
    id: int
    

    model_config = ConfigDict(from_attributes=True)

class TopicWithQuestionCountResponseGet(TopicBase):
    
    id: int
    number_of_questions: int # New field

    class Config:
        from_attributes = True # Allows Pydantic to read the added attribute

class QA_items_instance(BaseModel):
    id:int
    next_review:int

class TopicWithQuestionResponseGet(TopicBase):

    id: int
    qa_items: list[QA_items_instance]

    class Config:
        from_attributes = True # Allows Pydantic to read the added attribute


# LOGS

class ReviewSessionRequest(BaseModel):
    
    # These match your hybrid_property names exactly.
    # Pydantic will accept ISO strings and your SQLAlchemy 
    # setter will convert them to datetime objects automatically.
    start_review: str 
    end_review: str

    # Snapshot stats
    graduated_cards: int = 0
    learning_cards: int = 0
    relearning_cards: int = 0
    new_cards: int = 0

class ReviewSessionResponse(ReviewSessionRequest):
    id: int
    duration_minutes: float
    
    # Pydantic v2 uses model_config instead of class Config
    model_config = ConfigDict(from_attributes=True)    