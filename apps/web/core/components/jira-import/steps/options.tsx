/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";
import type { TJiraImportConfig, TJiraImportDetail, TJiraImportOptions } from "@plane/types";
import { ToggleSwitch } from "@plane/ui";
import { cn } from "@plane/utils";
// local
import { keepsKeys, targetProject } from "../helpers";

type Props = {
  detail: TJiraImportDetail;
  config: TJiraImportConfig;
  onChange: (config: TJiraImportConfig) => void;
};

type TToggleKey = Exclude<keyof TJiraImportOptions, "on_existing">;

export function JiraImportOptionsStep(props: Props) {
  const { detail, config, onChange } = props;
  const { t } = useTranslation();
  const { analysis } = detail;
  const features = analysis.features;
  const canKeepKeys = keepsKeys(detail, config);
  const isRerun = detail.status === "completed" || detail.status === "failed";

  const toggles: { key: TToggleKey; available: boolean; count?: number }[] = [
    { key: "keep_keys", available: canKeepKeys },
    { key: "sprints_as_cycles", available: analysis.sprints.length > 0, count: analysis.sprints.length },
    { key: "epics_as_modules", available: analysis.epics.length > 0, count: analysis.epics.length },
    { key: "issue_types_as_labels", available: analysis.issue_types.length > 0, count: analysis.issue_types.length },
    { key: "comments", available: features.comments },
    { key: "attachments", available: features.attachments },
    { key: "watchers", available: features.watchers },
  ];

  const setOption = (key: keyof TJiraImportOptions, value: boolean | "update" | "skip") =>
    onChange({ ...config, options: { ...config.options, [key]: value } });

  const unmapped = analysis.users.filter((user) => !config.user_map[user.id]).length;
  const createdStates = Object.values(config.status_map).filter((choice) => choice.mode === "create").length;
  const target =
    config.target.mode === "new"
      ? `${config.target.name} (${config.target.identifier})`
      : (targetProject(detail, config)?.name ?? "");

  return (
    <div className="space-y-5">
      <div className="divide-y divide-subtle rounded-md border border-subtle">
        {toggles.map((toggle) => (
          <div
            key={toggle.key}
            className={cn("flex items-center gap-3 px-3 py-2.5", { "opacity-50": !toggle.available })}
          >
            <div className="min-w-0 flex-1">
              <div className="text-13 font-medium text-primary">
                {t(`importer.options.${toggle.key}.title`)}
                {toggle.count !== undefined && toggle.available && (
                  <span className="font-normal ms-1.5 text-12 text-tertiary">({toggle.count})</span>
                )}
              </div>
              <div className="text-12 text-tertiary">
                {toggle.available ? t(`importer.options.${toggle.key}.description`) : t("importer.options.not_in_file")}
              </div>
            </div>
            <ToggleSwitch
              value={toggle.available && config.options[toggle.key]}
              onChange={() => toggle.available && setOption(toggle.key, !config.options[toggle.key])}
              disabled={!toggle.available}
              size="sm"
            />
          </div>
        ))}
        <div className="flex items-center gap-3 px-3 py-2.5">
          <div className="min-w-0 flex-1">
            <div className="text-13 font-medium text-primary">{t("importer.options.on_existing.title")}</div>
            <div className="text-12 text-tertiary">{t("importer.options.on_existing.description")}</div>
          </div>
          <div className="flex overflow-hidden rounded-md border border-subtle text-12">
            {(["update", "skip"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setOption("on_existing", mode)}
                className={cn("px-3 py-1", {
                  "bg-accent-primary text-on-color": config.options.on_existing === mode,
                  "text-secondary hover:bg-layer-1": config.options.on_existing !== mode,
                })}
              >
                {t(`importer.options.on_existing.${mode}`)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-md bg-layer-1 p-4 text-12 text-secondary">
        <div className="mb-2 text-13 font-medium text-primary">{t("importer.review.title")}</div>
        <ul className="list-disc space-y-1 ps-4">
          <li>{t("importer.review.target", { project: target })}</li>
          <li>{t("importer.review.work_items", { count: analysis.work_item_count })}</li>
          {createdStates > 0 && <li>{t("importer.review.new_states", { count: createdStates })}</li>}
          {config.options.sprints_as_cycles && analysis.sprints.length > 0 && (
            <li>{t("importer.review.cycles", { count: analysis.sprints.length })}</li>
          )}
          {unmapped > 0 && <li>{t("importer.review.unmapped", { count: unmapped })}</li>}
          {isRerun && <li>{t("importer.review.rerun")}</li>}
          <li>{t("importer.review.silent")}</li>
        </ul>
      </div>
    </div>
  );
}
