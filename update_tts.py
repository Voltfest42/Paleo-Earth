import sys

with open("js/tts.js", "r", encoding="utf-8") as f:
    js = f.read()

find = "import { DEV_MODE, API_BASE, POLLY_VOICE_ID } from './config.js';"
replace = """import { DEV_MODE, API_BASE, POLLY_VOICE_ID } from './config.js';

// Get user preferred voice, or default
export function getPollyVoice() {
  return localStorage.getItem('paleo_tts_voice') || POLLY_VOICE_ID;
}

export function setPollyVoice(voiceId) {
  localStorage.setItem('paleo_tts_voice', voiceId);
}"""

js = js.replace(find, replace)

find2 = "body: JSON.stringify({ text: clean, voiceId: POLLY_VOICE_ID }),"
replace2 = "body: JSON.stringify({ text: clean, voiceId: getPollyVoice() }),"

js = js.replace(find2, replace2)

with open("js/tts.js", "w", encoding="utf-8") as f:
    f.write(js)
