# Export assets

What the Word and PDF files Klar exports are drawn with (P9). Copied, never redrawn.

## Logo

- `klar-lockup-flat.svg`: the *klar-lockup-flat* logo from the Klar design system's Logos group
  (claude.ai artifact D3qnmjeUHcxJGb59eFJhz4, asset `4a1356763aa90af8979485ea61f286f7`, sha256
  `6112b65f…24a3`), the lockup the design system names for print, Word and PDF.
- `klar-lockup-flat.png`: the same file rasterised for Word, which can't show SVG: macOS Quick Look
  (`qlmanage -t -s 2000`) on a copy whose viewBox was made square, cropped back to the lockup's
  3452.9 × 1182 proportions (2000 × 685 px, white ground).

## Fonts

The design system's voices for paper: Newsreader (the Act's voice and drafted documents) and Geist
(the product's). Both are under the SIL Open Font License 1.1 (`OFL-*.txt`); neither declares a
Reserved Font Name.

| File | From | Axes |
| --- | --- | --- |
| `Newsreader-Regular.ttf` | google/fonts `ofl/newsreader/Newsreader[opsz,wght].ttf` (sha256 `8a08d13f…d7c1`) | wght 400, opsz 16 |
| `Newsreader-Medium.ttf` | the same | wght 500, opsz 24 |
| `Geist-Regular.ttf` | google/fonts `ofl/geist/Geist[wght].ttf` (sha256 `73894e04…9659`) | wght 400 |
| `Geist-SemiBold.ttf` | the same | wght 600 |

Each is a static instance of the variable font, made with fontTools
(`fontTools.varLib.instancer.instantiateVariableFont(font, axes, updateFontNames=False)`): a
variable font would be instanced again on every export, which takes about a second.
