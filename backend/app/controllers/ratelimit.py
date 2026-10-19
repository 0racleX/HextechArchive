import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException

from app.config import Settings, get_settings
from app.security.auth import CurrentUser, get_current_user

WINDOW_SECONDS = 60.0


class SlidingWindowLimiter:
    """Ventana deslizante en memoria por clave; válido para un único proceso."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float = WINDOW_SECONDS) -> int | None:
        """None si la petición cabe en el límite; si no, segundos hasta poder reintentar."""
        if limit <= 0:
            return None
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= window:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, int(window - (now - hits[0]) + 0.999))
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


chat_limiter = SlidingWindowLimiter()
upload_limiter = SlidingWindowLimiter()


def _enforce(limiter: SlidingWindowLimiter, user_id: str, limit: int, what: str) -> None:
    retry = limiter.check(user_id, limit)
    if retry is not None:
        raise HTTPException(
            429, f"Demasiadas {what}. Espera {retry} s antes de intentarlo de nuevo.",
            headers={"Retry-After": str(retry)},
        )


def limit_chat(user: CurrentUser = Depends(get_current_user), settings: Settings = Depends(get_settings)) -> None:
    _enforce(chat_limiter, user.id, settings.rate_limit_chat_per_min, "preguntas")


def limit_upload(user: CurrentUser = Depends(get_current_user), settings: Settings = Depends(get_settings)) -> None:
    _enforce(upload_limiter, user.id, settings.rate_limit_upload_per_min, "subidas de documentos")
