from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float, DateTime, func
from app.database import Base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional

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

    # meta data

 
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

# v2.0 
class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Timestamps
    start_review: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    end_review: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Session Stats (Snapshots)
    graduated_cards: Mapped[int] = mapped_column(Integer, default=0)
    learning_cards: Mapped[int] = mapped_column(Integer, default=0)
    relearning_cards: Mapped[int] = mapped_column(Integer, default=0)

    # Derived Attribute: Duration (Calculated on the fly)
    @property
    def duration_minutes(self) -> float:
        if self.start_review and self.end_review:
            delta = self.end_review - self.start_review
            return round(delta.total_seconds() / 60, 2)
        return 0.0    