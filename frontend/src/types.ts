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
  media: ClipMedia | null;
  candidates: Candidate[];
}

export interface Cut {
  id: string;
  start: number;
  end: number;
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
  base: { file: string; preview: string; has_video: boolean; volume: number };
  cuts: Cut[];
  clips: Clip[];
  markers: Marker[];
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
  kind: "process" | "export" | "fetch";
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
  exports: string[];
  jobs: Job[];
}

export interface Settings {
  pexels_api_key: string;
  anthropic_api_key: string;
  has_pexels_api_key: boolean;
  has_anthropic_api_key: boolean;
  projects_dir: string;
  whisper_model: string;
  whisper_device: string;
  default_aspect: Aspect;
  ffmpeg_ok: boolean;
}
