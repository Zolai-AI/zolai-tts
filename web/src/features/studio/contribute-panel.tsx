import { useEffect, useMemo, useState } from 'react'
import { Mic, MicOff, Square, Upload, UploadCloud } from 'lucide-react'

import { useMicRecorder } from '@/hooks/use-mic-recorder'
import {
  useContributeMutation,
  useContributionsQuery,
  useSetContributionStatusMutation,
} from '@/hooks/use-api'
import { formatBytes, formatDuration } from '@/lib/api'
import type { Contribution } from '@/lib/types'
import { AudioPreview } from '@/components/audio-preview'
import {
  MicSelector,
  MicSelectorContent,
  MicSelectorEmpty,
  MicSelectorInput,
  MicSelectorItem,
  MicSelectorLabel,
  MicSelectorList,
  MicSelectorTrigger,
  MicSelectorValue,
} from '@/components/ai-elements/mic-selector'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'

/** Prompt sentences for structured contributions (recorded, not synthesized). */
const PROMPTS = [
  { label: 'Greetings', text: 'Kamsinlo. Naam kongzong hi? (Hello. How are you?)' },
  { label: 'Family', text: 'Pa-khoi in natthang thinthing hi. (My father works in the field.)' },
  { label: 'Numbers', text: 'Sani, tthi, thinthin, si, nga. (One, two, three, four, five.)' },
  { label: 'Market', text: 'Kongsia tlang a hi tam aw. (How much is this vegetable?)' },
  { label: 'Free read', text: '' },
]

const LICENSES = [
  { value: 'cc-by-4.0', label: 'CC BY 4.0 — credit the speaker' },
  { value: 'cc-by-sa-4.0', label: 'CC BY-SA 4.0 — share alike' },
  { value: 'cc0-1.0', label: 'CC0 — public domain' },
]

function blobToTake(blob: Blob): File {
  const ext = blob.type.includes('ogg') ? 'ogg' : blob.type.includes('mp4') ? 'm4a' : 'webm'
  return new File([blob], `take-${Date.now()}.${ext}`, { type: blob.type || 'audio/webm' })
}

