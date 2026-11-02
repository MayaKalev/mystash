from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Item, User
from app.queue import queue
from app.schemas import ItemCreate, ItemOut
from app.tasks import process_item

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemOut, status_code=201)
def create_item(
    body: ItemCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Save a link. The worker fetches and processes it in the background."""
    item = Item(user_id=user.id, url=str(body.url), status="pending")
    db.add(item)
    db.commit()
    db.refresh(item)

    queue.enqueue(process_item, item.id)
    return item


@router.get("", response_model=list[ItemOut])
def list_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The user's saved links, newest first."""
    return db.scalars(
        select(Item).where(Item.user_id == user.id).order_by(Item.created_at.desc(), Item.id.desc())
    ).all()


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    # Another user's item gets the same reply, so nobody can tell which ids exist.
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
