import os
import re

def replace_in_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        content = re.sub(old, new, content)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

replacements = [
    # database and models
    (r'from database import (get_db|engine|Base|SessionLocal)', r'from app.database import \1'),
    (r'from database import ([a-zA-Z0-9_,\s]+)', r'from app.models import \1'),
    (r'import database', r'from app import database, models'),
    
    # auth
    (r'from auth import ', r'from app.auth import '),
    
    # schemas
    (r'from schemas import ', r'from app.schemas import '),
    
    # budget_engine
    (r'from budget_engine import ', r'from app.services.budget_engine import '),
    
    # pdf_generator
    (r'from pdf_generator import ', r'from app.services.pdf_generator import '),
    
    # routers
    (r'import user_routes, admin_routes', r'from app.routers import user_routes, admin_routes'),
    (r'import user_routes', r'from app.routers import user_routes'),
    (r'import admin_routes', r'from app.routers import admin_routes'),
]

# We also need to fix `from database import get_db, User, ...` which is tricky because get_db is in database, User in models
# Let's run a more specific replacement for that
def fix_database_imports(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    def replacer(match):
        imports = [i.strip() for i in match.group(1).split(',')]
        db_imports = []
        model_imports = []
        for i in imports:
            if i in ['get_db', 'engine', 'Base', 'SessionLocal', 'init_db']:
                db_imports.append(i)
            else:
                model_imports.append(i)
        
        res = []
        if db_imports:
            res.append(f"from app.database import {', '.join(db_imports)}")
        if model_imports:
            res.append(f"from app.models import {', '.join(model_imports)}")
        return "\n".join(res)
        
    content = re.sub(r'from database import ([a-zA-Z0-9_,\s]+)', replacer, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for root, dirs, files in os.walk('.'):
    if 'venv' in root or '.git' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py') and file != 'refactor.py':
            path = os.path.join(root, file)
            fix_database_imports(path)
            replace_in_file(path, replacements)

print("Refactoring complete.")
