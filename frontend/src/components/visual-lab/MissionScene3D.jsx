import React, { forwardRef, useImperativeHandle, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';

const PARTICLE_STARTS = Array.from({ length: 24 }, (_, index) => ({
  x: -2.05 + ((index * 37) % 190) / 100,
  y: -0.92 + ((index * 19) % 180) / 100,
  z: -0.78 + ((index * 31) % 150) / 100,
}));

function AirflowParticles({ settings, visible }) {
  const particles = useRef([]);
  useFrame((_, delta) => {
    if (!visible) return;
    particles.current.forEach((particle, index) => {
      if (!particle) return;
      particle.position.x += delta * settings.particleMotion;
      if (particle.position.x > 2.1) {
        particle.position.x = -2.1;
        particle.position.y = PARTICLE_STARTS[index].y;
      }
    });
  });

  return PARTICLE_STARTS.slice(0, settings.particleCount).map((position, index) => (
    <mesh
      key={index}
      ref={(node) => { particles.current[index] = node; }}
      position={[position.x, position.y, position.z]}
      visible={visible}
    >
      <sphereGeometry args={[0.025, 6, 6]} />
      <meshBasicMaterial color={settings.accent} transparent opacity={0.78} />
    </mesh>
  ));
}

function ChamberScene({ settings, mode, playing }) {
  const flame = useRef();
  useFrame(({ clock }) => {
    if (!playing || !flame.current) return;
    const pulse = 1 + Math.sin(clock.elapsedTime * 2.2) * 0.035;
    flame.current.scale.set(pulse, pulse, pulse);
  });

  const spherical = mode === 'spherical' || mode === 'microgravity';
  const propagation = mode === 'propagation';
  const showParticles = mode === 'airflow' || mode === 'chamber';

  return (
    <>
      <color attach="background" args={['#080f1f']} />
      <ambientLight intensity={0.8} />
      <pointLight position={[1.5, 1.5, 2.5]} color="#38bdf8" intensity={7} distance={8} />
      <pointLight position={[-1, -0.2, 0]} color="#fb923c" intensity={5} distance={5} />

      <group>
        <mesh>
          <boxGeometry args={[4.6, 2.8, 2.2]} />
          <meshPhysicalMaterial color="#38bdf8" transparent opacity={settings.chamberOpacity} roughness={0.25} />
        </mesh>
        <mesh>
          <boxGeometry args={[4.62, 2.82, 2.22]} />
          <meshBasicMaterial color={settings.accent} wireframe transparent opacity={0.52} />
        </mesh>

        <mesh position={[0, -0.93, 0]} rotation={[0, 0, 0]}>
          <boxGeometry args={[1.2, 0.16, 0.5]} />
          <meshStandardMaterial color={settings.materialSwatch} metalness={0.2} roughness={0.65} />
        </mesh>

        <group ref={flame} position={[0, -0.12, 0]}>
          {spherical ? (
            <mesh scale={[0.58, 0.72, 0.58]}>
              <sphereGeometry args={[0.56, 18, 14]} />
              <meshStandardMaterial color="#fb923c" emissive="#f97316" emissiveIntensity={settings.glowOpacity * 1.8} transparent opacity={settings.glowOpacity} />
            </mesh>
          ) : propagation ? (
            <mesh rotation={[0, 0, -Math.PI / 2]} scale={[1.05, 0.44, 0.5]}>
              <coneGeometry args={[0.46, 1.35, 16]} />
              <meshStandardMaterial color="#fb923c" emissive="#f97316" emissiveIntensity={settings.glowOpacity * 1.8} transparent opacity={settings.glowOpacity} />
            </mesh>
          ) : (
            <mesh position={[0, 0.22, 0]} scale={[0.7, 1.2, 0.7]}>
              <coneGeometry args={[0.43, 1.25, 16]} />
              <meshStandardMaterial color="#fb923c" emissive="#f97316" emissiveIntensity={settings.glowOpacity * 1.8} transparent opacity={settings.glowOpacity} />
            </mesh>
          )}
          <mesh position={[0, -0.23, 0]} scale={spherical ? [0.24, 0.28, 0.24] : [0.22, 0.36, 0.22]}>
            <sphereGeometry args={[0.45, 12, 10]} />
            <meshBasicMaterial color="#fde68a" transparent opacity={0.82} />
          </mesh>
        </group>
        <AirflowParticles settings={settings} visible={showParticles} />
      </group>
    </>
  );
}

export function StaticChamberFallback({ message = 'WebGL is unavailable; this static chamber view is illustrative.' }) {
  return (
    <div className="flex h-full min-h-64 flex-col items-center justify-center gap-3 rounded-xl border border-cyan-900/60 bg-space-sidebar p-6 text-center" role="status">
      <div className="relative flex h-40 w-64 items-center justify-center rounded-2xl border border-cyan-700/70 bg-cyan-950/10">
        <div className="absolute bottom-7 h-2 w-20 rounded bg-amber-300/80" />
        <div className="h-24 w-12 rounded-full bg-gradient-to-t from-orange-600/80 via-amber-300/80 to-transparent blur-[1px]" />
        <span className="absolute inset-0 rounded-2xl border border-cyan-400/20" />
      </div>
      <p className="max-w-sm text-xs leading-relaxed text-slate-300">{message}</p>
      <p className="text-[10px] text-slate-500">Illustration only; no validated flame behavior or measured quantities are modeled.</p>
    </div>
  );
}

const MissionScene3D = forwardRef(function MissionScene3D({ settings, mode, playing }, ref) {
  const cameraRef = useRef(null);
  useImperativeHandle(ref, () => ({
    rotateCamera(deltaX, deltaY) {
      const camera = cameraRef.current;
      if (!camera) return;
      const distance = camera.position.length();
      camera.position.x -= deltaX * 0.018;
      camera.position.y = Math.max(-distance * 0.75, Math.min(distance * 0.75, camera.position.y + deltaY * 0.014));
      camera.position.setLength(distance);
      camera.lookAt(0, 0, 0);
    },
    zoom(factor) {
      const camera = cameraRef.current;
      if (!camera) return;
      camera.position.setLength(Math.max(3.4, Math.min(11, camera.position.length() * factor)));
      camera.lookAt(0, 0, 0);
    },
    resetCamera() {
      const camera = cameraRef.current;
      if (!camera) return;
      camera.position.set(4.2, 2.8, 5.5);
      camera.lookAt(0, 0, 0);
    },
  }), []);

  return (
    <Canvas
      dpr={[1, 1.5]}
      frameloop={playing ? 'always' : 'demand'}
      camera={{ position: [4.2, 2.8, 5.5], fov: 43, near: 0.1, far: 40 }}
      gl={{ antialias: false, powerPreference: 'low-power', alpha: false }}
      onCreated={({ camera }) => {
        camera.lookAt(0, 0, 0);
        cameraRef.current = camera;
      }}
      fallback={<StaticChamberFallback />}
      aria-label="Illustrative 3D combustion chamber"
    >
      <ChamberScene settings={settings} mode={mode} playing={playing} />
    </Canvas>
  );
});

export default MissionScene3D;
