import { useState } from 'react'
import { useUsageQuery } from '@/hooks/use-api'
import { formatDuration } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const WINDOWS = [1, 7, 30, 90] as const

function money(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return value === 0 ? '$0.00' : `$${value.toFixed(value < 0.01 ? 6 : 4)}`
}

/** Cost observer: recorded spend per provider/tier/model against the budget. */
export function CostPanel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Cost &amp; usage</CardTitle>
        <CardDescription>
          Only real runs are recorded. Estimates use prices the provider publishes; where none exists the
          figure stays unknown instead of guessed.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <UsageBody />
      </CardContent>
    </Card>
  )
}

function UsageBody() {
  // One hook per window keeps each table independently fetchable without loops.
  return (
    <div className="space-y-4">
      <WindowSummary />
      <Breakdown />
    </div>
  )
}

function WindowSummary() {
  const usage = useUsageQuery(30)
  if (usage.isPending) return <p className="text-sm text-muted-foreground">Loading usage…</p>
  if (usage.isError)
    return <p className="text-sm text-destructive">{(usage.error as Error).message}</p>
  const data = usage.data!
  const dailyCap = data.budget.daily_usd
  const monthlyCap = data.budget.monthly_usd
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge variant="secondary">{data.totals.calls} calls</Badge>
        <Badge variant="secondary">{data.totals.characters.toLocaleString()} chars</Badge>
        <Badge variant="secondary">{formatDuration(data.totals.audio_seconds)} audio</Badge>
        <Badge variant={data.totals.cost_usd > 0 ? 'default' : 'outline'}>
          {money(data.totals.cost_usd)} / 30d
        </Badge>
        {data.budget.free_only && <Badge variant="destructive">free-only mode</Badge>}
      </div>

      {dailyCap > 0 && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Today</span>
            <span>
              {money(data.spend_today_usd)} of {money(dailyCap)}
            </span>
          </div>
          <Progress value={Math.min(100, (data.spend_today_usd / dailyCap) * 100)} />
        </div>
      )}
      {monthlyCap > 0 && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Month</span>
            <span>
              {money(data.spend_month_usd)} of {money(monthlyCap)}
            </span>
          </div>
          <Progress value={Math.min(100, (data.spend_month_usd / monthlyCap) * 100)} />
        </div>
      )}
      {dailyCap === 0 && monthlyCap === 0 && (
        <p className="text-xs text-muted-foreground">No budget limits set (Settings → Budget).</p>
      )}
    </div>
  )
}

function Breakdown() {
  const [days, setDays] = useState(30)
  const usage = useUsageQuery(days)
  if (usage.isPending || !usage.data) return null
  const { by_provider, by_model } = usage.data
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {WINDOWS.map((window) => (
          <Button
            key={window}
            size="sm"
            variant={days === window ? 'default' : 'outline'}
            onClick={() => setDays(window)}
          >
            {window}d
          </Button>
        ))}
      </div>

      {by_provider.length === 0 ? (
        <p className="text-sm text-muted-foreground">No calls recorded in this window.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Provider</TableHead>
              <TableHead>Tier</TableHead>
              <TableHead className="text-right">Calls</TableHead>
              <TableHead className="text-right">Chars</TableHead>
              <TableHead className="text-right">Audio</TableHead>
              <TableHead className="text-right">Cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {by_provider.map((row) => (
              <TableRow key={`${row.provider}-${row.tier}`}>
                <TableCell className="font-medium">{row.provider}</TableCell>
                <TableCell>
                  <Badge variant={row.tier === 'free' || row.tier === 'free-local' ? 'secondary' : 'outline'}>
                    {row.tier}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">{row.calls}</TableCell>
                <TableCell className="text-right">{row.characters.toLocaleString()}</TableCell>
                <TableCell className="text-right">{formatDuration(row.audio_seconds)}</TableCell>
                <TableCell className="text-right">{money(row.cost_usd)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {by_model.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">Top models</p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Model</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead className="text-right">Calls</TableHead>
                <TableHead className="text-right">Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {by_model.map((row) => (
                <TableRow key={`${row.provider}-${row.model}`}>
                  <TableCell className="max-w-[16rem] truncate font-mono text-xs">{row.model}</TableCell>
                  <TableCell>{row.tier}</TableCell>
                  <TableCell className="text-right">{row.calls}</TableCell>
                  <TableCell className="text-right">{money(row.cost_usd)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
