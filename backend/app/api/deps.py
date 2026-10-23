from typing import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models.meeting import Attendee, Meeting
from app.db.models.user import User, UserRole
from app.db.session import get_db

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> User:
    """Retrieve the authenticated user based on JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    """Dependency guard enforcing role-based access control."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {[r.value for r in allowed_roles]}, user has: {current_user.role.value}",
            )
        return current_user

    return role_checker


MEETING_MANAGERS = {UserRole.CHAIRMAN, UserRole.PRINCIPAL, UserRole.HOD}


def is_meeting_manager(user: User) -> bool:
    """Managers can access the university represented by this single-department app."""
    return user.role in MEETING_MANAGERS


def can_view_meeting(db: Session, meeting: Meeting, user: User) -> bool:
    if is_meeting_manager(user):
        return True
    if user.role == UserRole.STUDENT:
        return (
            db.query(Attendee.id)
            .filter(Attendee.meeting_id == meeting.id, Attendee.user_id == user.id)
            .first()
            is not None
        )
    if user.role == UserRole.TEACHER:
        return meeting.organizer_id == user.id or (
            db.query(Attendee.id)
            .filter(Attendee.meeting_id == meeting.id, Attendee.user_id == user.id)
            .first()
            is not None
        )
    return False


def require_meeting_access(db: Session, meeting: Meeting, user: User) -> None:
    if not can_view_meeting(db, meeting, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this meeting.",
        )


def visible_meetings_query(db: Session, user: User):
    query = db.query(Meeting)
    if is_meeting_manager(user):
        return query
    if user.role == UserRole.STUDENT:
        return query.join(Attendee).filter(Attendee.user_id == user.id)
    if user.role == UserRole.TEACHER:
        return query.filter(
            or_(
                Meeting.organizer_id == user.id,
                Meeting.id.in_(
                    db.query(Attendee.meeting_id).filter(Attendee.user_id == user.id)
                ),
            )
        )
    return query.filter(Meeting.id == -1)
