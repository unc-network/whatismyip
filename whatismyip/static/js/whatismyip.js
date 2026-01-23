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

$(document).ready(function () {

	// $(function() {
	// 	$('.allowCopy').click(function() {
	// 		var text = $('#address').text();
	// 		// const text = $(this).text();
	// 		//console.log("clicked address "+text);

	// 		try {
	// 			navigator.clipboard.writeText(text)
	// 			//event.target.textContent = 'Copied to clipboard'
	// 		} catch (err) {
	// 			console.error('Failed to copy!', err)
	// 		}

	// 	});
	// });

	//$('[data-toggle="tooltip"]').tooltip();

	/* extract the default ip detected */
	var address = $('#address').text();
	console.log("Connection from " + address);

	if (address.indexOf(':') != -1) {
		// default is IPv6 connection
		$('#connect-default').text("IPv6");
		$('#connect-ipv6').text("Supported");
		$('#connect-ipv4').text("Testing...");

		// var test_url = $('#second_address_section').data('test_url')
		var test_url = $('#connect-test').data('ipv4_url')
		$('#second_address_section').show()

		// Make AJAX call to the API to get the ipv4 address
		$.ajax({
			type: "GET",
			url: test_url + "/hostinfo",
			dataType: "json",
			success: function (result, status, xhr) {
				$('#connect-ipv4').text("Supported");
				console.log("Host check from " + result["address"]);
				$('#address2').text(result["address"]);

				// Populate 2nd address's details
				$('#address2-details').show();
				$('#address2-address').text(result["address"]);

				if ( result['address_details']["names"] ) {
					$('#addr2-names-row').show();
					$('#addr2-names').text(result['address_details']["names"]);
				} else if ( result['address_details']["ptr"] ) {
					$('#addr2-ptr-row').show();
					$('#addr2-ptr').text(result['address_details']["ptr"]);
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
					$('#net2-network').text(result['network']["cidr"]);
				}

				if ( result['network']["vlan_id"] ) {
					$('#net2-vlan-row').show();
					$('#net2-vlan').text(result['network']["vlan_id"] + ' (' + result['network']['vlan_name'] + ')');
				}

				if ( result['iplocation']["country_name"] ) {
					$('#net2-country-row').show();
					$('#net2-country').text(result['iplocation']["country_name"]);
				}
				if ( result['iplocation']["isp"] ) {
					$('#net2-isp-row').show();
					$('#net2-isp').text(result['iplocation']["isp"]);
				}
			},
			error: function (xhr, status, error) {
				$('#connect-ipv4').text("Not supported");
				console.log(error);
			}
		});
	} else {
		// default is IPv4 connection
		$('#connect-default').text("IPv4");
		$('#connect-ipv4').text("Supported");
		$('#connect-ipv6').text("Testing...");

		// Make AJAX call to the API to get the ipv6 address
		var test_url = $('#connect-test').data('ipv6_url')
		$.ajax({
			type: "GET",
			url: test_url + "/hostinfo",
			dataType: "json",
			success: function (result, status, xhr) {
				$('#second_address_section').show()
				$('#connect-ipv6').text("Supported");
				console.log("Host check from " + result["address"]);
				$('#address2').text(result["address"]);

				// Populate 2nd address's details
				$('#address2-details').show();
				$('#address2-address').text(result["address"]);
				$('#address2-ptr').text(result["ptr"]);
			},
			error: function (xhr, status, error) {
				$('#connect-ipv6').text("Not supported");
				console.log(error);
			}
		});
	}

});
