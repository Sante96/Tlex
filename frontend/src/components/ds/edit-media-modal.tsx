"use client";

import { useState, useEffect } from "react";
import { X, Pencil, Image as ImageIcon, Monitor, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  updateMediaItem,
  getMediaTmdbImages,
  updateSeries,
  getSeriesTmdbImages,
  updateSeasonPoster,
  getSeasonTmdbImages,
  type TMDBImage,
  type MediaUpdateBody,
} from "@/lib/api";
import { GeneralTab, ImagePickerTab, InfoTab } from "./edit-media-tabs";

export type EntityType = "media" | "series" | "season";

interface EditMediaModalProps {
  mediaId: number;
  title: string;
  overview: string | null;
  posterPath: string | null;
  releaseDate: string | null;
  entityType?: EntityType;
  seriesId?: number;
  seriesTitle?: string;
  seasonNumber?: number | null;
  episodeNumber?: number | null;
  onClose: () => void;
  onSaved: () => void;
}

type TabId = "general" | "poster" | "backdrop" | "info";

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const MEDIA_TABS: Tab[] = [
  { id: "general", label: "Generale", icon: <Pencil className="h-4 w-4" /> },
  { id: "poster", label: "Locandina", icon: <ImageIcon className="h-4 w-4" /> },
  { id: "backdrop", label: "Sfondo", icon: <Monitor className="h-4 w-4" /> },
  { id: "info", label: "Informazioni", icon: <Info className="h-4 w-4" /> },
];

const SERIES_TABS: Tab[] = [
  { id: "general", label: "Generale", icon: <Pencil className="h-4 w-4" /> },
  { id: "poster", label: "Locandina", icon: <ImageIcon className="h-4 w-4" /> },
  { id: "backdrop", label: "Sfondo", icon: <Monitor className="h-4 w-4" /> },
];

const SEASON_TABS: Tab[] = [
  { id: "poster", label: "Locandina", icon: <ImageIcon className="h-4 w-4" /> },
];

