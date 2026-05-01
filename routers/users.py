from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

# imported to avoid lazy loading which run a sync query in an async context which is not allowed. So, eager loading is implemented by importing selectinload to load them immediately with the main query.
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import PostResponse, UserCreate, UserPrivate, UserPublic, UserUpdate, Token

from auth import oauth2_scheme, hash_password, create_access_token, verify_access_token, verify_password
from config import settings


router = APIRouter()


# Create Users
@router.post("", response_model=UserPrivate, status_code=status.HTTP_201_CREATED)

async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.User).where(func.lower(models.User.username) == user.username.lower()))
    existing_user = result.scalars().first() # From the query result, it gives the first actual User object

    if(existing_user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User Already Exists")
    
    result = await db.execute(select(models.User).where(func.lower(models.User.email) == user.email.lower()))
    existing_email = result.scalars().first() 

    if(existing_email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email Already Exists")
    

    new_user = models.User(username=user.username, email=user.email.lower(), password_hash=hash_password(user.password))

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user



# Login
@router.post("/token", response_model=Token)
async def login_for_access_token(db : Annotated[AsyncSession, Depends(get_db)], form_data : Annotated[OAuth2PasswordRequestForm, Depends()]):

    # Look up user by email or username (case-insensitive)
    # Note: OAuth2PasswordRequestForm uses "username" field but we treat it as email
    # Allow login with username or email
    input_data = form_data.username.lower()
    result = await db.execute(
                    select(models.User)
                    .where(
                        or_(
                            func.lower(models.User.email) == input_data,
                            func.lower(models.User.username) == input_data
                        )
                    )
                )
    user = result.scalars().first()

    # Verify user exits and password is correct
    # Don't reveal which one failed (security best practice)
    if not user or not verify_password(form_data.password, user.password_hash): # password_hash in User class in models.py
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect Email or Password", headers={"WWW-Authenticate": "Bearer"}) 
        """
         headers telling "Use Bearer token authentication"
         FastAPI docs (/docs) use this header to:
             show Authorize button behavior
             understand auth type
         RFC standard → 401 responses should include WWW-Authenticate

        """
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(data = {"sub" : str(user.id)}, expires_delta=access_token_expires)
    return Token(access_token=access_token, token_type="bearer") # "Bearer" is a type of authentication token used in HTTP requests which means "Whoever holds this token is allowed to access"



# Get current User
@router.get("/me", response_model=UserPrivate)

async def get_current_user(db : Annotated[AsyncSession, Depends(get_db)], token : Annotated[str, Depends(oauth2_scheme)]):

    # Get the currently authenticated user
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    
    """
    JWT does NOT guarantee:
        user still exists in DB
        user_id is valid integer
        user is active / not deleted
    """
    
    # Validate user_id is a valid integer (defense against malformed JWT)
    try:
        user_id_int = int(user_id) # protects against malformed tokens like if "user_id" = "abc" -> check against int gives ValueError

    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User Not Found", headers={"WWW-Authenticate": "Bearer"})
    
    result = await db.execute(select(models.User).where(models.User.id == user_id_int))
    user = result.scalars().first()

    # Token created → user deleted later but DB: no user found
    # User ID exists in token but not in DB
    # Token forged (if secret leaked) -> sub = "999999" {Valid signature but fake user}


    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User Not Found", headers={"WWW-Authenticate": "Bearer"})
    
    return user
    



# get user
@router.get("/{user_id}", response_model=UserPublic)

async def get_user(user_id : int, db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if(user):
        return user
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")



# get user posts
@router.get("/{user_id}/posts", response_model=list[PostResponse])

async def get_user_posts(user_id : int, db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
    
    result = await db.execute(
                select(models.Post)
                .options(selectinload(models.Post.author))
                .where(models.Post.user_id == user_id)
                .order_by(models.Post.date_posted.desc())
            )
    posts = result.scalars().all()
    return posts



# Get all Users
@router.get("", response_model=list[str])
async def get_users(db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.User.username))
    users = result.scalars().all()
    return users



# Update User
@router.patch("/{user_id}", response_model=UserPrivate)

async def update_user(user_id : int, user_update : UserUpdate, db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
    
    if user.username is not None and user_update.username.lower() != user.username.lower():

        result = await db.execute(select(models.User).where(func.lower(models.User.username) == user_update.username.lower()))
        existing_username = result.scalars().first()

        if existing_username:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User Already Exists")
        

    if user.email is not None and user_update.email.lower() != user.email.lower():

        result = await db.execute(select(models.User).where(func.lower(models.User.email) == user_update.email.lower()))
        existing_email = result.scalars().first()

        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email Already Registered")

    update_data = user_update.model_dump(exclude_unset=True) # Only update what user wants to change [partial update]

    for field, value in update_data.items():
        value = value.lower()
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user



# Delete a User
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db : Annotated[AsyncSession, Depends(get_db)]):
    
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")

    await db.delete(user)
    await db.commit()
