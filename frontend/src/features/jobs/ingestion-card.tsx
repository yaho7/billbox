import {
  CircleCheckIcon,
  CircleXIcon,
  LoaderCircleIcon,
  MailSearchIcon,
  PlayIcon,
} from "lucide-react"

import type { JobRun } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { formatDateTime } from "@/lib/format"

type Props = {
  job: JobRun
  onRun: () => Promise<void>
}

const states = {
  never: {
    label: "尚未运行",
    icon: MailSearchIcon,
    variant: "outline" as const,
  },
  running: {
    label: "正在抓取",
    icon: LoaderCircleIcon,
    variant: "secondary" as const,
  },
  succeeded: {
    label: "最近成功",
    icon: CircleCheckIcon,
    variant: "secondary" as const,
  },
  failed: {
    label: "最近失败",
    icon: CircleXIcon,
    variant: "destructive" as const,
  },
}

export function IngestionCard({ job, onRun }: Props) {
  const state = states[job.state]
  const Icon = state.icon
  return (
    <Card id="automation">
      <CardHeader>
        <CardTitle>邮件自动归集</CardTitle>
        <CardDescription>
          定时读取已配置邮箱，按邮件 UID 去重后写入账本。
        </CardDescription>
        <CardAction>
          <Badge variant={state.variant}>
            <Icon
              aria-hidden="true"
              data-icon="inline-start"
              className={job.state === "running" ? "animate-spin" : undefined}
            />
            {state.label}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <dl className="job-meta">
          <div>
            <dt>开始时间</dt>
            <dd>
              {job.started_at ? formatDateTime(job.started_at) : "等待首次运行"}
            </dd>
          </div>
          <div>
            <dt>结束时间</dt>
            <dd>{job.finished_at ? formatDateTime(job.finished_at) : "—"}</dd>
          </div>
        </dl>
        {job.error ? (
          <p className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            {job.error}
          </p>
        ) : null}
        {job.log_text ? (
          <details>
            <summary className="cursor-pointer text-sm font-medium">
              查看最近日志
            </summary>
            <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-muted p-3 text-xs whitespace-pre-wrap">
              {job.log_text}
            </pre>
          </details>
        ) : null}
        <div>
          <Button
            type="button"
            variant="outline"
            onClick={onRun}
            disabled={job.state === "running"}
          >
            <PlayIcon data-icon="inline-start" aria-hidden="true" />
            立即抓取
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
