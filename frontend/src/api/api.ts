const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type EventResponse = {
  id: string;
  name: string;
  slug: string;
  collection_id: string;
  status: string;
  share_url: string;
};

type EventDetailResponse = EventResponse & {
  photo_count: number;
  person_count: number;
};

type UploadResponse = {
  uploads: Array<{
    filename: string;
    s3_key: string;
    upload_url: string;
    upload_required: boolean;
  }>;
};

type PhotoResponse = {
  id: string;
  filename: string;
  s3_key: string;
  status: string;
  created_at: string;
};

type ProcessResponse = {
  event_id: string;
  status: string;
  indexed_photos: number;
  persons: number;
  photo_faces: number;
};

type PublicEventResponse = {
  id: string;
  name: string;
  slug: string;
  status: string;
};

type SearchResponse = {
  id: string;
  status: string;
  similarity: number | null;
  photos: Array<{
    id: string;
    filename: string;
    url: string;
  }>;
};

const requestJson = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Request failed");
  }

  return response.json();
};

export const createEvent = (name: string) =>
  requestJson<EventResponse>("/events", {
    method: "POST",
    body: JSON.stringify({ name }),
  });

export const getEvent = (eventId: string) =>
  requestJson<EventDetailResponse>(`/events/${eventId}`);

export const createUploadUrls = (eventId: string, files: File[]) =>
  requestJson<UploadResponse>(`/events/${eventId}/upload-urls`, {
    method: "POST",
    body: JSON.stringify({
      files: files.map((file) => ({
        filename: file.name,
        content_type: file.type || null,
      })),
    }),
  });

export const uploadFilesToStorage = async (
  eventId: string,
  files: File[],
  uploads: UploadResponse["uploads"],
) => {
  const filesByName = new Map(files.map((file) => [file.name, file]));

  await Promise.all(
    uploads.map(async (upload) => {
      if (!upload.upload_required) {
        return;
      }

      const file = filesByName.get(upload.filename);
      if (!file) {
        throw new Error(`Missing selected file: ${upload.filename}`);
      }

      const response = await fetch(upload.upload_url, {
        method: "PUT",
        headers: file.type ? { "Content-Type": file.type } : undefined,
        body: file,
      }).catch(() => null);

      if (response === null) {
        await uploadFileThroughBackend(eventId, upload.s3_key, file);
        return;
      }

      if (!response.ok) {
        await uploadFileThroughBackend(eventId, upload.s3_key, file);
      }
    }),
  );
};

const uploadFileThroughBackend = async (eventId: string, s3Key: string, file: File) => {
  const formData = new FormData();
  formData.append("s3_key", s3Key);
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/events/${eventId}/upload-file`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? `Backend upload failed for ${file.name}`);
  }
};

export const registerPhotos = (
  eventId: string,
  uploads: UploadResponse["uploads"],
) =>
  requestJson<{ created: number; photos: PhotoResponse[] }>(
    `/events/${eventId}/photos`,
    {
      method: "POST",
      body: JSON.stringify({
        photos: uploads.map((upload) => ({
          filename: upload.filename,
          s3_key: upload.s3_key,
        })),
      }),
    },
  );

export const processEvent = (eventId: string) =>
  requestJson<ProcessResponse>(`/events/${eventId}/process`, {
    method: "POST",
  });

export const getPublicEvent = (slug: string) =>
  requestJson<PublicEventResponse>(`/public/events/${slug}`);

export const searchEvent = async (slug: string, selfie: File) => {
  const formData = new FormData();
  formData.append("selfie", selfie);

  const response = await fetch(`${API_BASE}/public/events/${slug}/search`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Search failed");
  }

  return response.json() as Promise<SearchResponse>;
};

export type {
  EventDetailResponse,
  EventResponse,
  PhotoResponse,
  ProcessResponse,
  PublicEventResponse,
  SearchResponse,
};
