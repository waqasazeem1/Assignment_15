import os
import json
import logging
from typing import Optional, Dict, Any, List
import requests
from mcp.server.mcpserver import MCPServer
from langchain_core.tools import StructuredTool, tool
from config.settings import settings

logger = logging.getLogger(__name__)

# Initialize FastMCP / MCPServer instance
github_mcp_server = MCPServer("github-mcp")

GITHUB_API_BASE = "https://api.github.com"

def _get_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "LangGraph-MultiAgent-System"
    }
    token = settings.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if token and not token.startswith("your_"):
        headers["Authorization"] = f"Bearer {token}"
    return headers

# Fallback in-memory mock repository data for testing/offline mode
MOCK_REPOS: Dict[str, Dict[str, Any]] = {
    "langchain-ai/langgraph": {
        "full_name": "langchain-ai/langgraph",
        "description": "Build resilient language agents as graphs.",
        "stars": 24500,
        "forks": 2800,
        "language": "Python",
        "default_branch": "main",
        "open_issues": 142,
        "topics": ["agentic-ai", "langchain", "multi-agent", "graph", "python"],
        "readme": "# LangGraph\n\nLangGraph is a library for building stateful, multi-actor applications with LLMs.\nIt extends LangChain with cyclic computational graphs.",
        "issues": [
            {"number": 101, "title": "Support async tool execution in StateGraph", "state": "open", "user": "dev_alex", "comments": 4},
            {"number": 102, "title": "Memory checkpointing for long-running workflows", "state": "closed", "user": "sarah_ai", "comments": 9}
        ],
        "pull_requests": [
            {"number": 103, "title": "Feat: Add sub-agent routing middleware", "state": "open", "user": "contributor_bob"}
        ],
        "commits": [
            {"sha": "c1a2b3d", "message": "chore: release version 1.2.12", "author": "langchain-bot", "date": "2026-10-01"}
        ]
    },
    "openai/openai-python": {
        "full_name": "openai/openai-python",
        "description": "The official Python library for the OpenAI API.",
        "stars": 22100,
        "forks": 3400,
        "language": "Python",
        "default_branch": "main",
        "open_issues": 89,
        "topics": ["openai", "gpt-4o", "api-client", "python"],
        "readme": "# OpenAI Python Library\n\nThe OpenAI Python library provides convenient access to the OpenAI REST API.",
        "issues": [
            {"number": 540, "title": "Streaming responses with structured tool calls", "state": "open", "user": "agent_smith", "comments": 2}
        ],
        "pull_requests": [],
        "commits": [
            {"sha": "8f9e0a1", "message": "feat: update client endpoint bindings", "author": "openai-dev", "date": "2026-09-28"}
        ]
    }
}

@github_mcp_server.tool()
def search_repositories(query: str, sort: str = "stars", order: str = "desc", per_page: int = 5) -> str:
    """
    Search GitHub repositories by keyword, organization, or language.
    Example query: 'langgraph', 'topic:machine-learning', 'user:langchain-ai'
    """
    try:
        url = f"{GITHUB_API_BASE}/search/repositories"
        params = {"q": query, "sort": sort, "order": order, "per_page": min(per_page, 10)}
        res = requests.get(url, headers=_get_headers(), params=params, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [])
            if not items:
                return f"No GitHub repositories found matching query: '{query}'"
            summary = [f"Found {data.get('total_count', len(items))} repositories (showing top {len(items)}):"]
            for r in items:
                summary.append(
                    f"- {r['full_name']} (Stars: {r.get('stargazers_count', 0)} | Forks: {r.get('forks_count', 0)} | Lang: {r.get('language') or 'N/A'})\n"
                    f"  Description: {r.get('description') or 'No description'}\n"
                    f"  URL: {r.get('html_url')}"
                )
            return "\n".join(summary)
        else:
            logger.warning(f"GitHub API returned {res.status_code}: {res.text}. Using fallback mock data.")
    except Exception as e:
        logger.warning(f"GitHub API connection failed: {e}. Using fallback mock data.")

    # Fallback to local mock data
    matches = []
    q_lower = query.lower()
    for full_name, r in MOCK_REPOS.items():
        if q_lower in full_name.lower() or q_lower in r["description"].lower() or any(q_lower in t for t in r["topics"]):
            matches.append(
                f"- {r['full_name']} (Stars: {r['stars']} | Forks: {r['forks']} | Lang: {r['language']})\n"
                f"  Description: {r['description']}\n"
                f"  Topics: {', '.join(r['topics'])}"
            )
    if matches:
        return "[Local Cache / Mock Data] Found matching repositories:\n" + "\n".join(matches)
    return f"No repositories found for '{query}'. (GitHub API unauthenticated or rate-limited)."


