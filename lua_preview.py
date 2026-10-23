"""Static Roblox/Luau UI preview. Parses declarations; never executes Lua."""
from dataclasses import dataclass, field
import math
import re
import tkinter as tk
import customtkinter as ctk

EXAMPLE_SOURCE = '''local gui = Instance.new("ScreenGui")
local window = Instance.new("Frame", gui)
window.Size = UDim2.fromOffset(440, 300)
window.Position = UDim2.fromScale(0.5, 0.5)
window.AnchorPoint = Vector2.new(0.5, 0.5)
window.BackgroundColor3 = Color3.fromRGB(24, 20, 38)

local title = Instance.new("TextLabel", window)
title.Position = UDim2.fromOffset(24, 22)
title.Size = UDim2.new(1, -48, 0, 40)
title.BackgroundTransparency = 1
title.Text = "Solos Hub"
title.TextSize = 28
title.TextColor3 = Color3.fromRGB(192, 151, 255)
title.TextXAlignment = Enum.TextXAlignment.Left

local subtitle = Instance.new("TextLabel", window)
subtitle.Position = UDim2.fromOffset(24, 76)
subtitle.Size = UDim2.new(1, -48, 0, 54)
subtitle.BackgroundTransparency = 1
subtitle.Text = "Edit this code to change the preview."
subtitle.TextSize = 16
subtitle.TextColor3 = Color3.fromRGB(210, 215, 235)

local button = Instance.new("TextButton", window)
button.Position = UDim2.fromOffset(24, 190)
button.Size = UDim2.new(1, -48, 0, 48)
button.BackgroundColor3 = Color3.fromRGB(155, 115, 245)
button.TextColor3 = Color3.fromRGB(255, 255, 255)
button.TextSize = 18
button.Text = "Get started"
'''

@dataclass(eq=False)
class Element:
    kind: str
    line: int
    props: dict = field(default_factory=dict)
    parent: object = None

@dataclass
class PreviewPlan:
    elements: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    error: str = ""

UNKNOWN = object()
GUI_CLASSES = {"ScreenGui", "Frame", "ScrollingFrame", "TextLabel", "TextButton", "TextBox",
               "ImageLabel", "ImageButton", "UICorner", "UIStroke", "UIListLayout", "UIPadding"}
HUB_CONTROLS = {"Section", "Toggle", "Slider", "Button", "Dropdown", "Input", "InfoRow", "Keybind", "Collapse"}


