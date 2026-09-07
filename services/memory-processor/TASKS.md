# 👤 Member 2 — Memory Processor

**Folder**: `services/memory-processor/`  
**Assigned To**: Member 2 (Processing Worker Developer)

---

## 🎯 What is this service for? (Simple Words)
This worker listens to Kafka events, figures out **what the user meant** (e.g. "I love rock music" -> preference), extracts the fact, finds the artist/song ID, and gives it a confidence score before saving it.

---

## 📝 Simple Steps to Complete
1. **Kafka Listener**: Build a worker that reads events from Kafka topic `interaction-events`.
2. **Classify Memory**: Figure out if the event is a `preference`, `correction`, `dislike`, or just chat.
3. **Entity Resolution**: Convert names like "Taylor Swift" into Spotify artist IDs (`spotify:artist:06HL4z0CvFAxyW27GXpf02`).
4. **Confidence Score**: Give high score (0.9) to direct statements ("I like X") and medium score (0.6) to implicit actions.
5. **Safety Check**: Flag sensitive items (emotions/health) so they are not saved automatically.
6. **Pass to Graph**: Call Member 3's `write_memory()` function to save approved memories in Neo4j.

---

## 🧪 How to Test
1. Send a mock event into Kafka.
2. Check logs to see if it correctly extracts the memory fact and entity ID!
