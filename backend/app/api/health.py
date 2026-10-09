from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def health() -> dict:
    """Process liveness; dependency readiness is checked by Docker Compose."""
    return {"data": {"status": "ok"}, "meta": {}}
