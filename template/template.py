from typing import List, Optional

from pybars import Compiler
import os

from cpc_types import Plagiarism
from terminal import with_color, BColor


def generate_html_report(plagiarisms: List[Plagiarism], file_path: str) -> None:
    print(with_color(f"\nGenerating plagiarism report at {file_path}", BColor.OK_CYAN))

    results_by_lang = {}
    for plag in plagiarisms:
        results_by_lang.setdefault(plag.language, []).append({
            "link": plag.results_url,
            "problem_alias": plag.problem_alias,
            "usernames": [_get_display_name(plag.names[i], plag.usernames[i]) for i in range(2)],
            "file_name": plag.file_names,
            "status": plag.status,
        })

    template_data = []
    for lang in sorted(results_by_lang.keys()):
        template_data.append({"lang": lang, "data": results_by_lang[lang]})

    html_compiler = Compiler()
    with open(os.path.join("template", "template.hbs"), "r") as t:
        template = html_compiler.compile("".join(t.readlines()))
        output = template({"results": template_data})
        with open(file_path, "w") as o:
            o.write(output)


def _get_display_name(name: Optional[str], username: str) -> str:
    return f"{name} ({username})" if name else username
