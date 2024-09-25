import os
from typing import Dict, Tuple, List

import mosspy
from bs4 import BeautifulSoup

from terminal import with_color, BColor
from cpc_types import MossHtml, Plagiarism

LANG_EXTENSION_TO_MOSS = {
    ".c": "c",
    ".cpp": "cc",
    ".cs": "csharp#",
    ".py": "python",
    ".java": "java",
    ".pascal": "pascal",
    ".txt": "ascii",
}


def check_plagiarism(
        moss_user_id: str,
        problem_aliases: List[str],
        min_plagiarism_perc: int,
        name_by_username: Dict[str, str],
) -> List[Plagiarism]:
    print("Sending information to Moss. Please be patient...")
    os.makedirs("submission", exist_ok=True)
    moss_htmls = []
    for problem_alias in problem_aliases:
        for ext, moss_lang in LANG_EXTENSION_TO_MOSS.items():
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
            moss_htmls.append(MossHtml(
                problem_alias=problem_alias,
                language=moss_lang,
                html_path=filtered_report_path,
            ))

    plagiarisms: List[Plagiarism] = []
    for moss_html in moss_htmls:
        for plag in _get_information_from_html(moss_html, name_by_username):
            if plag.similarity_perc >= min_plagiarism_perc:
                plagiarisms.append(plag)

    return sorted(plagiarisms, key=lambda p: -p.similarity_perc)


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


def _get_similarity_perc(status: str) -> int:
    return int(status.replace("(", "").replace(")", "").replace("%", ""))


def _get_information_from_html(moss_html: MossHtml, name_by_username: Dict[str, str]) -> List[Plagiarism]:
    results: List[Plagiarism] = []
    with open(moss_html.html_path) as h:
        scrapper = BeautifulSoup(h, "html.parser")
        a_tags = scrapper.find_all("a")

        # TODO: group by two
        for idx in range(0, len(a_tags), 2):
            tag = a_tags[idx]
            tag_pair = a_tags[idx + 1]

            if "results" in str(tag) and "results" in str(tag_pair):  # filter out the results
                url = tag.get("href")

                # Process first tag
                first_tag_information = tag.contents[0]
                problem_alias, username_1, file_name_1, status = _get_results_information(
                    first_tag_information
                )
                display_name_1 = name_by_username.get(username_1, username_1)

                # Process second tag
                second_tag_information = tag_pair.contents[0]
                _, username_2, file_name_2, _ = _get_results_information(
                    second_tag_information
                )
                display_name_2 = name_by_username.get(username_2, username_2)

                results.append(Plagiarism(
                    usernames=(username_1, username_2),
                    names=(display_name_1, display_name_2),
                    results_url=url,
                    problem_alias=problem_alias,
                    language=moss_html.language,
                    file_names=(file_name_1, file_name_2),
                    status=status,
                    similarity_perc=_get_similarity_perc(status),
                ))

    return results


def _get_results_information(information: str) -> Tuple[str, str, str, str]:
    content = information.split("/")
    _, problem_alias, username, file_name_and_status = content
    file_name, status = file_name_and_status.split(" ")
    return problem_alias, username, file_name, status
