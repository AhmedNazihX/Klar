<!-- Copied from the Klar design system, https://claude.ai/artifact/D3qnmjeUHcxJGb59eFJhz4 (version 1790858064-dcaa, 2026-10-01). The artifact is the source: when it changes, re-copy this file. -->

# Localisation

Klar works in English and German. These rules come from testing the result screen in German; follow them on every screen.

- **Plan for German about 30% longer than English**, and check every screen in German before handoff.
- **Button rows never shrink** (`flex-shrink: 0`). When a header runs out of room, the subtitle under the title wraps instead of the buttons squeezing or overlapping.
- **Citation columns are sized for German.** To-do citations need at least 112 px (*Art. 26 Abs. 11*); step lists need 220 px for step names (*2 Verbotene Praktiken*) and 280 px for citations (*Anhang III Nr. 4 Buchst. a, Art. 6 Abs. 3*). A citation never truncates or breaks mid-reference.
- **Sidebar labels must fit 220 px at 15 px.** Pick short German labels (*Fragen stellen*, not *Fragen zur KI-Verordnung*). Secondary link rows wrap onto a second line.
- **Use the Act's official German terms**: KI-Verordnung, Betreiber (deployer), Anbieter (provider), Betriebsanleitung (instructions for use), menschliche Aufsicht (human oversight), Arbeitnehmervertretung (workers' representatives). Address the reader as *Sie*; say *Bewerbende* for applicants.
- **German citation style**: *Art. 26 Abs. 1*, *Anhang III Nr. 4 Buchst. a*. **German dates**: *2. Dezember 2027*, *27.07.2026*.
- **Quoted provisions come word for word from the official German text on EUR-Lex.** The model never translates legal text itself.
- Notices in German: *Orientierungshilfe, keine Rechtsberatung.* and *Sie nutzen ein KI-System.*
