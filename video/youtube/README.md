# YouTube upload kit

Everything to paste into YouTube Studio for `video/forecast_2026.mp4`. All numbers match the video and
the repository's outputs (model run of 1 November 2026).

## Thumbnail

`thumbnail.png`: 1280×720, under 2 MB, as YouTube recommends. It shows the real forecast map in the
GUI's palette.

To re-render it after the data changes, run this from `video/`:

```bash
node render.mjs --thumbnail
```

The thumbnail answers what the title asks: the title is a question, and the thumbnail shows 80%.

## Title

**Who Controls the Senate After 2026? I Simulated the Election 50,000 Times**

Alternatives:
- I Built a 2026 Senate Forecast Model: Democrats Win Control in 80% of Simulations
- 2026 Senate Forecast: Polls, Fundamentals and 50,000 Simulated Elections
- How I Forecast Every 2026 Senate Race (and Tested It on 14 Past Elections)

## Description

```text
Who controls the U.S. Senate after the 2026 midterms? I built a statistical forecast that blends polls with fundamentals, simulates the election 50,000 times, and was tested on 14 past elections.

Code, data and full methodology: https://github.com/JanGradkowski/senate-forecast-2026

THE FORECAST (model run of 1 November 2026)
• Democrats + independents control the Senate in 80% of simulations; Republicans in 20%
• Median outcome: 52–48. 80% range: 49 to 55 seats
• A 50–50 tie happens 9% of the time, and the Republican vice president breaks it
• Closest races: Iowa (Turek 51%), Alaska (Sullivan 52%), Nebraska (Ricketts 61%), Maine (Jackson 73%), Kansas (Marshall 74%), South Carolina (Graham 77%), Texas (Talarico 85%)

HOW THE MODEL WORKS
1. Fundamentals: a Huber robust regression on each state's partisan lean, the generic ballot, a midterm penalty and incumbency (worth about 13 points)
2. Polls: a recency-weighted average with pollster house effects removed (ridge regression)
3. Blend: polls and fundamentals weighted by their precision. The more polls a race has, the more the polls count
4. Uncertainty: correlated, fat-tailed errors at the national, regional and race level, because polling misses are shared across states
5. Simulation: 50,000 simulated elections, including Georgia's runoff rule

HOW WELL IT WORKS
Tested out of sample on 14 elections (1998–2024, 473 races), each year hidden from the model:
• 93.9% of winners called correctly
• Its 80% ranges contained 80.3% of results
• Log loss 0.129, against 0.298 for fundamentals alone

CHAPTERS
0:00 Who controls the Senate after 2026?
0:14 Fundamentals and polls
0:26 The blend and correlated errors
0:39 50,000 simulations and validation
0:52 The 2026 forecast: the closest races

Built with Python (statsmodels, numpy, pandas) and D3.js. The video was rendered frame by frame from the project's own interactive map with headless Chromium and ffmpeg. The music and sound effects were synthesised in code for this video.

This is a model forecast, not a betting price or advice. It is an independent student project, not affiliated with any campaign, pollster or news organisation.

#2026Midterms #SenateForecast #DataScience
```

## Tags

Paste as one line. The whole field is 478 of 500 characters, counting the quotes YouTube adds around
multi-word tags.

```text
2026 senate forecast, 2026 midterms, senate forecast, senate election 2026, 2026 senate map, senate predictions 2026, who will win the senate, senate control 2026, midterm elections 2026, election forecast, election model, election simulation, monte carlo simulation, polling average, polls, data science, statistics, data visualization, forecasting, python, d3js, iowa senate race, maine senate race, texas senate race, nebraska senate race, alaska senate race
```

## Settings

| Setting | Choice |
|---|---|
| Category | News & Politics for reach, or Science & Technology if the goal is a data-science portfolio |
| Made for kids | No |
| Altered or synthetic content | No. The disclosure covers realistic footage of people, places or events; data graphics and synthesised music don't need it |
| Chapters | Leave automatic chapters on. The five timestamps above each last 10 s or more, as YouTube requires |
| Pinned comment | "Full code, data and methodology, including how the model was tested on 14 past elections: https://github.com/JanGradkowski/senate-forecast-2026" |
| Timing | Publish before election day, Tuesday 3 November. The forecast is a snapshot from 1 November |
