from pybars import Compiler
from bs4 import BeautifulSoup
from server import start_server
import os


def generate_website(html_lang_path, name_by_username):
    results_by_lang = {}
    for html_path in html_lang_path:
        lang_html = get_information_from_html(html_path["html"], name_by_username)
        lang = html_path["lang"]
        results_by_lang.setdefault(lang, []).append({"lang": lang, "data": lang_html})
    results = []
    for lang in sorted(results_by_lang.keys()):
        data = [r for res in results_by_lang[lang] for r in res["data"]]
        data = sorted(data, key=lambda d: -d["status_perc"])
        results.append({"lang": lang, "data": data})
    compile_website(results)


def status_as_int(status):
    return int(status.replace("(", "").replace(")", "").replace("%", ""))


def get_information_from_html(html_path, name_by_username):
    results = []
    with open(html_path) as h:
        scrapper = BeautifulSoup(h, "html.parser")
        a_tags = scrapper.find_all("a")

        # TODO: group by two
        for idx in range(0, len(a_tags), 2):
            tag = a_tags[idx]
            tag_pair = a_tags[idx + 1]

            if "results" in str(tag) and "results" in str(tag_pair):  # filter out the results
                link = tag.get("href")

                # Process first tag
                first_tag_information = tag.contents[0]
                problem_alias, username_1, file_name_1, status = get_results_information(
                    first_tag_information, name_by_username
                )

                # Process second tag
                second_tag_information = tag_pair.contents[0]
                _, username_2, file_name_2, _ = get_results_information(
                    second_tag_information, name_by_username
                )

                results.append(
                    {
                        "link": link,
                        "problem_alias": problem_alias,
                        "usernames": (username_1, username_2),
                        "file_name": (file_name_1, file_name_2),
                        "status": status,
                        "status_perc": status_as_int(status),
                    }
                )
    return results


# results = {lang, results: {link, problem_alias, username, file_name, status}}
def compile_website(results):
    html_compiler = Compiler()
    with open(os.path.join("template", "template.hbs"), "r") as t:
        template = html_compiler.compile("".join(t.readlines()))
        output = template({"results": results})
        start_server(output)

        with open("results.html", "w") as o:
            o.write(output)


def get_results_information(information, name_by_username):
    content = information.split("/")
    _, problem_alias, username, file_name_and_status = content
    file_name, status = file_name_and_status.split(" ")
    name = name_by_username.get(username)
    if name:
        username = f"{name} ({username})"
    return problem_alias, username, file_name, status
