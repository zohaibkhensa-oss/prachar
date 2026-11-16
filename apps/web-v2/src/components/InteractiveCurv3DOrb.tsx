"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { motion } from "framer-motion";
import { Brain, Sparkles, MessageCircle, Video, CheckCircle2 } from "lucide-react";

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

    const width = container.clientWidth || 600;
    const height = container.clientHeight || 600;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
    camera.position.set(0, 0, 7.8);

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

    const masterGroup = new THREE.Group();
    scene.add(masterGroup);

    // ─── 1. Brand Color Gradients ───
    const colorViolet = new THREE.Color(0x8b5cf6);
    const colorPurple = new THREE.Color(0x7c3aed);
    const colorMagenta = new THREE.Color(0xec4899);
    const colorCoral = new THREE.Color(0xf97316);
    const colorGold = new THREE.Color(0xfbbf24);

    function getCurvColor(t: number): THREE.Color {
      if (t < 0.28) {
        return colorViolet.clone().lerp(colorPurple, t / 0.28);
      } else if (t < 0.58) {
        return colorPurple.clone().lerp(colorMagenta, (t - 0.28) / 0.3);
      } else if (t < 0.82) {
        return colorMagenta.clone().lerp(colorCoral, (t - 0.58) / 0.24);
      } else {
        return colorCoral.clone().lerp(colorGold, (t - 0.82) / 0.18);
      }
    }

    // ─── 2. High-Fidelity Glow Bead Texture ───
    const beadTexture = (() => {
      const cv = document.createElement("canvas");
      cv.width = 128;
      cv.height = 128;
      const ctx = cv.getContext("2d");
      if (ctx) {
        const rad = 64;
        const grad = ctx.createRadialGradient(rad, rad, 0, rad, rad, rad);
        grad.addColorStop(0, "rgba(255, 255, 255, 1)");
        grad.addColorStop(0.18, "rgba(255, 255, 255, 0.95)");
        grad.addColorStop(0.42, "rgba(240, 215, 255, 0.85)");
        grad.addColorStop(0.68, "rgba(180, 120, 255, 0.45)");
        grad.addColorStop(0.88, "rgba(139, 92, 246, 0.15)");
        grad.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 128, 128);
      }
      return new THREE.CanvasTexture(cv);
    })();

    // ─── 3. Concentric C-Spiral Bead Assembly (Dense & Radiant) ───
    const spiralGroup = new THREE.Group();
    masterGroup.add(spiralGroup);

    const layers = 10;
    const pointsPerLayer = 260;
    const totalSpiralPoints = layers * pointsPerLayer;
    const spiralPositions = new Float32Array(totalSpiralPoints * 3);
    const spiralColors = new Float32Array(totalSpiralPoints * 3);
    const spiralSizes = new Float32Array(totalSpiralPoints);

    let idx = 0;
    for (let l = 0; l < layers; l++) {
      const layerFrac = l / (layers - 1);
      const baseRadius = 1.05 + layerFrac * 1.15;
      const zOffset = (layerFrac - 0.5) * 0.65;

      for (let p = 0; p < pointsPerLayer; p++) {
        const pFrac = p / pointsPerLayer;
        const angle = -0.28 + pFrac * Math.PI * 1.78;

        const r = baseRadius * (0.84 + pFrac * 0.32);
        const x = Math.cos(angle) * r;
        const y = Math.sin(angle) * r;
        const z = zOffset + Math.sin(pFrac * Math.PI * 2) * 0.38;

        spiralPositions[idx * 3] = x;
        spiralPositions[idx * 3 + 1] = y;
        spiralPositions[idx * 3 + 2] = z;

        const c = getCurvColor(pFrac);
        c.offsetHSL(0, 0.08, 0.15);

        spiralColors[idx * 3] = c.r;
        spiralColors[idx * 3 + 1] = c.g;
        spiralColors[idx * 3 + 2] = c.b;

        const sizeMod = Math.sin(pFrac * Math.PI) * 0.45 + 0.55;
        spiralSizes[idx] = (24 + (1 - layerFrac) * 16) * sizeMod + 16;

        idx++;
      }
    }

    const spiralGeo = new THREE.BufferGeometry();
    spiralGeo.setAttribute("position", new THREE.BufferAttribute(spiralPositions, 3));
    spiralGeo.setAttribute("color", new THREE.BufferAttribute(spiralColors, 3));
    spiralGeo.setAttribute("size", new THREE.BufferAttribute(spiralSizes, 1));

    const spiralMat = new THREE.PointsMaterial({
      size: 0.24,
      vertexColors: true,
      map: beadTexture,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
    });

    const spiralPoints = new THREE.Points(spiralGeo, spiralMat);
    spiralGroup.add(spiralPoints);

    // ─── 4. Ethereal Central Energy Core Sphere ───
    const coreGeo = new THREE.SphereGeometry(0.85, 32, 32);
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0x8b5cf6,
      transparent: true,
      opacity: 0.08,
      wireframe: true,
    });
    const coreSphere = new THREE.Mesh(coreGeo, coreMat);
    masterGroup.add(coreSphere);

    // ─── 5. Luminous Concentric Orbital Rings ───
    const ringGroup = new THREE.Group();
    masterGroup.add(ringGroup);

    const ringMatViolet = new THREE.MeshBasicMaterial({
      color: 0x8b5cf6,
      transparent: true,
      opacity: 0.4,
      wireframe: true,
    });
    const ringMatMagenta = new THREE.MeshBasicMaterial({
      color: 0xec4899,
      transparent: true,
      opacity: 0.3,
      wireframe: true,
    });
    const ringMatCyan = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.25,
      wireframe: true,
    });

    const ring1 = new THREE.Mesh(new THREE.TorusGeometry(2.65, 0.008, 12, 128), ringMatViolet);
    ring1.rotation.x = Math.PI / 3;
    ring1.rotation.y = Math.PI / 6;
    ringGroup.add(ring1);

    const ring2 = new THREE.Mesh(new THREE.TorusGeometry(3.05, 0.006, 12, 128), ringMatMagenta);
    ring2.rotation.x = -Math.PI / 4;
    ring2.rotation.y = Math.PI / 4;
    ringGroup.add(ring2);

    const ring3 = new THREE.Mesh(new THREE.TorusGeometry(2.25, 0.005, 8, 96), ringMatCyan);
    ring3.rotation.z = Math.PI / 5;
    ringGroup.add(ring3);

    // Traveling photons along orbital ring paths
    const photonGeo = new THREE.SphereGeometry(0.045, 12, 12);
    const photonMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const photon1 = new THREE.Mesh(photonGeo, photonMat);
    const photon2 = new THREE.Mesh(photonGeo, photonMat);
    ring1.add(photon1);
    ring2.add(photon2);

    // ─── 6. Intelligence Dust Starfield ───
    const dustCount = 340;
    const dustPositions = new Float32Array(dustCount * 3);
    const dustColors = new Float32Array(dustCount * 3);

    for (let i = 0; i < dustCount; i++) {
      const radius = 2.4 + Math.random() * 3.2;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      dustPositions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      dustPositions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      dustPositions[i * 3 + 2] = radius * Math.cos(phi);

      const colorPick = Math.random();
      const col =
        colorPick < 0.4 ? colorViolet : colorPick < 0.75 ? colorMagenta : colorCoral;
      dustColors[i * 3] = col.r;
      dustColors[i * 3 + 1] = col.g;
      dustColors[i * 3 + 2] = col.b;
    }

    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute("position", new THREE.BufferAttribute(dustPositions, 3));
    dustGeo.setAttribute("color", new THREE.BufferAttribute(dustColors, 3));

    const dustMat = new THREE.PointsMaterial({
      size: 0.05,
      vertexColors: true,
      map: beadTexture,
      transparent: true,
      opacity: 0.7,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const dustPoints = new THREE.Points(dustGeo, dustMat);
    masterGroup.add(dustPoints);

    // ─── 7. Lights & Interactivity ───
    const light1 = new THREE.PointLight(0x8b5cf6, 4.5, 12);
    light1.position.set(1.5, 1.5, 2);
    scene.add(light1);

    const light2 = new THREE.PointLight(0xec4899, 3.5, 12);
    light2.position.set(-1.5, -1.5, -1);
    scene.add(light2);

    let targetRotY = 0;
    let targetRotX = 0;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const ny = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      targetRotY = nx * 0.55;
      targetRotX = -ny * 0.45;
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });

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

    let animationFrameId: number;
    const clock = new THREE.Clock();
    setIsLoaded(true);

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Smooth mouse lerp
      masterGroup.rotation.y += (targetRotY - masterGroup.rotation.y) * 0.06;
      masterGroup.rotation.x += (targetRotX - masterGroup.rotation.x) * 0.06;

      // Slow orbital motion
      spiralGroup.rotation.z = Math.sin(elapsed * 0.28) * 0.09;
      spiralGroup.rotation.y = Math.sin(elapsed * 0.38) * 0.14;

      // Orbital rings rotation
      ring1.rotation.z = elapsed * 0.2;
      ring2.rotation.z = -elapsed * 0.16;
      ring3.rotation.y = elapsed * 0.24;

      // Photon motion
      const photonAngle1 = elapsed * 1.5;
      photon1.position.set(Math.cos(photonAngle1) * 2.65, Math.sin(photonAngle1) * 2.65, 0);
      const photonAngle2 = -elapsed * 1.2;
      photon2.position.set(Math.cos(photonAngle2) * 3.05, Math.sin(photonAngle2) * 3.05, 0);

      // Core pulse
      const coreBreath = 1 + Math.sin(elapsed * 1.4) * 0.04;
      coreSphere.scale.set(coreBreath, coreBreath, coreBreath);

      // Dust drift
      dustPoints.rotation.y = elapsed * 0.035;
      dustPoints.rotation.x = elapsed * 0.02;

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      resizeObserver.disconnect();
      cancelAnimationFrame(animationFrameId);

      spiralGeo.dispose();
      spiralMat.dispose();
      ring1.geometry.dispose();
      ring2.geometry.dispose();
      ring3.geometry.dispose();
      ringMatViolet.dispose();
      ringMatMagenta.dispose();
      ringMatCyan.dispose();
      dustGeo.dispose();
      dustMat.dispose();
      coreGeo.dispose();
      coreMat.dispose();
      photonGeo.dispose();
      photonMat.dispose();
      beadTexture.dispose();
      renderer.dispose();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className={`relative flex items-center justify-center w-full h-full min-h-[460px] lg:min-h-[620px] select-none ${className}`}
    >
      {/* Cinematic background atmospheric glow */}
      <div className="absolute w-[85%] aspect-square rounded-full bg-[#8B5CF6]/18 blur-[120px] pointer-events-none" />
      <div className="absolute w-[60%] aspect-square rounded-full bg-[#EC4899]/18 blur-[100px] pointer-events-none" />
      <div className="absolute w-[45%] aspect-square rounded-full bg-[#F97316]/12 blur-[80px] pointer-events-none" />

      {/* 3D WebGL Canvas */}
      {webglSupported ? (
        <canvas
          ref={canvasRef}
          className="relative z-10 w-full h-full max-w-[620px] max-h-[620px] cursor-grab active:cursor-grabbing"
          style={{ opacity: isLoaded ? 1 : 0, transition: "opacity 0.8s ease" }}
        />
      ) : (
        <div className="relative z-10 w-[280px] h-[280px] flex items-center justify-center drop-shadow-[0_0_80px_rgba(139,92,246,0.5)]">
          <img
            src="/curv-logo.png"
            alt="CURV AI"
            width={280}
            height={280}
            className="object-contain select-none"
            draggable={false}
          />
        </div>
      )}

      {/* Floating Glass AI Teammate Telemetry Cards */}
      {showCards && (
        <>
          {/* Top-Right: Aria */}
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: [0, -8, 0] }}
            transition={{
              opacity: { duration: 0.8, delay: 0.3 },
              y: { duration: 5.5, repeat: Infinity, ease: "easeInOut" },
            }}
            className="absolute top-[6%] right-[2%] z-20 glass-strong rounded-2xl px-4 py-3 border border-white/[0.1] shadow-3d-xl hidden sm:flex items-center gap-3 backdrop-blur-2xl"
          >
            <div className="w-9 h-9 rounded-xl bg-[#8B5CF6]/20 border border-[#8B5CF6]/30 flex items-center justify-center shrink-0 shadow-[0_0_15px_rgba(139,92,246,0.3)]">
              <Brain className="w-4 h-4 text-[#C4B5FD]" />
            </div>
            <div className="text-left">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-text tracking-tight">Aria · Strategy</span>
                <span className="flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-[#34D399] bg-[#34D399]/10 px-1.5 py-0.5 rounded">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#34D399] animate-pulse" /> Live
                </span>
              </div>
              <div className="font-mono text-[10px] text-text-muted mt-0.5">
                7 peak-time posts scheduled · Meta & YouTube
              </div>
            </div>
          </motion.div>

          {/* Mid-Left: Kian */}
          <motion.div
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, y: [0, 8, 0] }}
            transition={{
              opacity: { duration: 0.8, delay: 0.6 },
              y: { duration: 6, repeat: Infinity, ease: "easeInOut", delay: 1 },
            }}
            className="absolute top-[48%] left-[-4%] z-20 glass-strong rounded-2xl px-4 py-3 border border-white/[0.1] shadow-3d-xl hidden sm:flex items-center gap-3 backdrop-blur-2xl"
          >
            <div className="w-9 h-9 rounded-xl bg-[#34D399]/20 border border-[#34D399]/30 flex items-center justify-center shrink-0 shadow-[0_0_15px_rgba(52,211,153,0.3)]">
              <MessageCircle className="w-4 h-4 text-[#34D399]" />
            </div>
            <div className="text-left">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-text tracking-tight">Kian · Lead Recovery</span>
                <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#34D399]/15 text-[#34D399]">
                  +₹4,200 Close
                </span>
              </div>
              <div className="font-mono text-[10px] text-text-muted mt-0.5">
                4 WhatsApp inquiries recovered · 48s draft speed
              </div>
            </div>
          </motion.div>

          {/* Bottom-Right: Nova */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1, y: [0, -6, 0] }}
            transition={{
              opacity: { duration: 0.8, delay: 0.9 },
              y: { duration: 4.8, repeat: Infinity, ease: "easeInOut", delay: 0.5 },
            }}
            className="absolute bottom-[8%] right-[2%] z-20 glass-strong rounded-2xl px-4 py-3 border border-white/[0.1] shadow-3d-xl hidden md:flex items-center gap-3 backdrop-blur-2xl"
          >
            <div className="w-9 h-9 rounded-xl bg-[#EC4899]/20 border border-[#EC4899]/30 flex items-center justify-center shrink-0 shadow-[0_0_15px_rgba(236,72,153,0.3)]">
              <Video className="w-4 h-4 text-[#F472B6]" />
            </div>
            <div className="text-left">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-text tracking-tight">Nova · Wan 3.0 Studio</span>
                <span className="font-mono text-[9px] uppercase px-1.5 py-0.5 rounded bg-[#EC4899]/15 text-[#F472B6]">
                  1080p
                </span>
              </div>
              <div className="font-mono text-[10px] text-text-muted mt-0.5">
                5-slide product carousel + vertical reel rendered
              </div>
            </div>
          </motion.div>
        </>
      )}

      {/* Floating 3D Interaction Badge */}
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 px-3 py-1 rounded-full bg-bg-card/90 border border-white/[0.1] text-[10px] font-mono text-text-secondary backdrop-blur-md pointer-events-none shadow-3d">
        <Sparkles className="w-3 h-3 text-[#A78BFA] animate-pulse" />
        <span>Genuinely Interactive 3D · Drag to tilt & explore</span>
      </div>
    </div>
  );
}
