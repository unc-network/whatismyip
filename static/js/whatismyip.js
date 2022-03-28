/*!
  * whatismyip.js
  * Helper library for https://whatismyip.unc.edu
  */
$(document).ready(function () {

	$('#more-info [data-bs-toggle="collapse"]').click(function() {
	  $(this).toggleClass( "active" );
	  if ($(this).hasClass("active")) {
	    $(this).text("Hide Information");
	  } else {
	    $(this).text("Show More Information");
	  }
	});


	$(function() {
		$('.allowCopy').click(function() {
			const text = $(this).text();
			//console.log("clicked address "+text);

			try {
				navigator.clipboard.writeText(text)
				//event.target.textContent = 'Copied to clipboard'
			} catch (err) {
				console.error('Failed to copy!', err)
			}

		});
	});

	function gethostinfo() {
		var address = $('#address').text();
		$('#additional_ip').show()
		// Make AJAX call to the API to get the ipv4 address
		$.ajax({
			type: "GET",
			url: "/hostinfo.php",
			dataType: "json",
			success: function (result, status, xhr) {
				//console.log(result);
				$('#address2').text(result["address"]);
				$('#address2_sm').text(result["address"]);
			},
			error: function (xhr, status, error) {
				console.log(error);
			}
		});
	}

	var address = $('#address').text();
	//console.log(address);

	//gethostinfo();

	if (address.indexOf(':') != -1) {
		$('#additional_ip').show()
		// Make AJAX call to the API to get the ipv4 address
		$.ajax({
			type: "GET",
			//url: "https://whatismyipv4.unc.edu/hostinfo.php",
			url: "http://whatismyipv4.unc.edu:5000/hostinfo",
			dataType: "json",
			success: function (result, status, xhr) {
				//console.log(result);
				$('#address2').text(result["address"]);
				$('#address2_sm').text(result["address"]);
			},
			error: function (xhr, status, error) {
				console.log(error);
			}
		});
	}

});
