import { useEffect, useMemo, useState } from "react";
import "./App.css";
import {
  createEvent,
  createUploadUrls,
  getEvent,
  getPublicEvent,
  processEvent,
  registerPhotos,
  searchEvent,
  uploadFilesToStorage,
  type EventDetailResponse,
  type EventResponse,
  type PhotoResponse,
  type ProcessResponse,
  type PublicEventResponse,
  type SearchResponse,
} from "./api/api";

const shareUrlFor = (slug: string) => `${window.location.origin}/s/${slug}`;
type AdminStep = "create" | "upload" | "ready";

function ResultPhoto({ photo }: { photo: SearchResponse["photos"][number] }) {
  const [failed, setFailed] = useState(false);

  return (
    <article className="photo-tile">
      {failed ? (
        <div className="photo-preview">{photo.filename.slice(0, 2).toUpperCase()}</div>
      ) : (
        <img
          alt={photo.filename}
          className="result-image"
          loading="lazy"
          onError={() => setFailed(true)}
          src={photo.url}
        />
      )}
      <p>{photo.filename}</p>
    </article>
  );
}

function PublicSearchPage({ slug }: { slug: string }) {
  const [event, setEvent] = useState<PublicEventResponse | null>(null);
  const [selfie, setSelfie] = useState<File | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getPublicEvent(slug).then(setEvent).catch((err) => setError(err.message));
  }, [slug]);

  const runSearch = async () => {
    if (!selfie) return;
    setBusy(true);
    setError("");
    try {
      setResult(await searchEvent(slug, selfie));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Shared event</p>
          <h1>{event?.name ?? "Loading event"}</h1>
        </div>
        <a className="ghost-link" href="/">
          Admin
        </a>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Find Photos</h2>
            <p>{event?.status === "ready" ? "Ready" : event?.status ?? "Loading"}</p>
          </div>
        </div>

        <div className="input-row">
          <input
            type="file"
            accept="image/*"
            onChange={(event) => setSelfie(event.target.files?.[0] ?? null)}
          />
          <button disabled={!selfie || busy} onClick={runSearch}>
            {busy ? "Searching" : "Search"}
          </button>
        </div>

        {error && <p className="error">{error}</p>}

        {result && (
          <div className="results-grid">
            {result.photos.length === 0 ? (
              <p>No matching photos found.</p>
            ) : (
              result.photos.map((photo) => (
                <ResultPhoto key={photo.id} photo={photo} />
              ))
            )}
          </div>
        )}
      </section>
    </main>
  );
}

function AdminPage() {
  const [eventName, setEventName] = useState("Rahul Wedding");
  const [event, setEvent] = useState<EventResponse | null>(null);
  const [step, setStep] = useState<AdminStep>("create");
  const [files, setFiles] = useState<File[]>([]);
  const [photos, setPhotos] = useState<PhotoResponse[]>([]);
  const [details, setDetails] = useState<EventDetailResponse | null>(null);
  const [processed, setProcessed] = useState<ProcessResponse | null>(null);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");
  const [busy, setBusy] = useState(false);

  const shareUrl = useMemo(() => (event ? shareUrlFor(event.slug) : ""), [event]);

  const createNewEvent = async () => {
    setBusy(true);
    setError("");
    setProgress("");
    try {
      setProgress("Creating event");
      const created = await createEvent(eventName);
      setEvent(created);
      setStep("upload");
      setDetails(null);
      setPhotos([]);
      setProcessed(null);
      setFiles([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create event");
    } finally {
      setBusy(false);
    }
  };

  const uploadSelectedPhotos = async () => {
    if (!event || files.length === 0) return;
    setBusy(true);
    setError("");
    try {
      setProgress("Creating upload URLs");
      const uploadUrls = await createUploadUrls(event.id, files);
      setProgress("Uploading photos to S3");
      await uploadFilesToStorage(event.id, files, uploadUrls.uploads);
      setProgress("Registering photos");
      const registered = await registerPhotos(event.id, uploadUrls.uploads);
      setPhotos(registered.photos);
      setProgress("Indexing faces");
      const result = await processEvent(event.id);
      setProcessed(result);
      setProgress("Loading event status");
      const refreshed = await getEvent(event.id);
      setDetails(refreshed);
      setEvent((current) => (current ? { ...current, status: refreshed.status } : current));
      setStep("ready");
      setProgress("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload and index photos");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Face event search</p>
          <h1>
            {step === "create" && "Create Event"}
            {step === "upload" && (event?.name ?? "Upload Album")}
            {step === "ready" && "Share Event"}
          </h1>
        </div>
        <span className="status-pill">{event?.status ?? "Not created"}</span>
      </section>

      <div className="steps">
        <span className={step === "create" ? "active" : ""}>1. Event</span>
        <span className={step === "upload" ? "active" : ""}>2. Upload</span>
        <span className={step === "ready" ? "active" : ""}>3. Share</span>
      </div>

      {step === "create" && (
        <section className="panel focus-panel">
          <div className="section-heading">
            <div>
              <h2>Name The Event</h2>
              <p>This creates a private event workspace for one album.</p>
            </div>
          </div>
          <div className="input-row">
            <input
              value={eventName}
              onChange={(event) => setEventName(event.target.value)}
              placeholder="Event name"
            />
            <button disabled={busy || !eventName.trim()} onClick={createNewEvent}>
              Create Event
            </button>
          </div>
        </section>
      )}

      {step === "upload" && event && (
        <>
          <section className="panel focus-panel">
            <div className="section-heading">
              <div>
                <h2>Upload Photos</h2>
                <p>{photos.length} photos registered for {event.name}</p>
              </div>
            </div>
            <div className="input-row">
              <input
                type="file"
                multiple
                accept="image/*"
                onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
              />
              <button disabled={busy || files.length === 0} onClick={uploadSelectedPhotos}>
                {busy ? "Uploading And Indexing" : "Upload"}
              </button>
            </div>
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>Indexing Status</h2>
                <p>
                  {processed
                    ? `${processed.persons} persons found`
                    : photos.length > 0
                      ? "Indexing automatically"
                      : "Starts after upload"}
                </p>
              </div>
            </div>
            {(photos.length > 0 || busy) && (
              <div className="metrics">
                <span>{busy ? progress || "Processing" : `${photos.length} uploaded`}</span>
                <span>{files.length} selected</span>
              </div>
            )}
          </section>
        </>
      )}

      {step === "ready" && event && (
        <section className="panel share-panel focus-panel">
          <div className="section-heading">
            <div>
              <h2>Shareable Link</h2>
              <p>Guests can upload a selfie and see photos only from this event.</p>
            </div>
          </div>
          <div className="share-box">
            <a href={shareUrl}>{shareUrl}</a>
          </div>
          <div className="metrics">
            <span>{details?.photo_count ?? photos.length} photos indexed</span>
            <span>{details?.person_count ?? processed?.persons ?? 0} persons</span>
            <span>{event.status}</span>
          </div>
        </section>
      )}

      {error && <p className="error">{error}</p>}
    </main>
  );
}

function App() {
  const slug = window.location.pathname.startsWith("/s/")
    ? window.location.pathname.replace("/s/", "")
    : "";

  if (slug) {
    return <PublicSearchPage slug={slug} />;
  }

  return <AdminPage />;
}

export default App;
