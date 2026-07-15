"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Connection } from "@/lib/schemas";

const REGIONS: { name: string; channels: string[] }[] = [
  { name: "Americas", channels: ["google", "youtube", "instagram", "facebook", "x", "linkedin", "pinterest", "snap", "reddit", "amazon"] },
  { name: "Europe", channels: ["google", "youtube", "instagram", "facebook", "x", "linkedin", "pinterest", "tiktok"] },
  { name: "India", channels: ["google", "youtube", "instagram", "facebook", "whatsapp", "telegram", "amazon"] },
  { name: "SEA", channels: ["google", "youtube", "instagram", "tiktok", "facebook", "whatsapp", "telegram", "line"] },
  { name: "MENA", channels: ["google", "youtube", "instagram", "tiktok", "snap", "whatsapp", "telegram"] },
  { name: "East Asia", channels: ["google", "youtube", "instagram", "tiktok", "line", "kakao", "naver"] },
  { name: "CIS", channels: ["vk", "telegram", "yandex", "youtube"] },
];

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function ConnectionsPage() {
  const { data: connections, isLoading } = useQuery<Connection[]>({
    queryKey: ["connections"],
    queryFn: () => apiGet<Connection[]>("/connections"),
    retry: 0,
  });

  const connected = new Map(connections?.map((c) => [c.channel, c]) ?? []);

  return (
    <div className="p-8">
      <h1 className="font-display uppercase text-4xl tracking-wide mb-8">Connections</h1>
      {isLoading ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="space-y-8">
          {REGIONS.map((region) => (
            <div key={region.name}>
              <h2 className="font-display uppercase text-2xl tracking-wide mb-4">
                {region.name}
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {region.channels.map((ch) => {
                  const conn = connected.get(ch);
                  const isOn = conn?.status === "connected";
                  return (
                    <Card key={ch}>
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-display uppercase text-lg tracking-wide">
                          {ch}
                        </span>
                        <Badge variant={isOn ? "yellow" : "paper"}>
                          {isOn ? "connected" : "off"}
                        </Badge>
                      </div>
                      <Button
                        variant={isOn ? "paper" : "yellow"}
                        size="sm"
                        className="w-full"
                        onClick={() => {
                          window.location.href = `${BASE}/connections/${ch}/oauth`;
                        }}
                      >
                        {isOn ? "Reconnect" : "Connect →"}
                      </Button>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
