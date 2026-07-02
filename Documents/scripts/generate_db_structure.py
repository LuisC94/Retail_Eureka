import os
import django
from django.apps import apps
from django.db.models import ForeignKey, OneToOneField, ManyToManyField

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

mermaid_lines = ["erDiagram"]

for app_config in apps.get_app_configs():
    # Only include dashboard and core (or specific models) to avoid django auth if we want, or just include all.
    # We will exclude django built-in apps if they make diagram too noisy, but it's fine for now.
    if app_config.name not in ['dashboard', 'core', 'auth']:
        continue
        
    for model in app_config.get_models():
        model_name = model.__name__
        mermaid_lines.append(f"    {model_name} {{")
        
        relationships = []
        
        for field in model._meta.get_fields():
            if field.is_relation and field.many_to_one:
                if hasattr(field, 'related_model') and field.related_model:
                    related_name = field.related_model.__name__
                    relationships.append(f"    {related_name} ||--o{{ {model_name} : \"{field.name}\"")
                field_type = "ForeignKey"
                mermaid_lines.append(f"        {field_type} {field.name}")
            elif field.is_relation and field.one_to_one:
                if hasattr(field, 'related_model') and field.related_model:
                    related_name = field.related_model.__name__
                    relationships.append(f"    {related_name} ||--|| {model_name} : \"{field.name}\"")
                field_type = "OneToOne"
                mermaid_lines.append(f"        {field_type} {field.name}")
            elif field.is_relation and field.many_to_many:
                if hasattr(field, 'related_model') and field.related_model:
                    related_name = field.related_model.__name__
                    relationships.append(f"    {model_name} }}o--o{{ {related_name} : \"{field.name}\"")
                field_type = "ManyToMany"
                mermaid_lines.append(f"        {field_type} {field.name}")
            else:
                field_type = field.get_internal_type() if hasattr(field, 'get_internal_type') else type(field).__name__
                mermaid_lines.append(f"        {field_type} {field.name}")
                
        mermaid_lines.append("    }")
        
        for rel in relationships:
            mermaid_lines.append(rel)

# Write to file
with open('db_diagram_utf8.mermaid', 'w', encoding='utf-8') as f:
    f.write("\n".join(mermaid_lines))
