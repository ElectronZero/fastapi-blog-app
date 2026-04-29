from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# imported to avoid lazy loading which run a sync query in an async context which is not allowed. So, eager loading is implemented by importing selectinload to load them immediately with the main query.
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import PostResponse, UserCreate, UserResponse, UserUpdate


router = APIRouter()

# Create Users
@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)

async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.User).where(models.User.username == user.username))
    existing_user = result.scalars().first() # From the query result, it gives the first actual User object

    if(existing_user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User Already Exists")
    
    result = await db.execute(select(models.User).where(models.User.email == user.email))
    existing_email = result.scalars().first() 

    if(existing_email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email Already Exists")
    

    new_user = models.User(username=user.username, email=user.email)

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user



# get user
@router.get("/{user_id}", response_model=UserResponse)

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
@router.get("", response_model=list[UserResponse])
async def get_users(db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.User))
    users = result.scalars().all()
    return users



# Update User
@router.patch("/users/{user_id}", response_model=UserResponse)

async def update_user(user_id : int, user_update : UserUpdate, db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
    
    if user.username is not None and user_update.username != user.username:

        result = await db.execute(select(models.User).where(models.User.username == user_update.username))
        existing_username = result.scalars().first()

        if existing_username:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User Already Exists")
        

    if user.email is not None and user_update.email != user.email:

        result = await db.execute(select(models.User).where(models.User.email == user_update.email))
        existing_email = result.scalars().first()

        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email Already Registered")

    update_data = user_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
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
