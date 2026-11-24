import { useState } from 'react'
import { CheckCircle2, HelpCircle, XCircle } from 'lucide-react'

import { useAddReviewMutation, useReviewsQuery, useRunsQuery } from '@/hooks/use-api'
import { formatDuration } from '@/lib/api'
import type { Run } from '@/lib/types'
import { AudioPreview } from '@/components/audio-preview'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

/** Perceptual issues a Zolai listener can hear and tag. */
const ARTIFACTS = [
  { key: 'vowel', label: 'Vowel quality' },
  { key: 'tone', label: 'Tone/pitch' },
  { key: 'consonant', label: 'Consonant cluster' },
  { key: 'stress', label: 'Word stress' },
  { key: 'speed', label: 'Too fast/slow' },
  { key: 'break', label: 'Phrasing/breaks' },
  { key: 'noise', label: 'Artifacts/noise' },
  { key: 'intelligible', label: 'Intelligible overall' },
] as const

const VERDICTS = [
  { value: 'pass', label: 'Usable', icon: CheckCircle2, variant: 'default' as const },
  { value: 'maybe', label: 'Borderline', icon: HelpCircle, variant: 'secondary' as const },
  { value: 'fail', label: 'Not usable', icon: XCircle, variant: 'destructive' as const },
] as const

export function ReviewPanel() {
  const runs = useRunsQuery()
  const [selected, setSelected] = useState<Run | null>(null)
  const [verdict, setVerdict] = useState<'pass' | 'maybe' | 'fail'>('maybe')
  const [rating, setRating] = useState<number>(3)
  const [tags, setTags] = useState<string[]>([])
  const [note, setNote] = useState('')
  const [reviewer, setReviewer] = useState('')
  const addReview = useAddReviewMutation({
    onSuccess: () => {
      setNote('')
      setTags([])
    },
  })

  // Only runs that actually stored audio can be listened to and reviewed.
  const queue = (runs.data?.runs ?? []).filter((run) => run.ok && run.audio_url).slice(0, 12)
  const active = selected ?? queue[0] ?? null
  const reviews = useReviewsQuery(active?.id)

  const submit = () => {
    if (!active) return
    addReview.mutate({
      run_id: active.id,
      verdict,
      rating,
      artifacts: tags,
      note,
      reviewer,
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sound check</CardTitle>
        <CardDescription>
          Listen, tag what you hear, and record a verdict. Reviews are stored against the run so the same
          clip can be re-checked after a model or voice change.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {queue.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing to review yet — synthesize a phrase in the Studio tab first.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {queue.map((run) => (
                <Button
                  key={run.id}
                  size="sm"
                  variant={active?.id === run.id ? 'default' : 'outline'}
                  onClick={() => setSelected(run)}
                >
                  {run.provider} · {run.format ?? '—'} ·{' '}
                  {formatDuration(run.duration_seconds)}
                </Button>
              ))}
            </div>

            {active && (
              <div className="space-y-4">
                <AudioPreview
                  src={active.audio_url ?? ''}
                  caption={active.text}
                  meta={`${active.provider} · ${active.model || 'default model'} · ${active.voice}`}
                />

                <Field>
                  <FieldLabel>Verdict</FieldLabel>
                  <div className="flex gap-2">
                    {VERDICTS.map((option) => (
                      <Button
                        key={option.value}
                        size="sm"
                        variant={verdict === option.value ? option.variant : 'outline'}
                        onClick={() => setVerdict(option.value)}
                      >
                        <option.icon className="size-4" /> {option.label}
                      </Button>
                    ))}
                  </div>
                </Field>

                <Field>
                  <FieldLabel htmlFor="rating">Intelligibility 1–5</FieldLabel>
                  <div className="flex items-center gap-2">
                    {[1, 2, 3, 4, 5].map((value) => (
                      <Button
                        key={value}
                        size="sm"
                        variant={rating === value ? 'default' : 'outline'}
                        onClick={() => setRating(value)}
                      >
                        {value}
                      </Button>
                    ))}
                  </div>
                </Field>

                <Field>
                  <FieldLabel>What did you hear?</FieldLabel>
                  <div className="flex flex-wrap gap-2">
                    {ARTIFACTS.map((artifact) => (
                      <Badge
                        key={artifact.key}
                        variant={tags.includes(artifact.key) ? 'default' : 'outline'}
                        className="cursor-pointer select-none"
                        onClick={() =>
                          setTags((prev) =>
                            prev.includes(artifact.key)
                              ? prev.filter((t) => t !== artifact.key)
                              : [...prev, artifact.key],
                          )
                        }
                      >
                        {artifact.label}
                      </Badge>
                    ))}
                  </div>
                </Field>

                <Field>
                  <FieldLabel htmlFor="review-note">Note</FieldLabel>
                  <Textarea
                    id="review-note"
                    rows={2}
                    placeholder="e.g. second syllable vowel is raised; usable for demos with a caption"
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                  />
                </Field>

                <div className="flex items-end gap-2">
                  <Field className="flex-1">
                    <FieldLabel htmlFor="reviewer">Reviewer</FieldLabel>
                    <Input
                      id="reviewer"
                      placeholder="alias (optional)"
                      value={reviewer}
                      onChange={(event) => setReviewer(event.target.value)}
                    />
                  </Field>
                  <Button onClick={submit} disabled={addReview.isPending}>
                    {addReview.isPending ? 'Saving…' : 'Save verdict'}
                  </Button>
                </div>
                {addReview.isError && (
                  <p className="text-sm text-destructive">{(addReview.error as Error).message}</p>
                )}

                <div className="space-y-2 border-t pt-3">
                  <p className="text-sm font-medium">History for this run</p>
                  {(reviews.data?.reviews ?? []).length === 0 && (
                    <p className="text-sm text-muted-foreground">No reviews yet.</p>
                  )}
                  {(reviews.data?.reviews ?? []).map((review) => (
                    <div key={review.id} className="text-sm">
                      <div className="flex items-center gap-2">
                        <Badge variant={review.verdict === 'pass' ? 'default' : 'outline'}>
                          {review.verdict}
                        </Badge>
                        {review.rating && <span className="text-xs">· {review.rating}/5</span>}
                        <span className="text-xs text-muted-foreground">
                          {new Date(review.created_at).toLocaleString()}
                          {review.reviewer ? ` · ${review.reviewer}` : ''}
                        </span>
                      </div>
                      {review.artifacts.length > 0 && (
                        <p className="text-xs text-muted-foreground">
                          {review.artifacts.join(', ')}
                        </p>
                      )}
                      {review.note && <p className="text-xs">{review.note}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
