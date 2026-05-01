from datetime import UTC, datetime, timedelta

import jwt
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
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