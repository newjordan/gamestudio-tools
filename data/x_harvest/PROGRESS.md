# x_harvest PROGRESS (final checkpoint 2026-11-25)
- [x] bookmarks: folders=0 (get_users_bookmark_folders returned empty body), bookmarks=99 (one page, no next_token) -> bookmarks_raw.json
- [x] public search: 13 queries + 3 thread/author lookups via x.search_posts_all; 124 unique search posts -> search_posts.json; all_posts.json = 223 (bookmarks+search)
- [x] t.co resolved (tco_cache.json); licences checked on the live pages / LICENSE files
- [x] downloads: 15 items in assets/ (itch via the public download flow, GitHub via shallow clone, .git removed)
- [x] manifest.csv / manifest.jsonl / candidates_skipped.csv / candidates_skipped.json / SLOTTING_NOTES.md
- Resume: scripts consolidate.py, resolve.py, itch_dl.py, build_manifest.py, build_skipped.py
- Not done: Quaternius/KayKit/OpenGameArt/Poly Haven/ambientCG direct packs (not evaluated); Kenney held (noai signal)

## Round 2 (2026-11-25 ~4pm-)
- Jordan lifted noai/tdm/robots skip; Kenney fetched (76 packs + pattern-pack-2 via itch), tge-assets cloned; Apache/GPL code and CC-BY-SA assets allowed; cap 2.5 GB, keep >=1.5 GB free.
- Round-2 X queries: 18 more (r2_posts.json, r2b_posts.json), all_posts.json now 424 posts.
- Downloaded: Quaternius (itch, CC0 kits), KayKit free tiers, Poly Haven (API sample), ambientCG (API sample), Vuena CC0 GLB, OGA (CC0, slow 10 s delay, oga_dl.py may still be running), misc itch/GitHub.
- Manifest rebuilt by build_manifest_r2.py (rows tagged round=2). Re-run after OGA finishes.
- Round 2 DONE: 167 manifest rows (total manifest 182), 2326 MB. OGA finished (2d/3d/texture/music/sfx, 24 each). Added Apache/GPL repos (awesome-gamedev-agent-skills, autopilot, Assets2Godot) previously skipped. NVlabs/motionbricks attempted but aborted/removed (729 MB, ran out of space mid-clone).
- 

## Round 3
- Loktar = Jason Brown, X @loktar00 (id 1598199015375601665; profile links github.com/loktar00), GitHub loktar00 (twitter_username field = loktar00). Inventory in loktar00_repo_inventory.csv (126 repos).
- Repos: 13 with a licence -> assets/github_loktar/; 19 without a licence -> reference/loktar00/ (flagged in manifest notes). X posts read: 24 recent + 16 search (r3/loktar_posts.json, loktar_search.json).
- Also: Quaternius nature pack + fantasy-props megakit; itch CC0 listing (22 packs, per-file cap 25 MB); OGA 6 more.
- Round 3 total 62 rows, ~665 MB; free space 1554 MB (floor 1500). Further X queries returned only already-seen posts.
- Nothing written to turbo/other machines.

## Round 4
- Jordan linked https://x.com/xqliu/status/2125409558973813099 (pt224u). Read-only. The post (Larry @xqliu, 2026-11-24 8:01 PM America/Chicago) shares kociden/sakurai-skill, an unofficial Japanese Claude Code Agent Skill distilled from all 257 episodes of Masahiro Sakurai's YouTube series 桜井政博のゲーム作るには. Follow-up https://x.com/xqliu/status/2125409563344286035 has the repo link.
- Brought in (all under reference/, no licence files): the 34-post thread, kociden/sakurai-skill (1.3 MB, sha 913dc46b), and the earlier related repo named in that README, kokuren333/Sakurai-Skills (3.4 MB). Hajiki example source is not in the repo (unityroom playable; screenshots + notes only). Manifest source=jordan_link, round=4. Disk still ~1.6 GB free.
