declare module "react-simple-maps" {
  import type { ComponentType, ReactNode } from "react";

  export interface ComposableMapProps {
    projection?: unknown;
    projectionConfig?: unknown;
    width?: number;
    height?: number;
    children?: ReactNode;
    className?: string;
    style?: React.CSSProperties;
  }
  export const ComposableMap: ComponentType<ComposableMapProps>;

  export interface GeographyDatum {
    id?: string | number;
    rsmKey: string;
    properties?: Record<string, unknown>;
    [key: string]: unknown;
  }

  export interface GeographiesProps {
    geography?: string | unknown;
    parseGeographies?: (geo: unknown) => unknown;
    children?: (args: {
      geographies: GeographyDatum[];
      outline: unknown;
      borders: unknown;
      path: unknown;
    }) => ReactNode;
  }
  export const Geographies: ComponentType<GeographiesProps>;

  export interface GeographyProps {
    geography?: unknown;
    fill?: string;
    stroke?: string;
    strokeWidth?: number | string;
    style?: Record<string, unknown>;
    onClick?: (geo: unknown) => void;
    className?: string;
  }
  export const Geography: ComponentType<GeographyProps>;

  export interface MarkerProps {
    coordinates?: [number, number];
    children?: ReactNode;
    className?: string;
  }
  export const Marker: ComponentType<MarkerProps>;

  export interface ZoomableGroupProps {
    center?: [number, number];
    zoom?: number;
    minZoom?: number;
    maxZoom?: number;
    translateExtent?: [[number, number], [number, number]];
    children?: ReactNode;
  }
  export const ZoomableGroup: ComponentType<ZoomableGroupProps>;

  export interface SphereProps {
    id?: string;
    fill?: string;
    stroke?: string;
    strokeWidth?: number | string;
  }
  export const Sphere: ComponentType<SphereProps>;

  export interface GraticuleProps {
    id?: string;
    fill?: string;
    stroke?: string;
    strokeWidth?: number | string;
    step?: [number, number];
  }
  export const Graticule: ComponentType<GraticuleProps>;
}
