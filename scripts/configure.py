"""Create local environment files without overwriting existing credentials."""

import argparse
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def write_env(path: Path, content: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--admin", action="store_true", help="Also create .env.admin for a new database"
    )
    args = parser.parse_args()
    paths = [ROOT / ".env"]
    if args.admin:
        paths.append(ROOT / ".env.admin")
    if any(path.exists() for path in paths):
        parser.error(
            "Environment file already exists; edit it directly to keep existing credentials."
        )
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    content = content.replace("replace-locally", "Aw9!" + secrets.token_urlsafe(32))
    content = content.replace(
        "replace-with-a-random-token-at-least-32-characters", secrets.token_urlsafe(36)
    )
    write_env(paths[0], content)
    if args.admin:
        write_env(
            paths[1],
            "AW_ADMIN_USER=sqldayadmin\nAW_ADMIN_PASSWORD=Aw9!" + secrets.token_urlsafe(32) + "\n",
        )
    print(
        "Created "
        + ", ".join(path.name for path in paths)
        + ". Edit SQL connection settings before use."
    )


if __name__ == "__main__":
    main()
