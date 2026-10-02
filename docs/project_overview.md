# Paleo Earth: Project Overview

## What is Paleo Earth?
Paleo Earth is an educational web application designed to allow users to interactively explore the geological, climatic, and biological history of Earth. It presents a 3D interactive globe that updates dynamically as the user scrubs through a geologic timeline.

## Key Functional Modules

1. **The Globe View**
   - An interactive 3D WebGL globe (powered by Three.js).
   - Features dynamic textures for diffuses, normals, roughness, and political borders spanning from 540 Ma (Million years ago) to Present Day.
   - Textures can be hot-swapped between High, Medium, and Low quality tiers for performance.
   - Features dynamic lighting, atmospheric Fresnel effects, and shadow lifting.

2. **The Time Slider**
   - A timeline scrubber (0 to 540 Ma) that allows users to travel through time.
   - Includes a Geologic Time Scale (GTS) ribbon above the slider, visually delineating periods (e.g., Cambrian, Jurassic) with standard geological colors.
   - Snaps to specific "Keyframes" (Periods and Extinction Events) for precise viewing.

3. **Keyframe Data and Summaries**
   - As the slider hits a keyframe, a side panel dynamically updates to provide a summary of the era or event.
   - Data is driven by a localized JSON database mapping Ma values to descriptions, periods, and subtitles.

4. **The Text Window (Wiki & Chatbot)**
   - **Wiki Tab**: Displays an in-depth, formatted educational summary of the currently selected era.
   - **Ask Questions Tab**: A built-in AI chatbot connected to AWS Lambda and Amazon Bedrock. The chatbot is context-aware, anchoring its responses to the specific geologic time period the user is currently viewing.

5. **Text-to-Speech (TTS) Integration**
   - Uses Amazon Polly (via AWS Lambda) to read wiki entries and chatbot responses aloud.
   - Features a settings modal to toggle voices (e.g., Matthew vs Joanna) and manage playback.
