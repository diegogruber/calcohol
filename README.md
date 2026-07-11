# Calcohol

A lightweight web-based drink calculator built with [FastHTML](https://docs.fastht.ml/) and Python. Calculate totals for drinks sold at a stand, including prices and pfand (deposit) returns per device.

## Features

- Per-device drink quantity inputs with real-time totals
- Pfand (deposit) return tracking
- Session-based state (each device gets its own session)
- Admin panel to manage drinks and prices via YAML
- PIN-protected admin access (default PIN: `1234`)
- Responsive single-page UI with card flip animation
- Docker support

## Setup

### Prerequisites

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation

```bash
uv sync
```

Or with pip:

```bash
pip install python-fasthtml pyyaml
```

## Usage

```bash
uv run main.py
```

The app will be available at `http://localhost:8080`.

Set the port via environment variable:

```bash
PORT=8081 uv run main.py
```

## Configuration

Drinks are configured in `drinks.yml`:

```yaml
pfand_default: 2.00
drinks:
  - name: "🍻 Bier/Radler"
    price: 4.00
    pfand: 2.00
  - name: "🥤 Mineral / Limo"
    price: 3.00
    pfand: false
```

Fields:
- `pfand_default`: Global default deposit amount
- `drinks`: List of drinks, each with `name`, `price`, and optional `pfand` (overrides global default; use `false` for no deposit)

## Usage

- **➖ / ➕**: Adjust drink counts
- **♻️ Pfand Rückgabe**: Record bottle/can returns to subtract from the total
- **🔁 Reset**: Clear all counts and pfand returns for the current device
- **🔑 Admin**: Open the admin panel (requires PIN)

## Admin Panel

Accessible via the Admin button on the calculator card. Allows editing the `drinks.yml` content directly in the browser. Changes are applied immediately and take effect globally.

## Docker

```bash
docker build -t calcohol .
docker run -p 8000:8000 calcohol
```

## Tech Stack

- [FastHTML](https://docs.fastht.ml/) — web framework
- [PyYAML](https://pyyaml.org/) — drink configuration
- [uv](https://docs.astral.sh/uv/) — dependency management
- Ruff — linting
