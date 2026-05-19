# 0005 - Add wellness agent

Date: 2026-05-18

## Status

Accepted

## Context

The live schedule had news, sport, and weather. The channel needs a lighter
segment about fitness, wellbeing, personal care, and everyday habits, with
fresh material and small anecdotes.

## Decision

Add a `wellness` character to the director rotation. The scraper now collects
ANSA Salute&Benessere and ANSA Lifestyle RSS items, then mixes them with local
rotating wellness prompts. Selection prioritizes lighter lifestyle and habit
items and penalizes heavy clinical/crisis headlines.

## Consequences

The rotation becomes `news`, `sport`, `wellness`, `meteo`. The wellness segment
can still run when RSS items are too clinical because local evergreen prompts
provide a fresh practical angle.
