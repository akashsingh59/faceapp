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

type UploadPlanResponse = {
  photo_id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  s3_key: string;
  status: string;
  upload_mode: "single_put" | "multipart";
  upload_session_id: string;
  expires_in_seconds: number;
  upload_url?: string;
  multipart?: {
    upload_id: string;
    part_size_bytes: number;
    part_count: number;
    parts: Array<{
      part_number: number;
      upload_url: string;
    }>;
  };
};

type UploadResponse = {
  uploads: UploadPlanResponse[];
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
  requestJson<UploadResponse>(`/events/${eventId}/uploads/init`, {
    method: "POST",
    body: JSON.stringify({
      files: files.map((file) => ({
        filename: file.name,
        size_bytes: file.size,
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
      const file = filesByName.get(upload.filename);
      if (!file) {
        throw new Error(`Missing selected file: ${upload.filename}`);
      }

      if (upload.upload_mode === "single_put") {
        if (!upload.upload_url) {
          throw new Error(`Missing upload URL for ${upload.filename}`);
        }

        const response = await fetch(upload.upload_url, {
          method: "PUT",
          headers: file.type ? { "Content-Type": file.type } : undefined,
          body: file,
        });

        if (!response.ok) {
          const errorText = await response.text().catch(() => "");
          throw new Error(errorText || `Single-file upload failed for ${upload.filename}`);
        }

        const completeResponse = await fetch(`${API_BASE}/events/${eventId}/uploads/${upload.photo_id}/complete`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ upload_mode: "single_put" }),
        });

        if (!completeResponse.ok) {
          const error = await completeResponse.json().catch(() => ({}));
          throw new Error(error.detail ?? `Upload completion failed for ${upload.filename}`);
        }

        return;
      }

      if (!upload.multipart) {
        throw new Error(`Missing multipart metadata for ${upload.filename}`);
      }

      const partResponses = await Promise.all(
        upload.multipart.parts.map(async (part) => {
          const start = (part.part_number - 1) * upload.multipart!.part_size_bytes;
          const end = Math.min(start + upload.multipart!.part_size_bytes, file.size);
          const partBody = file.slice(start, end);

          const response = await fetch(part.upload_url, {
            method: "PUT",
            headers: file.type ? { "Content-Type": file.type } : undefined,
            body: partBody,
          });

          if (!response.ok) {
            const errorText = await response.text().catch(() => "");
            throw new Error(errorText || `Multipart upload failed for ${upload.filename} part ${part.part_number}`);
          }

          const etag = response.headers.get("etag") ?? "";
          return {
            part_number: part.part_number,
            etag,
          };
        }),
      );

      const completeResponse = await fetch(`${API_BASE}/events/${eventId}/uploads/${upload.photo_id}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          upload_mode: "multipart",
          upload_id: upload.multipart.upload_id,
          parts: partResponses,
        }),
      });

      if (!completeResponse.ok) {
        const error = await completeResponse.json().catch(() => ({}));
        throw new Error(error.detail ?? `Multipart completion failed for ${upload.filename}`);
      }
    }),
  );
};

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
