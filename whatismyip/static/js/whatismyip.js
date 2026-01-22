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
				$('#v6_help_text').show();

				// Populate 2nd address's details
				$('#address2-details').show();
				$('#address2-address').text(result["address"]);
				$('#address2-ptr').text(result["ptr"]);
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
