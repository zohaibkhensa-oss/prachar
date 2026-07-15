"use client";

import { ComposableMap, Geographies, Geography } from "react-simple-maps";

const TOPO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

const REGION_COUNTRIES: Record<string, number[]> = {
  Americas: [840, 124, 76, 32, 484, 170, 604, 862],
  Europe: [276, 250, 826, 380, 752, 578, 246, 616],
  India: [356],
  SEA: [360, 764, 458, 702, 104, 418, 410],
  MENA: [792, 682, 12, 422, 512, 748, 887],
  "East Asia": [392, 410, 158, 344, 446],
  CIS: [643, 804, 112, 51, 31, 268],
};

const ACTIVE_IDS = new Set<number>();
function refreshActive(regions: string[]) {
  ACTIVE_IDS.clear();
  for (const r of regions) {
    for (const id of REGION_COUNTRIES[r] ?? []) ACTIVE_IDS.add(id);
  }
}

export function WorldMap({ activeRegions }: { activeRegions: string[] }) {
  refreshActive(activeRegions);
  return (
    <div className="border-3 border-ink bg-ink p-0 overflow-hidden">
      <ComposableMap
        projection="geoEqualEarth"
        projectionConfig={{ scale: 160, center: [0, 0] }}
        width={800}
        height={380}
        style={{ width: "100%", height: "auto", display: "block", backgroundColor: "#141414" }}
      >
        <Geographies geography={TOPO_URL}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const id = Number(geo.id);
              const active = ACTIVE_IDS.has(id);
              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill={active ? "#FFD400" : "#141414"}
                  stroke="#F7F7F4"
                  strokeWidth={0.4}
                  style={
                    active
                      ? {
                          default: { animation: "pulse-yellow 1.6s ease-in-out infinite" },
                          hover: { fill: "#E6C000" },
                          pressed: { fill: "#E6C000" },
                        }
                      : {
                          default: { fill: "#141414" },
                          hover: { fill: "#2a2a2a" },
                          pressed: { fill: "#2a2a2a" },
                        }
                  }
                />
              );
            })
          }
        </Geographies>
      </ComposableMap>
    </div>
  );
}
