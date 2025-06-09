# rag_data_studio/components/browser.py
"""
The interactive QWebEngineView component for visual element selection.
This is an enhanced version that provides smart selector suggestions.
"""
import uuid
import json
from PySide6.QtCore import Signal, QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView


class InteractiveBrowser(QWebEngineView):
    """Browser with smart element targeting that suggests parent/container selectors."""
    element_selected = Signal(str, str, dict)  # Emits: selector, text, suggestions_dict

    def __init__(self):
        super().__init__()
        self.targeting_active = False
        self.page().profile().setHttpUserAgent("ScrapeStudio/1.0 InteractiveBrowser")

        # Unique IDs for JS variables to prevent conflicts
        self.selection_var = f"__scrapeStudioSelection_{uuid.uuid4().hex}"
        self.cleanup_func = f"__scrapeStudioCleanup_{uuid.uuid4().hex}"

        # Timer to poll for selection from the web page
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.check_for_selection)

    def _get_targeting_js(self) -> str:
        """Generates the JavaScript code to be injected for element selection."""
        return f"""
        (function() {{
            // Prevent re-injection
            if (window.{self.cleanup_func}) {{
                window.{self.cleanup_func}();
            }}
            console.log('ScrapeStudio: Activating targeting mode.');

            let isTargeting = true;
            let highlightedEl = null;
            const tooltip = document.createElement('div');
            tooltip.id = 'scrape-studio-tooltip';
            tooltip.style.cssText = `
                position: fixed; top: 15px; right: 15px; background: #4CAF50; color: white;
                padding: 10px 15px; border-radius: 8px; z-index: 9999999;
                font-family: Arial, sans-serif; font-size: 14px; font-weight: bold;
                box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            `;
            tooltip.textContent = '🎯 Targeting Active: Click any element';
            document.body.appendChild(tooltip);

            function generateSelector(el) {{
                if (!el || !(el instanceof Element)) return '';
                if (el.id) return '#' + el.id.trim().replace(/\\s+/g, '-');

                let parts = [];
                while (el && el.nodeType === Node.ELEMENT_NODE) {{
                    let selector = el.nodeName.toLowerCase();
                    if (el.className && typeof el.className === 'string') {{
                        const stableClasses = el.className.trim().split(/\\s+/).filter(c => c && !c.includes(':')).slice(0, 2);
                        if (stableClasses.length > 0) {{
                            selector += '.' + stableClasses.join('.');
                        }}
                    }}
                    let sib = el, nth = 1;
                    while ((sib = sib.previousElementSibling)) {{
                        if (sib.nodeName.toLowerCase() == selector.split('.')[0]) nth++;
                    }}
                    if (el.parentElement && el.parentElement.children.length > 1) {{
                       selector += `:nth-of-type(${'{nth}'})`;
                    }}

                    parts.unshift(selector);
                    if (parts.length > 3) break; // Keep selectors reasonably short
                    el = el.parentElement;
                }}
                return parts.join(' > ');
            }}

            function highlight(el) {{
                if (highlightedEl) {{
                    highlightedEl.style.outline = '';
                    highlightedEl.style.backgroundColor = '';
                }}
                el.style.outline = '3px solid #FF5722';
                el.style.backgroundColor = 'rgba(255, 87, 34, 0.2)';
                highlightedEl = el;
            }}

            function onMouseOver(e) {{
                if (!isTargeting) return;
                highlight(e.target);
            }}

            function onClick(e) {{
                if (!isTargeting) return;
                e.preventDefault();
                e.stopPropagation();

                const target = e.target;
                const suggestions = {{}};

                // 1. Current Element
                suggestions.current = {{
                    selector: generateSelector(target),
                    text: target.textContent.trim(),
                    type: target.tagName.toLowerCase()
                }};

                // 2. Parent Element
                const parent = target.parentElement;
                if (parent && parent.nodeName.toLowerCase() !== 'body') {{
                    suggestions.parent = {{
                        selector: generateSelector(parent),
                        text: parent.textContent.trim(),
                        type: parent.tagName.toLowerCase()
                    }};
                }}

                // 3. Container Element (for list-like items)
                const container = target.closest('tr, li, .item, .card, [class*="row"], [class*="item-"]');
                if (container && container !== target && container !== parent) {{
                    suggestions.container = {{
                        selector: generateSelector(container),
                        text: container.textContent.trim(),
                        type: container.tagName.toLowerCase()
                    }};
                }}

                window['{self.selection_var}'] = {{
                    selector: suggestions.current.selector,
                    text: suggestions.current.text,
                    suggestions: suggestions
                }};

                console.log('ScrapeStudio: Element selected:', window['{self.selection_var}']);
                // We don't disable targeting here, we just set the value and let Python handle it.
            }}

            window.{self.cleanup_func} = function() {{
                console.log('ScrapeStudio: Cleaning up targeting mode.');
                isTargeting = false;
                if (highlightedEl) {{
                    highlightedEl.style.outline = '';
                    highlightedEl.style.backgroundColor = '';
                }}
                tooltip.remove();
                document.removeEventListener('mouseover', onMouseOver, true);
                document.removeEventListener('click', onClick, true);
            }};

            document.addEventListener('mouseover', onMouseOver, true);
            document.addEventListener('click', onClick, true);
        }})();
        """

    def enable_selector_mode(self):
        """Injects JS and starts polling for selections."""
        if self.targeting_active: return
        print("ScrapeStudio Browser: Enabling selector mode.")
        self.targeting_active = True
        self.page().runJavaScript(f"window['{self.selection_var}'] = null;")  # Clear previous selection
        self.page().runJavaScript(self._get_targeting_js())
        self.poll_timer.start(500)  # Check for a selection every 500ms

    def disable_selector_mode(self):
        """Removes JS listeners and stops polling."""
        if not self.targeting_active: return
        print("ScrapeStudio Browser: Disabling selector mode.")
        self.targeting_active = False
        self.poll_timer.stop()
        self.page().runJavaScript(f"if (window.{self.cleanup_func}) window.{self.cleanup_func}();")

    def check_for_selection(self):
        """Called by QTimer to check for a selection from the web page."""
        if not self.targeting_active: return

        js_to_check = f"JSON.stringify(window['{self.selection_var}'] || null);"

        def callback(result_json_str):
            if result_json_str and result_json_str != "null":
                print(f"ScrapeStudio Browser: Python received selection: {result_json_str[:200]}...")
                try:
                    data = json.loads(result_json_str)
                    if data and data.get('selector'):
                        # Important: Clear the JS variable so we don't process it again
                        self.page().runJavaScript(f"window['{self.selection_var}'] = null;")
                        self.element_selected.emit(data['selector'], data['text'], data['suggestions'])
                except (json.JSONDecodeError, Exception) as e:
                    print(f"ScrapeStudio Browser: Error processing selection JSON: {e}")

        self.page().runJavaScript(js_to_check, callback)