from typing import Annotated # Separates type (int) from metadata (Query)
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import models
from database import get_db
from schemas import PostResponse, PostCreate, PostUpdate, PaginatedPostResponse
from auth import CurrentUser
from config import settings

router = APIRouter()



#Create Posts
@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)

async def create_post(post: PostCreate, current_user : CurrentUser, db : Annotated[AsyncSession, Depends(get_db)]):
    
    new_post = models.Post(title=post.title, content=post.content, user_id=current_user.id)

    db.add(new_post) # Does not interact with database, no I/O -> does not need await
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"])

    return new_post



#get all posts
@router.get("", response_model=PaginatedPostResponse)

async def get_posts(
    db : Annotated[AsyncSession, Depends(get_db)], 
    skip : Annotated[int, Query(ge=0)] = 0, 
    limit : Annotated[int, Query(ge=1, le=100)] = settings.posts_per_page
):

    count_result = await db.execute(select(func.count()).select_from(models.Post))
    total = count_result.scalar() or 0 # output -> one value (first column of first row), used for count, avg, sum

    result = await db.execute(
            select(models.Post)
            .options(selectinload(models.Post.author))
            .order_by(models.Post.date_posted.desc())
            .offset(skip)
            .limit(limit)
        )
    
    posts = result.scalars().all() # fetch many rows

    has_more = skip + len(posts) < total

    return PaginatedPostResponse(
        posts=[PostResponse.model_validate(post) for post in posts], # Loop through the DB and take each "post" from DB → convert it into PostResponse → put in a new list
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more
    )

    


#get a specific post
@router.get("/{post_id}", response_model=PostResponse)

async def get_post(post_id : int, db : Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Post).options(selectinload(models.Post.author)).where(models.Post.id == post_id))
    post = result.scalars().first()  # fetch one row (or None)

    if not post:
        raise HTTPException(status_code = status.HTTP_404_NOT_FOUND, detail = "Post not Found")
    
    return post



# Update Post Fully
@router.put("/{post_id}", response_model=PostResponse)

async def update_post_fully(post_id : int, post_data : PostCreate, current_user : CurrentUser, db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first() 

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post Not Found")
    
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this post")
        
    post.title = post_data.title
    post.content = post_data.content

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post



# Update post partially
@router.patch("/{post_id}", response_model=PostResponse)

async def update_post_partially(post_id : int, post_data : PostUpdate, current_user : CurrentUser, db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post Not Found")
    
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this post")
    
    # Manual Update

    # if post_data.title is not None:
    #     post.title = post_data.title

    # if post_data.content is not None:
    #     post.content = post_data.content

    # if post_data.user_id is not None:
    #     post.user_id = post_data.user_id


    # Dynamic Update
    
    update_data = post_data.model_dump(exclude_unset=True) # Return a dict by only extracting the provided fields, not replacing with default values

    for field, value in update_data.items():
        setattr(post, field, value) # Setting the old value of the post with new value

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post



# Delete Post
@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)

async def delete_post(post_id : int, current_user : CurrentUser, db : Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post Not Found")
    
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this post")
    
    await db.delete(post)
    await db.commit()   #Later on adding authentication we will allow only the author of the post to delete it.
