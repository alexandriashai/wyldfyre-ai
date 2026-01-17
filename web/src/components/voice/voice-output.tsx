"use client";

import * as React from "react";
import { Play, Pause, Volume2, VolumeX, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

interface VoiceOutputProps {
  text: string;
  voice?: string;
  autoPlay?: boolean;
  onPlayStart?: () => void;
  onPlayEnd?: () => void;
  onError?: (error: string) => void;
  className?: string;
}

export function VoiceOutput({
  text,
  voice = "alloy",
  autoPlay = false,
  onPlayStart,
  onPlayEnd,
  onError,
  className,
}: VoiceOutputProps) {
  const [isLoading, setIsLoading] = React.useState(false);
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [volume, setVolume] = React.useState(1);
  const [isMuted, setIsMuted] = React.useState(false);
  const [audioUrl, setAudioUrl] = React.useState<string | null>(null);
  const [progress, setProgress] = React.useState(0);
  const [duration, setDuration] = React.useState(0);

  const audioRef = React.useRef<HTMLAudioElement | null>(null);
  const previousTextRef = React.useRef<string>("");

  // Cleanup audio URL on unmount
  React.useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  // Auto-play when text changes (if enabled)
  React.useEffect(() => {
    if (autoPlay && text && text !== previousTextRef.current) {
      previousTextRef.current = text;
      synthesizeAndPlay();
    }
  }, [text, autoPlay]);

  const synthesizeAndPlay = async () => {
    if (!text.trim()) return;

    setIsLoading(true);

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_VOICE_URL || "http://localhost:8001"}/api/synthesize`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            text: text,
            voice: voice,
            response_format: "mp3",
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Speech synthesis failed");
      }

      const audioBlob = await response.blob();
      const url = URL.createObjectURL(audioBlob);

      // Revoke previous URL
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }

      setAudioUrl(url);

      // Create and play audio
      const audio = new Audio(url);
      audio.volume = isMuted ? 0 : volume;
      audioRef.current = audio;

      audio.onloadedmetadata = () => {
        setDuration(audio.duration);
      };

      audio.ontimeupdate = () => {
        setProgress((audio.currentTime / audio.duration) * 100);
      };

      audio.onplay = () => {
        setIsPlaying(true);
        onPlayStart?.();
      };

      audio.onended = () => {
        setIsPlaying(false);
        setProgress(0);
        onPlayEnd?.();
      };

      audio.onerror = () => {
        onError?.("Failed to play audio");
        setIsPlaying(false);
      };

      await audio.play();

    } catch (error) {
      console.error("TTS error:", error);
      onError?.("Failed to synthesize speech. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const togglePlay = () => {
    if (!audioRef.current) {
      synthesizeAndPlay();
      return;
    }

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
    }
  };

  const toggleMute = () => {
    setIsMuted(!isMuted);
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? volume : 0;
    }
  };

  const handleVolumeChange = (value: number[]) => {
    const newVolume = value[0];
    setVolume(newVolume);
    setIsMuted(newVolume === 0);
    if (audioRef.current) {
      audioRef.current.volume = newVolume;
    }
  };

  const handleDownload = () => {
    if (audioUrl) {
      const a = document.createElement("a");
      a.href = audioUrl;
      a.download = "speech.mp3";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {/* Play/Pause button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={togglePlay}
        disabled={isLoading || !text.trim()}
        className="h-8 w-8"
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : isPlaying ? (
          <Pause className="h-4 w-4" />
        ) : (
          <Play className="h-4 w-4" />
        )}
      </Button>

      {/* Progress bar (optional, shown when audio is loaded) */}
      {duration > 0 && (
        <div className="flex-1 min-w-[100px]">
          <div className="h-1 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-100"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>{formatTime((progress / 100) * duration)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>
      )}

      {/* Volume controls */}
      <Button
        variant="ghost"
        size="icon"
        onClick={toggleMute}
        className="h-8 w-8"
      >
        {isMuted || volume === 0 ? (
          <VolumeX className="h-4 w-4" />
        ) : (
          <Volume2 className="h-4 w-4" />
        )}
      </Button>

      <Slider
        value={[isMuted ? 0 : volume]}
        max={1}
        step={0.1}
        onValueChange={handleVolumeChange}
        className="w-20"
      />

      {/* Download button */}
      {audioUrl && (
        <Button
          variant="ghost"
          size="icon"
          onClick={handleDownload}
          className="h-8 w-8"
        >
          <Download className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
