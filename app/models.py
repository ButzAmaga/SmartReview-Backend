from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float, DateTime, func
from app.database import Base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.hybrid import hybrid_property


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

    # Add this to link back to ReviewSession
    review_sessions: Mapped[list["ReviewSession"]] = relationship(
        "ReviewSession", back_populates="topic", cascade="all, delete-orphan"
    )


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

    context = Column(String, nullable=True, default="no context")

    topic = relationship("Topic", back_populates="qa_items")



class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # 1. Add the Foreign Key column
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), server_default="1" )

    # 2. Add the relationship to Topic
    topic: Mapped["Topic"] = relationship(back_populates="review_sessions")
    
    # Storage columns
    start_review: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_review: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Session Stats
    graduated_cards: Mapped[int] = mapped_column(Integer, default=0)
    learning_cards: Mapped[int] = mapped_column(Integer, default=0)
    relearning_cards: Mapped[int] = mapped_column(Integer, default=0)
    new_cards: Mapped[int] = mapped_column(Integer, default=0)
    review_cards: Mapped[int] = mapped_column(Integer, default=0)
 