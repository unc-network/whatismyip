/*!
  * whatismyip.js
  * Helper library for https://whatismyip.unc.edu
  */

function formatIPAddress(ip) {
	return $('<span>').text(ip).html().replace(/([.:])/g, '$1<wbr>');
}

var reportDataPrimary = null;
var reportDataSecondary = null;
var reportNetworkPurpose = null;
var reportClockStatus = null;
var reportConnectV4 = '—';
var reportConnectV6 = '—';
var reportDnsProviderGeo = null;
var reportDnsProviderIp = null;
var reportDnsEdnsGeo = null;
var reportDnsEdnsIp = null;
var reportDnsFiltering = null;
var reportInternetIp = null;

function buildNacDiagram(nac, userDevice) {
	var es = nac.endSystem || {};
	var bldg = nac.nit_building || {};
	var isWireless = es.connection_type === 'wireless';

	var bldgName = bldg.number
		? 'Bldg ' + bldg.number
		: (bldg.official_name || bldg.full_name || '');
	var bldgSub = (bldg.official_name || bldg.full_name || '');

	function esc(s) {
		return $('<span>').text(String(s)).html();
	}

	function node(icon, label, sub) {
		return '<div class="nac-node">'
			+ '<div class="nac-icon"><i class="fa-solid ' + icon + '" aria-hidden="true"></i></div>'
			+ '<div class="nac-text">'
			+ '<div class="nac-label">' + esc(label) + '</div>'
			+ (sub ? '<div class="nac-sub">' + esc(sub) + '</div>' : '')
			+ '</div>'
			+ '</div>';
	}

	function connector(wireless, linkLabel, linkClass) {
		var inner = '<div class="nac-connector' + (wireless ? ' wireless' : '') + '" aria-hidden="true"></div>';
		if (linkLabel) {
			return '<div class="nac-connector-wrap">'
				+ inner
				+ '<div class="nac-link-label' + (linkClass ? ' ' + linkClass : '') + '">' + esc(linkLabel) + '</div>'
				+ '</div>';
		}
		return inner;
	}

	var deviceIcon = (userDevice && (userDevice.is_mobile || userDevice.is_tablet))
		? 'fa-mobile-screen' : 'fa-laptop';

	var html = '<div class="nac-diagram" role="img" aria-label="Network connection path">';

	if (isWireless) {
		var controller = es.wireless_controller || es.switchIP || null;
		var wirelessLabel = '', wirelessClass = '';
		if (nac.meraki_signal && nac.meraki_signal.rssi != null) {
			var rssi = nac.meraki_signal.rssi;
			var quality = rssi >= -65 ? 'Good' : rssi >= -70 ? 'Fair' : 'Poor';
			wirelessClass = rssi >= -65 ? 'signal-good' : rssi >= -70 ? 'signal-fair' : 'signal-poor';
			wirelessLabel = rssi + ' dBm — ' + quality;
		}
		html += node(deviceIcon, 'Your Device', es.macAddress || '');
		html += connector(true, wirelessLabel, wirelessClass);
		html += node('fa-wifi', es.wireless_ap_name || 'Access Point', es.wireless_ssid || '');
		if (bldgName) {
			html += connector(false);
			html += node('fa-building', bldgName, bldgSub !== bldgName ? bldgSub : '');
		}
		if (controller) {
			html += connector(false);
			html += node('fa-server', controller, 'Wireless Controller');
		}
	} else {
		html += node(deviceIcon, 'Your Device', es.macAddress || '');
		if (es.switchPortId) {
			html += connector(false);
			html += node('fa-ethernet', 'Port ' + es.switchPortId, 'Switch Port');
		}
		if (es.switchIP) {
			html += connector(false);
			html += node('fa-network-wired', es.switchIP, 'Switch');
		}
		if (bldgName) {
			html += connector(false);
			html += node('fa-building', bldgName, bldgSub !== bldgName ? bldgSub : '');
		}
	}

	html += '</div>';
	return html;
}

