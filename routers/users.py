from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, Query # UploadFile = a file object sent by the client (form upload) represents a file coming from "multipart/form-data"
from fastapi.security import OAuth2PasswordRequestForm
from PIL import UnidentifiedImageError # Error if file is NOT a valid image
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

"""
process_profile_image()
    -uses PIL
    -does file I/O + CPU work
    -is not async

Problem without Threadpool -> Blocking function inside async route → freezes event loop ❌
with Threadpool -> Run a normal (blocking) function in a separate thread
"""
from starlette.concurrency import run_in_threadpool

# imported to avoid lazy loading which run a sync query in an async context which is not allowed. So, eager loading is implemented by importing selectinload to load them immediately with the main query.
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import PostResponse, UserCreate, UserPrivate, UserPublic, UserUpdate, Token, PaginatedPostResponse

from image_utils import process_profile_image, delete_profile_image
from auth import hash_password, create_access_token, verify_password, CurrentUser
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

async def get_current_user(current_user : CurrentUser):
    return current_user
    



# get user
@router.get("/{user_id}", response_model=UserPublic)

async def get_user(user_id : int, db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if(user):
        return user
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")



# get user posts
@router.get("/{user_id}/posts", response_model=PaginatedPostResponse)

async def get_user_posts(
    user_id : int, 
    db : Annotated[AsyncSession, Depends(get_db)],
    skip : int = Query(0, ge=0),
    limit : Annotated[int, Query(ge=1, le=100)] = settings.posts_per_page
):

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
    
    count_result = await db.execute(select(func.count()).select_from(models.Post).where(models.Post.id == user_id))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == user_id).order_by()
        .order_by(models.Post.date_posted.desc())
        .offset(skip)
        .limit(limit)
    )

    posts = result.scalars().all()

    has_more = skip + len(posts) < total

    return PaginatedPostResponse(
        posts= [PostResponse.model_validate(post) for post in posts],
        total= total,
        skip= skip,
        limit= limit,
        has_more= has_more
    )



# Get all Users
@router.get("", response_model=list[str])
async def get_users(db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.User.username))
    users = result.scalars().all()
    return users



# Update User
@router.patch("/{user_id}", response_model=UserPrivate)

async def update_user(user_id : int, user_update : UserUpdate, current_user : CurrentUser, db : Annotated[AsyncSession, Depends(get_db)]):

    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this user")
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

    # update_data = user_update.model_dump(exclude_unset=True) # Only update what user wants to change [partial update]

    # for field, value in update_data.items():
    #     value = value.lower()
    #     setattr(user, field, value)

    if user_update.username is not None:
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email.lower()

    await db.commit()
    await db.refresh(user)
    return user



# Delete a User
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, current_user : CurrentUser, db : Annotated[AsyncSession, Depends(get_db)]):

    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this user")
    
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")

    old_filename = current_user.image_file

    await db.delete(user)
    await db.commit()

    if old_filename:
        delete_profile_image(old_filename)






# PROFILE PICTURES

# Upload Profile Picture
@router.patch("/{user_id}/picture", response_model=UserPrivate)

async def upload_profile_picture(user_id : int, current_user : CurrentUser, file : UploadFile, db : Annotated[AsyncSession, Depends(get_db)]):

    if current_user.id != user_id:
        raise(HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized to update this user's profile"))
    
    content = await file.read()

    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File too large. Maximum size is {settings.max_upload_size_bytes // (1024 * 1024)} MB")
    
    try:
        new_filename = await run_in_threadpool(process_profile_image, content)

    except UnidentifiedImageError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file. Please upload a valid image (JPEG, PNG, GIF, WebP)") from err
    
    old_filename = current_user.image_file
    current_user.image_file = new_filename

    await db.commit()
    await db.refresh(current_user)

    if old_filename:
        delete_profile_image(old_filename)

    return current_user

    

# Delete Profile Picture
@router.delete("/{user_id}/picture", response_model=UserPrivate)
async def delete_profile_picture(user_id : int, current_user : CurrentUser, file : UploadFile, db : Annotated[AsyncSession, Depends(get_db)]):

    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not Authorized to delete this user's profile")
    
    old_filename = current_user.image_file

    if old_filename is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No profile picture to delete")
    
    current_user.image_file = None
    await db.commit()
    await db.refresh(current_user)

    delete_profile_image(old_filename)
    return current_user

    

 
