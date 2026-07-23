import datetime as dt
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from .database import get_db
from . import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_secret(secret: str) -> str:
    return pwd_context.hash(secret)


def verify_secret(secret: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return pwd_context.verify(secret, hashed)
    except Exception:
        return False


def create_access_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = data.copy()
    expire = dt.datetime.utcnow() + dt.timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nicht angemeldet oder Sitzung abgelaufen",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    payload = decode_token(token)
    if not payload:
        raise credentials_exception
    username = payload.get("sub")
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.active:
        raise credentials_exception
    return user


def require_roles(*roles):
    """Erlaubt Zugriff, wenn der Benutzer MINDESTENS eine der angegebenen Rollen besitzt
    (ein Benutzer kann mehrere Rollen gleichzeitig haben)."""
    wanted = [r.value if hasattr(r, "value") else r for r in roles]

    def checker(user: models.User = Depends(get_current_user)):
        if wanted and not user.has_role(*wanted):
            raise HTTPException(status_code=403, detail="Keine Berechtigung fuer diese Aktion")
        return user
    return checker
