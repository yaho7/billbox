import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { TransactionList } from "@/features/transactions/transaction-list"

const transaction = {
  id: "tx-1",
  account_id: "cmb-credit",
  account_name: "招商信用卡",
  category_id: null,
  category_name: null,
  kind: "expense" as const,
  amount_minor: 2680,
  currency: "CNY",
  merchant: "社区面包店",
  note: "",
  channel: "掌上生活",
  occurred_at: "2026-09-07T08:05:00+08:00",
  review_state: "pending" as const,
}

describe("TransactionList", () => {
  it("renders a semantic table and exposes pending review actions", async () => {
    const user = userEvent.setup()
    const onEdit = vi.fn()
    render(<TransactionList items={[transaction]} onEdit={onEdit} />)

    expect(screen.getByRole("table", { name: "交易明细" })).toBeVisible()
    expect(screen.getAllByText("社区面包店").length).toBeGreaterThan(0)
    expect(screen.getAllByText("待确认").length).toBeGreaterThan(0)

    await user.click(
      screen.getAllByRole("button", { name: "编辑社区面包店" })[0]
    )
    expect(onEdit).toHaveBeenCalledWith(transaction)
  })

  it("renders a useful empty state", () => {
    render(<TransactionList items={[]} onEdit={vi.fn()} />)

    expect(screen.getByText("没有符合条件的记录")).toBeVisible()
    expect(screen.getByText("换个筛选条件，或手动补一笔。")).toBeVisible()
  })
})
