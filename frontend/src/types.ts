export type Aspect = "9:16" | "16:9";

export interface ProjectMeta {
  id: string;
  name: string;
  aspect: Aspect;
  created_at: number;
  updated_at: number;
  status?: string;
}

export interface Candidate {
  source: string;
  kind: "image" | "video";
  id: string;
  thumb: string | null;
  url: string;
  width?: number;
  height?: number;
  duration?: number;
  author?: string | null;
  page?: string | null;
}

export interface ClipMedia {
  file: string;
  kind: "image" | "video";
  source: string;
  id?: string | null;
  thumb?: string | null;
  author?: string | null;
  page?: string | null;
  duration?: number;
  has_audio?: boolean;
}

export interface Clip {
  id: string;
  shot_id: string | null;
  kind: "image" | "video";
  description: string;
  query: string;
  start: number;
  end: number;
  motion: "zoom_in" | "none" | null;
  volume: number;
  fit: "cover" | "contain";
  estimated: boolean; // الفقرة بتاعتها ماتلقتش في التسجيل، فوقتها متقدّر
  page: number | null; // صورة صفحة اللوحة رقم N
  media: ClipMedia | null;
  candidates: Candidate[];
}

export interface Cut {
  id: string;
  start: number;
  end: number;
  auto?: "silence" | "retake" | null;
}

export interface Caption {
  id: string;
  start: number;
  end: number;
  text: string;
}

export interface CaptionStyle {
  enabled: boolean;
  font: string;
  size: number;
  color: string;
  box: boolean;
  box_color: string;
  position: "bottom" | "middle" | "top";
}

export interface Marker {
  paragraph_id: string;
  start: number;
  end: number;
  estimated: boolean;
}

export interface Timeline {
  version: number;
  aspect: Aspect;
  duration: number;
  base: { file: string; preview: string; has_video: boolean; volume: number; clean_audio: boolean };
  cuts: Cut[];
  clips: Clip[];
  markers: Marker[];
  captions: Caption[];
  caption_style: CaptionStyle;
  brand: { logo: boolean; title: boolean };
}

export interface Script {
  title: string;
  sections: { id: string; title: string; page: number | null; level: number }[];
  paragraphs: { id: string; section_id: string; text: string }[];
  shots: { id: string; section_id: string; kind: string; description: string; paragraph_id: string | null }[];
  cues: { id: string; section_id: string; kind: string; text: string; paragraph_id: string | null }[];
}

export interface Job {
  id: string;
  project_id: string;
  kind: "process" | "export" | "fetch" | "generate";
  status: "running" | "done" | "error";
  progress: number;
  message: string;
  error: string | null;
  result: any;
}

export interface ProjectData {
  meta: ProjectMeta;
  script_text: string;
  script: Script | null;
  recording: { duration: number; has_video: boolean; file: string; preview: string; width: number | null; height: number | null } | null;
  has_transcript: boolean;
  alignment: { paragraph_id: string; start: number; end: number; estimated: boolean; ratio: number }[] | null;
  timeline: Timeline | null;
  pages: Record<string, string>; // رقم الصفحة ← اسم الملف في media/
  exports: string[];
  jobs: Job[];
}

export interface Brand {
  primary_color: string;
  accent_color: string;
  text_color: string;
  font: string;
  logo_position: "top-right" | "top-left" | "bottom-right" | "bottom-left";
  logo_size: number;
  logo_opacity: number;
}

export interface Settings {
  pixabay_api_key: string;
  pexels_api_key: string;
  anthropic_api_key: string;
  openai_api_key: string;
  openai_image_model: string;
  has_pixabay_api_key: boolean;
  has_pexels_api_key: boolean;
  has_anthropic_api_key: boolean;
  has_openai_api_key: boolean;
  brand: Brand;
  has_logo: boolean;
  fonts: string[];
  projects_dir: string;
  whisper_model: string;
  whisper_device: string;
  default_aspect: Aspect;
  ffmpeg_ok: boolean;
}
