/*!
  * whatismyip.js
  * Helper library for https://whatismyip.unc.edu
  */

function copyAddress(id_of_address) {
	//const text = $("#address").text()
	const text = $(id_of_address).text()
	try {
		navigator.clipboard.writeText(text)
		//console.log("Copied the address: " + text);
	} catch (err) {
		console.error('Failed to copy the address!', err)
	}
}

function set_intro_text(is_campus, network_purpose) {
	// add some user text at the very top of the page
	$('#intro_text').html(`<p>hello</p>`);

	if (is_campus) {
		if ( network_purpose == 'VPN' ) {
			$('#intro_text').html(`<p>Your IP address indicates that you are connected with the campus VPN service.</p>`);
		} else if ( network_purpose == 'Wireless' ) {
			$('#intro_text').html(`<p>Your IP address indicates that you are connected to the campus wireless network.</p>`);
		} else {
			$('#intro_text').html(`<p>Your IP address indicates that you are connected to the local campus network.</p>`);
		}
	} else {
		$('#intro_text').html(`<p>Your IP address indicates that you are off campus and connected over the Internet.</p>`);
	}
}

function test_primary_url(default_version) {
	// call the test url and display address information

	// handle starting state
	if ( default_version == 4 ) {
		$('#connect-default').text("IPv4");
		// $('#connect-ipv4').text("Testing...");
		$('#connect-ipv4').html('<i class="fa-solid fa-question"></i> Testing');
	}

	// Make AJAX call to the API to get the ipv4 address
	var test_url = $('#connect-test').data('ipv4_url')
	$.ajax({
		type: "GET",
		url: test_url + "/hostinfo",
		dataType: "json",
		success: function (result, status, xhr) {
			// $('#connect-ipv4').text("Supported");
			$('#connect-ipv4').html('<i class="fa-solid fa-circle-check text-success"></i> Supported');
			//console.log("Host check from " + result["address"]);

			if ( default_version == 4 ) {
				$('#first_address_section').show()
				$('#address1').text(result["client_address"]);
				set_intro_text(result['is_campus'], result['network']['purpose']);
			} else {
				$('#second_address_section').show()
				$('#address2').text(result["client_address"]);
			}

			// Populate IPv4 address's details
			$('#address1-details').show();
			$('#address1-address').text(result["client_address"]);

			if ( result['address_details']["names"] && result['address_details']['names'].length > 0) {
				$('#addr1-names-row').show();
				lowercaseNames = result['address_details']['names'].map(item => item.toLowerCase());
				uniqueNames = [...new Set(lowercaseNames)]
				// uniqueNames = [...new Set(result['address_details']['names'])]
				for (address_name of uniqueNames) {
				// for (address_name of result['address_details']['names']) {
					$('#addr1-names').append(`<li class="list-group-item p-0">${address_name}</li>`);
				}
			} else if ( result["ptr"] ) {
				$('#addr1-names-row').show();
				$('#addr1-names').append(`<li class="list-group-item p-0">${result["ptr"]}</li>`);
			}

			if ( result['address_details']["mac"] ) {
				$('#addr1-mac-row').show();
				$('#addr1-mac').text(result['address_details']["mac"]);
			}

			if ( result['address_details']["comment"] ) {
				$('#addr1-comment-row').show();
				$('#addr1-comment').text(result['address_details']["comment"]);
			}

			// if ( result['address_details']["dhcp_lease_state"] ) {
			// 	$('#addr1-lease-row').show();
			// 	$('#addr1-lease').text(result['address_details']["dhcp_lease_state"]);
			// }

			if ( result['address_details']["username"] ) {
				$('#addr1-username-row').show();
				$('#addr1-username').text(result['address_details']["username"]);
			}

			// if ( result['address_details']["types"] ) {
			// 	$('#addr1-types-row').show();
			// 	$('#addr1-types').text(result['address_details']["types"]);
			// }

			// if ( result['address_details']["status"] ) {
			// 	$('#addr1-status-row').show();
			// 	$('#addr1-status').text(result['address_details']["status"]);
			// }

			// Populate address's network details
			if ( result['network']["cidr"] ) {
				$('#net1-network-row').show();
				if ( result['network']['comment'] ) {
					$('#net1-network').text(result['network']["cidr"] + ' (' + result['network']['comment'] + ')');
				} else {
					$('#net1-network').text(result['network']["cidr"]);
				}
			}

			if ( result['network']["vlan_id"] ) {
				$('#net1-vlan-row').show();
				$('#net1-vlan').text(result['network']["vlan_id"] + ' (' + result['network']['vlan_name'] + ')');
			}

			if ( result['iplocation']["city"] ) {
				$('#net1-city-row').show();
				$('#net1-city').text(result['iplocation']["city"]);
			}
			if ( result['iplocation']["country_name"] ) {
				$('#net1-country-row').show();
				$('#net1-country').text(result['iplocation']["country_name"]);
			} else if ( result['iplocation']['country']) {
				$('#net1-country-row').show();
				$('#net1-country').text(result['iplocation']["country"]);
			}
			if ( result['iplocation']["isp"] ) {
				$('#net1-isp-row').show();
				$('#net1-isp').text(result['iplocation']["isp"]);
			}
			if (result['iplocation']['lat'] && result['iplocation']['lon']) {
				// console.log('adding marker to map');
				pin_to_map(result['iplocation']['lat'],result['iplocation']['lon'],'Your IP location');
			}

			// dump nac data
			if (result['nac']['endSystem']) {
				$('#nac-row').show();
				for (const [key, value] of Object.entries(result['nac']['endSystem'])) {
					if ( value ) {
						$('#nac-table tbody').append(`<tr><th>${key}</th><td>${value}</td></tr>`);
					}
				}
			}
			if (result['nac']['endSystemInfo']) {
				$('#nac-row').show();
				for (const [key, value] of Object.entries(result['nac']['endSystemInfo'])) {
					if ( value ) {
						$('#nac-table tbody').append(`<tr><th>${key}</th><td>${value}</td></tr>`);
					}
				}
			}

			// dump building data
			if (result['nac']['nit_building']) {
				$('#bldg-col').show();
				for (const [key, value] of Object.entries(result['nac']['nit_building'])) {
					if ( value ) {
						$('#bldg-table tbody').append(`<tr><th>${key}</th><td>${value}</td></tr>`);
					}
				}
			}
		},
		error: function (xhr, status, error) {
			// $('#connect-ipv4').text("Not supported");
			$('#connect-ipv4').html('<i class="fa-solid fa-circle-xmark text-danger"></i> Not supported');
			//console.log(error);
		}
	});

}

