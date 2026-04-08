from pydantic import BaseModel

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
