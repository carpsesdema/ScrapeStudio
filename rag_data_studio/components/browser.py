# rag_data_studio/components/browser.py
"""
The interactive QWebEngineView component for visual element selection.
This is a robust version with stable selector generation and rich context awareness.
"""
import uuid
import json
from PySide6.QtCore import Signal, QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView


class InteractiveBrowser(QWebEngineView):
    """Browser with a robust element targeting system that provides full context on click."""
    element_selected = Signal(dict)  # Emits a dictionary with full context about the selection

    def __init__(self):
        super().__init__()
        self.targeting_active = False
        self.page().profile().setHttpUserAgent("ScrapeStudio/1.2 InteractiveBrowser")
        self.selection_var = f"__scrapeStudioSelection_{uuid.uuid4().hex}"
        self.cleanup_func = f"__scrapeStudioCleanup_{uuid.uuid4().hex}"
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.check_for_selection)

    def _get_targeting_js(self) -> str:
        """Generates the JavaScript code to be injected for element selection."""
        return f"""
        (function() {{
            if (window.{self.cleanup_func}) return;
            console.log('ScrapeStudio: Activating full-context targeting mode.');

            let isTargeting = true;
            let highlightedEl = null;

            // Function to generate a detailed, unique CSS path for an element
            function getCssPath(el) {{
                if (!(el instanceof Element)) return;
                const path = [];
                while (el.nodeType === Node.ELEMENT_NODE) {{
                    let selector = el.nodeName.toLowerCase();
                    if (el.id) {{
                        selector = '#' + el.id.replace(/\\s/g, '-');
                        path.unshift(selector);
                        break;
                    }} else {{
                        let sib = el, nth = 1;
                        while ((sib = sib.previousElementSibling)) {{
                            if (sib.nodeName.toLowerCase() === el.nodeName.toLowerCase()) nth++;
                        }}
                        if (nth != 1) selector += `:nth-of-type(${'{nth}'})`;
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

            function onClick(e) {{
                if (!isTargeting) return;
                e.preventDefault();
                e.stopPropagation();

                const el = e.target;
                const table = el.closest('table');
                const row = el.closest('tr');

                const selectionContext = {{
                    clicked_element: {{
                        selector: getCssPath(el),
                        text: el.textContent.trim(),
                        tag: el.tagName.toLowerCase()
                    }},
                    is_in_table: !!table,
                }};

                if (table) {{
                    selectionContext.table = {{
                        selector: getCssPath(table),
                        tag: 'table'
                    }};
                    const thead = table.querySelector('thead');
                    // Find headers in thead, or fallback to the first row of the table
                    const header_cells = table.querySelectorAll('thead th, tr:first-child th');
                    selectionContext.table.headers = Array.from(header_cells).map(th => th.textContent.trim());

                    if(row) {{
                        // Provide a generic selector for ALL rows in the tbody, not just the one clicked
                        const tbody = table.querySelector('tbody') || table;
                        selectionContext.table.all_rows_selector = getCssPath(tbody) + ' > tr';
                    }}
                }}

                window['{self.selection_var}'] = selectionContext;
                console.log('ScrapeStudio: Full context captured:', window['{self.selection_var}']);
            }}

            window.{self.cleanup_func} = function() {{
                if (highlightedEl) highlightedEl.style.outline = '';
                document.removeEventListener('mouseover', (e) => highlight(e.target), true);
                document.removeEventListener('click', onClick, true);
            }};

            document.addEventListener('mouseover', (e) => highlight(e.target), true);
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
                    if data and data.get('clicked_element'):
                        self.element_selected.emit(data)
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Browser Error: Could not process selection: {e}")

        self.page().runJavaScript(js_to_check, callback)