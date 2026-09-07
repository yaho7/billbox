import { useRef, useState, type FormEvent } from "react"

import type {
  LedgerOptions,
  ManualTransaction,
  TransactionKind,
} from "@/api/types"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { kindLabels, toLocalDateTimeInput } from "@/lib/format"

type Props = {
  options: LedgerOptions
  onSubmit: (transaction: ManualTransaction) => Promise<void>
  isSaving?: boolean
}

const orderedKinds: TransactionKind[] = [
  "expense",
  "income",
  "refund",
  "transfer",
  "repayment",
]

export function TransactionForm({
  options,
  onSubmit,
  isSaving = false,
}: Props) {
  const [kind, setKind] = useState<TransactionKind>("expense")
  const [amount, setAmount] = useState("")
  const [accountId, setAccountId] = useState(options.accounts[0]?.id ?? "")
  const [categoryId, setCategoryId] = useState("__none__")
  const [merchant, setMerchant] = useState("")
  const [note, setNote] = useState("")
  const [occurredAt, setOccurredAt] = useState(toLocalDateTimeInput())
  const [errors, setErrors] = useState<{
    amount?: string
    account?: string
    occurredAt?: string
  }>({})
  const amountInput = useRef<HTMLInputElement>(null)
  const timeInput = useRef<HTMLInputElement>(null)

  const availableCategories = options.categories.filter(
    (category) =>
      category.scope === "both" ||
      category.scope ===
        (kind === "income" || kind === "refund" ? "income" : "expense")
  )

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const amountNumber = Number(amount)
    if (!Number.isFinite(amountNumber) || amountNumber <= 0) {
      setErrors({ amount: "请输入大于 0 的金额" })
      amountInput.current?.focus()
      return
    }
    if (!accountId) {
      setErrors({ account: "请先选择账户" })
      return
    }
    const occurredDate = new Date(occurredAt)
    if (!occurredAt || Number.isNaN(occurredDate.getTime())) {
      setErrors({ occurredAt: "请选择有效的发生时间" })
      timeInput.current?.focus()
      return
    }
    setErrors({})
    await onSubmit({
      account_id: accountId,
      category_id: categoryId === "__none__" ? null : categoryId,
      kind,
      amount: amountNumber.toFixed(2),
      currency: "CNY",
      merchant: merchant.trim(),
      note: note.trim(),
      channel: "手动记录",
      occurred_at: occurredDate.toISOString(),
    })
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <FieldGroup>
        <FieldSet>
          <FieldLegend>收支类型</FieldLegend>
          <ToggleGroup
            type="single"
            value={kind}
            onValueChange={(value) =>
              value && setKind(value as TransactionKind)
            }
            variant="outline"
            spacing={0}
            className="grid w-full grid-cols-3 sm:grid-cols-5"
          >
            {orderedKinds.map((value) => (
              <ToggleGroupItem
                key={value}
                value={value}
                role="radio"
                aria-checked={kind === value}
                className="w-full"
              >
                {kindLabels[value]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </FieldSet>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field data-invalid={Boolean(errors.amount)}>
            <FieldLabel htmlFor="transaction-amount">金额</FieldLabel>
            <Input
              id="transaction-amount"
              ref={amountInput}
              name="amount"
              type="number"
              inputMode="decimal"
              min="0.01"
              step="0.01"
              autoComplete="off"
              placeholder="0.00"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              aria-invalid={Boolean(errors.amount)}
            />
            {errors.amount ? <FieldError>{errors.amount}</FieldError> : null}
          </Field>

          <Field data-invalid={Boolean(errors.account)}>
            <FieldLabel htmlFor="transaction-account">账户</FieldLabel>
            <Select
              name="account_id"
              value={accountId}
              onValueChange={setAccountId}
            >
              <SelectTrigger id="transaction-account" className="w-full">
                <SelectValue placeholder="选择账户…" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {options.accounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            {errors.account ? <FieldError>{errors.account}</FieldError> : null}
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field>
            <FieldLabel htmlFor="transaction-category">分类</FieldLabel>
            <Select
              name="category_id"
              value={categoryId}
              onValueChange={setCategoryId}
            >
              <SelectTrigger id="transaction-category" className="w-full">
                <SelectValue placeholder="选择分类…" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="__none__">稍后分类</SelectItem>
                  {availableCategories.map((category) => (
                    <SelectItem key={category.id} value={category.id}>
                      {category.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>

          <Field data-invalid={Boolean(errors.occurredAt)}>
            <FieldLabel htmlFor="transaction-time">发生时间</FieldLabel>
            <Input
              id="transaction-time"
              ref={timeInput}
              name="occurred_at"
              type="datetime-local"
              autoComplete="off"
              value={occurredAt}
              onChange={(event) => setOccurredAt(event.target.value)}
              aria-invalid={Boolean(errors.occurredAt)}
            />
            {errors.occurredAt ? (
              <FieldError>{errors.occurredAt}</FieldError>
            ) : null}
          </Field>
        </div>

        <Field>
          <FieldLabel htmlFor="transaction-merchant">商户或来源</FieldLabel>
          <Input
            id="transaction-merchant"
            name="merchant"
            autoComplete="off"
            placeholder="例如：社区面包店…"
            value={merchant}
            onChange={(event) => setMerchant(event.target.value)}
          />
        </Field>

        <Field>
          <FieldLabel htmlFor="transaction-note">备注</FieldLabel>
          <Input
            id="transaction-note"
            name="note"
            autoComplete="off"
            placeholder="可选…"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
          <FieldDescription>保存后仍可修改分类和备注。</FieldDescription>
        </Field>

        <Button type="submit" size="lg" disabled={isSaving}>
          {isSaving ? "正在保存…" : "保存记录"}
        </Button>
      </FieldGroup>
    </form>
  )
}
