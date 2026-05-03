from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from config import settings
from typing import Annotated
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from config import settings



# datetime → token expiry time
# jwt → create/verify tokens
# OAuth2PasswordBearer → extracts token from request
# PasswordHash → secure password hashing
# settings → secret key, algorithm, expiry
# timedelta → duration of time like 30 minutes

password_hash = PasswordHash.recommended() # It is hashed instead of encrypted as encrytion can be reversed and hash cannot

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")

def hash_password(password : str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password : str, hashed_password : str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(data : dict, expires_delta : timedelta | None = None) -> str:
    """ Create a JWT access token """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta

    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp" : expire})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key.get_secret_value(), algorithm=settings.algorithm)

    return encoded_jwt
    


def verify_access_token(token : str) -> str | None:
    """ Verify a JWT token and return the subject (user id) if valid """
   
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=[settings.algorithm], options={"require" : ["exp", "sub"]})

        # options={"require" : ["exp", "sub"]} -> Token MUST contain:
        #                                             - exp (expiry)
        #                                             - sub (user id)

    except jwt.InvalidTokenError:
        return None # return -> None if invalid token
    
    else:
        return payload.get("sub")  # means token is valid -> return user_id
    


async def get_current_user(db : Annotated[AsyncSession, Depends(get_db)], token : Annotated[str, Depends(oauth2_scheme)]):

    # Get the currently authenticated user
    user_id = verify_access_token(token)

    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, deatail="Invalid or Expired token", headers={"WWW-Authenticate" : "Bearer"})
    
    """
    JWT does NOT guarantee:
        user still exists in DB
        user_id is valid integer
        user is active / not deleted
    """
    
    # Validate user_id is a valid integer (defense against malformed JWT)
    
    try:
        user_id_int = int(user_id)

    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User Not Found", headers={"WWW-Authenticate" : "Bearer"})
    
    # Token created → user deleted later but DB: no user found
    # User ID exists in token but not in DB
    # Token forged (if secret leaked) -> sub = "999999" {Valid signature but fake user}
    
    result = await db.execute(select(models.User).where(models.User.id == user_id_int))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User Not Found", headers={"WWW-Authenticate" : "Bearer"})
    
    return user

CurrentUser = Annotated[models.User, Depends(get_current_user)]