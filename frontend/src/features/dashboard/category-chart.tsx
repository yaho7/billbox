import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

import type { Dashboard } from "@/api/types"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { formatCurrency } from "@/lib/format"

const config = {
  amount: {
    label: "支出",
    color: "var(--chart-1)",
  },
} satisfies ChartConfig

type Props = {
  dashboard: Dashboard
}

export function CategoryChart({ dashboard }: Props) {
  const data = dashboard.categories.slice(0, 7).map((item) => ({
    category: item.category_name,
    amount: item.amount_minor,
  }))

  return (
    <Card className="chart-card">
      <CardHeader>
        <CardTitle>支出去向</CardTitle>
        <CardDescription>按分类汇总，展示金额最高的 7 项。</CardDescription>
      </CardHeader>
      <CardContent>
        {data.length ? (
          <ChartContainer
            config={config}
            className="h-64 w-full"
            aria-label="分类支出图表"
            role="img"
          >
            <BarChart
              accessibilityLayer
              data={data}
              layout="vertical"
              margin={{ left: 0, right: 12 }}
            >
              <CartesianGrid horizontal={false} />
              <XAxis type="number" hide domain={[0, "dataMax"]} />
              <YAxis
                dataKey="category"
                type="category"
                tickLine={false}
                axisLine={false}
                width={72}
              />
              <ChartTooltip
                cursor={false}
                content={
                  <ChartTooltipContent
                    hideLabel
                    formatter={(value) => (
                      <span className="font-medium tabular-nums">
                        {formatCurrency(Number(value))}
                      </span>
                    )}
                  />
                }
              />
              <Bar
                dataKey="amount"
                fill="var(--color-amount)"
                radius={[0, 6, 6, 0]}
              />
            </BarChart>
          </ChartContainer>
        ) : (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
            本月还没有支出数据
          </div>
        )}
      </CardContent>
    </Card>
  )
}
