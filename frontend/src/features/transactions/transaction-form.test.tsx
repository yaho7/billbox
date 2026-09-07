import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import type { LedgerOptions } from "@/api/types"
import { TransactionForm } from "@/features/transactions/transaction-form"

const options = {
  accounts: [
    { id: "cash", name: "现金", kind: "cash", currency: "CNY" },
    { id: "cmb-credit", name: "招商信用卡", kind: "credit", currency: "CNY" },
  ],
  categories: [
    { id: "dining", name: "餐饮", scope: "expense" },
    { id: "salary", name: "工资", scope: "income" },
  ],
} satisfies LedgerOptions

describe("TransactionForm", () => {
  it("uses explicit labels and submits a normalized manual entry", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<TransactionForm options={options} onSubmit={onSubmit} />)

    expect(screen.getByLabelText("金额")).toBeVisible()
    expect(screen.getByLabelText("账户")).toBeVisible()
    expect(screen.getByLabelText("发生时间")).toBeVisible()

    await user.click(screen.getByRole("radio", { name: "收入" }))
    await user.type(screen.getByLabelText("金额"), "88.50")
    await user.type(screen.getByLabelText("商户或来源"), "退款到账")
    await user.click(screen.getByRole("button", { name: "保存记录" }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        account_id: "cash",
        amount: "88.50",
        kind: "income",
        merchant: "退款到账",
      })
    )
  })

  it("keeps the dialog open and shows validation when amount is missing", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<TransactionForm options={options} onSubmit={onSubmit} />)

    await user.click(screen.getByRole("button", { name: "保存记录" }))

    expect(screen.getByRole("alert")).toHaveTextContent("请输入大于 0 的金额")
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
