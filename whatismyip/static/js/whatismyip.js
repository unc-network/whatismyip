/*!
  * whatismyip.js
  * Helper library for https://whatismyip.unc.edu
  */

function copyAddress(id_of_address) {
	//const text = $("#address").text()
	const text = $(id_of_address).text()
	try {
		navigator.clipboard.writeText(text)
		console.log("Copied the address: " + text);
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

	/* extract the default ip detected */
	var address = $('#address').text();

	if (address.indexOf(':') != -1) {
		$('#second_address_section').show()
		// Make AJAX call to the API to get the ipv4 address
		$.ajax({
			type: "GET",
			url: "https://whatismyipv4.unc.edu/hostinfo",
			//url: "http://whatismyipv4.unc.edu:5000/hostinfo",
			//url: "http://127.0.0.1:5000/hostinfo",
			dataType: "json",
			success: function (result, status, xhr) {
				//console.log(result);
				$('#address2').text(result["address"]);
			},
			error: function (xhr, status, error) {
				console.log(error);
			}
		});
	}

});
