"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { getToken } from "@/lib/auth";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { AIDock } from "@/components/AIDock";
import { OrbPanel } from "@/components/OrbPanel";
import { ProactiveNotifications } from "@/components/ProactiveNotifications";
import { CommandPalette } from "@/components/ui/command-palette";
import { getPracharMessages } from "@/lib/proactive";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifCount, setNotifCount] = useState(0);
  const [orbOpen, setOrbOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeBrandId, setActiveBrandId] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    const storedEmail = localStorage.getItem("prachar_email");
    if (storedEmail) setEmail(storedEmail);

    const onboarded = localStorage.getItem("prachar_onboarded");
    if (onboarded) {
      // Already onboarded — load brand ID and proceed
      const storedBrandId = localStorage.getItem("prachar_active_brand_id");
      if (storedBrandId) setActiveBrandId(storedBrandId);
      setReady(true);
      return;
    }

    // Not marked as onboarded in localStorage — check backend for brands
    // (returning users may have brands but lost the localStorage flag)
    (async () => {
      try {
        const { apiGet } = await import("@/lib/api");
        const res = await apiGet<{ id: string }[] | { items: { id: string }[] }>("/brands?limit=1");
        const brands = Array.isArray(res) ? res : res.items;
        if (brands && brands.length > 0) {
          // User has brands — skip onboarding, mark as onboarded
          localStorage.setItem("prachar_onboarded", "1");
          const id = brands[0]?.id;
          if (id) {
            setActiveBrandId(id);
            localStorage.setItem("prachar_active_brand_id", id);
          }
          setReady(true);
        } else {
          // No brands — go to onboarding
          router.replace("/onboarding");
        }
      } catch {
        // API error — let them in anyway, onboarding is optional
        localStorage.setItem("prachar_onboarded", "1");
        setReady(true);
      }
    })();
  }, [router]);

  // Fetch active brand if not in localStorage
  useEffect(() => {
    if (!ready || activeBrandId) return;
    const fetchBrands = async () => {
      try {
        const { apiGet } = await import("@/lib/api");
        const res = await apiGet<{ id: string }[] | { items: { id: string }[] }>("/brands?limit=1");
        // API returns a plain array, but handle both shapes
        const brands = Array.isArray(res) ? res : res.items;
        if (brands && brands.length > 0) {
          const id = brands[0]?.id;
          if (id) {
            setActiveBrandId(id);
            localStorage.setItem("prachar_active_brand_id", id);
          }
        }
      } catch {
        // Silent fail — orb will work without brand for general chat
      }
    };
    fetchBrands();
  }, [ready, activeBrandId]);

  // Fetch proactive notification count
  useEffect(() => {
    if (!ready) return;
    let active = true;
    const fetchNotifs = async () => {
      try {
        const res = await getPracharMessages();
        if (active && res.messages) {
          setNotifCount(res.messages.length);
        }
      } catch {
        // Silent fail
      }
    };
    fetchNotifs();
    const interval = setInterval(fetchNotifs, 30000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [ready]);

  const handleOrbClick = useCallback(() => {
    setOrbOpen((prev) => !prev);
  }, []);

  // Memoize sidebar callbacks so the Sidebar's pathname effect doesn't
  // fire on every render (which would immediately close the mobile drawer).
  const handleMobileClose = useCallback(() => setSidebarOpen(false), []);

  // Listen for orb open events from other pages (NOT the home page, which
  // uses inline conversation). Other pages can still dispatch this event to
  // open the floating orb panel.
  useEffect(() => {
    const handler = () => setOrbOpen(true);
    window.addEventListener("prachar-open-orb", handler);
    return () => window.removeEventListener("prachar-open-orb", handler);
  }, []);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
          className="w-8 h-8 rounded-full border-2 border-accent/20 border-t-accent"
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg flex overflow-x-hidden">
      <CommandPalette />
      <ProactiveNotifications open={notifOpen} onClose={() => setNotifOpen(false)} />

      {/* Sidebar */}
      <Sidebar mobileOpen={sidebarOpen} onMobileClose={handleMobileClose} />

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen pb-16 relative">
        <TopBar
          onSearchClick={() => {
            const event = new KeyboardEvent("keydown", { key: "k", metaKey: true });
            document.dispatchEvent(event);
          }}
          onNotificationsClick={() => setNotifOpen(true)}
          onMenuClick={() => setSidebarOpen(true)}
          notifCount={notifCount}
          email={email}
        />

        <main className="flex-1 p-4 lg:p-6">
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          >
            {children}
          </motion.div>
        </main>

        {/* Bottom AI Dock — inside main content so it respects sidebar width */}
        <AIDock onOrbClick={handleOrbClick} />
      </div>

      {/* Floating AI Orb Panel — real runtime integration */}
      <AnimatePresence>
        {orbOpen && (
          <OrbPanel brandId={activeBrandId} onClose={() => setOrbOpen(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}