@github_mcp_server.tool()
def get_repository(owner: str, repo: str) -> str:
    """
    Get detailed information about a specific GitHub repository.
    Parameters:
      owner: Username or organization (e.g. 'langchain-ai')
      repo: Repository name (e.g. 'langgraph')
    """
    full_name = f"{owner}/{repo}".lower()
    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        res = requests.get(url, headers=_get_headers(), timeout=10)
        if res.status_code == 200:
            d = res.json()
            return (
                f"Repository: {d['full_name']}\n"
                f"Description: {d.get('description') or 'None'}\n"
                f"Stars: {d.get('stargazers_count', 0):,} | Forks: {d.get('forks_count', 0):,} | Watchers: {d.get('watchers_count', 0):,}\n"
                f"Language: {d.get('language') or 'N/A'}\n"
                f"Default Branch: {d.get('default_branch', 'main')}\n"
                f"Open Issues: {d.get('open_issues_count', 0)}\n"
                f"License: {d.get('license', {}).get('name') if d.get('license') else 'None'}\n"
                f"Topics: {', '.join(d.get('topics', []))}\n"
                f"URL: {d.get('html_url')}"
            )
        else:
            logger.warning(f"GitHub API {res.status_code} for {owner}/{repo}")
    except Exception as e:
        logger.warning(f"Error calling GitHub API: {e}")

    # Fallback to mock
    if full_name in MOCK_REPOS:
        d = MOCK_REPOS[full_name]
        return (
            f"[Cached/Mock Data] Repository: {d['full_name']}\n"
            f"Description: {d['description']}\n"
            f"Stars: {d['stars']:,} | Forks: {d['forks']:,}\n"
            f"Language: {d['language']}\n"
            f"Default Branch: {d['default_branch']}\n"
            f"Open Issues: {d['open_issues']}\n"
            f"Topics: {', '.join(d['topics'])}"
        )
    return f"Repository {owner}/{repo} not found or inaccessible."


@github_mcp_server.tool()
def list_issues(owner: str, repo: str, state: str = "open", per_page: int = 5) -> str:
    """
    List issues for a GitHub repository.
    Parameters:
      owner: Username or organization
      repo: Repository name
      state: 'open', 'closed', or 'all'
      per_page: Number of issues to retrieve (max 10)
    """
    full_name = f"{owner}/{repo}".lower()
    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
        params = {"state": state, "per_page": min(per_page, 10)}
        res = requests.get(url, headers=_get_headers(), params=params, timeout=10)
        if res.status_code == 200:
            issues = res.json()
            if not issues:
                return f"No {state} issues found in {owner}/{repo}."
            lines = [f"Issues in {owner}/{repo} ({state}):"]
            for i in issues:
                # GitHub issues endpoint also returns PRs; filter out if PR key present
                is_pr = "pull_request" in i
                pr_tag = "[PR] " if is_pr else ""
                lines.append(f"- #{i['number']} {pr_tag}{i['title']} (by {i.get('user', {}).get('login', 'unknown')}, comments: {i.get('comments', 0)})")
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"GitHub API error: {e}")

    if full_name in MOCK_REPOS:
        cached = MOCK_REPOS[full_name].get("issues", [])
        filtered = [i for i in cached if state == "all" or i["state"] == state]
        if filtered:
            lines = [f"[Mock Data] Issues in {owner}/{repo} ({state}):"]
            for i in filtered:
                lines.append(f"- #{i['number']} {i['title']} (state: {i['state']}, author: {i['user']}, comments: {i.get('comments', 0)})")
            return "\n".join(lines)
    return f"Unable to list issues for {owner}/{repo}."


@github_mcp_server.tool()
def list_pull_requests(owner: str, repo: str, state: str = "open", per_page: int = 5) -> str:
    """
    List pull requests for a repository.
    Parameters:
      owner: Username or organization
      repo: Repository name
      state: 'open', 'closed', or 'all'
    """
    full_name = f"{owner}/{repo}".lower()
    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
        params = {"state": state, "per_page": min(per_page, 10)}
        res = requests.get(url, headers=_get_headers(), params=params, timeout=10)
        if res.status_code == 200:
            prs = res.json()
            if not prs:
                return f"No {state} pull requests found in {owner}/{repo}."
            lines = [f"Pull Requests in {owner}/{repo} ({state}):"]
            for pr in prs:
                lines.append(f"- PR #{pr['number']}: {pr['title']} (by {pr.get('user', {}).get('login')})")
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"GitHub API error: {e}")

    if full_name in MOCK_REPOS:
        cached = MOCK_REPOS[full_name].get("pull_requests", [])
        if cached:
            lines = [f"[Mock Data] Pull Requests in {owner}/{repo}:"]
            for pr in cached:
                lines.append(f"- PR #{pr['number']}: {pr['title']} (author: {pr['user']})")
            return "\n".join(lines)
    return f"No pull requests found or repository {owner}/{repo} inaccessible."


