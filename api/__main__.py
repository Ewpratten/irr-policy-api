from textwrap import dedent
import flask
from webapputils import Webapp
import requests
from typing import Dict, List
import requests
import re

RADB_API = "https://www.radb.net/query"
MEMBER_RE = r"members:\s*(.*)"
EXPORT_RE = r"export:\s*.*to\s([A-Z\d-]+)\sannounce\s(.*)"
IMPORT_RE = r"import:\s*.*from\s([A-Z\d-]+)\saccept(.*)"

# Set up an app
app = Webapp(__name__, static_directory="static", google_tracking_code=None)


def get_route_set_members(name) -> List[str]:
    # ANY is special
    if name == "ANY":
        return ["0.0.0.0/0", "::/0"]

    resp = requests.get(RADB_API, params={
        "keywords": name,
        "advanced_query": "",
        "-T option": "",
        "ip_option": "",
        "-i option": ""
    })

    # Get all members from the response
    member_sections = re.findall(MEMBER_RE, resp.text)
    members = []
    for section in member_sections:
        members.extend([x.strip() for x in section.split(",")])

    return members


def get_aut_num_rules(aut_num) -> Dict[str, Dict[str, str]]:
    resp = requests.get(RADB_API, params={
        "keywords": aut_num,
        "advanced_query": "",
        "-T option": "",
        "ip_option": "",
        "-i option": ""
    })

    # Get all rules
    import_rules = re.findall(IMPORT_RE, resp.text)
    export_rules = re.findall(EXPORT_RE, resp.text)

    # Add all import rules to the ruleset
    output = {}
    for rule in import_rules:
        output[rule[0]] = {"import": rule[1].strip()}

    # Add all export rules to the ruleset
    for rule in export_rules:
        if rule[0] not in output:
            output[rule[0]] = {}
        output[rule[0]]["export"] = rule[1].strip()

    return output


@app.errorhandler(404)
def page_not_found(e):
    return "Error 404", 404
    # return flask.render_template('404.html'), 404


@app.route("/")
def index():
    return dedent("""
                  Welcome to the IRR Policy API
                  <br><br>
                  Endpoints:<br>
                   - /route-set/[id]<br>
                   - /generate-for/[ownas]/[peeras]<br>
                  """)


def get_rsm_recur(id):
    # Get all route set members
    members = get_route_set_members(id)

    # Any member containing `RS-` or `:RS-` is a sub-route-set
    while any(x.startswith("RS-") or ":RS-" in x for x in members):
        for member in members:
            if member.startswith("RS-") or ":RS-" in member:
                members.extend(get_route_set_members(member))
                members.remove(member)
    return members


@app.route("/route-set/<id>")
def route_set(id):

    # Get all route set members
    members = get_rsm_recur(id)

    # If we have no members, 404
    if len(members) == 0:
        return "Route set not found, or is empty", 404

    # Build and return repsonse
    return {
        "members": members
    }


@app.route("/generate-for/<ownas>/<peeras>")
def generate_for(ownas, peeras):

    # Get own autnum rules
    rules = get_aut_num_rules(ownas)

    # Get the rules for the peer autnum
    peer_rules = rules.get(peeras, {})

    # If we have no rules, 404
    if peer_rules == {}:
        return "No rules found", 404

    return {
        "import": get_rsm_recur(peer_rules["import"]) if "import" in peer_rules else [],
        "export": get_rsm_recur(peer_rules["export"]) if "export" in peer_rules else []
    }


if __name__ == "__main__":
    app.run(debug=True)
