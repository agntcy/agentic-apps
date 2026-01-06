# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import tempfile
from ioa_observe.sdk.decorators import tool

try:
    import speech_recognition as sr
    import pygame
    from gtts import gTTS
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Audio libraries not found. Audio functionalities will be disabled.")

class AudioSystem:
    def __init__(self):
        self.enabled = AUDIO_AVAILABLE
        self.tts_enabled = False
        self.speech_enabled = False
        
        if self.enabled:
            try:
                print("Initializing audio...")
                
                try:
                    self.recognizer = sr.Recognizer()
                    self.microphone = sr.Microphone()
                    with self.microphone as source:
                        self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    
                    self.recognizer.energy_threshold = 300
                    self.recognizer.dynamic_energy_threshold = True
                    self.recognizer.pause_threshold = 0.8
                    self.speech_enabled = True
                    print("Speech recognition ready")
                except Exception as e:
                    print(f"Speech recognition failed: {e}")
                    self.speech_enabled = False
                
                try:
                    pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=1024)
                    pygame.mixer.init()
                    self.tts_enabled = True
                    print("TTS system ready")
                except Exception as e:
                    print(f"TTS init failed: {e}")
                    self.tts_enabled = False
                    
            except Exception as e:
                print(f"Audio init failed: {e}")
                self.enabled = False
    
    @tool(name="listening_tool")
    async def listen(self, timeout=5):
        if not self.speech_enabled:
            return input("You: ").strip()
        
        print("Listening...")
        
        def _listen():
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=6)
                result = self.recognizer.recognize_google(audio, language='en-US')
                print(f"Recognized: '{result}'")
                return result.strip()
            except sr.UnknownValueError:
                return "UNCLEAR"
            except sr.WaitTimeoutError:
                return "TIMEOUT"
            except Exception:
                return "ERROR"
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _listen)
    
    @tool(name="speaking_tool")
    async def speak(self, text):
        print(f"Agent: {text}")
        
        if not self.tts_enabled:
            print("TTS: Not enabled, skipping audio")
            return
        
        def _speak():
            try:
                tts = gTTS(text=text, lang='en', slow=False)
                
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                    temp_file = tmp.name
                
                try:
                    tts.save(temp_file)
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    
                    max_wait = 30
                    wait_count = 0
                    while pygame.mixer.music.get_busy() and wait_count < max_wait * 20:
                        pygame.time.wait(50)
                        wait_count += 1
                    
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.stop()
                        
                finally:
                    try:
                        os.unlink(temp_file)
                    except Exception:
                        pass
                        
                return True
                        
            except Exception as e:
                print(f"TTS error: {e}")
                return False
        
        if self.tts_enabled:
            try:
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, _speak), 
                    timeout=35
                )
            except Exception as e:
                print(f"TTS: Error: {e}")