class Builder:
    def __init__(self, source):
        self.raw = source.encode("utf-8")
        self.env = {}
        self.plan = PreviewPlan()
        self.steps = 0

    def text(self, node):
        return self.raw[node.start_byte:node.end_byte].decode("utf-8")

    def note(self, text):
        if text not in self.plan.notes and len(self.plan.notes) < 12:
            self.plan.notes.append(text)

    def element(self, kind, node, props=None, parent=None):
        if len(self.plan.elements) >= 1000:
            self.note("Preview limited to 1,000 UI elements.")
            return UNKNOWN
        item = Element(kind, node.start_point.row + 1, props or {}, parent if isinstance(parent, Element) else None)
        self.plan.elements.append(item)
        return item

    def value(self, node):
        self.steps += 1
        if node is None or self.steps > 100000:
            return UNKNOWN
        kind, children = node.type, node.named_children
        if kind == "string":
            text = self.text(node)
            if text.startswith("["):
                match = re.match(r"\[(=*)\[(.*)\]\1\]$", text, re.S)
                return match.group(2) if match else UNKNOWN
            # Decode common Lua escapes without running an expression.
            return re.sub(r'\\([nrt\\\'\"])', lambda m: {"n": "\n", "r": "\r", "t": "\t"}.get(m[1], m[1]), text[1:-1])
        if kind == "number":
            try:
                return float(self.text(node))
            except ValueError:
                return UNKNOWN
        if kind in ("true", "false"):
            return kind == "true"
        if kind == "nil":
            return None
        if kind == "identifier":
            return self.env.get(self.text(node), UNKNOWN)
        if kind == "parenthesized_expression":
            return self.value(children[0]) if children else UNKNOWN
        if kind == "unary_expression" and children:
            value = self.value(children[-1])
            if isinstance(value, (int, float)) and self.text(node).lstrip().startswith("-"):
                return -value
            return UNKNOWN
        if kind == "binary_expression" and len(children) == 2:
            left, right = (self.value(c) for c in children)
            op = self.raw[children[0].end_byte:children[1].start_byte].decode().strip()
            if op == ".." and isinstance(left, (str, int, float)) and isinstance(right, (str, int, float)):
                return str(left) + str(right)
            if all(isinstance(v, (int, float)) for v in (left, right)):
                try:
                    return {"+": lambda: left + right, "-": lambda: left - right,
                            "*": lambda: left * right, "/": lambda: left / right}.get(op, lambda: UNKNOWN)()
                except ArithmeticError:
                    return UNKNOWN
            return UNKNOWN
        if kind == "table_constructor":
            result = {}
            for index, entry in enumerate(children):
                if entry.type != "field" or not entry.named_children:
                    continue
                parts = entry.named_children
                key = self.text(parts[0]) if len(parts) > 1 else index + 1
                value = self.value(parts[-1])
                if value is not UNKNOWN:
                    result[key] = value
            return result
        if kind in ("dot_index_expression", "method_index_expression"):
            name = self.text(node)
            if name.startswith("Enum."):
                return name.rsplit(".", 1)[-1]
            if len(children) == 2:
                base = self.value(children[0])
                key = self.text(children[1])
                if isinstance(base, dict):
                    return base.get(key, UNKNOWN)
                if isinstance(base, Element):
                    return base.props.get(key, UNKNOWN)
            return self.env.get(name, UNKNOWN)
        if kind != "function_call" or len(children) < 2:
            return UNKNOWN
        name = self.text(children[0])
        args_node = children[-1]
        # Function callback bodies never enter the evaluator.
        args = [self.value(c) if c.type != "function_definition" else UNKNOWN for c in args_node.named_children]
        nums = lambda count: len(args) == count and all(isinstance(v, (int, float)) and math.isfinite(v) for v in args)
        if name == "UDim2.new" and nums(4):
            return tuple(args)
        if name == "UDim2.fromOffset" and nums(2):
            return (0, args[0], 0, args[1])
        if name == "UDim2.fromScale" and nums(2):
            return (args[0], 0, args[1], 0)
        if name in ("Vector2.new", "UDim.new") and nums(2):
            return tuple(args)
        if name in ("Color3.fromRGB", "Color3.new") and nums(3):
            factor = 255 if name == "Color3.new" else 1
            return "#" + "".join("%02x" % round(max(0, min(255, n * factor))) for n in args)
        if name == "Color3.fromHex" and args and isinstance(args[0], str):
            color = args[0].lstrip("#")
            return "#" + color if re.fullmatch(r"[0-9a-fA-F]{6}", color) else UNKNOWN
        if name in ("Instance.new", "new") and args and isinstance(args[0], str) and args[0] in GUI_CLASSES:
            props = args[1] if name == "new" and len(args) > 1 and isinstance(args[1], dict) else {}
            parent = (args[2] if len(args) > 2 else props.get("Parent")) if name == "new" else (args[1] if len(args) > 1 else None)
            return self.element(args[0], node, props, parent)
        if name == "Label" and len(args) > 1:
            props = {"BackgroundTransparency": 1, "TextSize": 14, "Size": (1, -28, 0, 32), "Position": (0, 14, 0, 0)}
            if isinstance(args[1], dict):
                props.update(args[1])
            return self.element("TextLabel", node, props, args[0])
        if name == "Row" and args:
            return self.element("Frame", node, {"Size": (1, 0, 0, args[1] if len(args) > 1 and isinstance(args[1], (int, float)) else 36)}, args[0])
        if name.endswith("GamePanel") or name.endswith("MergePanel"):
            return self.element("HubPanel", node, {"Text": args[0] if args and isinstance(args[0], str) else "Solos Hub"})
        if name.endswith(".Sub") or name == "AddTab":
            return self.element("HubPage", node, {"Text": args[0] if args and isinstance(args[0], str) else "Page"})
        control = name.rsplit(".", 1)[-1]
        if control in HUB_CONTROLS and args:
            props = {"Text": args[1] if len(args) > 1 and isinstance(args[1], str) else control}
            if control == "Button" and len(args) > 2 and isinstance(args[2], str):
                props["Action"] = args[2]
            if control == "Toggle" and len(args) > 2:
                props["Value"] = args[2] is True
            if control == "Slider" and len(args) > 4:
                props["Value"] = args[4] if isinstance(args[4], (int, float)) else "—"
            if control == "Section" and len(args) > 2 and isinstance(args[2], str):
                props["Description"] = args[2]
            return self.element("Hub" + control, node, props, args[0])
        if name in ("round",) and args and isinstance(args[0], Element):
            args[0].props["CornerRadius"] = args[1] if len(args) > 1 else 8
        return UNKNOWN

    def statement(self, node):
        kind = node.type
        if kind in ("chunk", "block", "variable_declaration", "do_statement"):
            for child in node.named_children:
                self.statement(child)
        elif kind == "assignment_statement":
            children = node.named_children
            if len(children) < 2:
                return
            values = [self.value(c) for c in children[1].named_children]
            for target, value in zip(children[0].named_children, values):
                if value is UNKNOWN:
                    if target.type == "dot_index_expression" and isinstance(self.value(target.named_children[0]), Element):
                        self.note("Some UI properties depend on runtime values and use preview defaults.")
                    continue
                if target.type == "identifier":
                    self.env[self.text(target)] = value
                elif target.type == "dot_index_expression":
                    base = self.value(target.named_children[0])
                    key = self.text(target.named_children[-1])
                    if isinstance(base, Element):
                        if key == "Parent":
                            base.parent = value if isinstance(value, Element) else None
                        else:
                            base.props[key] = value
                    elif isinstance(base, dict):
                        base[key] = value
        elif kind == "function_call":
            self.value(node)
        elif kind in ("if_statement", "for_statement", "while_statement", "repeat_statement"):
            self.note("Conditional/loop-created UI is omitted; callbacks and game logic are not run.")
        # Function declarations are definitions, not preview elements.


