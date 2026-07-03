// Leaflet/OpenStreetMap implementation — loaded when config.toml [map] provider = "leaflet"
// Exposes: loadCampusMap, loadLatLonMap (called by whatismyip.js)

var map = null;
var mapInitialized = false;

function initLeafletMap(lat, lon, zoom) {
	if (mapInitialized) return;
	const mapEl = document.getElementById('map');
	mapEl.classList.remove('map-loading');
	map = L.map('map').setView([lat, lon], zoom);
	L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
		maxZoom: 19,
		alt: 'OpenStreetMap tile',
		attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
	}).addTo(map);

	mapInitialized = true;
}

function placeLeafletMarker(lat, lon, title) {
	var label = title || 'Location marker';
	var marker = L.marker([lat, lon]).addTo(map).bindPopup(label);
	marker.on('add', function () {
		var el = marker.getElement();
		if (el) {
			el.querySelectorAll('img').forEach(function (img) { img.alt = label; });
		}
	});
}

function loadCampusMap(address, title, lat, lon) {
	if (!lat || !lon || isNaN(lat) || isNaN(lon)) return;
	initLeafletMap(lat, lon, 17);
	placeLeafletMarker(lat, lon, title || address);
}

function loadLatLonMap(lat, lon, label) {
	$('#map_label').show();
	initLeafletMap(lat, lon, 11);
	placeLeafletMarker(lat, lon, label);
}
