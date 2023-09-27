import os
import requests
import time
import ipaddress
#from ipwhois import IPWhois

from flask import current_app as app


def isCampusIP( ip ):
    # Check if the IP address is in a campus block.
    # If so, further testing can take place.

    prefixes = [ 
    '152.2.','152.19.','152.23.',
    '172.16.','172.17.','172.18.','172.19.',
    '172.20.','172.21.','172.22.','172.23.',
    '172.24.','172.25.','172.26.','172.27.',
    '172.28.','172.29.','172.30.','172.31.',
    '198.85.230.','198.85.231.',
    '204.84.','204.85.',
    '2610:28:3090:','2610:28:3091:',
    '2610:2701:4000:'
    ]

    for prefix in prefixes:
        if ip.startswith( prefix ):
            return True
    return False

# def getISP( ip ):
# 	# Lookup ISP information

# 	ipaddr = ipaddress.ip_address(ip)
# 	app.logger.debug("getISP {}".format(ip))

# 	if not ipaddr.is_private:
# 		obj = IPWhois( ip )
# 		ret = obj.lookup_rdap()
# 		print("Found {}".format(ret))
# 		return ret
    
# 	return {}

def getForwardedAddress( forwarded_for ):
    # A proxy will populate the X-Forwarded-For header, so find the client
    proxy_detected = None
    fwd_list = forwarded_for.split(',')
    if len(fwd_list) > 2:
        # multiple proxy detected, only trust the last 2 for campus
        # the last for cloudapps and second to last for client
        client_address = fwd_list[-2].strip()
        proxy_detected = ",".join( fwd_list[:-2] )
    else:
        # normal: the last for cloudapps and second to last for client
        client_address = fwd_list[0].strip()
    return client_address, proxy_detected

def getNetwork( ip ):
    # Find the network for this address in IPAM.
    startTime = time.time()
    app.logger.debug("getNetwork {}".format(ip))

    # make sure we have a valid ip address
    try:
        ipaddr = ipaddress.ip_address(ip)
    except ValueError:
        app.logger.warn("{} is not a valid ip address".format(ip))
        return {}

    if ( isCampusIP( ip ) ):
        # Do the lookup only if we think this is a campus address
        ib_server = os.environ.get('IB_SERVER')
        ib_username = os.environ.get('IB_USERNAME')
        ib_password = os.environ.get('IB_PASSWORD')
        url = "https://{}/wapi/v2.10.5/".format(ib_server)

        app.logger.info("Checking for address info")
        session = requests.Session()
        requests.packages.urllib3.disable_warnings()
        params = {
            '_return_fields': 'comment,network,network_view,members,extattrs,vlans.id,options',
            '_inheritance': True,
            'contains_address': ip,
        }
        if ipaddr.version == 6:
            object_type = 'ipv6network'
        else:
            object_type = 'network'
        #print("Using {} with {}".format(url,params))
        #response = session.get("{}network".format(url), params=params, auth=(ib_username, ib_password), verify=False)
        response = session.get("{}{}".format(url,object_type), params=params, auth=(ib_username, ib_password), verify=False)
        app.logger.debug("{}".format(response))
        if response.status_code != 200:
            app.logger.warning("query failed {}".format(response))
        else:
            network_list = response.json()
            app.logger.debug("network details: {}".format(network_list))

        if (len(network_list) == 1):
            executionTime = (time.time() - startTime)
            app.logger.debug("getNetwork complete in {} seconds".format(executionTime))
            return network_list[0]
        else:
            executionTime = (time.time() - startTime)
            app.logger.debug("getNetwork complete in {} seconds".format(executionTime))
            return {}

    else:
        executionTime = (time.time() - startTime)
        app.logger.debug("getNetwork complete in {} seconds".format(executionTime))
        return {}


def getAddressObjects( ip ):
    # Find Infoblox records
    startTime = time.time()
    app.logger.debug("getAddressObjects {}".format(ip))

    # make sure we have a valid ip address
    try:
        ipaddr = ipaddress.ip_address(ip)
    except ValueError:
        app.logger.warn("{} is not a valid ip address".format(ip))
        return {}

    if ( isCampusIP( ip ) ):
        # Do the lookup only if we think this is a campus address
        ib_server = os.environ.get('IB_SERVER')
        ib_username = os.environ.get('IB_USERNAME')
        ib_password = os.environ.get('IB_PASSWORD')
        url = "https://{}/wapi/v2.10.5/".format(ib_server)

        session = requests.Session()
        requests.packages.urllib3.disable_warnings()
        params = {
            'network_view': 'default',
            '_return_fields+': 'discovered_data,extattrs,fingerprint,ms_ad_user_data',
            'ip_address': ip
        }
        if ipaddr.version == 6:
            object_type = 'ipv6address'
        else:
            object_type = 'ipv4address'
        #response = session.get("{}ipv4address".format(url), params=params, auth=(ib_username, ib_password), verify=False)
        response = session.get("{}{}".format(url,object_type), params=params, auth=(ib_username, ib_password), verify=False)
        app.logger.debug("{}".format(response))
        if response.status_code != 200:
            app.logger.warn("{} query failed {}".format(object_type,response))
        else:
            address_list = response.json()
            app.logger.debug("{} details: {}".format(object_type,address_list))

        if (len(address_list) == 1):
            executionTime = (time.time() - startTime)
            app.logger.debug("getAddressObject complete in {} seconds".format(executionTime))
            return address_list[0]
        else:
            executionTime = (time.time() - startTime)
            app.logger.debug("getAddressObject complete in {} seconds".format(executionTime))
            return {}

    else:
        executionTime = (time.time() - startTime)
        app.logger.debug("getAddressObject complete in {} seconds".format(executionTime))
        return {}

def getIPLocation( ip ):
    # Get location data for the IP
    # Currently using https://iplocation.net
    # Other options: https://ipapi.co/
    startTime = time.time()
    app.logger.debug("getIPLocation {}".format(ip))

    # make sure we have a valid ip address
    try:
        ipaddr = ipaddress.ip_address(ip)
    except ValueError:
        app.logger.warn("{} is not a valid ip address".format(ip))
        return {}

    if not ipaddr.is_private:
        # Do not attempt this with private IP addresses
        api_url = "https://api.iplocation.net/?ip="
        session = requests.Session()
        try:
            response = session.get("{}{}".format(api_url,ip), timeout=3)
        except requests.ReadTimeout:
            # Something went wrong, return no data
            app.logger.warn("unable to query location api")
            return {}
        if response.status_code != 200:
            app.logger.warn("iplocation query failed {}".format(response))
            executionTime = (time.time() - startTime)
            app.logger.debug("getIPLocation complete in {} seconds".format(executionTime))
            return {}
        else:
            iplocation = response.json()
            app.logger.debug("iplocation details: {}".format( iplocation ))
            executionTime = (time.time() - startTime)
            app.logger.debug("getIPLocation complete in {} seconds".format(executionTime))
            return iplocation
    else:
        executionTime = (time.time() - startTime)
        app.logger.debug("getIPLocation complete in {} seconds".format(executionTime))
        return {}
