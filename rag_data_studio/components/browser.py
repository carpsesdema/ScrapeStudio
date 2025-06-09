# rag_data_studio/components/browser.py
"""
The interactive QWebEngineView component for visual element selection.
This is a robust version with stable selector generation.
"""
import uuid
import json
from PySide6.QtCore import Signal, QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView


class InteractiveBrowser(QWebEngineView):
    """Browser with a robust element targeting system."""
    element_selected = Signal(str, str)  # Emits a UNIQUE selector and the text of the clicked element

    def __init__(self):
        super().__init__()
        self.targeting_active = False
        self.page().profile().setHttpUserAgent("ScrapeStudio/1.1 InteractiveBrowser")
        self.selection_var = f"__scrapeStudioSelection_{uuid.uuid4().hex}"
        self.cleanup_func = f"__scrapeStudioCleanup_{uuid.uuid4().hex}"
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.check_for_selection)

    def _get_targeting_js(self) -> str:
        """Generates the JavaScript code to be injected for element selection."""
        return f"""
        (function() {{
            if (window.{self.cleanup_func}) return;
            console.log('ScrapeStudio: Activating robust targeting mode.');

            let isTargeting = true;
            let highlightedEl = null;

            function getCssPath(el) {{
                if (!(el instanceof Element)) return;
                const path = [];
                while (el.nodeType === Node.ELEMENT_NODE) {{
                    let selector = el.nodeName.toLowerCase();
                    if (el.id) {{
                        selector += '#' + el.id;
                        path.unshift(selector);
                        break;
                    }} else {{
                        let sib = el, nth = 1;
                        while ((sib = sib.previousElementSibling)) {{
                            if (sib.nodeName.toLowerCase() == selector) nth++;
                        }}
                        if (nth != 1) selector += ":nth-of-type("+nth+")";
                    }}
                    path.unshift(selector);
                    el = el.parentNode;
                }}
                return path.join(" > ");
            }}

            function highlight(el) {{
                if (highlightedEl) highlightedEl.style.outline = '';
                el.style.outline = '3px solid #FF5722';
                highlightedEl = el;
            }}

            function onMouseOver(e) {{ if (isTargeting) highlight(e.target); }}

            function onClick(e) {{
                if (!isTargeting) return;
                e.preventDefault();
                e.stopPropagation();

                window['{self.selection_var}'] = {{
                    selector: getCssPath(e.target),
                    text: e.target.textContent.trim()
                }};

                console.log('ScrapeStudio: Element selected:', window['{self.selection_var}']);
            }}

            window.{self.cleanup_func} = function() {{
                console.log('ScrapeStudio: Cleaning up targeting.');
                if (highlightedEl) highlightedEl.style.outline = '';
                document.removeEventListener('mouseover', onMouseOver, true);
                document.removeEventListener('click', onClick, true);
            }};

            document.addEventListener('mouseover', onMouseOver, true);
            document.addEventListener('click', onClick, true);
        }})();
        """

    def enable_selector_mode(self):
        if self.targeting_active: return
        self.targeting_active = True
        self.page().runJavaScript(f"window['{self.selection_var}'] = null;")
        self.page().runJavaScript(self._get_targeting_js())
        self.poll_timer.start(300)

    def disable_selector_mode(self):
        if not self.targeting_active: return
        self.targeting_active = False
        self.poll_timer.stop()
        self.page().runJavaScript(f"if (window.{self.cleanup_func}) window.{self.cleanup_func}();")

    def check_for_selection(self):
        if not self.targeting_active: return
        js_to_check = f"JSON.stringify(window['{self.selection_var}'] || null);"

        def callback(result_json_str):
            if result_json_str and result_json_str != "null":
                self.page().runJavaScript(f"window['{self.selection_var}'] = null;")
                try:
                    data = json.loads(result_json_str)
                    if data and data.get('selector'):
                        self.element_selected.emit(data['selector'], data['text'])
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Browser Error: Could not process selection: {e}")

        self.page().runJavaScript(js_to_check, callback)

    def get_element_info(self, selector: str, callback):
        """A new, reliable way to ask the browser for info about an element."""
        escaped_selector = selector.replace('\\', '\\\\').replace("'", "\\'")
        js_get_info = f"""
        (() => {{
            const el = document.querySelector('{escaped_selector}');
            if (!el) return null;

            function getCssPath(el) {{
                if (!(el instanceof Element)) return;
                const path = [];
                while (el.nodeType === Node.ELEMENT_NODE) {{
                    let selector = el.nodeName.toLowerCase();
                    if (el.id) {{
                        selector += '#' + el.id;
                        path.unshift(selector);
                        break;
                    }} else {{
                        let sib = el, nth = 1;
                        while ((sib = sib.previousElementSibling)) {{
                            if (sib.nodeName.toLowerCase() == selector) nth++;
                        }}
                        if (nth != 1) selector += ":nth-of-type("+nth+")";
                    }}
                    path.unshift(selector);
                    el = el.parentNode;
                }}
                return path.join(" > ");
            }}

            const info = {{}};
            const table = el.closest('table');
            if (table) {{
                info.is_in_table = true;
                info.table_selector = getCssPath(table);

                const thead = table.querySelector('thead');
                const headers = thead ? thead.querySelectorAll('th') : table.querySelectorAll('tr:first-child th');
                info.headers = Array.from(headers).map(th => th.textContent.trim());

                const row = el.closest('tr');
                if(row) {{
                    info.row_selector = getCssPath(row);
                }}
            }}
            return info;
        }})();
        """
        self.page().runJavaScript(js_get_info, callback)