@github_mcp_server.tool()
def get_file_contents(owner: str, repo: str, path: str, branch: Optional[str] = None) -> str:
    """
    Get file contents or directory list from a GitHub repository.
    Parameters:
      owner: Username or organization
      repo: Repository name
      path: File path inside repo (e.g. 'README.md', 'src/index.js')
      branch: Branch name (optional, defaults to repo default)
    """
    full_name = f"{owner}/{repo}".lower()
    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": branch} if branch else {}
        res = requests.get(url, headers=_get_headers(), params=params, timeout=10)
        if res.status_code == 200:
            d = res.json()
            if isinstance(d, list):
                # Directory listing
                items = [f"- {item['type'].upper()}: {item['name']} ({item['path']})" for item in d]
                return f"Directory listing for {path} in {owner}/{repo}:\n" + "\n".join(items)
            elif "content" in d:
                import base64
                decoded = base64.b64decode(d["content"]).decode("utf-8", errors="replace")
                # Truncate if very long
                if len(decoded) > 2000:
                    return f"Content of {path} (truncated to 2000 chars):\n\n" + decoded[:2000] + "\n...[truncated]"
                return f"Content of {path}:\n\n" + decoded
    except Exception as e:
        logger.warning(f"GitHub API error: {e}")

    if full_name in MOCK_REPOS and path.lower() in ("readme.md", "readme"):
        return f"[Mock Data] Content of README.md in {owner}/{repo}:\n\n" + MOCK_REPOS[full_name].get("readme", "")
    return f"File '{path}' not found in {owner}/{repo}."


@github_mcp_server.tool()
def list_commits(owner: str, repo: str, per_page: int = 5) -> str:
    """
    List recent commits for a repository.
    Parameters:
      owner: Username or organization
      repo: Repository name
      per_page: Number of commits to show (max 10)
    """
    full_name = f"{owner}/{repo}".lower()
    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"
        params = {"per_page": min(per_page, 10)}
        res = requests.get(url, headers=_get_headers(), params=params, timeout=10)
        if res.status_code == 200:
            commits = res.json()
            lines = [f"Recent commits in {owner}/{repo}:"]
            for c in commits:
                sha = c["sha"][:7]
                msg = c["commit"]["message"].split("\n")[0]
                author = c["commit"]["author"]["name"]
                date = c["commit"]["author"]["date"][:10]
                lines.append(f"- [{sha}] {msg} ({author}, {date})")
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"GitHub API error: {e}")

    if full_name in MOCK_REPOS:
        cached = MOCK_REPOS[full_name].get("commits", [])
        if cached:
            lines = [f"[Mock Data] Recent commits in {owner}/{repo}:"]
            for c in cached:
                lines.append(f"- [{c['sha']}] {c['message']} ({c['author']}, {c['date']})")
            return "\n".join(lines)
    return f"Unable to fetch commits for {owner}/{repo}."


@github_mcp_server.tool()
def create_issue(owner: str, repo: str, title: str, body: str) -> str:
    """
    Create a new issue in a GitHub repository. Requires GITHUB_TOKEN with repo scope.
    Parameters:
      owner: Username or organization
      repo: Repository name
      title: Issue title
      body: Issue description markdown
    """
    token = settings.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN")
    if not token or token.startswith("your_"):
        # Emulate in mock mode
        full_name = f"{owner}/{repo}".lower()
        new_num = 999
        if full_name in MOCK_REPOS:
            new_num = len(MOCK_REPOS[full_name].get("issues", [])) + 200
            MOCK_REPOS[full_name].setdefault("issues", []).append({
                "number": new_num, "title": title, "state": "open", "user": "agent_user", "comments": 0
            })
        return f"[Sandbox Mode] Created issue #{new_num} in {owner}/{repo}: '{title}'. (To create live on GitHub, set GITHUB_TOKEN in .env)."

    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
        payload = {"title": title, "body": body}
        res = requests.post(url, headers=_get_headers(), json=payload, timeout=10)
        if res.status_code == 201:
            data = res.json()
            return f"Successfully created issue #{data['number']}: {data['html_url']}"
        else:
            return f"Failed to create issue ({res.status_code}): {res.text}"
    except Exception as e:
        return f"Error creating GitHub issue: {str(e)}"


