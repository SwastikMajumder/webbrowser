from PIL import Image, ImageDraw, ImageFont, ImageTk
import tkinter as tk
from tkinter import messagebox
import re
import requests
import io
import time
import platform

# -------------------------
# Tree structure
# -------------------------
class TreeNode:
    def __init__(self, name, text="", attrs=None, children=None):
        self.name = name
        self.text = text
        self.attrs = attrs or {}
        self.children = children or []

# -------------------------
# Simple HTML-like parser (with attributes)
# -------------------------
def parse_html(html):
    tag_pattern = re.compile(r"<(/?)(\w+)([^>]*)>")
    attr_pattern = re.compile(r'(\w+)="([^"]*)"')

    root = TreeNode("root")
    stack = [root]
    pos = 0

    for match in tag_pattern.finditer(html):
        start, end = match.span()
        if start > pos:
            text = html[pos:start]
            if text.strip():
                stack[-1].children.append(TreeNode("text", text=text))

        closing, tag, attr_str = match.groups()
        if closing:  # closing tag
            if len(stack) > 1:
                stack.pop()
        else:  # opening tag
            attrs = dict(attr_pattern.findall(attr_str))
            node = TreeNode(tag, attrs=attrs)
            stack[-1].children.append(node)
            stack.append(node)

        pos = end

    if pos < len(html):
        stack[-1].children.append(TreeNode("text", text=html[pos:]))

    return root

# -------------------------
# Font setup (Windows paths)
# -------------------------
def load_fonts():
    return {
        "normal": ImageFont.truetype("arial.ttf", 20),
        "bold": ImageFont.truetype("arialbd.ttf", 20),
        "italic": ImageFont.truetype("ariali.ttf", 20),
        "mono": ImageFont.truetype("cour.ttf", 20),
        "h1": ImageFont.truetype("arialbd.ttf", 32),
        "h2": ImageFont.truetype("arialbd.ttf", 28),
        "h3": ImageFont.truetype("arialbd.ttf", 24),
        "supsub": ImageFont.truetype("arial.ttf", 14)
    }

fonts = load_fonts()

# -------------------------
# Text drawing with cursor
# -------------------------
def draw_text_with_cursor(img, text, cursor, font, new_line=False, line_spacing=5, underline=False, superscript=False, subscript=False):
    draw = ImageDraw.Draw(img)
    x, y = cursor
    max_w, max_h = 0, 0
    if new_line:
        for line in text.split("\n"):
            if line.strip():
                bbox = draw.textbbox((x, y), line, font=font)
                draw.text((x, y), line, font=font, fill="black")
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                if underline:
                    draw.line([(x, y + h + 2), (x + w, y + h + 2)], fill="black", width=1)
                y += h + line_spacing
                max_w = max(max_w, w)
                max_h += h + line_spacing
        return (x, y), (max_w, max_h)
    else:
        if text.strip():
            y_offset = -5 if superscript else 5 if subscript else 0
            bbox = draw.textbbox((x, y + y_offset), text, font=font)
            draw.text((x, y + y_offset), text, font=font, fill="black")
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if underline:
                draw.line([(x, y + h + 2 + y_offset), (x + w, y + h + 2 + y_offset)], fill="black", width=1)
            max_w = max(max_w, w)
            max_h = h
        return (x + max_w, y), (max_w, max_h)

