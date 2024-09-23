import argparse
from typing import Optional, List, Dict, Union

import omegaup.api
import sys
import os
import math
import mosspy
from template.template import generate_website
from terminal import with_color, BColor

from util import get_credentials_from_file, print_table

omegaup_lang_extension = {
    "c11-clang": ".c",
    "c11-gcc": ".c",
    "cpp11-clang": ".cpp",
    "cpp11-gcc": ".cpp",
    "cpp17-clang": ".cpp",
    "cpp17-gcc": ".cpp",
    "cpp20-clang": ".cpp",
    "cpp20-gcc": ".cpp",
    "cs": ".cs",
    "java": ".java",
    "kj": ".java",
    "kp": ".pascal",
    "py2": ".py",
    "py3": ".py",
}

lang_extension_to_moss = {
    ".c": "c",
    ".cpp": "cc",
    ".cs": "csharp#",
    ".py": "python",
    ".java": "java",
    ".pascal": "pascal",
    ".txt": "ascii",
}


def _choose_contest_interactively(contest_class: omegaup.api.Contest) -> str:
    contests = contest_class.adminList()

    columns = []
    for idx, contest in enumerate(contests.contests):
        columns.append([str(idx), contest.alias])

    print("\nPlease select a a contest:")
    print_table(columns)
    contest_idx = int(input("Enter the contest number: "))

    if contest_idx < 0 or contest_idx >= len(contests.contests):
        print("Invalid contest number")
        sys.exit(1)

    return contests.contests[contest_idx].alias


def _choose_problems_interactively(problems: omegaup.api.ContestProblemsResponse) -> List[str]:
    columns = [[0, "all"]]

    for idx, problem in enumerate(problems.problems):
        columns.append([str(idx + 1), problem.alias])

    print("\nPlease select a problem:")

    print_table(columns)

    problem_idx = int(input("Enter the problem number: "))

    if problem_idx < 0 or problem_idx >= len(problems.problems) + 1:
        print("Invalid problem number")
        sys.exit(1)

    if problem_idx == 0:
        # return an array of problem aliases
        return [problem.alias for problem in problems.problems]
    return [problems.problems[problem_idx - 1].alias]


def _get_runs_by_username_for_problem(
        contest_class: omegaup.api.Contest,
        run_class: omegaup.api.Run,
        contest_alias: str,
        problem_alias: str,
) -> Dict[str, List[Dict[str, Union[float, str]]]]:
    runs = contest_class.runs(contest_alias=contest_alias, problem_alias=problem_alias)

    print(with_color(f"\nGetting runs from problem: {problem_alias}", BColor.BOLD))
    runs_by_username = {}
    for run in runs.runs:
        if run.username not in runs_by_username:
            runs_by_username[run.username] = []
        runs_by_username[run.username].append(
            {
                "run_alias": run.guid,
                "problem_alias": run.alias,
                "language": run.language,
                "score": run.score,
                "verdict": run.verdict,
                "source": _get_source_from_run(run_class, run.guid),
            }
        )
    print(f"Obtained {len(runs.runs)} runs")
    return runs_by_username


def _get_source_from_run(run_class, run_alias: str) -> str:
    source = run_class.source(run_alias=run_alias)
    return source.source


def _save_source_code(runs_by_username: Dict[str, List[Dict[str, Union[float, str]]]], problem_alias: str) -> None:
    print("\nSaving source code locally...")

    for username, runs in runs_by_username.items():
        path = os.path.join("generated", problem_alias, username)
        os.makedirs(path, exist_ok=True)

        runs.reverse()  # reverse to get the latest run first
        for idx, run in enumerate(runs):
            language = run["language"]
            score = math.floor(run["score"] * 100)
            extension = ".txt"

            for lang, ext in omegaup_lang_extension.items():
                if language.startswith(lang):
                    extension = ext
            if extension == ".txt":
                print(with_color(f"WARNING: extension for language {language} not found", BColor.WARNING))

            file_name = (
                f"{idx}_{username}_{problem_alias}_{run['verdict']}_{score}{extension}"
            )
            with open(os.path.join(path, file_name), "w") as f:
                f.write(run["source"])

    print("Problems saved! Please check the generated folder")


