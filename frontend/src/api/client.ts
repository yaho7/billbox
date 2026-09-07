import type {
  Dashboard,
  JobRun,
  LedgerFilters,
  LedgerOptions,
  ManualTransaction,
  Transaction,
  TransactionPage,
} from "@/api/types"

type Session =
  { authenticated: false } | { authenticated: true; csrf_token: string }

let csrfToken = ""

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) {
    headers.set("Content-Type", "application/json")
  }
  if (init.method && init.method !== "GET" && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken)
  }
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers,
  })
  if (!response.ok) {
    let message = "请求没有完成，请稍后重试"
    try {
      const payload = (await response.json()) as { detail?: string }
      message = payload.detail || message
    } catch {
      // Keep the useful fallback for non-JSON gateway errors.
    }
    throw new Error(message)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

function monthRange(month: string) {
  const [year, monthNumber] = month.split("-").map(Number)
  const lastDay = new Date(year, monthNumber, 0).getDate()
  return {
    date_from: `${month}-01`,
    date_to: `${month}-${String(lastDay).padStart(2, "0")}`,
  }
}

export const api = {
  async session() {
    const session = await request<Session>("/api/session")
    csrfToken = session.authenticated ? session.csrf_token : ""
    return session
  },

  async login(password: string) {
    await request<void>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    })
    return this.session()
  },

  async logout() {
    await request<void>("/api/auth/logout", { method: "POST" })
    csrfToken = ""
  },

  dashboard(month: string) {
    return request<Dashboard>(
      `/api/dashboard?${new URLSearchParams({ month }).toString()}`
    )
  },

  transactions(filters: LedgerFilters) {
    const params = new URLSearchParams({
      query: filters.query,
      account: filters.account,
      category: filters.category,
      kind: filters.kind,
      review_state: filters.review_state,
      page: String(filters.page),
      ...monthRange(filters.month),
    })
    return request<TransactionPage>(`/api/transactions?${params.toString()}`)
  },

  options() {
    return request<LedgerOptions>("/api/options")
  },

  latestJob() {
    return request<JobRun>("/api/jobs/latest")
  },

  createTransaction(transaction: ManualTransaction) {
    return request<Transaction>("/api/transactions", {
      method: "POST",
      body: JSON.stringify(transaction),
    })
  },

  updateTransaction(
    id: string,
    changes: {
      category_id?: string | null
      note?: string
      review_state?: "pending" | "confirmed"
    }
  ) {
    return request<Transaction>(`/api/transactions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    })
  },

  runIngestion() {
    return request<{ started: boolean }>("/api/jobs/ingest", {
      method: "POST",
    })
  },
}
