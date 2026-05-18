/*!
  * whatismyip.js
  * Helper library for https://whatismyip.unc.edu
  */

function showCopyNotification(message, isError = false) {
	let notification = $('#copy-notification');

	if (notification.length === 0) {
		$('body').append('<div id="copy-notification" role="status" aria-live="polite"></div>');
		notification = $('#copy-notification');
		notification.css({
			position: 'fixed',
			top: '80px',
			right: '20px',
			zIndex: 2000,
			padding: '10px 14px',
			borderRadius: '6px',
			color: '#ffffff',
			fontWeight: '600',
			boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
			display: 'none'
		});
	}

	notification.stop(true, true);
	notification.text(message);
	notification.css('backgroundColor', isError ? '#b42318' : '#4b9cd3');
	notification.fadeIn(150).delay(1300).fadeOut(250);
}

function getAddressLabel(text) {
	if (/^\d{1,3}(\.\d{1,3}){3}$/.test(text)) {
		return 'IPv4 address';
	}

	if (text.includes(':')) {
		return 'IPv6 address';
	}

	return 'Address';
}

function copyAddress(addressSelector) {
	const text = $(addressSelector).text().trim();
	const addressLabel = getAddressLabel(text);

	if (!text || text === 'loading...') {
		showCopyNotification('Address is not available yet', true);
		return;
	}

	navigator.clipboard.writeText(text)
		.then(() => {
			showCopyNotification(`${addressLabel} copied to your clipboard`);
		})
		.catch((err) => {
			console.error('Failed to copy the address!', err);
			showCopyNotification('Unable to copy address', true);
		});
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

			// Do the Map work
			if (result['nac']['nit_building'] && result['nac']['nit_building']['address']) {
				loadCampusMap(result['nac']['nit_building']['address'], result['nac']['nit_building']['full_name']);
			}
			// } else if (is_campus && result['iplocation']['lat'] && result['iplocation']['lon']) {
			// 	add_marker(result['iplocation']['lat'],result['iplocation']['lon'],'Your IP location');
			// }

			// dump nac data
			if (result['nac']['endSystem']) {
				$('#toggle-button').show();
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
			if (result['nac']['nit_building'] && Object.keys(result['nac']['nit_building']).length > 0) {
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
			$('#connect-ipv4').html('<i class="fa-solid fa-triangle-exclamation text-warning"></i> Not supported');
			//console.log(error);
		}
	});

}

let map;
let geocoder;
let mapInitialized = false;

function loadCampusMap(address, title) {
	if (!address) {
		return;
	}

	$('#map_card').show();

	if (mapInitialized) {
		codeAddress(address, title);
		return;
	}

	mapInitialized = true;
	initMap()
		.then(() => {
			codeAddress(address, title);
		})
		.catch((error) => {
			console.error('Failed to load campus map', error);
			$('#map_card').hide();
			mapInitialized = false;
		});
}

async function initMap() {
	// Request needed libraries asynchronously
	const { Map } = await google.maps.importLibrary("maps");
	const { Geocoder } = await google.maps.importLibrary("geocoding");
	const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");

	// Initialize the map
	var defaultLocation = {lat: 35.9049, lng: -79.0469};
	map = new Map(document.getElementById("map"), {
		center: defaultLocation, 
		zoom: 15,
		mapId: 'LOCATION_MAP_ID',
		disableDefaultUI: true,
	});
	geocoder = new Geocoder();
}

async function add_marker (lat, lon, label) {
	// Translate lat/lon to position to add map marker
	var position = {lat: lat, lon: lon};
	addAdvancedMarker(position, label);
}

function codeAddress(address, title) {
	// Translate address to a map marker
	console.log(`Mapping address ${address}`);
	geocoder.geocode({ address: address }, (results, status) => {
		if (status === "OK") {
			map.setCenter(results[0].geometry.location);
			addAdvancedMarker(results[0].geometry.location, title); 
		} else {
			console.log("Geocode was not successful for the following reason: " + status);
		}
	});
}

async function addAdvancedMarker(position, title) {
	// Add a marker to the map
	console.log(`Adding map marker at ${position} titled ${title}`)
	const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
	new AdvancedMarkerElement({
		map: map,
		position: position,
		title: title,
	});
}

function createRandomString(length) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

function append_dns_table_row(label, value, rowId = null, useHtmlValue = false) {
	const row = $('<tr>');
	if (rowId) {
		row.attr('id', rowId);
	}

	const cell = $('<td colspan="2"></td>');
	cell.append(`<div class="fw-bold">${label}</div>`);
	const valueContainer = $('<div class="dns-row-value text-break" style="white-space: pre-line;"></div>');
	if (useHtmlValue) {
		valueContainer.html(value);
	} else {
		valueContainer.text(value);
	}
	cell.append(valueContainer);
	row.append(cell);

	$('#dns-table tbody').append(row);
}