def build_preview(source):
    try:
        from tree_sitter import Language, Parser
        import tree_sitter_luau
        builder = Builder(source)
        tree = Parser(Language(tree_sitter_luau.language())).parse(builder.raw)
        if tree.root_node.has_error:
            builder.note("Syntax errors: this is a partial preview of readable declarations.")
        builder.statement(tree.root_node)
        if any(e.kind in ("ImageLabel", "ImageButton") for e in builder.plan.elements):
            builder.note("Images use placeholders; Roblox assets are not downloaded.")
        builder.note("Approximate layout. Runtime-created UI, animations, and game actions need Roblox Studio.")
        return builder.plan
    except Exception as error:
        return PreviewPlan(error="Preview unavailable: " + str(error))


class LuaPreview(ctk.CTkFrame):
    def __init__(self, parent, on_select, on_example):
        super().__init__(parent, fg_color="#141625", corner_radius=0)
        self.on_select = on_select
        self.plan = PreviewPlan()
        self.key = None
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(header, text="LIVE PREVIEW", text_color="#BDA7FF", font=("Segoe UI", 12, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Example", width=76, height=28, fg_color="#302448", command=on_example).pack(side="right")
        self.pages = ctk.CTkOptionMenu(self, values=["Canvas"], command=lambda value: self.draw(), fg_color="#242A3D", button_color="#302448")
        self.pages.pack(fill="x", padx=12, pady=6)
        self.caption = ctk.CTkLabel(self, text="Open a Luau file to preview its UI", text_color="#9AA3BA", anchor="w", wraplength=370, justify="left")
        self.caption.pack(fill="x", padx=12, pady=(0, 6))
        area = tk.Frame(self, bg="#0B0D14")
        area.pack(fill="both", expand=True, padx=10)
        self.canvas = tk.Canvas(area, bg="#0B0D14", highlightthickness=0, width=1, height=1)
        scroll = ctk.CTkScrollbar(area, command=self.canvas.yview, height=30, fg_color="#141625")
        scroll.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda event: self.draw())
        self.canvas.bind("<Button-1>", self.select_element)
        self.notes = ctk.CTkLabel(self, text="Preview only · click a control to find its code", text_color="#9AA3BA", anchor="w", justify="left", wraplength=370)
        self.notes.pack(fill="x", padx=12, pady=10)
        self.locations = {}
        self.bind("<Configure>", self.resize_labels)

    def resize_labels(self, event):
        self.caption.configure(wraplength=max(200, event.width - 28))
        self.notes.configure(wraplength=max(200, event.width - 28))

    def waiting(self, text):
        self.caption.configure(text=text)

    def show(self, plan, key):
        if self.key == key:
            return
        self.key, self.plan = key, plan
        self.page_elements = [e for e in plan.elements if e.kind == "HubPage"]
        names = [str(e.props.get("Text", "Page")) for e in self.page_elements]
        values = ["Canvas"] + names
        current = self.pages.get()
        self.pages.configure(values=values)
        if current not in values or (current == "Canvas" and names):
            self.pages.set(names[0] if names else "Canvas")
        self.caption.configure(text=plan.error or ("%d UI elements · click one to locate its code" % len(plan.elements)))
        self.notes.configure(text="\n".join(plan.notes) or "Preview only · actions do not run")
        self.draw()

    def select_element(self, event):
        items = self.canvas.find_overlapping(event.x, self.canvas.canvasy(event.y), event.x, self.canvas.canvasy(event.y))
        for item in reversed(items):
            if item in self.locations:
                self.on_select(self.locations[item])
                break

    def item(self, method, element, *args, **kwargs):
        item = getattr(self.canvas, method)(*args, **kwargs)
        self.locations[item] = element.line
        return item

    @staticmethod
    def number(value, default):
        return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else default

    @staticmethod
    def color(value, default):
        return value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else default

    def draw(self):
        self.canvas.delete("all")
        self.locations = {}
        width = max(200, self.canvas.winfo_width())
        if not self.plan.elements:
            self.canvas.create_text(width / 2, 120, text=self.plan.error or "No supported UI declarations found.\nUse Example to try a live preview.",
                                    fill="#9AA3BA", width=width - 40, justify="center", font=("Segoe UI", 13))
            self.canvas.configure(scrollregion=(0, 0, width, 300))
            return
        if self.pages.get() != "Canvas":
            page = next((e for e in self.plan.elements if e.kind == "HubPage" and e.props.get("Text") == self.pages.get()), None)
            self.draw_hub(width, page)
        elif any(e.kind.startswith("Hub") for e in self.plan.elements) and not any(e.kind == "ScreenGui" for e in self.plan.elements):
            self.draw_hub(width, None)
        else:
            try:
                self.draw_canvas(width)
            except (ValueError, TypeError, OverflowError, tk.TclError) as error:
                self.caption.configure(text="Some layout values could not be drawn: " + str(error))

    def draw_hub(self, width, page):
        panel = next((e for e in self.plan.elements if e.kind == "HubPanel"), None)
        self.canvas.create_text(18, 24, text=(panel.props.get("Text") if panel else "Solos Hub"), fill="#C7A5FF", font=("Segoe UI", 19, "bold"), anchor="w")
        y = 52
        def belongs(item):
            seen = set()
            while item is not None and id(item) not in seen:
                if item is page:
                    return True
                seen.add(id(item))
                item = item.parent
            return page is None
        for element in self.plan.elements:
            if not element.kind.startswith("Hub") or element.kind in ("HubPanel", "HubPage") or not belongs(element):
                continue
            section = element.kind in ("HubSection", "HubCollapse")
            height = 70 if section and element.props.get("Description") else (46 if section else 52)
            self.item("create_rectangle", element, 10, y, width - 12, y + height - 5, fill="#211B34" if section else "#171B28", outline="")
            self.item("create_text", element, 22, y + 20, text=element.props.get("Text", ""), width=max(60, width - 145), anchor="w",
                      fill="#D6BDFF" if section else "#E8EAF5", font=("Segoe UI", 12, "bold" if section else "normal"))
            if section and element.props.get("Description"):
                self.item("create_text", element, 22, y + 47, text=element.props["Description"], width=width - 50, anchor="w", fill="#96A0B8", font=("Segoe UI", 9))
            if element.kind == "HubToggle":
                on = element.props.get("Value")
                self.item("create_rectangle", element, width - 68, y + 12, width - 24, y + 34, fill="#9B75F5" if on else "#394058", outline="")
                x = width - 35 if on else width - 57
                self.item("create_oval", element, x - 7, y + 16, x + 7, y + 30, fill="#F0ECFF", outline="")
            elif element.kind == "HubButton":
                self.item("create_rectangle", element, width - 100, y + 10, width - 22, y + 36, fill="#49386F", outline="")
                self.item("create_text", element, width - 61, y + 23, text=element.props.get("Action", "Run"), fill="#E8DFFF", font=("Segoe UI", 10))
            elif element.kind in ("HubDropdown", "HubInput", "HubKeybind", "HubInfoRow", "HubSlider"):
                self.item("create_text", element, width - 30, y + 23, text=str(element.props.get("Value", "▾" if element.kind == "HubDropdown" else "…")), anchor="e", fill="#BBA4F2", font=("Segoe UI", 12))
            y += height
        self.canvas.configure(scrollregion=(0, 0, width, max(y + 20, 300)))

    def draw_canvas(self, width):
        scale = max(0.1, min((width - 20) / 720, (self.canvas.winfo_height() - 28) / 480))
        left = max(10, (width - 720 * scale) / 2)
        viewport = (left, 14, 720, 480)
        self.canvas.create_rectangle(left, 14, left + 720 * scale, 14 + 480 * scale, fill="#191D2A", outline="#333B55")
        children = {}
        for element in self.plan.elements:
            children.setdefault(id(element.parent), []).append(element)
        visited = set()
        def render(element, parent_box, inherited_bg, depth=0):
            if id(element) in visited or depth > 40:
                return
            visited.add(id(element))
            p = element.props
            if p.get("Visible") is False or (element.kind == "ScreenGui" and p.get("Enabled") is False):
                return
            if element.kind in ("UICorner", "UIStroke", "UIListLayout", "UIPadding"):
                return
            px, py, pw, ph = parent_box
            if element.kind == "ScreenGui":
                box, bg = parent_box, inherited_bg
            else:
                size = p.get("Size", (0, 100, 0, 100 if element.kind in ("Frame", "ScrollingFrame") else 40))
                pos = p.get("Position", (0, 0, 0, 0))
                anchor = p.get("AnchorPoint", (0, 0))
                if not isinstance(size, tuple) or len(size) != 4 or not isinstance(pos, tuple) or len(pos) != 4:
                    return
                if not isinstance(anchor, tuple) or len(anchor) != 2:
                    anchor = (0, 0)
                w, h = max(0, size[0] * pw + size[1]), max(0, size[2] * ph + size[3])
                w, h = min(w, 10000), min(h, 10000)
                x, y = px + (pos[0] * pw + pos[1] - anchor[0] * w) * scale, py + (pos[2] * ph + pos[3] - anchor[1] * h) * scale
                box = (x, y, w, h)
                bg = self.color(p.get("BackgroundColor3"), "#30263F" if element.kind == "TextButton" else "#242A3A")
                alpha = max(0, min(1, self.number(p.get("BackgroundTransparency"), 0)))
                if alpha:
                    bg = "#" + "".join("%02x" % round(int(bg[i:i+2], 16) * (1-alpha) + int(inherited_bg[i:i+2], 16) * alpha) for i in (1, 3, 5))
                decorations = children.get(id(element), [])
                corner = next((e.props.get("CornerRadius", (0, 8)) for e in decorations if e.kind == "UICorner"), p.get("CornerRadius", 0))
                if isinstance(corner, tuple) and len(corner) == 2:
                    corner = min(w, h) * corner[0] + corner[1]
                radius = min(w * scale / 2, h * scale / 2, max(0, self.number(corner, 0) * scale))
                stroke = next((e for e in decorations if e.kind == "UIStroke"), None)
                outline = self.color(stroke.props.get("Color"), "#9B87F5") if stroke else ""
                if alpha < 1 or stroke:
                    x2, y2 = x + w * scale, y + h * scale
                    if radius:
                        self.item("create_polygon", element, x+radius,y, x2-radius,y, x2,y, x2,y+radius,
                                  x2,y2-radius, x2,y2, x2-radius,y2, x+radius,y2, x,y2, x,y2-radius, x,y+radius, x,y,
                                  smooth=True, fill=bg if alpha < 1 else "", outline=outline)
                    else:
                        self.item("create_rectangle", element, x, y, x2, y2, fill=bg if alpha < 1 else "", outline=outline)
                if element.kind.startswith("Text"):
                    text = p.get("Text", p.get("PlaceholderText", element.kind))
                    text = str(text)[:2000]
                    if p.get("RichText"):
                        text = re.sub(r"<[^>]*>", "", text)
                    align = p.get("TextXAlignment", "Center")
                    tx = x + (8 if align == "Left" else w * scale - 8 if align == "Right" else w * scale / 2)
                    self.item("create_text", element, tx, y + h * scale / 2, text=text, width=max(1, w * scale - 12),
                              anchor={"Left": "w", "Right": "e"}.get(align, "center"), justify=align.lower() if align in ("Left", "Right", "Center") else "center",
                              fill=self.color(p.get("TextColor3"), "#F0F2FA"), font=("Segoe UI", max(7, min(64, round(self.number(p.get("TextSize"), 14) * scale)))))
                elif element.kind.startswith("Image"):
                    self.item("create_text", element, x + w * scale / 2, y + h * scale / 2, text="[ Image ]", fill="#BDA7FF", font=("Segoe UI", 12))
            items = children.get(id(element), [])
            layout = next((item for item in items if item.kind == "UIListLayout"), None)
            pad = next((item for item in items if item.kind == "UIPadding"), None)
            def udim(value, extent):
                return value[0] * extent + value[1] if isinstance(value, tuple) and len(value) == 2 else 0
            if pad:
                left = udim(pad.props.get("PaddingLeft"), box[2])
                right = udim(pad.props.get("PaddingRight"), box[2])
                top = udim(pad.props.get("PaddingTop"), box[3])
                bottom = udim(pad.props.get("PaddingBottom"), box[3])
                box = (box[0] + left * scale, box[1] + top * scale, max(0, box[2]-left-right), max(0, box[3]-top-bottom))
            cursor = 0
            for child in sorted(items, key=lambda item: self.number(item.props.get("LayoutOrder" if layout else "ZIndex"), 1)):
                if child.kind in ("UICorner", "UIStroke", "UIListLayout", "UIPadding") or child.props.get("Visible") is False:
                    continue
                if layout:
                    # Keep the model immutable while computing this canvas layout.
                    original = child.props
                    child.props = dict(original)
                    horizontal = layout.props.get("FillDirection") == "Horizontal"
                    child.props["Position"] = (0, cursor if horizontal else 0, 0, 0 if horizontal else cursor)
                    child.props["AnchorPoint"] = (0, 0)
                    size = child.props.get("Size", (0, 100, 0, 40))
                    extent = box[2] if horizontal else box[3]
                    axis = 0 if horizontal else 2
                    advance = size[axis] * extent + size[axis+1] if isinstance(size, tuple) and len(size) == 4 else 40
                    try:
                        render(child, box, bg, depth + 1)
                    finally:
                        child.props = original
                    cursor += advance + udim(layout.props.get("Padding"), extent)
                else:
                    render(child, box, bg, depth + 1)
        for element in children.get(id(None), []):
            if not element.kind.startswith("Hub"):
                render(element, viewport, "#191D2A")
        self.canvas.configure(scrollregion=(0, 0, width, max(300, 480 * scale + 30)))
