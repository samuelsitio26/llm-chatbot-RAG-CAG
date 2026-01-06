import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix default marker icon issue with Leaflet + React
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
});

// Custom red icon for tourism locations
const redIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Custom gold icon for highlighted locations
const goldIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Component to fit map bounds to markers
function FitBounds({ locations }) {
  const map = useMap();
  
  useEffect(() => {
    if (locations && locations.length > 0) {
      const bounds = L.latLngBounds(locations.map(loc => [loc.lat, loc.lng]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });
    }
  }, [locations, map]);
  
  return null;
}

// Main MapView Component
function MapView({ 
  locations = [], 
  height = '400px', 
  showAll = true, 
  highlightLocation = null,
  onMarkerClick = null 
}) {
  const [mapCenter] = useState([2.6500, 98.8500]); // Danau Toba center
  const [mapZoom] = useState(10);
  
  // Filter locations if highlightLocation is specified
  const displayLocations = highlightLocation 
    ? locations.filter(loc => 
        loc.name.toLowerCase().includes(highlightLocation.toLowerCase())
      )
    : (showAll ? locations : []);
  
  // If filtering didn't find anything, show all
  const finalLocations = displayLocations.length > 0 ? displayLocations : locations;
  
  if (!locations || locations.length === 0) {
    return (
      <div style={{ 
        padding: '2rem', 
        textAlign: 'center', 
        background: 'rgba(30, 41, 59, 0.6)', 
        borderRadius: '8px',
        border: '1px solid rgba(220, 38, 38, 0.3)'
      }}>
        <p style={{ color: 'rgba(255, 255, 255, 0.7)', margin: 0 }}>
          📍 No location data available. Run extract_locations.py first.
        </p>
      </div>
    );
  }

  return (
    <div style={{ 
      borderRadius: '12px', 
      overflow: 'hidden', 
      border: '2px solid #fbbf24',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)'
    }}>
      <MapContainer 
        center={mapCenter} 
        zoom={mapZoom} 
        style={{ height, width: '100%' }}
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {finalLocations.map((location, idx) => {
          const isHighlighted = highlightLocation && 
            location.name.toLowerCase().includes(highlightLocation.toLowerCase());
          
          return (
            <Marker 
              key={`${location.lat}-${location.lng}-${idx}`}
              position={[location.lat, location.lng]}
              icon={isHighlighted ? goldIcon : redIcon}
              eventHandlers={{
                click: () => {
                  if (onMarkerClick) onMarkerClick(location);
                }
              }}
            >
              <Popup>
                <div style={{ minWidth: '180px', maxWidth: '250px' }}>
                  <h3 style={{ 
                    marginBottom: '0.5rem', 
                    marginTop: 0,
                    color: '#dc2626',
                    fontSize: '1.1rem',
                    borderBottom: '2px solid #fbbf24',
                    paddingBottom: '0.5rem'
                  }}>
                    📍 {location.name}
                  </h3>
                  
                  {location.description && (
                    <p style={{ 
                      margin: '0.5rem 0', 
                      fontSize: '0.9rem',
                      color: '#333',
                      lineHeight: '1.4'
                    }}>
                      {location.description}
                    </p>
                  )}
                  
                  <div style={{ 
                    background: '#f5f5f5', 
                    padding: '0.5rem',
                    borderRadius: '4px',
                    marginTop: '0.5rem'
                  }}>
                    <p style={{ 
                      margin: '0.25rem 0', 
                      fontSize: '0.85rem',
                      color: '#666'
                    }}>
                      <strong>Lat:</strong> {location.lat.toFixed(4)}°
                    </p>
                    <p style={{ 
                      margin: '0.25rem 0', 
                      fontSize: '0.85rem',
                      color: '#666'
                    }}>
                      <strong>Lng:</strong> {location.lng.toFixed(4)}°
                    </p>
                  </div>
                  
                  {location.source && location.source !== 'default' && (
                    <p style={{ 
                      marginTop: '0.5rem', 
                      marginBottom: 0,
                      fontSize: '0.75rem',
                      color: '#999',
                      fontStyle: 'italic'
                    }}>
                      📄 {location.source}
                    </p>
                  )}
                  
                  <a 
                    href={`https://www.google.com/maps?q=${location.lat},${location.lng}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'block',
                      marginTop: '0.75rem',
                      padding: '0.5rem',
                      background: '#dc2626',
                      color: 'white',
                      textAlign: 'center',
                      borderRadius: '4px',
                      textDecoration: 'none',
                      fontSize: '0.85rem',
                      fontWeight: '500'
                    }}
                  >
                    🗺️ Open in Google Maps
                  </a>
                </div>
              </Popup>
            </Marker>
          );
        })}
        
        <FitBounds locations={finalLocations} />
      </MapContainer>
      
      {/* Legend */}
      <div style={{
        background: 'rgba(26, 26, 26, 0.95)',
        padding: '0.5rem 1rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: '0.85rem',
        color: 'rgba(255, 255, 255, 0.8)'
      }}>
        <span>📍 {finalLocations.length} lokasi wisata</span>
        <span style={{ color: '#fbbf24' }}>Klik marker untuk detail</span>
      </div>
    </div>
  );
}

export default MapView;
