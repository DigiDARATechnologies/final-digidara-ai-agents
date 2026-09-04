// src/components/ResumeDocument.jsx
import React from "react";
import { TEMPLATE_REGISTRY } from "./templates/templateRegistry.js";

export default function ResumeDocument({ resumeData, templateId }) {
  const Template = TEMPLATE_REGISTRY[templateId] || TEMPLATE_REGISTRY["steady-form"];
  return <Template resume={resumeData} />;
}
