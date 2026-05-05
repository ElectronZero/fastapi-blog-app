from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler

from starlette.exceptions import HTTPException as StarletteHTTPException #This is imported as whenever user goes to wrong link starlette raises an exception

from typing import Annotated
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# imported to avoid lazy loading which run a sync query in an async context which is not allowed. So, eager loading is implemented by importing selectinload to load them immediately with the main query.
from sqlalchemy.orm import selectinload 

import models
from database import Base, engine, get_db
from contextlib import asynccontextmanager

from routers import posts, users
from config import settings



@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) # engine.begin() to get an async connection and run the sync create call inside of the async connection
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(lifespan = lifespan) # Use the lifespan function to control the app’s lifecycle where lifespan is async context manager

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

templates = Jinja2Templates(directory="templates")


app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])




# 200 OK - Successful GET, PUT, or PATCH
# 201 Created - Successful POST for users and posts
# 204 No Content - Successful DELETE
# 400 Bad Request - Duplicate username/email when creating user
# 404 Not Found - Resource doesn't exist (user or post)
# 422 Unprocessable Entity - Validation error (automatic from Pydantic)*


#login
@app.get("/login", include_in_schema=False)

async def login_page(request : Request):
    return templates.TemplateResponse(request, "login.html", {"title" : "Login"})


# Register
@app.get("/register", include_in_schema=False)

async def register_page(request : Request):
    return templates.TemplateResponse(request, "register.html", {"title" : "Register"})


# Account
@app.get("/account", include_in_schema=False)

async def account_page(request : Request):
    return templates.TemplateResponse(request, "account.html", {"title" : "Account"})



#home
@app.get("/", include_in_schema=False, name = "home")
@app.get("/posts", include_in_schema=False, name = "posts")

async def home(request : Request, db : Annotated[AsyncSession, Depends(get_db)]):

    count_result = await db.execute(select(func.count()).select_from(models.Post))
    total = count_result.scalar()

    
    result = await db.execute(
            select(models.Post)
            .options(selectinload(models.Post.author)) # Also load the related User (author) for each Post as author has a relationship with posts to avoid N+1 problem where 1 query fetches posts and N queries to fetch author in home.html. So, using selectinload to load the author immediately with the post
            .order_by(models.Post.date_posted.desc())
            .limit(settings.posts_per_page) 
        ) 
    
    posts = result.scalars().all()
    has_more = len(posts) < total

    return templates.TemplateResponse(request, "home.html", {"posts" : posts, "title" : "Home", "limit" : settings.posts_per_page, "has_more" : has_more})




#get a specific post (with paremeters (post_id))
@app.get("/posts/{post_id}", include_in_schema=False)

async def post_page(request : Request, post_id : int, db : Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id))
    post = result.scalars().first()
 
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not Found")
    
    title = post.title[:50]
    return templates.TemplateResponse(request, "post.html", {"post" : post, "title" : title})






# Get user's post page
@app.get("/users/{user_id}/posts", include_in_schema=False)

async def user_posts_page(request : Request, user_id : int, db : Annotated[AsyncSession, Depends(get_db)]): 

    result = await db.execute(select(models.User).where(models.User.id == user_id)) # No selectinload as we are not accessing any relationships in the User object
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
    
    count_result = await db.execute(select(func.count()).select_from(models.Post).where(models.Post.id == user_id))
    total = count_result.scalar()
    
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == user_id)
        .order_by(models.Post.date_posted.desc())
        .limit(settings.posts_per_page)
    )
    
    posts = result.scalars().all()
    has_more = len(posts) < total

    return templates.TemplateResponse(request, "user_posts.html", {"posts" : posts, "user" : user, "title" : f"{user.username}'s Posts", "limit" : settings.posts_per_page, "has_more" : has_more})





# Starlette Exception Handler
@app.exception_handler(StarletteHTTPException)
async def general_exception_handler(request : Request, exception : StarletteHTTPException):

    if request.url.path.startswith("/api"):
        return await http_exception_handler(request, exception)
    
    message = (
        exception.detail if exception.detail
        else "An Error Occured. Please  check your request and try again"
    )
    
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code" : exception.status_code,
            "title" : exception.status_code,
            "message" : message,

        },
        status_code = exception.status_code,
    )




#Validation Exception Handler -> when str is passed instead of int
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request : Request, exception : RequestValidationError):

    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exception)
    
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code" : status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title" : status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message" : "Invalid request, please check your input and try again",

        },
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
    ) 

