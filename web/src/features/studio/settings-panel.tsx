import { useState } from 'react'
import { KeyRound, RefreshCw, ShieldCheck, Trash2 } from 'lucide-react'

import {
  useClearSecretMutation,
  useRefreshCatalogsMutation,
  useSaveSettingsMutation,
  useSecretsQuery,
  useSettingsQuery,
  useSetSecretsMutation,
} from '@/hooks/use-api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

/** Env names the studio accepts as session keys. Values are write-only. */
const KEY_FIELDS = [
  { name: 'GEMINI_API_KEY', label: 'Gemini API key', hint: 'ZOLAI_TTS_GEMINI_API_KEY also works' },
  { name: 'OPENROUTER_API_KEY', label: 'OpenRouter API key', hint: 'Used for hosted TTS catalogs and calls' },
] as const

const TIER_OPTIONS = [
  { value: 'any', label: 'Any' },
  { value: 'free', label: 'Free only' },
  { value: 'paid', label: 'Paid only' },
] as const

export function SettingsPanel({ providers }: { providers: { name: string; label: string }[] }) {
  const settings = useSettingsQuery()
  const secrets = useSecretsQuery()
  const saveSettings = useSaveSettingsMutation()
  const setSecrets = useSetSecretsMutation()
  const clearSecret = useClearSecretMutation()
  const refreshCatalogs = useRefreshCatalogsMutation()

  const [tierPolicy, setTierPolicy] = useState<Record<string, string>>({})
  const [budget, setBudget] = useState({ daily_usd: '', monthly_usd: '', free_only: false })
  const [storage, setStorage] = useState<'local' | 'r2' | 'auto'>('local')
  const [keyValues, setKeyValues] = useState<Record<string, string>>({})
  const [initialized, setInitialized] = useState(false)
  const [saved, setSaved] = useState<string | null>(null)

  // Seed local form state once the first settings response lands.
  if (!initialized && settings.data) {
    setTierPolicy(settings.data.tier_policy ?? {})
    setBudget({
      daily_usd: settings.data.budget?.daily_usd ? String(settings.data.budget.daily_usd) : '',
      monthly_usd: settings.data.budget?.monthly_usd ? String(settings.data.budget.monthly_usd) : '',
      free_only: Boolean(settings.data.budget?.free_only),
    })
    setStorage((settings.data.storage?.preferred as 'local' | 'r2' | 'auto') ?? 'local')
    setInitialized(true)
  }

  const persist = () => {
    saveSettings.mutate(
      {
        tier_policy: tierPolicy,
        budget: {
          daily_usd: Number(budget.daily_usd || 0),
          monthly_usd: Number(budget.monthly_usd || 0),
          free_only: budget.free_only,
        },
        storage: { preferred: storage },
      },
      { onSuccess: () => setSaved('Settings saved.') },
    )
  }

  const commitKey = (name: string) => {
    const value = keyValues[name]?.trim()
    if (!value) return
    setSecrets.mutate({ [name]: value }, { onSuccess: () => setKeyValues((prev) => ({ ...prev, [name]: '' })) })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="size-4" /> Settings
        </CardTitle>
        <CardDescription>
          Keys live in memory for this session only. Tier policy, budget and storage are stored in the
          studio database.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="keys">
          <TabsList className="mb-4">
            <TabsTrigger value="keys">Keys</TabsTrigger>
            <TabsTrigger value="tiers">Tiers</TabsTrigger>
            <TabsTrigger value="budget">Budget</TabsTrigger>
            <TabsTrigger value="storage">Storage</TabsTrigger>
          </TabsList>

          <TabsContent value="keys" className="space-y-4">
            {KEY_FIELDS.map((field) => {
              const state = secrets.data?.secrets?.[field.name]
              return (
                <Field key={field.name}>
                  <FieldLabel htmlFor={`key-${field.name}`}>
                    <span className="flex items-center gap-2">
                      <KeyRound className="size-3.5" /> {field.label}
                      {state?.present ? (
                        <Badge variant={state.source === 'session' ? 'default' : 'secondary'}>
                          {state.source === 'session' ? 'session' : 'environment'} · {state.hint}
                        </Badge>
                      ) : (
                        <Badge variant="outline">not set</Badge>
                      )}
                    </span>
                  </FieldLabel>
                  <div className="flex gap-2">
                    <Input
                      id={`key-${field.name}`}
                      type="password"
                      autoComplete="off"
                      placeholder={state?.present ? 'Present — type to replace' : field.hint}
                      value={keyValues[field.name] ?? ''}
                      onChange={(event) =>
                        setKeyValues((prev) => ({ ...prev, [field.name]: event.target.value }))
                      }
                    />
                    <Button
                      onClick={() => commitKey(field.name)}
                      disabled={!keyValues[field.name]?.trim() || setSecrets.isPending}
                    >
                      {setSecrets.isPending ? 'Saving…' : 'Save'}
                    </Button>
                    {state?.present && state.source === 'session' && (
                      <Button
                        variant="outline"
                        size="icon"
                        aria-label={`Clear ${field.label}`}
                        onClick={() => clearSecret.mutate(field.name)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    )}
                  </div>
                  <FieldDescription>
                    Sent over localhost only; never written to the database, logs, or responses.
                  </FieldDescription>
                </Field>
              )
            })}
            <Separator />
            <Field>
              <FieldLabel>Catalog discovery</FieldLabel>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  onClick={() => refreshCatalogs.mutate(undefined)}
                  disabled={refreshCatalogs.isPending}
                >
                  <RefreshCw className={refreshCatalogs.isPending ? 'size-4 animate-spin' : 'size-4'} />
                  Refresh all providers
                </Button>
                {refreshCatalogs.data && (
                  <FieldDescription>
                    {Object.entries(refreshCatalogs.data.refreshed as Record<string, { models?: number }>)
                      .map(([name, value]) => `${name}: ${value.models ?? 0}`)
                      .join(' · ')}
                  </FieldDescription>
                )}
              </div>
              <FieldDescription>
                Models, voices and formats come from each provider's live API and are persisted to the
                database.
              </FieldDescription>
            </Field>
          </TabsContent>

          <TabsContent value="tiers" className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Default model tier per provider. "Free only" filters the catalog to provably free models; a
              provider with none will show an empty list.
            </p>
            {providers.map((provider) => (
              <Field key={provider.name}>
                <FieldLabel htmlFor={`tier-${provider.name}`}>{provider.label}</FieldLabel>
                <div className="flex gap-2" id={`tier-${provider.name}`}>
                  {TIER_OPTIONS.map((option) => (
                    <Button
                      key={option.value}
                      size="sm"
                      variant={tierPolicy[provider.name] === option.value ? 'default' : 'outline'}
                      onClick={() =>
                        setTierPolicy((prev) => ({ ...prev, [provider.name]: option.value }))
                      }
                    >
                      {option.label}
                    </Button>
                  ))}
                </div>
              </Field>
            ))}
          </TabsContent>

          <TabsContent value="budget" className="space-y-4">
            <Field>
              <FieldLabel htmlFor="budget-daily">Daily limit (USD)</FieldLabel>
              <Input
                id="budget-daily"
                type="number"
                min="0"
                step="0.01"
                placeholder="0 = unlimited"
                value={budget.daily_usd}
                onChange={(event) => setBudget((prev) => ({ ...prev, daily_usd: event.target.value }))}
              />
              <FieldDescription>Checked before each paid call, using recorded usage.</FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="budget-monthly">Monthly limit (USD)</FieldLabel>
              <Input
                id="budget-monthly"
                type="number"
                min="0"
                step="0.01"
                placeholder="0 = unlimited"
                value={budget.monthly_usd}
                onChange={(event) => setBudget((prev) => ({ ...prev, monthly_usd: event.target.value }))}
              />
            </Field>
            <Field orientation="horizontal">
              <Switch
                id="budget-free-only"
                checked={budget.free_only}
                onCheckedChange={(checked) => setBudget((prev) => ({ ...prev, free_only: checked }))}
              />
              <FieldLabel htmlFor="budget-free-only">Free-only mode</FieldLabel>
              <FieldDescription>
                Blocks billed calls and calls whose price is not published.
              </FieldDescription>
            </Field>
          </TabsContent>

          <TabsContent value="storage" className="space-y-4">
            <Field>
              <FieldLabel>Audio backend</FieldLabel>
              <div className="flex gap-2">
                {(['local', 'r2', 'auto'] as const).map((option) => (
                  <Button
                    key={option}
                    size="sm"
                    variant={storage === option ? 'default' : 'outline'}
                    onClick={() => setStorage(option)}
                  >
                    {option}
                  </Button>
                ))}
              </div>
              <FieldDescription>
                R2 talks S3 through the Cloudflare endpoint and needs ZOLAI_TTS_R2_* credentials. A local
                mirror is kept whenever R2 is active, so playback still works offline.
              </FieldDescription>
            </Field>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Current backend</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p>
                  Active: <Badge variant="secondary">{settings.data?.storage?.active ?? '—'}</Badge>
                </p>
                <p className="font-mono text-xs text-muted-foreground">
                  local root: {settings.data?.storage?.local?.root ?? '—'}
                </p>
                <p className="font-mono text-xs text-muted-foreground">
                  r2 bucket: {settings.data?.storage?.r2?.bucket || 'not configured'}
                </p>
                <p className="font-mono text-xs text-muted-foreground">
                  db: {settings.data?.database?.dialect ?? '—'} · {settings.data?.database?.url ?? ''}
                </p>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <Separator className="my-4" />
        <div className="flex items-center gap-3">
          <Button onClick={persist} disabled={saveSettings.isPending}>
            {saveSettings.isPending ? 'Saving…' : 'Save settings'}
          </Button>
          {saved && <span className="text-sm text-muted-foreground">{saved}</span>}
          {saveSettings.isError && (
            <span className="text-sm text-destructive">{(saveSettings.error as Error).message}</span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

