import React, { useState, useEffect, useCallback } from 'react';
import Map, { NavigationControl, Source, Layer, Marker } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import axios from 'axios';
import { Search, MapPin, Navigation, Loader2, Info } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Bengaluru coords roughly
const INITIAL_VIEW_STATE = {
  longitude: 77.6245,
  latitude: 12.9352,
  zoom: 14,
  pitch: 45
};

const VEHICLES = [
  { id: 'bike', label: 'Motorcycle', width: 1.0, height: 1.5, weight: 0.2 },
  { id: 'hatchback', label: 'Hatchback', width: 1.8, height: 1.6, weight: 1.2 },
  { id: 'suv', label: 'SUV', width: 2.2, height: 2.0, weight: 2.5 },
  { id: 'van', label: 'Delivery Van', width: 2.4, height: 2.6, weight: 3.5 },
];

const DEMO_SPEEDS = {
  bike: 28,
  hatchback: 22,
  suv: 17,
  van: 14,
};

const toRadians = (deg) => (deg * Math.PI) / 180;

const haversineKm = (a, b) => {
  const earthRadiusKm = 6371;
  const dLat = toRadians(b.lat - a.lat);
  const dLon = toRadians(b.lon - a.lon);
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);

  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;

  return 2 * earthRadiusKm * Math.asin(Math.sqrt(h));
};

const buildDemoRoute = (origin, destination, vehicle) => {
  const waypointCount = 12;
  const factors = {
    bike: 0.8,
    hatchback: 1.0,
    suv: 1.3,
    van: 1.6,
  };

  const coords = [];
  const routeBias = factors[vehicle.id] || 1.0;

  for (let i = 0; i <= waypointCount; i += 1) {
    const t = i / waypointCount;
    const lat = origin.lat + (destination.lat - origin.lat) * t;
    const lon = origin.lon + (destination.lon - origin.lon) * t;
    const wobbleLat = Math.sin(t * Math.PI * 2.3) * 0.0018 * routeBias;
    const wobbleLon = Math.cos(t * Math.PI * 2.7) * 0.0024 * routeBias;

    coords.push([
      lon + wobbleLon,
      lat + wobbleLat,
    ]);
  }

  return {
    type: 'LineString',
    coordinates: coords,
  };
};

const buildDemoStats = (origin, destination, vehicle) => {
  const distanceKm = haversineKm(origin, destination);
  const speedKmh = DEMO_SPEEDS[vehicle.id] || 20;
  const etaMins = Math.max(1, (distanceKm / speedKmh) * 60);

  return {
    routeDistanceKm: distanceKm,
    routeEtaMins: etaMins,
    comparisonDistanceKm: distanceKm * 0.94,
    comparisonEtaMins: Math.max(1, etaMins * 0.9),
  };
};

const mapStyle = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '&copy; OpenStreetMap Contributors'
    }
  },
  layers: [
    {
      id: 'osm',
      type: 'raster',
      source: 'osm'
    }
  ]
};

// Debounce hook for geocoding
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

