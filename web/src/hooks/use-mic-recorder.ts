import { useCallback, useEffect, useRef, useState } from 'react'

export type RecorderStatus = 'idle' | 'recording' | 'stopped' | 'denied' | 'unsupported'

interface MicRecorderState {
  status: RecorderStatus
  seconds: number
  blob: Blob | null
  mime: string
  error: string
  /** Human-readable label of the capture device in use, for dataset notes. */
  deviceLabel: string
  start: (deviceId?: string) => Promise<void>
  stop: () => void
  reset: () => void
}

/**
 * Browser microphone capture via MediaRecorder. The audio stays in memory until
 * `upload` sends it to POST /api/recordings, where it is written to local
 * storage with a metadata sidecar. Nothing is sent to a hosted provider.
 */
export function useMicRecorder(): MicRecorderState {
  const [status, setStatus] = useState<RecorderStatus>('idle')
  const [seconds, setSeconds] = useState(0)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [mime, setMime] = useState('audio/webm')
  const [error, setError] = useState('')
  const [deviceLabel, setDeviceLabel] = useState('')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<number | null>(null)

  const clearTimer = () => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }

  const start = useCallback(
    async (deviceId?: string) => {
      setError('')
      setBlob(null)
      chunksRef.current = []
      if (typeof MediaRecorder === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
        setStatus('unsupported')
        setError('This browser has no MediaRecorder support. Use the file upload instead.')
        return
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: deviceId ? { deviceId: { exact: deviceId } } : true,
        })
        streamRef.current = stream
        const track = stream.getAudioTracks()[0]
        setDeviceLabel(track?.label ?? (deviceId ? 'selected device' : 'default device'))
        const type = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : MediaRecorder.isTypeSupported('audio/webm')
            ? 'audio/webm'
            : ''
        const recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined)
        recorderRef.current = recorder
        setMime(recorder.mimeType || 'audio/webm')
        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) chunksRef.current.push(event.data)
        }
        recorder.onstop = () => {
          const collected = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
          setBlob(collected.size > 0 ? collected : null)
          if (collected.size === 0) setError('Recording was empty.')
          stopStream()
          clearTimer()
        }
        recorder.onerror = () => {
          setError('Recorder failed. Check microphone permissions.')
          stopStream()
          clearTimer()
          setStatus('idle')
        }
        recorder.start()
        setStatus('recording')
        setSeconds(0)
        timerRef.current = window.setInterval(() => setSeconds((value) => value + 1), 1000)
      } catch (cause) {
        const name = cause instanceof DOMException ? cause.name : ''
        if (name === 'NotAllowedError' || name === 'SecurityError') {
          setStatus('denied')
          setError('Microphone permission denied. Allow it in the browser, or upload a file.')
        } else {
          setStatus('idle')
          setError(cause instanceof Error ? cause.message : 'Could not open the microphone.')
        }
        stopStream()
      }
    },
    [],
  )

  const stop = useCallback(() => {
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
      setStatus('stopped')
    }
    clearTimer()
  }, [])

  const reset = useCallback(() => {
    setBlob(null)
    setSeconds(0)
    setStatus('idle')
    setError('')
    chunksRef.current = []
  }, [])

  useEffect(
    () => () => {
      clearTimer()
      stopStream()
    },
    [],
  )

  return { status, seconds, blob, mime, error, deviceLabel, start, stop, reset }
}
