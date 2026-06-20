from pathlib import PurePosixPath


def classify_changed_file(path: str) -> list[str]:
    normalized = path.replace("\\", "/").lower()
    path_parts = set(PurePosixPath(normalized).parts)
    categories: list[str] = []

    if normalized.endswith((".tsx", ".jsx", ".css", ".scss")) or "frontend" in path_parts:
        categories.append("ui")

    if any(part in path_parts for part in ["api", "apis", "router", "routers", "route", "routes"]):
        categories.append("api")

    if any(part in path_parts for part in ["model", "models", "migration", "migrations"]):
        categories.append("db")
    if normalized.endswith((".sql", ".sqlite")):
        categories.append("db")

    if any(part in path_parts for part in ["service", "services", "utils", "lib", "shared"]):
        categories.append("logic")

    if not categories:
        categories.append("unknown")

    return list(dict.fromkeys(categories))


def summarize_categories(changed_files: list[str]) -> dict[str, int]:
    summary: dict[str, int] = {}

    for path in changed_files:
        for category in classify_changed_file(path):
            summary[category] = summary.get(category, 0) + 1

    return summary


def recommended_layers(category_summary: dict[str, int]) -> list[str]:
    recommendations: list[str] = []

    if category_summary.get("ui"):
        recommendations.append("ui")
    if category_summary.get("api") or category_summary.get("logic"):
        recommendations.append("api")
    if category_summary.get("db"):
        recommendations.append("db")

    return recommendations
