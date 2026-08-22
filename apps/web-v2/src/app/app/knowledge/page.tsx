"use client";

import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  FileText,
  Link as LinkIcon,
  Upload,
  Trash2,
  Sparkles,
  AlertCircle,
  Clock,
  Plus,
  X,
  Type,
  Loader2,
  Database,
  Layers,
  Box,
} from "lucide-react";
import { Card } from "@/components/ui/card-3d";
import { SectionHeader } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, apiPost, apiUpload, apiDelete, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface KnowledgeSource {
  id: string;
  title: string;
  source_type: string;
  file_type: string | null;
  status: string;
  chunk_count: number;
  created_at: string;
  description?: string | null;
  level?: string;
  processing_error?: string | null;
  total_tokens?: number | null;
}

interface KnowledgeStats {
  total_sources: number;
  total_chunks: number;
  total_embeddings: number;
  by_level: Record<string, number>;
  by_status: Record<string, number>;
  by_source_type: Record<string, number>;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
}

const SOURCE_ICON: Record<string, typeof FileText> = {
  url: LinkIcon,
  file: FileText,
  text: Type,
  integration: LinkIcon,
};

const STATUS_STYLE: Record<string, string> = {
  ready: "badge-success",
  processing: "badge-warning",
  failed: "badge-danger",
  pending: "badge-neutral",
};

