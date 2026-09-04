// src/components/templates/templateRegistry.js
import { createElement } from "react";
import ClassicClearTemplate from "./ClassicClearTemplate.jsx";
import ExecutiveSidebarTemplate from "./ExecutiveSidebarTemplate.jsx";
import SteadyFormTemplate from "./SteadyFormTemplate.jsx";
import TraditionalProfessionalTemplate from "./TraditionalProfessionalTemplate.jsx";
import TimelineTealTemplate from "./TimelineTealTemplate.jsx";
import SidebarMonoTemplate from "./SidebarMonoTemplate.jsx";
import HorizonCoralTemplate from "./HorizonCoralTemplate.jsx";
import LedgerNavyTemplate from "./LedgerNavyTemplate.jsx";
import SplitOliveTemplate from "./SplitOliveTemplate.jsx";
import CanvasSandTemplate from "./CanvasSandTemplate.jsx";
import ColumnIndigoTemplate from "./ColumnIndigoTemplate.jsx";
import ArcSlateTemplate from "./ArcSlateTemplate.jsx";
import PulseRoseTemplate from "./PulseRoseTemplate.jsx";
import SignalAmberTemplate from "./SignalAmberTemplate.jsx";
import NavyPortraitTemplate from "./NavyPortraitTemplate.jsx";
import AtsStandardTemplate from "./AtsStandardTemplate.jsx";
import ModernResumeTemplate from "./ModernResumeTemplate.jsx";

const MinimalistLineTemplate = ({ resume }) => createElement(ModernResumeTemplate, { resume, variant: "minimalist-line" });
const SidebarFocusTemplate = ({ resume }) => createElement(ModernResumeTemplate, { resume, twoColumn: true, variant: "sidebar-focus" });
const CompactImpactTemplate = ({ resume }) => createElement(ModernResumeTemplate, { resume, variant: "compact-impact" });
const StudioBoldTemplate = ({ resume }) => createElement(ModernResumeTemplate, { resume, variant: "studio-bold" });

export const TEMPLATE_REGISTRY = {
  "classic-serif": TraditionalProfessionalTemplate,
  "mercury-flow": ClassicClearTemplate,
  "slate-dawn": ExecutiveSidebarTemplate,
  "steady-form": SteadyFormTemplate,
  "minimalist-line": MinimalistLineTemplate,
  "sidebar-focus": SidebarFocusTemplate,
  "compact-impact": CompactImpactTemplate,
  "studio-bold": StudioBoldTemplate,
  "timeline-teal": TimelineTealTemplate,
  "sidebar-mono": SidebarMonoTemplate,
  "horizon-coral": HorizonCoralTemplate,
  "ledger-navy": LedgerNavyTemplate,
  "split-olive": SplitOliveTemplate,
  "canvas-sand": CanvasSandTemplate,
  "column-indigo": ColumnIndigoTemplate,
  "arc-slate": ArcSlateTemplate,
  "pulse-rose": PulseRoseTemplate,
  "signal-amber": SignalAmberTemplate,
  "navy-portrait": NavyPortraitTemplate,
  "ats-standard": AtsStandardTemplate,
};
