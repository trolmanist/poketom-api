# Poketom API

Poketom API is a free, self-hosted Pokemon TCG JSON API that ships as static files and runs entirely on GitHub Pages.

There is no backend, no database, and no paid API dependency. The repository fetches open Pokemon TCG data, transforms it into a lightweight schema, and publishes versioned JSON files from the [`docs/`](/Users/tom/dev/poketom-api/docs) folder.

## Data Sources

- [PokemonTCG/pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data) is the current canonical source for generated card and set JSON.
- [tcgdex/cards-database](https://github.com/tcgdex/cards-database) is an additional open dataset worth tracking for future enrichment or fallback coverage.

## API Shape

Once GitHub Pages is enabled, the API is available at:

- `https://USERNAME.github.io/poketom-api/index.json`
- `https://USERNAME.github.io/poketom-api/cards/base1-4.json`
- `https://USERNAME.github.io/poketom-api/sets/index.json`
- `https://USERNAME.github.io/poketom-api/sets/base1.json`

### `index.json`

Top-level card index for search and browsing. Each item is a lightweight card record:

```json
{
  "id": "base1-4",
  "name": "Charizard",
  "set": "Base",
  "setId": "base1",
  "number": "4",
  "rarity": "Rare Holo",
  "types": ["Fire"],
  "hp": "120",
  "artist": "Mitsuhiro Arita",
  "imageSmall": "https://images.pokemontcg.io/base1/4.png",
  "imageLarge": "https://images.pokemontcg.io/base1/4_hires.png"
}
```

### `cards/{id}.json`

Individual card endpoint. Card files use the same lightweight schema as `index.json`, so fetching a single card is cheap and consistent.

### `sets/index.json`

Lightweight set directory. Each set record contains:

- `id`
- `name`
- `series`
- `printedTotal`
- `total`
- `cardCount`
- `releaseDate`
- `updatedAt`
- `symbolImage`
- `logoImage`

### `sets/{setId}.json`

Full set endpoint with set metadata plus a `cards` array containing lightweight card records for that set.

## Repository Structure

```text
poketom-api/
├── .github/
│   └── workflows/
│       ├── deploy-pages.yml
│       └── refresh-data.yml
├── docs/
│   ├── .nojekyll
│   ├── index.json
│   ├── meta.json
│   ├── cards/
│   │   └── *.json
│   └── sets/
│       ├── index.json
│       └── *.json
├── scripts/
│   └── generate_api.py
└── README.md
```

## How Generation Works

[`scripts/generate_api.py`](/Users/tom/dev/poketom-api/scripts/generate_api.py) does four things:

1. Fetches the latest set index from the upstream `pokemon-tcg-data` repository.
2. Downloads each set's English card JSON.
3. Transforms the data into a simplified, static API schema.
4. Writes the generated files into [`docs/`](/Users/tom/dev/poketom-api/docs).

Run it locally with:

```bash
python3 scripts/generate_api.py
```

The script uses only Python's standard library, so no dependency install is required.

## GitHub Actions

### Weekly Refresh

[`refresh-data.yml`](/Users/tom/dev/poketom-api/.github/workflows/refresh-data.yml) runs every Monday at `02:00 UTC` and can also be triggered manually. It:

- regenerates `docs/`
- commits changes if the upstream data changed
- pushes the refreshed JSON back to `main`

### GitHub Pages Deploy

[`deploy-pages.yml`](/Users/tom/dev/poketom-api/.github/workflows/deploy-pages.yml) deploys the contents of [`docs/`](/Users/tom/dev/poketom-api/docs) to GitHub Pages on every push to `main`.

## Deploy On GitHub

1. Create a GitHub repository named `poketom-api`.
2. Push this project to the `main` branch.
3. In GitHub, open `Settings` -> `Pages`.
4. Set the Pages source to `GitHub Actions`.
5. Push a commit or run the `Deploy GitHub Pages` workflow once.

After that, your JSON API will be live at:

`https://YOUR_USERNAME.github.io/poketom-api/`

## Notes

- The generated JSON is committed to the repository so web apps and AI artefacts can fetch it directly.
- Because the API is static, it works well with GitHub Pages caching and CDN delivery.
- `meta.json` provides a tiny summary of the last generated snapshot.
