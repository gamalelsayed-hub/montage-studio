import type { Job } from "./types";

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let message = `خطأ ${response.status}`;
    try {
      const data = await response.json();
      if (data.detail) message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* الرد مش JSON */
    }
    throw new Error(message);
  }
  return response.json();
}

export const api = {
  get: <T>(url: string) => request<T>("GET", url),
  post: <T>(url: string, body: unknown = {}) => request<T>("POST", url, body),
  put: <T>(url: string, body: unknown) => request<T>("PUT", url, body),
  patch: <T>(url: string, body: unknown) => request<T>("PATCH", url, body),
  del: <T>(url: string) => request<T>("DELETE", url),
};

/** رفع ملف مع نسبة التقدم (التسجيلات ممكن تبقى كبيرة). */
export function upload<T>(url: string, file: File, onProgress?: (fraction: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    xhr.open("POST", url);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      let data: any = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* تجاهل */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new Error(data?.detail || `خطأ ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error("الاتصال بالسيرفر وقع"));
    xhr.send(form);
  });
}

/** يستنى لحد ما الشغلانة تخلص، ويبلّغ بالتقدم. */
export async function waitForJob(jobId: string, onUpdate: (job: Job) => void): Promise<Job> {
  for (;;) {
    const job = await api.get<Job>(`/api/jobs/${jobId}`);
    onUpdate(job);
    if (job.status !== "running") return job;
    await new Promise((r) => setTimeout(r, 700));
  }
}

export const fileUrl = (projectId: string, path: string) =>
  `/files/${encodeURIComponent(projectId)}/${path.split("/").map(encodeURIComponent).join("/")}`;

export function formatTime(seconds: number, withFraction = false): string {
  const safe = Math.max(0, seconds || 0);
  const m = Math.floor(safe / 60);
  const s = Math.floor(safe % 60);
  const base = `${m}:${s.toString().padStart(2, "0")}`;
  return withFraction ? `${base}.${Math.floor((safe % 1) * 10)}` : base;
}
