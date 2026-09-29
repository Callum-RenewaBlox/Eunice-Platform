# RenewaBlox brand assets (Atlas v2 client skin)

Web copies of the official logos. The sources are in the RenewaBlox Google Drive, under
*Brand, Logos and Guidelines / LOGOS*.

| File | Source | Use |
| --- | --- | --- |
| `wordmark-light.png` | `2.png` (RENEWA teal, BLOX. black) | header on the light theme, PNG export band |
| `wordmark-dark.png` | `4.png` (RENEWA teal, BLOX. white) | header on the dark theme |
| `wordmark-mono.png` | `3.png` (RENEWA white, BLOX. black) | on brand-teal panels |
| `roundel-64.png`, `roundel-192.png` | `BLOXLogo.jpg`, set as a white BLOX. on a teal disc (the pitch deck's roundel) | favicon, Streamlit page icon |

Each wordmark was trimmed to its ink and resized to 72 px tall (3× the 24 px display size). It was then saved
as a palette PNG with alpha, at about 5 KB each. `atlas/build.py` inlines these files as data URIs, so the
built page stays self-contained.

## Brand tokens

These come from the January 2026 pitch deck and the business cards.

| Token | Hex | Where the brand uses it |
| --- | --- | --- |
| Blox teal | `#156082` | "RENEWA", headline bands, tagline on the cards |
| Deep navy | `#0B3549` | headings |
| Sea teal | `#218099` | sub-headings |
| Sky | `#83CBEB` | accent circles |
| Mist | `#E7F1F7` / `#E9EDF4` | panel tints |
| Greys | `#7F7F7F` / `#595959` / `#404040` | tagline, body text |

The brand typeface is **Leelawadee UI**, a Windows system font with Regular, Semilight and Bold weights. It
cannot be served as a web font. The skin therefore asks for Leelawadee UI first, which renders on Windows.
Everywhere else it falls back to **Open Sans** from Google Fonts. Open Sans is the open-licence humanist sans
closest to Leelawadee UI, whose Latin letters come from Segoe UI.

The brand tagline is "no Watt wasted".
