"""
Paleo Earth — AWS Lambda Handler
=================================
Routes (via API Gateway proxy integration):
  POST /chat  — Calls Amazon Bedrock (Claude 3 Haiku) with conversation history
  POST /tts   — Calls Amazon Polly (neural) and returns base64-encoded MP3

Environment: Python 3.11, us-east-1
"""

import os
import json
import base64
import boto3
import urllib.request
import urllib.error
import traceback

# ---------------------------------------------------------------------------
# AWS clients
# ---------------------------------------------------------------------------
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
polly   = boto3.client("polly",           region_name="us-east-1")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ANTHROPIC_DIRECT_MODEL = "claude-haiku-4-5-20251001"
BEDROCK_MODEL_ID       = "anthropic.claude-3-haiku-20240307-v1:0"
DEFAULT_VOICE_ID       = "Matthew"

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(status_code: int, body: dict) -> dict:
    """Build an API Gateway proxy-compatible response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _error(status_code: int, message: str, detail: str = "") -> dict:
    """Return a structured error response."""
    print(f"[ERROR {status_code}] {message} — {detail}")
    body = {"success": False, "error": message}
    if detail:
        body["detail"] = detail
    return _response(status_code, body)


def _parse_body(event: dict) -> dict:
    """
    API Gateway proxy delivers the request body as a JSON *string*.
    Parse it and return the resulting dict (or raise ValueError).
    """
    raw = event.get("body") or "{}"
    if isinstance(raw, str):
        return json.loads(raw)
    return raw  # already a dict in some test harnesses


def _build_system_prompt(ctx: dict) -> str:
    """
    Construct the system prompt anchored to the current geologic period and image gallery.

    ctx keys expected:
        label               — e.g. "Early Cambrian"
        ma                  — e.g. 530  (millions of years ago)
        period              — e.g. "Cambrian"
        systemPromptContext — multi-sentence context string about this period
        currentPeriodImages — list of images available for this period
        otherImages         — list of other images in the gallery
    """
    label   = ctx.get("label", "Unknown Period")
    ma      = ctx.get("ma", "?")
    period  = ctx.get("period", label)
    context = ctx.get("systemPromptContext", "")
    current_images = ctx.get("currentPeriodImages", [])
    other_images   = ctx.get("otherImages", [])
    is_mobile      = ctx.get("isMobile", False)
    
    device_context = "MOBILE DEVICE (Smartphone/Tablet)" if is_mobile else "DESKTOP DEVICE (Computer/Laptop)"


    image_gallery_text = ""
    if current_images:
        image_gallery_text += f"\nFeatured illustrations available in Paleo Earth for {label} ({ma} Ma):\n"
        for img in current_images:
            image_gallery_text += f"  - \"{img.get('title', '')}\" -> embed with: [[IMAGE: {img.get('title', '')}]] (tags: {img.get('tags', '')})\n"
    if other_images:
        image_gallery_text += f"\nOther prehistoric illustrations in the library from other periods:\n"
        for img in other_images:
            image_gallery_text += f"  - \"{img.get('title', '')}\" -> embed with: [[IMAGE: {img.get('title', '')}]]\n"

    return f"""You are an expert paleontologist and science educator for Paleo Earth, \
an interactive educational web application about Earth's prehistoric past.

The user is currently exploring the {label} ({ma} Ma — that is, {ma} million years ago), \
part of the {period} Period.

Key facts and context for this time period:
{context}

VISUAL ILLUSTRATION CAPABILITY & RULES:
Paleo Earth includes a visual paleoart library with authentic reconstructions by scientific illustrator Nobu Tamura (licensed CC BY-SA 4.0).
Your chat interface RENDERS THESE ILLUSTRATIONS DIRECTLY to the user on screen whenever you include an image embed tag: [[IMAGE: Title or Tag]].
{image_gallery_text}
CRITICAL INSTRUCTIONS FOR IMAGES:
1. NEVER say "I cannot display images", "I am a text-only AI", "I am unable to show pictures", or anything similar. You CAN and MUST display images by emitting [[IMAGE: Name or Tag]].
2. When the user asks to see an image, asks what an organism looked like, or asks for visual examples of life in this period, ALWAYS fulfill the request by embedding the tag: e.g. "Here is a reconstruction of the early chordate Haikouella: [[IMAGE: Haikouella lanceolata]]".
3. When explaining prehistoric life or answering questions naturally, proactively embed 1–2 relevant image tags from the catalog so the user can see what you are describing.
4. Only embed images that exist in the library catalog above. Do NOT invent image tags for animals that are not in the library.
5. If the user asks for an image of a specific animal not yet in the library (e.g. Anomalocaris or Hallucigenia), clearly describe what it looked like in text, and mention/embed a related creature from the gallery if applicable (e.g. "We don't have an illustration of Anomalocaris in the library yet, but here is another stem-arthropod from the Chengjiang fauna, Fuxianhuia protensa: [[IMAGE: Fuxianhuia protensa]]").

Your role and guidelines:
1. Answer questions engagingly and accurately for a general educational audience \
   (curious adults, students, enthusiasts — not specialists).
