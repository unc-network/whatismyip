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
	var icon, msg, cls;
	if (is_campus) {
		if (network_purpose == 'VPN') {
			icon = 'fa-shield text-success';
			msg  = 'You are connected through the campus VPN.';
		} else if (network_purpose == 'Wireless') {
			icon = 'fa-wifi text-success';
			msg  = 'You are connected to the campus wireless network.';
		} else {
			icon = 'fa-building text-success';
			msg  = 'You are connected to the campus network.';
		}
	} else {
		icon = 'fa-earth-americas text-secondary';
		msg  = 'You are connected from off campus over the Internet.';
	}
	$('#intro_text').html(`<div class="intro-status"><i class="fa-solid ${icon} me-2"></i>${msg}</div>`);
}

function test_primary_url(default_version) {
	// call the test url and display address information
	var simulate = !!$('#connect-test').data('simulate');

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
		url: test_url + "/hostinfo" + (simulate ? '?simulate=4' : ''),
		dataType: "json",
		success: function (result, status, xhr) {
			// $('#connect-ipv4').text("Supported");
			$('#connect-ipv4').html('<i class="fa-solid fa-circle-check text-success"></i> Supported');
			//console.log("Host check from " + result["address"]);

			if ( default_version == 4 ) {
				$('#first_address_section').show();
				$('#address1').text(result["client_address"]);
				$('#address_box .ip-bar-label').text('IPv4');
				set_intro_text(result['is_campus'], result['network']['purpose']);
			} else {
				$('#second_address_section').show();
				$('#address2').text(result["client_address"]);
				$('#additional_ip .ip-bar-label').text('IPv4');
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
			if ( result['iplocation']["region"] ) {
				$('#net1-region-row').show();
				$('#net1-region').text(result['iplocation']["region"]);
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
			if ( result['iplocation']["org"] ) {
				$('#net1-org-row').show();
				$('#net1-org').text(result['iplocation']["org"]);
			}
			if ( result['iplocation']["asn"] ) {
				$('#net1-asn-row').show();
				$('#net1-asn').text(result['iplocation']["asn"]);
			}
			var net1_flags = [];
			if (result['iplocation']['mobile']) net1_flags.push('<i class="fa-solid fa-mobile-screen text-info" title="Mobile connection"></i> Mobile');
			if (result['iplocation']['proxy'])  net1_flags.push('<i class="fa-solid fa-shield text-warning" title="Proxy or VPN detected"></i> Proxy / VPN');
			if (result['iplocation']['hosting']) net1_flags.push('<i class="fa-solid fa-server text-secondary" title="Hosting provider or datacenter"></i> Hosting');
			if (net1_flags.length > 0) {
				$('#net1-flags-row').show();
				$('#net1-flags').html(net1_flags.join('&ensp;'));
			}

			// Do the Map work
			if (result['nac']['nit_building'] && result['nac']['nit_building']['address']) {
				// Building lat/lon preferred; address passed as fallback for Google Maps geocoder
				var bldgMapLat = parseFloat(result['nac']['nit_building']['latitude']);
				var bldgMapLon = parseFloat(result['nac']['nit_building']['longitude']);
				loadCampusMap(result['nac']['nit_building']['address'], result['nac']['nit_building']['full_name'], bldgMapLat, bldgMapLon);
			} else {
				// Approximate IP geolocation (city-level) for everyone else
				var mapLat = parseFloat(result['iplocation']['lat']);
				var mapLon = parseFloat(result['iplocation']['lon']);
				// Skip if geolocation failed (null, NaN, or the 0,0 fallback ip-api.com returns on lookup failure)
				if (!isNaN(mapLat) && !isNaN(mapLon) && !(mapLat === 0 && mapLon === 0)) {
					var mapLabel = result['iplocation']['city'] || 'IP location';
					loadLatLonMap(mapLat, mapLon, mapLabel);
				}
			}

			// dump nac data
			var nacIp  = result['client_address'];
			var nacMac = result['address_details'] && result['address_details']['mac']
				? result['address_details']['mac'].toLowerCase() : null;

			function nacCell(key, value) {
				var warn = '';
				if (key === 'ipAddress' && nacIp && value !== nacIp) {
					warn = ' <i class="fa-solid fa-triangle-exclamation text-warning ms-1" title="Does not match detected IPv4 address (' + nacIp + ')"></i>';
				}
				if (key === 'macAddress' && nacMac && value.toLowerCase() !== nacMac) {
					warn = ' <i class="fa-solid fa-triangle-exclamation text-warning ms-1" title="Does not match MAC from IPAM (' + result['address_details']['mac'] + ')"></i>';
				}
				return value + warn;
			}

			if (result['nac']['endSystem']) {
				$('#toggle-button').show();
				$('#additional-info').show();
				$('#nac-col').show();
				$('#nac-card').show();
				for (const [key, value] of Object.entries(result['nac']['endSystem'])) {
					if (value) {
						$('#nac-table tbody').append(`<tr><th>${key}</th><td>${nacCell(key, value)}</td></tr>`);
					}
				}
			}
			if (result['nac']['endSystemInfo']) {
				$('#additional-info').show();
				$('#nac-col').show();
				$('#nac-card').show();
				for (const [key, value] of Object.entries(result['nac']['endSystemInfo'])) {
					if (value) {
						$('#nac-table tbody').append(`<tr><th>${key}</th><td>${nacCell(key, value)}</td></tr>`);
					}
				}
			}

			// dump building data
			if (result['nac']['nit_building'] && Object.keys(result['nac']['nit_building']).length > 0) {
				var bldg = result['nac']['nit_building'];
				$('#detail-col').show();
				$('#bldg-card').show();
				if (bldg['official_name'] || bldg['full_name']) {
					$('#bldg-name-row').show();
					$('#bldg-name').text(bldg['official_name'] || bldg['full_name']);
				}
				if (bldg['address']) {
					$('#bldg-address-row').show();
					$('#bldg-address').text(bldg['address']);
				}
				if (bldg['building_id']) {
					$('#bldg-id-row').show();
					$('#bldg-id').text(bldg['building_id']);
				}
			}

			// User device card — populate once; both callbacks return identical data
			populateDeviceCard(result['user_device']);

			// Network configuration card — IPv4 section (populated by primary/IPv4 callback)
			var hasV4Config = false;
			if (result['network']['netmask']) {
				$('#net-config-v4-mask-row').show();
				$('#net-config-v4-mask').text(result['network']['netmask']);
				hasV4Config = true;
			}
			if (result['network']['dhcp_routers']) {
				$('#net-config-v4-gateway-row').show();
				$('#net-config-v4-gateway').text(result['network']['dhcp_routers']);
				hasV4Config = true;
			}
			if (result['network']['dhcp_dns_servers'] && result['network']['dhcp_dns_servers'].length > 0) {
				$('#net-config-v4-dns-row').show();
				$('#net-config-v4-dns').html(result['network']['dhcp_dns_servers'].join('<br>'));
				hasV4Config = true;
			}
			if (result['network']['dhcp_domain_name']) {
				$('#net-config-v4-domain-row').show();
				$('#net-config-v4-domain').text(result['network']['dhcp_domain_name']);
				hasV4Config = true;
			}
			if (result['network']['router_device']) {
				$('#net-config-v4-router-row').show();
				$('#net-config-v4-router').text(result['network']['router_device']);
				hasV4Config = true;
			}
			if (hasV4Config) {
				$('#net-config-v4').show();
				$('#net-config-card').show();
				$('#detail-col').show();
				$('#additional-info').show();
				$('#toggle-button').show();
			}
		},
		error: function (xhr, status, error) {
			// $('#connect-ipv4').text("Not supported");
			$('#connect-ipv4').html('<i class="fa-solid fa-triangle-exclamation text-warning"></i> Not supported');
			//console.log(error);
		}
	});

}