export default function KnowledgePage() {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [addMode, setAddMode] = useState<"url" | "text">("url");
  const [urlValue, setUrlValue] = useState("");
  const [urlTitle, setUrlTitle] = useState("");
  const [textTitle, setTextTitle] = useState("");
  const [textContent, setTextContent] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: sources, isLoading, error, refetch } = useQuery<
    KnowledgeSource[]
  >({
    queryKey: ["knowledge-sources"],
    queryFn: () => apiGet<KnowledgeSource[]>("/knowledge/sources"),
    retry: 1,
  });

  const { data: stats } = useQuery<KnowledgeStats>({
    queryKey: ["knowledge-stats"],
    queryFn: () => apiGet<KnowledgeStats>("/knowledge/stats"),
    retry: 1,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiDelete(`/knowledge/sources/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-sources"] });
      qc.invalidateQueries({ queryKey: ["knowledge-stats"] });
    },
  });

  const urlMutation = useMutation({
    mutationFn: (body: { url: string; title: string }) =>
      apiPost<KnowledgeSource>("/knowledge/url", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-sources"] });
      qc.invalidateQueries({ queryKey: ["knowledge-stats"] });
      setShowAddModal(false);
      setUrlValue("");
      setUrlTitle("");
      setAddError(null);
    },
    onError: (err) => {
      setAddError(
        err instanceof ApiError
          ? `Failed to add URL (${err.status})`
          : "Failed to add URL. Please try again.",
      );
    },
  });

  const textMutation = useMutation({
    mutationFn: (body: { title: string; content: string }) =>
      apiPost<KnowledgeSource>("/knowledge/text", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-sources"] });
      qc.invalidateQueries({ queryKey: ["knowledge-stats"] });
      setShowAddModal(false);
      setTextTitle("");
      setTextContent("");
      setAddError(null);
    },
    onError: (err) => {
      setAddError(
        err instanceof ApiError
          ? `Failed to add text (${err.status})`
          : "Failed to add text. Please try again.",
      );
    },
  });

  const filtered = (sources ?? []).filter(
    (s) =>
      s.title.toLowerCase().includes(query.toLowerCase()) ||
      (s.description ?? "").toLowerCase().includes(query.toLowerCase()),
  );

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", file.name);
      await apiUpload<KnowledgeSource>("/knowledge/upload", formData);
      qc.invalidateQueries({ queryKey: ["knowledge-sources"] });
      qc.invalidateQueries({ queryKey: ["knowledge-stats"] });
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? `Upload failed (${err.status})`
          : "Upload failed. Please try again.";
      setUploadError(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleAddSubmit = () => {
    setAddError(null);
    if (addMode === "url") {
      if (!urlValue.trim()) {
        setAddError("Please enter a URL");
        return;
      }
      urlMutation.mutate({ url: urlValue.trim(), title: urlTitle.trim() });
    } else {
      if (!textTitle.trim() || !textContent.trim()) {
        setAddError("Please enter a title and content");
        return;
      }
      textMutation.mutate({ title: textTitle.trim(), content: textContent });
    }
  };

  const isAdding = urlMutation.isPending || textMutation.isPending;
  const hasSources = (sources?.length ?? 0) > 0;

  return (
    <div className="p-4 lg:p-8 max-w-[1600px] mx-auto animate-fade-in pb-32">
      {/* Header */}
      <div className="flex flex-col gap-4 mb-8 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-display uppercase text-2xl sm:text-3xl lg:text-4xl tracking-wide text-text mb-1">
            Knowledge Base
          </h1>
          <p className="text-sm text-text-secondary">
            Documents and brand info that help the AI understand your business.
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative w-full lg:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search sources..."
              className="input-field pl-10"
            />
          </div>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileChange}
            accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.csv,.txt,.md,.html,.json,.png,.jpg,.jpeg,.gif,.webp"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="btn-secondary flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            {uploading ? "Uploading..." : "Upload File"}
          </button>
          <button
            onClick={() => {
              setAddMode("url");
              setShowAddModal(true);
              setAddError(null);
            }}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Source
          </button>
        </div>
      </div>

      {uploadError && (
        <div className="mb-6 rounded-lg bg-danger/10 border border-danger/20 px-4 py-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-danger shrink-0" />
          <p className="text-sm text-danger">{uploadError}</p>
          <button
            onClick={() => setUploadError(null)}
            className="ml-auto text-danger/60 hover:text-danger"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Stats — always show when we have data */}
      {!isLoading && !error && stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={<Database className="w-4 h-4" />}
            label="Total Sources"
            value={stats.total_sources}
          />
          <StatCard
            icon={<Layers className="w-4 h-4" />}
            label="Total Chunks"
            value={stats.total_chunks}
          />
          <StatCard
            icon={<Box className="w-4 h-4" />}
            label="Embeddings"
            value={stats.total_embeddings}
          />
          <StatCard
            icon={<FileText className="w-4 h-4" />}
            label="Source Types"
            value={Object.keys(stats.by_source_type).length}
          />
        </div>
      )}

      {isLoading && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-20 rounded-xl" />
            ))}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-40 rounded-xl" />
            ))}
          </div>
        </div>
      )}

      {!isLoading && error && (
        <Card className="text-center py-16" hover={false}>
          <div className="w-14 h-14 rounded-2xl bg-danger/10 flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-7 h-7 text-danger" />
          </div>
          <h3 className="font-display text-lg font-medium text-text mb-2">
            Couldn&apos;t load knowledge sources
          </h3>
          <p className="text-sm text-text-secondary mb-6">
            Something went wrong. Please try again.
          </p>
          <button
            onClick={() => refetch()}
            className="btn-primary inline-flex items-center gap-2"
          >
            Try Again
          </button>
        </Card>
      )}

      {!isLoading && !error && !hasSources && (
        <Card className="text-center py-20" hover={false}>
          <motion.div
            animate={{ y: [0, -6, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-5 glow-ring"
          >
            <Sparkles className="w-8 h-8 text-accent" />
          </motion.div>
          <h3 className="font-display text-xl font-medium text-text mb-2">
            No knowledge sources yet
          </h3>
          <p className="text-sm text-text-secondary max-w-md mx-auto mb-8 leading-relaxed">
            Upload documents, brand guidelines, or product info to help the AI
            understand your business better. The AI uses this knowledge to
            generate more accurate, on-brand content.
          </p>
          <div className="flex items-center justify-center gap-3 flex-wrap">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="btn-primary inline-flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              {uploading ? "Uploading..." : "Upload a Document"}
            </button>
            <button
              onClick={() => {
                setAddMode("url");
                setShowAddModal(true);
                setAddError(null);
              }}
              className="btn-secondary inline-flex items-center gap-2"
            >
              <LinkIcon className="w-4 h-4" />
              Add a URL
            </button>
          </div>
        </Card>
      )}

      {!isLoading && !error && hasSources && (
        <div>
          <SectionHeader
            title="All Sources"
            subtitle={`${filtered.length} source${filtered.length === 1 ? "" : "s"}`}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((s, i) => {
              const Icon = SOURCE_ICON[s.source_type] ?? FileText;
              return (
                <motion.div
                  key={s.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                >
                  <Card hover className="h-full group">
                    <div className="flex items-start justify-between mb-3">
                      <div className="w-10 h-10 rounded-lg bg-white/[0.06] flex items-center justify-center text-text-secondary group-hover:text-accent transition-colors">
                        <Icon className="w-5 h-5" />
                      </div>
                      <button
                        onClick={() => deleteMutation.mutate(s.id)}
                        disabled={deleteMutation.isPending}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-text-muted hover:text-danger disabled:opacity-50"
                        aria-label="Delete source"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <h3 className="font-display text-base font-medium text-text leading-snug mb-2 group-hover:text-accent transition-colors">
                      {s.title}
                    </h3>
                    {s.description && (
                      <p className="text-xs text-text-secondary leading-relaxed mb-3 line-clamp-2">
                        {s.description}
                      </p>
                    )}
                    {s.processing_error && s.status === "failed" && (
                      <p className="text-xs text-danger/80 leading-relaxed mb-3 line-clamp-2">
                        {s.processing_error}
                      </p>
                    )}
                    <div className="flex items-center gap-2 flex-wrap mb-3">
                      <span className="badge text-[10px]">{s.source_type}</span>
                      {s.file_type && (
                        <span className="badge text-[10px]">{s.file_type}</span>
                      )}
                      <span
                        className={cn(
                          "badge text-[10px]",
                          STATUS_STYLE[s.status] ?? "badge-neutral",
                        )}
                      >
                        {s.status}
                      </span>
                    </div>
                    <div className="flex items-center justify-between pt-3 border-t border-white/[0.04]">
                      <span className="font-mono text-[10px] text-text-muted flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {formatDate(s.created_at)}
                      </span>
                      <span className="font-mono text-[10px] text-text-muted">
                        {s.chunk_count} chunks
                      </span>
                    </div>
                  </Card>
                </motion.div>
              );
            })}
          </div>

          {filtered.length === 0 && (
            <Card className="text-center py-12" hover={false}>
              <Search className="w-8 h-8 text-text-muted mx-auto mb-3" />
              <p className="text-text-secondary">
                No sources found for &quot;{query}&quot;
              </p>
              <button
                onClick={() => setQuery("")}
                className="btn-ghost mt-3 text-xs"
              >
                Clear search
              </button>
            </Card>
          )}
        </div>
      )}

      {/* Add Source Modal */}
      <AnimatePresence>
        {showAddModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            onClick={() => !isAdding && setShowAddModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="glass-strong rounded-xl p-6 w-full max-w-md border border-white/10"
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-display text-lg font-medium text-text">
                  Add Knowledge Source
                </h3>
                <button
                  onClick={() => !isAdding && setShowAddModal(false)}
                  className="text-text-muted hover:text-text"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Mode toggle */}
              <div className="flex items-center gap-1 p-1 rounded-lg bg-white/[0.04] mb-5">
                <button
                  onClick={() => {
                    setAddMode("url");
                    setAddError(null);
                  }}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm transition-all",
                    addMode === "url"
                      ? "bg-accent text-white font-medium"
                      : "text-text-secondary hover:text-text",
                  )}
                >
                  <LinkIcon className="w-4 h-4" /> URL
                </button>
                <button
                  onClick={() => {
                    setAddMode("text");
                    setAddError(null);
                  }}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm transition-all",
                    addMode === "text"
                      ? "bg-accent text-white font-medium"
                      : "text-text-secondary hover:text-text",
                  )}
                >
                  <Type className="w-4 h-4" /> Text
                </button>
              </div>

              {addMode === "url" ? (
                <div className="space-y-4">
                  <div>
                    <label className="label-field mb-1.5 block">URL</label>
                    <input
                      value={urlValue}
                      onChange={(e) => setUrlValue(e.target.value)}
                      placeholder="https://example.com/about"
                      className="input-field"
                      disabled={isAdding}
                    />
                  </div>
                  <div>
                    <label className="label-field mb-1.5 block">
                      Title (optional)
                    </label>
                    <input
                      value={urlTitle}
                      onChange={(e) => setUrlTitle(e.target.value)}
                      placeholder="About Us Page"
                      className="input-field"
                      disabled={isAdding}
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className="label-field mb-1.5 block">Title</label>
                    <input
                      value={textTitle}
                      onChange={(e) => setTextTitle(e.target.value)}
                      placeholder="Brand Guidelines"
                      className="input-field"
                      disabled={isAdding}
                    />
                  </div>
                  <div>
                    <label className="label-field mb-1.5 block">Content</label>
                    <textarea
                      value={textContent}
                      onChange={(e) => setTextContent(e.target.value)}
                      placeholder="Paste your brand info, product details, or any text..."
                      rows={5}
                      className="input-field resize-none"
                      disabled={isAdding}
                    />
                  </div>
                </div>
              )}

              {addError && (
                <div className="mt-4 rounded-lg bg-danger/10 border border-danger/20 px-3 py-2 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-danger shrink-0" />
                  <p className="text-sm text-danger">{addError}</p>
                </div>
              )}

              <div className="flex justify-end gap-3 mt-6">
                <button
                  onClick={() => !isAdding && setShowAddModal(false)}
                  disabled={isAdding}
                  className="btn-ghost"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddSubmit}
                  disabled={isAdding}
                  className="btn-primary flex items-center gap-2"
                >
                  {isAdding ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" /> Adding...
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4" /> Add Source
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="card-3d rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-lg bg-white/[0.04] flex items-center justify-center text-text-secondary">
          {icon}
        </div>
        <p className="label-field">{label}</p>
      </div>
      <p className="font-display text-2xl font-semibold text-text">{value}</p>
    </div>
  );
}