def _check_plagiarism(moss_user_id: str, problem_aliases: List[str], name_by_username: Dict[str, str]) -> None:
    print("Sending information to Moss. Please be patient...")

    os.makedirs("submission", exist_ok=True)
    html_paths = []
    for problem_alias in problem_aliases:
        for ext, moss_lang in lang_extension_to_moss.items():
            m = mosspy.Moss(moss_user_id, moss_lang)
            m.addFilesByWildcard(os.path.join("generated", problem_alias, "*", f"*{ext}"))
            if len(m.files) == 0:
                continue

            url = m.send(lambda file_path, display_name: print("*", end="", flush=True))

            print()
            print(with_color(f"OK: {moss_lang}", BColor.OK_GREEN))
            print(f"Unfiltered Online Report (May contain duplicates): {with_color(url, BColor.OK_CYAN)}")

            # Save report file
            report_path = os.path.join(
                "submission", f"{problem_alias}_{moss_lang}_unfiltered_report.html"
            )
            filtered_report_path = os.path.join(
                "submission", f"{problem_alias}_{moss_lang}_filtered_report.html"
            )
            print("The unfiltered report has been saved locally inside: ", report_path)
            m.saveWebPage(url, report_path)

            _remove_same_user_matches(report_path, filtered_report_path, problem_alias)
            html_paths.append(
                {
                    "problem_alias": problem_alias,
                    "lang": moss_lang,
                    "html": filtered_report_path,
                },
            )
    generate_website(html_paths, name_by_username)


def _remove_same_user_matches(report_path: str, filtered_report_path: str, problem_alias: str) -> None:
    with open(report_path, "r") as f:
        lines = f.readlines()

    with open(filtered_report_path, "w") as f:
        idx = 0
        while idx < len(lines) - 2:
            line = lines[idx]
            next_line = lines[idx + 1]
            if line.startswith("<TR><TD>"):
                first_line_user = _get_user_from_html_line(line, problem_alias)
                second_line_user = _get_user_from_html_line(next_line, problem_alias)
                if first_line_user != second_line_user:
                    f.write(line)
                    f.write(next_line)
                    f.write(lines[idx + 2])  # align table line
                idx += 2
            else:
                f.write(line)
            idx += 1
    print(f"--- The filtered report has been saved locally inside: {filtered_report_path}")


def _get_user_from_html_line(line: str, problem_alias: str) -> str:
    search_index = line.index(problem_alias) + len(problem_alias) + 1
    # Now find the user
    user_index = line.index("/", search_index)
    return line[search_index:user_index]


def _main(contest_alias: Optional[str], problem_alias: Optional[str]) -> None:
    username, password, moss_user_id = get_credentials_from_file("login.txt")

    client_class = omegaup.api.Client(username=username, password=password)
    contest_class = omegaup.api.Contest(client=client_class)
    run_class = omegaup.api.Run(client=client_class)

    contest_alias = contest_alias if contest_alias else _choose_contest_interactively(contest_class)
    problems = contest_class.problems(contest_alias=contest_alias)
    if problem_alias == "all":
        problem_aliases = [problem.alias for problem in problems.problems]
    elif problem_alias:
        problem_aliases = [problem_alias]
    else:
        problem_aliases = _choose_problems_interactively(problems)

    name_by_username = {
        contestant.username: contestant.name
        for contestant in contest_class.scoreboard(contest_alias=contest_alias).ranking
    }

    print(f"Getting the code of all runs for {len(problem_aliases)} problems for contest {contest_alias}")
    for problem_alias in problem_aliases:
        runs_by_username = _get_runs_by_username_for_problem(
            contest_class, run_class, contest_alias, problem_alias
        )
        _save_source_code(runs_by_username, problem_alias)

    _check_plagiarism(moss_user_id, problem_aliases, name_by_username)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="moss", description="Check code plagiarism in omegaUp via Moss")
    parser.add_argument("-c", "--contest", help="Contest alias to check")
    parser.add_argument("-p", "--problem", help="Problem alias to check, use 'all' for all contest problems")
    args = parser.parse_args()

    _main(contest_alias=args.contest, problem_alias=args.problem)
