import argparse
import csv
from datetime import timedelta
from typing import Optional, List, Dict, Tuple, Set

import omegaup.api
import sys
import os
import math

from plagiarism import check_plagiarism
from template.template import generate_website
from terminal import with_color, BColor
from cpc_types import SuspiciousActivity

from util import get_credentials_from_file, print_table, get_school_name

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


def _download_runs_for_problem(
        run_class: omegaup.api.Run,
        runs_by_username: Dict[str, List[omegaup.api._Run]],
        problem_alias: str,
) -> Dict[str, str]:
    print(f"Saving their source code locally...")
    source_by_run_id = {}
    for username, user_runs in runs_by_username.items():
        path = os.path.join("generated", problem_alias, username)
        os.makedirs(path, exist_ok=True)
        for idx, run in enumerate(user_runs):
            language = run.language
            extension = None
            for lang, ext in omegaup_lang_extension.items():
                if language.startswith(lang):
                    extension = ext
            if not extension:
                print(with_color(f"Extension for language {language} not found", BColor.WARNING))
                extension = ".txt"

            score = math.floor(run.score * 100)
            file_name = (
                f"{idx:02}_{username}_{problem_alias}_{run.verdict}_{score}{extension}"
            )
            file_path = os.path.join(path, file_name)
            if os.path.exists(file_path):
                # Avoid re-downloading, but read the file so it can be set
                with open(file_path) as f:
                    source_by_run_id[run.guid] = "\n".join(f.readlines())
                continue

            source = _get_source_from_run(run_class, run.guid)
            source_by_run_id[run.guid] = source
            with open(file_path, "w") as f:
                f.write(source)

    print("Source code saved!")
    return source_by_run_id


def _get_source_from_run(run_class, run_alias: str) -> str:
    source = run_class.source(run_alias=run_alias)
    return source.source


def _count_comments(source: List[str], language: str) -> Tuple[int, Set[str]]:
    comment_starts = ["#"] if language.startswith("py") else ["//", "/*"]
    count = 0
    matching_lines = set()
    for line in source:
        for comment_start in comment_starts:
            if comment_start in line:
                count += 1
                matching_lines.add(line)
                break
    return count, matching_lines


def _count_accents(source: List[str]) -> Tuple[int, Set[str]]:
    count = 0
    matching_lines = set()
    for line in source:
        for char in line.lower():
            if char in "áéíóú":
                count += 1
                matching_lines.add(line)
    return count, matching_lines


def _count_exceptions(source: List[str]) -> Tuple[int, Set[str]]:
    count = 0
    matching_lines = set()
    for line in source:
        if "Exception" in line or "Error" in line:
            count += 1
            matching_lines.add(line)
            break
    return count, matching_lines


def _check_suspicious_activity(
        runs_by_username: Dict[str, List[omegaup.api._Run]],
        source_by_run_id: Dict[str, str],
        problem_alias: str,
        name_by_username: Dict[str, str],
) -> List[SuspiciousActivity]:
    print(f"Checking suspicious activity for problem {problem_alias}")
    suspicious_activity = []
    for username, runs in runs_by_username.items():
        languages = set()
        previous_run = None
        warnings = set()
        suspicious_lines = set()
        for run in runs:
            source = source_by_run_id[run.guid]
            source_lines = source.split("\n")
            extension = omegaup_lang_extension[run.language]
            languages.add(extension)
            if previous_run:
                previous_extension = omegaup_lang_extension[previous_run.language]
                if extension != previous_extension:
                    time_diff = run.time - previous_run.time
                    if time_diff < timedelta(minutes=15):
                        warnings.add(f"Used different languages within {math.ceil(time_diff.total_seconds() / 60)} minutes")

            comment_count, comment_lines = _count_comments(source_lines, run.language)
            suspicious_lines.update(comment_lines)
            if comment_count > 3:
                warnings.add(f"Code has {comment_count} comments")

            accent_count, accent_lines = _count_accents(source_lines)
            suspicious_lines.update(accent_lines)
            if accent_count > 0:
                warnings.add(f"Code has {accent_count} accents")

            exception_count, exception_lines = _count_exceptions(source_lines)
            suspicious_lines.update(exception_lines)
            if exception_count > 1:
                warnings.add(f"Code has {exception_count} exceptions")

            previous_run = run

        if len(languages) > 1:
            warnings.add(f"Used more than language: {languages}")

        suspicious_lines = {line.strip() for line in suspicious_lines}
        if warnings:
            name = name_by_username.get(username)
            warnings_desc = [f"  - {w}" for w in sorted(warnings)]
            suspicious_activity.append(SuspiciousActivity(
                username=username,
                name=name,
                problem_alias=problem_alias,
                reason="Code might be AI-generated:" + "\n".join(warnings_desc),
                details="\n".join(sorted(suspicious_lines)),
            ))

    return suspicious_activity


