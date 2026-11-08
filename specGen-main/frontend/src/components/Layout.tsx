import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

/** Sources panel on the left, result area on the right. */
export function PageLayout({
  title,
  description,
  fields,
  footer,
  children,
}: {
  title: string;
  description: string;
  fields: ReactNode;
  footer: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-[calc(100vh-64px)] flex-wrap items-stretch">
      <aside className="flex max-w-full flex-[1_1_380px] flex-col border-r border-line bg-surface lg:sticky lg:top-16 lg:h-[calc(100vh-64px)] lg:max-w-[460px]">
        <div className="flex flex-1 flex-col gap-6 overflow-y-auto px-8 pb-6 pt-8">
          <div>
            <h1 className="text-[30px] font-bold leading-tight text-ink">{title}</h1>
            <p className="mt-2 text-sm leading-normal text-ink-muted">{description}</p>
          </div>
          {fields}
        </div>
        <div className="border-t border-line bg-surface px-8 pb-7 pt-5">{footer}</div>
      </aside>
      <main className="min-w-0 flex-[999_1_560px] p-4 sm:p-8 xl:p-12">{children}</main>
    </div>
  );
}

export function GenerateFooter({
  label,
  busyLabel,
  isBusy,
  disabledReason,
  onClick,
}: {
  label: string;
  busyLabel: string;
  isBusy: boolean;
  disabledReason: string | null;
  onClick: () => void;
}) {
  return (
    <div>
      <button
        type="button"
        onClick={onClick}
        disabled={isBusy || disabledReason !== null}
        className={`btn-primary min-h-[48px] w-full text-base ${isBusy ? "disabled:cursor-progress disabled:bg-navy-muted" : ""}`}
      >
        {isBusy && <Loader2 className="h-[18px] w-[18px] animate-spin" aria-hidden />}
        {isBusy ? busyLabel : label}
      </button>
      {disabledReason && !isBusy && <p className="mt-2 text-center text-[13px] text-ink-subtle">{disabledReason}</p>}
    </div>
  );
}