function App() {
  const [vehicle, setVehicle] = useState(VEHICLES[1]);
  const [loading, setLoading] = useState(false);
  const [routeStats, setRouteStats] = useState(null);
  const [demoMode, setDemoMode] = useState(false);

  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const [routeGeojson, setRouteGeojson] = useState(null);
  const [gmapsGeojson, setGmapsGeojson] = useState(null);

  // Search States
  const [origQuery, setOrigQuery] = useState('');
  const [destQuery, setDestQuery] = useState('');
  const [origResults, setOrigResults] = useState([]);
  const [destResults, setDestResults] = useState([]);
  const [showOrigDropdown, setShowOrigDropdown] = useState(false);
  const [showDestDropdown, setShowDestDropdown] = useState(false);

  const debouncedOrig = useDebounce(origQuery, 500);
  const debouncedDest = useDebounce(destQuery, 500);

  // Geocoding effect
  useEffect(() => {
    if (debouncedOrig.length > 3) {
      axios.get(`https://nominatim.openstreetmap.org/search?format=json&q=${debouncedOrig}&limit=5`)
        .then(res => { setOrigResults(res.data); setShowOrigDropdown(true); })
        .catch(console.error);
    }
  }, [debouncedOrig]);

  useEffect(() => {
    if (debouncedDest.length > 3) {
      axios.get(`https://nominatim.openstreetmap.org/search?format=json&q=${debouncedDest}&limit=5`)
        .then(res => { setDestResults(res.data); setShowDestDropdown(true); })
        .catch(console.error);
    }
  }, [debouncedDest]);

  const selectOrigin = (loc) => {
    setOrigin({ lat: parseFloat(loc.lat), lon: parseFloat(loc.lon) });
    setOrigQuery(loc.display_name.split(',')[0]);
    setShowOrigDropdown(false);
  };

  const selectDest = (loc) => {
    setDestination({ lat: parseFloat(loc.lat), lon: parseFloat(loc.lon) });
    setDestQuery(loc.display_name.split(',')[0]);
    setShowDestDropdown(false);
  };

  const locateMe = () => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition((pos) => {
        setOrigin({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setOrigQuery("My Location");
      });
    } else {
      alert("Geolocation is not supported by your browser");
    }
  };

  const handleMapClick = (e) => {
    const coords = { lon: e.lngLat.lng, lat: e.lngLat.lat };
    if (!origin) {
      setOrigin(coords);
      setOrigQuery("Map Location (Origin)");
    } else if (!destination) {
      setDestination(coords);
      setDestQuery("Map Location (Destination)");
    }
  };

  const calculateRoute = async () => {
    if (!origin || !destination) {
      alert("Please select both Origin and Destination.");
      return;
    }

    setLoading(true);
    setDemoMode(false);

    try {
      const res = await axios.post(`${API_BASE_URL}/route/compare`, {
        orig_lat: origin.lat,
        orig_lon: origin.lon,
        dest_lat: destination.lat,
        dest_lon: destination.lon,
        vehicle_width: vehicle.width,
        vehicle_height: vehicle.height,
        vehicle_weight: vehicle.weight
      });

      setRouteGeojson(res.data.roadfit_geometry);
      setGmapsGeojson(res.data.gmaps_geometry);

      setRouteStats({
        rf_distance: res.data.roadfit_stats.distance_km,
        rf_eta: res.data.roadfit_stats.eta_mins,
        gmaps_distance: res.data.gmaps_stats.distance_km,
        gmaps_eta: res.data.gmaps_stats.eta_mins
      });
    } catch (error) {
      console.warn("Backend unavailable; using demo route fallback.", error);

      const fallbackRoute = buildDemoRoute(origin, destination, vehicle);
      const fallbackStats = buildDemoStats(origin, destination, vehicle);

      setRouteGeojson(fallbackRoute);
      setGmapsGeojson({
        ...fallbackRoute,
        coordinates: fallbackRoute.coordinates.map(([lon, lat], index) => {
          if (index === 0 || index === fallbackRoute.coordinates.length - 1) return [lon, lat];
          return [lon + 0.0008, lat - 0.0004];
        }),
      });

      setRouteStats({
        rf_distance: fallbackStats.routeDistanceKm,
        rf_eta: fallbackStats.routeEtaMins,
        gmaps_distance: fallbackStats.comparisonDistanceKm,
        gmaps_eta: fallbackStats.comparisonEtaMins,
      });

      setDemoMode(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Map Background */}
      <Map
        initialViewState={INITIAL_VIEW_STATE}
        mapStyle={mapStyle}
        style={{width: '100%', height: '100%', position: 'absolute'}}
        onClick={handleMapClick}
      >
        <NavigationControl position="bottom-right" />
        
        {/* Draggable Markers */}
        {origin && (
          <Marker 
            longitude={origin.lon} 
            latitude={origin.lat} 
            color="#10b981"
            draggable
            onDragEnd={(e) => {
                setOrigin({ lon: e.lngLat.lng, lat: e.lngLat.lat });
                setOrigQuery("Custom Map Pin");
            }}
          />
        )}
        
        {destination && (
          <Marker 
            longitude={destination.lon} 
            latitude={destination.lat} 
            color="#ef4444"
            draggable
            onDragEnd={(e) => {
                setDestination({ lon: e.lngLat.lng, lat: e.lngLat.lat });
                setDestQuery("Custom Map Pin");
            }}
          />
        )}
        
        {/* Google Maps Route Layer (Underneath, Red) */}
        {gmapsGeojson && (
          <Source id="gmaps-route" type="geojson" data={gmapsGeojson}>
            <Layer
              id="gmaps-route-line"
              type="line"
              paint={{
                'line-color': '#ef4444',
                'line-width': 4,
                'line-opacity': 0.6,
                'line-dasharray': [2, 2]
              }}
            />
          </Source>
        )}
        
        {/* RoadFit Route Layer (On top, Blue) */}
        {routeGeojson && (
          <Source id="rf-route" type="geojson" data={routeGeojson}>
            <Layer
              id="rf-route-line"
              type="line"
              paint={{
                'line-color': '#4f46e5',
                'line-width': 6,
                'line-opacity': 0.9
              }}
            />
          </Source>
        )}
      </Map>

      {/* Floating Glassmorphism Sidebar */}
      <div className="sidebar">
        <div className="header">
          <h1>RoadFit</h1>
          <p>Vehicle-Aware Hyperlocal Routing</p>
        </div>

        {/* Origin Search */}
        <div className="form-group">
          <label>Origin</label>
          <div className="input-with-icon">
            <Search className="input-icon" size={18} />
            <input 
              className="form-control" 
              type="text" 
              placeholder="Search origin..." 
              value={origQuery}
              onChange={(e) => setOrigQuery(e.target.value)}
            />
            <button className="icon-btn locate-btn" onClick={locateMe} title="Locate Me">
              <Navigation size={18} />
            </button>
          </div>
          {showOrigDropdown && origResults.length > 0 && (
            <div className="dropdown">
              {origResults.map(loc => (
                <div key={loc.place_id} className="dropdown-item" onClick={() => selectOrigin(loc)}>
                  <MapPin size={14} className="mr-2 inline" />
                  {loc.display_name}
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* Destination Search */}
        <div className="form-group">
          <label>Destination</label>
          <div className="input-with-icon">
            <Search className="input-icon" size={18} />
            <input 
              className="form-control" 
              type="text" 
              placeholder="Search destination..." 
              value={destQuery}
              onChange={(e) => setDestQuery(e.target.value)}
            />
          </div>
          {showDestDropdown && destResults.length > 0 && (
            <div className="dropdown">
              {destResults.map(loc => (
                <div key={loc.place_id} className="dropdown-item" onClick={() => selectDest(loc)}>
                  <MapPin size={14} className="mr-2 inline" />
                  {loc.display_name}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="form-group">
          <label>Select Vehicle Profile</label>
          <div className="vehicle-selector">
            {VEHICLES.map(v => (
              <button 
                key={v.id}
                className={`vehicle-btn ${vehicle.id === v.id ? 'active' : ''}`}
                onClick={() => setVehicle(v)}
              >
                {v.label}
              </button>
            ))}
          </div>
        </div>
        
        <div className="metrics-panel info-panel">
          <Info size={16} color="#94a3b8" />
          <span style={{fontSize: '12px', color: '#cbd5e1', marginLeft: '8px'}}>
            Constraints: W &gt; {vehicle.width}m | H &gt; {vehicle.height}m | Wgt {vehicle.weight}t
          </span>
        </div>

        <button className="primary-btn" onClick={calculateRoute} disabled={loading || !origin || !destination}>
          {loading ? (
            <span style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px'}}>
              <Loader2 className="spinner" size={20} />
              Routing...
            </span>
          ) : 'Calculate Optimal Route'}
        </button>

        {demoMode && (
          <div className="metrics-panel info-panel">
            <Info size={16} color="#fbbf24" />
            <span style={{fontSize: '12px', color: '#fef3c7', marginLeft: '8px'}}>
              Demo mode: backend unavailable; local fallback route shown.
            </span>
          </div>
        )}

        {routeStats && (
          <div className="results-container">
            <div className="result-card roadfit">
              <div className="result-header">RoadFit (Live Traffic)</div>
              <div className="result-stats">
                <div className="stat"><span>Dist</span><strong>{routeStats.rf_distance.toFixed(1)} km</strong></div>
                <div className="stat"><span>ETA</span><strong>{routeStats.rf_eta.toFixed(1)} min</strong></div>
              </div>
            </div>
            
            <div className="result-card gmaps">
              <div className="result-header">Google Maps Benchmark</div>
              <div className="result-stats">
                <div className="stat"><span>Dist</span><strong>{routeStats.gmaps_distance.toFixed(1)} km</strong></div>
                <div className="stat"><span>ETA</span><strong>{routeStats.gmaps_eta.toFixed(1)} min</strong></div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
