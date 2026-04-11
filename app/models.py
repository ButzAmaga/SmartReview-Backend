from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float
from app.database import Base
from sqlalchemy.orm import relationship

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    age = Column(Integer, nullable=True)



class Topic(Base):
    __tablename__ = "topics"
 
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
 
    qa_items = relationship("QAItem", back_populates="topic", cascade="all, delete-orphan")
 
 
class QAItem(Base):
    __tablename__ = "qa_items"
 
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)

    # Spaced Repetition / State
    next_review = Column(Integer, nullable=False, default=0)
    current_step_index = Column(Integer, nullable=False, default=0)
    ease_factor = Column(Float, nullable=False, default=2.5)
    interval = Column(Integer, nullable=False, default=0)
    phase = Column(String, nullable=False, default="new") 

    topic = relationship("Topic", back_populates="qa_items")