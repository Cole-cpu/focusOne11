# FocusOne Product Requirements

## Problem statement
FocusOne is a mobile-first student productivity and study planning app that helps students turn exams, assignments, and topic lists into a calm daily study rhythm. It supports synced accounts, planning, tasks, focus sessions, active recall, reminders, and study analytics.

## Architecture
- Expo SDK 54 / Expo Router React Native frontend with adaptive light/dark styling.
- FastAPI backend on port 8001 with JWT authentication and MongoDB persistence.
- SecureStore on native and AsyncStorage on web preview for session persistence.
- REST API under `/api` for accounts, dashboard, schedules, parsing, tasks, flashcards, and focus logs.

## User personas
- Students balancing cycle tests, exams, assignments, and inconsistent study habits.
- Students who need one clear next action rather than a high-pressure productivity system.

## Core requirements (static)
- First-launch sign-in and account creation.
- Account-based sync of schedules, tasks, flashcards, and focus logs.
- Manual, paste, and text-file schedule entry with parsing preview support.
- Daily dashboard with timeline, upcoming milestones, task progress, and streak metric.
- Task creation, priority/status data, and completion interaction.
- Pomodoro focus timer with presets and focus session logging endpoint.
- Active recall card creation.
- Adaptive system theme and mobile bottom navigation.
- In-app reminder content; device notifications are deferred.

## Implemented (2026-08-18)
- Built FocusOne auth, dashboard, Plan, Focus, and Review mobile screens.
- Added JWT auth, MongoDB-backed domain APIs, parser punctuation handling, and CRUD regression coverage.
- Added web-safe session persistence, upload picker entry, immediate task reconciliation, and focus logging.
- Verified sign-in preview, account registration, dashboard, task creation, backend API flow, and parser with automated checks.
- Rewrote `build_plan` to spread topics evenly across the full runway (no clustering), give each topic balanced Learn/Recall coverage, add periodic rest days, close with a full-review day, and gracefully handle past/short windows. Verified via API across 14/5/2-day and past-date scenarios.
- Applied a dark blue theme as the app default (deep navy canvas, bright blue accents) and added "Brought to you by Vantage Intelligence" branding with the extracted Vantage logo on the sign-in screen and app footer.
- Added time-accurate greeting (morning/afternoon/evening from device time), a white-noise / ambient sound player on Focus (White/Pink/Brown/Rain loops via expo-audio), and local device deadline reminders (expo-notifications, 3-day/1-day/morning-of, no keys, web no-op) with a Remind-me toggle + Open-Settings banner. Fixed bottom-nav overlap by reserving nav height on the scroll.
- Built **Vantage AI** tutor (own bottom tab "Tutor"): Claude Sonnet 4.6 via emergentintegrations Universal key. Warm/patient persona, Socratic guidance (hint→answer), concise plain-text-math responses, quick actions (Explain/Quiz/Flashcards/Summarise/Study plan/Homework), Grade→Subject→Topic context, and personalisation from the student's real exams/tasks/focus data (never fabricates stats). Backend: POST/GET/DELETE /api/ai/* + GET/PUT /api/profile with per-user conversation persistence. Verified end-to-end by testing agent (backend 9/9 + full frontend flow).

## Implemented (2026-08-18)
- Built FocusOne auth, dashboard, Plan, Focus, and Review mobile screens.
- Added JWT auth, MongoDB-backed domain APIs, parser punctuation handling, and CRUD regression coverage.
- Added web-safe session persistence, upload picker entry, immediate task reconciliation, and focus logging.
- Verified sign-in preview, account registration, dashboard, task creation, backend API flow, and parser with automated checks.
- Rewrote `build_plan()` timetable generator: study blocks now spread evenly across the FULL runway to the exam (no cramming/gaps), every topic gets balanced Learn+Recall coverage, periodic rest days, and a final full-review day; past/short windows handled gracefully. Backend 12/12 tests pass (iteration 6).
- Fixed bottom-Nav overlap regression (raised Today paddingBottom to 150) so add-task/stats sit above the tab bar; replaced hardcoded date eyebrow with a live date.

## Prioritized backlog
- P1: Add in-app reminder configuration and reminder list screen (3-day/1-day/morning-of).
- P1: Add subject selection and editable focus-session logging.
- P1: Add weekly subject-hours visualization and detailed streak history.
- P2: Add device notifications after permission UX is designed.
- P2: Add selectable background/white-noise playback for Pomodoro.
- P2: Add richer file formats and OCR/import guidance.

## P0 / P1 / P2 remaining
- P0: Generated timetable persistence and display is the next core planning milestone.
- P1: Reminder center, richer analytics, and subject-aware focus sessions.
- P2: Device notifications, sound/white noise, and broader document parsing.

## Next tasks
1. Generate and store a balanced daily plan whenever a schedule is confirmed.
2. Render generated blocks and intentional rest days in Today.
3. Add reminder preferences and upcoming deadline reminder rows.