function pin_to_map(lat, lon, label) {

	// var map = L.map('map').setView([35.9114, -79.0509], 13);
	// console.log(`updating map ${lat}, ${lon}`);
	var map = L.map('map').setView([lat, lon], 11);
	L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
		attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
	}).addTo(map);

	// add device marker to the map
	//var campusMarker = L.marker([35.9114, -79.0509]); // South Building
	var deviceMarker = L.marker([lat, lon]).addTo(map).bindPopup(label);
	//var group = new L.featureGroup([campusMarker, deviceMarker])
	//map.fitBounds(group.getBounds());
}

function createRandomString(length) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

function get_dns_info() {
	// testing DNS identification
	// https://ip-api.com/docs/dns
	tmp_name = createRandomString(32);
	const test_url = `https://${tmp_name}.edns.ip-api.com/json`;
	// console.log(`Checking DNS servers with ${test_url}`);

	$.ajax({
		type: "GET",
		url: test_url,
		dataType: "json",
		success: function (result, status, xhr) {
			// console.dir(`success: ${result}`)
			// dump dns data
			if (result['dns']) {
				let geo = result['dns']['geo']
				if ( geo.includes('Akamai') ) {
					$('#dns-table tbody').append(`<tr><th>Security Filtering <a href="https://tdx.unc.edu/TDClient/33/Portal/KB/ArticleDet?ID=333" alt="Security Filtering Service"><i class="fa-solid fa-circle-info" alt="More Information"></i></a></th><td><i class="fa-solid fa-circle-check text-success"></i> Active</td></tr>`);
				} else {
					$('#dns-table tbody').append(`<tr><th>Security Filtering <a href="https://tdx.unc.edu/TDClient/33/Portal/KB/ArticleDet?ID=333" alt="Security Filtering Service"><i class="fa-solid fa-circle-info" alt="More Information"></i></a></th><td><i class="fa-solid fa-circle-xmark text-danger"></i> Inactive</td></tr>`);
				}
				$('#dns-test').show();
				// for (const [key, value] of Object.entries(result['dns'])) {
				// 	if ( value ) {
				// 		$('#dns-table tbody').append(`<tr><th>${key}</th><td>${value}</td></tr>`);
				// 	}
				// }
			}
			// if (result['edns']) {
			// 	$('#dns-test').show();
			// 	for (const [key, value] of Object.entries(result['edns'])) {
			// 		if ( value ) {
			// 			$('#dns-table tbody').append(`<tr><th>${key}</th><td>${value}</td></tr>`);
			// 		}
			// 	}
			// }
		},
		error: function (xhr, status, error) {
			console.dir(`DNS test failed: ${error}`)
		}
	});

	// fetch('http://www.akamaietpmalwaretest.com/')
	// .then(response => response.text()) // Parse body as text
	// .then(text => {
	// 	console.log(text); // Handle the parsed text
	// })
	// .catch(error => console.error('Error:', error));

}

