import type { ReactNode } from "react";
import { FileUp, Layers, Monitor, Trash2 } from "lucide-react";
import type { Page } from "../lib/types";
import { APP_VERSION } from "../lib/version";

const CARDS: { page: Page; step: string; title: string; description: string; io: string[]; icon: ReactNode }[] = [
  {
    page: "markdown",
    step: "Étape 1 · optionnelle",
    title: "Convertir en Markdown",
    description: "Transformez un document existant (Word, PDF, PowerPoint, schéma draw.io…) en Markdown exploitable comme source de contexte.",
    io: ["DOCX, PDF, PPTX, XLSX, HTML, TXT, draw.io", "Fichier .md"],
    icon: <FileUp className="h-[22px] w-[22px]" strokeWidth={1.8} />,
  },
  {
    page: "context",
    step: "Étape 2",
    title: "Créer un contexte",
    description: "Générez le document d’architecture UX et le contexte global de l’application, avec ses parcours utilisateur.",
    io: ["Markdown, JSON global, librairie de composants", "DOCX, Markdown, HTML"],
    icon: <Layers className="h-[22px] w-[22px]" strokeWidth={1.8} />,
  },
  {
    page: "spec",
    step: "Étape 3",
    title: "Générer une spécification",
    description: "Produisez la spécification UX / HMI détaillée d’un écran ou d’un composant : variantes, états, comportements, erreurs.",
    io: ["Contexte, JSON écran, image de la feature", "DOCX, Markdown, HTML"],
    icon: <Monitor className="h-[22px] w-[22px]" strokeWidth={1.8} />,
  },
];

export function HomePage({ onNavigate, onReset, canReset }: { onNavigate: (page: Page) => void; onReset: () => void; canReset: boolean }) {
  return (
    <main className="mx-auto w-full max-w-[1240px] px-4 pb-16 pt-10 sm:px-8">
      <div className="nn-page-head mb-8">
        <div>
          <h1 className="nn-page-title">Générateur de spécifications</h1>
          <p className="nn-page-subtitle">
            Formalisez le contexte projet et générez la spécification UX / HMI de vos interfaces, prête à transmettre aux développeurs.
          </p>
        </div>
        <button
          type="button"
          onClick={onReset}
          disabled={!canReset}
          title={canReset ? "Effacer les fichiers et documents de ce poste" : "Rien à effacer"}
          className="nn-btn nn-btn-secondary disabled:opacity-50"
        >
          <Trash2 className="h-4 w-4" aria-hidden />
          Tout effacer
        </button>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-5">
        {CARDS.map((card, index) => (
          <section key={card.page} className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-6">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-[15px] font-bold text-accent-ink">{index + 1}</span>
              <span className="text-[13px] font-medium text-accent-ink">{card.step}</span>
              <span className="ml-auto text-ink-subtle" aria-hidden>{card.icon}</span>
            </div>
            <div className="flex flex-grow flex-col gap-2">
              <h2 className="text-[21px] font-bold text-ink">{card.title}</h2>
              <p className="text-[15px] leading-normal text-ink-body">{card.description}</p>
            </div>
            <dl className="grid grid-cols-[64px_minmax(0,1fr)] gap-y-1.5 rounded-md bg-surface-2 px-3.5 py-3 text-[13px]">
              <dt className="text-ink-subtle">Entrée</dt>
              <dd className="text-ink-body">{card.io[0]}</dd>
              <dt className="text-ink-subtle">Sortie</dt>
              <dd className="text-ink-body">{card.io[1]}</dd>
            </dl>
            <button
              type="button"
              onClick={() => onNavigate(card.page)}
              className="nn-btn nn-btn-secondary text-[15px]"
            >
              Commencer
            </button>
          </section>
        ))}
      </div>
      <p className="mt-10 text-[13px] text-ink-subtle">SpecGen v{APP_VERSION}</p>
    </main>
  );
}
