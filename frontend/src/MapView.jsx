import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Tooltip, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix default marker icon issue with Leaflet + React
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
});

// ── Icons ────────────────────────────────────────────────────────────────────
function makeIcon(color) {
  return new L.Icon({
    iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${color}.png`,
    shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
  });
}

const ICONS = {
  red:  makeIcon('red'),
  gold: makeIcon('gold'),
  blue: makeIcon('blue'),
};

// ── Category metadata (emoji + label only, all markers red) ──────────────────
const CATEGORY_META = {
  pantai:             { label: 'Pantai',       emoji: '🏖️' },
  air_terjun:         { label: 'Air Terjun',   emoji: '💧' },
  danau:              { label: 'Danau',         emoji: '🏞️' },
  bukit:              { label: 'Bukit',         emoji: '⛰️' },
  gunung:             { label: 'Gunung',        emoji: '🏔️' },
  desa_wisata:        { label: 'Desa Wisata',   emoji: '🏘️' },
  budaya:             { label: 'Budaya',        emoji: '🏛️' },
  rekreasi:           { label: 'Rekreasi',      emoji: '🎡' },
  geowisata:          { label: 'Geowisata',     emoji: '🪨' },
  tour:               { label: 'Tur',           emoji: '🧭' },
  kuliner:            { label: 'Kuliner',       emoji: '🍽️' },
  restaurant:         { label: 'Restoran',      emoji: '🍽️' },
  hotel:              { label: 'Hotel',         emoji: '🏨' },
  penginapan:         { label: 'Penginapan',    emoji: '🛏️' },
  accommodation_data: { label: 'Penginapan',    emoji: '🏨' },
};
const DEFAULT_META = { label: 'Wisata', emoji: '📍' };

function getCategoryMeta(category) {
  return CATEGORY_META[category] || DEFAULT_META;
}

function getMarkerIcon(isHighlighted) {
  return isHighlighted ? ICONS.gold : ICONS.red;
}

function renderStars(rating) {
  if (!rating && rating !== 0) return null;
  const rounded = Math.round(rating * 2) / 2;
  return '★'.repeat(Math.floor(rounded)) + (rounded % 1 ? '½' : '') + '☆'.repeat(5 - Math.ceil(rounded));
}

// ── Haversine distance ────────────────────────────────────────────────────────
function haversineDistance(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const toRad = (deg) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ── FlyToLocation: only flies when position genuinely changes ─────────────────
function FlyToLocation({ position }) {
  const map = useMap();
  const lastPos = useRef(null);

  useEffect(() => {
    if (!position) return;
    const isSame =
      lastPos.current &&
      lastPos.current.lat === position.lat &&
      lastPos.current.lng === position.lng;
    if (!isSame) {
      map.flyTo([position.lat, position.lng], 14, { duration: 1.5 });
      lastPos.current = position;
    }
  }, [position, map]);

  return null;
}

// ── FitBounds: only re-fits when highlightLocation changes, not on re-renders ─
function FitBounds({ locations, highlightLocation }) {
  const map = useMap();
  const prevHighlight = useRef(undefined);
  const initialFit = useRef(false);

  useEffect(() => {
    if (!locations || locations.length === 0) return;
    const highlightChanged = highlightLocation !== prevHighlight.current;
    if (!initialFit.current || highlightChanged) {
      const bounds = L.latLngBounds(locations.map((loc) => [loc.lat, loc.lng]));
      map.fitBounds(bounds, {
        padding: [50, 50],
        maxZoom: highlightLocation ? 14 : 12,
      });
      initialFit.current = true;
      prevHighlight.current = highlightLocation;
    }
  }, [locations, highlightLocation, map]);

  return null;
}

// ── Main MapView Component ────────────────────────────────────────────────────
function MapView({
  locations = [],
  height = '420px',
  showAll = true,
  highlightLocation = null,
  onMarkerClick = null,
}) {
  const [mapCenter] = useState([2.65, 98.85]);
  const [mapZoom] = useState(10);
  const [userLocation, setUserLocation] = useState(null);
  const [isLocating, setIsLocating] = useState(false);
  const [locationError, setLocationError] = useState(null);

  const handleLocateMe = () => {
    if (!navigator.geolocation) {
      setLocationError('Browser tidak mendukung geolocation.');
      return;
    }
    setIsLocating(true);
    setLocationError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setIsLocating(false);
      },
      () => {
        setLocationError('Tidak dapat mengakses lokasi. Aktifkan izin lokasi.');
        setIsLocating(false);
      },
      { timeout: 10000 }
    );
  };

  const displayLocations = highlightLocation
    ? locations.filter((loc) =>
        loc.name.toLowerCase().includes(highlightLocation.toLowerCase())
      )
    : showAll
    ? locations
    : [];

  const baseLocations = displayLocations.length > 0 ? displayLocations : locations;

  const finalLocations = userLocation
    ? [...baseLocations].sort((a, b) => {
        const dA = haversineDistance(userLocation.lat, userLocation.lng, a.lat, a.lng);
        const dB = haversineDistance(userLocation.lat, userLocation.lng, b.lat, b.lng);
        return dA - dB;
      })
    : baseLocations;

  if (!locations || locations.length === 0) {
    return (
      <div
        style={{
          padding: '2rem',
          textAlign: 'center',
          background: 'rgba(30, 41, 59, 0.6)',
          borderRadius: '8px',
          border: '1px solid rgba(220, 38, 38, 0.3)',
        }}
      >
        <p style={{ color: 'rgba(255,255,255,0.7)', margin: 0 }}>
          📍 Data lokasi tidak tersedia.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        borderRadius: '14px',
        overflow: 'hidden',
        border: '2px solid #fbbf24',
        boxShadow: '0 8px 32px rgba(0,0,0,0.45)',
      }}
    >
      {/* Map title bar */}
      <div
        style={{
          background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
          padding: '0.55rem 1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          borderBottom: '1px solid rgba(251,191,36,0.3)',
        }}
      >
        <span style={{ fontSize: '1rem' }}>🗺️</span>
        <span
          style={{
            color: '#fbbf24',
            fontWeight: '700',
            fontSize: '0.9rem',
            letterSpacing: '0.04em',
          }}
        >
          Peta Wisata Danau Toba
        </span>
        <span
          style={{
            marginLeft: 'auto',
            background: 'rgba(251,191,36,0.15)',
            color: '#fbbf24',
            border: '1px solid rgba(251,191,36,0.4)',
            borderRadius: '20px',
            padding: '2px 10px',
            fontSize: '0.72rem',
            fontWeight: '600',
          }}
        >
          {finalLocations.length} lokasi
        </span>
      </div>

      {/* Map */}
      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        style={{ height, width: '100%' }}
        scrollWheelZoom={true}
        zoomControl={true}
      >
        {/* CartoDB Voyager – closest free tile to Google Maps style */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          maxZoom={19}
        />

        {finalLocations.map((loc, idx) => {
          const isHighlighted =
            highlightLocation &&
            loc.name.toLowerCase().includes(highlightLocation.toLowerCase());
          const meta = getCategoryMeta(loc.category);
          const distance = userLocation
            ? haversineDistance(userLocation.lat, userLocation.lng, loc.lat, loc.lng)
            : null;

          return (
            <Marker
              key={`${loc.lat}-${loc.lng}-${idx}`}
              position={[loc.lat, loc.lng]}
              icon={getMarkerIcon(isHighlighted)}
              eventHandlers={{
                click: () => onMarkerClick && onMarkerClick(loc),
              }}
            >
              {/* Tooltip: shows name on hover */}
              <Tooltip direction="top" offset={[0, -38]} opacity={0.97}>
                <div
                  style={{
                    fontWeight: '700',
                    fontSize: '0.78rem',
                    color: '#1e293b',
                    whiteSpace: 'nowrap',
                    maxWidth: '220px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {meta.emoji} {loc.name}
                  {distance !== null && (
                    <span style={{ color: '#2563eb', marginLeft: '0.4rem', fontWeight: '500' }}>
                      · {distance.toFixed(1)} km
                    </span>
                  )}
                </div>
              </Tooltip>

              {/* Popup: full info card */}
              <Popup minWidth={275} maxWidth={315}>
                <div style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}>
                  {/* Category badge */}
                  <span
                    style={{
                      display: 'inline-block',
                      background: isHighlighted ? '#d97706' : '#dc2626',
                      color: '#fff',
                      fontSize: '0.68rem',
                      fontWeight: '700',
                      padding: '2px 9px',
                      borderRadius: '12px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      marginBottom: '0.4rem',
                    }}
                  >
                    {meta.emoji} {meta.label}
                  </span>

                  {/* Name */}
                  <h3
                    style={{
                      margin: '0 0 0.3rem 0',
                      fontSize: '1rem',
                      fontWeight: '700',
                      color: '#1e293b',
                      lineHeight: '1.3',
                    }}
                  >
                    {loc.name}
                  </h3>

                  {/* Rating */}
                  {loc.rating != null && (
                    <div
                      style={{
                        color: '#f59e0b',
                        fontSize: '0.9rem',
                        letterSpacing: '1px',
                        marginBottom: '0.4rem',
                      }}
                    >
                      {renderStars(loc.rating)}
                      <span
                        style={{
                          color: '#64748b',
                          fontSize: '0.75rem',
                          marginLeft: '0.35rem',
                          letterSpacing: 'normal',
                        }}
                      >
                        {loc.rating.toFixed(1)} / 5
                      </span>
                    </div>
                  )}

                  {/* Description */}
                  {loc.description && (
                    <p
                      style={{
                        margin: '0 0 0.5rem 0',
                        fontSize: '0.8rem',
                        color: '#475569',
                        lineHeight: '1.5',
                        borderLeft: '3px solid #dc2626',
                        paddingLeft: '0.5rem',
                      }}
                    >
                      {loc.description.length > 130
                        ? loc.description.slice(0, 130) + '…'
                        : loc.description}
                    </p>
                  )}

                  {/* Info rows */}
                  <div
                    style={{
                      background: '#f8fafc',
                      borderRadius: '8px',
                      padding: '0.5rem 0.6rem',
                      fontSize: '0.78rem',
                      color: '#475569',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.28rem',
                    }}
                  >
                    {loc.address && (
                      <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'flex-start' }}>
                        <span style={{ flexShrink: 0 }}>📍</span>
                        <span style={{ lineHeight: '1.4' }}>{loc.address}</span>
                      </div>
                    )}
                    {loc.location && !loc.address && (
                      <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <span>🗺️</span>
                        <span>{loc.location}</span>
                      </div>
                    )}
                    {loc.hours && (
                      <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <span>🕐</span>
                        <span>{loc.hours}</span>
                      </div>
                    )}
                    {loc.price && (
                      <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <span>💰</span>
                        <span style={{ color: '#16a34a', fontWeight: '600' }}>{loc.price}</span>
                      </div>
                    )}
                    {distance !== null && (
                      <div
                        style={{
                          display: 'flex',
                          gap: '0.4rem',
                          color: '#1d4ed8',
                          fontWeight: '600',
                          borderTop: '1px solid #e2e8f0',
                          paddingTop: '0.28rem',
                          marginTop: '0.1rem',
                        }}
                      >
                        <span>📏</span>
                        <span>{distance.toFixed(1)} km dari lokasi Anda</span>
                      </div>
                    )}
                  </div>

                  {/* Google Maps button */}
                  <a
                    href={`https://www.google.com/maps?q=${loc.lat},${loc.lng}&z=17`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.35rem',
                      marginTop: '0.6rem',
                      padding: '0.45rem',
                      background: 'linear-gradient(135deg, #dc2626, #b91c1c)',
                      color: '#fff',
                      borderRadius: '7px',
                      textDecoration: 'none',
                      fontSize: '0.82rem',
                      fontWeight: '700',
                      letterSpacing: '0.02em',
                    }}
                  >
                    🗺️ Buka di Google Maps
                  </a>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* User location marker */}
        {userLocation && (
          <Marker
            position={[userLocation.lat, userLocation.lng]}
            icon={ICONS.blue}
            zIndexOffset={1000}
          >
            <Tooltip direction="top" offset={[0, -38]} opacity={1} permanent>
              <div
                style={{
                  fontWeight: '700',
                  fontSize: '0.75rem',
                  color: '#1e40af',
                  whiteSpace: 'nowrap',
                }}
              >
                📌 Lokasi Saya
              </div>
            </Tooltip>
            <Popup>
              <div style={{ fontFamily: 'system-ui, sans-serif', minWidth: '165px' }}>
                <h3 style={{ margin: '0 0 0.4rem 0', color: '#1d4ed8', fontSize: '0.95rem' }}>
                  📌 Posisi Anda
                </h3>
                <p style={{ margin: 0, fontSize: '0.8rem', color: '#555' }}>
                  {userLocation.lat.toFixed(5)}°, {userLocation.lng.toFixed(5)}°
                </p>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Smart fly-to: only flies when userLocation genuinely changes */}
        <FlyToLocation position={userLocation} />
        {/* Smart fit-bounds: only refits on initial load or new highlight */}
        <FitBounds locations={finalLocations} highlightLocation={highlightLocation} />
      </MapContainer>

      {/* Footer legend + controls */}
      <div
        style={{
          background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
          padding: '0.55rem 1rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.5rem',
          borderTop: '1px solid rgba(251,191,36,0.2)',
        }}
      >
        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.75rem', color: 'rgba(255,255,255,0.7)' }}>
          <span>📍 {finalLocations.length} lokasi wisata</span>
          {userLocation && <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: '0.7rem' }}>· diurutkan terdekat</span>}
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          {locationError && (
            <span style={{ color: '#f87171', fontSize: '0.71rem' }}>{locationError}</span>
          )}
          {userLocation && (
            <span style={{ color: '#60a5fa', fontSize: '0.75rem', fontWeight: '500' }}>
              ✓ Lokasi ditemukan
            </span>
          )}
          <button
            onClick={handleLocateMe}
            disabled={isLocating}
            style={{
              background: userLocation
                ? 'linear-gradient(135deg, #1e40af, #1d4ed8)'
                : 'linear-gradient(135deg, #2563eb, #3b82f6)',
              border: 'none',
              color: '#fff',
              padding: '0.4rem 0.9rem',
              borderRadius: '8px',
              cursor: isLocating ? 'not-allowed' : 'pointer',
              fontSize: '0.8rem',
              fontWeight: '700',
              opacity: isLocating ? 0.7 : 1,
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
              boxShadow: '0 2px 10px rgba(37,99,235,0.45)',
            }}
          >
            {isLocating ? '⏳ Mencari...' : '📍 Lokasi Saya'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default MapView;
