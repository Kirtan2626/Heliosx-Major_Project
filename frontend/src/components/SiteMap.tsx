import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { Coordinates } from '@/types';
import { useEffect } from 'react';

// Fix Leaflet icon issue in Next.js
const customIcon = new L.Icon({
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});

interface SiteMapProps {
  position: Coordinates;
  onPositionChange: (pos: Coordinates) => void;
}

function LocationMarker({ position, onPositionChange }: SiteMapProps) {
  const map = useMapEvents({
    click(e) {
      onPositionChange({ lat: e.latlng.lat, lon: e.latlng.lng });
    },
  });

  useEffect(() => {
    if (position) {
      map.flyTo([position.lat, position.lon], map.getZoom());
    }
  }, [position, map]);

  return position === null ? null : (
    <Marker position={[position.lat, position.lon]} icon={customIcon}></Marker>
  );
}

export default function SiteMap({ position, onPositionChange }: SiteMapProps) {
  // Use a stable key to prevent re-initialization unless absolutely necessary
  // This avoids the "Map container is being reused by another instance" error in dev mode
  return (
    <div className="h-64 w-full rounded-xl overflow-hidden border border-slate-700">
      <MapContainer 
        key="heliosx-map-instance"
        center={[position.lat, position.lon]} 
        zoom={13} 
        scrollWheelZoom={true} 
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <LocationMarker position={position} onPositionChange={onPositionChange} />
      </MapContainer>
    </div>
  );
}

