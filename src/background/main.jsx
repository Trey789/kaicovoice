import React from 'react';
import { createRoot } from 'react-dom/client';
import GhostFibers from './GhostFibers';

const mount = document.getElementById('siteFibers');
if (mount && document.createElement('canvas').getContext('webgl2')) {
  createRoot(mount).render(
    <GhostFibers
      lineColor="#173122"
      glowColor="#89B52E"
      speed={0.2}
      scale={2}
      rotation={0}
      rotationSpeed={0.25}
      layers={4}
      waveAmplitude={0.015}
      waveFrequency={3}
      waveSpeed={0.15}
      layerSpeed={0.08}
      twist={0.1}
      twistFrequency={5}
      twistSpeed={1.2}
      lineFrequency={5}
      lineSpacing={2}
      lineSharpness={16}
      glowFalloff={10}
      glowIntensity={1.15}
      brightness={1.5}
      blueBoost={1}
      vignette={0.8}
      grain={0.05}
      dpr={1}
      fps={30}
    />
  );
}
