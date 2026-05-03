from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime


# USERS

class UserBase(BaseModel):
    username : str = Field(min_length=2, max_length=50)
    email : EmailStr = Field(max_length=100)


class UserCreate(UserBase):
    password : str = Field(min_length=8, max_length=50)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=100)
    image_file: str | None = Field(default=None, min_length=1, max_length=200)




class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id : int
    username : str
    image_file : str | None
    image_path : str


class UserPrivate(UserPublic):
    email : EmailStr







# TOKEN

class Token(BaseModel):
    access_token : str
    token_type : str






# POSTS

class PostBase(BaseModel):
    title : str = Field(min_length = 1, max_length= 100)
    content : str = Field(min_length = 5)

class PostCreate(PostBase):
    pass

class PostUpdate(BaseModel):
    title : str | None = Field(default=None, min_length=1, max_length=100)
    content : str | None = Field(default = None, min_length=1)

class PostResponse(PostBase):
    #Allow this model to read values from object attributes (like obj.id) instead of only dictionaries.
    model_config = ConfigDict(from_attributes=True) 

    id : int
    user_id : int
    date_posted : datetime
    author : UserPublic