export function ContributePanel({ languages }: { languages: { code: string; label: string }[] }) {
  const recorder = useMicRecorder()
  const contribute = useContributeMutation()
  const [promptKey, setPromptKey] = useState(PROMPTS[0].label)
  const [alias, setAlias] = useState('')
  const [language, setLanguage] = useState('ted')
  const [license, setLicense] = useState('cc-by-4.0')
  const [note, setNote] = useState('')
  const [consent, setConsent] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [deviceId, setDeviceId] = useState<string | undefined>(undefined)

  const prompt = useMemo(() => PROMPTS.find((item) => item.label === promptKey)?.text ?? '', [promptKey])
  const isRecording = recorder.status === 'recording'

  useEffect(() => {
    if (!recorder.blob) setFile(null)
  }, [recorder.blob])

  const audioUrl = useMemo(() => {
    const source = recorder.blob ?? file
    return source ? URL.createObjectURL(source) : ''
  }, [recorder.blob, file])

  useEffect(
    () => () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl)
    },
    [audioUrl],
  )

  const submit = async () => {
    const source = file ?? (recorder.blob ? blobToTake(recorder.blob) : null)
    if (!source || !consent) return
    const form = new FormData()
    form.append('file', source, source.name)
    form.append('speaker_alias', alias || 'anonymous')
    form.append('language', language)
    form.append('prompt', prompt)
    form.append('consent', 'true')
    form.append('license', license)
    form.append('note', note)
    form.append('mic_device', recorder.deviceLabel)
    await contribute.mutateAsync(form)
    recorder.reset()
    setFile(null)
    setNote('')
    setConsent(false)
  }

  const size = file?.size ?? recorder.blob?.size ?? 0

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Contribute a voice take</CardTitle>
          <CardDescription>
            Record your own Tedim Zolai speech for the dataset. Nothing is uploaded until you tick the
            consent box; consent, license and alias are stored with the audio.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field>
            <FieldLabel htmlFor="prompt-select">Prompt</FieldLabel>
            <Select value={promptKey} onValueChange={setPromptKey}>
              <SelectTrigger id="prompt-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROMPTS.map((item) => (
                  <SelectItem key={item.label} value={item.label}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {prompt && <FieldDescription className="pt-2 text-sm">{prompt}</FieldDescription>}
          </Field>

          <div className="flex flex-wrap items-center gap-2">
            {isRecording ? (
              <Button variant="destructive" onClick={() => recorder.stop()}>
                <Square className="size-4" /> Stop
              </Button>
            ) : (
              <Button onClick={() => recorder.start(deviceId)}>
                <Mic className="size-4" /> Record
              </Button>
            )}
            <span className="text-sm tabular-nums text-muted-foreground">
              {formatDuration(recorder.seconds)}
            </span>
            <MicSelector value={deviceId} onValueChange={setDeviceId}>
              <MicSelectorTrigger variant="outline" size="sm">
                <MicOff className="size-4" />
                <MicSelectorValue />
              </MicSelectorTrigger>
              <MicSelectorContent>
                <MicSelectorInput placeholder="Search microphones…" />
                <MicSelectorList>
                  {(devices) => (
                    <>
                      {devices.map((device) => (
                        <MicSelectorItem key={device.deviceId} value={device.deviceId}>
                          <MicSelectorLabel device={device} />
                        </MicSelectorItem>
                      ))}
                      <MicSelectorEmpty>No microphones found.</MicSelectorEmpty>
                    </>
                  )}
                </MicSelectorList>
              </MicSelectorContent>
            </MicSelector>
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
              <Upload className="size-4" />
              <input
                type="file"
                accept="audio/*"
                className="sr-only"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              Upload instead
            </label>
            {recorder.error && <p className="text-sm text-destructive">{recorder.error}</p>}
          </div>

          {(recorder.blob || file) && (
            <div className="space-y-2">
              <AudioPreview src={audioUrl} label="Preview before submitting" meta={formatBytes(size)} />
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  recorder.reset()
                  setFile(null)
                }}
              >
                Discard take
              </Button>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="alias">Speaker alias</FieldLabel>
              <Input
                id="alias"
                value={alias}
                placeholder="anonymous"
                onChange={(event) => setAlias(event.target.value)}
              />
              <FieldDescription>Shown in the dataset; never a legal name.</FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="contrib-language">Language</FieldLabel>
              <Select value={language} onValueChange={setLanguage}>
                <SelectTrigger id="contrib-language">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {languages.map((item) => (
                    <SelectItem key={item.code} value={item.code}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="contrib-license">License</FieldLabel>
              <Select value={license} onValueChange={setLicense}>
                <SelectTrigger id="contrib-license">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LICENSES.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="contrib-note">Note</FieldLabel>
              <Input
                id="contrib-note"
                value={note}
                placeholder="dialect village, age band, etc."
                onChange={(event) => setNote(event.target.value)}
              />
            </Field>
          </div>

          <Field orientation="horizontal">
            <Switch id="consent" checked={consent} onCheckedChange={setConsent} />
            <FieldLabel htmlFor="consent">
              I consent to this recording being used for Zolai TTS research and training under the
              selected license.
            </FieldLabel>
          </Field>

          <Button onClick={submit} disabled={!consent || (!recorder.blob && !file) || contribute.isPending}>
            <UploadCloud className="size-4" />
            {contribute.isPending ? 'Submitting…' : 'Submit contribution'}
          </Button>
          {contribute.isError && (
            <p className="text-sm text-destructive">{(contribute.error as Error).message}</p>
          )}
        </CardContent>
      </Card>

      <ContributionQueue />
    </div>
  )
}

function ContributionQueue() {
  const contributions = useContributionsQuery()
  const setStatus = useSetContributionStatusMutation()
  const rows: Contribution[] = contributions.data?.contributions ?? []

  return (
    <Card>
      <CardHeader>
        <CardTitle>Contribution queue</CardTitle>
        <CardDescription>
          Review before anything enters the corpus. Accepted takes are the ones a Zolai voice model can
          be trained on.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {contributions.isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!contributions.isPending && rows.length === 0 && (
          <p className="text-sm text-muted-foreground">No contributions yet.</p>
        )}
        {rows.map((row) => (
          <div key={row.id} className="space-y-2 rounded-md border p-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant={row.status === 'accepted' ? 'default' : 'outline'}>{row.status}</Badge>
              <span className="font-medium">{row.speaker_alias}</span>
              <span>· {row.language}</span>
              <span>· {row.license}</span>
              <span>· {formatBytes(row.bytes)}</span>
              <span>· {formatDuration(row.duration_seconds)}</span>
              <span className="text-muted-foreground">
                · {new Date(row.created_at).toLocaleString()}
              </span>
            </div>
            {row.prompt && <p className="text-xs text-muted-foreground">{row.prompt}</p>}
            <AudioPreview src={row.audio_url} />
            <div className="flex gap-2">
              {(['accepted', 'rejected', 'reviewing'] as const).map((status) => (
                <Button
                  key={status}
                  size="sm"
                  variant={row.status === status ? 'default' : 'outline'}
                  disabled={setStatus.isPending}
                  onClick={() => setStatus.mutate({ id: row.id, status })}
                >
                  {status}
                </Button>
              ))}
            </div>
            {!row.consent && (
              <p className="text-xs text-destructive">No consent record — cannot be accepted.</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
