import os
from flask import Flask, render_template, request, jsonify, make_response
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
    environ = dict(request.environ)
    context['xfwd']     = request.environ.get("HTTP_X_FORWARDED_FOR")
    context['address']  = request.environ.get("REMOTE_ADDR")
    context['port']     = request.environ.get("REMOTE_PORT")
    context['method']   = request.environ.get("REQUEST_METHOD")
    context['protocol'] = request.environ.get("SERVER_PROTOCOL")
    context['agent']    = request.environ.get("HTTP_USER_AGENT")

    xfwd = request.environ.get("HTTP_X_FORWARDED_FOR",'').split(',')
    context['address'] = xfwd[0]

    if isCampusIP( context['address'] ):
        print("Campus IP")
        network = getNetwork( context['address'] )
    else:
        print("not campus IP")

    return render_template("home.html", context = context, headers = headers, environ = environ)
    
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
    
    message = jsonify(data)
    response = make_response(message)
    response.headers.add("Access-Control-Allow-Origin", "http://whatismyip.unc.edu:5000")
    response.headers.add('Access-Control-Allow-Headers', "GET")
    response.headers.add('Access-Control-Allow-Methods', "origin, x-requested-with, content-type, accept")
    return response

@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)