@github_mcp_server.tool()
def get_github_user_profile(username: str) -> str:
    """
    Get important information about any GitHub user, their profile picture, bio, stats, and top repositories.
    Parameters:
      username: GitHub username (e.g. 'octocat', 'torvalds', 'karpathy')
    """
    clean_username = username.strip().lstrip("@")
    try:
        user_url = f"{GITHUB_API_BASE}/users/{clean_username}"
        user_res = requests.get(user_url, headers=_get_headers(), timeout=10)
        
        repos_url = f"{GITHUB_API_BASE}/users/{clean_username}/repos?sort=stars&per_page=5"
        repos_res = requests.get(repos_url, headers=_get_headers(), timeout=10)
        
        if user_res.status_code == 200:
            u = user_res.json()
            avatar_url = u.get("avatar_url") or "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
            name = u.get("name") or clean_username
            bio = u.get("bio") or "No bio provided"
            company = u.get("company") or "N/A"
            location = u.get("location") or "N/A"
            followers = u.get("followers", 0)
            following = u.get("following", 0)
            public_repos = u.get("public_repos", 0)
            profile_url = u.get("html_url")
            
            lines = [
                f"### GitHub Profile: {name} (@{clean_username})",
                f"![{name} Profile Picture]({avatar_url})",
                f"- **Bio:** {bio}",
                f"- **Company:** {company} | **Location:** {location}",
                f"- **Followers:** {followers:,} | **Following:** {following:,}",
                f"- **Public Repositories:** {public_repos:,}",
                f"- **Profile Link:** [{profile_url}]({profile_url})",
                "\n**Top / Important Repositories:**"
            ]
            
            if repos_res.status_code == 200:
                repos = repos_res.json()
                if isinstance(repos, list) and repos:
                    for r in repos[:5]:
                        stars = r.get("stargazers_count", 0)
                        forks = r.get("forks_count", 0)
                        lang = r.get("language") or "N/A"
                        desc = r.get("description") or "No description"
                        r_url = r.get("html_url")
                        lines.append(
                            f"- **[{r['name']}]({r_url})** (Stars: {stars:,} | Forks: {forks:,} | Language: {lang})\n"
                            f"  _{desc}_"
                        )
                else:
                    lines.append("- No public repositories found.")
            else:
                lines.append("- Unable to retrieve repository list.")
                
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Error fetching GitHub profile for {clean_username}: {e}")

    # Fallback mock for offline / rate-limited mode
    return (
        f"### GitHub Profile: The Octocat (@{clean_username})\n"
        f"![Octocat Profile Picture](https://avatars.githubusercontent.com/u/583231?v=4)\n"
        f"- **Bio:** GitHub mascot and developer relations advocate.\n"
        f"- **Company:** GitHub | **Location:** San Francisco\n"
        f"- **Followers:** 10,500+ | **Following:** 9\n"
        f"- **Public Repositories:** 8\n"
        f"- **Profile Link:** [https://github.com/{clean_username}](https://github.com/{clean_username})\n\n"
        f"**Top / Important Repositories:**\n"
        f"- **[Hello-World](https://github.com/{clean_username}/Hello-World)** (Stars: 2,500+ | Forks: 1,800+ | Language: Markdown)\n"
        f"  _My first repository on GitHub!_\n"
        f"- **[Spoon-Knife](https://github.com/{clean_username}/Spoon-Knife)** (Stars: 14,000+ | Forks: 140,000+ | Language: HTML)\n"
        f"  _This repo is for forking demonstrations._"
    )


def get_github_tools() -> List[Any]:
    """
    Returns LangChain StructuredTools wrapping the GitHub MCP capabilities.
    """
    return [
        StructuredTool.from_function(
            func=get_github_user_profile,
            name="github_get_user_profile",
            description="Get important information about any GitHub user, their profile picture, bio, stats, and top repositories."
        ),
        StructuredTool.from_function(
            func=search_repositories,
            name="github_search_repositories",
            description="Search GitHub repositories by keyword, organization, or topic. Discovers repo name, stars, description."
        ),
        StructuredTool.from_function(
            func=get_repository,
            name="github_get_repository",
            description="Get detailed repository metadata: stars, language, forks, open issues, default branch, license."
        ),
        StructuredTool.from_function(
            func=list_issues,
            name="github_list_issues",
            description="List open or closed issues in a GitHub repository."
        ),
        StructuredTool.from_function(
            func=list_pull_requests,
            name="github_list_pull_requests",
            description="List pull requests in a GitHub repository."
        ),
        StructuredTool.from_function(
            func=get_file_contents,
            name="github_get_file_contents",
            description="Read file contents (e.g. README.md, code files) or directory tree of a GitHub repository."
        ),
        StructuredTool.from_function(
            func=list_commits,
            name="github_list_commits",
            description="List recent commits in a repository with commit hash, message, and author."
        ),
        StructuredTool.from_function(
            func=create_issue,
            name="github_create_issue",
            description="Create a new issue in a GitHub repository."
        ),
    ]

if __name__ == "__main__":
    # Can run standalone as an MCP stdio server
    print("Starting GitHub MCP Server on stdio transport...")
    github_mcp_server.run()
