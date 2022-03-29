import os
from flask import Flask, render_template, request, jsonify, make_response
from dotenv import load_dotenv
from user_agents import parse

from whatismyip.utils import *
#from dns import resolver, reversename
#from whatismyip import views

# load dotenv in the base root
APP_ROOT = os.path.join(os.path.dirname(__file__), '..')   # refers to application_top
dotenv_path = os.path.join(APP_ROOT, '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)
app.secret_key = os.getenv(
    'FLASK_SECRET_KEY',
    # safe value used for development when FLASK_SECRET_KEY might not be set
    '9e4@&tw46$l31)zrqe3wi+-slqm(ruvz&se0^%9#6(_w3ui!c0'
)


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
    http_user_agent      = request.environ.get("HTTP_USER_AGENT",None)

    # Parse out the actual client ip address from header data
    if forwarded_for:
        # Proxy was used, client IP should be first in the list
        fwd_list = forwarded_for.split(',')
        context['client_address'] = fwd_list[0]
    else:
        # No proxy was used
        context['client_address'] = remote_address
    context['client_address'] = '152.2.198.50'
    #context['client_address'] = '152.2.198.224'
    #context['client_address'] = '152.2.198.240'
    #context['client_address'] = '152.23.198.240'
    #context['client_address'] = '172.17.32.38'
    #context['client_address'] = '75.183.206.183'
    app.logger.debug("Finding information for {}".format( context['client_address'] ))

    # collect device information
    user_agent = parse(http_user_agent)
    context['user_device'] = str(user_agent)
    # context['user_browser'] = "{} {}".format(user_agent.browser.family,user_agent.browser.version_string)
    # context['user_os'] = "{} {}".format(user_agent.os.family,user_agent.os.version_string)
    #context['user_device'] = "{} {}".format(user_agent.device.brand,user_agent.device.model)

    # collect dns data
    #reverse_addr = reversename.from_address( context['client_address'] )
    #try:
    #    dns_response = resolver.query(reverse_addr, "PTR")
    #    for val in dns_response:
    #        print("PTR {}".format(val.to_text()))
    #except:
    #    print("reverse DNS lookup failed")

    # collect isp info
    iplocation = getIPLocation( context['client_address'])
    context['iplocation'] = iplocation

    # collect isp info
    # ipwhois = getISP( context['client_address'])
    # context['ipwhois'] = ipwhois
    # app.logger.debug("Parsed ip whois")

    # collect information about the network for this address
    network = getNetwork( context['client_address'] )
    context['network'] = network
    if network:
        # collect network data to display
        context['network_cidr'] = network.get('network',None)
        context['network_comment'] = network.get('comment',None)
        context['network_type'] = network.get('extattrs',{}).get('Purpose',{}).get('value',None)
        context['network_router'] = network.get('extattrs',{}).get('Router Device',{}).get('value',None)

        # collect vlan data to display
        vlan_list = network.get('vlans',None)
        if vlan_list:
            context['vlan_id'] = vlan_list[0].get('id',None)
            context['vlan_name'] = vlan_list[0].get('name',None)

    # Find any address objects
    address_records = getAddressObjects( context['client_address'] )
    context['address_records'] = address_records

    return render_template("home.html", context = context, headers = headers, environ = environ, network=network)
    
@app.route("/hostinfo.php")
def hostinfo():
    """Return JSON structure with IP address information."""

    # build the main data dictionary
    data = {
        'forwarded_for':   request.environ.get("HTTP_X_FORWARDED_FOR",''),
        'remote_address':  request.environ.get("REMOTE_ADDR",''),
        'remote_port':     request.environ.get("REMOTE_PORT",''),
        'request_method':  request.environ.get("REQUEST_METHOD",''),
        'server_protocol': request.environ.get("SERVER_PROTOCOL",''),
        'user_agent':      request.environ.get("HTTP_USER_AGENT",''),
        'network': '',
    }
    
    # Parse out the actual client ip address from header data
    if data['forwarded_for']:
        # Proxy was used
        fwd_list = data['forwarded_for'].split(',')
        data['address'] = fwd_list[0]   # the original client should be the first ip
    else:
        # No proxy was used
        data['address'] = data['remote_address']
    #data['address'] = '152.2.198.50'
    #context['client_address'] = '152.2.198.224'
    #context['client_address'] = '152.2.198.240'
    #context['client_address'] = '152.23.198.240'
    #context['client_address'] = '172.17.32.38'
    #context['client_address'] = '75.183.206.183'
    app.logger.debug("Finding information for {}".format( data['address'] ))

    # collect information about the network for this address
    network = getNetwork( data['address'] )
    data['network'] = network

    # build the json response
    message = jsonify(data)
    response = make_response(message)
    #response.headers.add("Access-Control-Allow-Origin", "http://whatismyip.unc.edu:5000")
    #response.headers.add('Access-Control-Allow-Headers', "GET")
    #response.headers.add('Access-Control-Allow-Methods', "origin, x-requested-with, content-type, accept")
    return response

@app.route("/about")
def about():
    """Display a basic webpage with about information."""
    return render_template("about.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)