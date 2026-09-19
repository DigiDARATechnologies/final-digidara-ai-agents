import {
  AlertTriangle,
  ArrowLeft,
  Award,
  Bot,
  BookOpen,
  Boxes,
  BrainCircuit,
  Briefcase,
  Camera,
  ChartNoAxesCombined,
  Check,
  CircleAlert,
  CircleX,
  CheckCircle2,
  Cloud,
  DatabaseZap,
  Edit3,
  FileText,
  Gauge,
  GitBranch,
  History,
  Layers,
  LayoutGrid,
  ListChecks,
  Mail,
  Megaphone,
  Menu,
  MessageCircle,
  Mic,
  Network,
  Phone,
  Plus,
  Rocket,
  Save,
  Search,
  Share2,
  Sparkles,
  Sprout,
  Star,
  Terminal,
  Trash2,
  User,
  Workflow,
  X,
  Zap,
} from "lucide-react";
import {
  SiFastapi,
  SiFlask,
  SiJavascript,
  SiLangchain,
  SiMongodb,
  SiMysql,
  SiPython,
  SiReact,
  SiScikitlearn,
} from "react-icons/si";

export const NAV_ICONS = {
  dashboard: LayoutGrid,
  setup: Plus,
  history: History,
  profile: User,
};

export const ROUND_TYPE_ICONS = {
  technical: Terminal,
  hr: MessageCircle,
};

export const STAT_ICONS = {
  totalInterviews: Layers,
  averageScore: Star,
  technicalRounds: Terminal,
  hrRounds: MessageCircle,
  warning: AlertTriangle,
  correct: CheckCircle2,
};

export const PROFILE_FIELD_ICONS = {
  email: Mail,
  phone: Phone,
  course_enrolled: BookOpen,
  target_role: Briefcase,
};

export const ACTION_ICONS = {
  edit: Edit3,
  save: Save,
  cancel: X,
  achievement: Award,
  camera: Camera,
  remove: Trash2,
};

export const APP_ICONS = {
  brand: Sparkles,
  menu: Menu,
  start: Rocket,
  questions: ListChecks,
  back: ArrowLeft,
  close: X,
  selected: Check,
};

export const DIFFICULTY_ICONS = {
  Beginner: Sprout,
  Intermediate: Gauge,
  Advanced: Zap,
};

export const SUBJECT_ICONS = {
  Python: { icon: SiPython, color: "#3776AB" },
  MySQL: { icon: SiMysql, color: "#4479A1" },
  JavaScript: { icon: SiJavascript, color: "#EAB308" },
  React: { icon: SiReact, color: "#0EA5E9" },
  Flask: { icon: SiFlask, color: "#334155" },
  "Data Science": { icon: ChartNoAxesCombined, color: "#8B5CF6" },
  "Power BI": { icon: ChartNoAxesCombined, color: "#D97706" },
  MongoDB: { icon: SiMongodb, color: "#47A248" },
  "Machine Learning": { icon: SiScikitlearn, color: "#F97316" },
  "AI & ML": { icon: BrainCircuit, color: "#7C3AED" },
  "Generative AI": { icon: Sparkles, color: "#DB2777" },
  "LangChain & LangGraph": { icon: SiLangchain, color: "#0F766E" },
  "RAG & Vector Databases": { icon: DatabaseZap, color: "#2563EB" },
  FastAPI: { icon: SiFastapi, color: "#009688" },
  "AI Agent Development": { icon: Bot, color: "#4F46E5" },
  SEO: { icon: Search, color: "#F43F5E" },
  "SEM & Google Ads": { icon: Megaphone, color: "#EA580C" },
  "Social Media Marketing": { icon: Share2, color: "#DB2777" },
  "Content Marketing": { icon: FileText, color: "#0891B2" },
  "Email Marketing": { icon: Mail, color: "#65A30D" },
  MLOps: { icon: Workflow, color: "#6366F1" },
  "Docker & Kubernetes": { icon: Boxes, color: "#2563EB" },
  "CI/CD Pipelines": { icon: GitBranch, color: "#059669" },
  "Cloud Platforms": { icon: Cloud, color: "#0EA5E9" },
  "System Design": { icon: Network, color: "#7C3AED" },
  fallback: { icon: Workflow, color: "#64748B" },
};

export const INTERVIEW_ICONS = {
  interviewer: Bot,
  microphone: Mic,
};

export const VERDICT_ICONS = {
  correct: CheckCircle2,
  partial: CircleAlert,
  wrong: CircleX,
};
