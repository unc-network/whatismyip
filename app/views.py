from flask import Flask, render_template, request, jsonify

from app import app
from app.utils import *

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