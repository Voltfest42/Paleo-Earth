# Paleo Earth: Project Plan & Roadmap

## Phase 1: MVP and Core Engine (Completed)
- Initial setup of the Three.js 3D globe.
- Implementation of the time slider and basic texture swapping.
- Setup of the local development environment and basic CSS layout.

## Phase 2: UI/UX & Educational Features (Completed)
- Implementation of the dual-tab text window (Wiki & Ask Questions).
- Integration of the context-aware chatbot (AWS Lambda/Bedrock).
- Integration of Text-to-Speech (Amazon Polly).
- Addition of the Geologic Time Scale (GTS) ribbon to the time slider.

## Phase 3: Optimization and Polish (Completed)
- Mobile responsiveness (resizing fixes, touch-friendly UI adjustments).
- Dynamic texture quality settings (High, Medium, Low) for performance scaling.
- Batch python scripts for generating and processing diffuse, normal, roughness, and border SVGs into exact filename conventions.

## Phase 4: Interactive 3D Paleocontinents (Up Next)
- **Goal**: Allow dynamic interaction with the globe to identify ancient and modern continents.
- **Features**: 3D bounding boxes and overlay textures for continents (e.g., Gondwana, Laurasia).
- **Interactions**: Hover/click events that trigger inner glows on borders and display the continent's name.

## Phase 5: Production and Logistics (Future)
- Transitioning from development hosting to a production domain.
- Optimizing API costs (Amazon Bedrock and Polly).
- Finalizing hosting infrastructure and CI/CD pipelines.

## Phase 6: Post-Launch Features (Speculative)
- Additional datasets (e.g., temperature/climate gauges, fossil site locators).
- Extended timeframes or higher fidelity assets.
