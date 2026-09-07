import type { TransactionKind } from "@/api/types"

export const kindLabels: Record<TransactionKind, string> = {
  expense: "支出",
  income: "收入",
  refund: "退款",
  transfer: "转账",
  repayment: "还款",
}

export function formatCurrency(amountMinor: number, currency = "CNY") {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amountMinor / 100)
}

export function formatDateTime(value: string) {
  const parts = new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date(value))
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? ""
  return `${part("month")}月${part("day")}日 ${part("hour")}:${part("minute")}`
}

export function monthLabel(month: string) {
  const [year, monthNumber] = month.split("-").map(Number)
  return `${year}年${monthNumber}月`
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value)
}

export function toLocalDateTimeInput(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}
