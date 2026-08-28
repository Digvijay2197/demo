"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { PdfDocument } from "./types";
import { apiUrl } from "../lib/api";

export function DocumentsPanel() {
  const [docs, setDocs] = useState<PdfDocument[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    fetch(apiUrl("/documents"))
      .then((r) => r.json())
      .then((data) => setDocs(data.documents || []))
      .catch(() => setDocs([]));
  }, []);

  useEffect(refresh, [refresh]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setNote(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(apiUrl("/documents/upload"), { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) {
        setNote(data.detail || "Upload failed");
      } else {
        setNote(`Indexed ${data.source_file}: +${data.chunks_new} chunks`);
        refresh();
      }
    } catch {
      setNote("Network error during upload");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
      <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        Indexed PDFs &middot; {docs.length}
      </h2>

      <label className="cursor-pointer rounded-lg border border-dashed border-zinc-300 px-3 py-2 text-center text-xs text-zinc-500 hover:border-emerald-400 hover:text-emerald-600 dark:border-zinc-700">
        {busy ? "Uploading…" : "+ Upload a recipe PDF"}
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={onUpload}
          disabled={busy}
        />
      </label>
      {note && <p className="text-[11px] text-zinc-500">{note}</p>}

      {docs.length === 0 && (
        <p className="text-xs text-zinc-400">
          No PDFs indexed yet. Drop files into <code>backend/data/pdfs/</code> and run{" "}
          <code>python scripts/ingest.py</code>, or upload one above.
        </p>
      )}

      {docs.map((d) => (
        <div
          key={d.source_file}
          className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-medium text-zinc-900 dark:text-zinc-100" title={d.source_file}>
              📄 {d.source_file}
            </span>
            <span className={d.indexed ? "text-emerald-600" : "text-zinc-400"}>
              {d.indexed ? "✓" : "○"}
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            {d.pages_indexed} pages &middot; {d.chunks_indexed} chunks
            {d.size_kb != null && <> &middot; {d.size_kb} KB</>}
            {!d.on_disk && <> &middot; <span className="text-amber-600">file removed</span></>}
          </p>
        </div>
      ))}
    </div>
  );
}
