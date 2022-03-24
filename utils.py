import os
import requests
import ipaddress
from ipwhois import IPWhois

# test ip if campus
def isCampusIP( ip ):
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

def getISP( ip ):
	"""Lookup ISP information"""
	ipaddr = ipaddress.ip_address(ip)

	if not ipaddr.is_private:
		obj = IPWhois( ip )
		ret = obj.lookup_rdap()
		print("Found {}".format(ret))
		return ret
	
	return {}

def getNetwork( ip ):
	# find the network information for a given ip address
	print("Check ip {}".format(ip))

	if ( isCampusIP( ip ) ):
		# Do the lookup only if we think this is a campus address
		ib_server = os.environ.get('IB_SERVER')
		ib_username = os.environ.get('IB_USERNAME')
		ib_password = os.environ.get('IB_PASSWORD')
		url = "https://{}/wapi/v2.10.5/{}".format(ib_server,'network')

		session = requests.Session()
		requests.packages.urllib3.disable_warnings()
		params = {
			'_return_fields': 'comment,network,network_view,members,extattrs,vlans.id,options',
			'_inheritance': True,
			'contains_address': ip,
		}
		#print("Using {} with {}".format(url,params))
		response = session.get(url, params=params, auth=(ib_username, ib_password), verify=False)
		if response.status_code != 200:
			print("query failed {}".format(response))
		else:
			network_list = response.json()
			print("got {}".format(network_list))

		if (len(network_list) == 1):
			return network_list[0]
		else:
			return None

	else:
		return None
