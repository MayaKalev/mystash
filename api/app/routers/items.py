from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai import normalize_tags
from app.auth import get_current_user
from app.database import get_db
from app.models import Item, ItemTag, Tag, User
from app.queue import queue
from app.schemas import ItemCreate, ItemOut, TagsUpdate
from app.tasks import get_or_create_tag, process_item

router = APIRouter(prefix="/items", tags=["items"])

# More than the AI's 5, so users can add their own, but still a sensible limit.
MAX_USER_TAGS = 20


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
def list_items(
    status: str | None = None,
    content_type: str | None = None,
    tag: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The user's saved links, newest first. Each filter is optional."""
    query = select(Item).where(Item.user_id == user.id)
    if status:
        query = query.where(Item.status == status)
    if content_type:
        query = query.where(Item.content_type == content_type)
    if tag:
        tagged = select(ItemTag.item_id).join(Tag).where(Tag.user_id == user.id, Tag.name == tag)
        query = query.where(Item.id.in_(tagged))

    return db.scalars(query.order_by(Item.created_at.desc(), Item.id.desc())).all()


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return find_own_item(db, user, item_id)


@router.put("/{item_id}/tags", response_model=ItemOut)
def update_tags(
    item_id: int,
    body: TagsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replace the item's tags with this list. New tags are saved with source "user"."""
    item = find_own_item(db, user, item_id)
    # The worker adds the AI's tags at the end of processing, and the two could clash.
    if item.status in ("pending", "processing"):
        raise HTTPException(status_code=409, detail="Wait until the link has been processed")

    names = normalize_tags(body.tags, limit=MAX_USER_TAGS)
    current = {tag.name: tag for tag in item.tags}

    removed_ids = [tag.id for name, tag in current.items() if name not in names]
    if removed_ids:
        db.execute(
            delete(ItemTag).where(ItemTag.item_id == item.id, ItemTag.tag_id.in_(removed_ids))
        )

    # Tags the item already has keep their source, so an AI tag stays "ai".
    for name in names:
        if name not in current:
            tag = get_or_create_tag(db, user.id, name)
            db.add(ItemTag(item_id=item.id, tag_id=tag.id, source="user"))

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Delete a saved link. The database removes its item_tags rows by itself."""
    item = find_own_item(db, user, item_id)
    db.delete(item)
    db.commit()


def find_own_item(db: Session, user: User, item_id: int) -> Item:
    item = db.get(Item, item_id)
    # Another user's item gets the same reply, so nobody can tell which ids exist.
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