function populateDeviceCard(ud) {
	if (!ud || $('#device-card').is(':visible')) return;
	var hasInfo = false;
	if (ud['browser'] && ud['browser'] !== 'Other') {
		var browser = ud['browser'];
		if (ud['browser_version']) browser += ' ' + ud['browser_version'];
		$('#device-browser-row').show();
		$('#device-browser').text(browser);
		hasInfo = true;
	}
	if (ud['os'] && ud['os'] !== 'Other') {
		var os = ud['os'];
		if (ud['os_version']) os += ' ' + ud['os_version'];
		$('#device-os-row').show();
		$('#device-os').text(os);
		hasInfo = true;
	}
	var deviceType = ud['is_bot'] ? 'Bot / Crawler' : ud['is_mobile'] ? 'Mobile' : ud['is_tablet'] ? 'Tablet' : ud['is_pc'] ? 'PC / Desktop' : null;
	if (deviceType) {
		$('#device-type-row').show();
		$('#device-type').text(deviceType);
		hasInfo = true;
	}
	if (ud['device_family']) {
		var model = (ud['device_brand'] && ud['device_brand'] !== ud['device_family'])
			? ud['device_brand'] + ' ' + ud['device_family']
			: ud['device_family'];
		$('#device-model-row').show();
		$('#device-model').text(model);
		hasInfo = true;
	}
	if (hasInfo) {
		$('#device-card').show();
		$('#detail-col').show();
		$('#additional-info').show();
		$('#toggle-button').show();
	}
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

async function test_dns_security_filtering(test_url) {
	// Fetch test_url in the visitor's browser.
	// When filtering is INACTIVE: the test site loads (returns false).
	// When filtering is ACTIVE: the connection is blocked (returns true).
	const controller = new AbortController();
	const timeoutId = setTimeout(() => controller.abort(), 5000);

	try {
		await fetch(test_url, {
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

	const dns_test_url = $('#dns-test').data('dns_test_url') || '';

	// Add Security Filtering row only if a test URL is configured
	if (dns_test_url) {
		append_dns_table_row(
			'DNS Security Filtering',
			'<i class="fa-solid fa-question"></i> Testing',
			'security-filtering-row',
			true
		);
	}
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

					append_dns_table_row('EDNS Client Subnet', clientSubnetDetails);
				}
			}
		},
		error: function (xhr, status, error) {
			console.dir(`DNS provider test failed: ${error}`)
		}
	});

	// Test DNS security filtering by attempting to fetch the configured test URL
	if (dns_test_url) {
		test_dns_security_filtering(dns_test_url)
			.then(isFiltered => {
				let filteringHtml;
				if (isFiltered === true) {
					filteringHtml = `<i class="fa-solid fa-circle-check text-success"></i> Active`;
				} else if (isFiltered === false) {
					filteringHtml = `<i class="fa-solid fa-triangle-exclamation text-warning"></i> Inactive`;
				} else {
					filteringHtml = `<i class="fa-solid fa-circle-question text-warning"></i> Unable to verify`;
				}
				$('#security-filtering-row .dns-row-value').html(filteringHtml);
			})
			.catch(error => {
				console.error('DNS security filtering test error:', error);
				$('#security-filtering-row .dns-row-value').html(`<i class="fa-solid fa-circle-question text-warning"></i> Unable to verify`);
			});
	}
}

