import uuid

from fastapi import APIRouter, BackgroundTasks, status

from src.api.deps import AdminUser, DbSession
from src.models import User
from src.schemas.common import MessageResponse
from src.schemas.invitation import InviteUserRequest
from src.schemas.user import UserResponse
from src.services import email_service, invitation_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _send_invitation_email(background_tasks: BackgroundTasks, user: User, token: str) -> None:
    background_tasks.add_task(
        email_service.send_invitation,
        user.email,
        user.full_name,
        user.role.value,
        invitation_service.build_invitation_link(token),
    )


@router.post("/invitations", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def invite_user(data: InviteUserRequest, admin: AdminUser, db: DbSession, background_tasks: BackgroundTasks):
    user, token = invitation_service.invite_user(db, data, invited_by=admin)
    db.commit()
    db.refresh(user)
    _send_invitation_email(background_tasks, user, token)
    return user


@router.post(
    "/invitations/{user_id}/resend", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
def resend_invitation(user_id: uuid.UUID, admin: AdminUser, db: DbSession, background_tasks: BackgroundTasks):
    user, token = invitation_service.resend_invitation(db, user_id, invited_by=admin)
    db.commit()
    _send_invitation_email(background_tasks, user, token)
    return MessageResponse(message="Invitation resent")
