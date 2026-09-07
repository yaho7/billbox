import { useCallback, useEffect, useState } from "react"
import {
  CalendarDaysIcon,
  LogOutIcon,
  MoonIcon,
  PlusIcon,
  RefreshCwIcon,
  SunIcon,
} from "lucide-react"
import { toast } from "sonner"

import { api } from "@/api/client"
import type {
  Dashboard,
  JobRun,
  LedgerFilters,
  LedgerOptions,
  ManualTransaction,
  Transaction,
  TransactionPage,
} from "@/api/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Toaster } from "@/components/ui/sonner"
import { useTheme } from "@/components/theme-provider"
import { LoginPage } from "@/features/auth/login-page"
import { CategoryChart } from "@/features/dashboard/category-chart"
import { LedgerLoading } from "@/features/dashboard/ledger-loading"
import { SummaryCards } from "@/features/dashboard/summary-cards"
import { IngestionCard } from "@/features/jobs/ingestion-card"
import { EditTransactionDialog } from "@/features/transactions/edit-transaction-dialog"
import { LedgerFilterBar } from "@/features/transactions/ledger-filters"
import { TransactionForm } from "@/features/transactions/transaction-form"
import { TransactionList } from "@/features/transactions/transaction-list"
import { formatNumber, monthLabel } from "@/lib/format"

const EMPTY_OPTIONS: LedgerOptions = { accounts: [], categories: [] }

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`
}

function filtersFromUrl(): LedgerFilters {
  const params = new URLSearchParams(window.location.search)
  const month = params.get("month") ?? ""
  const page = Number(params.get("page"))
  return {
    month: /^\d{4}-(0[1-9]|1[0-2])$/.test(month) ? month : currentMonth(),
    query: params.get("query") ?? "",
    account: params.get("account") ?? "",
    category: params.get("category") ?? "",
    kind: params.get("kind") ?? "",
    review_state: params.get("review_state") ?? "",
    page: Number.isInteger(page) && page > 0 ? page : 1,
  }
}

function writeFiltersToUrl(filters: LedgerFilters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value && !(key === "page" && value === 1)) {
      params.set(key, String(value))
    }
  })
  const query = params.toString()
  window.history.replaceState(
    null,
    "",
    `${window.location.pathname}${query ? `?${query}` : ""}`
  )
}

function adjacentMonth(month: string, offset: number) {
  const [year, monthNumber] = month.split("-").map(Number)
  const next = new Date(year, monthNumber - 1 + offset, 1)
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`
}

export function App() {
  const [authentication, setAuthentication] = useState<
    "checking" | "in" | "out"
  >("checking")

  useEffect(() => {
    api
      .session()
      .then((session) =>
        setAuthentication(session.authenticated ? "in" : "out")
      )
      .catch(() => setAuthentication("out"))
  }, [])

  if (authentication === "checking") {
    return <AppBoot />
  }

  if (authentication === "out") {
    return (
      <>
        <a className="skip-link" href="#main-content">
          跳到主要内容
        </a>
        <LoginPage
          onLogin={async (password) => {
            await api.login(password)
            setAuthentication("in")
          }}
        />
        <Toaster position="top-center" />
      </>
    )
  }

  return (
    <LedgerApp
      onLogout={async () => {
        await api.logout()
        setAuthentication("out")
      }}
    />
  )
}

function AppBoot() {
  return (
    <main
      className="grid min-h-svh place-items-center bg-background"
      aria-label="正在验证登录状态"
    >
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <RefreshCwIcon className="animate-spin" aria-hidden="true" />
        正在打开账本…
      </div>
    </main>
  )
}

