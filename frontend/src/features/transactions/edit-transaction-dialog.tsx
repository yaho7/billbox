import { useState } from "react"

import type { LedgerOptions, Transaction } from "@/api/types"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

type Props = {
  transaction: Transaction | null
  options: LedgerOptions
  onOpenChange: (open: boolean) => void
  onSave: (changes: {
    category_id: string | null
    note: string
    review_state: "confirmed"
  }) => Promise<void>
}

export function EditTransactionDialog({
  transaction,
  options,
  onOpenChange,
  onSave,
}: Props) {
  return (
    <Dialog open={Boolean(transaction)} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>确认这笔交易</DialogTitle>
          <DialogDescription>
            调整自动分类或备注，保存后标记为已确认。
          </DialogDescription>
        </DialogHeader>
        {transaction ? (
          <EditTransactionFields
            key={transaction.id}
            transaction={transaction}
            options={options}
            onSave={onSave}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function EditTransactionFields({
  transaction,
  options,
  onSave,
}: {
  transaction: Transaction
  options: LedgerOptions
  onSave: Props["onSave"]
}) {
  const [categoryId, setCategoryId] = useState(
    transaction.category_id ?? "__none__"
  )
  const [note, setNote] = useState(transaction.note)
  const [isSaving, setIsSaving] = useState(false)
  const categories = options.categories.filter(
    (category) =>
      category.scope === "both" ||
      category.scope ===
        (transaction.kind === "income" || transaction.kind === "refund"
          ? "income"
          : "expense")
  )

  async function handleSave() {
    setIsSaving(true)
    try {
      await onSave({
        category_id: categoryId === "__none__" ? null : categoryId,
        note: note.trim(),
        review_state: "confirmed",
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="edit-category">分类</FieldLabel>
          <Select
            name="category_id"
            value={categoryId}
            onValueChange={setCategoryId}
          >
            <SelectTrigger id="edit-category" className="w-full">
              <SelectValue placeholder="选择分类…" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="__none__">待分类</SelectItem>
                {categories.map((category) => (
                  <SelectItem key={category.id} value={category.id}>
                    {category.name}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel htmlFor="edit-note">备注</FieldLabel>
          <Input
            id="edit-note"
            name="note"
            autoComplete="off"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </Field>
      </FieldGroup>
      <DialogFooter>
        <Button type="button" onClick={handleSave} disabled={isSaving}>
          {isSaving ? "正在保存…" : "保存并确认"}
        </Button>
      </DialogFooter>
    </>
  )
}
