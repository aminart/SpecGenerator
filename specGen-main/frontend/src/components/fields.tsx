import { useId, useRef, useState, type DragEvent, type ReactNode } from "react";
import { CloudUpload, Plus, X } from "lucide-react";
import type { Language } from "../lib/types";

export function Field({ label, optional, hint, children }: { label: string; optional?: boolean; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="field-label">
        {label} {optional && <span className="font-normal text-ink-subtle">(optionnel)</span>}
      </span>
      {children}
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}

function useFileDrop(onFiles: (files: File[]) => void, multiple: boolean) {
  const [isDragging, setIsDragging] = useState(false);
  return {
    isDragging,
    dropHandlers: {
      onDragOver: (event: DragEvent) => {
        event.preventDefault();
        setIsDragging(true);
      },
      onDragLeave: () => setIsDragging(false),
      onDrop: (event: DragEvent) => {
        event.preventDefault();
        setIsDragging(false);
        const files = Array.from(event.dataTransfer.files);
        if (files.length) onFiles(multiple ? files : files.slice(0, 1));
      },
    },
  };
}

function HiddenFileInput({ id, accept, multiple, onFiles }: { id: string; accept: string; multiple: boolean; onFiles: (files: File[]) => void }) {
  return (
    <input
      id={id}
      type="file"
      className="hidden"
      accept={accept}
      multiple={multiple}
      onChange={(event) => {
        const files = Array.from(event.target.files ?? []);
        if (files.length) onFiles(files);
        event.target.value = "";
      }}
    />
  );
}

/** Large drop area, shown while a field is still empty. */
export function LargeDropzone({
  accept,
  multiple = false,
  formats,
  onFiles,
}: {
  accept: string;
  multiple?: boolean;
  formats: string;
  onFiles: (files: File[]) => void;
}) {
  const id = useId();
  const { isDragging, dropHandlers } = useFileDrop(onFiles, multiple);
  return (
    <>
      <label
        htmlFor={id}
        {...dropHandlers}
        className={`flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border-[1.5px] border-dashed px-6 py-7 text-center transition hover:border-accent hover:bg-navy-softer ${
          isDragging ? "border-accent bg-navy-softer" : "border-line-dashed bg-surface-2"
        }`}
      >
        <CloudUpload className="h-9 w-9 text-ink-subtle" strokeWidth={1.5} aria-hidden />
        <span className="text-[15px] text-ink-body">
          Glissez-déposez {multiple ? "vos fichiers" : "le fichier"} ou <span className="font-medium text-accent underline">parcourir</span>
        </span>
        <span className="text-xs text-ink-subtle">{formats}</span>
      </label>
      <HiddenFileInput id={id} accept={accept} multiple={multiple} onFiles={onFiles} />
    </>
  );
}

/** Compact dashed button to add more files once a field already has some. */
export function AddFileButton({
  label,
  accept,
  multiple = false,
  onFiles,
}: {
  label: string;
  accept: string;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
}) {
  const id = useId();
  const { isDragging, dropHandlers } = useFileDrop(onFiles, multiple);
  return (
    <>
      <label
        htmlFor={id}
        {...dropHandlers}
        className={`flex min-h-[44px] cursor-pointer items-center justify-center gap-2 rounded-lg border-[1.5px] border-dashed text-sm font-medium text-accent transition hover:border-accent hover:bg-navy-softer ${
          isDragging ? "border-accent bg-navy-softer" : "border-line-dashed"
        }`}
      >
        <Plus className="h-4 w-4" aria-hidden />
        {label}
      </label>
      <HiddenFileInput id={id} accept={accept} multiple={multiple} onFiles={onFiles} />
    </>
  );
}

export function FileChip({
  icon,
  name,
  detail,
  detailTone = "muted",
  highlighted,
  onRemove,
  action,
}: {
  icon: ReactNode;
  name: string;
  detail?: ReactNode;
  detailTone?: "muted" | "success" | "error";
  highlighted?: boolean;
  onRemove?: () => void;
  action?: ReactNode;
}) {
  const toneClass = detailTone === "success" ? "text-success-text" : detailTone === "error" ? "text-danger-text" : "text-ink-muted";
  return (
    <div
      className={`flex items-center gap-3 rounded-lg px-3.5 py-3 ${
        highlighted ? "border-[1.5px] border-accent bg-navy-softer" : "border border-line-strong bg-surface"
      }`}
    >
      <span className="shrink-0 text-accent">{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-ink" title={name}>
          {name}
        </div>
        {detail && <div className={`flex items-center gap-1.5 text-xs ${toneClass}`}>{detail}</div>}
      </div>
      {action}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Retirer ${name}`}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-ink-subtle hover:bg-surface-3 hover:text-ink"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export function LanguageField({ value, onChange }: { value: Language; onChange: (value: Language) => void }) {
  const options: { value: Language; label: string }[] = [
    { value: "fr", label: "Français" },
    { value: "en", label: "English" },
  ];
  return (
    <Field label="Langue de sortie">
      <div role="radiogroup" aria-label="Langue de sortie" className="flex rounded-lg bg-surface-3 p-1">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={value === option.value}
            onClick={() => onChange(option.value)}
            className={`min-h-[36px] flex-1 rounded-md text-sm transition ${
              value === option.value ? "bg-surface font-medium text-ink shadow-[0_1px_2px_rgba(16,24,64,0.12)]" : "text-ink-muted hover:text-ink"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </Field>
  );
}

/** Triggers a hidden file input from a text link. */
export function FileLink({ accept, onFiles, children }: { accept: string; onFiles: (files: File[]) => void; children: ReactNode }) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <button type="button" className="font-medium text-accent underline hover:text-accent-ink" onClick={() => inputRef.current?.click()}>
        {children}
      </button>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept={accept}
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          if (files.length) onFiles(files);
          event.target.value = "";
        }}
      />
    </>
  );
}
