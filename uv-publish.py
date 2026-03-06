import configparser
import os
import subprocess
import sys


def publish_with_uv(index_name: str):
    pypirc = os.path.expanduser("~/.pypirc")
    config = configparser.ConfigParser()
    config.read(pypirc)

    if index_name not in config:
        print(f"Index '{index_name}' not found in ~/.pypirc")
        sys.exit(1)

    repo = config[index_name]
    url = repo.get("repository", "")
    username = repo.get("username", "")
    password = repo.get("password", "")

    if not url or not username or not password:
        print(f"Missing fields in ~/.pypirc for index '{index_name}'")
        sys.exit(1)

    cmd = [
        "uv",
        "publish",
        "--publish-url",
        url,
        "--username",
        username,
        "--password",
        password,
    ]
    safe_cmd = cmd.copy()
    safe_cmd[5] = "********"
    safe_cmd[7] = "********"
    print("Running:", " ".join(safe_cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"Error: uv publish exited with status {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run uv-publish.py <index_name>")
        sys.exit(1)
    index = sys.argv[1]
    publish_with_uv(index)
