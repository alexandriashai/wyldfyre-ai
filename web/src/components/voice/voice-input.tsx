"use client";

import * as React from "react";
import { Mic, MicOff, Square, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface VoiceInputProps {
  onTranscription: (text: string) => void;
  onError?: (error: string) => void;
  disabled?: boolean;
  className?: string;
  mode?: "push-to-talk" | "toggle";
}

export function VoiceInput({
  onTranscription,
  onError,
  disabled = false,
  className,
  mode = "toggle",
}: VoiceInputProps) {
  const [isRecording, setIsRecording] = React.useState(false);
  const [isProcessing, setIsProcessing] = React.useState(false);
  const [audioLevel, setAudioLevel] = React.useState(0);

  const mediaRecorderRef = React.useRef<MediaRecorder | null>(null);
  const audioChunksRef = React.useRef<Blob[]>([]);
  const analyserRef = React.useRef<AnalyserNode | null>(null);
  const animationFrameRef = React.useRef<number>();

  // Cleanup on unmount
  React.useEffect(() => {
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      stopRecording();
    };
  }, []);

  const updateAudioLevel = React.useCallback(() => {
    if (!analyserRef.current) return;

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);

    // Calculate average level
    const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
    setAudioLevel(Math.min(100, average));

    if (isRecording) {
      animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
    }
  }, [isRecording]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });

      // Set up audio analyser for level visualization
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Create media recorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });

      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop());

        if (audioChunksRef.current.length > 0) {
          await processRecording();
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(100); // Collect data every 100ms
      setIsRecording(true);

      // Start audio level monitoring
      animationFrameRef.current = requestAnimationFrame(updateAudioLevel);

    } catch (error) {
      console.error("Failed to start recording:", error);
      onError?.("Failed to access microphone. Please check permissions.");
    }
  };

  const stopRecording = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }

    setIsRecording(false);
    setAudioLevel(0);
  };

  const processRecording = async () => {
    setIsProcessing(true);

    try {
      const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });

      // Create form data
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.webm");

      // Send to voice service
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_VOICE_URL || "http://localhost:8001"}/api/transcribe`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error("Transcription failed");
      }

      const result = await response.json();

      if (result.text) {
        onTranscription(result.text);
      }

    } catch (error) {
      console.error("Transcription error:", error);
      onError?.("Failed to transcribe audio. Please try again.");
    } finally {
      setIsProcessing(false);
      audioChunksRef.current = [];
    }
  };

  const handleToggle = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const handlePushToTalkStart = () => {
    if (!isRecording && !isProcessing) {
      startRecording();
    }
  };

  const handlePushToTalkEnd = () => {
    if (isRecording) {
      stopRecording();
    }
  };

  if (mode === "push-to-talk") {
    return (
      <Button
        variant={isRecording ? "destructive" : "secondary"}
        size="icon"
        disabled={disabled || isProcessing}
        className={cn("relative", className)}
        onMouseDown={handlePushToTalkStart}
        onMouseUp={handlePushToTalkEnd}
        onMouseLeave={handlePushToTalkEnd}
        onTouchStart={handlePushToTalkStart}
        onTouchEnd={handlePushToTalkEnd}
      >
        {isProcessing ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : isRecording ? (
          <>
            <Mic className="h-4 w-4" />
            <span
              className="absolute inset-0 rounded-md bg-red-500/20 animate-pulse"
              style={{ transform: `scale(${1 + audioLevel / 200})` }}
            />
          </>
        ) : (
          <Mic className="h-4 w-4" />
        )}
      </Button>
    );
  }

  return (
    <Button
      variant={isRecording ? "destructive" : "secondary"}
      size="icon"
      disabled={disabled || isProcessing}
      className={cn("relative", className)}
      onClick={handleToggle}
    >
      {isProcessing ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : isRecording ? (
        <>
          <Square className="h-4 w-4" />
          <span
            className="absolute inset-0 rounded-md bg-red-500/20"
            style={{
              transform: `scale(${1 + audioLevel / 200})`,
              transition: "transform 0.1s ease-out",
            }}
          />
        </>
      ) : (
        <Mic className="h-4 w-4" />
      )}
    </Button>
  );
}
