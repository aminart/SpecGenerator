import type { ReactNode } from "react";
import { FileUp, Layers, Monitor } from "lucide-react";
import type { Page } from "../lib/types";
import { APP_VERSION } from "../lib/version";

const CARDS: { page: Page; step: string; title: string; description: string; io: string[]; icon: ReactNode }[] = [
  {
    page: "markdown",
    step: "Étape 1 · optionnelle",
    title: "Convertir en Markdown",
    description: "Transformez un document existant (Word, PDF, PowerPoint, schéma draw.io…) en Markdown exploitable comme source de contexte.",
    io: ["Entrée : DOCX, PDF, PPTX, XLSX, HTML, TXT, draw.io", "Sortie : fichier .md"],
    icon: <FileUp className="h-[22px] w-[22px]" strokeWidth={1.8} />,
  },
  {
    page: "context",
    step: "Étape 2",
    title: "Créer un contexte",
    description: "Générez le document d’architecture UX et le contexte global de l’application, avec ses parcours utilisateur.",
    io: ["Entrée : Markdown(s), JSON global, librairie composants", "Sortie : DOCX, Markdown, HTML"],
    icon: <Layers className="h-[22px] w-[22px]" strokeWidth={1.8} />,
  },
  {
    page: "spec",
    step: "Étape 3",
    title: "Générer une spécification",
    description: "Produisez la spécification UX / HMI détaillée d’un écran ou d’un composant : variantes, états, comportements, erreurs.",
    io: ["Entrée : contexte, JSON écran, image de la feature", "Sortie : DOCX, Markdown, HTML"],
    icon: <Monitor className="h-[22px] w-[22px]" strokeWidth={1.8} />,
  },
];

export function HomePage({ onNavigate }: { onNavigate: (page: Page) => void }) {
  return (
    <main className="mx-auto w-full max-w-[1240px] px-4 pb-16 pt-14 sm:px-8 sm:pt-[88px]">
      <div className="mb-14 text-center">
        <h1 className="text-[32px] font-bold leading-tight text-accent sm:text-[40px]">Générateur de spécifications</h1>
        <p className="mx-auto mt-3.5 max-w-[640px] text-lg leading-normal text-ink-body">
          Formalisez le contexte projet et générez la spécification UX / HMI de vos interfaces, prête à transmettre aux développeurs.
        </p>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-6">
        {CARDS.map((card) => (
          <section key={card.page} className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-8 shadow-[0_1px_3px_rgba(16,24,64,0.06)]">
            <div className="flex items-center justify-between">
              <span className="flex h-11 w-11 items-center justify-center rounded-[10px] bg-navy-soft text-accent">{card.icon}</span>
              <span className="text-[13px] font-medium text-ink-subtle">{card.step}</span>
            </div>
            <h2 className="text-2xl font-bold text-accent">{card.title}</h2>
            <p className="text-[15px] leading-normal text-ink-body">{card.description}</p>
            <p className="text-[13px] leading-normal text-ink-subtle">
              {card.io[0]}
              <br />
              {card.io[1]}
            </p>
            <button
              type="button"
              onClick={() => onNavigate(card.page)}
              className="btn mt-auto min-h-[48px] border-[1.5px] border-accent text-[15px] text-accent hover:bg-navy hover:text-white"
            >
              Commencer
            </button>
          </section>
        ))}
      </div>
      <p className="mt-10 text-center text-[13px] text-ink-subtle">SpecGen v{APP_VERSION}</p>
    </main>
  );
}
