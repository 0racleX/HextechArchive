from fastapi import APIRouter, Depends

from app.security.auth import CurrentUser, get_current_user

router = APIRouter(tags=["me"])


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"id": user.id, "email": user.email}
