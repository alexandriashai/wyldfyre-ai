"use client";

import { useState, useRef, useCallback, useEffect } from "react";

interface UseVoiceOptions {
  onTranscription?: (text: string) => void;
  onError?: (error: string) => void;
  voiceServiceUrl?: string;
}

interface VoiceInfo {
  id: string;
  name: string;
  description: string;
}

export function useVoice({
  onTranscription,
  onError,
  voiceServiceUrl = process.env.NEXT_PUBLIC_VOICE_URL || "",
}: UseVoiceOptions = {}) {
  const isVoiceEnabled = Boolean(voiceServiceUrl);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [availableVoices, setAvailableVoices] = useState<VoiceInfo[]>([]);
  const [currentVoice, setCurrentVoice] = useState("alloy");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  // Fetch available voices on mount
  useEffect(() => {
    fetchVoices();
  }, [voiceServiceUrl]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
      }
    };
  }, []);

  const fetchVoices = async () => {
    if (!isVoiceEnabled) return;
    try {
      const response = await fetch(`${voiceServiceUrl}/api/synthesize/voices`);
      if (response.ok) {
        const voices = await response.json();
        setAvailableVoices(voices);
      }
    } catch (err) {
      console.error("Failed to fetch voices:", err);
    }
  };

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Set up audio analyser for level monitoring
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Monitor audio levels
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateLevel = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
        setAudioLevel(average / 255);
        animationFrameRef.current = requestAnimationFrame(updateLevel);
      };
      updateLevel();

      // Set up media recorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/mp4",
      });

      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Clean up
        stream.getTracks().forEach((track) => track.stop());
        if (audioContextRef.current) {
          audioContextRef.current.close();
          audioContextRef.current = null;
        }
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
        }
        setAudioLevel(0);

        // Process audio
        if (audioChunksRef.current.length > 0) {
          setIsProcessing(true);
          try {
            const audioBlob = new Blob(audioChunksRef.current, {
              type: mediaRecorder.mimeType,
            });
            await transcribeAudio(audioBlob);
          } catch (err) {
            onError?.(err instanceof Error ? err.message : "Transcription failed");
          } finally {
            setIsProcessing(false);
          }
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(100); // Collect data every 100ms
      setIsRecording(true);
    } catch (err) {
      onError?.(
        err instanceof Error ? err.message : "Failed to access microphone"
      );
    }
  }, [onError, voiceServiceUrl]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, [isRecording]);

  const transcribeAudio = useCallback(
    async (audioBlob: Blob) => {
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.webm");

      const response = await fetch(`${voiceServiceUrl}/api/transcribe`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Transcription request failed");
      }

      const data = await response.json();
      if (data.text) {
        onTranscription?.(data.text);
      }
    },
    [onTranscription, voiceServiceUrl]
  );

  const speak = useCallback(
    async (text: string, voice?: string) => {
      try {
        // Stop any currently playing audio
        if (currentAudioRef.current) {
          currentAudioRef.current.pause();
          currentAudioRef.current = null;
        }

        setIsSpeaking(true);

        const response = await fetch(`${voiceServiceUrl}/api/synthesize`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            text,
            voice: voice || currentVoice,
            response_format: "mp3",
          }),
        });

        if (!response.ok) {
          throw new Error("Speech synthesis request failed");
        }

        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        currentAudioRef.current = audio;

        audio.onended = () => {
          URL.revokeObjectURL(audioUrl);
          setIsSpeaking(false);
          currentAudioRef.current = null;
        };

        audio.onerror = () => {
          URL.revokeObjectURL(audioUrl);
          setIsSpeaking(false);
          currentAudioRef.current = null;
          onError?.("Failed to play audio");
        };

        await audio.play();
      } catch (err) {
        setIsSpeaking(false);
        onError?.(err instanceof Error ? err.message : "Speech synthesis failed");
      }
    },
    [currentVoice, onError, voiceServiceUrl]
  );

  const stopSpeaking = useCallback(() => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
      setIsSpeaking(false);
    }
  }, []);

  return {
    // State
    isRecording,
    isProcessing,
    isSpeaking,
    audioLevel,
    availableVoices,
    currentVoice,

    // Actions
    startRecording,
    stopRecording,
    speak,
    stopSpeaking,
    setCurrentVoice,

    // Legacy alias
    playAudio: speak,
  };
}