function test_secondary_url(default_version) {
	// test secondary url
	var simulate = !!$('#connect-test').data('simulate');

	var test_url = $('#connect-test').data('ipv6_url');
	if (!test_url) {
		if (!simulate) {
			$('#connect-ipv6').html('<i class="fa-solid fa-minus text-secondary"></i> Not configured');
			return;
		}
		// In simulate mode, fall back to the IPv4 server so ?simulate=6 still works
		test_url = $('#connect-test').data('ipv4_url') || window.location.origin;
	}

	// handle starting state
	if ( default_version == 6 ) {
		$('#connect-default').text("IPv6");
		$('#connect-ipv6').html('<i class="fa-solid fa-question"></i> Testing');
	}

	// Make AJAX call to the API to get the ipv6 address
	$.ajax({
		type: "GET",
		url: test_url + "/hostinfo" + (simulate ? '?simulate=6' : ''),
		dataType: "json",
		success: function (result, status, xhr) {
			// $('#connect-ipv6').text("Supported");
			$('#connect-ipv6').html('<i class="fa-solid fa-circle-check text-success"></i> Supported');
			//console.log("Host check from " + result["address"]);

			if ( default_version == 6 ) {
				$('#first_address_section').show();
				$('#address1').text(result["client_address"]);
				$('#address_box .ip-bar-label').text('IPv6');
				set_intro_text(result['is_campus'], result['network']['purpose']);
			} else {
				$('#second_address_section').show();
				$('#address2').text(result["client_address"]);
				$('#additional_ip .ip-bar-label').text('IPv6');
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
			if ( result['iplocation']["region"] ) {
				$('#net2-region-row').show();
				$('#net2-region').text(result['iplocation']["region"]);
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
			if ( result['iplocation']["org"] ) {
				$('#net2-org-row').show();
				$('#net2-org').text(result['iplocation']["org"]);
			}
			if ( result['iplocation']["asn"] ) {
				$('#net2-asn-row').show();
				$('#net2-asn').text(result['iplocation']["asn"]);
			}
			var net2_flags = [];
			if (result['iplocation']['mobile']) net2_flags.push('<i class="fa-solid fa-mobile-screen text-info" title="Mobile connection"></i> Mobile');
			if (result['iplocation']['proxy'])  net2_flags.push('<i class="fa-solid fa-shield text-warning" title="Proxy or VPN detected"></i> Proxy / VPN');
			if (result['iplocation']['hosting']) net2_flags.push('<i class="fa-solid fa-server text-secondary" title="Hosting provider or datacenter"></i> Hosting');
			if (net2_flags.length > 0) {
				$('#net2-flags-row').show();
				$('#net2-flags').html(net2_flags.join('&ensp;'));
			}

			// User device card — populate once; both callbacks return identical data
			populateDeviceCard(result['user_device']);

			// Network configuration card — IPv6 section (populated by secondary/IPv6 callback)
			var hasV6Config = false;
			if (result['network']['prefixlen']) {
				$('#net-config-v6-prefix-row').show();
				$('#net-config-v6-prefix').text('/' + result['network']['prefixlen']);
				hasV6Config = true;
			}
			if (result['network']['dhcp_routers']) {
				$('#net-config-v6-gateway-row').show();
				$('#net-config-v6-gateway').text(result['network']['dhcp_routers']);
				hasV6Config = true;
			}
			if (result['network']['dhcp_dns_servers'] && result['network']['dhcp_dns_servers'].length > 0) {
				$('#net-config-v6-dns-row').show();
				$('#net-config-v6-dns').html(result['network']['dhcp_dns_servers'].join('<br>'));
				hasV6Config = true;
			}
			if (result['network']['dhcp_domain_name']) {
				$('#net-config-v6-domain-row').show();
				$('#net-config-v6-domain').text(result['network']['dhcp_domain_name']);
				hasV6Config = true;
			}
			if (result['network']['router_device']) {
				$('#net-config-v6-router-row').show();
				$('#net-config-v6-router').text(result['network']['router_device']);
				hasV6Config = true;
			}
			if (hasV6Config) {
				$('#net-config-v6').show();
				$('#net-config-card').show();
				$('#detail-col').show();
				$('#additional-info').show();
				$('#toggle-button').show();
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
