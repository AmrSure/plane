/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlertTriangle, RefreshCw } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Loader } from "@plane/ui";
import { cn } from "@plane/utils";
// local imports
import { getErrorCode } from "./utils";

export function ReportChartLoader({ className }: { className?: string }) {
  return (
    <Loader className={cn("flex h-full w-full items-end gap-3 p-4", className)}>
      {[45, 70, 55, 90, 35, 65].map((height) => (
        <Loader.Item key={height} width="100%" height={`${height}%`} />
      ))}
    </Loader>
  );
}

type ErrorProps = {
  error: unknown;
  onRetry?: () => void;
  className?: string;
  timeoutKey?: string;
};

export function ReportChartError(props: ErrorProps) {
  const { error, onRetry, className, timeoutKey = "dashboards.widget.states.timeout" } = props;
  const { t } = useTranslation();
  const code = getErrorCode(error);
  return (
    <div className={cn("flex h-full w-full flex-col items-center justify-center gap-2 p-4 text-center", className)}>
      <AlertTriangle className="size-5 text-warning-primary" />
      <p className="text-13 text-secondary">
        {code === "query_timeout" ? t(timeoutKey) : t("dashboards.widget.states.error")}
      </p>
      {onRetry && (
        <Button variant="secondary" size="sm" prependIcon={<RefreshCw className="size-3" />} onClick={onRetry}>
          {t("dashboards.widget.states.retry")}
        </Button>
      )}
    </div>
  );
}

export function ReportChartEmpty({ className, message }: { className?: string; message?: string }) {
  const { t } = useTranslation();
  return (
    <div className={cn("flex h-full w-full items-center justify-center p-4 text-center", className)}>
      <p className="text-13 text-tertiary">{message ?? t("dashboards.widget.states.empty")}</p>
    </div>
  );
}
