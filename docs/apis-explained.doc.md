# The APIs, in plain words

Why this file exists: the other docs explain *how* each API works, in
detail. This one explains *what* each API is for, in one page, with no
jargon.

Two of the ten are built.

---

## The big picture

Spotify's chat and player already exist. This system sits behind them and
gives them a memory.

```
   Listener talks to Spotify
            │
            ▼
   ┌─────────────────────────────────┐
   │  1. Write it down    ✅ built    │
   │  2. Decide what matters ✅ built │
   │  3. Save it          (next)     │
   │  4. Find it again    (later)    │
   │  5. Use it in a reply(later)    │
   └─────────────────────────────────┘
```

Right now we can write things down and work out what matters. We cannot
yet save it — so the system still forgets everything.

---

## API 1 — `POST /v1/events`

### What it does

**Writes down that something happened.**

Someone presses play, skips a track, or types a message. The Spotify app
tells us. We check it is allowed, then store it.

### Who calls it

The Spotify app, automatically. **Not a person.** Nobody types into this.
The listener never sees it and never knows it ran.

### A real example

The listener types *"I don't want country music"* in Spotify chat. The
chat app sends us:

```
who      : user_001
what     : an AI interaction
where    : chat
when     : today at 12:00
they said: "I don't want country music"
```

We reply `evt_8fae2a5d3bbf` — a receipt. Done.

### What it checks before storing

| Check | Why |
|---|---|
| Is this a real caller? | Anyone must not be able to write into someone's history |
| Is this *their* data? | user_002 must not write into user_001's history |
| Did they agree to be remembered? | We check **our** record, not what the caller claims |
| Have we seen this already? | The network retries; one event must not be stored twice |
| Are they sending too fast? | 120 a minute, then we say no |

### The important one

Consent. The app tells us *"they agreed"* — **and we ignore that** and
check our own database. If our record says they opted out, we refuse, even
though the app said otherwise.

A caller cannot talk its way past consent.

### What it does not do

It does not decide whether anything is worth remembering. That is API 2.

---

## API 2 — `POST /v1/memories/extract`

### What it does

**Decides what is worth remembering.**

A listener says a hundred things. Most mean nothing. This sorts them.

```
"hi"                         -> forget it
"play this"                  -> forget it
"I don't want country music" -> REMEMBER THIS ONE
```

### Who calls it

Also the app, automatically, after an event is stored.

### A real example

We ran this for real. The listener said:

> *"honestly I don't want any more country music, I prefer The Weeknd
> while working"*

One sentence, and out came **two** separate memories:

```
1. exclusion             "Does not want to hear country music."
                         keep for 730 days

2. explicit_preference   "Prefers listening to The Weeknd while working."
                         keep for 365 days
```

### The five kinds of memory

| Kind | Means | Example |
|---|---|---|
| Episode | happened once | "played focus music this morning" |
| Explicit preference | they said so | "I prefer instrumental" |
| Candidate preference | we suspect it | three folk playlists this week |
| Exclusion | do not do this | "no country music" |
| Correction | we had it wrong | "no, I never liked jazz" |

And a sixth answer: **nothing worth remembering.** That is a correct
answer, not a failure.

### How it decides

Two steps.

**Step 1 — an AI reads the sentence.** Needed because no keyword rule can
tell these apart:

- *"I don't want country music"* → a refusal
- *"I don't want to stop listening"* → enthusiasm

Same words, opposite meaning. And it works in any language.

**Step 2 — our own rules check the AI's answer.** The AI suggests; our
code decides. It throws things out for six reasons:

| Rule | Example of what it stops |
|---|---|
| Must be one of the five kinds | AI invents "mood" → dropped |
| Must have real text | empty → dropped |
| **Nothing private** | "is depressed" → dropped |
| Confidence must be a number | "very sure" → dropped |
| **One play is not a preference** | pressed play once → not a preference |
| Not absurdly long | 10,000 characters → dropped |

### The two rules worth knowing

**Nothing private.** If someone says *"I listen to sad songs because I'm
depressed"*, the music part may be kept — but *"is depressed"* is thrown
away. We do not build a picture of someone's mental state.

**One play is not a preference.** Playing a country song once does not
mean they like country. A preference needs them to *say* it, or to happen
again and again.

### Two more things it does

**Same name, different spelling.** These are one artist, not four:

```
"the weeknd"  "The Weeknd"  "WEEKND"  "Abel Tesfaye"
                    ↓
            artist_the_weeknd
```

Without this, a search for The Weeknd would find nothing.

If a name is not in our catalog, we keep the words but claim no match.
Guessing wrong would attach the memory to the wrong artist.

**Said twice is still one fact.**

```
Monday : "I like instrumental music"
Friday : "I prefer instrumental"
           ↓
     one memory, from two events
```

Both events are kept as the source, so nothing becomes untraceable.

### How long things are kept

| Kind | Kept for | Why |
|---|---|---|
| Exclusion | 730 days | Forgetting one means doing what they forbade |
| Correction | 730 days | The old wrong belief could come back |
| Explicit preference | 365 days | They said it outright |
| Candidate preference | 90 days | Only a guess |
| Episode | 30 days | One thing that happened |

### What it does not do

**It does not save anything.** It works out what *should* be remembered
and hands the answer back. Nothing is written down.

That is API 3.

---

## What this means today

If a listener says *"no country music"* right now:

- API 1 writes down that they said it ✅
- API 2 works out it is an exclusion ✅
- Nothing saves it ❌
- Tomorrow, the system has forgotten ❌

**The loop is not closed yet.** Three more APIs close it:

| | |
|---|---|
| API 3 | Save the memory so it survives |
| API 4 | Find it when they ask something related |
| API 5 | Hand it to the AI so the reply uses it |

---

## Where to read more

| Doc | What is in it |
|---|---|
| `events.doc.md` | API 1 in detail |
| `memories-extract.doc.md` | API 2 in detail |
| `HOW_IT_WORKS.md` | API 1 line by line, with the code |
| `REQUIREMENTS.md` | What the project has to deliver |