2. Anchor every answer in the correct geologic time: use full period names and Ma values \
   when referencing time (e.g. "during the Cambrian Period, around 520 Ma").
3. Keep responses focused and concise — aim for 2–4 paragraphs maximum. \
   Prioritise depth over breadth; it is fine to cover fewer topics well.
4. Do not fabricate fossil evidence or species names. If something is uncertain or \
   debated in the scientific literature, say so.
5. Write in a warm, curious, enthusiastic tone — make prehistoric life feel vivid and \
   exciting without sacrificing scientific accuracy.
6. Write in natural flowing prose. Avoid emojis, unicode pictographs, or raw markdown \
   tables, as your answers may be read aloud by text-to-speech audio.
7. You are the onboard guide for Paleo Earth. If the user asks how to use the app or where to find features, provide accurate assistance based on their current device.
8. NEVER answer questions completely unrelated to paleontology, Earth history, or using the Paleo Earth app (e.g., do not write code, do not give biographies of modern historical figures). Politely redirect them to Earth's history or app features.

APPLICATION NAVIGATION & INTERFACE GUIDE:
The user is currently using a {device_context}. Adjust your UI instructions accordingly.

Main Layout:
- Two main windows: the 3D Globe Window (user can drag to rotate) and the Text Window (where this chat is).
- On desktop, they are stacked horizontally (Globe left, Text right).
- Fullscreen Mode: On Desktop, click the square icon top-right of either window. On Mobile, drag the resizing bar all the way to the top (fullscreen text) or bottom (fullscreen globe).

Text Window Tabs:
- "Period Information" tab: encyclopedic description of the current era.
- "Ask Questions" tab: this chatbot.
- Text-to-Speech (TTS): Speaker buttons in the top right allow the user to have texts or chat responses read aloud.

Timeline Slider (Bottom of Globe Window):
- Features a geological timescale ribbon. Drag the knob to move through time (textures update every 5 million years).
- Play button: auto-plays the timeline animation.
- Keyframes: Snap points along the timeline. Period keyframes broadly describe the era. Event keyframes (marked with yellow dots) describe specific historical events (like mass extinctions).

