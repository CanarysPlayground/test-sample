import requests
from datetime import datetime, timedelta
import csv
from dateutil.relativedelta import relativedelta

# Constants
GITLAB_URL = "https://gitlab.com"          # Replace this with GitLab details
ACCESS_TOKEN = ""                          # Replace 'your_gitlab_token' with your actual GitLab token
CSV_FILE = "gitlab_projects_inventory.csv"
PER_PAGE = 100

# Helper functions
def get_headers():
    return {
        "Private-Token": ACCESS_TOKEN
    }

def get_projects():
    projects = []
    page = 1
    while True:
        url = f"{GITLAB_URL}/api/v4/projects"
        params = {
            "membership": True,
            "per_page": PER_PAGE,
            "page": page
        }
        response = requests.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        page_projects = response.json()
        if not page_projects:
            break
        projects.extend(page_projects)
        page += 1
    return projects

def get_merge_requests(project_id, created_after):
    merge_requests = []
    page = 1
    while True:
        url = f"{GITLAB_URL}/api/v4/projects/{project_id}/merge_requests"
        params = {
            "created_after": created_after,
            "state": "all",
            "order_by": "updated_at",
            "sort": "desc",
            "per_page": PER_PAGE,
            "page": page
        }
        response = requests.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        page_merge_requests = response.json()
        if not page_merge_requests:
            break
        merge_requests.extend(page_merge_requests)
        page += 1
    return merge_requests

def get_recent_commits(project_id):
    commits = []
    page = 1
    while True:
        url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/commits"
        since_date = (datetime.now() - relativedelta(years=2)).isoformat() + 'Z'
        params = {
            "since" : since_date,
            "order_by": "created_at",
            "per_page": PER_PAGE,
            "page": page

        }
        response = requests.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        page_commits = response.json()
        if not page_commits:
            break
        commits.extend(page_commits)
        page += 1
    return commits

def get_total_commit_count(project_id):
    commits = []
    page = 1
    while True:
        url = f"{GITLAB_URL}/api/v4/projects/{project_id}/repository/commits"
        params = {
            "per_page": PER_PAGE,
            "page": page
        }
        response = requests.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        page_commits = response.json()
        if not page_commits:
            break
        commits.extend(page_commits)
        page += 1
    return len(commits)

def get_project_size(project_id):
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}?statistics=true"
    response = requests.get(url, headers=get_headers())
    response.raise_for_status()
    project_info = response.json()
    return project_info.get("statistics", {}).get("repository_size")

def get_pipelines(project_id):
    pipelines = []
    page = 1
    while True:
        url = f"{GITLAB_URL}/api/v4/projects/{project_id}/pipelines"
        params = {
            "per_page": PER_PAGE,
            "page": page
        }
        response = requests.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        page_pipelines = response.json()
        if not page_pipelines:
            break
        pipelines.extend(page_pipelines)
        page += 1
    return [pipeline for pipeline in pipelines if pipeline.get('yaml_errors') is None]

def get_project_members(project_id):
    members = []
    page = 1
    while True:
        url = f"{GITLAB_URL}/api/v4/projects/{project_id}/members/all"
        params = {
            "per_page": PER_PAGE,
            "page": page
        }
        response = requests.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        page_members = response.json()
        if not page_members:
            break
        members.extend(page_members)
        page += 1
    return members

def main():
    projects = get_projects()
    inventory = []

    for project in projects:
        repository_size = get_project_size(project["id"])
        repository_size_mb = round(repository_size / (1024 * 1024), 2) if repository_size else None

        project_details = {
            "id": project["id"],
            "name": project["name"],
            "full_path": project["path_with_namespace"],
            "namespace": "group" if project["namespace"]["kind"] == "group" else "user",
            "repository_size": repository_size_mb,  # Convert to MB if available
            "clone_url": project["http_url_to_repo"]
        }

        # Get all merge requests and count them
        merge_requests = get_merge_requests(project["id"], (datetime.now() - timedelta(days=30)).isoformat() + 'Z')
        project_details["latest_merge_request_date"] = merge_requests[0]["created_at"] if merge_requests else None
        project_details["merge_request_count"] = len(merge_requests)

        # Get the latest commit creation date
        latest_commit_date = get_recent_commits(project["id"])
        if len(latest_commit_date) > 0:            
                project_details["latest_commit_date"] = latest_commit_date[len(latest_commit_date) - 1]["committed_date"]
        else:
            project_details["latest_commit_date"] = None
        
        # Get the count of pipelines involved
        pipelines = get_pipelines(project["id"])
        project_details["pipeline_count"] = len(pipelines)

        # Get the total commit count
        total_commit_count = get_total_commit_count(project["id"])
        project_details["total_commit_count"] = total_commit_count

        # Get project members and their access levels
        members = get_project_members(project["id"])
        read_users = [member for member in members if member['access_level'] == 20]  # Guest access
        write_users = [member for member in members if member['access_level'] == 30]  # Reporter access
        admin_users = [member for member in members if member['access_level'] >= 40]  # Maintainer and Owner access

        project_details["read_user_count"] = len(read_users)
        project_details["write_user_count"] = len(write_users)
        project_details["admin_user_count"] = len(admin_users)
        project_details["total_user_count"] = len(members)

        inventory.append(project_details)

    # Write to CSV
    with open(CSV_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Project Full Path", "Namespace", "Repository Size (MB)", "Clone URL", "Latest Merge Request Date", "Latest Commit Date", "Merge Request Count", "Pipeline Count", "Total Commit Count", "Read User Count", "Write User Count", "Admin User Count", "Total User Count"])
        
        for project in inventory:
            writer.writerow([
                project["full_path"],
                project["namespace"],
                project["repository_size"],
                project["clone_url"],
                project["latest_merge_request_date"],
                project["latest_commit_date"],
                project["merge_request_count"],
                project["pipeline_count"],
                project["total_commit_count"],
                project["read_user_count"],
                project["write_user_count"],
                project["admin_user_count"],
                project["total_user_count"]
            ])

    print(f"Inventory has been written to {CSV_FILE}")

if __name__ == "__main__":
    main()
