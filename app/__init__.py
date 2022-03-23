from flask import Flask

app = Flask(__name__)

# Load the views
from app import views