# -------------------------
# Image downloading and rendering with retries
# -------------------------
def draw_image(img, url, cursor, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image_data = io.BytesIO(response.content)
            web_image = Image.open(image_data)
            img.paste(web_image, cursor)
            return (cursor[0], cursor[1] + web_image.size[1]), web_image.size
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
            else:
                # Generate placeholder image
                placeholder = Image.new("RGB", (200, 100), "gray")
                draw = ImageDraw.Draw(placeholder)
                draw.text((10, 40), f"Failed: {url}", font=fonts["normal"], fill="white")
                img.paste(placeholder, cursor)
                return (cursor[0], cursor[1] + 100), (200, 100)

# -------------------------
# Recursive rendering
# -------------------------
def render_html_dfs(node, img, cursor=(10, 10), table_cell_w=150, table_cell_h=40):
    draw = ImageDraw.Draw(img)
    max_x, max_y = cursor

    def dfs(node, cursor, table_border=1, list_indent=20, list_counter=0):
        nonlocal max_x, max_y
        x, y = cursor

        if node.name == "text":
            (nx, ny), (w, h) = draw_text_with_cursor(img, node.text, cursor, fonts["normal"], new_line=False)
            max_x = max(max_x, nx + w)
            max_y = max(max_y, ny + h)
            return (nx, ny)

        elif node.name == "br":
            return (10, y + 25)

        elif node.name in ["h1", "h2", "h3"]:
            font_key = node.name
            for child in node.children:
                if child.name == "text":
                    (nx, ny), (_, h) = draw_text_with_cursor(img, child.text, cursor, fonts[font_key], new_line=True)
                    cursor = (nx, ny)
                else:
                    cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            max_x = max(max_x, cursor[0])
            max_y = max(max_y, cursor[1] + 25)
            return (10, cursor[1] + 25)

        elif node.name == "p":
            for child in node.children:
                cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            max_x = max(max_x, cursor[0])
            max_y = max(max_y, cursor[1] + 25)
            return (10, cursor[1] + 25)

        elif node.name == "div":
            for child in node.children:
                cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            max_x = max(max_x, cursor[0])
            max_y = max(max_y, cursor[1] + 25)
            return (10, cursor[1] + 25)

        elif node.name == "b" or node.name == "strong":
            for child in node.children:
                if child.name == "text":
                    (nx, ny), _ = draw_text_with_cursor(img, child.text, cursor, fonts["bold"], new_line=False)
                    cursor = (nx, ny)
                else:
                    cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            return cursor

        elif node.name == "i" or node.name == "em":
            for child in node.children:
                if child.name == "text":
                    (nx, ny), _ = draw_text_with_cursor(img, child.text, cursor, fonts["italic"], new_line=False)
                    cursor = (nx, ny)
                else:
                    cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            return cursor

        elif node.name == "u":
            for child in node.children:
                if child.name == "text":
                    (nx, ny), _ = draw_text_with_cursor(img, child.text, cursor, fonts["normal"], new_line=False, underline=True)
                    cursor = (nx, ny)
                else:
                    cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            return cursor

        elif node.name == "tt":
            for child in node.children:
                if child.name == "text":
                    (nx, ny), _ = draw_text_with_cursor(img, child.text, cursor, fonts["mono"], new_line=False)
                    cursor = (nx, ny)
                else:
                    cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            return cursor

        elif node.name == "sup":
            for child in node.children:
                if child.name == "text":
                    (nx, ny), _ = draw_text_with_cursor(img, child.text, cursor, fonts["supsub"], new_line=False, superscript=True)
                    cursor = (nx, ny)
                else:
                    cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            return cursor

        elif node.name == "sub":
            for child in node.children:
                if child.name == "text":
                    (nx, ny), _ = draw_text_with_cursor(img, child.text, cursor, fonts["supsub"], new_line=False, subscript=True)
                    cursor = (nx, ny)
                else:
                    cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            return cursor

        elif node.name == "ul":
            cursor = (10, y + 25)
            for child in node.children:
                cursor = dfs(child, cursor, table_border, list_indent + 20, 0)
            max_x = max(max_x, cursor[0])
            max_y = max(max_y, cursor[1] + 25)
            return (10, cursor[1] + 25)

        elif node.name == "ol":
            cursor = (10, y + 25)
            list_counter = 1
            for child in node.children:
                cursor = dfs(child, cursor, table_border, list_indent + 20, list_counter)
                list_counter += 1
            max_x = max(max_x, cursor[0])
            max_y = max(max_y, cursor[1] + 25)
            return (10, cursor[1] + 25)

        elif node.name == "li":
            indent_x = x + list_indent
            if list_counter > 0:
                marker = f"{list_counter}. "
                (nx, ny), _ = draw_text_with_cursor(img, marker, (x, y), fonts["normal"], new_line=False)
                cursor = (nx, ny)
            else:
                marker = "• "
                (nx, ny), _ = draw_text_with_cursor(img, marker, (x, y), fonts["normal"], new_line=False)
                cursor = (nx, ny)
            for child in node.children:
                cursor = dfs(child, (cursor[0], cursor[1]), table_border, list_indent, list_counter)
            max_x = max(max_x, cursor[0])
            max_y = max(max_y, cursor[1] + 25)
            return (10, cursor[1] + 25)

        elif node.name == "table":
            border_width = int(node.attrs.get("border", table_border))
            cursor = (10, y + 25)
            row = 0
            col = 0
            cell_positions = {}
            max_cols = 0
            for child in node.children:
                if child.name == "tr":
                    col = 0
                    for td_child in child.children:
                        if td_child.name in ["td", "th"]:
                            rowspan = int(td_child.attrs.get("rowspan", 1))
                            colspan = int(td_child.attrs.get("colspan", 1))
                            while (row, col) in cell_positions:
                                col += 1
                            cell_x = 10 + col * table_cell_w
                            cell_y = y + row * table_cell_h
                            draw.rectangle([cell_x, cell_y, cell_x + colspan * table_cell_w - 5, cell_y + rowspan * table_cell_h - 5],
                                           outline="black", width=border_width)
                            inner_cursor = (cell_x + 5, cell_y + 5)
                            inner_cursor = dfs(td_child, inner_cursor, border_width, list_indent, list_counter)
                            for r in range(row, row + rowspan):
                                for c in range(col, col + colspan):
                                    cell_positions[(r, c)] = True
                            col += colspan
                    max_cols = max(max_cols, col)
                    row += 1
            max_x = max(max_x, 10 + max_cols * table_cell_w)
            max_y = max(max_y, y + row * table_cell_h)
            return (10, y + row * table_cell_h)

        elif node.name in ["td", "th"]:
            font = fonts["bold"] if node.name == "th" else fonts["normal"]
            for child in node.children:
                cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            return cursor

        elif node.name == "img":
            src = node.attrs.get("src", "")
            if src:
                (nx, ny), (w, h) = draw_image(img, src, cursor)
                max_x = max(max_x, nx + w)
                max_y = max(max_y, ny + h)
                cursor = (10, ny + 25)
            return cursor

        else:
            for child in node.children:
                cursor = dfs(child, cursor, table_border, list_indent, list_counter)
            return cursor

    final_cursor = dfs(node, cursor)
    max_x = max(max_x, final_cursor[0] + 10)
    max_y = max(max_y, final_cursor[1] + 10)
    img_resized = img.crop((0, 0, max_x, max_y))
    return final_cursor

# -------------------------
# Tkinter GUI with Scrollbars and Mouse Wheel
# -------------------------
class HTMLRendererApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HTML Renderer")
        self.fonts = load_fonts()
        self.image = None
        self.photo = None

        # GUI Layout with Scrollbars
        self.frame = tk.Frame(self.root)
        self.frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Canvas with Scrollbars
        self.canvas = tk.Canvas(self.frame, bg="white")
        self.h_scrollbar = tk.Scrollbar(self.frame, orient=tk.HORIZONTAL)
        self.v_scrollbar = tk.Scrollbar(self.frame, orient=tk.VERTICAL)
        self.h_scrollbar.config(command=self.canvas.xview)
        self.v_scrollbar.config(command=self.canvas.yview)
        self.canvas.config(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)

        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind mouse wheel events
        if platform.system() == "Windows":
            self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
            self.canvas.bind("<Shift-MouseWheel>", self.on_mouse_wheel_horizontal)
        else:  # macOS/Linux
            self.canvas.bind("<Button-4>", self.on_mouse_wheel)
            self.canvas.bind("<Button-5>", self.on_mouse_wheel)
            self.canvas.bind("<Shift-Button-4>", self.on_mouse_wheel_horizontal)
            self.canvas.bind("<Shift-Button-5>", self.on_mouse_wheel_horizontal)

        # Default HTML with img tag
        self.default_html = """
<html>
  <body>
    <h1>HTML Render Test</h1>
    <h2>Subheading</h2>
    <h3>Smaller Heading</h3>

    <p>This is <b>bold</b>, <strong>strong</strong>, <i>italic</i>, <em>emphasized</em>, <u>underlined</u>, and <tt>monospaced</tt> text.<br>New line after br.</p>

    <div>
      <p>Inside a div with <sup>superscript</sup> and <sub>subscript</sub>.</p>
      <img src="https://dummyimage.com/150x150/cccccc/969696.png">
    </div>

    <ul>
      <li>First item</li>
      <li>Second item with <b>bold</b></li>
    </ul>

    <ol>
      <li>Numbered item 1</li>
      <li>Numbered item 2</li>
    </ol>

    <table border="2">
      <tr>
        <td><b>Name</b></td>
        <td><b>Age</b></td>
        <td><b>Note</b></td>
      </tr>
      <tr>
        <td>Alice</td>
        <td><i>23</i></td>
        <td><tt>Loves coding</tt></td>
      </tr>
      <tr>
        <td>Bob</td>
        <td>30</td>
        <td><b><i><tt>Chess player</tt></i></b></td>
      </tr>
    </table>

    <p>End of <b>test</b>.</p>
  </body>
</html>
"""

        # Initial render
        self.render_html()

    def render_html(self, event=None):
        try:
            html = self.default_html.strip()
            root = parse_html(html)
            # Create image with larger initial size
            self.image = Image.new("RGB", (3200, 3200), "white")
            render_html_dfs(root, self.image)
            self.photo = ImageTk.PhotoImage(self.image)
            self.canvas.delete("all")  # Clear previous content
            self.canvas.config(scrollregion=(0, 0, self.image.width, self.image.height))
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to render HTML: {str(e)}")

    def on_mouse_wheel(self, event):
        if platform.system() == "Windows":
            delta = event.delta / 120  # Normalize wheel delta
            self.canvas.yview_scroll(int(-delta), "units")
        else:  # macOS/Linux
            if event.num == 4:  # Scroll up
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:  # Scroll down
                self.canvas.yview_scroll(1, "units")

    def on_mouse_wheel_horizontal(self, event):
        if platform.system() == "Windows":
            delta = event.delta / 120  # Normalize wheel delta
            self.canvas.xview_scroll(int(-delta), "units")
        else:  # macOS/Linux
            if event.num == 4:  # Scroll left
                self.canvas.xview_scroll(-1, "units")
            elif event.num == 5:  # Scroll right
                self.canvas.xview_scroll(1, "units")

# -------------------------
# Run the application
# -------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = HTMLRendererApp(root)
    root.mainloop()