function showCopyNotification(message, isError = false) {
	const notification = $('#copy-notification');
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

function checkAddressMismatch() {
	if (!reportDataPrimary || !reportDataSecondary) return;
	if (reportDataPrimary['is_campus'] === reportDataSecondary['is_campus']) return;

	var offCampus = reportDataPrimary['is_campus'] ? reportDataSecondary : reportDataPrimary;
	var isp = (offCampus['iplocation'] && offCampus['iplocation']['isp']) || '';
	var note;

	if (/icloud|private relay/i.test(isp)) {
		note = 'iCloud Private Relay is routing one of your addresses off-campus.';
	} else if (offCampus['iplocation'] && offCampus['iplocation']['proxy']) {
		note = 'A VPN or proxy service is routing one of your addresses off-campus.';
	} else {
		note = 'Your two addresses are on different networks — one campus, one off-campus.';
	}

	$('#intro_text .intro-status').append(
		`<div class="mt-1 small text-muted"><i class="fa-solid fa-circle-info text-info me-1" aria-hidden="true"></i>${note}</div>`
	);
}

function showPrimaryLoadError() {
	$('#intro_text').html('<div class="intro-status text-warning"><i class="fa-solid fa-triangle-exclamation me-2" aria-hidden="true"></i>Connection details could not be retrieved. <a href="javascript:void(0)" onclick="location.reload()">Refresh to try again.</a></div>');
	$('#report-btn').prop('disabled', true);
}

function set_intro_text(is_campus, network_purpose) {
	var icon, msg;
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
	var mainHtml = `<i class="fa-solid ${icon} me-2" aria-hidden="true"></i>${msg}`;
	if ($('#intro-main-status').length) {
		// Update only the main line — preserve any sub-lines appended by renderNATResult.
		$('#intro-main-status').html(mainHtml);
	} else {
		$('#intro_text').html(`<div class="intro-status"><div id="intro-main-status">${mainHtml}</div></div>`);
	}
}

function downloadReport() {
	if (!reportDataPrimary) {
		alert('Connection data is still loading — please try again in a moment.');
		return;
	}

	var now = new Date();
	var ts = now.toLocaleString('en-US', {
		weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
		hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short'
	});

	function e(str) {
		var d = document.createElement('div');
		d.textContent = String(str);
		return d.innerHTML;
	}
	function rpt(label, value) {
		if (!value) return '';
		return `<tr><th>${e(String(label))}</th><td>${e(String(value))}</td></tr>`;
	}
	function section(title, rows) {
		var content = rows.filter(Boolean).join('');
		if (!content) return '';
		return `<h2>${e(title)}</h2><table><tbody>${content}</tbody></table>`;
	}

	var r = reportDataPrimary;
	var primaryIsV6 = r.client_address && r.client_address.includes(':');
	var primaryLabel = primaryIsV6 ? 'IPv6' : 'IPv4';
	var secondaryLabel = primaryIsV6 ? 'IPv4' : 'IPv6';

	var statusMsg;
	if (r.is_campus) {
		var purpose = r.network && r.network.purpose;
		if (purpose === 'VPN') statusMsg = 'Connected through the campus VPN';
		else if (purpose === 'Wireless') statusMsg = 'Connected to the campus wireless network';
		else statusMsg = 'Connected to the campus network';
	} else {
		statusMsg = 'Connected from off campus over the Internet';
	}

	var ad = r.address_details || {};
	var net = r.network || {};
	var loc = r.iplocation || {};

	var primaryNames = (ad.names && ad.names.length)
		? [...new Set(ad.names.map(n => n.toLowerCase()))].join(', ')
		: (r.ptr || '');
	var primaryFlags = [loc.mobile ? 'Mobile' : null, loc.proxy ? 'Proxy/VPN' : null, loc.hosting ? 'Hosting' : null].filter(Boolean).join(', ');

	var primarySection = section('Primary Address (' + primaryLabel + ')', [
		rpt('IP Address', r.client_address),
		rpt('PTR / Host Names', primaryNames),
		rpt('Network', net.cidr ? (net.comment ? net.cidr + ' (' + net.comment + ')' : net.cidr) : null),
		rpt('VLAN', net.vlan_id ? net.vlan_id + ' (' + net.vlan_name + ')' : null),
		rpt('City', loc.city),
		rpt('Region', loc.region),
		rpt('Country', loc.country_name || loc.country),
		rpt('ISP', loc.isp),
		rpt('Organization', loc.org),
		rpt('ASN', loc.asn),
		rpt('Connection Flags', primaryFlags),
		rpt('MAC Address', ad.mac),
		rpt('Username', ad.username),
		rpt('IPAM Comment', ad.comment),
	]);

	var secondarySection = '';
	if (reportDataSecondary) {
		var r2 = reportDataSecondary;
		var ad2 = r2.address_details || {};
		var net2 = r2.network || {};
		var loc2 = r2.iplocation || {};
		var s2Names = (ad2.names && ad2.names.length)
			? [...new Set(ad2.names.map(n => n.toLowerCase()))].join(', ')
			: (r2.ptr || '');
		secondarySection = section('Secondary Address (' + secondaryLabel + ')', [
			rpt('IP Address', r2.client_address),
			rpt('PTR / Host Names', s2Names),
			rpt('Network', net2.cidr ? (net2.comment ? net2.cidr + ' (' + net2.comment + ')' : net2.cidr) : null),
			rpt('VLAN', net2.vlan_id ? net2.vlan_id + ' (' + net2.vlan_name + ')' : null),
			rpt('City', loc2.city),
			rpt('Region', loc2.region),
			rpt('Country', loc2.country_name || loc2.country),
			rpt('ISP', loc2.isp),
			rpt('Organization', loc2.org),
			rpt('ASN', loc2.asn),
		]);
	}

	var connectSection = section('Connectivity', [
		rpt('Default Protocol', primaryLabel),
		rpt('IPv4', reportConnectV4),
		rpt('IPv6', reportConnectV6),
		rpt('Internet Address', reportInternetIp ? reportInternetIp + ' (differs from campus address)' : null),
	]);

	var dnsProvider = [reportDnsProviderGeo, reportDnsProviderIp].filter(Boolean).join(' — ');
	var dnsEdns = [reportDnsEdnsGeo, reportDnsEdnsIp].filter(Boolean).join(' — ');
	var dnsSection = section('DNS', [
		rpt('Internet DNS Provider', dnsProvider),
		rpt('EDNS Client Subnet', dnsEdns),
		rpt('Campus DNS Security', reportDnsFiltering),
	]);

	var nacRows = [];
	if (r.nac) {
		if (r.nac.endSystem) Object.entries(r.nac.endSystem).forEach(([k, v]) => { if (v) nacRows.push(rpt(k, v)); });
		if (r.nac.endSystemInfo) Object.entries(r.nac.endSystemInfo).forEach(([k, v]) => { if (v) nacRows.push(rpt(k, v)); });
	}
	var nacSection = nacRows.length ? section('Campus NAC Details', nacRows) : '';

	var merakiSection = '';
	if (r.nac && (r.nac.meraki_client || r.nac.meraki_ap || r.nac.meraki_signal)) {
		var mc = r.nac.meraki_client || {};
		var ma = r.nac.meraki_ap || {};
		var ms = r.nac.meraki_signal || {};
		var rssiText = ms.rssi !== undefined && ms.rssi !== null
			? ms.rssi + ' dBm (' + (ms.rssi >= -65 ? 'Good' : ms.rssi >= -70 ? 'Fair' : 'Poor') + ')'
			: null;
		var snrText = ms.snr !== undefined && ms.snr !== null
			? ms.snr + ' dB (' + (ms.snr >= 25 ? 'Good' : ms.snr >= 15 ? 'Fair' : 'Poor') + ')'
			: null;
		var lastSeenText = mc.last_seen ? new Date(mc.last_seen * 1000).toLocaleString() : null;
		merakiSection = section('Wireless Connection', [
			rpt('Manufacturer', mc.manufacturer),
			rpt('Device', mc.description),
			rpt('OS', mc.os),
			rpt('User', mc.user),
			rpt('Status', mc.status),
			rpt('SSID', mc.ssid),
			rpt('VLAN', mc.vlan),
			rpt('Last Seen', lastSeenText),
			rpt('Client MAC', mc.mac),
			rpt('Signal (RSSI)', rssiText),
			rpt('Signal/Noise (SNR)', snrText),
			rpt('Capabilities', mc.wireless_capabilities),
			rpt('AP Name', ma.name),
			rpt('AP Model', ma.model),
		]);
	}

	var bldgSection = '';
	if (r.nac && r.nac.nit_building && Object.keys(r.nac.nit_building).length) {
		var bldg = r.nac.nit_building;
		bldgSection = section('Building', [
			rpt('Name', bldg.official_name || bldg.full_name),
			rpt('Address', bldg.address),
			rpt('Building ID', bldg.building_id),
		]);
	}

	var cfgRows = [];
	var hasV4cfg = net.netmask || net.dhcp_routers || (net.dhcp_dns_servers && net.dhcp_dns_servers.length) || net.dhcp_domain_name || net.router_device;
	if (hasV4cfg) {
		cfgRows.push('<tr><td colspan="2" style="font-weight:700;background:#edf5fb;padding:4px 8px;">IPv4</td></tr>');
		if (net.netmask) cfgRows.push(rpt('Subnet Mask', net.netmask));
		if (net.dhcp_routers) cfgRows.push(rpt('Default Gateway', net.dhcp_routers));
		if (net.dhcp_dns_servers && net.dhcp_dns_servers.length) cfgRows.push(rpt('DNS Servers', net.dhcp_dns_servers.join(', ')));
		if (net.dhcp_domain_name) cfgRows.push(rpt('Search Domain', net.dhcp_domain_name));
		if (net.router_device) cfgRows.push(rpt('Router Device', net.router_device));
	}
	if (reportDataSecondary) {
		var net2b = reportDataSecondary.network || {};
		var hasV6cfg = net2b.prefixlen || net2b.dhcp_routers || (net2b.dhcp_dns_servers && net2b.dhcp_dns_servers.length) || net2b.dhcp_domain_name || net2b.router_device;
		if (hasV6cfg) {
			cfgRows.push('<tr><td colspan="2" style="font-weight:700;background:#edf5fb;padding:4px 8px;">IPv6</td></tr>');
			if (net2b.prefixlen) cfgRows.push(rpt('Prefix Length', '/' + net2b.prefixlen));
			if (net2b.dhcp_routers) cfgRows.push(rpt('Default Gateway', net2b.dhcp_routers));
			if (net2b.dhcp_dns_servers && net2b.dhcp_dns_servers.length) cfgRows.push(rpt('DNS Servers', net2b.dhcp_dns_servers.join(', ')));
			if (net2b.dhcp_domain_name) cfgRows.push(rpt('Search Domain', net2b.dhcp_domain_name));
			if (net2b.router_device) cfgRows.push(rpt('Router Device', net2b.router_device));
		}
	}
	var netConfigSection = cfgRows.filter(Boolean).length
		? `<h2>Network Configuration</h2><table><tbody>${cfgRows.filter(Boolean).join('')}</tbody></table>`
		: '';

	var ud = r.user_device || {};
	var browser = (ud.browser && ud.browser !== 'Other') ? (ud.browser + (ud.browser_version ? ' ' + ud.browser_version : '')) : null;
	var os = (ud.os && ud.os !== 'Other') ? (ud.os + (ud.os_version ? ' ' + ud.os_version : '')) : null;
	var deviceType = ud.is_bot ? 'Bot / Crawler' : ud.is_mobile ? 'Mobile' : ud.is_tablet ? 'Tablet' : ud.is_pc ? 'PC / Desktop' : null;
	var model = ud.device_family ? ((ud.device_brand && ud.device_brand !== ud.device_family) ? ud.device_brand + ' ' + ud.device_family : ud.device_family) : null;
	var deviceSection = section('Device Information', [
		rpt('Browser', browser),
		rpt('Operating System', os),
		rpt('Device Type', deviceType),
		rpt('Device Model', model),
		rpt('Clock Sync', reportClockStatus),
	]);

	var origin = window.location.origin;

	var html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Network Diagnostic Report</title>
<style>
  body{font-family:Arial,Helvetica,sans-serif;font-size:11pt;color:#222;margin:15mm 20mm}
  h1{font-size:16pt;color:#13294B;margin:0 0 2px}
  h2{font-size:10.5pt;font-weight:700;color:#13294B;background:#EDF5FB;border-left:4px solid #4B9CD3;padding:5px 10px;margin:14px 0 0}
  table{width:100%;border-collapse:collapse;font-size:10pt}
  th{text-align:left;font-weight:600;width:38%;padding:3px 8px;vertical-align:top;background:#fafafa}
  td{padding:3px 8px;vertical-align:top;word-break:break-all}
  tr{border-bottom:1px solid #e8e8e8}
  .hdr{border-bottom:3px solid #4B9CD3;padding-bottom:10px;margin-bottom:12px}
  .sub{color:#5B6670;font-size:10pt;margin:2px 0 0}
  .ts{color:#888;font-size:9.5pt;margin:4px 0 0}
  .status{background:#EDF5FB;border-left:4px solid #4B9CD3;padding:7px 12px;margin:12px 0 14px;font-size:11pt;font-weight:600;color:#13294B}
  .ftr{margin-top:20px;border-top:1px solid #ddd;padding-top:8px;color:#aaa;font-size:9pt}
  a{color:#4B9CD3}
  @media print{body{margin:8mm 12mm}}
</style>
</head>
<body>
<div class="hdr">
  <h1>Network Diagnostic Report</h1>
  <p class="sub">UNC Chapel Hill ITS &mdash; What Is My IP?</p>
  <p class="ts">${e(ts)}</p>
</div>
<div class="status">${e(statusMsg)}</div>
${primarySection}
${secondarySection}
${connectSection}
${dnsSection}
${nacSection}
${merakiSection}
${bldgSection}
${netConfigSection}
${deviceSection}
<div class="ftr">Generated by <a href="${origin}">${e(origin)}</a> &nbsp;&bull;&nbsp; ${e(ts)}</div>
<script>window.print();<\/script>
</body>
</html>`;

	var win = window.open('', '_blank', 'width=820,height=960');
	if (win) {
		win.document.write(html);
		win.document.close();
	}
}

function test_primary_url(default_version) {
	// call the test url and display address information
	var simulate = !!$('#connect-test').data('simulate');

	// handle starting state
	if ( default_version == 4 ) {
		$('#connect-default').text("IPv4");
		// $('#connect-ipv4').text("Testing...");
		$('#connect-ipv4').html('<i class="fa-solid fa-question" aria-hidden="true"></i> Testing');
	}

	// Make AJAX call to the API to get the ipv4 address
	var test_url = $('#connect-test').data('ipv4_url')
	$.ajax({
		type: "GET",
		url: test_url + "/hostinfo" + (simulate ? '?simulate=4' : ''),
		dataType: "json",
		success: function (result, status, xhr) {
			// $('#connect-ipv4').text("Supported");
			$('#connect-ipv4').html('<i class="fa-solid fa-circle-check text-success" aria-hidden="true"></i> Supported');
			//console.log("Host check from " + result["address"]);

			if ( default_version == 4 ) {
				$('#first_address_section').show();
				$('#address1').html(formatIPAddress(result["client_address"]));
				$('#address_box .ip-bar-label').text('IPv4');
				set_intro_text(result['is_campus'], result['network']['purpose']);
			} else {
				$('#second_address_section').show();
				$('#address2').html(formatIPAddress(result["client_address"]));
				$('#additional_ip .ip-bar-label').text('IPv4');
				$('#second_address_section .ip-copy-card').removeClass('ip-loading');
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

			if ( result['iplocation']["isp"] ) {
				$('#net1-isp-row').show();
				$('#net1-isp').text(result['iplocation']["isp"]);
			}
			if ( result['iplocation']["org"] ) {
				$('#net1-org-row').show();
				$('#net1-org').text(result['iplocation']["org"]);
			}
			var net1city = result['iplocation']["city"], net1region = result['iplocation']["region"];
			var net1country = result['iplocation']["country_name"] || result['iplocation']["country"];
			if (net1city || net1region || net1country) {
				$('#net1-location-row').show();
				$('#net1-location').text([net1city, net1region, net1country].filter(Boolean).join(', '));
			}
			if ( result['iplocation']["asn"] ) {
				$('#net1-asn-row').show();
				$('#net1-asn').text(result['iplocation']["asn"]);
			}
			var net1_flags = [];
			if (result['iplocation']['mobile']) net1_flags.push('<i class="fa-solid fa-mobile-screen text-info" aria-hidden="true" title="Mobile connection"></i> Mobile');
			if (result['iplocation']['proxy'])  net1_flags.push('<i class="fa-solid fa-shield text-warning" aria-hidden="true" title="Proxy or VPN detected"></i> Proxy / VPN');
			if (result['iplocation']['hosting']) net1_flags.push('<i class="fa-solid fa-server text-secondary" aria-hidden="true" title="Hosting provider or datacenter"></i> Hosting');
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
			} else if (result['nac']['meraki_ap'] && result['nac']['meraki_ap']['lat'] && result['nac']['meraki_ap']['lon']) {
				// Meraki AP coordinates — more precise than IP geolocation when building lookup isn't available
				var apLat = parseFloat(result['nac']['meraki_ap']['lat']);
				var apLon = parseFloat(result['nac']['meraki_ap']['lon']);
				var apLabel = result['nac']['meraki_ap']['name'] || 'Access Point';
				loadCampusMap(apLabel, apLabel, apLat, apLon);
				$('#map_label').text(apLabel).show();
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
					warn = ` <i class="fa-solid fa-triangle-exclamation text-warning ms-1" role="img" aria-label="Warning: does not match detected IPv4 address (${nacIp})"></i>`;
				}
				if (key === 'macAddress' && nacMac && value.toLowerCase() !== nacMac) {
					warn = ` <i class="fa-solid fa-triangle-exclamation text-warning ms-1" role="img" aria-label="Warning: does not match MAC from IPAM (${result['address_details']['mac']})"></i>`;
				}
				return value + warn;
			}

			var nacTbody = $('#nac-table tbody');
			function escHtml(s) { return $('<span>').text(String(s)).html(); }
			function nacRow(label, html) { nacTbody.append(`<tr><th>${label}</th><td>${html}</td></tr>`); }

			if (result['nac']['endSystem']) {
				$('#nac-diagram-row').show();
				$('#nac-card').show();

				// Build connection diagram
				var diagHtml = buildNacDiagram(result['nac'], result['user_device']);
				if (diagHtml) {
					$('#nac-diagram').html(diagHtml);
					$('#nac-diagram-card').show();
				}

				var es = result['nac']['endSystem'];
				var ei = result['nac']['endSystemInfo'] || {};

				// Connection time — XMC returns ISO string or ms timestamp
				if (es['lastSeenTime']) {
					var raw = es['lastSeenTime'];
					var num = Number(raw);
					var dt = new Date(isNaN(num) ? raw : (num > 1e12 ? num : num * 1000));
					nacRow('Connected', escHtml(dt.toLocaleString()));
				}

				// Client identity
				if (es['ipAddress'])  nacRow('IP Address',  nacCell('ipAddress',  es['ipAddress']));
				if (es['macAddress']) nacRow('MAC Address', nacCell('macAddress', es['macAddress']));

				// NAC appliance info
				if (es['nacApplianceGroupName']) nacRow('Appliance Group', escHtml(es['nacApplianceGroupName']));
				if (es['nacProfileName'])        nacRow('Profile',         escHtml(es['nacProfileName']));
				if (es['nacApplianceIP'])        nacRow('Appliance',       escHtml(es['nacApplianceIP']));

				// Policy and reason
				if (es['policy']) nacRow('Policy', escHtml(es['policy']));
				if (es['reason']) nacRow('Reason', escHtml(es['reason']));

				// Groups from endSystemInfo (shown here, not in the generic dump below)
				if (ei['groups']) nacRow('Groups', escHtml(ei['groups']));

				// Switch / AP connection
				var isWireless = es['connection_type'] === 'wireless';
				if (es['switchIP']) nacRow(isWireless ? 'Wireless Controller' : 'Switch IP', escHtml(es['switchIP']));
				if (isWireless) {
					if (es['wireless_ap_mac']) nacRow('AP MAC', escHtml(es['wireless_ap_mac']));
				} else {
					if (es['switchPortId']) nacRow('Port', escHtml(es['switchPortId']));
				}
			}
			if (result['nac']['endSystemInfo']) {
				$('#nac-card').show();
				for (const [key, value] of Object.entries(result['nac']['endSystemInfo'])) {
					if (value && key !== 'groups' && key !== 'groupDescription' && key !== 'groupDescr2') {
						nacRow(key, escHtml(String(value)));
					}
				}
			}

			// Wireless connection card — common fields from endSystem (Aruba + Meraki)
			var showMerakiCard = false;
			function merakiRow(rowId, val) {
				if (val) {
					$('#' + rowId).text(val);
					$('#' + rowId + '-row').show();
					showMerakiCard = true;
				}
			}
			var es = result['nac']['endSystem'];
			if (es && es['connection_type'] === 'wireless') {
				merakiRow('wireless-ssid', es['wireless_ssid']);
				merakiRow('wireless-ap-name', es['wireless_ap_name']);
				merakiRow('wireless-ap-mac', es['wireless_ap_mac']);
				merakiRow('wireless-controller', es['wireless_controller']);
			}
			if (result['nac']['meraki_client']) {
				var mc = result['nac']['meraki_client'];
				merakiRow('meraki-manufacturer', mc.manufacturer);
				merakiRow('meraki-description', mc.description);
				merakiRow('meraki-os', mc.os);
				merakiRow('meraki-user', mc.user);
				merakiRow('meraki-status', mc.status);
				merakiRow('meraki-vlan', mc.vlan);
				if (mc.last_seen) {
					var lsDate = new Date(mc.last_seen * 1000);
					$('#meraki-last-seen').text(lsDate.toLocaleString());
					$('#meraki-last-seen-row').show();
					showMerakiCard = true;
				}
				if (mc.mac) {
					var ipamMac = nacMac;
					var merakiMacHtml = escHtml(mc.mac);
					if (ipamMac && mc.mac.toLowerCase() !== ipamMac) {
						merakiMacHtml += ` <i class="fa-solid fa-triangle-exclamation text-warning ms-1" role="img" aria-label="Warning: does not match MAC from IPAM (${escHtml(result['address_details']['mac'])})"></i>`;
					}
					$('#meraki-mac').html(merakiMacHtml);
					$('#meraki-mac-row').show();
					showMerakiCard = true;
				}
				merakiRow('meraki-capabilities', mc.wireless_capabilities);
			}
			if (result['nac']['meraki_ap']) {
				merakiRow('meraki-ap-model', result['nac']['meraki_ap'].model);
			}
			if (result['nac']['meraki_signal']) {
				var ms = result['nac']['meraki_signal'];
				if (ms.rssi !== null && ms.rssi !== undefined) {
					var rssiIcon = ms.rssi >= -65 ? 'fa-circle-check text-success' : ms.rssi >= -70 ? 'fa-triangle-exclamation text-warning' : 'fa-circle-xmark text-danger';
					var rssiCls  = ms.rssi >= -65 ? '' : ms.rssi >= -70 ? 'text-warning' : 'text-danger';
					var rssiLabel = ms.rssi >= -65 ? 'Good' : ms.rssi >= -70 ? 'Fair' : 'Poor';
					$('#meraki-rssi').html(`${ms.rssi} dBm &mdash; <i class="fa-solid ${rssiIcon} me-1" aria-hidden="true"></i><span class="${rssiCls}">${rssiLabel}</span>`);
					$('#meraki-rssi-row').show();
					showMerakiCard = true;
				}
				if (ms.snr !== null && ms.snr !== undefined) {
					var snrIcon = ms.snr >= 25 ? 'fa-circle-check text-success' : ms.snr >= 15 ? 'fa-triangle-exclamation text-warning' : 'fa-circle-xmark text-danger';
					var snrCls  = ms.snr >= 25 ? '' : ms.snr >= 15 ? 'text-warning' : 'text-danger';
					var snrLabel = ms.snr >= 25 ? 'Good' : ms.snr >= 15 ? 'Fair' : 'Poor';
					$('#meraki-snr').html(`${ms.snr} dB &mdash; <i class="fa-solid ${snrIcon} me-1" aria-hidden="true"></i><span class="${snrCls}">${snrLabel}</span>`);
					$('#meraki-snr-row').show();
					showMerakiCard = true;
				}
			}
			if (showMerakiCard) {
				$('#meraki-card').show();
				$('#nac-diagram-row').show();
			}

			// dump building data
			if (result['nac']['nit_building'] && Object.keys(result['nac']['nit_building']).length > 0) {
				var bldg = result['nac']['nit_building'];
				$('#bldg-card').show();
				if (bldg['official_name'] || bldg['full_name']) {
					$('#bldg-name-row').show();
					$('#bldg-name').text(bldg['official_name'] || bldg['full_name']);
				}
				if (bldg['address']) {
					$('#bldg-address-row').show();
					$('#bldg-address').text(bldg['address']);
				}
			}

			// User device card — populate once; both callbacks return identical data
			populateDeviceCard(result['user_device']);
			checkClockSync(result['server_time']);

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
			if (result['network']['contact_name']) {
				$('#net-config-v4-contact-row').show();
				$('#net-config-v4-contact').text(result['network']['contact_name']);
				hasV4Config = true;
			}
			if (hasV4Config) {
				$('#net-config-v4-address').text(result['client_address']);
				$('#net-config-v4-address-row').show();
				$('#net-config-v4').show();
				$('#net-config-card').show();
			}

			if (result['is_campus'] && !result['network']['cidr']) {
				$('#net1-ipam-unavailable-row').show();
			}

			if (result['network']['purpose']) reportNetworkPurpose = result['network']['purpose'];
			reportDataPrimary = result;
			checkAddressMismatch();
			if (!simulate) checkNATType(result['client_address']);
			if (default_version == 4) reportConnectV4 = 'Supported';
			else reportConnectV6 = 'Supported';
			$('#report-btn').prop('disabled', false);
		},
		error: function (xhr, status, error) {
			$('#connect-ipv4').html('<i class="fa-solid fa-triangle-exclamation text-warning" aria-hidden="true"></i> Not supported');
			if (default_version == 4) {
				reportConnectV4 = 'Not detected';
				showPrimaryLoadError();
			} else {
				reportConnectV6 = 'Not detected';
			}
		}
	});

}

function checkNATType(serverIp) {
	if (!serverIp) return;
	fetchExternalIPv4().then(function (externalIp) {
		renderNATResult(serverIp, externalIp, reportNetworkPurpose);
	});
}

function fetchExternalIPv4() {
	var controller = new AbortController();
	var timer = setTimeout(function () { controller.abort(); }, 5000);
	return fetch('https://api4.ipify.org?format=json', {
		cache: 'no-store',
		signal: controller.signal
	})
		.then(function (r) { clearTimeout(timer); return r.json(); })
		.then(function (d) { return d.ip || null; })
		.catch(function () { clearTimeout(timer); return null; });
}

function renderNATResult(serverIp, externalIp, networkPurpose) {
	var isV6 = serverIp.includes(':');
	var pathsDiffer = !isV6 && externalIp && externalIp !== serverIp;
	if (!pathsDiffer) return;

	reportInternetIp = externalIp;

	if (networkPurpose === 'VPN') {
		$('#intro_text .intro-status').append(
			`<div class="mt-1 small text-muted"><i class="fa-solid fa-circle-info text-info me-1" aria-hidden="true"></i>Internet traffic bypasses the VPN tunnel and exits via ${externalIp}.</div>`
		);
	} else if (networkPurpose) {
		$('#intro_text .intro-status').append(
			`<div class="mt-1 small text-muted"><i class="fa-solid fa-circle-info text-info me-1" aria-hidden="true"></i>Your internet traffic exits the campus network as ${externalIp}.</div>`
		);
	} else {
		$('#intro_text .intro-status').append(
			`<div class="mt-1 small text-muted"><i class="fa-solid fa-circle-info text-info me-1" aria-hidden="true"></i>Your internet traffic appears to use a different address (${externalIp}) than your campus connection.</div>`
		);
	}
}

function checkClockSync(serverTime) {
	if (!serverTime) return;
	var offsetSec = Math.round(Math.abs(Date.now() - serverTime) / 1000);
	var label, icon, cls;

	function fmt(s) {
		if (s < 60) return s + ' second' + (s !== 1 ? 's' : '');
		var m = Math.floor(s / 60), r = s % 60;
		if (m < 60) return m + 'm ' + (r > 0 ? r + 's' : '');
		return Math.floor(m / 60) + 'h ' + (m % 60) + 'm';
	}

	if (offsetSec < 30) {
		icon = 'fa-circle-check text-success';
		cls  = '';
		label = 'Synchronized';
	} else if (offsetSec < 300) {
		icon = 'fa-triangle-exclamation text-warning';
		cls  = 'text-warning';
		label = fmt(offsetSec) + ' offset detected — check system clock';
	} else {
		icon = 'fa-circle-xmark text-danger';
		cls  = 'text-danger';
		label = fmt(offsetSec) + ' offset — may cause authentication and VPN failures';
	}

	reportClockStatus = label;
	$('#device-clock').html(`<i class="fa-solid ${icon} me-1" aria-hidden="true"></i><span class="${cls}">${label}</span>`);
	$('#device-clock-row').show();
	$('#device-card').show();
	$('#additional-info').show();
	$('#nac-diagram-row').show();
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
		$('#additional-info').show();
		$('#nac-diagram-row').show();
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
	const simulate = !!$('#connect-test').data('simulate');

	if (simulate) {
		// Inject static campus-realistic DNS data so simulate is fully self-contained.
		append_dns_table_row('Internet DNS Provider', 'Akamai Technologies\nUnited States\n192.0.2.53');
		append_dns_table_row('EDNS Client Subnet', 'University of North Carolina at Chapel Hill\nUnited States\n192.0.2.0');
		if (dns_test_url) {
			append_dns_table_row(
				'Campus DNS Security',
				'<i class="fa-solid fa-circle-check text-success" aria-hidden="true"></i> Active',
				'security-filtering-row',
				true
			);
		}
		$('#dns-test').show();
		return;
	}

	// Add Security Filtering row only if a test URL is configured
	if (dns_test_url) {
		append_dns_table_row(
			'Campus DNS Security',
			'<i class="fa-solid fa-question" aria-hidden="true"></i> Testing',
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
					let geoParts = geo ? geo.split(' - ') : [];
					let geoFormatted = geoParts.length === 2 ? `${geoParts[1]}\n${geoParts[0]}` : (geo || '');
					let providerDetails = geoFormatted || '';
					if (geoFormatted && ip) {
						providerDetails = `${geoFormatted}\n${ip}`;
					} else if (ip) {
						providerDetails = ip;
					}

					append_dns_table_row('Internet DNS Provider', providerDetails);
					reportDnsProviderGeo = geo || null;
					reportDnsProviderIp = ip || null;
				}
			}

			if (result['edns']) {
				let geo = result['edns']['geo']
				let ip = result['edns']['ip']

				if (geo || ip) {
					let geoParts = geo ? geo.split(' - ') : [];
					let geoFormatted = geoParts.length === 2 ? `${geoParts[1]}\n${geoParts[0]}` : (geo || '');
					let clientSubnetDetails = geoFormatted || '';
					if (geoFormatted && ip) {
						clientSubnetDetails = `${geoFormatted}\n${ip}`;
					} else if (ip) {
						clientSubnetDetails = ip;
					}

					append_dns_table_row('EDNS Client Subnet', clientSubnetDetails);
					reportDnsEdnsGeo = geo || null;
					reportDnsEdnsIp = ip || null;
				}
			}

			// Post provider data as soon as it arrives — independent of the filtering test.
			if (!simulate && (reportDnsProviderGeo || reportDnsProviderIp)) {
				fetch('/dns-result', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						dns_ip: reportDnsProviderIp,
						dns_geo: reportDnsProviderGeo,
						edns_ip: reportDnsEdnsIp,
						edns_geo: reportDnsEdnsGeo,
					}),
					keepalive: true
				}).catch(() => {});
			}
		},
		error: function (xhr, status, error) {
			console.warn(`DNS provider test failed (${xhr.status}): ${error}`);
			append_dns_table_row('Internet DNS Provider', 'Unavailable');
		}
	});

	// Test DNS security filtering by attempting to fetch the configured test URL
	if (dns_test_url) {
		test_dns_security_filtering(dns_test_url)
			.then(isFiltered => {
				let filteringHtml, filteringKey;
				if (isFiltered === true) {
					filteringHtml = `<i class="fa-solid fa-circle-check text-success" aria-hidden="true"></i> Active`;
					filteringKey = 'active';
					reportDnsFiltering = 'Active';
				} else if (isFiltered === false) {
					filteringHtml = `<i class="fa-solid fa-triangle-exclamation text-warning" aria-hidden="true"></i> Inactive`;
					filteringKey = 'inactive';
					reportDnsFiltering = 'Inactive';
				} else {
					filteringHtml = `<i class="fa-solid fa-circle-question text-warning" aria-hidden="true"></i> Unable to verify`;
					filteringKey = 'inconclusive';
					reportDnsFiltering = 'Unable to verify';
				}
				$('#security-filtering-row .dns-row-value').html(filteringHtml);
				if (!simulate) {
					fetch('/dns-result', {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({ filtering: filteringKey }),
						keepalive: true
					}).catch(() => {});
				}
			})
			.catch(error => {
				console.error('DNS security filtering test error:', error);
				$('#security-filtering-row .dns-row-value').html(`<i class="fa-solid fa-circle-question text-warning" aria-hidden="true"></i> Unable to verify`);
			});
	}
}

function test_secondary_url(default_version) {
	// test secondary url
	var simulate = !!$('#connect-test').data('simulate');

	var test_url = $('#connect-test').data('ipv6_url');
	if (!test_url) {
		if (!simulate) {
			$('#connect-ipv6').html('<i class="fa-solid fa-minus text-secondary" aria-hidden="true"></i> Not configured');
			return;
		}
		// In simulate mode, fall back to the IPv4 server so ?simulate=6 still works
		test_url = $('#connect-test').data('ipv4_url') || window.location.origin;
	}

	// handle starting state
	if ( default_version == 6 ) {
		$('#connect-default').text("IPv6");
		$('#connect-ipv6').html('<i class="fa-solid fa-question" aria-hidden="true"></i> Testing');
	}

	// Make AJAX call to the API to get the ipv6 address
	$.ajax({
		type: "GET",
		url: test_url + "/hostinfo" + (simulate ? '?simulate=6' : ''),
		dataType: "json",
		success: function (result, status, xhr) {
			// $('#connect-ipv6').text("Supported");
			$('#connect-ipv6').html('<i class="fa-solid fa-circle-check text-success" aria-hidden="true"></i> Supported');
			//console.log("Host check from " + result["address"]);

			if ( default_version == 6 ) {
				$('#first_address_section').show();
				$('#address1').html(formatIPAddress(result["client_address"]));
				$('#address_box .ip-bar-label').text('IPv6');
				set_intro_text(result['is_campus'], result['network']['purpose']);
			} else {
				$('#second_address_section').show();
				$('#address2').html(formatIPAddress(result["client_address"]));
				$('#additional_ip .ip-bar-label').text('IPv6');
				$('#second_address_section .ip-copy-card').removeClass('ip-loading');
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

			if ( result['iplocation']["isp"] ) {
				$('#net2-isp-row').show();
				$('#net2-isp').text(result['iplocation']["isp"]);
			}
			if ( result['iplocation']["org"] ) {
				$('#net2-org-row').show();
				$('#net2-org').text(result['iplocation']["org"]);
			}
			var net2city = result['iplocation']["city"], net2region = result['iplocation']["region"];
			var net2country = result['iplocation']["country_name"] || result['iplocation']["country"];
			if (net2city || net2region || net2country) {
				$('#net2-location-row').show();
				$('#net2-location').text([net2city, net2region, net2country].filter(Boolean).join(', '));
			}
			if ( result['iplocation']["asn"] ) {
				$('#net2-asn-row').show();
				$('#net2-asn').text(result['iplocation']["asn"]);
			}
			var net2_flags = [];
			if (result['iplocation']['mobile']) net2_flags.push('<i class="fa-solid fa-mobile-screen text-info" aria-hidden="true" title="Mobile connection"></i> Mobile');
			if (result['iplocation']['proxy'])  net2_flags.push('<i class="fa-solid fa-shield text-warning" aria-hidden="true" title="Proxy or VPN detected"></i> Proxy / VPN');
			if (result['iplocation']['hosting']) net2_flags.push('<i class="fa-solid fa-server text-secondary" aria-hidden="true" title="Hosting provider or datacenter"></i> Hosting');
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
			if (result['network']['contact_name']) {
				$('#net-config-v6-contact-row').show();
				$('#net-config-v6-contact').text(result['network']['contact_name']);
				hasV6Config = true;
			}
			if (hasV6Config) {
				$('#net-config-v6-address').text(result['client_address']);
				$('#net-config-v6-address-row').show();
				$('#net-config-v6').show();
				$('#net-config-card').show();
			}

			if (result['is_campus'] && !result['network']['cidr']) {
				$('#net2-ipam-unavailable-row').show();
			}

			if (result['network']['purpose']) reportNetworkPurpose = result['network']['purpose'];
			reportDataSecondary = result;
			checkAddressMismatch();
			if (default_version == 4) reportConnectV6 = 'Supported';
			else reportConnectV4 = 'Supported';
		},
		error: function (xhr, status, error) {
			$('#connect-ipv6').html('<i class="fa-solid fa-triangle-exclamation text-warning" aria-hidden="true"></i> Not supported');
			if (default_version == 6) {
				reportConnectV6 = 'Not detected';
				showPrimaryLoadError();
			} else {
				reportConnectV4 = 'Not detected';
			}
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
