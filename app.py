import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from utils import *

# load dotenv in the base root
APP_ROOT = os.path.join(os.path.dirname(__file__), '..')   # refers to application_top
dotenv_path = os.path.join(APP_ROOT, '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)

# Routes

@app.route("/")
def home():
    context = {}

    # variables from the request header
    headers = dict(request.headers)
    context['xfwd']     = request.environ.get("HTTP_X_FORWARDED_FOR")
    context['address']  = request.environ.get("REMOTE_ADDR")
    context['port']     = request.environ.get("REMOTE_PORT")
    context['method']   = request.environ.get("REQUEST_METHOD")
    context['protocol'] = request.environ.get("SERVER_PROTOCOL")
    context['agent']    = request.environ.get("HTTP_USER_AGENT")

    if isCampusIP( context['address'] ):
        print("Campus IP")
    else:
        print("not campus IP")

    return render_template("home.html", context = context, headers = headers)
    
@app.route("/hostinfo")
def hostinfo():
    data = {}
    data['xfwd']     = request.environ.get("HTTP_X_FORWARDED_FOR")
    data['address']  = request.environ.get("REMOTE_ADDR")
    data['port']     = request.environ.get("REMOTE_PORT")
    data['method']   = request.environ.get("REQUEST_METHOD")
    data['protocol'] = request.environ.get("SERVER_PROTOCOL")
    data['agent']    = request.environ.get("HTTP_USER_AGENT")
    data['network']  = ''
    return jsonify(data)

@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)