function LedgerApp({ onLogout }: { onLogout: () => Promise<void> }) {
  const { theme, setTheme } = useTheme()
  const [filters, setFilters] = useState(filtersFromUrl)
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [transactions, setTransactions] = useState<TransactionPage | null>(null)
  const [options, setOptions] = useState<LedgerOptions>(EMPTY_OPTIONS)
  const [job, setJob] = useState<JobRun>({
    job_name: "mail-ingestion",
    state: "never",
  })
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [editing, setEditing] = useState<Transaction | null>(null)

  const load = useCallback(async (nextFilters: LedgerFilters) => {
    setError("")
    try {
      const [nextDashboard, nextTransactions, nextOptions, nextJob] =
        await Promise.all([
          api.dashboard(nextFilters.month),
          api.transactions(nextFilters),
          api.options(),
          api.latestJob(),
        ])
      setDashboard(nextDashboard)
      setTransactions(nextTransactions)
      setOptions(nextOptions)
      setJob(nextJob)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "账本加载失败")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const timeout = window.setTimeout(
      () => load(filters),
      filters.query ? 220 : 0
    )
    return () => window.clearTimeout(timeout)
  }, [filters, load])

  useEffect(() => {
    function restoreFilters() {
      setFilters(filtersFromUrl())
    }
    window.addEventListener("popstate", restoreFilters)
    return () => window.removeEventListener("popstate", restoreFilters)
  }, [])

  function updateFilters(changes: Partial<LedgerFilters>) {
    setFilters((current) => {
      const next = { ...current, ...changes }
      writeFiltersToUrl(next)
      return next
    })
  }

  async function createTransaction(transaction: ManualTransaction) {
    setIsSaving(true)
    try {
      await api.createTransaction(transaction)
      setIsCreateOpen(false)
      toast.success("这笔记录已保存")
      await load(filters)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : "记录没有保存")
      throw caught
    } finally {
      setIsSaving(false)
    }
  }

  async function saveCorrection(changes: {
    category_id: string | null
    note: string
    review_state: "confirmed"
  }) {
    if (!editing) return
    try {
      await api.updateTransaction(editing.id, changes)
      setEditing(null)
      toast.success("分类已确认")
      await load(filters)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : "修改没有保存")
      throw caught
    }
  }

  async function runIngestion() {
    try {
      await api.runIngestion()
      toast.success("邮件抓取已开始")
      setJob((current) => ({ ...current, state: "running" }))
      window.setTimeout(() => load(filters), 1_200)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : "无法启动邮件抓取")
    }
  }

  return (
    <>
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <header className="app-header">
        <a className="brand" href="/" aria-label="Billbox 首页">
          <span className="brand-mark" aria-hidden="true" translate="no">
            B
          </span>
          <span>
            <strong translate="no">Billbox</strong>
            <small>私人账本</small>
          </span>
        </a>
        <nav aria-label="页面导航" className="header-nav">
          <a href="#ledger">本月账本</a>
          <a href="#automation">自动归集</a>
        </nav>
        <div className="header-actions">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={theme === "dark" ? "切换到浅色模式" : "切换到深色模式"}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? (
              <SunIcon aria-hidden="true" />
            ) : (
              <MoonIcon aria-hidden="true" />
            )}
          </Button>
          <Button type="button" variant="ghost" onClick={onLogout}>
            <LogOutIcon data-icon="inline-start" aria-hidden="true" />
            <span className="logout-label">退出</span>
          </Button>
        </div>
      </header>

      {isLoading && !dashboard ? (
        <LedgerLoading />
      ) : (
        <main className="app-main" id="main-content">
          <section className="page-heading" id="ledger">
            <div>
              <p className="eyebrow">MONTHLY OVERVIEW</p>
              <h1>{monthLabel(filters.month)}账本</h1>
              <p>先看结余，再处理系统标出的待确认账单。</p>
            </div>
            <div className="month-actions">
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  updateFilters({
                    month: adjacentMonth(filters.month, -1),
                    page: 1,
                  })
                }
                aria-label="查看上个月"
              >
                上月
              </Button>
              <label htmlFor="ledger-month" className="sr-only">
                选择月份
              </label>
              <div className="month-input-wrap">
                <CalendarDaysIcon aria-hidden="true" />
                <Input
                  id="ledger-month"
                  name="month"
                  type="month"
                  value={filters.month}
                  onChange={(event) =>
                    updateFilters({ month: event.target.value, page: 1 })
                  }
                />
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  updateFilters({
                    month: adjacentMonth(filters.month, 1),
                    page: 1,
                  })
                }
                aria-label="查看下个月"
              >
                下月
              </Button>
            </div>
          </section>

          {error ? (
            <Alert variant="destructive">
              <AlertTitle>账本暂时没有加载完整</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          {dashboard ? <SummaryCards dashboard={dashboard} /> : null}

          <section className="content-grid">
            {dashboard ? <CategoryChart dashboard={dashboard} /> : null}
            <IngestionCard job={job} onRun={runIngestion} />
          </section>

          <Card className="ledger-card">
            <CardHeader className="ledger-card-header">
              <div>
                <CardTitle>交易明细</CardTitle>
                <CardDescription>
                  {transactions
                    ? `共 ${formatNumber(transactions.total)} 笔，筛选条件会保留在网址中。`
                    : "正在读取…"}
                </CardDescription>
              </div>
              <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                <DialogTrigger asChild>
                  <Button type="button">
                    <PlusIcon data-icon="inline-start" aria-hidden="true" />
                    记一笔
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-xl">
                  <DialogHeader>
                    <DialogTitle>手动记账</DialogTitle>
                    <DialogDescription>
                      金额按人民币记录，数据保存在本机 SQLite。
                    </DialogDescription>
                  </DialogHeader>
                  <TransactionForm
                    options={options}
                    onSubmit={createTransaction}
                    isSaving={isSaving}
                  />
                </DialogContent>
              </Dialog>
            </CardHeader>
            <Separator />
            <CardContent className="flex flex-col gap-4">
              <LedgerFilterBar
                filters={filters}
                options={options}
                onChange={updateFilters}
              />
              <TransactionList
                items={transactions?.items ?? []}
                onEdit={setEditing}
              />
              {transactions && transactions.pages > 1 ? (
                <nav className="pagination" aria-label="交易明细分页">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={transactions.page <= 1}
                    onClick={() =>
                      updateFilters({ page: transactions.page - 1 })
                    }
                  >
                    上一页
                  </Button>
                  <span aria-live="polite">
                    第 {formatNumber(transactions.page)} /{" "}
                    {formatNumber(transactions.pages)} 页
                  </span>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={transactions.page >= transactions.pages}
                    onClick={() =>
                      updateFilters({ page: transactions.page + 1 })
                    }
                  >
                    下一页
                  </Button>
                </nav>
              ) : null}
            </CardContent>
          </Card>
        </main>
      )}

      <EditTransactionDialog
        transaction={editing}
        options={options}
        onOpenChange={(open) => !open && setEditing(null)}
        onSave={saveCorrection}
      />
      <Toaster position="top-center" />
    </>
  )
}

export default App
