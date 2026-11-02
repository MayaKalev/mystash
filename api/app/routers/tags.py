from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ItemTag, Tag, User
from app.schemas import TagOut

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The user's tags that are on at least one item, A to Z. Used for the tag filter."""
    in_use = select(ItemTag.tag_id)
    return db.scalars(
        select(Tag).where(Tag.user_id == user.id, Tag.id.in_(in_use)).order_by(Tag.name)
    ).all()
