"""Claim before other writes in the caller's transaction; failed actions can retry."""
from sqlalchemy.exc import IntegrityError

from ..models import ActionReceipt


def claim_action(db, user_id: str, key: str) -> tuple[ActionReceipt, bool]:
    existing = db.query(ActionReceipt).filter_by(user_id=user_id, action_key=key).one_or_none()
    if existing is not None:
        return existing, False
    receipt = ActionReceipt(user_id=user_id, action_key=key)
    try:
        db.add(receipt)
        db.flush()
    except IntegrityError:
        db.rollback()
        return db.query(ActionReceipt).filter_by(user_id=user_id, action_key=key).one(), False
    return receipt, True
