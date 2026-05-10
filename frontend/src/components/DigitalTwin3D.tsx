import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sky, Box, Cylinder } from '@react-three/drei';
import * as THREE from 'three';

interface DigitalTwin3DProps {
  obstacles: any[];
  sunAlt: number;
  sunAz: number;
  panelAction: string; // "tracking", "stow", "diffuse"
}

function SunLight({ alt, az }: { alt: number, az: number }) {
  const distance = 100;
  const phi = (90 - alt) * (Math.PI / 180);
  const azRad = az * (Math.PI / 180);
  
  // Convert spherical to cartesian (X=East, -Z=North, Y=Up)
  const r_h = distance * Math.sin(phi);
  const sunX = r_h * Math.sin(azRad);
  const sunZ = r_h * -Math.cos(azRad);
  const sunY = distance * Math.cos(phi);

  return (
    <group>
      <directionalLight 
        castShadow 
        position={[sunX, sunY, sunZ]} 
        intensity={2.0} 
        shadow-mapSize={[2048, 2048]}
      />
      <mesh position={[sunX, sunY, sunZ]}>
         <sphereGeometry args={[5, 16, 16]} />
         <meshBasicMaterial color="#fbbf24" />
      </mesh>
    </group>
  );
}

function Building({ obs }: { obs: any }) {
  const shape = useMemo(() => {
    const s = new THREE.Shape();
    if (!obs.polygon || obs.polygon.length === 0) return s;
    obs.polygon.forEach((pt: number[], idx: number) => {
        // x is East (+X), y is North (-Z in Three.js)
        if (idx === 0) s.moveTo(pt[0], -pt[1]);
        else s.lineTo(pt[0], -pt[1]);
    });
    return s;
  }, [obs.polygon]);

  const height = obs.z_height || 10;

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} castShadow receiveShadow>
      <extrudeGeometry args={[shape, { depth: height, bevelEnabled: false }]} />
      <meshStandardMaterial color="#475569" roughness={0.9} />
    </mesh>
  );
}

function Obstacles({ data }: { data: any[] }) {
  return (
    <group>
      {data.map((obs, i) => {
        if (obs.type === 'building' && obs.polygon && obs.polygon.length > 0) {
            return <Building key={`b-${i}`} obs={obs} />
        }
        if (obs.type === 'tree' && obs.point && obs.point.length >= 2) {
            const height = obs.z_height || 5;
            const radius = obs.radius || 2;
            return (
              <Cylinder key={`t-${i}`} args={[radius, radius, height, 8]} position={[obs.point[0], height/2, -obs.point[1]]} castShadow receiveShadow>
                 <meshStandardMaterial color="#166534" />
              </Cylinder>
            )
        }
        return null;
      })}
    </group>
  );
}

function SolarPanel({ action, sunAlt, sunAz }: { action: string, sunAlt: number, sunAz: number }) {
  const groupRef = useRef<THREE.Group>(null);
  
  useFrame(() => {
    if (!groupRef.current) return;
    
    // Animate to target rotation
    let targetTilt = 0; // Pitch (X-axis)
    let targetAz = 180; // Yaw (Y-axis)
    
    if (action === "tracking") {
        targetTilt = Math.max(0, 90 - sunAlt);
        targetAz = sunAz;
    } else if (action === "stow" || action === "diffuse") {
        targetTilt = 0; // Flat
        targetAz = 180; // South
    }
    
    // Smooth interpolation could go here, snapping for now
    groupRef.current.rotation.x = THREE.MathUtils.degToRad(targetTilt);
    groupRef.current.rotation.y = THREE.MathUtils.degToRad(180 - targetAz);
  });

  return (
    <group position={[0, 2, 0]}>
        {/* Animated Head */}
        <group ref={groupRef}>
            <Box args={[4, 0.1, 2]} castShadow receiveShadow>
                <meshStandardMaterial color="#1e3a8a" roughness={0.2} metalness={0.8} />
            </Box>
        </group>
        {/* Static Mount */}
        <Cylinder args={[0.2, 0.2, 2]} position={[0, -1, 0]} castShadow receiveShadow>
            <meshStandardMaterial color="#94a3b8" />
        </Cylinder>
    </group>
  );
}

export default function DigitalTwin3D({ obstacles, sunAlt, sunAz, panelAction }: DigitalTwin3DProps) {
  const distance = 100;
  const phi = (90 - sunAlt) * (Math.PI / 180);
  const azRad = sunAz * (Math.PI / 180);
  
  const r_h = distance * Math.sin(phi);
  const sunX = r_h * Math.sin(azRad);
  const sunZ = r_h * -Math.cos(azRad);
  const sunY = distance * Math.cos(phi);

  return (
    <Canvas shadows camera={{ position: [15, 15, 25], fov: 45 }} className="w-full h-full bg-slate-900">
      <color attach="background" args={['#1e293b']} />
      
      {/* Sky component breaks if sun is below horizon, clamp Y to a higher minimum for twilight look */}
      <Sky sunPosition={[sunX, Math.max(5, sunY), sunZ]} turbidity={0.2} rayleigh={0.8} />
      
      {/* Brighter ambient light so we can always see the scene */}
      <ambientLight intensity={0.8} />
      <hemisphereLight skyColor="#ffffff" groundColor="#334155" intensity={0.6} />
      
      {sunAlt > 0 && <SunLight alt={sunAlt} az={sunAz} />}
      
      {/* Ground */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[200, 200]} />
        <meshStandardMaterial color="#334155" />
      </mesh>
      
      <gridHelper args={[200, 40, '#64748b', '#1e293b']} position={[0, 0.01, 0]} />
      
      <SolarPanel action={panelAction} sunAlt={sunAlt} sunAz={sunAz} />
      <Obstacles data={obstacles || []} />
      
      <OrbitControls makeDefault maxPolarAngle={Math.PI / 2 - 0.05} target={[0, 2, 0]} />
    </Canvas>
  );
}
