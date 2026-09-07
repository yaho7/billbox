export type TransactionKind =
  "expense" | "income" | "refund" | "transfer" | "repayment"

export type ReviewState = "pending" | "confirmed"

export type Account = {
  id: string
  name: string
  kind: string
  currency: string
}

export type Category = {
  id: string
  name: string
  scope: "expense" | "income" | "both"
}

export type LedgerOptions = {
  accounts: Account[]
  categories: Category[]
}

export type Transaction = {
  id: string
  account_id: string
  account_name: string
  category_id: string | null
  category_name: string | null
  kind: TransactionKind
  amount_minor: number
  currency: string
  merchant: string
  note: string
  channel: string
  occurred_at: string
  review_state: ReviewState
}

export type TransactionPage = {
  items: Transaction[]
  total: number
  page: number
  page_size: number
  pages: number
}

export type Dashboard = {
  month: string
  expense_minor: number
  income_minor: number
  net_minor: number
  review_count: number
  categories: Array<{
    category_id: string
    category_name: string
    amount_minor: number
  }>
  daily: Array<{
    day: string
    expense_minor: number
    income_minor: number
  }>
}

export type JobRun = {
  id?: string
  job_name: string
  state: "never" | "running" | "succeeded" | "failed"
  started_at?: string
  finished_at?: string | null
  summary?: Record<string, unknown>
  log_text?: string
  error?: string | null
}

export type ManualTransaction = {
  account_id: string
  category_id: string | null
  kind: TransactionKind
  amount: string
  currency: string
  merchant: string
  note: string
  channel: string
  occurred_at: string
}

export type LedgerFilters = {
  month: string
  query: string
  account: string
  category: string
  kind: string
  review_state: string
  page: number
}
