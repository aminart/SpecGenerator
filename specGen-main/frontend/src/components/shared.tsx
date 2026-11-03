import { Braces } from "lucide-react";
import { formatSize, readJsonFile } from "../lib/files";
import type { LoadedFile } from "../lib/types";
import { AddFileButton, Field, FileChip } from "./fields";
import { useToast } from "./Toasts";

export const JsonIcon = () => <Braces className="h-[22px] w-[22px]" strokeWidth={1.8} />;

/** Component library field: one file shared by the context and spec pages. */
export function ComponentLibraryField({
  file,
  onChange,
  sharedWith,
}: {
  file: LoadedFile | null;
  onChange: (file: LoadedFile | null) => void;
  sharedWith: string;
}) {
  const toast = useToast();
  return (
    <Field label="JSON librairie composants" optional hint={file ? undefined : `Partagée avec l’étape « ${sharedWith} ».`}>
      {file ? (
        <FileChip icon={<JsonIcon />} name={file.name} detail={`${formatSize(file.size)} · partagée avec « ${sharedWith} »`} onRemove={() => onChange(null)} />
      ) : (
        <AddFileButton
          label="Ajouter un fichier .json"
          accept=".json"
          onFiles={async ([selected]) => {
            try {
              onChange(await readJsonFile(selected));
            } catch (error) {
              toast("error", (error as Error).message);
            }
          }}
        />
      )}
    </Field>
  );
}
