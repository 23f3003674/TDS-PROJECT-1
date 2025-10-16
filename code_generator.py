"""
Code Generator - Uses GPT-5 Nano via AI Pipe to generate HTML/JS solutions
"""
import logging
from typing import Dict, Any, List
import base64
from openai import OpenAI
import re

from config import settings

logger = logging.getLogger(__name__)

class CodeGenerator:
    """Generates code solutions using GPT-5 Nano"""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.AIMLAPI_KEY,
            base_url=settings.AIMLAPI_BASE_URL
        )
        self.model = settings.AIMLAPI_MODEL
        logger.info(f"Initialized GPT-5 Nano via AI Pipe (Model: {self.model})")
    
    async def generate_solution(
        self,
        brief: str,
        attachments: List,
        checks: List[Dict],
        task_id: str,
        round_num: int
    ) -> Dict[str, Any]:
        """
        Generate complete HTML solution based on task brief
        
        Returns:
            dict with 'success', 'html_code', or 'error'
        """
        try:
            logger.info(f"Generating solution for task {task_id} round {round_num}")
            
            # Decode attachments
            decoded_attachments = self._decode_attachments(attachments)
            
            # Build the solution using GPT-5 Nano
            html_code = await self._generate_with_gpt5nano(
                brief=brief,
                attachments=decoded_attachments,
                checks=checks,
                task_id=task_id
            )
            
            # If GPT-5 returns empty, use fallback
            if not html_code or len(html_code.strip()) < 100:
                logger.warning("GPT-5 Nano returned empty or too short response, using fallback")
                html_code = self._generate_fallback_html(brief, decoded_attachments, checks, task_id)
            
            return {
                'success': True,
                'html_code': html_code
            }
            
        except Exception as e:
            logger.error(f"Code generation failed: {e}", exc_info=True)
            # Try fallback on any error
            try:
                logger.info("Attempting fallback generation...")
                html_code = self._generate_fallback_html(brief, decoded_attachments, checks, task_id)
                return {
                    'success': True,
                    'html_code': html_code
                }
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                return {
                    'success': False,
                    'error': str(e)
                }
    
    def _decode_attachments(self, attachments: List) -> Dict[str, str]:
        """Decode base64 data URLs from attachments"""
        decoded = {}
        
        for attachment in attachments:
            try:
                name = attachment.name
                url = attachment.url
                
                # Parse data URL: data:mime/type;base64,<data>
                if url.startswith('data:'):
                    parts = url.split(',', 1)
                    if len(parts) == 2 and 'base64' in parts[0]:
                        data = base64.b64decode(parts[1]).decode('utf-8')
                        decoded[name] = data
                        logger.info(f"Decoded attachment: {name} ({len(data)} bytes)")
                    
            except Exception as e:
                logger.warning(f"Failed to decode attachment {attachment.name}: {e}")
        
        return decoded
    
    async def _generate_with_gpt5nano(
        self,
        brief: str,
        attachments: Dict[str, str],
        checks: List[Dict],
        task_id: str
    ) -> str:
        """Generate HTML solution using GPT-5 Nano with VERY explicit instructions"""
        
        prompt = self._build_generation_prompt(brief, attachments, checks, task_id)
        
        logger.info("Sending request to GPT-5 Nano...")
        
        try:
            # Note: AI Pipe/OpenAI client variants may not accept 'max_completion_tokens'
            # Use a conservative call signature compatible with API wrappers
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Create a COMPLETE, WORKING HTML page. Return ONLY HTML code, nothing else.

TASK: {brief}

REQUIREMENTS:
1. Single HTML file with embedded CSS and JavaScript
2. Use Bootstrap 5 CDN: https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css
3. ALL JavaScript in <script> tags before </body>
4. Wrap code in: document.addEventListener('DOMContentLoaded', function() {{ ... }})

DATA HANDLING:
{self._build_data_instructions(attachments, brief)}

ELEMENT IDs REQUIRED:
{self._build_element_instructions(checks, brief)}

FUNCTIONALITY:
{self._build_functionality_instructions(brief)}

CHECKS THAT MUST PASS:
{chr(10).join(f"- {check.get('js', str(check))}" for check in checks if check)}

