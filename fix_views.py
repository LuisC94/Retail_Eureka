import os

file_path = r'c:\Users\luis.carvalho\OneDrive - Retail Consult\Projetos\Retail_2025\Retail-Eureka\dashboard\views.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_count = 0
found_first = False

target_line_start = "        harvest_sums = Harvest.objects.filter(producer=user).values("

for i, line in enumerate(lines):
    if skip_count > 0:
        skip_count -= 1
        continue
    
    if line.startswith(target_line_start):
        if found_first:
            # This is the second occurrence (the duplicate), skip it and the next 4 lines
            print(f"Found duplicate at line {i+1}, removing...")
            skip_count = 4 # Skip this line + 4 more = 5 lines total
            continue
        else:
            found_first = True
    
    new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Finished fixing views.py")
