import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { usePickedModel } from "../lib/modelChoice";
import type { ModelOptions } from "../lib/types";
import { Field } from "./fields";

const label = (options: ModelOptions, id: string | null) => {
  const option = options.options.find((o) => o.id === id);
  return option ? `${option.model} · ${option.connection}` : "";
};

/** Models grouped by Studio Dock connection, for a <select>. */
export function ModelOptionGroups({ options }: { options: ModelOptions }) {
  const groups = options.options.reduce<Record<string, ModelOptions["options"]>>((acc, o) => {
    (acc[o.connection] ??= []).push(o);
    return acc;
  }, {});
  return (
    <>
      {Object.entries(groups).map(([connection, models]) => (
        <optgroup key={connection} label={connection}>
          {models.map((o) => <option key={o.id} value={o.id}>{o.model}</option>)}
        </optgroup>
      ))}
    </>
  );
}

/** Model used for this generation, among those set in Studio Dock. Hidden when Studio Dock offers no choice. */
export function ModelField() {
  const [options, setOptions] = useState<ModelOptions | null>(null);
  const [picked, pick] = usePickedModel();

  useEffect(() => {
    api.models().then(setOptions).catch(() => setOptions(null));
  }, []);

  if (!options?.available || options.options.length < 2) return null;
  const value = picked && options.options.some((o) => o.id === picked) ? picked : "";
  return (
    <Field label="Modèle d’IA" hint="Valable pour cette session. Le modèle par défaut se règle dans Paramètres.">
      <select
        aria-label="Modèle d’IA"
        value={value}
        onChange={(event) => pick(event.target.value || null)}
        className="min-h-[44px] w-full rounded-lg border border-line-strong bg-surface px-3 text-[15px] text-ink focus:border-accent focus:outline-none focus:ring-[3px] focus:ring-navy-soft"
      >
        <option value="">Par défaut : {label(options, options.default)}</option>
        <ModelOptionGroups options={options} />
      </select>
    </Field>
  );
}
