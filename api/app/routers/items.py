from fastapi import APIRouter, Depends
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
