import { useState, useEffect, useRef } from "react";
import axios from "axios";

export function useVoice(onTranscript) {
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const recognitionRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioSourceRef = useRef(null);
  const onTranscriptRef = useRef(onTranscript);

  // Sync the latest onTranscript callback ref
  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  // Initialize Speech Recognition
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let rec = null;
    if (SpeechRecognition) {
      rec = new SpeechRecognition();
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = "en-IN"; // English (India) language support for currencies/names

      rec.onstart = () => {
        setIsListening(true);
      };

      rec.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        console.log("Speech-To-Text result:", transcript);
        if (onTranscriptRef.current) {
          onTranscriptRef.current(transcript);
        }
      };

      rec.onerror = (e) => {
        console.error("Speech Recognition error:", e);
        setIsListening(false);
      };

      rec.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = rec;
    }

    return () => {
      if (rec) {
        try {
          rec.abort();
        } catch (err) {
          console.error("Error aborting SpeechRecognition:", err);
        }
      }
    };
  }, []);

  const startListening = () => {
    if (recognitionRef.current) {
      stopPlayback();
      try {
        recognitionRef.current.start();
      } catch (err) {
        console.error("Error starting SpeechRecognition:", err);
      }
    } else {
      alert("Speech Recognition not supported in this browser. Please use Google Chrome.");
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  };

  const stopPlayback = () => {
    // Stop ElevenLabs Web Audio
    if (audioSourceRef.current) {
      try {
        audioSourceRef.current.stop();
      } catch (e) {}
    }
    // Stop local SpeechSynthesis
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsPlaying(false);
  };

  const speakText = async (text) => {
    if (!voiceEnabled || !text) return;
    
    stopPlayback();
    
    try {
      // Try backend ElevenLabs endpoint
      const response = await axios.post("http://localhost:8080/voice/tts", { text }, {
        responseType: "arraybuffer",
        headers: { "Content-Type": "application/json" }
      });
      
      const audioData = response.data;
      if (!audioData || audioData.byteLength === 0) {
        throw new Error("No audio content returned");
      }

      // Play audio using Web Audio API
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }
      
      const ctx = audioContextRef.current;
      
      // Resume context if suspended (browser security autoplays)
      if (ctx.state === "suspended") {
        await ctx.resume();
      }

      const buffer = await ctx.decodeAudioData(audioData);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      
      source.onended = () => {
        setIsPlaying(false);
      };
      
      audioSourceRef.current = source;
      setIsPlaying(true);
      source.start(0);
      
    } catch (err) {
      console.warn("ElevenLabs TTS unavailable. Falling back to browser SpeechSynthesis.", err.message);
      
      // Fallback to browser SpeechSynthesis
      if (window.speechSynthesis) {
        const cleanText = text
          .replace(/[₹]/g, " Rupees ")
          .replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{27BF}]/gu, ""); // Strip out standard emojis to prevent vocalization
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 1.0;
        
        utterance.onstart = () => {
          setIsPlaying(true);
        };
        utterance.onend = () => {
          setIsPlaying(false);
        };
        utterance.onerror = () => {
          setIsPlaying(false);
        };
        
        window.speechSynthesis.speak(utterance);
      }
    }
  };

  return {
    voiceEnabled,
    setVoiceEnabled,
    isListening,
    isPlaying,
    startListening,
    stopListening,
    speakText,
    stopPlayback
  };
}
