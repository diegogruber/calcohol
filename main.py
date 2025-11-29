from fasthtml.common import *
from typing import List
import yaml

app, rt = fast_app(debug=True)

# --- State ---
pfand_returns = 0


class Drink:
    def __init__(self, name: str, price: float, pfand: bool):
        self.name = name
        self.price = price
        self.pfand = pfand
        self.count = 0


# Load drinks from YAML
with open("drinks.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

pfand_value: float = config["pfand"]
drinks: List[Drink] = [Drink(**entry) for entry in config["drinks"]]

# Track flip state
flip_state = {"flipped": False}


# --- Helpers ---
def total():
    base = sum(d.count * (d.price + (pfand_value if d.pfand else 0)) for d in drinks)
    return round(base - (pfand_returns * pfand_value), 2)


# --- UI ---
def wrap_card():
    return Div(
        Link(rel="stylesheet", href="/static/style.css"),
        Div(
            Div(calc_content(), cls="card-front"),
            Div(admin_content(), cls="card-back"),
            cls=f"card-inner {'flipped' if flip_state['flipped'] else ''}",
        ),
        cls="card-container",
    )


def calc_content():
    return Div(
        Div(f"💰 Gesamt: € {total():.2f}", cls="total-box"),
        *[
            Div(
                Span(f"{d.name} (€ {d.price:.2f}{' + Pfand' if d.pfand else ''})"),
                Div(
                    Button("➖", hx_post=f"/change/{i}/-1", hx_target="body"),
                    Span(str(d.count), cls="count-display"),
                    Button("➕", hx_post=f"/change/{i}/1", hx_target="body"),
                    Span(
                        f"€ {d.count * (d.price + (pfand_value if d.pfand else 0)):.2f}",
                        cls="subtotal",
                    ),
                    cls="controls",
                ),
                cls="drink-row",
            )
            for i, d in enumerate(drinks)
        ],
        Hr(),
        Div(
            Span("♻️ Pfand Rückgabe:"),
            Div(
                Button("➖", hx_post="/return_pfand/-1", hx_target="body"),
                Span(f"{pfand_returns}", cls="count-display"),
                Button("➕", hx_post="/return_pfand/1", hx_target="body"),
                Span(
                    f"€ {pfand_returns * pfand_value:.2f}",
                    cls="subtotal",
                ),
                cls="controls",
            ),
            cls="drink-row",
        ),
        Hr(),
        Div(
            Button("🔁 Zurücksetzen", hx_post="/reset", hx_target="body"),
            Button("🔄 Verwaltung", hx_get="/flip", hx_target="body"),
            cls="button-row",
        ),
        cls="container",
    )


def admin_content():
    drink_data = {
        "pfand": round(pfand_value, 2),
        "drinks": [
            {"name": d.name, "price": d.price, "pfand": d.pfand} for d in drinks
        ],
    }
    return Div(
        H2("Verwaltung"),
        Form(
            Textarea(
                yaml.dump(drink_data, allow_unicode=True),
                name="yaml_text",
                rows="15",
                cols="40",
            ),
            Div(
                Button("✅ Speichern", type="submit"),
                Button("↩️ Zurück", type="button", hx_get="/flip", hx_target="body"),
                cls="button-row",
            ),
            cls="admin-view",
            hx_post="/upload",
            hx_target="body",
        ),
    )


# --- Routes ---
@rt("/")
def calculator():
    return wrap_card()


@rt("/flip")
def flip():
    flip_state["flipped"] = not flip_state["flipped"]
    return wrap_card()


@rt("/change/{idx}/{delta}")
def change(idx: int, delta: int):
    drinks[idx].count = max(0, drinks[idx].count + delta)
    return wrap_card()


@rt("/return_pfand/{delta}", methods=["POST"])
def return_pfand(delta: int):
    global pfand_returns
    pfand_returns = max(0, pfand_returns + delta)
    return wrap_card()


@rt("/upload", methods=["POST"])
def upload_drinks(yaml_text: str):
    global drinks, pfand_value
    try:
        data = yaml.safe_load(yaml_text)
        pfand_value = float(data.get("pfand"))
        drinks = [
            Drink(d["name"], float(d["price"]), bool(d.get("pfand", False)))
            for d in data.get("drinks", [])
        ]
        pfand_returns = 0
        for d in drinks:
            d.count = 0
    except Exception as e:
        return Div("❌ Fehler beim Laden der YAML-Daten!", str(e))
    return wrap_card()


@rt("/reset", methods=["POST"])
def reset():
    global pfand_returns
    pfand_returns = 0
    for d in drinks:
        d.count = 0
    return wrap_card()


# --- Run App ---
serve()
