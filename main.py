from fasthtml.common import *
from typing import List, Dict, Any
import yaml
import os

app, rt = fast_app(debug=True)

# --- Global (shared) state: drinks/prices are global and loaded from YAML ---
class Drink:
    def __init__(self, name: str, price: float, pfand: bool):
        self.name = name
        self.price = price
        self.pfand = pfand

with open("drinks.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

pfand_value: float = config["pfand"]
drinks: List[Drink] = [Drink(**entry) for entry in config["drinks"]]

# TODO: UI flip is global, move into session
flip_state = {"flipped": False}

# --- Session helpers (per-device state) ---
SESSION_KEY = "calc_state"


def default_state() -> Dict[str, Any]:
    return {"counts": [0] * len(drinks), "pfand_returns": 0}


def get_calc_state(request) -> Dict[str, Any]:
    """
    Read the per-device state from the session. If missing or malformed,
    return a default state. Also keep counts length in sync with drinks.
    """
    s = request.session.get(SESSION_KEY)
    if not isinstance(s, dict):
        s = default_state()
    # Ensure counts length matches drinks
    counts = s.get("counts", [])
    if len(counts) != len(drinks):
        counts = counts[: len(drinks)] + [0] * max(0, len(drinks) - len(counts))
    s["counts"] = counts
    # Ensure pfand_returns exists and is int
    s["pfand_returns"] = int(s.get("pfand_returns", 0))
    return s


def save_calc_state(request, state: Dict[str, Any]) -> None:
    """
    Persist the per-device state in the session (Starlette session middleware).
    """
    request.session[SESSION_KEY] = state


# --- Calculation helpers ---
def compute_total_from_state(state: Dict[str, Any]) -> float:
    counts = state["counts"]
    base = 0.0
    for i, d in enumerate(drinks):
        cnt = counts[i] if i < len(counts) else 0
        base += cnt * (d.price + (pfand_value if d.pfand else 0))
    total = round(base - (state["pfand_returns"] * pfand_value), 2)
    return total


# --- UI builders (stateless: built from drinks + session state) ---
def wrap_card(state: Dict[str, Any]):
    return Div(
        Link(rel="stylesheet", href="/static/style.css"),
        Div(
            Div(calc_content(state), cls="card-front"),
            Div(admin_content(), cls="card-back"),
            cls=f"card-inner {'flipped' if flip_state['flipped'] else ''}",
        ),
        cls="card-container",
    )


def calc_content(state: Dict[str, Any]):
    counts = state["counts"]
    return Div(
        Div(f"💰 Gesamt: € {compute_total_from_state(state):.2f}", cls="total-box"),
        *[
            Div(
                Span(f"{d.name} (€ {d.price:.2f}{' + Pfand' if d.pfand else ''})"),
                Div(
                    Button("➖", hx_post=f"/change/{i}/-1", hx_target="body"),
                    Span(str(counts[i]), cls="count-display"),
                    Button("➕", hx_post=f"/change/{i}/1", hx_target="body"),
                    Span(
                        f"€ {counts[i] * (d.price + (pfand_value if d.pfand else 0)):.2f}",
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
                Span(f"{state['pfand_returns']}", cls="count-display"),
                Button("➕", hx_post="/return_pfand/1", hx_target="body"),
                Span(f"€ {state['pfand_returns'] * pfand_value:.2f}", cls="subtotal"),
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
        "drinks": [{"name": d.name, "price": d.price, "pfand": d.pfand} for d in drinks],
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


# --- Routes (use session—per device) ---
@rt("/")
def calculator(request):
    state = get_calc_state(request)
    return wrap_card(state)


@rt("/flip")
def flip(request):
    flip_state["flipped"] = not flip_state["flipped"]
    state = get_calc_state(request)
    return wrap_card(state)


@rt("/change/{idx}/{delta}")
def change(request, idx: int, delta: int):
    state = get_calc_state(request)
    idx = int(idx)
    delta = int(delta)
    if 0 <= idx < len(state["counts"]):
        state["counts"][idx] = max(0, state["counts"][idx] + delta)
    save_calc_state(request, state)
    return wrap_card(state)


@rt("/return_pfand/{delta}", methods=["POST"])
def return_pfand(request, delta: int):
    state = get_calc_state(request)
    delta = int(delta)
    state["pfand_returns"] = max(0, state["pfand_returns"] + delta)
    save_calc_state(request, state)
    return wrap_card(state)


@rt("/upload", methods=["POST"])
def upload_drinks(request, yaml_text: str):
    """
    Admin uploads new YAML. This updates global drinks/prices.
    Note: existing sessions keep their counts — you may want to reset sessions separately.
    """
    global drinks, pfand_value
    try:
        data = yaml.safe_load(yaml_text)
        pfand_value = float(data.get("pfand"))
        drinks = [
            Drink(d["name"], float(d["price"]), bool(d.get("pfand", False)))
            for d in data.get("drinks", [])
        ]
        # Optionally: reset flip_state or other global flags
    except Exception as e:
        return Div("❌ Fehler beim Laden der YAML-Daten!", str(e))
    # After changing drinks structure, we should ensure sessions have correct sized counts.
    # We return the admin view; session adjustment will be done on next request via get_calc_state().
    state = get_calc_state(request)
    return wrap_card(state)


@rt("/reset", methods=["POST"])
def reset(request):
    state = default_state()
    save_calc_state(request, state)
    return wrap_card(state)


# --- Run App ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    serve(host="0.0.0.0", port=port)