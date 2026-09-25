# Fun Fact for Today

**Fun Fact for Today** gives you a fun fact about today's date (or any other date) from Wikipedia's *On this day* feed. You get historical events, famous birthdays, notable deaths and holidays as ready-to-share sentences, with Wikipedia links and images. No API key or setup needed.

## What can Fun Fact for Today do?

- 🎲 Pick a **random fun fact for today** with one click
- 📅 Look up **any date**: `2026-12-24` or just `12-24`
- 🗂️ Choose fact types: **selected highlights, events, births, deaths, holidays**
- 🌍 Use **other Wikipedia languages** (`de`, `fr`, `sv`, …)
- 🕐 Decide what "today" means with a **timezone** setting
- 🖼️ Get **Wikipedia links, summaries and thumbnails** for each fact
- ⏰ Run it on a **schedule** and send the fact to Slack, email or a webhook with [Apify integrations](https://docs.apify.com/platform/integrations)

## What data does it return?

| Field | Description |
|---|---|
| `funFact` | Ready-to-share sentence, e.g. *On September 25, 1789: The United States Congress passes twelve constitutional amendments…* For non-English Wikipedias it's language-neutral: *25. 9. 1792: …* |
| `text` | Original text from Wikipedia |
| `type` | `selected`, `events`, `births`, `deaths` or `holidays` |
| `year` / `yearsAgo` | When it happened (negative years are BC) and how many years ago from today |
| `wikipediaTitle`, `wikipediaExtract`, `wikipediaUrl` | Related Wikipedia article |
| `thumbnailUrl` | Article image, if there is one |
| `date`, `language` | Date (MM-DD) and Wikipedia language |

## How to get a fun fact for today

1. Click **Try for free** / **Start**.
2. Keep the defaults for one random highlight in English, or change the fact types, number of facts, language or date.
3. Click **Start** and open the **Output** tab.

## Input

| Field | Default | Description |
|---|---|---|
| `factTypes` | `["selected"]` | Which kinds of facts to include |
| `maxFacts` | `1` | How many facts to return (1–500) |
| `randomize` | `true` | Random pick. When off, facts keep Wikipedia's order (newest first) and alternate between the selected types |
| `language` | `en` | Wikipedia language code |
| `date` | today | `YYYY-MM-DD` or `MM-DD` (only month and day are used for the lookup) |
| `timezone` | `UTC` | IANA timezone that decides what "today" is, e.g. `Europe/Prague` |

```json
{
    "factTypes": ["selected", "births"],
    "maxFacts": 3,
    "randomize": true,
    "language": "en",
    "timezone": "Europe/Prague"
}
```

## Output

All facts go to the default **dataset** (exportable as JSON, CSV, Excel or HTML). The first fact is also saved as the `FUN_FACT` record in the key-value store, which is handy for integrations.

```json
{
    "date": "09-25",
    "type": "selected",
    "year": 1789,
    "yearsAgo": 237,
    "text": "The United States Congress passes twelve constitutional amendments, ten of which later become the Bill of Rights.",
    "funFact": "On September 25, 1789: The United States Congress passes twelve constitutional amendments, ten of which later become the Bill of Rights.",
    "wikipediaTitle": "United States Bill of Rights",
    "wikipediaUrl": "https://en.wikipedia.org/wiki/United_States_Bill_of_Rights",
    "thumbnailUrl": "https://upload.wikimedia.org/...",
    "language": "en"
}
```

## How much does it cost?

One run makes a single API request and finishes in a few seconds on 256 MB of memory, so it uses a tiny fraction of a compute unit. A daily schedule fits comfortably within the Apify free plan.

## Use it through the API

```bash
curl -X POST "https://api.apify.com/v2/acts/<username>~fun-fact-for-today/run-sync-get-dataset-items?token=<YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"maxFacts": 1}'
```

## FAQ

**Where does the data come from?** From the public [Wikimedia "On this day" feed](https://api.wikimedia.org/wiki/Feed_API/Reference/On_this_day). The content is available under [CC BY-SA](https://creativecommons.org/licenses/by-sa/4.0/). Please credit Wikipedia when you publish the facts.

**Which languages work?** Every Wikipedia edition that publishes the feed. If a language isn't supported, the run fails with a clear message.

**Why is "today" a different day than I expected?** "Today" is based on the `timezone` input (UTC by default). Set it to your timezone.

**Found a bug or have an idea?** Open an issue in the **Issues** tab.
