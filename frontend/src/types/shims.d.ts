// Type shims for libraries that ship without typings.

declare module "react-cytoscapejs" {
  import type {
    Core,
    ElementDefinition,
    Stylesheet,
    LayoutOptions,
  } from "cytoscape";
  import type { ComponentType, CSSProperties } from "react";

  interface CytoscapeComponentProps {
    elements: ElementDefinition[];
    style?: CSSProperties;
    stylesheet?: Stylesheet[];
    layout?: LayoutOptions | Record<string, unknown>;
    cy?: (cy: Core) => void;
    className?: string;
    wheelSensitivity?: number;
    minZoom?: number;
    maxZoom?: number;
  }

  const CytoscapeComponent: ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}
