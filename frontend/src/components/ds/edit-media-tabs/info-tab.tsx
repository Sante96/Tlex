/* ── Tab: Informazioni ────────────────────────────────────────── */
"use client";

import { useState, useEffect } from "react";
import { Info } from "lucide-react";

interface StreamData {
  codec_type: string;
  codec_name: string;
  language: string | null;
  title: string | null;
}

export function InfoTab({ mediaId }: { mediaId: number }) {
  const [streams, setStreams] = useState<StreamData[]>([]);

  useEffect(() => {
    const loadStreams = async () => {
      try {
        const { getMediaDetails } = await import("@/lib/api");
        const details = await getMediaDetails(mediaId);
        if (details.streams) {
          setStreams(details.streams);
        }
      } catch {}
    };
    loadStreams();
  }, [mediaId]);

  if (streams.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-[#71717a]">
        <Info className="h-10 w-10 mb-3 opacity-50" />
        <p className="text-sm">Nessuna informazione tecnica disponibile</p>
      </div>
    );
  }

  const videoStreams = streams.filter((s) => s.codec_type === "VIDEO");
  const audioStreams = streams.filter((s) => s.codec_type === "AUDIO");
  const subtitleStreams = streams.filter((s) => s.codec_type === "SUBTITLE");

  return (
    <div className="flex flex-col gap-5">
      {videoStreams.length > 0 && (
        <StreamGroup label="Video" streams={videoStreams} />
      )}
      {audioStreams.length > 0 && (
        <StreamGroup label="Audio" streams={audioStreams} />
      )}
      {subtitleStreams.length > 0 && (
        <StreamGroup label="Sottotitoli" streams={subtitleStreams} />
      )}
    </div>
  );
}

function StreamGroup({
  label,
  streams,
}: {
  label: string;
  streams: Array<{
    codec_name: string;
    language: string | null;
    title: string | null;
  }>;
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-[#fafafa] mb-2">{label}</h3>
      <div className="flex flex-col gap-1.5">
        {streams.map((s, i) => (
          <div
            key={i}
            className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/5 text-xs"
          >
            <span className="text-[#e5a00d] font-mono font-semibold uppercase">
              {s.codec_name}
            </span>
            {s.language && (
              <span className="text-[#a1a1aa] uppercase">{s.language}</span>
            )}
            {s.title && (
              <span className="text-[#71717a] truncate">{s.title}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