async function test_dns_security_filtering() {
	// Test if DNS security filtering is active using Akamai's phishing test URL.
	// When filtering is INACTIVE: the test site loads successfully (returns a warning page).
	// When filtering is ACTIVE: the site is blocked by the filter and the fetch fails.
	const controller = new AbortController();
	const timeoutId = setTimeout(() => controller.abort(), 5000);

	try {
		await fetch('https://www.akamaietpphishingtest.com/', {
			method: 'HEAD',
			signal: controller.signal,
			mode: 'no-cors',
			cache: 'no-store',
			credentials: 'omit'
		});

		return false; // Site loaded successfully - filtering is INACTIVE
	} catch (error) {
		if (error.name === 'AbortError') {
			return null; // Timeout - inconclusive
		}
		if (error.name === 'TypeError') {
			return true; // Connection blocked - filtering is ACTIVE
		}
		return null; // Other error - inconclusive
	} finally {
		clearTimeout(timeoutId);
	}
}

function get_dns_info() {
	// testing DNS identification
	// https://ip-api.com/docs/dns
	
	// Add Security Filtering row first (will be updated once test completes)
	append_dns_table_row(
		'Security Filtering',
		'<i class="fa-solid fa-question"></i> Testing',
		'security-filtering-row',
		true
	);
	$('#dns-test').show();
	
	tmp_name = createRandomString(32);
	const test_url = `https://${tmp_name}.edns.ip-api.com/json`;

	$.ajax({
		type: "GET",
		url: test_url,
		dataType: "json",
		success: function (result, status, xhr) {
			if (result['dns']) {
				let geo = result['dns']['geo']
				let ip = result['dns']['ip']

				// Add DNS provider details as one section to reduce vertical space.
				if (geo || ip) {
					let providerDetails = geo || '';
					if (geo && ip) {
						providerDetails = `${geo}\n${ip}`;
					} else if (ip) {
						providerDetails = ip;
					}

					append_dns_table_row('Internet DNS Provider', providerDetails);
				}
			}

			if (result['edns']) {
				let geo = result['edns']['geo']
				let ip = result['edns']['ip']

				if (geo || ip) {
					let clientSubnetDetails = geo || '';
					if (geo && ip) {
						clientSubnetDetails = `${geo}\n${ip}`;
					} else if (ip) {
						clientSubnetDetails = ip;
					}

					append_dns_table_row('Client Subnet', clientSubnetDetails);
				}
			}
		},
		error: function (xhr, status, error) {
			console.dir(`DNS provider test failed: ${error}`)
		}
	});

	// Test DNS security filtering by attempting to fetch the test domain
	test_dns_security_filtering()
		.then(isFiltered => {
			let filteringHtml;
			if (isFiltered === true) {
				filteringHtml = `<i class="fa-solid fa-circle-check text-success"></i> Active`;
			} else if (isFiltered === false) {
				filteringHtml = `<i class="fa-solid fa-triangle-exclamation text-warning"></i> Inactive`;
			} else {
				filteringHtml = `<i class="fa-solid fa-circle-question text-warning"></i> Unable to verify`;
			}
			
			// Update the Security Filtering row with the result
			$('#security-filtering-row .dns-row-value').html(filteringHtml);
		})
		.catch(error => {
			console.error('DNS security filtering test error:', error);
			$('#security-filtering-row .dns-row-value').html(`<i class="fa-solid fa-circle-question text-warning"></i> Unable to verify`);
		});
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
			$('#connect-ipv6').html('<i class="fa-solid fa-triangle-exclamation text-warning"></i> Not supported');
			//console.log(error);
		}
	});

}

$(document).ready(function () {
	// Extract information passed from initial connection
	const is_campus = JSON.parse(document.getElementById('is_campus').textContent);
	const default_address = JSON.parse(document.getElementById('default_address').textContent);
	//console.log("Connection from " + default_address );

	const isLocalhost = window.location.hostname === "localhost" || 
						window.location.hostname === "127.0.0.1" ||
						window.location.hostname === "::1"; // IPv6 loopback address

	// Setup Google Map
	//initMap();

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

	// if (isLocalhost || is_campus) {
		// console.log(`Doing extended testing for campus`);
		if ('requestIdleCallback' in window) {
			window.requestIdleCallback(() => get_dns_info(), { timeout: 2000 });
		} else {
			setTimeout(get_dns_info, 0);
		}
	// }
});
