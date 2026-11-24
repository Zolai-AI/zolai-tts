import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Spinner } from '@/components/ui/spinner'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Toaster } from '@/components/ui/sonner'
import {
  AudioPlayer,
  AudioPlayerControlBar,
  AudioPlayerDurationDisplay,
  AudioPlayerElement,
  AudioPlayerPlayButton,
  AudioPlayerTimeDisplay,
  AudioPlayerTimeRange,
} from '@/components/ai-elements/audio-player'
import { queryKeys } from '@/lib/api'
import {
  useCatalogsQueries,
  useProvidersQuery,
  useRecordingsQuery,
  useRunsQuery,
  useSynthesizeMutation,
  useUploadRecordingMutation,
} from '@/hooks/use-api'
import type { Catalog, SynthesizeResponse } from '@/lib/types'

const LANGUAGES = ['ted', 'zolai', 'zomi', 'en'] as const
const CUSTOM = '__custom__' 

function App() {
  const queryClient = useQueryClient()
  const [provider, setProvider] = useState('piper')
  const [language, setLanguage] = useState('ted')
  const [model, setModel] = useState('')
  const [voice, setVoice] = useState('')
  const [format, setFormat] = useState('wav')
  const [baseUrl, setBaseUrl] = useState('')
  const [customModel, setCustomModel] = useState('')
  const [customVoice, setCustomVoice] = useState('')
  const [text, setText] = useState('Dam maw? Zomi')
  const [dryRun, setDryRun] = useState(true)
  const [result, setResult] = useState<SynthesizeResponse | null>(null)
  const [note, setNote] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const lastProvider = useRef('')

  const providersQuery = useProvidersQuery()
  const providers = providersQuery.data?.providers ?? []
  useEffect(() => {
    if (!providers.length) return
    setProvider((current) =>
      providers.some((item) => item.name === current)
        ? current
        : (providers.find((item) => !item.hosted)?.name ?? providers[0].name),
    )
  }, [providers])

  const catalogQueries = useCatalogsQueries(providers.map((item) => item.name))
  const catalogs = Object.fromEntries(
    catalogQueries.flatMap((query) => {
      const catalog = query.data?.catalog
      return catalog ? [[catalog.provider, catalog] as const] : []
    }),
  ) as Record<string, Catalog>

  const runsQuery = useRunsQuery()
  const recordingsQuery = useRecordingsQuery()

  const activeProvider = providers.find((item) => item.name === provider)
  const catalog = catalogs[provider]
  const modelInfo = catalog?.model_infos.find((item) => item.id === model)
  const voices = modelInfo?.voices.length ? modelInfo.voices : (catalog?.voices ?? [])
  const formats = modelInfo?.formats.length ? modelInfo.formats : (catalog?.formats ?? ['wav'])
  const loading = providersQuery.isPending
  const error = providersQuery.error instanceof Error ? providersQuery.error.message : ''
  const synthMutation = useSynthesizeMutation({
    onSuccess: (response) => {
      setResult(response)
      toast.success(response.dry_run ? 'Dry run ready' : 'Synthesis complete')
    },
    onError: (cause) => {
      toast.error(cause instanceof Error ? cause.message : String(cause))
    },
  })

  const uploadMutation = useUploadRecordingMutation({
    onSuccess: () => {
      toast.success('Recording saved locally')
      setNote('')
    },
    onError: (cause) => {
      toast.error(cause instanceof Error ? cause.message : String(cause))
    },
  })

  const busy = synthMutation.isPending || uploadMutation.isPending
  const runs = runsQuery.data?.runs ?? []
  const recordings = recordingsQuery.data?.recordings ?? []

  useEffect(() => {
    if (!catalog || lastProvider.current === provider) return
    lastProvider.current = provider
    const preferred = ['fish-audio/s2.1-pro-free:free', 'heygen/heygen-voice-1-turbo:free']
    setModel(preferred.find((id) => catalog.models.includes(id)) ?? catalog.models[0] ?? '')
    setVoice(catalog.voices[0] ?? '')
    setFormat(catalog.formats[0] ?? 'wav')
    setBaseUrl(provider === 'openrouter' ? 'https://openrouter.ai/api/v1' : '')
    setCustomModel('')
    setCustomVoice('')
  }, [provider, catalog])

  function onModelChange(value: string) {
    setModel(value)
    if (value === CUSTOM) return
    const info = catalog?.model_infos.find((item) => item.id === value)
    setVoice(info?.voices[0] ?? catalog?.voices[0] ?? '')
    setFormat(info?.formats[0] ?? catalog?.formats[0] ?? 'wav')
  }

  async function onSynthesize() {
    if (!text.trim()) {
      toast.error('Text is required.')
      return
    }
    await synthMutation.mutateAsync({
      provider,
      text,
      language,
      voice: customVoice || voice,
      model: customModel || model || null,
      response_format: format,
      base_url: baseUrl || null,
      dry_run: dryRun,
    })
  }

  async function onRefresh() {
    try {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.providers }),
        ...providers.map((item) =>
          queryClient.refetchQueries({ queryKey: queryKeys.catalog(item.name) }),
        ),
        queryClient.invalidateQueries({ queryKey: queryKeys.runs }),
        queryClient.invalidateQueries({ queryKey: queryKeys.recordings }),
      ])
      toast.success('Catalogs refreshed')
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : String(cause))
    }
  }

  async function onUpload(file: File | undefined) {
    if (!file) return
    const body = new FormData()
    body.append('file', file)
    body.append('provider', provider)
    body.append('model', customModel || model)
    body.append('voice', customVoice || voice)
    body.append('note', note)
    await uploadMutation.mutateAsync(body)
    if (fileRef.current) fileRef.current.value = ''
  }

  

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 p-4 md:p-8">
      <Toaster />
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">Zolai TTS Studio</h1>
          <Badge variant="secondary">local research</Badge>
          <Badge variant="outline">no key stored</Badge>
        </div>
        <p className="text-muted-foreground text-sm">
          Local synthesis UI over the registered Zolai-TTS providers. Models, voices and
          formats are fetched live from each provider. Piper is the real local voice;
          hosted paths have no native Tedim/Zolai/Zomi support.
        </p>
      </header>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Cannot reach the API</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm">
          <Spinner /> Loading providers and catalogs…
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Synthesize</CardTitle>
            <CardDescription>
              Dry run builds a safe request plan. Real synthesis needs a voice and, for
              hosted providers, an env API key.
            </CardDescription>
            <CardAction>
              <Button variant="outline" size="sm" onClick={() => void onRefresh()} disabled={busy}>
                Refresh all
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="tts-text">Text</FieldLabel>
                <Textarea
                  id="tts-text"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder="Enter Tedim/Zolai/Zomi or English text…"
                  rows={4}
                />
                <FieldDescription>Up to 8000 characters per request.</FieldDescription>
              </Field>
              <div className="grid gap-4 md:grid-cols-2">
                <Field>
                  <FieldLabel htmlFor="tts-provider">Provider</FieldLabel>
                  <Select value={provider} onValueChange={setProvider}>
                    <SelectTrigger id="tts-provider">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {providers.map((item) => (
                          <SelectItem key={item.name} value={item.name}>
                            {item.label}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel htmlFor="tts-language">Language</FieldLabel>
                  <Select value={language} onValueChange={setLanguage}>
                    <SelectTrigger id="tts-language">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {LANGUAGES.map((item) => (
                          <SelectItem key={item} value={item}>
                            {item}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
              </div>

              <Field>
                <FieldLabel htmlFor="tts-model">Model</FieldLabel>
                <Select value={model || undefined} onValueChange={onModelChange}>
                  <SelectTrigger id="tts-model">
                    <SelectValue placeholder="Select a model" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {(catalog?.models ?? []).map((id) => (
                        <SelectItem key={id} value={id}>
                          {catalog?.model_infos.find((info) => info.id === id)?.name || id}
                        </SelectItem>
                      ))}
                      <SelectItem value={CUSTOM}>Custom model…</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
                {model === CUSTOM ? (
                  <Input
                    aria-label="Custom model id"
                    value={customModel}
                    onChange={(event) => setCustomModel(event.target.value)}
                    placeholder="author/model-id"
                  />
                ) : null}
                <FieldDescription>
                  {catalog?.source ? `Source: ${catalog.source}` : 'Waiting for catalog.'}
                </FieldDescription>
              </Field>

              <Field>
                <FieldLabel htmlFor="tts-voice">
                  {activeProvider?.voice_kind === 'path' ? 'Voice model path (.onnx)' : 'Voice'}
                </FieldLabel>
                <Select value={voice || undefined} onValueChange={setVoice}>
                  <SelectTrigger id="tts-voice">
                    <SelectValue placeholder="Select a voice" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {voices.map((id) => (
                        <SelectItem key={id} value={id}>
                          {id}
                        </SelectItem>
                      ))}
                      <SelectItem value={CUSTOM}>Custom voice…</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
                {voice === CUSTOM ? (
                  <Input
                    aria-label="Custom voice"
                    value={customVoice}
                    onChange={(event) => setCustomVoice(event.target.value)}
                    placeholder={
                      activeProvider?.voice_kind === 'path'
                        ? '/path/to/voice.onnx'
                        : 'voice id'
                    }
                  />
                ) : null}
              </Field>

              <div className="grid gap-4 md:grid-cols-2">
                <Field>
                  <FieldLabel htmlFor="tts-format">Response format</FieldLabel>
                  <Select value={format || undefined} onValueChange={setFormat}>
                    <SelectTrigger id="tts-format">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {formats.map((id) => (
                          <SelectItem key={id} value={id}>
                            {id}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
                {activeProvider?.hosted && provider === 'openrouter' ? (
                  <Field>
                    <FieldLabel htmlFor="tts-base-url">Base URL</FieldLabel>
                    <Input
                      id="tts-base-url"
                      value={baseUrl}
                      onChange={(event) => setBaseUrl(event.target.value)}
                      placeholder="https://openrouter.ai/api/v1"
                    />
                  </Field>
                ) : null}
              </div>

              <Field orientation="horizontal">
                <FieldLabel htmlFor="tts-dry-run">Dry run</FieldLabel>
                <Switch id="tts-dry-run" checked={dryRun} onCheckedChange={setDryRun} />
                <FieldDescription>No audio, no key required.</FieldDescription>
              </Field>
            </FieldGroup>
          </CardContent>
          <CardFooter className="flex flex-wrap items-center gap-3">
            <Button onClick={() => void onSynthesize()} disabled={busy}>
              {busy ? <Spinner /> : null}
              {dryRun ? 'Build plan' : 'Synthesize'}
            </Button>
            {activeProvider ? (
              <Badge variant={activeProvider.key_present ? 'secondary' : 'outline'}>
                {activeProvider.hosted
                  ? `Env key ${activeProvider.key_present ? 'set' : 'not set'}`
                  : 'Local provider'}
              </Badge>
            ) : null}
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Result</CardTitle>
            <CardDescription>
              {result?.dry_run ? 'Dry-run request plan (redacted).' : 'Latest synthesis output.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {result?.run?.audio_url ? (
              <AudioPlayer>
                <AudioPlayerElement src={result.run.audio_url} preload="metadata" />
                <AudioPlayerControlBar>
                  <AudioPlayerPlayButton />
                  <AudioPlayerTimeRange />
                  <AudioPlayerTimeDisplay />
                  <AudioPlayerDurationDisplay />
                </AudioPlayerControlBar>
              </AudioPlayer>
            ) : null}
            {result?.error ? (
              <Alert variant="destructive">
                <AlertTitle>Synthesis failed</AlertTitle>
                <AlertDescription>{result.error}</AlertDescription>
              </Alert>
            ) : null}
            <ScrollArea className="bg-muted rounded-md p-3 text-xs">
              <pre className="whitespace-pre-wrap break-all">
                {result ? JSON.stringify(result, null, 2) : 'No result yet.'}
              </pre>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Provider catalog</CardTitle>
          <CardDescription>
            Live models, voices and formats per provider. Free-tier terms and quotas vary;
            nothing here is unlimited-free.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Provider</TableHead>
                <TableHead>Models</TableHead>
                <TableHead>Voices</TableHead>
                <TableHead>Formats</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Env key</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {providers.map((item) => {
                const entry = catalogs[item.name]
                return (
                  <TableRow key={item.name}>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell>{entry?.models.length ?? 0}</TableCell>
                    <TableCell>{entry?.voices.length ?? 0}</TableCell>
                    <TableCell>{entry?.formats.length ?? 0}</TableCell>
                    <TableCell className="text-muted-foreground text-xs">
                      {entry?.source ?? 'pending'}
                    </TableCell>
                    <TableCell>
                      {item.hosted ? (item.key_present ? 'set' : 'not set') : 'n/a'}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
          {Object.values(catalogs).some((entry) => entry.error) ? (
            <Alert className="mt-4">
              <AlertTitle>Catalog warnings</AlertTitle>
              <AlertDescription>
                {Object.values(catalogs)
                  .filter((entry) => entry.error)
                  .map((entry) => `${entry.provider}: ${entry.error}`)
                  .join(' · ')}
              </AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Capture & history</CardTitle>
          <CardDescription>
            Mic/upload files stay in local storage with a metadata sidecar. Nothing is
            transmitted by this UI.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-end gap-3">
            <Field className="min-w-56 flex-1">
              <FieldLabel htmlFor="rec-note">Recording note</FieldLabel>
              <Input
                id="rec-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Optional consent / context note"
              />
            </Field>
            <input
              ref={fileRef}
              aria-label="Audio file"
              className="text-muted-foreground text-sm"
              type="file"
              accept="audio/*"
              onChange={(event) => void onUpload(event.target.files?.[0])}
            />
          </div>
          <Separator />
          <Tabs defaultValue="runs">
            <TabsList>
              <TabsTrigger value="runs">Runs</TabsTrigger>
              <TabsTrigger value="recordings">Recordings</TabsTrigger>
            </TabsList>
            <TabsContent value="runs">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Voice</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">{item.id}</TableCell>
                      <TableCell>{item.provider}</TableCell>
                      <TableCell className="max-w-48 truncate">{item.voice}</TableCell>
                      <TableCell>
                        <Badge variant={item.ok ? 'secondary' : 'destructive'}>
                          {item.ok ? 'ok' : 'failed'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {item.created_at}
                      </TableCell>
                    </TableRow>
                  ))}
                  {runs.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-muted-foreground">
                        No synthesis runs yet.
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </TabsContent>
            <TabsContent value="recordings">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Format</TableHead>
                    <TableHead>Bytes</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recordings.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">{item.id}</TableCell>
                      <TableCell className="max-w-48 truncate">{item.source_name}</TableCell>
                      <TableCell>{item.format}</TableCell>
                      <TableCell>{item.bytes}</TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {item.created_at}
                      </TableCell>
                    </TableRow>
                  ))}
                  {recordings.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-muted-foreground">
                        No recordings yet.
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}

export default App
