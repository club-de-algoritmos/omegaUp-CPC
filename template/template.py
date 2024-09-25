from typing import List, Dict, Any

from pybars import Compiler
from server import start_server
import os

from cpc_types import Plagiarism


def generate_website(plagiarisms: List[Plagiarism]) -> None:
    results_by_lang = {}
    for plag in plagiarisms:
        results_by_lang.setdefault(plag.language, []).append({
            "link": plag.results_url,
            "problem_alias": plag.problem_alias,
            "usernames": [_get_display_name(plag.usernames[i], plag.usernames[i]) for i in range(2)],
            "file_name": plag.file_names,
            "status": plag.status,
        })

    template_data = []
    for lang in sorted(results_by_lang.keys()):
        template_data.append({"lang": lang, "data": results_by_lang[lang]})
    _compile_website(template_data)


def _get_display_name(name: str, username: str) -> str:
    if name == username:
        return name
    return f"{name} ({username})"


def _compile_website(results: List[Dict[str, Any]]) -> None:
    html_compiler = Compiler()
    with open(os.path.join("template", "template.hbs"), "r") as t:
        template = html_compiler.compile("".join(t.readlines()))
        output = template({"results": results})
        start_server(output)

        with open("results.html", "w") as o:
            o.write(output)
