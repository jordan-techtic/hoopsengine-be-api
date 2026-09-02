"""Extract all API endpoints from FastAPI OpenAPI schema."""
from app.main import app

paths = sorted(app.openapi()["paths"].items())
methods_count = 0
for path, methods in paths:
    for m in methods:
        if m in ("get", "post", "put", "patch", "delete", "head", "options"):
            methods_count += 1

print(f"Total paths: {len(paths)}")
print(f"Total operations: {methods_count}")
print("---")
for path, methods in paths:
    for m in sorted(methods.keys()):
        if m in ("get", "post", "put", "patch", "delete"):
            op = methods[m]
            tags = op.get("tags", [""])
            summary = op.get("summary", op.get("operationId", ""))
            tag = tags[0] if tags else ""
            print(f"{m.upper():6} {path:70} | {tag:30} | {summary}")
