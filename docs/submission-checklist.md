# Submission checklist

Compiled from the [official rules](https://nebiusglobalaihackathon.devpost.com/rules) and [hackathon home](https://nebiusglobalaihackathon.devpost.com/) (read 27 Oct 2026). Submission period ends **Friday 30 October 2026, 10:00 am Pacific Time**. Judging 1–15 Dec 2026. Winners around 11 Jan 2027.

## Devpost entry

- [ ] Register / join the hackathon on Devpost while eligible (age of majority; not a resident of a comprehensively sanctioned territory; not a judge or sponsor employee — see rules §3).
- [ ] Identify track: **Best Apps and Agents**.
- [ ] English text description (or translation) of features and functionality.
- [ ] URL of a **working demo** (hosted app or test build). Required for this track.
- [ ] Public repository URL (this GitHub repo).
- [ ] Open-source license **visible at the top of the repository page** (MIT `LICENSE` is present).
- [ ] README with setup and how to run.
- [ ] README / submission text highlights **NVIDIA Nemotron** and **where Token Factory is used**.
- [ ] Demonstration video **&lt; 3 minutes**, publicly visible on **YouTube**, no unlicensed music/trademarks.
- [ ] Video shows the project actually running, including Nemotron via Token Factory.
- [ ] Feedback field on Token Factory / AI Cloud / NVIDIA tools filled in.
- [ ] If any IRL Builders & Brews event was attended, select that city (City Winner Award).
- [ ] Project is new during the submission window (it is).

## Project requirements (rules)

- [ ] Working software, not a slide deck.
- [ ] Makes a **runtime call** to the Token Factory inference API **or** runs on Nebius AI Cloud compute. This app uses Token Factory chat completions.
- [ ] Uses at least one **NVIDIA open-source model** (Nemotron 3 Nano by default).
- [ ] Fits the track (practical app / copilot / workflow — not a robotics demo).
- [ ] Installs and runs as documented; behaves as the video claims.
- [ ] Third-party APIs (Materials Project, if used) authorized by their terms; keys not committed.

## Judging (equal weight)

| Criterion | How this repo answers |
| --- | --- |
| Technological implementation | Token Factory function calling, GP+EI ranking, labeled playbook, tests |
| Design | Agent / Plan / Review workspace, empty/loading/error/success, labeled data kinds |
| Potential impact | Specific audience (battery process researchers) plus run sheet — without overclaiming lab savings |
| Quality of the idea | Nemotron as a tool-using campaign manager, not a fake scientist |

## Before you click Submit

- [ ] Hosted demo stays up through **15 Dec 2026** judging (rules: free access for sponsor/judges until judging ends).
- [ ] `.env` is not in git; `.env.example` is.
- [ ] Live inference verified once with Nicole’s Token Factory key.
- [ ] Optional: deploy with `docs/deployment.md`.
