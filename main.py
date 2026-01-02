from fasthtml.common import *
from typing import List, Dict, Any
import yaml
import os

app, rt = fast_app(debug=True)

# --- Global (shared) state: drinks/prices are global and loaded from YAML ---
class Drink:
    def __init__(self, name: str, price: float, pfand: float = 0.0):
        self.name = name
        self.price = price
        self.pfand = pfand

with open("drinks.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

pfand_default: float = float(
    config.get("pfand_default", config.get("pfand", 0.0))
)

drinks: List[Drink] = []
for entry in config["drinks"]:
    pf = entry.get("pfand", None)

    # backward compatibility
    if isinstance(pf, bool):
        pf = pfand_default if pf else 0.0
    elif pf is None:
        pf = pfand_default

    drinks.append(
        Drink(
            name=entry["name"],
            price=float(entry["price"]),
            pfand=float(pf),
        )
    )

# --- Session helpers (per-device state) ---
SESSION_KEY = "calc_state"
ADMIN_PIN = "1234"


def default_state() -> Dict[str, Any]:
    return {
        "counts": [0] * len(drinks),
        "pfand_returns": {},  # {0.25: 2, 0.50: 1}
        "flipped": False,
        "is_admin": False,
    }


def get_calc_state(request) -> Dict[str, Any]:
    """
    Read the per-device state from the session. If missing or malformed,
    return a default state. Also keep counts length in sync with drinks.
    """
    state: Dict[str, Any] = request.session.get(SESSION_KEY)

    if not isinstance(state, dict):
        state = default_state()

    # Ensure counts is correct length
    counts: List[int] = state.get("counts", [])
    if len(counts) != len(drinks):
        counts = counts[:len(drinks)] + [0] * max(0, len(drinks) - len(counts))
    state["counts"] = counts

    # Ensure pfand_returns exists and is int
    pfand_returns = state.get("pfand_returns", {})
    if not isinstance(pfand_returns, dict):
        pfand_returns = {}

    # Ensure numeric keys
    state["pfand_returns"] = {
        float(k): int(v)
        for k, v in pfand_returns.items()
        if float(k) > 0
    }

    # Ensure flipped exists and is bool
    flipped: bool = bool(state.get("flipped", False))
    state["flipped"] = flipped

    # Ensure is_admin exists and is bool
    state["is_admin"] = bool(state.get("is_admin", False))

    return state


def save_calc_state(request, state: Dict[str, Any]) -> None:
    """
    Persist the per-device state in the session (Starlette session middleware).
    """
    request.session[SESSION_KEY] = state


# --- Calculation helpers ---
def compute_total_from_state(state: Dict[str, Any]) -> float:
    total = 0.0

    # Add drinks (price + pfand)
    for i, d in enumerate(drinks):
        total += state["counts"][i] * (d.price + d.pfand)

    # Subtract returned pfand (by pfand level)
    for pfand_value, returned in state["pfand_returns"].items():
        total -= returned * pfand_value

    return round(total, 2)


# --- UI builders (stateless: built from drinks + session state) ---
def wrap_card(state: Dict[str, Any]):
    return Div(
        Link(rel="stylesheet", href="/static/style.css"),

        # CARD UI
        Div(
            Div(calc_content(state), cls="card-front"),
            Div(admin_content(), cls="card-back"),
            cls=f"card-inner {'flipped' if state.get('flipped') else ''}",
        ),

        # POPUP HOLDER – dialog loads here
        Div(id="pin-dialog"),

        cls="card-container",
    )


def calc_content(state: Dict[str, Any]):
    counts = state["counts"]

    # --- Total box becomes PIN entry if needed ---
    if state.get("awaiting_pin", False):
        total_box = Div(
            Form(
                Input(type="password", name="pin", placeholder="Admin PIN", cls="pin-input"),
                Button("✔️", type="submit"),
                cls="pin-form",
                hx_post="/enter_pin",
                hx_target="body",
            ),
            Div(state.get("pin_error", ""), cls="pin-error") if state.get("pin_error") else "",
            cls="total-box pin-mode",
        )
    else:
        total_box = Div(
            f"💰 Gesamt: € {compute_total_from_state(state):.2f}",
            cls="total-box"
        )

    return Div(
        total_box,

        *[
            Div(
                Div(
                    Div(d.name, cls="drink-name"),
                    Div(
                        f"€ {d.price:.2f}"
                        + (f" + € {d.pfand:.2f}" if d.pfand > 0 else ""),
                        cls="drink-price",
                    ),
                ),
                Div(
                    Button("➖", hx_post=f"/change/{i}/-1", hx_target="body"),
                    Span(str(counts[i]), cls="count-display"),
                    Button("➕", hx_post=f"/change/{i}/1", hx_target="body"),
                    Span(
                        f"€ {counts[i] * (d.price + (pfand_default if d.pfand else 0)):.2f}",
                        cls="subtotal",
                    ),
                    cls="controls",
                ),
                cls="drink-row",
            )
            for i, d in enumerate(drinks)
        ],

        Hr(),

        pfand_return_section(state),

        Hr(),

        Div(
            Button("🔁 Reset", hx_post="/reset", hx_target="body"),
            Button("🔑 Admin", hx_post="/request_pin", hx_target="body"),
            cls="button-row",
        ),

        cls="container",
    )

def pfand_return_section(state):
    pfand_levels = sorted({d.pfand for d in drinks if d.pfand > 0})

    if not pfand_levels:
        return ""

    return Div(
        H4("♻️ Pfand Rückgabe"),
        *[
            Div(
                Span(f"€ {pfand:.2f}"),
                Div(
                    Button("➖", hx_post=f"/return_pfand/{pfand}/-1", hx_target="body"),
                    Span(
                        str(state["pfand_returns"].get(pfand, 0)),
                        cls="count-display",
                    ),
                    Button("➕", hx_post=f"/return_pfand/{pfand}/1", hx_target="body"),
                    Span(
                        f"€ {state['pfand_returns'].get(pfand, 0) * pfand:.2f}",
                        cls="subtotal",
                    ),
                    cls="controls",
                ),
                cls="drink-row",
            )
            for pfand in pfand_levels
        ],
    )


def admin_content():
    drink_data = {
        "pfand": round(pfand_default, 2),
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

def pin_dialog(error: str | None = None):
    return Dialog(
        Form(
            H3("🔐 Admin PIN"),
            (Div(error, cls="pin-error") if error else ""),
            Input(type="password", name="pin", placeholder="PIN eingeben", cls="pin-input"),
            Div(
                Button("Abbrechen", type="button", hx_get="/close_pin", hx_target="#pin-dialog"),
                Button("OK", type="submit"),
                cls="button-row",
            ),
            hx_post="/check_pin",
            hx_target="#pin-dialog",
        ),
        id="pin-dialog",
        open=True   # THIS makes the dialog show
    )

# --- Routes (use session—per device) ---
@rt("/")
def calculator(request):
    state = get_calc_state(request)
    return wrap_card(state)


@rt("/flip")
def flip(request):
    state = get_calc_state(request)

    # If not in admin mode → require PIN
    if not state.get("flipped", False):
        state["entering_pin"] = True
        save_calc_state(request, state)
        return wrap_card(state)

    # Already admin → flip back
    state["flipped"] = False
    save_calc_state(request, state)
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


@rt("/return_pfand/{pfand}/{delta}", methods=["POST"])
def return_pfand(request, pfand: float, delta: int):
    state = get_calc_state(request)
    pfand = float(pfand)
    delta = int(delta)

    current = state["pfand_returns"].get(pfand, 0)
    state["pfand_returns"][pfand] = max(0, current + delta)

    save_calc_state(request, state)
    return wrap_card(state)


@rt("/upload", methods=["POST"])
def upload_drinks(request, yaml_text: str):
    """
    Admin uploads new YAML. This updates global drinks/prices.
    Note: existing sessions keep their counts — you may want to reset sessions separately.
    """
    global drinks, pfand_default
    try:
        data = yaml.safe_load(yaml_text)
        pfand_default = float(data.get("pfand"))
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

@rt("/request_pin", methods=["POST"])
def request_pin(request):
    state = get_calc_state(request)
    state["awaiting_pin"] = True
    state["pin_error"] = ""
    save_calc_state(request, state)
    return wrap_card(state)

@rt("/enter_pin", methods=["POST"])
def enter_pin(request, pin: str):
    state = get_calc_state(request)
    if pin == ADMIN_PIN:
        state["awaiting_pin"] = False
        state["pin_error"] = ""
        state["flipped"] = True
    else:
        state["pin_error"] = "❌ Falscher PIN"
    save_calc_state(request, state)
    return wrap_card(state)


# --- Run App ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    serve(host="0.0.0.0", port=port)