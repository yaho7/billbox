import { SearchIcon } from "lucide-react"

import type { LedgerFilters, LedgerOptions } from "@/api/types"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { kindLabels } from "@/lib/format"

type Props = {
  filters: LedgerFilters
  options: LedgerOptions
  onChange: (changes: Partial<LedgerFilters>) => void
}

const ALL = "__all__"

export function LedgerFilterBar({ filters, options, onChange }: Props) {
  return (
    <div className="filter-grid" aria-label="交易筛选">
      <Field className="search-field">
        <FieldLabel htmlFor="transaction-search" className="sr-only">
          搜索商户或备注
        </FieldLabel>
        <div className="relative">
          <SearchIcon
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            id="transaction-search"
            name="query"
            type="search"
            autoComplete="off"
            placeholder="搜索商户或备注…"
            value={filters.query}
            onChange={(event) =>
              onChange({ query: event.target.value, page: 1 })
            }
            className="pl-8"
          />
        </div>
      </Field>

      <FilterSelect
        label="账户"
        value={filters.account || ALL}
        onValueChange={(value) =>
          onChange({ account: value === ALL ? "" : value, page: 1 })
        }
        items={options.accounts.map((account) => ({
          value: account.id,
          label: account.name,
        }))}
      />
      <FilterSelect
        label="分类"
        value={filters.category || ALL}
        onValueChange={(value) =>
          onChange({ category: value === ALL ? "" : value, page: 1 })
        }
        items={options.categories.map((category) => ({
          value: category.id,
          label: category.name,
        }))}
      />
      <FilterSelect
        label="类型"
        value={filters.kind || ALL}
        onValueChange={(value) =>
          onChange({ kind: value === ALL ? "" : value, page: 1 })
        }
        items={Object.entries(kindLabels).map(([value, label]) => ({
          value,
          label,
        }))}
      />
      <FilterSelect
        label="确认状态"
        value={filters.review_state || ALL}
        onValueChange={(value) =>
          onChange({ review_state: value === ALL ? "" : value, page: 1 })
        }
        items={[
          { value: "pending", label: "待确认" },
          { value: "confirmed", label: "已确认" },
        ]}
      />
    </div>
  )
}

function FilterSelect({
  label,
  value,
  onValueChange,
  items,
}: {
  label: string
  value: string
  onValueChange: (value: string) => void
  items: Array<{ value: string; label: string }>
}) {
  const id = `filter-${label}`
  return (
    <Field>
      <FieldLabel htmlFor={id} className="sr-only">
        {label}
      </FieldLabel>
      <Select name={id} value={value} onValueChange={onValueChange}>
        <SelectTrigger id={id} className="w-full">
          <SelectValue placeholder={label} />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value={ALL}>全部{label}</SelectItem>
            {items.map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.label}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </Field>
  )
}
