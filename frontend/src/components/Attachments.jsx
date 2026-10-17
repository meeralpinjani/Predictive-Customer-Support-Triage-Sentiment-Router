import { useRef, useState } from "react";
import clsx from "clsx";
import { FileText, Image as ImageIcon, Paperclip, UploadCloud, X } from "lucide-react";
import { ACCEPT, MAX_FILES, MAX_MB } from "../api.js";

const OK_TYPES = ACCEPT.split(",");

export function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Client-side checks mirror the server's (the server re-checks the actual file bytes). */
export function validateFiles(current, incoming) {
  const errors = [];
  const ok = [];
  for (const f of incoming) {
    if (!OK_TYPES.includes(f.type)) errors.push(`${f.name}: only PNG, JPG or PDF`);
    else if (f.size > MAX_MB * 1024 * 1024) errors.push(`${f.name}: larger than ${MAX_MB} MB`);
    else ok.push(f);
  }
  const room = MAX_FILES - current.length;
  if (ok.length > room) errors.push(`At most ${MAX_FILES} files`);
  return { files: [...current, ...ok.slice(0, Math.max(room, 0))], errors };
}

/** Selected-but-not-sent files, removable. */
export function PendingFiles({ files, onRemove }) {
  if (!files.length) return null;
  return (
    <ul className="flex flex-wrap gap-2">
      {files.map((f, i) => (
        <li key={`${f.name}-${i}`} className="chip bg-sunken text-ink-2 !py-1 !pl-2 !pr-1">
          {f.type === "application/pdf" ? <FileText className="w-3.5 h-3.5" aria-hidden /> : <ImageIcon className="w-3.5 h-3.5" aria-hidden />}
          <span className="max-w-[140px] truncate">{f.name}</span>
          <span className="text-ink-3 font-normal">{fmtSize(f.size)}</span>
          <button type="button" onClick={() => onRemove(i)} className="rounded-full p-0.5 hover:bg-line" aria-label={`Remove ${f.name}`}>
            <X className="w-3 h-3" />
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Paperclip button for chat composers. */
export function AttachButton({ files, setFiles, onError, disabled }) {
  const input = useRef();
  return (
    <>
      <input ref={input} type="file" accept={ACCEPT} multiple className="hidden"
             onChange={(e) => {
               const r = validateFiles(files, [...e.target.files]);
               setFiles(r.files);
               if (r.errors.length) onError?.(r.errors.join(" · "));
               e.target.value = "";
             }} />
      <button type="button" className="btn-ghost !px-3 h-[44px]" disabled={disabled || files.length >= MAX_FILES}
              onClick={() => input.current.click()} aria-label="Attach files" title={`Attach PNG, JPG or PDF (max ${MAX_FILES}, ${MAX_MB} MB each)`}>
        <Paperclip className="w-4 h-4" />
      </button>
    </>
  );
}

/** Drag-and-drop area for the new-ticket form. */
export function DropZone({ files, setFiles, onError }) {
  const input = useRef();
  const [over, setOver] = useState(false);
  const add = (list) => {
    const r = validateFiles(files, [...list]);
    setFiles(r.files);
    onError?.(r.errors.join(" · "));
  };
  return (
    <div>
      <button type="button" onClick={() => input.current.click()}
              onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); add(e.dataTransfer.files); }}
              className={clsx("w-full rounded-2xl border-2 border-dashed px-4 py-5 text-center transition",
                over ? "border-glacier bg-glacier-soft/50" : "border-line hover:border-ink-3/40")}>
        <UploadCloud className="w-5 h-5 mx-auto text-ink-3" aria-hidden />
        <p className="mt-1 text-sm font-semibold">Add screenshots or files</p>
        <p className="text-xs text-ink-3">PNG, JPG or PDF · up to {MAX_FILES} files · {MAX_MB} MB each</p>
      </button>
      <input ref={input} type="file" accept={ACCEPT} multiple className="hidden"
             onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      <div className="mt-2"><PendingFiles files={files} onRemove={(i) => setFiles(files.filter((_, j) => j !== i))} /></div>
    </div>
  );
}

/** Sent attachments: image thumbnails (open full size) and PDF chips. */
export function AttachmentList({ items, compact = false, light = false }) {
  if (!items?.length) return null;
  const images = items.filter((a) => a.is_image);
  const docs = items.filter((a) => !a.is_image);
  return (
    <div className="mt-2 space-y-2">
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {images.map((a) => (
            <a key={a.id} href={a.url} target="_blank" rel="noreferrer" title={a.filename}
               className={clsx("block overflow-hidden rounded-xl border", light ? "border-white/30" : "border-line", compact ? "w-20 h-16" : "w-32 h-24")}>
              <img src={a.url} alt={a.filename} loading="lazy" className="w-full h-full object-cover" />
            </a>
          ))}
        </div>
      )}
      {docs.map((a) => (
        <a key={a.id} href={a.url} target="_blank" rel="noreferrer"
           className={clsx("flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-xs font-semibold w-fit",
             light ? "bg-white/15" : "bg-sunken text-ink-2 hover:bg-line")}>
          <FileText className="w-4 h-4" aria-hidden /> {a.filename} <span className="font-normal opacity-70">{fmtSize(a.size)}</span>
        </a>
      ))}
    </div>
  );
}