def _generate_activity_report(suspicious_activities: List[SuspiciousActivity], file_path: str) -> None:
    print(with_color(f"\nGenerating suspicious activity report at {file_path}", BColor.OK_CYAN))
    activities = sorted(suspicious_activities, key=lambda a: (
        get_school_name(a.display_name), a.display_name, a.problem_alias, a.reason
    ))
    with open(file_path, "w") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            quoting=csv.QUOTE_ALL,
            fieldnames=["School", "Name", "User", "Problem", "Reason", "Details"],
        )
        writer.writeheader()
        for activity in activities:
            writer.writerow({
                "School": get_school_name(activity.display_name),
                "Name": activity.display_name,
                "User": activity.username,
                "Problem": activity.problem_alias,
                "Reason": activity.reason,
                "Details": activity.details,
            })


def _main(
        contest_alias: Optional[str],
        problem_alias: Optional[str],
        should_check_plagiarism: bool,
        min_plagiarism_perc: int,
) -> None:
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
    suspicious_counts = {}
    suspicious_activities: List[SuspiciousActivity] = []
    for problem_alias in problem_aliases:
        print(with_color(f"\nGetting the runs for problem {problem_alias}", BColor.BOLD))
        # TODO: Get runs directly for problem to be able to compare against previous solutions (make it a flag?)
        runs = sorted(
            contest_class.runs(contest_alias=contest_alias, problem_alias=problem_alias).runs,
            # Ensure runs are ordered by submission time
            key=lambda r: r.time,
        )
        runs_by_username = {}
        for run in runs:
            runs_by_username.setdefault(run.username, []).append(run)

        source_by_run_id = _download_runs_for_problem(run_class, runs_by_username, problem_alias)
        suspicious_activities.extend(
            _check_suspicious_activity(runs_by_username, source_by_run_id, problem_alias, name_by_username)
        )

    print()
    if should_check_plagiarism:
        plagiarisms = check_plagiarism(
            moss_user_id,
            problem_aliases,
            min_plagiarism_perc,
            name_by_username,
        )
        for plag in plagiarisms:
            for user_idx in range(2):
                other_user_idx = 1 - user_idx
                suspicious_activities.append(SuspiciousActivity(
                    username=plag.usernames[user_idx],
                    name=plag.display_names[user_idx],
                    problem_alias=plag.problem_alias,
                    reason=f"Code is {plag.similarity_perc}% similar to the code from {plag.display_names[other_user_idx]}",
                    details=plag.results_url,
                ))
    else:
        plagiarisms = []
        print("The plagiarism check has been skipped")

    _generate_activity_report(suspicious_activities, "suspicious_activity.csv")

    for activity in suspicious_activities:
        name = activity.name or activity.username
        suspicious_counts.setdefault(name, 0)
        suspicious_counts[name] += 1

    suspicious_school_counts = {}
    for name in suspicious_counts.keys():
        school = get_school_name(name)
        if school:
            suspicious_school_counts.setdefault(school, 0)
            suspicious_school_counts[school] += 1

    suspicious_schools = sorted(
        ((school, count) for school, count in suspicious_school_counts.items() if count > 1),
        key=lambda e: (-e[1], e[0]),
    )
    if suspicious_schools:
        print(with_color("Suspicious schools:", BColor.WARNING))
        for school, count in suspicious_schools:
            print(f"  - {school}: {count} suspicious teams")

    if should_check_plagiarism:
        generate_website(plagiarisms)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="moss", description="Check code plagiarism in omegaUp via Moss")
    parser.add_argument("-c", "--contest", help="Contest alias to check")
    parser.add_argument("-p", "--problem", help="Problem alias to check, use 'all' for all contest problems")
    parser.add_argument("--skip-plagiarism", action="store_true", help="Skip doing the plagiarism check with Moss")
    parser.add_argument("--min-plagiarism-perc", default=30, help="Minimum percentage of similarity to detect plagiarism, defaults to 30%")
    args = parser.parse_args()

    _main(
        contest_alias=args.contest,
        problem_alias=args.problem,
        should_check_plagiarism=not args.skip_plagiarism,
        min_plagiarism_perc=args.min_plagiarism_perc,
    )
