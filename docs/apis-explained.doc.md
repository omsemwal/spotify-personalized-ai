# The APIs, in plain words

Why this file exists: the other docs explain *how* each API works, in
detail. This one explains *what* each API is for, in one page, with no
jargon.

Three of the ten are built.

---

## The big picture

Spotify's chat and player already exist. This system sits behind them and
gives them a memory.

```
   Listener talks to Spotify
            │
            ▼
   ┌─────────────────────────────────┐
   │  1. Write it down       ✅ built │
   │  2. Decide what matters ✅ built │
   │  3. Save it             ✅ built │
   │  4. Find it again       (next)  │
   │  5. Use it in a reply   (later) │
   └─────────────────────────────────┘
```

Memories are now saved and survive. What is missing is using them: nothing
finds a memory when someone asks a question, and nothing hands it to the
AI.

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
and hands the answer back.

That is API 3.

---

## API 3 — `POST /v1/memories`

### What it does

**Saves the memory, so it is still there tomorrow.**

APIs 1 and 2 work things out and then forget them. This one writes the
memory down properly.

### Where it goes

Into Neo4j, a database built for things that are connected. A memory is
stored joined to what it is about:

```
    "Prefers instrumental music while working"
                  │
          ┌───────┴───────┐
          ▼               ▼
   instrumental        working
```

### The clever part: changing your mind

The listener says *"I love country"* on Monday, and *"no more country"* on
Friday. Those cannot both be true.

The system **notices this by itself** - nobody tells it - and retires the
Monday memory:

```
"Loves country music"        finished on Friday   (kept)
"Does not want country"      the live one
```

**The old memory is not deleted.** It is marked finished and kept. So you
can always answer "why did it think I liked country?"

That matters more than it sounds. A system that quietly overwrites what it
believed cannot explain itself, and nobody can check it.

### Saying something twice

```
Monday : "I like jazz"
Friday : "I like jazz"
```

This does **not** make two memories. It makes **one memory we are now more
sure of** - because saying a thing twice is stronger evidence than saying
it once.

### Forgetting old things

Every memory is saved with a use-by date, set by its kind:

| Kind | Kept |
|---|---|
| Exclusion | 730 days |
| Correction | 730 days |
| Explicit preference | 365 days |
| Candidate preference | 90 days |
| Episode | 30 days |

Once the date passes, the memory is marked finished. Again - marked, not
deleted.

### Searching by meaning

When a memory is saved, its sentence is also turned into **384 numbers**.
Sentences that mean similar things get similar numbers.

That lets us find a memory **without sharing any words with it**:

```
you search : "music with no vocals"
it finds   : "Prefers instrumental music while working"
```

Not one word in common. Ordinary word-matching would find nothing.

It works across languages too - searching in Spanish finds a memory
written in English.

### Things the caller does not get to decide

The app sending the memory cannot choose the memory's id, its entity ids,
how long it is kept, or its numbers. We work all of those out ourselves,
so an app cannot smuggle in something it should not.

And a sensitive fact - "feels depressed" - is refused here too, the same
as in API 2. There is no back door.

### What it does not do

**It does not find memories for you.** It stores them and makes them
findable. Actually finding the right ones for a question is API 4.

---

## What this means today

If a listener says *"no country music"* right now:

- API 1 writes down that they said it ✅
- API 2 works out it is an exclusion ✅
- API 3 saves it, and retires anything it contradicts ✅
- Nothing looks it up when they next ask for music ❌
- So the reply still ignores it ❌

**The loop is nearly closed.** Two more APIs finish it:

| | |
|---|---|
| API 4 | Find the right memories when they ask something |
| API 5 | Hand them to the AI so the reply actually uses them |

---

## Where to read more

| Doc | What is in it |
|---|---|
| `events.doc.md` | API 1 in detail |
| `memories-extract.doc.md` | API 2 in detail |
| `memories.doc.md` | API 3 in detail |
| `HOW_IT_WORKS.md` | API 1 line by line, with the code |
| `REQUIREMENTS.md` | What the project has to deliver |
