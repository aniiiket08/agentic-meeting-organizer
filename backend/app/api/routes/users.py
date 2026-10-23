from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.db.models.user import User, UserRole
from app.db.schemas.user import UserDirectoryEntry

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserDirectoryEntry])
def list_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_roles(UserRole.CHAIRMAN, UserRole.PRINCIPAL, UserRole.HOD, UserRole.TEACHER)
    ),
) -> list[User]:
    """Return the university member directory to authenticated users."""
    return db.query(User).order_by(User.name, User.email).all()