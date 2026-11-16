"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { motion } from "framer-motion";
import { Brain, Sparkles, MessageCircle, Video } from "lucide-react";

interface InteractiveCurv3DOrbProps {
  className?: string;
  showCards?: boolean;
}

export function InteractiveCurv3DOrb({
  className = "",
  showCards = true,
}: InteractiveCurv3DOrbProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [webglSupported, setWebglSupported] = useState(true);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    // Check WebGL availability
    try {
      const testGl = canvas.getContext("webgl2") || canvas.getContext("webgl");
      if (!testGl) {
        setWebglSupported(false);
        return;
      }
    } catch {
      setWebglSupported(false);
      return;
    }

    const width = container.clientWidth || 500;
    const height = container.clientHeight || 500;

    // Scene, Camera, Renderer
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.z = 7.2;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        alpha: true,
        antialias: true,
        powerPreference: "high-performance",
      });
    } catch {
      setWebglSupported(false);
      return;
    }

    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    // Master group for mouse tilt and gentle orbital rotation
    const masterGroup = new THREE.Group();
    scene.add(masterGroup);

    // ─── 1. Signature CURV C-Spiral Multi-Layer Particle Assembly ───
    // The iconic CURV brand mark is a C-shaped arc of glowing beads
    // spiraling through violet, magenta, coral and gold.
    const spiralGroup = new THREE.Group();
    masterGroup.add(spiralGroup);

    // Palette stops for CURV brand
    const colorViolet = new THREE.Color(0x8b5cf6);
    const colorPurple = new THREE.Color(0x7c3aed);
    const colorMagenta = new THREE.Color(0xec4899);
    const colorOrange = new THREE.Color(0xf97316);
    const colorGold = new THREE.Color(0xfbbf24);

    function getCurvColor(t: number): THREE.Color {
      // t: 0.0 (top violet) -> 0.35 (magenta) -> 0.75 (orange) -> 1.0 (gold)
      if (t < 0.3) {
        return colorViolet.clone().lerp(colorPurple, t / 0.3);
      } else if (t < 0.6) {
        return colorPurple.clone().lerp(colorMagenta, (t - 0.3) / 0.3);
      } else if (t < 0.85) {
        return colorMagenta.clone().lerp(colorOrange, (t - 0.6) / 0.25);
      } else {
        return colorOrange.clone().lerp(colorGold, (t - 0.85) / 0.15);
      }
    }

    // High quality soft luminous spherical bead texture
    const beadTexture = (() => {
      const cv = document.createElement("canvas");
      cv.width = 128;
      cv.height = 128;
      const ctx = cv.getContext("2d");
      if (ctx) {
        const rad = 64;
        const grad = ctx.createRadialGradient(rad, rad, 0, rad, rad, rad);
        grad.addColorStop(0, "rgba(255,255,255,1)");
        grad.addColorStop(0.22, "rgba(255,255,255,0.95)");
        grad.addColorStop(0.48, "rgba(235,210,255,0.85)");
        grad.addColorStop(0.72, "rgba(165,110,255,0.45)");
        grad.addColorStop(0.9, "rgba(139,92,246,0.15)");
        grad.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 128, 128);
      }
      return new THREE.CanvasTexture(cv);
    })();

    // Construct dense concentric C-spiral particle arcs matching CURV logo
    const layers = 8;
    const pointsPerLayer = 220;
    const totalSpiralPoints = layers * pointsPerLayer;
    const spiralPositions = new Float32Array(totalSpiralPoints * 3);
    const spiralColors = new Float32Array(totalSpiralPoints * 3);
    const spiralSizes = new Float32Array(totalSpiralPoints);

    let idx = 0;
    for (let l = 0; l < layers; l++) {
      const layerFrac = l / (layers - 1);
      const baseRadius = 1.15 + layerFrac * 0.95;
      const zOffset = (layerFrac - 0.5) * 0.55;

      for (let p = 0; p < pointsPerLayer; p++) {
        const pFrac = p / pointsPerLayer;
        // C-shape covers roughly 315 degrees (leaving open mouth on right side)
        const angle = -0.32 + pFrac * Math.PI * 1.75;

        // Spiral taper: inner radius grows slightly along the arc
        const r = baseRadius * (0.85 + pFrac * 0.28);
        const x = Math.cos(angle) * r;
        const y = Math.sin(angle) * r;
        // Wave depth in Z gives genuine 3D feel when tilted
        const z = zOffset + Math.sin(pFrac * Math.PI * 2) * 0.35;

        spiralPositions[idx * 3] = x;
        spiralPositions[idx * 3 + 1] = y;
        spiralPositions[idx * 3 + 2] = z;

        const c = getCurvColor(pFrac);
        // Brighten up to create radiant jewel effect
        c.offsetHSL(0, 0.05, 0.12);

        spiralColors[idx * 3] = c.r;
        spiralColors[idx * 3 + 1] = c.g;
        spiralColors[idx * 3 + 2] = c.b;

        // Particle size tapers along the C
        const sizeMod = Math.sin(pFrac * Math.PI) * 0.45 + 0.55;
        spiralSizes[idx] = (22 + (1 - layerFrac) * 14) * sizeMod + 16;

        idx++;
      }
    }

    const spiralGeo = new THREE.BufferGeometry();
    spiralGeo.setAttribute("position", new THREE.BufferAttribute(spiralPositions, 3));
    spiralGeo.setAttribute("color", new THREE.BufferAttribute(spiralColors, 3));
    spiralGeo.setAttribute("size", new THREE.BufferAttribute(spiralSizes, 1));

    const spiralMat = new THREE.PointsMaterial({
      size: 0.22,
      vertexColors: true,
      map: beadTexture,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
    });

    const spiralPoints = new THREE.Points(spiralGeo, spiralMat);
    spiralGroup.add(spiralPoints);

    // ─── 2. Luminous Thin Orbital Rings ───
    const ringGroup = new THREE.Group();
    masterGroup.add(ringGroup);

    const ringMatViolet = new THREE.MeshBasicMaterial({
      color: 0x8b5cf6,
      transparent: true,
      opacity: 0.35,
      wireframe: true,
    });
    const ringMatMagenta = new THREE.MeshBasicMaterial({
      color: 0xec4899,
      transparent: true,
      opacity: 0.25,
      wireframe: true,
    });

    const ringGeo1 = new THREE.TorusGeometry(2.45, 0.008, 12, 128);
    const ring1 = new THREE.Mesh(ringGeo1, ringMatViolet);
    ring1.rotation.x = Math.PI / 3;
    ring1.rotation.y = Math.PI / 6;
    ringGroup.add(ring1);

    const ringGeo2 = new THREE.TorusGeometry(2.75, 0.006, 12, 128);
    const ring2 = new THREE.Mesh(ringGeo2, ringMatMagenta);
    ring2.rotation.x = -Math.PI / 4;
    ring2.rotation.y = Math.PI / 4;
    ringGroup.add(ring2);

    const ringGeo3 = new THREE.TorusGeometry(2.1, 0.005, 8, 96);
    const ring3 = new THREE.Mesh(ringGeo3, ringMatViolet);
    ring3.rotation.z = Math.PI / 5;
    ringGroup.add(ring3);

    // ─── 3. Ambient Star / Intelligence Dust Field ───
    const dustCount = 280;
    const dustPositions = new Float32Array(dustCount * 3);
    const dustColors = new Float32Array(dustCount * 3);

    for (let i = 0; i < dustCount; i++) {
      const radius = 2.2 + Math.random() * 2.8;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      dustPositions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      dustPositions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      dustPositions[i * 3 + 2] = radius * Math.cos(phi);

      const colorPick = Math.random();
      const col =
        colorPick < 0.45 ? colorViolet : colorPick < 0.8 ? colorMagenta : colorGold;
      dustColors[i * 3] = col.r;
      dustColors[i * 3 + 1] = col.g;
      dustColors[i * 3 + 2] = col.b;
    }

    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute("position", new THREE.BufferAttribute(dustPositions, 3));
    dustGeo.setAttribute("color", new THREE.BufferAttribute(dustColors, 3));

    const dustMat = new THREE.PointsMaterial({
      size: 0.045,
      vertexColors: true,
      map: beadTexture,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const dustPoints = new THREE.Points(dustGeo, dustMat);
    masterGroup.add(dustPoints);

    // ─── 4. Central Energy Core Light & Specular Glow ───
    const coreLight1 = new THREE.PointLight(0x8b5cf6, 4, 10);
    coreLight1.position.set(0, 0, 1.2);
    scene.add(coreLight1);

    const coreLight2 = new THREE.PointLight(0xec4899, 3, 10);
    coreLight2.position.set(0, 0, -1.2);
    scene.add(coreLight2);

    // ─── Mouse Interactivity with Spring Lerp ───
    let mouseX = 0;
    let mouseY = 0;
    let targetRotationX = 0;
    let targetRotationY = 0;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const ny = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      mouseX = nx;
      mouseY = ny;
      targetRotationY = nx * 0.45;
      targetRotationX = -ny * 0.35;
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });

    // Handle Resize
    const handleResize = () => {
      if (!container || !renderer) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    // Animation Loop
    let animationFrameId: number;
    let clock = new THREE.Clock();

    setIsLoaded(true);

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Smooth mouse tilt lerp
      masterGroup.rotation.y += (targetRotationY - masterGroup.rotation.y) * 0.05;
      masterGroup.rotation.x += (targetRotationX - masterGroup.rotation.x) * 0.05;

      // Slow orbital rotation of the C-spiral assembly
      spiralGroup.rotation.z = Math.sin(elapsed * 0.25) * 0.08;
      spiralGroup.rotation.y = Math.sin(elapsed * 0.35) * 0.12;

      // Rotate orbital rings at differing speeds
      ring1.rotation.z = elapsed * 0.18;
      ring2.rotation.z = -elapsed * 0.14;
      ring3.rotation.y = elapsed * 0.22;

      // Subtle breathing scale
      const breath = 1 + Math.sin(elapsed * 1.2) * 0.025;
      spiralGroup.scale.set(breath, breath, breath);

      // Slow dust rotation
      dustPoints.rotation.y = elapsed * 0.03;
      dustPoints.rotation.x = elapsed * 0.02;

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      resizeObserver.disconnect();
      cancelAnimationFrame(animationFrameId);

      // Clean up Three.js resources
      spiralGeo.dispose();
      spiralMat.dispose();
      ringGeo1.dispose();
      ringGeo2.dispose();
      ringGeo3.dispose();
      ringMatViolet.dispose();
      ringMatMagenta.dispose();
      dustGeo.dispose();
      dustMat.dispose();
      beadTexture.dispose();
      renderer.dispose();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className={`relative flex items-center justify-center w-full h-full min-h-[420px] lg:min-h-[580px] select-none ${className}`}
    >
      {/* Ambient background glows */}
      <div className="absolute w-[80%] aspect-square rounded-full bg-[#8B5CF6]/14 blur-3xl pointer-events-none" />
      <div className="absolute w-[55%] aspect-square rounded-full bg-[#EC4899]/16 blur-2xl pointer-events-none" />
      <div className="absolute w-[40%] aspect-square rounded-full bg-[#F97316]/10 blur-xl pointer-events-none" />

      {/* 3D WebGL Canvas */}
      {webglSupported ? (
        <canvas
          ref={canvasRef}
          className="relative z-10 w-full h-full max-w-[580px] max-h-[580px] cursor-grab active:cursor-grabbing"
          style={{ opacity: isLoaded ? 1 : 0, transition: "opacity 0.8s ease" }}
        />
      ) : (
        /* Graceful 2D Fallback */
        <div className="relative z-10 w-[240px] h-[240px] flex items-center justify-center drop-shadow-[0_0_60px_rgba(139,92,246,0.45)]">
          <img
            src="/curv-logo.png"
            alt="CURV AI"
            width={240}
            height={240}
            className="object-contain select-none"
            draggable={false}
          />
        </div>
      )}

      {/* Floating AI Activity Cards representing real platform modules */}
      {showCards && (
        <>
          {/* Top-Right: Aria / Marketing */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: [0, -8, 0] }}
            transition={{
              opacity: { duration: 0.8, delay: 0.3 },
              y: { duration: 5.5, repeat: Infinity, ease: "easeInOut" },
            }}
            className="absolute top-[6%] right-[2%] z-20 glass-strong rounded-2xl px-4 py-3 border border-white/[0.08] shadow-3d-lg hidden sm:flex items-center gap-3 backdrop-blur-xl"
          >
            <div className="w-8 h-8 rounded-xl bg-[#8B5CF6]/20 border border-[#8B5CF6]/30 flex items-center justify-center shrink-0">
              <Brain className="w-4 h-4 text-[#A78BFA]" />
            </div>
            <div className="text-left">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-text">Aria · Strategy</span>
                <span className="w-1.5 h-1.5 rounded-full bg-[#34D399] animate-pulse" />
              </div>
              <div className="font-mono text-[10px] text-text-muted mt-0.5">
                7 peak-time posts scheduled · Multi-channel
              </div>
            </div>
          </motion.div>

          {/* Bottom-Left: Kian / Leads */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: [0, 8, 0] }}
            transition={{
              opacity: { duration: 0.8, delay: 0.6 },
              y: { duration: 6, repeat: Infinity, ease: "easeInOut", delay: 1 },
            }}
            className="absolute bottom-[8%] left-[0%] z-20 glass-strong rounded-2xl px-4 py-3 border border-white/[0.08] shadow-3d-lg hidden sm:flex items-center gap-3 backdrop-blur-xl"
          >
            <div className="w-8 h-8 rounded-xl bg-[#34D399]/20 border border-[#34D399]/30 flex items-center justify-center shrink-0">
              <MessageCircle className="w-4 h-4 text-[#34D399]" />
            </div>
            <div className="text-left">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-text">Kian · Lead Recovery</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#34D399]/15 text-[#34D399]">
                  +₹4,200
                </span>
              </div>
              <div className="font-mono text-[10px] text-text-muted mt-0.5">
                4 WhatsApp inquiries recovered · Instant follow-up
              </div>
            </div>
          </motion.div>

          {/* Bottom-Right: Nova / Creative Studio */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1, y: [0, -6, 0] }}
            transition={{
              opacity: { duration: 0.8, delay: 0.9 },
              y: { duration: 4.8, repeat: Infinity, ease: "easeInOut", delay: 0.5 },
            }}
            className="absolute bottom-[9%] right-[1%] z-20 glass-strong rounded-2xl px-3.5 py-2.5 border border-white/[0.08] shadow-3d-lg hidden md:flex items-center gap-2.5 backdrop-blur-xl"
          >
            <div className="w-7 h-7 rounded-lg bg-[#EC4899]/20 border border-[#EC4899]/30 flex items-center justify-center shrink-0">
              <Video className="w-3.5 h-3.5 text-[#F472B6]" />
            </div>
            <div className="text-left">
              <div className="text-[11px] font-semibold text-text">Nova · Wan 3.0</div>
              <div className="font-mono text-[9px] text-text-muted">
                5-slide product carousel + reel rendered
              </div>
            </div>
          </motion.div>
        </>
      )}

      {/* Interaction Hint */}
      <div className="absolute bottom-1 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.06] text-[10px] font-mono text-text-muted pointer-events-none">
        <Sparkles className="w-3 h-3 text-[#A78BFA]" />
        <span>Interactive 3D · Drag to tilt</span>
      </div>
    </div>
  );
}