export function EditMediaModal({
  mediaId,
  title: initialTitle,
  overview: initialOverview,
  posterPath: initialPosterPath,
  releaseDate: initialReleaseDate,
  entityType = "media",
  seriesId,
  seriesTitle,
  seasonNumber,
  episodeNumber,
  onClose,
  onSaved,
}: EditMediaModalProps) {
  const tabs =
    entityType === "season"
      ? SEASON_TABS
      : entityType === "series"
        ? SERIES_TABS
        : MEDIA_TABS;
  const [activeTab, setActiveTab] = useState<TabId>(
    entityType === "season" ? "poster" : "general",
  );
  const [saving, setSaving] = useState(false);

  // Form state
  const [formTitle, setFormTitle] = useState(initialTitle);
  const [formOverview, setFormOverview] = useState(initialOverview || "");
  const [formPosterPath, setFormPosterPath] = useState(initialPosterPath || "");
  const [formBackdropPath, setFormBackdropPath] = useState("");
  const [formReleaseDate, setFormReleaseDate] = useState(
    initialReleaseDate || "",
  );

  // TMDB images
  const [tmdbImages, setTmdbImages] = useState<{
    stills: TMDBImage[];
    posters: TMDBImage[];
    backdrops: TMDBImage[];
  }>({ stills: [], posters: [], backdrops: [] });
  const [loadingImages, setLoadingImages] = useState(false);

  useEffect(() => {
    const loadImages = async () => {
      setLoadingImages(true);
      try {
        const images =
          entityType === "season" && seriesId && seasonNumber != null
            ? await getSeasonTmdbImages(seriesId, seasonNumber)
            : entityType === "series"
              ? await getSeriesTmdbImages(mediaId)
              : await getMediaTmdbImages(mediaId);
        setTmdbImages(images);
      } catch {}
      setLoadingImages(false);
    };
    loadImages();
  }, [mediaId, entityType, seriesId, seasonNumber]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const body: MediaUpdateBody = {};
      if (formTitle !== initialTitle) body.title = formTitle;
      if (formOverview !== (initialOverview || ""))
        body.overview = formOverview;
      if (formPosterPath !== (initialPosterPath || ""))
        body.poster_path = formPosterPath;
      if (formBackdropPath) body.backdrop_path = formBackdropPath;
      if (formReleaseDate !== (initialReleaseDate || ""))
        body.release_date = formReleaseDate;

      if (
        entityType === "season" &&
        seriesId &&
        seasonNumber != null &&
        formPosterPath !== (initialPosterPath || "")
      ) {
        await updateSeasonPoster(seriesId, seasonNumber, formPosterPath);
      } else if (Object.keys(body).length > 0) {
        if (entityType === "series") {
          await updateSeries(mediaId, {
            title: body.title,
            overview: body.overview,
            poster_path: body.poster_path,
            backdrop_path: body.backdrop_path,
            first_air_date: body.release_date,
          });
        } else {
          await updateMediaItem(mediaId, body);
        }
      }
      onSaved();
      onClose();
    } catch {}
    setSaving(false);
  };

  const modalTitle = (() => {
    const parts = ["Modifica"];
    if (seriesTitle) parts.push(seriesTitle, "-");
    parts.push(initialTitle);
    if (seasonNumber != null && episodeNumber != null) {
      parts.push(`(S${seasonNumber} E${episodeNumber})`);
    }
    return parts.join(" ");
  })();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      <div
        className="relative w-full max-w-3xl h-[85vh] rounded-xl overflow-hidden flex flex-col"
        style={{
          background: "rgba(24, 24, 27, 0.95)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.1)",
          boxShadow: "0 24px 48px rgba(0,0,0,0.5)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <Pencil className="h-5 w-5 text-[#e5a00d]" />
            <h2 className="text-lg font-semibold text-[#fafafa] truncate">
              {modalTitle}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="h-5 w-5 text-[#a1a1aa]" />
          </button>
        </div>

        {/* Body: sidebar tabs + content */}
        <div className="flex flex-1 overflow-hidden">
          <nav className="w-44 shrink-0 border-r border-white/10 py-3 px-2 flex flex-col gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left",
                  activeTab === tab.id
                    ? "bg-[#e5a00d]/15 text-[#e5a00d]"
                    : "text-[#a1a1aa] hover:bg-white/5 hover:text-[#fafafa]",
                )}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </nav>

          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === "general" && (
              <GeneralTab
                title={formTitle}
                overview={formOverview}
                releaseDate={formReleaseDate}
                onTitleChange={setFormTitle}
                onOverviewChange={setFormOverview}
                onReleaseDateChange={setFormReleaseDate}
              />
            )}
            {activeTab === "poster" && (
              <ImagePickerTab
                label="Locandina"
                images={
                  tmdbImages.stills.length > 0
                    ? tmdbImages.stills
                    : tmdbImages.posters
                }
                selected={formPosterPath}
                onSelect={setFormPosterPath}
                loading={loadingImages}
                aspect={tmdbImages.stills.length > 0 ? "still" : "poster"}
              />
            )}
            {activeTab === "backdrop" && (
              <ImagePickerTab
                label="Sfondo"
                images={tmdbImages.backdrops}
                selected={formBackdropPath}
                onSelect={setFormBackdropPath}
                loading={loadingImages}
                aspect="backdrop"
              />
            )}
            {activeTab === "info" && <InfoTab mediaId={mediaId} />}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/10">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-lg text-sm font-medium text-[#fafafa] hover:bg-white/10 transition-colors"
          >
            Annulla
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-lg text-sm font-semibold text-black bg-[#e5a00d] hover:bg-[#f0b429] active:bg-[#c89200] transition-colors disabled:opacity-50"
          >
            {saving ? "Salvataggio..." : "Salva Modifiche"}
          </button>
        </div>
      </div>
    </div>
  );
}
