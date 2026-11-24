import {
  AudioPlayer,
  AudioPlayerControlBar,
  AudioPlayerDurationDisplay,
  AudioPlayerElement,
  AudioPlayerMuteButton,
  AudioPlayerPlayButton,
  AudioPlayerTimeDisplay,
  AudioPlayerTimeRange,
} from '@/components/ai-elements/audio-player'
import { cn } from '@/lib/utils'

/** Compact media-chrome player used by the result, runs and recordings panels. */
export function AudioPreview({
  src,
  label,
  caption,
  meta,
  className,
}: {
  src: string
  label?: string
  /** Text that was synthesized, shown above the player. */
  caption?: string | null
  /** Provider / model / voice summary line. */
  meta?: string | null
  className?: string
}) {
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      {label ? <span className="text-muted-foreground text-xs">{label}</span> : null}
      {caption ? <p className="text-sm">{caption}</p> : null}
      {meta ? <p className="text-muted-foreground text-xs">{meta}</p> : null}
      <AudioPlayer className="rounded-md border">
        <AudioPlayerElement src={src} preload="metadata" />
        <AudioPlayerControlBar>
          <AudioPlayerPlayButton />
          <AudioPlayerTimeRange />
          <AudioPlayerTimeDisplay />
          <AudioPlayerDurationDisplay />
          <AudioPlayerMuteButton />
        </AudioPlayerControlBar>
      </AudioPlayer>
    </div>
  )
}
