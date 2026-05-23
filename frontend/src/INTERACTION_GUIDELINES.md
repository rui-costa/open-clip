# Development Protocol: UI Interaction Standards

## 1. Interaction Guidelines
- **Strictly No `window.alert`, `window.confirm`, or `window.prompt`**: Use of browser-native alert dialogs is strictly forbidden in this codebase. They are intrusive, unstyleable, and disrupt the user experience.
- **In-UI Components Only**: All confirmations, alerts, and feedback must be handled through custom React components within the application UI (e.g., modals, toast notifications, inline confirmation overlays).
- **Accessibility & Design**: Any custom UI confirmation must be keyboard accessible, provide screen reader support (ARIA), and adhere to the project's visual design system.

## 2. Enforcement
- **Code Review**: Any pull request containing `window.alert`, `window.confirm`, or `window.prompt` will be automatically rejected.
- **Refactoring Requirement**: If such code is discovered, it must be immediately replaced with an in-UI equivalent.
