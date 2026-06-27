// Leaflet/OpenStreetMap implementation — loaded when config.toml [map] provider = "leaflet"
// Exposes: loadCampusMap, loadLatLonMap (called by whatismyip.js)

var map = null;
var mapInitialized = false;

function initLeafletMap(lat, lon, zoom) {
	if (mapInitialized) return;
	map = L.map('map').setView([lat, lon], zoom);
	L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
		maxZoom: 19,
		attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
	}).addTo(map);
	mapInitialized = true;
}

function placeLeafletMarker(lat, lon, title) {
	L.marker([lat, lon]).addTo(map).bindPopup(title).openPopup();
}

function loadCampusMap(address, title, lat, lon) {
	if (!lat || !lon || isNaN(lat) || isNaN(lon)) return;
	$('#map_card').show();
	$('#map_label').hide();
	initLeafletMap(lat, lon, 17);
	placeLeafletMarker(lat, lon, title || address);
}

function loadLatLonMap(lat, lon, label) {
	$('#map_card').show();
	$('#map_label').show();
	initLeafletMap(lat, lon, 11);
	placeLeafletMarker(lat, lon, label);
}
