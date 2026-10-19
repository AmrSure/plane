/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { Check } from "lucide-react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TJiraImportConfig, TJiraImportDetail } from "@plane/types";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { cn } from "@plane/utils";
// hooks
import { useFileSize } from "@/hooks/use-file-size";
import { useAppRouter } from "@/hooks/use-app-router";
import { useUser } from "@/hooks/store/user";
// services
import type { TJiraImportApiError } from "@/services/jira-import.service";
import { JiraImportService } from "@/services/jira-import.service";
// local
import { IDENTIFIER_PATTERN, initialConfig } from "./helpers";
import { JiraImportMappingStep } from "./steps/mapping";
import { JiraImportOptionsStep } from "./steps/options";
import { JiraImportPeopleStep } from "./steps/people";
import { JiraImportProgressStep } from "./steps/progress";
import { JiraImportTargetStep } from "./steps/target";
import { JiraImportUploadStep } from "./steps/upload";

const service = new JiraImportService();

const STEPS = ["upload", "project", "mapping", "people", "options", "progress"] as const;
type TStep = (typeof STEPS)[number];

type Props = {
  workspaceSlug: string;
  isOpen: boolean;
  onClose: () => void;
  /** Continue an uploaded import, or re-run a finished one */
  importId?: string | null;
  onChanged: () => void;
};

