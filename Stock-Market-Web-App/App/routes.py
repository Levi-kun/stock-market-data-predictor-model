"""
This routes.py script will contain the routes/path for our application 
"""
from flask import Blueprint, render_template,request 
from .db import query_test
from .login import handle_login
from .register import handle_registration

bp = Blueprint("main",__name__)

## initializes a blue print 
@bp.route("/")
def index():
    ## we will change this to render html home page later on
    #ok = query_test("SELECT 1")
    #if ok:
    #    return "<h1> Flask is running! Database Connection is Suceessful! </h1>"
    #else:
    #    return "<h1> Flask is running! BUT Datavse test query returned no results! :c </h1>"
    return render_template("index.html")
## add the route for the login

@bp.route("/login",methods = ["GET","POST"]) ## local host / login
def login():
    if request.method == "POST":
        print("Hi!")  ## erase this it is just there to prevent error
    return render_template("login.html")

@bp.route("/register",methods = ["GET","POST"])
def register():
    if request.method == "POST":
        ## Call the register.py script logic here
        print("hi")

    return render_template("register.html")
    
## about page route 

@bp.route("/about")
def about():
    return render_template("about.html")