Globe Window Overlays & Controls:
- Settings button: Change TTS voice (Matthew/Joanna) or Globe texture quality (Low/Medium/High).
- Borders button: Toggles modern political borders so users can see where modern nations were located in the deep past.
- Atmosphere button: Toggles climate gauges (O2, CO2, Surface Temp) for the current period.
- Continent button: Toggles outlines of ancient paleocontinents (e.g., Gondwana, Pangaea). Pointing at continents shows their names.
- About (?) button (bottom right): Shows app info and credits the scientists whose datasets were used."""


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def handle_chat(body: dict) -> dict:
    """
    POST /chat
    ----------
    Expected body:
      {
        "messages":      [{"role": "user"|"assistant", "content": "..."}],
        "systemContext": {"label": "...", "ma": 530, "period": "...", "systemPromptContext": "..."},
        "userMessage":   "What animals lived here?"
      }

    Appends userMessage to messages, calls Claude 3 Haiku via Bedrock,
    and returns the assistant reply.
    """
    messages       = body.get("messages", [])
    system_context = body.get("systemContext", {})
    user_message   = body.get("userMessage", "").strip()

    if not user_message:
        return _error(400, "userMessage is required and must not be empty.")

    # Append the latest user turn to the history
    messages = list(messages)  # shallow copy — don't mutate caller's list
    messages.append({"role": "user", "content": user_message})

    # Validate message structure — Bedrock is strict about alternating roles
    # and non-empty content; surface a helpful error rather than a cryptic 5xx.
    for i, msg in enumerate(messages):
        if msg.get("role") not in ("user", "assistant"):
            return _error(400, f"Message at index {i} has invalid role '{msg.get('role')}'.")
        if not str(msg.get("content", "")).strip():
            return _error(400, f"Message at index {i} has empty content.")

    system_prompt = _build_system_prompt(system_context)

    # -----------------------------------------------------------------------
    # Route 1: Direct Anthropic API (if ANTHROPIC_API_KEY is configured)
    # -----------------------------------------------------------------------
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key:
        print(f"[chat] Invoking Anthropic API directly model={ANTHROPIC_DIRECT_MODEL}, "
              f"history_length={len(messages)}, period={system_context.get('label')}")
        payload = {
            "model":      ANTHROPIC_DIRECT_MODEL,
            "max_tokens": 1024,
            "system":     system_prompt,
            "messages":   messages,
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key":         anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                blocks = resp_data.get("content", [])
                reply_text = " ".join(
                    b.get("text", "") for b in blocks if b.get("type") == "text"
                ).strip()
                if not reply_text:
                    return _error(502, "Anthropic API returned an empty response.")
                return _response(200, {"reply": reply_text, "response": reply_text, "success": True})
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            print(f"[chat] Anthropic API HTTP error {exc.code}: {err_body}")
            return _error(exc.code, "Anthropic API error.", err_body)
        except Exception as exc:
            print(traceback.format_exc())
            return _error(502, "Failed to call Anthropic API directly.", str(exc))

    # -----------------------------------------------------------------------
    # Route 2: Amazon Bedrock (default when ANTHROPIC_API_KEY is not set)
    # -----------------------------------------------------------------------
    request_payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens":        1024,
        "system":            system_prompt,
        "messages":          messages,
    }

    print(f"[chat] Invoking Bedrock model={BEDROCK_MODEL_ID}, "
          f"history_length={len(messages)}, period={system_context.get('label')}")

    try:
        bedrock_response = bedrock.invoke_model(
            modelId     = BEDROCK_MODEL_ID,
            contentType = "application/json",
            accept      = "application/json",
            body        = json.dumps(request_payload),
        )
    except bedrock.exceptions.AccessDeniedException as exc:
        return _error(403, "Bedrock model access denied. "
                           "Ensure the model is enabled in the AWS console "
                           "and the Lambda role has bedrock:InvokeModel permission.",
                      str(exc))
    except Exception as exc:
        print(traceback.format_exc())
        return _error(502, "Failed to call Bedrock.", str(exc))

    # Parse Claude's response
    response_body = json.loads(bedrock_response["body"].read())

    # The messages API returns content as a list of content blocks
    content_blocks = response_body.get("content", [])
    reply_text = " ".join(
        block.get("text", "") for block in content_blocks if block.get("type") == "text"
    ).strip()

    if not reply_text:
        print(f"[chat] Unexpected Bedrock response shape: {response_body}")
        return _error(502, "Bedrock returned an empty or unexpected response.")

    print(f"[chat] Reply length={len(reply_text)} chars, "
          f"stop_reason={response_body.get('stop_reason')}")

    return _response(200, {"reply": reply_text, "response": reply_text, "success": True})


def handle_tts(body: dict) -> dict:
    """
    POST /tts
    ---------
    Expected body:
      {
        "text":    "Text to synthesize...",
        "voiceId": "Matthew"   (optional, defaults to 'Matthew')
      }

    Returns:
      { "audio": "<base64 MP3>", "contentType": "audio/mpeg", "success": true }

    Note: The client is responsible for stripping markdown before sending;
    Polly receives plain text only (TextType='text').
    """
    text     = body.get("text", "").strip()
    voice_id = body.get("voiceId", DEFAULT_VOICE_ID) or DEFAULT_VOICE_ID

    if not text:
        return _error(400, "text is required and must not be empty.")

    # Polly has a hard limit of 3,000 characters for the SynthesizeSpeech action.
    # Truncate gracefully rather than failing, and warn in logs.
    POLLY_CHAR_LIMIT = 3000
    if len(text) > POLLY_CHAR_LIMIT:
        print(f"[tts] text length {len(text)} exceeds Polly limit "
              f"({POLLY_CHAR_LIMIT}); truncating.")
        text = text[:POLLY_CHAR_LIMIT]

    print(f"[tts] Synthesising speech: voiceId={voice_id}, text_length={len(text)}")

    try:
        polly_response = polly.synthesize_speech(
            Text       = text,
            VoiceId    = voice_id,
            Engine     = "neural",       # Higher quality, more natural delivery
            OutputFormat = "mp3",
            TextType   = "text",         # Plain text — markdown stripped client-side
        )
    except polly.exceptions.InvalidSsmlException as exc:
        # Shouldn't happen with TextType='text', but guard anyway
        return _error(400, "Invalid text sent to Polly.", str(exc))
    except polly.exceptions.UnsupportedPlsLanguageException as exc:
        return _error(400, "Unsupported language for Polly.", str(exc))
    except polly.exceptions.LexiconNotFoundException as exc:
        return _error(400, "Polly lexicon not found.", str(exc))
    except Exception as exc:
        print(traceback.format_exc())
        return _error(502, "Failed to call Polly.", str(exc))

    # Read and base64-encode the MP3 audio stream
    audio_bytes  = polly_response["AudioStream"].read()
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    print(f"[tts] Success: audio_bytes={len(audio_bytes)}, voice={voice_id}")

    return _response(200, {
        "audio":       audio_base64,
        "contentType": "audio/mpeg",
        "success":     True,
    })


# ---------------------------------------------------------------------------
# Main Lambda entry point
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context) -> dict:
    """
    API Gateway Lambda proxy integration entry point.

    Routing is determined by:
      event["httpMethod"]  — GET, POST, OPTIONS …
      event["path"]        — /chat, /tts, …
    """
    method = event.get("httpMethod", "").upper()
    path   = event.get("path", "")

    print(f"[handler] {method} {path}")

    # ---- CORS preflight -------------------------------------------------- #
    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers":    CORS_HEADERS,
            "body":       "",
        }

    # ---- Parse body ------------------------------------------------------- #
    try:
        body = _parse_body(event)
    except (json.JSONDecodeError, ValueError) as exc:
        return _error(400, "Request body must be valid JSON.", str(exc))

    # ---- Route ------------------------------------------------------------ #
    if path == "/chat" and method == "POST":
        return handle_chat(body)

    if path == "/tts" and method == "POST":
        return handle_tts(body)

    # ---- Unknown route ---------------------------------------------------- #
    return _error(404, f"Route not found: {method} {path}")
