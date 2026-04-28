from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException #This is imported as whenever user goes to wrong link starlette raises an exception

from schemas import PostCreate, PostResponse, UserCreate, UserResponse, PostUpdate, UserUpdate
from typing import Annotated
from sqlalchemy import select
from sqlalchemy.orm import Session
import models
from database import Base, engine, get_db



Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

templates = Jinja2Templates(directory="templates")




# 200 OK - Successful GET, PUT, or PATCH
# 201 Created - Successful POST for users and posts
# 204 No Content - Successful DELETE
# 400 Bad Request - Duplicate username/email when creating user
# 404 Not Found - Resource doesn't exist (user or post)
# 422 Unprocessable Entity - Validation error (automatic from Pydantic)*





#home
@app.get("/", include_in_schema=False, name = "home")

@app.get("/posts", include_in_schema=False, name = "posts")
def home(request : Request, db : Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Post))
    posts = result.scalars().all()

    return templates.TemplateResponse(request, "home.html", {"posts" : posts, "title" : "Home"})






#Create Posts
@app.post("/api/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)

def create_post(post: PostCreate, db : Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.User).where(models.User.id == post.user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
    
    new_post = models.Post(title=post.title, content=post.content, user_id=post.user_id)

    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    return new_post



#get all posts
@app.get("/api/posts", response_model=list[PostResponse])

def get_posts(db : Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Post))
    posts = result.scalars().all()
    return posts




#get a specific post (with paremeters (post_id))
@app.get("/posts/{post_id}", include_in_schema=False)

def post_page(request : Request, post_id : int, db : Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()
 
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not Found")
    
    title = post.title[:50]
    return templates.TemplateResponse(request, "post.html", {"post" : post, "title" : title})
    


#get a specific post
@app.get("/api/posts/{post_id}", response_model=PostResponse)

def get_post(post_id : int, db : Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()

    if not post:
        raise HTTPException(status_code = status.HTTP_404_NOT_FOUND, detail = "Post not Found")
    
    return post



# Update Post Fully
@app.put("/api/post/{post_id}", response_model=PostResponse)

def update_post_fully(post_id : int, post_data : PostCreate, db : Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, details="Post Not Found")
    
    # Is the post being reassigned to another user? If yes → verify new user exists
    if post_data.user_id != post.user_id:    
        result = db.execute(select(models.User).where(models.User.id == post_data.user_id))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, details="User Not Found")
        
    post.title = post_data.title
    post.content = post_data.content
    post.user_id = post_data.user_id

    db.commit()
    db.refresh(post)
    return post



# Update post partially
@app.patch("/api/post/{post_id}", response_model=PostResponse)

def update_post_partially(post_id : int, post_data : PostUpdate, db : Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post Not Found")
    
    update_data = post_data.model_dump(exclude_unset=True) # Return a dict by only extracting the provided fields, not replacing with default values

    for field, value in update_data.items():
        setattr(post, field, value) # Setting the old value of the post with new value

    db.commit()
    db.refresh(post)
    return post



# Delete Post
@app.delete("/api/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)

def delete_post(post_id : int, db : Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()

    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post Not Found")
    
    db.delete(post)
    db.commit()   #Later on adding authentication we will allow only the author of the [post to delete it.






# Create Users
@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)

def create_user(user: UserCreate, db: Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.User).where(models.User.username == user.username))
    existing_user = result.scalars().first() # From the query result, it gives the first actual User object

    if(existing_user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User Already Exists")
    
    result = db.execute(select(models.User).where(models.User.email == user.email))
    existing_email = result.scalars().first() 

    if(existing_email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email Already Exists")
    

    new_user = models.User(username=user.username, email=user.email)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user



# get user
@app.get("/api/users/{user_id}", response_model=UserResponse)

def get_user(user_id : int, db : Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if(user):
        return user
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")



# get user posts
@app.get("/api/users/{user_id}/posts", response_model=list[PostResponse])

def get_user_posts(user_id : int, db : Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
    
    result = db.execute(select(models.Post).where(models.Post.user_id == user_id))
    posts = result.scalars().all()
    return posts



# Get user's post page
@app.get("/users/{user_id}/posts", response_model=list[PostResponse], include_in_schema=False)

def user_posts_page(request : Request, user_id : int, db : Annotated[Session, Depends(get_db)]): 

    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
    
    result = db.execute(select(models.Post).where(models.Post.user_id == user_id))
    posts = result.scalars().all()
    return templates.TemplateResponse(request, "user_posts.html", {"posts" : posts, "user" : user, "title" : f"{user.username}'s Posts"})



# Get all Users
@app.get("/api/users", response_model=list[UserResponse])
def get_users(db = Depends(get_db)):
    users = db.query(models.User).all()
    return users



# Update User
@app.patch("/api/users/{user_id}", response_model=UserResponse)

def update_user(user_id : int, user_update : UserUpdate, db : Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
    
    if user.username is not None and user_update.username != user.username:

        result = db.execute(select(models.User).where(models.User.username == user_update.username))
        existing_username = result.scalars().first()

        if existing_username:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User Already Exists")
        

    if user.email is not None and user_update.email != user.email:

        result = db.execute(select(models.User).where(models.User.email == user_update.email))
        existing_email = result.scalars().first()

        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email Already Registered")

    update_data = user_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user



# Delete a User
@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db : Annotated[Session, Depends(get_db)]):
    
    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")

    db.delete(user)
    db.commit()





# Starlette Exception Handler
@app.exception_handler(StarletteHTTPException)
def general_exception_handler(request : Request, exception : StarletteHTTPException):
    message = (
        exception.detail if exception.detail
        else "An Error Occured. Please  check your request and try again"
    )

    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exception.status_code,
            content = {"detail" : message},
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
def validation_exception_handler(request : Request, exception : RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content = {"detail" : exception.errors()},
        ) 
    
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

