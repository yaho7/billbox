import { describe, expect, it } from "vitest"

import { formatCurrency, formatDateTime, monthLabel } from "@/lib/format"

describe("ledger formatting", () => {
  it("formats minor units as CNY without floating-point drift", () => {
    expect(formatCurrency(123456)).toContain("1,234.56")
    expect(formatCurrency(-990)).toMatch(/^-.*9\.90$/)
  })

  it("formats month and time for a Chinese interface", () => {
    expect(monthLabel("2026-09")).toBe("2026年9月")
    expect(formatDateTime("2026-09-07T08:05:00+08:00")).toMatch(
      /09月07日.*08:05/
    )
  })
})
