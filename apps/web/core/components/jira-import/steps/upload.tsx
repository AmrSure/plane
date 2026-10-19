/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef, useState } from "react";
import { FileUp } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
// local
import { formatBytes } from "../helpers";

type Props = {
  file: File | null;
  onFile: (file: File) => void;
  error: string | null;
  maxSize: number;
};

export function JiraImportUploadStep(props: Props) {
  const { file, onFile, error, maxSize } = props;
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pick = (files: FileList | null) => {
    const picked = files?.[0];
    if (picked) onFile(picked);
  };

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          pick(event.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-subtle px-6 py-10 text-center transition-colors hover:bg-layer-1",
          { "border-accent-strong bg-layer-1": dragging, "border-danger-strong": Boolean(error) }
        )}
      >
        <FileUp className="size-8 text-tertiary" />
        <span className="text-14 font-medium text-primary">{file ? file.name : t("importer.upload.drop_title")}</span>
        <span className="text-12 text-tertiary">
          {file ? formatBytes(file.size) : t("importer.upload.drop_hint", { size: formatBytes(maxSize) })}
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(event) => {
          pick(event.target.files);
          event.target.value = "";
        }}
      />
      {error && <p className="text-12 text-danger-primary">{error}</p>}
      <div className="rounded-md bg-layer-1 p-4 text-12 text-secondary">
        <p className="mb-2 font-medium text-primary">{t("importer.upload.how_title")}</p>
        <ol className="list-decimal space-y-1 ps-4">
          <li>{t("importer.upload.how_step_1")}</li>
          <li>{t("importer.upload.how_step_2")}</li>
          <li>{t("importer.upload.how_step_3")}</li>
        </ol>
      </div>
    </div>
  );
}
