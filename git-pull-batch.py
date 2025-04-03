# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "gitpython",
# ]
# ///
import git

from pathlib import Path


def does_repo_exist(content: list[Path]) -> bool:
    return any(".git" == path.name for path in content if path.is_dir())


def pull_all_repos(current: Path) -> None:
    path_contents = [path for path in current.iterdir() if path.is_dir()]
    if does_repo_exist(path_contents):
        git_repo = git.cmd.Git(current)
        git_repo.status()
        try:
            git_repo.pull()
            print(f"Pulled {current.name}")
        except Exception as e:
            print(f"Failed to pull {current.name}: {e}")
    else:
        for path in path_contents:
            if path.is_file():
                continue
            pull_all_repos(path)


if __name__ == "__main__":
    fiel_path = Path(__file__)
    pull_all_repos(fiel_path.parent)
