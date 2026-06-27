// Google Maps implementation — loaded when config.toml [map] provider = "google"
// Exposes: loadCampusMap, loadLatLonMap (called by whatismyip.js)

let map;
let geocoder;
let mapInitialized = false;

async function initMap(lat, lon, zoom) {
	const { Map } = await google.maps.importLibrary("maps");
	const { Geocoder } = await google.maps.importLibrary("geocoding");
	map = new Map(document.getElementById("map"), {
		center: { lat: lat, lng: lon },
		zoom: zoom,
		mapId: 'LOCATION_MAP_ID',
		disableDefaultUI: true,
	});
	geocoder = new Geocoder();
}

async function addAdvancedMarker(position, title) {
	const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
	new AdvancedMarkerElement({ map, position, title });
}

function codeAddress(address, title) {
	geocoder.geocode({ address: address }, (results, status) => {
		if (status === "OK") {
			map.setCenter(results[0].geometry.location);
			addAdvancedMarker(results[0].geometry.location, title);
		} else {
			console.log("Geocode failed: " + status);
		}
	});
}

async function placeLatLonMarker(lat, lon, title) {
	var position = { lat: lat, lng: lon };
	map.setCenter(position);
	addAdvancedMarker(position, title);
}

function loadCampusMap(address, title, lat, lon) {
	$('#map_card').show();
	$('#map_label').hide();

	var useCampusLatLon = lat && lon && !isNaN(lat) && !isNaN(lon);
	var startLat = useCampusLatLon ? lat : 35.9049;
	var startLon = useCampusLatLon ? lon : -79.0469;

	if (mapInitialized) {
		useCampusLatLon ? placeLatLonMarker(lat, lon, title) : codeAddress(address, title);
		return;
	}
	mapInitialized = true;
	initMap(startLat, startLon, 17)
		.then(() => useCampusLatLon ? placeLatLonMarker(lat, lon, title) : codeAddress(address, title))
		.catch((error) => {
			console.error('Failed to load campus map', error);
			$('#map_card').hide();
			mapInitialized = false;
		});
}

function loadLatLonMap(lat, lon, label) {
	$('#map_card').show();
	$('#map_label').show();

	if (mapInitialized) {
		placeLatLonMarker(lat, lon, label);
		return;
	}
	mapInitialized = true;
	initMap(lat, lon, 11)
		.then(() => placeLatLonMarker(lat, lon, label))
		.catch((error) => {
			console.error('Failed to load map', error);
			$('#map_card').hide();
			mapInitialized = false;
		});
}
