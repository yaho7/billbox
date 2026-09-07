import { useState, type FormEvent } from "react"
import { LockKeyholeIcon } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

type Props = {
  onLogin: (password: string) => Promise<void>
}

export function LoginPage({ onLogin }: Props) {
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setIsSubmitting(true)
    try {
      await onLogin(password)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "登录失败，请重试")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-shell" id="main-content">
      <div className="login-intro">
        <div className="brand-mark" aria-hidden="true" translate="no">
          B
        </div>
        <p className="eyebrow">LOCAL LEDGER</p>
        <h1>账本在家，心里有数。</h1>
        <p>
          邮件账单自动归集到你自己的
          SQLite。这里没有第三方账户，也没有云端数据副本。
        </p>
      </div>

      <Card className="login-card">
        <CardHeader>
          <CardTitle>进入 Billbox</CardTitle>
          <CardDescription>使用服务端配置的访问密码。</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="login-password">访问密码</FieldLabel>
                <Input
                  id="login-password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </Field>
              {error ? (
                <Alert variant="destructive">
                  <LockKeyholeIcon aria-hidden="true" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}
              <Button type="submit" size="lg" disabled={isSubmitting}>
                {isSubmitting ? "正在验证…" : "进入账本"}
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
