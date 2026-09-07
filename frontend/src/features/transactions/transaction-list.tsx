import { PencilIcon, ReceiptTextIcon } from "lucide-react"

import type { Transaction } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatCurrency, formatDateTime, kindLabels } from "@/lib/format"

type Props = {
  items: Transaction[]
  onEdit: (transaction: Transaction) => void
}

export function TransactionList({ items, onEdit }: Props) {
  if (items.length === 0) {
    return (
      <Empty className="min-h-56 border">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <ReceiptTextIcon aria-hidden="true" />
          </EmptyMedia>
          <EmptyTitle>没有符合条件的记录</EmptyTitle>
          <EmptyDescription>换个筛选条件，或手动补一笔。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <>
      <div className="mobile-transaction-list md:hidden">
        {items.map((transaction) => {
          const isPositive =
            transaction.kind === "income" || transaction.kind === "refund"
          const displayName =
            transaction.merchant || kindLabels[transaction.kind]
          return (
            <article key={transaction.id} className="mobile-transaction">
              <header>
                <div className="min-w-0">
                  <h3 className="truncate font-medium" title={displayName}>
                    {displayName}
                  </h3>
                  <p className="truncate text-xs text-muted-foreground">
                    {formatDateTime(transaction.occurred_at)}
                    {transaction.channel ? ` · ${transaction.channel}` : ""}
                  </p>
                </div>
                <span
                  className={
                    isPositive
                      ? "font-medium text-income tabular-nums"
                      : "font-medium text-expense tabular-nums"
                  }
                >
                  {isPositive ? "+" : "−"}
                  {formatCurrency(
                    transaction.amount_minor,
                    transaction.currency
                  )}
                </span>
              </header>
              <dl>
                <div>
                  <dt>账户</dt>
                  <dd>{transaction.account_name}</dd>
                </div>
                <div>
                  <dt>分类</dt>
                  <dd>
                    {transaction.category_name ?? "待分类"}
                    {transaction.review_state === "pending" ? (
                      <Badge variant="outline" className="ml-2 text-review">
                        待确认
                      </Badge>
                    ) : null}
                  </dd>
                </div>
              </dl>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`编辑${displayName}`}
                onClick={() => onEdit(transaction)}
              >
                <PencilIcon data-icon="inline-start" aria-hidden="true" />
                编辑
              </Button>
            </article>
          )
        })}
      </div>

      <div className="hidden md:block">
        <Table aria-label="交易明细">
          <TableHeader>
            <TableRow>
              <TableHead>时间 / 商户</TableHead>
              <TableHead>账户</TableHead>
              <TableHead>分类</TableHead>
              <TableHead className="text-right">金额</TableHead>
              <TableHead>
                <span className="sr-only">操作</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((transaction) => {
              const isPositive =
                transaction.kind === "income" || transaction.kind === "refund"
              const displayName =
                transaction.merchant || kindLabels[transaction.kind]
              return (
                <TableRow key={transaction.id}>
                  <TableCell>
                    <div className="flex max-w-72 min-w-44 flex-col gap-1">
                      <span
                        className="truncate font-medium"
                        title={displayName}
                      >
                        {displayName}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {formatDateTime(transaction.occurred_at)}
                        {transaction.channel ? ` · ${transaction.channel}` : ""}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>{transaction.account_name}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span>{transaction.category_name ?? "待分类"}</span>
                      {transaction.review_state === "pending" ? (
                        <Badge variant="outline" className="text-review">
                          待确认
                        </Badge>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell
                    className={
                      isPositive
                        ? "text-right font-medium text-income"
                        : "text-right font-medium text-expense"
                    }
                  >
                    {isPositive ? "+" : "−"}
                    {formatCurrency(
                      transaction.amount_minor,
                      transaction.currency
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`编辑${displayName}`}
                      onClick={() => onEdit(transaction)}
                    >
                      <PencilIcon aria-hidden="true" />
                    </Button>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </>
  )
}
