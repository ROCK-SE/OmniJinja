from flask import Flask,render_template
from dataclasses import dataclass

app=Flask(__name__)

@dataclass
class Profile:
    avatar_url:str
    bio:str

@dataclass
class User:
    name:str
    email:str
    profile:Profile
    is_admin:bool

def role_label(value):
    '''
    Custom Jinja filter to display user role based on boolean value.
    '''
    return "Administrator" if value else "User"

app.jinja_env.filters["role_label"]=role_label

@app.route("/")
def index():
    user=User(
        name="Alice",
        email="alice@example.com",
        profile=Profile(
            avatar_url="/static/avatar.png",
            bio="Template developer"
        ),
        is_admin=True
    )

    stats={
        "visits":120,
        "likes":35
    }

    return render_template(
        "index.html",
        user=user,
        stats=stats,
        show_profile=True
    )
    