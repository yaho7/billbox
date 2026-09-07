import {
  ArrowDownLeftIcon,
  ArrowUpRightIcon,
  CircleAlertIcon,
  WalletCardsIcon,
} from "lucide-react"

import type { Dashboard } from "@/api/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatCurrency, formatNumber } from "@/lib/format"

type Props = {
  dashboard: Dashboard
}

const summaries = [
  {
    key: "expense_minor" as const,
    label: "本月支出",
    icon: ArrowUpRightIcon,
    tone: "text-expense",
  },
  {
    key: "income_minor" as const,
    label: "本月收入",
    icon: ArrowDownLeftIcon,
    tone: "text-income",
  },
  {
    key: "net_minor" as const,
    label: "本月结余",
    icon: WalletCardsIcon,
    tone: "text-foreground",
  },
]

export function SummaryCards({ dashboard }: Props) {
  return (
    <section className="summary-grid" aria-label="本月概览">
      {summaries.map(({ key, label, icon: Icon, tone }) => (
        <Card key={key} size="sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
              <Icon aria-hidden="true" />
              {label}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p
              className={`text-2xl font-semibold tracking-tight tabular-nums ${tone}`}
            >
              {formatCurrency(dashboard[key])}
            </p>
          </CardContent>
        </Card>
      ))}
      <Card size="sm" className="review-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
            <CircleAlertIcon aria-hidden="true" />
            待确认
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold tracking-tight text-review tabular-nums">
            {formatNumber(dashboard.review_count)} 笔
          </p>
        </CardContent>
      </Card>
    </section>
  )
}
