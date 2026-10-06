"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * The dedicated /app/chat route was superseded by the Orb panel mounted in
 * the app layout — redirect so stale links/bookmarks don't 404.
 */
export default function ChatRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/app");
  }, [router]);
  return null;
}
