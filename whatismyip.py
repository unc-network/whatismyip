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
    """Display the base homepage with IP address information."""
    context = {}

    # variables to help debug
    headers = dict(request.headers)
    environ = dict(request.environ)

    # get the request headers
    forwarded_for   = request.environ.get("HTTP_X_FORWARDED_FOR",None)
    remote_address  = request.environ.get("REMOTE_ADDR",None)
    remote_port     = request.environ.get("REMOTE_PORT",None)
    request_method  = request.environ.get("REQUEST_METHOD",None)
    server_protocol = request.environ.get("SERVER_PROTOCOL",None)
    user_agent      = request.environ.get("HTTP_USER_AGENT",None)

    # Parse out the actual client ip address from header data
    if forwarded_for:
        # Proxy was used, client IP should be first in the list
        fwd_list = forwarded_for.split(',')
        context['client_address'] = fwd_list[0]
    else:
        # No proxy was used
        context['client_address'] = remote_address

    # collect isp info
    ipwhois = getISP( context['client_address'])
    context['ipwhois'] = ipwhois

    # collect information about the network for this address
    network = getNetwork( context['client_address'] )
    if network:
        # collect network data to display
        context['network'] = network.get('network',None)
        context['network_comment'] = network.get('comment',None)
        context['network_type'] = network.get('extattrs',{}).get('Purpose',{}).get('value',None)
        context['network_router'] = network.get('extattrs',{}).get('Router Device',{}).get('value',None)

        # collect vlan data to display
        vlan_list = network.get('vlans',None)
        if vlan_list:
            context['vlan_id'] = vlan_list[0].get('id',None),
            context['vlan_name'] = vlan_list[0].get('name',None)

    return render_template("home.html", context = context, headers = headers, environ = environ, network=network)
    
@app.route("/hostinfo")
def hostinfo():
    """Return JSON structure with IP address information."""

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
    """Display a basic webpage with about information."""
    return render_template("about.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)