export const JiraImportModal = observer(function JiraImportModal(props: Props) {
  const { workspaceSlug, isOpen, onClose, importId, onChanged } = props;
  const { t } = useTranslation();
  const router = useAppRouter();
  const { maxFileSize } = useFileSize();
  const { data: currentUser } = useUser();

  const [step, setStep] = useState<TStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [detail, setDetail] = useState<TJiraImportDetail | null>(null);
  const [config, setConfig] = useState<TJiraImportConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // A finished import opened again is re-run into the same project, so the project step is skipped
  const [isRerun, setIsRerun] = useState(false);

  // Reset, or load the import being continued, each time the modal opens
  useEffect(() => {
    if (!isOpen) return;
    setFile(null);
    setError(null);
    setDetail(null);
    setConfig(null);
    setIsRerun(false);
    setStep(importId ? "project" : "upload");
    if (!importId) return;
    service
      .retrieve(workspaceSlug, importId, true)
      .then((loaded) => {
        const rerun = loaded.status === "completed" || loaded.status === "failed";
        setIsRerun(rerun);
        setStep(rerun ? "mapping" : "project");
        setDetail(loaded);
        setConfig(initialConfig(loaded));
      })
      .catch(() => {
        setToast({ type: TOAST_TYPE.ERROR, title: t("importer.toast.load_failed") });
        onClose();
      });
  }, [isOpen, importId, workspaceSlug]); // eslint-disable-line react-hooks/exhaustive-deps

  const running = detail?.status === "queued" || detail?.status === "running";
  useSWR(
    step === "progress" && detail && running ? ["jira-import-progress", detail.id] : null,
    () => service.retrieve(workspaceSlug, detail!.id),
    {
      refreshInterval: 1500,
      onSuccess: (next) => {
        setDetail((previous) => (previous ? { ...previous, ...next } : next));
        if (next.status !== "queued" && next.status !== "running") onChanged();
      },
    }
  );

  const errorMessage = (apiError: TJiraImportApiError | undefined) => {
    const code = apiError?.code;
    return code
      ? t(`importer.errors.${code}`, { size: Math.round(maxFileSize / 1024 / 1024) })
      : t("importer.errors.generic");
  };

  const upload = async () => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) return setError(t("importer.errors.invalid_type"));
    if (file.size > maxFileSize)
      return setError(t("importer.errors.file_too_large", { size: Math.round(maxFileSize / 1024 / 1024) }));
    setBusy(true);
    setError(null);
    try {
      const uploaded = await service.upload(
        workspaceSlug,
        file,
        currentUser?.user_timezone || Intl.DateTimeFormat().resolvedOptions().timeZone
      );
      setDetail(uploaded);
      setConfig(initialConfig(uploaded));
      setStep("project");
      onChanged();
    } catch (apiError) {
      setError(errorMessage(apiError as TJiraImportApiError));
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    if (!detail || !config) return;
    setBusy(true);
    setError(null);
    try {
      const started = await service.start(workspaceSlug, detail.id, config);
      setDetail({ ...detail, ...started });
      setStep("progress");
      onChanged();
    } catch (apiError) {
      setError(errorMessage(apiError as TJiraImportApiError));
    } finally {
      setBusy(false);
    }
  };

  const visibleSteps = useMemo(
    () => STEPS.filter((s) => !(isRerun && s === "project") && !(importId && s === "upload")),
    [isRerun, importId]
  );
  const index = visibleSteps.indexOf(step);

  const canContinue = (() => {
    if (busy) return false;
    if (step === "upload") return Boolean(file);
    if (step === "project" && config?.target.mode === "new")
      return Boolean(config.target.name.trim()) && IDENTIFIER_PATTERN.test(config.target.identifier);
    return Boolean(config);
  })();

  const next = () => {
    setError(null);
    if (step === "upload") return void upload();
    if (step === "options") return void start();
    setStep(visibleSteps[index + 1]);
  };

  const back = () => {
    setError(null);
    if (index > 0) setStep(visibleSteps[index - 1]);
  };

  const finished = step === "progress" && !running;
  const projectLink = detail?.project ? `/${workspaceSlug}/projects/${detail.project.id}/issues` : null;

  const body = () => {
    if (step === "upload")
      return (
        <JiraImportUploadStep
          file={file}
          onFile={(f) => (setFile(f), setError(null))}
          error={error}
          maxSize={maxFileSize}
        />
      );
    if (!detail || !config) return <div className="h-48 animate-pulse rounded-md bg-layer-1" />;
    if (step === "project") return <JiraImportTargetStep detail={detail} config={config} onChange={setConfig} />;
    if (step === "mapping") return <JiraImportMappingStep detail={detail} config={config} onChange={setConfig} />;
    if (step === "people") return <JiraImportPeopleStep detail={detail} config={config} onChange={setConfig} />;
    if (step === "options") return <JiraImportOptionsStep detail={detail} config={config} onChange={setConfig} />;
    return <JiraImportProgressStep detail={detail} />;
  };

  return (
    <ModalCore
      isOpen={isOpen}
      handleClose={running ? () => {} : onClose}
      position={EModalPosition.TOP}
      width={EModalWidth.XXXL}
    >
      <div className="flex max-h-[85vh] flex-col">
        <div className="space-y-4 border-b border-subtle px-5 pt-5 pb-4">
          <div>
            <h3 className="text-18 font-medium text-primary">{t("importer.modal.title")}</h3>
            {detail && <p className="text-12 text-tertiary">{detail.file_name}</p>}
          </div>
          <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-12">
            {visibleSteps.map((s, i) => (
              <li key={s} className="flex items-center gap-2">
                <span
                  className={cn("flex size-5 items-center justify-center rounded-full text-11", {
                    "bg-accent-primary text-on-color": i === index,
                    "bg-success-subtle text-success-primary": i < index,
                    "bg-layer-2 text-tertiary": i > index,
                  })}
                >
                  {i < index ? <Check className="size-3" /> : i + 1}
                </span>
                <span className={cn({ "font-medium text-primary": i === index, "text-tertiary": i !== index })}>
                  {t(`importer.steps.${s}`)}
                </span>
                {i < visibleSteps.length - 1 && <span className="text-tertiary">·</span>}
              </li>
            ))}
          </ol>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">{body()}</div>

        {error && step !== "upload" && <p className="px-5 pb-2 text-12 text-danger-primary">{error}</p>}

        <div className="flex items-center justify-end gap-2 border-t border-subtle px-5 py-3">
          {step === "progress" ? (
            <>
              <Button variant="secondary" onClick={onClose} disabled={running}>
                {t("importer.modal.close")}
              </Button>
              {finished && projectLink && (
                <Button
                  variant="primary"
                  onClick={() => {
                    onClose();
                    router.push(projectLink);
                  }}
                >
                  {t("importer.modal.open_project")}
                </Button>
              )}
            </>
          ) : (
            <>
              <Button variant="secondary" onClick={index > 0 && !(importId && index === 0) ? back : onClose}>
                {index > 0 ? t("importer.modal.back") : t("cancel")}
              </Button>
              <Button variant="primary" onClick={next} disabled={!canContinue} loading={busy}>
                {step === "upload"
                  ? busy
                    ? t("importer.modal.analyzing")
                    : t("importer.modal.analyze")
                  : step === "options"
                    ? t("importer.modal.start")
                    : t("importer.modal.next")}
              </Button>
            </>
          )}
        </div>
      </div>
    </ModalCore>
  );
});