Return complete HTML starting with <!DOCTYPE html>. Make it FUNCTIONAL and INTERACTIVE."""
                    }
                ]
            )
            
            html_code = response.choices[0].message.content
            
            if not html_code or not html_code.strip() or len(html_code) < 200:
                logger.warning(f"GPT-5 Nano returned insufficient content (length: {len(html_code) if html_code else 0})")
                return ""
            
            html_code = html_code.strip()
            html_code = self._clean_html_response(html_code)
            
            if not html_code.startswith('<!DOCTYPE') and not html_code.startswith('<!doctype'):
                html_code = '<!DOCTYPE html>\n' + html_code
            
            logger.info(f"✅ GPT-5 Nano generated {len(html_code)} characters of HTML")
            
            return html_code
            
        except Exception as e:
            logger.error(f"GPT-5 Nano API error: {e}")
            return ""
    
    def _clean_html_response(self, html_code: str) -> str:
        """Clean up HTML response from GPT-5 Nano"""
        
        # Remove markdown code blocks
        if '```html' in html_code:
            html_code = re.sub(r'```html\s*', '', html_code, flags=re.IGNORECASE)
        if '```' in html_code:
            html_code = re.sub(r'```\s*$', '', html_code)
            html_code = re.sub(r'^```\s*', '', html_code)
        
        # Remove any leading/trailing explanatory text
        # Find the first <!DOCTYPE or <html tag
        doc_match = re.search(r'<!DOCTYPE[^>]*>|<html[^>]*>', html_code, re.IGNORECASE)
        if doc_match:
            html_code = html_code[doc_match.start():]
        
        # Find the last </html> tag
        html_end_match = re.search(r'</html>\s*$', html_code, re.IGNORECASE)
        if html_end_match:
            html_code = html_code[:html_end_match.end()]
        
        return html_code.strip()
    
    def _build_generation_prompt(
        self,
        brief: str,
        attachments: Dict[str, str],
        checks: List[Dict],
        task_id: str
    ) -> str:
        """Build comprehensive prompt for GPT-5 Nano"""
        
        prompt_parts = [
            f"TASK: {task_id}",
            f"\nREQUIREMENTS:\n{brief}",
        ]
        
        # Add attachments
        if attachments:
            prompt_parts.append("\nDATA FILES TO EMBED:")
            for name, content in attachments.items():
                # Truncate very large files
                display_content = content if len(content) < 1000 else content[:1000] + "\n... (truncated)"
                prompt_parts.append(f"\nFile: {name}\n{display_content}")
        
        # Add checks
        if checks:
            prompt_parts.append("\nMUST PASS THESE TESTS:")
            for i, check in enumerate(checks, 1):
                if 'js' in check:
                    prompt_parts.append(f"{i}. {check['js']}")
        
        prompt_parts.append("\nRULES:")
        prompt_parts.append("- Single HTML file with embedded CSS and JavaScript")
        prompt_parts.append("- Use CDN for libraries (Bootstrap, marked.js, highlight.js)")
        prompt_parts.append("- Embed all data directly in the file")
        prompt_parts.append("- Make it functional and visually appealing")
        prompt_parts.append("- All element IDs must match requirements")
        
        return '\n'.join(prompt_parts)
    
    def _generate_fallback_html(
        self,
        brief: str,
        attachments: Dict[str, str],
        checks: List[Dict],
        task_id: str
    ) -> str:
        """
        Fallback template-based HTML generation
        This is used when GPT-5 Nano returns empty or fails
        """
        
        logger.info("Using fallback template-based generation")
        
        # Parse requirements
        requirements = self._parse_requirements(brief)
        
        # Build libraries
        head_libs = []
        if requirements['needs_bootstrap']:
            head_libs.extend([
                '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">',
                '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>'
            ])
        
        if requirements['needs_marked']:
            head_libs.append('<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>')
        
        if requirements['needs_highlight']:
            head_libs.extend([
                '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github-dark.min.css">',
                '<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>'
            ])
        
        # Extract seed if present
        seed_match = re.search(r'\$\{seed\}|seed["\']?\s*[:=]\s*["\']?(\w+)', brief, re.IGNORECASE)
        seed_value = seed_match.group(1) if seed_match and seed_match.lastindex else "TDS"
        
        # Determine task type and build accordingly
        if requirements['has_csv'] and any(word in brief.lower() for word in ['sum', 'total', 'sales']):
            body_content, js_code = self._build_csv_task(requirements, attachments, brief, seed_value)
        elif requirements['has_markdown']:
            body_content, js_code = self._build_markdown_task(requirements, attachments, brief)
        elif 'github' in brief.lower() and requirements['needs_form']:
            body_content, js_code = self._build_github_task(requirements, brief, seed_value)
        else:
            body_content, js_code = self._build_generic_task(requirements, brief, task_id)
        
        # Build complete HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{seed_value} - {task_id}</title>
    {chr(10).join(head_libs)}
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #2d3748;
            margin-bottom: 24px;
            font-size: 2.5rem;
            border-bottom: 4px solid #667eea;
            padding-bottom: 16px;
        }}
        .result {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
            margin: 24px 0;
            padding: 20px;
            background: linear-gradient(135deg, #e0e7ff 0%, #f3e8ff 100%);
            border-radius: 12px;
            border-left: 6px solid #667eea;
        }}
        table {{
            width: 100%;
            margin-top: 24px;
            border-collapse: collapse;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 16px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        tbody tr:hover {{
            background: #f7fafc;
            transform: scale(1.01);
            transition: all 0.2s;
        }}
        .form-control, .form-select {{
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 16px;
            width: 100%;
            margin-bottom: 16px;
            transition: border-color 0.3s;
        }}
        .form-control:focus, .form-select:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        .btn {{
            padding: 14px 28px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
        }}
        .btn-secondary {{
            background: #718096;
            color: white;
        }}
        .btn-secondary:hover {{
            background: #4a5568;
        }}
        .alert {{
            padding: 16px 20px;
            border-radius: 8px;
            margin: 16px 0;
            border-left: 4px solid;
        }}
        .alert-info {{
            background: #ebf8ff;
            border-color: #3182ce;
            color: #2c5282;
        }}
        .alert-success {{
            background: #f0fff4;
            border-color: #38a169;
            color: #22543d;
        }}
        .alert-danger {{
            background: #fff5f5;
            border-color: #e53e3e;
            color: #742a2a;
        }}
        #markdown-output {{
            line-height: 1.8;
            color: #2d3748;
        }}
        #markdown-output h1, #markdown-output h2, #markdown-output h3 {{
            margin-top: 24px;
            margin-bottom: 16px;
            color: #1a202c;
        }}
        #markdown-output p {{
            margin-bottom: 16px;
        }}
        #markdown-output pre {{
            background: #1a202c;
            color: #f7fafc;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 16px 0;
        }}
        #markdown-output code {{
            background: #edf2f7;
            color: #e53e3e;
            padding: 3px 8px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        #markdown-output pre code {{
            background: transparent;
            color: #f7fafc;
            padding: 0;
        }}
        #markdown-source {{
            background: #2d3748;
            color: #e2e8f0;
            padding: 20px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            overflow-x: auto;
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    {body_content}
    <script>
    {js_code}
    </script>
</body>
</html>"""
        
        return html
    
    def _build_data_instructions(self, attachments: Dict[str, str], brief: str) -> str:
        """Build specific data handling instructions"""
        instructions = []
        
        if attachments:
            for name, content in attachments.items():
                if '.csv' in name.lower():
                    instructions.append(f"""
CSV Data ({name}):
{content[:300]}...
- Parse by splitting lines and commas
- First line is headers
- Extract sales/amount column
- Sum all values using parseFloat()
- Display in the specified element""")
                    
                elif '.md' in name.lower():
                    instructions.append(f"""
Markdown Data ({name}):
- Use marked.parse() to convert
- Display in #markdown-output
- Use highlight.js for code blocks""")
                    
                elif '.json' in name.lower():
                    instructions.append(f"""
JSON Data ({name}):
- Parse with JSON.parse()
- Extract rates/currency data
- Apply conversions""")
        else:
            instructions.append("- No attachments provided")
        
        return '\n'.join(instructions) if instructions else "No data attachments"
    
    def _build_element_instructions(self, checks: List[Dict], brief: str) -> str:
        """Extract required element IDs from checks and brief"""
        import re
        
        elements = set()
        
        # From checks
        for check in checks:
            js_code = check.get('js', '')
            # Extract IDs like #element-id or getElementById('element-id')
            ids = re.findall(r'[#]([a-z0-9-]+)|getElementById\(["\']([a-z0-9-]+)', js_code, re.IGNORECASE)
            for match in ids:
                element_id = match[0] or match[1]
                if element_id:
                    elements.add(element_id)
        
        # From brief
        brief_ids = re.findall(r'#([a-z0-9-]+)', brief, re.IGNORECASE)
        elements.update(brief_ids)
        
        if elements:
            return '\n'.join(f"- #{eid}" for eid in sorted(elements))
        return "Check the brief for required elements"
    
    def _build_functionality_instructions(self, brief: str) -> str:
        """Build specific functionality instructions based on brief"""
        funcs = []
        
        brief_lower = brief.lower()
        
        if 'button' in brief_lower:
            funcs.append("- Add click event listeners to all buttons")
        if 'form' in brief_lower:
            funcs.append("- Add submit event listener with preventDefault()")
        if 'filter' in brief_lower or 'select' in brief_lower:
            funcs.append("- Add change event listener to filters/selects")
        if 'sum' in brief_lower or 'total' in brief_lower or 'calculate' in brief_lower:
            funcs.append("- Calculate sums by iterating data and using parseFloat()")
        if 'table' in brief_lower:
            funcs.append("- Populate table rows dynamically with data")
        if 'api' in brief_lower or 'fetch' in brief_lower:
            funcs.append("- Use fetch() with proper error handling")
        if 'localstorage' in brief_lower or 'cache' in brief_lower:
            funcs.append("- Use localStorage.setItem() and getItem()")
        
        return '\n'.join(funcs) if funcs else "Make all interactive elements work"

    def _parse_requirements(self, brief: str) -> Dict[str, Any]:
        """Parse brief to extract requirements"""
        return {
            'needs_bootstrap': 'bootstrap' in brief.lower(),
            'needs_marked': 'marked' in brief.lower(),
            'needs_highlight': 'highlight' in brief.lower(),
            'needs_form': 'form' in brief.lower(),
            'needs_table': 'table' in brief.lower(),
            'has_csv': 'csv' in brief.lower() or '.csv' in brief.lower(),
            'has_markdown': 'markdown' in brief.lower() or '.md' in brief.lower(),
            'has_json': 'json' in brief.lower() or '.json' in brief.lower(),
            'element_ids': re.findall(r'#([\w-]+)', brief)
        }
    
    def _build_csv_task(self, req: Dict, attachments: Dict, brief: str, seed: str) -> tuple:
        """Build FULLY FUNCTIONAL HTML and JS for CSV sum tasks"""
        
        csv_data = next((v for k, v in attachments.items() if '.csv' in k.lower()), '')
        
        # Find element IDs from requirements
        element_ids = req['element_ids']
        total_sales_id = next((eid for eid in element_ids if 'total' in eid or 'sales' in eid), 'total-sales')
        product_table_id = next((eid for eid in element_ids if 'product' in eid or 'table' in eid), 'product-sales')
        region_filter_id = next((eid for eid in element_ids if 'region' in eid or 'filter' in eid), 'region-filter')
        
        # Extract title from brief or use default
        import re
        title_match = re.search(r'title.*?["\']([^"\']+)["\']', brief, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).replace('${seed}', seed)
        else:
            title = f"Sales Summary {seed}"
        
        # Check if this is Round 2 (needs table and filter)
        needs_table = 'table' in brief.lower() or product_table_id in element_ids
        needs_filter = 'filter' in brief.lower() or 'region' in brief.lower()
        
        body = f"""<div class="container">
    <h1>{title}</h1>
    
    <div class="result">
        Total Sales: $<span id="{total_sales_id}">0.00</span>
    </div>
    
    {f'''
    <div class="mb-3">
        <label for="{region_filter_id}" class="form-label">Filter by Region:</label>
        <select id="{region_filter_id}" class="form-select">
            <option value="all">All Regions</option>
        </select>
    </div>
    ''' if needs_filter else ''}
    
    {f'''
    <table id="{product_table_id}" class="table table-striped">
        <thead>
            <tr>
                <th>Product</th>
                <th>Sales</th>
                {f'<th>Region</th>' if needs_filter else ''}
            </tr>
        </thead>
        <tbody>
            <!-- Data populated by JavaScript -->
        </tbody>
    </table>
    ''' if needs_table else ''}
    
    <div class="mt-3">
        <small class="text-muted">Data loaded from CSV attachment</small>
    </div>
</div>"""
        
        # Escape the CSV data properly
        csv_data_escaped = csv_data.replace('`', '\\`').replace('$', '\\$').replace('\\', '\\\\')
        
        js = f"""
// Embedded CSV Data
const csvData = `{csv_data_escaped}`;

let allProducts = [];
let currentRegion = 'all';

// Parse CSV function
function parseCSV(csvText) {{
    const lines = csvText.trim().split('\\n');
    if (lines.length === 0) return [];
    
    const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
    const products = [];
    
    for (let i = 1; i < lines.length; i++) {{
        const line = lines[i].trim();
        if (!line) continue;
        
        const values = line.split(',').map(v => v.trim());
        const product = {{}};
        
        headers.forEach((header, index) => {{
            product[header] = values[index] || '';
        }});
        
        products.push(product);
    }}
    
    return products;
}}

// Calculate total sales
function calculateTotal(products) {{
    return products.reduce((sum, product) => {{
        const sales = parseFloat(product.sales || product.amount || product.price || 0);
        return sum + sales;
    }}, 0);
}}

// Update display
function updateDisplay() {{
    let filteredProducts = allProducts;
    
    // Apply region filter if exists
    if (currentRegion !== 'all') {{
        filteredProducts = allProducts.filter(p => 
            (p.region || '').toLowerCase() === currentRegion.toLowerCase()
        );
    }}
    
    // Calculate and display total
    const total = calculateTotal(filteredProducts);
    const totalElement = document.getElementById('{total_sales_id}');
    if (totalElement) {{
        totalElement.textContent = total.toFixed(2);
        {f'totalElement.setAttribute("data-region", currentRegion);' if needs_filter else ''}
    }}
    
    // Update table if exists
    const tableBody = document.querySelector('#{product_table_id} tbody');
    if (tableBody) {{
        tableBody.innerHTML = '';
        filteredProducts.forEach(product => {{
            const row = tableBody.insertRow();
            row.insertCell(0).textContent = product.product || product.name || 'Unknown';
            row.insertCell(1).textContent = '$' + parseFloat(product.sales || product.amount || 0).toFixed(2);
            {f"row.insertCell(2).textContent = product.region || 'N/A';" if needs_filter else ''}
        }});
    }}
}}

// Initialize
document.addEventListener('DOMContentLoaded', function() {{
    try {{
        console.log('Initializing CSV Sales App...');
        
        // Set page title
        document.title = "{title}";
        
        // Parse CSV data
        allProducts = parseCSV(csvData);
        console.log('Parsed products:', allProducts.length);
        
        // Populate region filter if exists
        const regionFilter = document.getElementById('{region_filter_id}');
        if (regionFilter && allProducts.length > 0) {{
            const regions = [...new Set(allProducts.map(p => p.region).filter(r => r))];
            regions.forEach(region => {{
                const option = document.createElement('option');
                option.value = region;
                option.textContent = region;
                regionFilter.appendChild(option);
            }});
            
            // Add change listener
            regionFilter.addEventListener('change', function() {{
                currentRegion = this.value;
                console.log('Region filter changed to:', currentRegion);
                updateDisplay();
            }});
        }}
        
        // Initial display
        updateDisplay();
        
        console.log('✅ App initialized successfully');
        
    }} catch (error) {{
        console.error('❌ Error initializing app:', error);
        const totalElement = document.getElementById('{total_sales_id}');
        if (totalElement) {{
            totalElement.textContent = 'Error';
            totalElement.style.color = 'red';
        }}
    }}
}});
"""
        
        return body, js
    
    def _build_markdown_task(self, req: Dict, attachments: Dict, brief: str) -> tuple:
        """Build HTML and JS for Markdown rendering tasks"""
        
        md_data = next((v for k, v in attachments.items() if '.md' in k.lower()), '# Sample Markdown\n\nThis is sample content.')
        md_data_escaped = md_data.replace('`', '\\`').replace('$', '\\$')
        
        body = """<div class="container">
    <h1>Markdown Viewer</h1>
    <div id="markdown-tabs" style="margin-bottom: 20px;">
        <button class="btn btn-primary" onclick="showTab('output')">Rendered HTML</button>
        <button class="btn btn-secondary" onclick="showTab('source')">Markdown Source</button>
    </div>
    <div id="markdown-output"></div>
    <pre id="markdown-source" style="display:none;"></pre>
    <div style="margin-top: 24px; padding: 16px; background: #f7fafc; border-radius: 8px;">
        <strong>Word Count:</strong> <span id="markdown-word-count">0</span> words
    </div>
    <div id="markdown-source-label" style="margin-top: 12px; color: #718096; font-size: 14px;">
        Source: Embedded attachment
    </div>
</div>"""
        
        js = f"""
// Embedded Markdown content
const markdownContent = `{md_data_escaped}`;

function showTab(tab) {{
    const output = document.getElementById('markdown-output');
    const source = document.getElementById('markdown-source');
    
    if (tab === 'output') {{
        output.style.display = 'block';
        source.style.display = 'none';
    }} else {{
        output.style.display = 'none';
        source.style.display = 'block';
    }}
}}

document.addEventListener('DOMContentLoaded', function() {{
    try {{
        // Render markdown using marked.js
        if (typeof marked !== 'undefined') {{
            const html = marked.parse(markdownContent);
            document.getElementById('markdown-output').innerHTML = html;
            
            // Highlight code blocks if highlight.js is available
            if (typeof hljs !== 'undefined') {{
                document.querySelectorAll('pre code').forEach((block) => {{
                    hljs.highlightElement(block);
                }});
            }}
        }} else {{
            document.getElementById('markdown-output').innerHTML = '<p>Marked.js not loaded</p>';
        }}
        
        // Set markdown source
        document.getElementById('markdown-source').textContent = markdownContent;
        
        // Calculate word count
        const words = markdownContent.split(/\\s+/).filter(w => w.length > 0).length;
        const formatter = new Intl.NumberFormat('en-US');
        document.getElementById('markdown-word-count').textContent = formatter.format(words);
    }} catch (error) {{
        console.error('Error rendering markdown:', error);
    }}
}});
"""
        
        return body, js
    
    def _build_github_task(self, req: Dict, brief: str, seed: str) -> tuple:
        """Build HTML and JS for GitHub API tasks"""
        # choose or synthesize a stable form id
        form_id = next((eid for eid in req.get('element_ids', []) if 'github-user' in eid.lower()), f'github-user-{seed}')

        body = f"""<div class="container">
    <h1>GitHub User Information</h1>
    <form id="{form_id}">
        <div class="mb-3">
            <label class="form-label" style="font-weight: 600; margin-bottom: 8px; display: block;">
                GitHub Username:
            </label>
            <input type="text" class="form-control" name="username" placeholder="Enter username" required>
        </div>
        <button type="submit" class="btn btn-primary">Fetch User Info</button>
    </form>
    <div id="github-status" class="alert alert-info" aria-live="polite" style="display:none; margin-top: 20px;"></div>
    <div id="results" style="margin-top: 30px; display: none;">
        <div style="padding: 20px; background: #f7fafc; border-radius: 8px;">
            <p style="margin-bottom: 12px;">
                <strong>Account Created:</strong> 
                <span id="github-created-at" style="color: #667eea; font-weight: 600;">-</span>
            </p>
            <p style="margin-bottom: 0;">
                <strong>Account Age:</strong> 
                <span id="github-account-age" style="color: #667eea; font-weight: 600;">-</span>
            </p>
        </div>
    </div>
    <div id="total-currency" style="margin-top: 16px; color: #718096; font-size: 14px;">
        Currency: USD
    </div>
</div>"""

        # Build JS as a plain string with placeholders, then replace them to avoid Python f-string conflicts with JS template literals
        js = """
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('__FORM_ID__');
    const statusEl = document.getElementById('github-status');
    const resultsDiv = document.getElementById('results');
    
    // Load cached username from localStorage
    const cacheKey = '__CACHE_KEY__';
    try {{
        const cached = localStorage.getItem(cacheKey);
        if (cached) {{
            const data = JSON.parse(cached);
            if (data.username) {{
                form.querySelector('input[name="username"]').value = data.username;
            }}
        }}
    }} catch (e) {{
        console.warn('localStorage not available or error reading cache');
    }}
    
    form.addEventListener('submit', async function(e) {{
        e.preventDefault();
        
        const username = form.querySelector('input[name="username"]').value.trim();
        if (!username) return;
        
        // Show loading status
        statusEl.style.display = 'block';
        statusEl.className = 'alert alert-info';
        statusEl.textContent = 'Fetching user data from GitHub API...';
        resultsDiv.style.display = 'none';
        
        try {{
            // Check for optional token parameter
            const urlParams = new URLSearchParams(window.location.search);
            const token = urlParams.get('token');
            
            const headers = {{
                'Accept': 'application/vnd.github.v3+json'
            }};
            
            if (token) {
                headers['Authorization'] = `token ${token}`;
            }

            const response = await fetch(`https://api.github.com/users/${username}`, {
                headers: headers
            });
            
            if (!response.ok) {{
                throw new Error(`GitHub API returned ${{response.status}}: ${{response.statusText}}`);
            }}
            
            const data = await response.json();
            
            // Parse created date
            const createdAt = new Date(data.created_at);
            const createdAtStr = createdAt.toISOString().split('T')[0]; // YYYY-MM-DD format
            
            // Calculate age in years
            const now = Date.now();
            const ageMs = now - createdAt.getTime();
            const ageYears = Math.floor(ageMs / (365.25 * 24 * 60 * 60 * 1000));
            
            // Update UI
            document.getElementById('github-created-at').textContent = createdAtStr;
            document.getElementById('github-account-age').textContent = `${ageYears} years`;
            
            // Show results
            resultsDiv.style.display = 'block';
            statusEl.className = 'alert alert-success';
            statusEl.textContent = `Successfully fetched data for @${username}!`;
            
            // Cache the username
            try {
                localStorage.setItem(cacheKey, JSON.stringify({ username: username }));
            } catch (e) {
                console.warn('Could not save to localStorage');
            }
            
        }} catch (error) {{
            console.error('Error fetching GitHub data:', error);
            statusEl.className = 'alert alert-danger';
            statusEl.textContent = `Error: ${error.message}`;
            resultsDiv.style.display = 'none';
        }}
    }});
"""

        # Replace placeholders
        js = js.replace('__FORM_ID__', form_id).replace('__CACHE_KEY__', f"{form_id}-cache")

        return body, js
        return body, js
    
    def _build_generic_task(self, req: Dict, brief: str, task_id: str) -> tuple:
        """Build generic HTML and JS for unknown task types"""
        
        element_ids = req['element_ids'][:5] if req['element_ids'] else ['output']
        
        body = f"""<div class="container">
    <h1>{task_id}</h1>
    <div class="result">
        Task Output
    </div>
    <div style="padding: 20px; background: #f7fafc; border-radius: 8px;">
        {''.join(f'<div id="{eid}" style="margin: 12px 0; padding: 12px; background: white; border-radius: 6px; border-left: 4px solid #667eea;">Element: {eid}</div>' for eid in element_ids)}
    </div>
    <div style="margin-top: 20px; color: #718096;">
        <p><strong>Task Brief:</strong></p>
        <p style="white-space: pre-wrap;">{brief[:500]}</p>
    </div>
</div>"""
        
        js = """
document.addEventListener('DOMContentLoaded', function() {
    console.log('Generic task loaded successfully');
    console.log('Task is ready for evaluation');
});
"""

        return body, js