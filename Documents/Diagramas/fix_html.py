import os

file_path = r'c:\Users\luis.carvalho\OneDrive - Retail Consult\Projetos\Retail_2025\Retail-Eureka\dashboard\templates\dashboard\producerDash.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove duplicated header rows
# We look for the specific sequence of lines
dup_header = """                            <tr>
                                <th>Product</th>

                            </tr>
"""
if dup_header in content:
    print("Found duplicated header, removing...")
    content = content.replace(dup_header, "")
else:
    print("Duplicated header not found exactly as expected.")

# 2. Update Summary Table Body
old_body_row = """                            <tr>
                                <td>{{ item.plantation__product__name }}</td>
                                <td>{{ item.total_kg }}</td>
                            </tr>"""

new_body_row = """                            <tr>
                                <td>{{ item.plantation__product__name }}</td>
                                <td>{{ item.total_kg }}</td>
                                <td>{{ item.delivered_kg|default:"0" }}</td>
                                <td><strong>{{ item.current_stock }}</strong></td>
                            </tr>"""

if old_body_row in content:
    print("Found old summary body, updating...")
    content = content.replace(old_body_row, new_body_row)
else:
    print("Old summary body not found.")

# 3. Update Detailed Records Table Header
old_detailed_header = """                            <tr>
                                <th>Date</th>
                                <th>Product</th>
                                <th>Quantity (Kg)</th>
                            </tr>"""

new_detailed_header = """                            <tr>
                                <th>Date</th>
                                <th>Product</th>
                                <th>Quantity (Kg)</th>
                                <th>Delivered (Kg)</th>
                            </tr>"""

if old_detailed_header in content:
    print("Found old detailed header, updating...")
    content = content.replace(old_detailed_header, new_detailed_header)
else:
    print("Old detailed header not found.")

# 4. Update Detailed Records Table Body
old_detailed_body_row = """                            <tr>
                                <td>{{ record.harvest_date|date:"d-m-Y" }}</td>
                                <td>
                                    {% if record.plantation %}
                                    {{ record.plantation.product.name }}
                                    {% else %}
                                    -
                                    {% endif %}
                                </td>
                                <td>{{ record.harvest_quantity_kg }}</td>
                            </tr>"""

new_detailed_body_row = """                            <tr>
                                <td>{{ record.harvest_date|date:"d-m-Y" }}</td>
                                <td>
                                    {% if record.plantation %}
                                    {{ record.plantation.product.name }}
                                    {% else %}
                                    -
                                    {% endif %}
                                </td>
                                <td>{{ record.harvest_quantity_kg }}</td>
                                <td>{{ record.delivered_quantity_kg|default:"0" }}</td>
                            </tr>"""

if old_detailed_body_row in content:
    print("Found old detailed body, updating...")
    content = content.replace(old_detailed_body_row, new_detailed_body_row)
else:
    print("Old detailed body not found.")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Finished fixing producerDash.html")
