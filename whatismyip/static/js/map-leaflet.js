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

	// Stamp alt="" on every img Leaflet injects (tiles, marker icons, shadows).
	// Empty alt is correct for decorative/functional map imagery.
	const mapEl = document.getElementById('map');
	new MutationObserver(function () {
		mapEl.querySelectorAll('img:not([alt])').forEach(function (img) { img.alt = ''; });
	}).observe(mapEl, { childList: true, subtree: true });

	mapInitialized = true;
}

function placeLeafletMarker(lat, lon, title) {
	var label = title || 'Location marker';
	var marker = L.marker([lat, lon]).addTo(map).bindPopup(label).openPopup();
	marker.on('add', function () {
		var el = marker.getElement();
		if (el) {
			el.querySelectorAll('img').forEach(function (img) { img.alt = label; });
		}
	});
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