function test_secondary_url(default_version) {
	// test secondary url

	// handle starting state
	if ( default_version == 6 ) {
		$('#connect-default').text("IPv6");
		// $('#connect-ipv6').text("Testing...");
		$('#connect-ipv6').html('<i class="fa-solid fa-question"></i> Testing');
	}

	// Make AJAX call to the API to get the ipv6 address
	var test_url = $('#connect-test').data('ipv6_url')
	$.ajax({
		type: "GET",
		url: test_url + "/hostinfo",
		dataType: "json",
		success: function (result, status, xhr) {
			// $('#connect-ipv6').text("Supported");
			$('#connect-ipv6').html('<i class="fa-solid fa-circle-check text-success"></i> Supported');
			//console.log("Host check from " + result["address"]);

			if ( default_version == 6 ) {
				$('#first_address_section').show()
				$('#address1').text(result["client_address"]);
				set_intro_text(result['is_campus'], result['network']['purpose']);
			} else {
				$('#second_address_section').show()
				$('#address2').text(result["client_address"]);
			}
			// Populate IPv6 address's details
			$('#address2-details').show();
			$('#address2-address').text(result["client_address"]);

			if ( result['address_details']["names"] && result['address_details']['names'].length > 0) {
				$('#addr2-names-row').show();
				lowercaseNames = result['address_details']['names'].map(item => item.toLowerCase());
				uniqueNames = [...new Set(lowercaseNames)]
				// uniqueNames = [...new Set(result['address_details']['names'])]
				for (address_name of uniqueNames) {
				// for (address_name of result['address_details']['names']) {
					$('#addr2-names').append(`<li class="list-group-item p-0">${address_name}</li>`);
				}
			} else if ( result["ptr"] ) {
				$('#addr2-names-row').show();
				$('#addr2-names').append(`<li class="list-group-item p-0">${result["ptr"]}</li>`);
			}

			if ( result['address_details']["mac"] ) {
				$('#addr2-mac-row').show();
				$('#addr2-mac').text(result['address_details']["mac"]);
			}

			if ( result['address_details']["comment"] ) {
				$('#addr2-comment-row').show();
				$('#addr2-comment').text(result['address_details']["comment"]);
			}

			// if ( result['address_details']["dhcp_lease_state"] ) {
			// 	$('#addr2-lease-row').show();
			// 	$('#addr2-lease').text(result['address_details']["dhcp_lease_state"]);
			// }

			if ( result['address_details']["username"] ) {
				$('#addr2-username-row').show();
				$('#addr2-username').text(result['address_details']["username"]);
			}

			// if ( result['address_details']["types"] ) {
			// 	$('#addr2-types-row').show();
			// 	$('#addr2-types').text(result['address_details']["types"]);
			// }

			// if ( result['address_details']["status"] ) {
			// 	$('#addr2-status-row').show();
			// 	$('#addr2-status').text(result['address_details']["status"]);
			// }

			// Populate 2nd address's network details
			if ( result['network']["cidr"] ) {
				$('#net2-network-row').show();
				if ( result['network']['comment'] ) {
					$('#net2-network').text(result['network']["cidr"] + ' (' + result['network']['comment'] + ')');
				} else {
					$('#net2-network').text(result['network']["cidr"]);
				}
			}

			if ( result['network']["vlan_id"] ) {
				$('#net2-vlan-row').show();
				$('#net2-vlan').text(result['network']["vlan_id"] + ' (' + result['network']['vlan_name'] + ')');
			}

			if ( result['iplocation']["city"] ) {
				$('#net2-city-row').show();
				$('#net2-city').text(result['iplocation']["city"]);
			}
			if ( result['iplocation']["country_name"] ) {
				$('#net2-country-row').show();
				$('#net2-country').text(result['iplocation']["country_name"]);
			} else if ( result['iplocation']['country']) {
				$('#net2-country-row').show();
				$('#net2-country').text(result['iplocation']["country"]);
			}
			if ( result['iplocation']["isp"] ) {
				$('#net2-isp-row').show();
				$('#net2-isp').text(result['iplocation']["isp"]);
			}

		},
		error: function (xhr, status, error) {
			// $('#connect-ipv6').text("Not supported");
			$('#connect-ipv6').html('<i class="fa-solid fa-circle-xmark text-danger"></i> Not supported');
			//console.log(error);
		}
	});

}

$(document).ready(function () {
	/* extract the default ip detected */
	var default_address = $('#address1').text();
	//console.log("Connection from " + default_address);

	default_version = null;
	if (default_address.indexOf(':') != -1) {
		// default is IPv6 connection
		default_version = 6;
	} else {
		// default is IPv4 connection
		default_version = 4;
	}

	test_primary_url(default_version);

	test_secondary_url(default_version);

	const is_campus = JSON.parse(document.getElementById('campus_id').textContent);
	if (is_campus) {
		// Do additional tests for campus
		get_dns_info();
	}
	get_dns_info();
});
