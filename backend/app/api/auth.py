from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.repositories.auth import AuthRepository
from app.schemas.auth import AuthResponse, Credentials, MeResponse, RefreshRequest, UserResponse
from app.services.auth import AuthService
from app.services.rate_limit import AuthRateLimiter

router = APIRouter(prefix="/api/v1", tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)


def prevent_caching(response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


router.dependencies.append(Depends(prevent_caching))


def get_auth_service(
    session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)
):
    return AuthService(AuthRepository(session), settings)


def get_rate_limiter(request: Request, settings: Settings = Depends(get_settings)):
    return AuthRateLimiter(request.app.state.redis, settings)


async def rate_limit(request: Request, limiter=Depends(get_rate_limiter)):
    await limiter.check(request.client.host if request.client else "unknown")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    service: AuthService = Depends(get_auth_service),
):
    if credentials is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    return await service.current_user(credentials.credentials)


@router.post(
    "/auth/register",
    response_model=AuthResponse,
    status_code=201,
    dependencies=[Depends(rate_limit)],
)
async def register(body: Credentials, service: AuthService = Depends(get_auth_service)):
    return {"data": await service.register(body)}


@router.post("/auth/login", response_model=AuthResponse, dependencies=[Depends(rate_limit)])
async def login(body: Credentials, service: AuthService = Depends(get_auth_service)):
    return {"data": await service.login(body)}


@router.post("/auth/refresh", response_model=AuthResponse, dependencies=[Depends(rate_limit)])
async def refresh(body: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    return {"data": await service.refresh(body.refresh_token.get_secret_value())}


@router.post("/auth/logout", status_code=204)
async def logout(body: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    await service.logout(body.refresh_token.get_secret_value())
    return Response(status_code=204)


@router.get("/users/me", response_model=MeResponse)
async def me(user=Depends(get_current_user)):
    return {"data": UserResponse.model_validate(user)}
