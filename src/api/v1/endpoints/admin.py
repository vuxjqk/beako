from fastapi import APIRouter, BackgroundTasks, status

from src.api.deps import AdminUser, DbSession
from src.schemas.invitation import InviteUserRequest
from src.schemas.user import UserResponse
from src.services import email_service, invitation_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/invitations", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def invite_user(data: InviteUserRequest, admin: AdminUser, db: DbSession, background_tasks: BackgroundTasks):
    user, token = invitation_service.invite_user(db, data, invited_by=admin)
    db.commit()
    db.refresh(user)
    background_tasks.add_task(
        email_service.send_invitation,
        user.email,
        user.full_name,
        user.role.value,
        invitation_service.build_invitation_link(token),
    )
    return user
