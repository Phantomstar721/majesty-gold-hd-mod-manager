# Majesty Mod Manager icon

`manager-icon-source.png` is the project-owned source image for the manager's
Windows identity. It was generated with OpenAI's built-in image generation tool
for this project, then mechanically resized into the runtime PNG and
multi-resolution ICO by `scripts/build_manager_icon.py`.

The selected concept is **Royal Scribe**. It replaces the earlier shield-and-
gear draft so the manager reads as a distinct Majesty-era utility rather than
another copy of the game icon.

Final generation prompt:

> Use case: logo-brand
> Asset type: Windows desktop application icon for "Majesty Mod Manager"
> Primary request: Create an original Royal Scribe emblem: a bold golden quill
> crossing an unfurled parchment, with three simple burgundy wax seals aligned
> on the parchment to suggest organizing several mods.
> Style/medium: painted like a late-1990s fantasy strategy-game interface
> asset, designed to remain legible at 16x16 and 32x32 pixels.
> Composition/framing: single centered square icon with a strong silhouette
> and a genuinely transparent background.
> Color palette: aged parchment, antique gold, deep burgundy, and a dark-brown
> outline.
> Constraints: no text, letters, shield, gear, crown, scenery, existing game
> or company logo, or watermark; visually distinct from the Majesty game icon.

Rebuild the derived files with:

```powershell
.\.venv\Scripts\python.exe .\scripts\build_manager_icon.py
```

## Steam Workshop preview

`workshop/workshop-preview-source.png` is the full-resolution project-owned
source for the Steam cover. `workshop/workshop-preview.jpg` is its mechanically
converted upload copy, kept below Steam's preview-image size limit. The source
image was generated for this project with OpenAI's built-in image generation
tool.

Final generation prompt:

> Use case: ads-marketing
> Asset type: square Steam Workshop preview image for a Windows game utility
> Primary request: Create an original cover image for a fan-made tool titled
> exactly "MAJESTY MOD MANAGER". Show a dignified royal scribe at a candlelit
> medieval strategy-table, using a golden quill to organize three distinct
> parchment scrolls with burgundy wax seals into one finished royal document.
> The visual idea is choosing, organizing, and safely combining game mods.
> Scene/backdrop: warm stone study with dark carved wood, subtle maps and
> shelves, kept simple enough for a small thumbnail.
> Subject: the Royal Scribe and the converging scrolls are the clear focal
> point.
> Style/medium: polished hand-painted late-1990s fantasy strategy-game
> interface illustration; original artwork, not a copy of any existing game
> art.
> Composition/framing: square cover, bold dark-wood and antique-gold frame,
> large central silhouette, exact title across the upper portion, legible at
> thumbnail size.
> Lighting/mood: warm candlelight, regal, welcoming, practical rather than
> ominous.
> Color palette: aged parchment, antique gold, deep burgundy, dark walnut, and
> restrained midnight-blue accents.
> Text: "MAJESTY MOD MANAGER"
> Constraints: title exactly once; no subtitle, extra words, logos, UI
> screenshots, shields, gears, crowns, weapons, or watermark.
