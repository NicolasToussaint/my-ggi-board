#!/usr/bin/python3
# ######################################################################
# Copyright (c) 2022 Boris Baldassari, Nico Toussaint and others
#
# This program and the accompanying materials are made
# available under the terms of the Eclipse Public License 2.0
# which is available at https://www.eclipse.org/legal/epl-2.0/
#
# SPDX-License-Identifier: EPL-2.0
######################################################################

# This script:
# - reads the metadata defined in the `conf` directory,
# - retrieves information from the gitlab project,
# - updates the static website with new information and plots


import gitlab
import json
import argparse
import pandas as pd
import re
import glob, os
from fileinput import FileInput
from datetime import date


# Define some variables.

file_conf = 'conf/ggi_deployment.json'
file_meta = 'conf/ggi_activities_metadata.json'
file_json_out = 'ggi_activities_full.json'

# Define regexps
# Identify tasks in description:
re_tasks = re.compile(r"^\s*- \[(.)\] (.+)$")
# Identify tasks in description:
re_activity_id = re.compile(r"^Activity ID: \[(GGI-A-\d\d)\]\(.+\).$")

#
# Parse arguments from command line.
#

parser = argparse.ArgumentParser(prog='ggi_update_website')
#parser.add_argument('-a', '--activities', 
#    dest='opt_activities', 
#    action='store_true', 
#    help='Create activities')
parser.add_argument('-i', '--issues', 
    dest='opt_issues_csv', 
    help='Read issues from csv file.')
args = parser.parse_args()

if args.opt_issues_csv:
    issues_csv_file = args.opt_issues_csv 

#
# Read metadata for activities and deployment options.
#

#print(f"\n# Reading metadata from {file_meta}.")
#with open(file_meta, 'r', encoding='utf-8') as f:
#    metadata = json.load(f)
  
print(f"# Reading deployment options from {file_conf}.")
with open(file_conf, 'r', encoding='utf-8') as f:
    conf = json.load(f)

# Determine GitLab server URL and Project name
# From Environment variable if available
# From configuration file otherwise

if 'CI_SERVER_URL' in os.environ:
    GGI_GITLAB_URL = os.environ['CI_SERVER_URL']
    print("Use GitLab URL from environment variable")
else:
    print("Use GitLab URL from configuration file")
    GGI_GITLAB_URL=conf['gitlab_url']

if 'CI_PROJECT_PATH' in os.environ:
    GGI_GITLAB_PROJECT=os.environ['CI_PROJECT_PATH']
    print("Use GitLab Project from environment variable")
else:
    print("Use GitLab URL from configuration file")
    GGI_GITLAB_PROJECT=conf['gitlab_project']

if 'GGI_GITLAB_TOKEN' in os.environ:
    print("Using ggi_gitlab_token from env var.")
else:
    print(" Cannot find env var GGI_GITLAB_TOKEN. Please set it and re-run me.")
    exit(1)

issues = []
issues_cols = ['issue_id', 'activity_id', 'state', 'title', 'labels', 'updated_at', 'url', 'desc', 'tasks_total', 'tasks_done']
tasks = []
hist = []
hist_cols = ['time', 'issue_id', 'event_id', 'type', 'author', 'action', 'url']
if args.opt_issues_csv:
    print(f"# Reading issues from {issues_csv_file}.")
    with open(issues_csv_file, 'r') as f:
        issues = pd.read_csv(issues_csv_file)
    for index, row in issues.iterrows():
        print(f"- {row[0]} {row[2]}.")
else:
    print(f"\n# Connection to GitLab at {GGI_GITLAB_URL} - {GGI_GITLAB_PROJECT}.")
    gl = gitlab.Gitlab(url=GGI_GITLAB_URL, per_page=50, private_token=os.environ['GGI_GITLAB_TOKEN'])
    project = gl.projects.get(GGI_GITLAB_PROJECT)

    print("# Fetching issues..")
    gl_issues = project.issues.list(state='opened', all=True)

    count = 1
    for i in gl_issues:
        desc = i.description
        paragraphs = desc.split('\n\n')
        short_desc = paragraphs[3]
        lines = desc.split('\n')
        a_id = 'Unknown'
        for l in lines:
            tasks_match = re_tasks.match(l)
            if tasks_match:
                tasks.append([i.iid, tasks_match.group(0), tasks_match.group(1)])
            activity_id_match = re_activity_id.match(l)
            if activity_id_match:
                a_id = activity_id_match.group(1)
        tasks_total = i.task_completion_status['count']
        tasks_done = i.task_completion_status['completed_count']
        issues.append([i.iid, a_id, i.state, i.title, ','.join(i.labels),
                       i.updated_at, i.web_url, short_desc, tasks_total, tasks_done])
    
        # Retrieve information about labels.
        for n in i.resourcelabelevents.list():
            event = i.resourcelabelevents.get(n.id)
            n_type = 'label'
            label = n.label['name'] if n.label else ''
            n_action = f"{n.action} {label}"
            line = [n.created_at, i.iid,
                    n.id, n_type, n.user['username'], 
                    n_action, i.web_url]
            hist.append(line)

        print(f"- {i.iid} - {a_id} - {i.title} - {i.web_url} - {i.updated_at}.")
        
        # Remove these lines when dev/debug is over
        if count == 50:
            break
        else:
            count += 1
            
# Convert lists to dataframes
issues = pd.DataFrame(issues, columns=issues_cols)
tasks = pd.DataFrame(tasks, columns=['issue_id', 'state', 'task'])
hist = pd.DataFrame(hist, columns=hist_cols)

# Identify activities depending on their progress
issues_in_progress = []
issues_done = []
issues_not_started = []
for issue in issues.itertuples(index=False):
    print(f"DBG {issue}")
    if conf['progress_labels']['not_started'] in issue[4].split(','):
        issues_not_started.append(issue)
    if conf['progress_labels']['in_progress'] in issue[4].split(','):
        issues_in_progress.append(issue)
    if conf['progress_labels']['done'] in issue[4].split(','):
        issues_done.append(issue)

issues_not_started = pd.DataFrame(issues_not_started,
                           columns=issues_cols)
issues_in_progress = pd.DataFrame(issues_in_progress,
                                  columns=issues_cols)
issues_done = pd.DataFrame(issues_done,
                           columns=issues_cols)

# Print all issues, tasks and events to CSV file
print("\n# Writing issues and history to files.") 
issues.to_csv('web/content/includes/issues.csv', index=False)
hist.to_csv('web/content/includes/labels_hist.csv', index=False)
tasks.to_csv('web/content/includes/tasks.csv', index=False)

# Generate list of current activities
print("\n# Writing current issues.") 
my_issues = []
my_issues_long = []
for local_id, activity_id, title, url, desc in zip(
        issues_in_progress['issue_id'],
        issues_in_progress['activity_id'],
        issues_in_progress['title'],
        issues_in_progress['url'],
        issues_in_progress['desc']):
    print(f" {local_id}, {activity_id}, {title}, {url}")
    my_issues.append(f"* [{title}]({url}) ({activity_id}).")
    my_issues_long.append(f"## {title}\n")
    my_issues_long.append(f"Link to activity in board: {url} \n")
    my_issues_long.append(f"{desc}\n\n")

with open('web/content/includes/current_activities.inc', 'w') as f:
    f.write('\n'.join(my_issues))
with open('web/content/includes/current_activities_long.inc', 'w') as f:
    f.write('\n'.join(my_issues_long))

# Generate list of past activities
print("\n# Writing past issues.") 
my_issues = []
my_issues_long = []
for local_id, activity_id, title, url, desc in zip(
        issues_done['issue_id'],
        issues_in_progress['activity_id'],
        issues_done['title'],
        issues_done['url'],
        issues_done['desc']):
    print(f" {local_id}, {activity_id}, {title}, {url}")
    my_issues.append(f"* [{title}]({url}) ({activity_id}).")
    my_issues_long.append(f"## {title}\n")
    my_issues_long.append(f"Link to activity in board: {url} \n")
    my_issues_long.append(f"{desc}\n\n")

with open('web/content/includes/past_activities.inc', 'w') as f:
    f.write('\n'.join(my_issues))
with open('web/content/includes/past_activities_long.inc', 'w') as f:
    f.write('\n'.join(my_issues_long))
    
# Generate data points for the dashboard
ggi_data_all_activities = f'[{issues_not_started.shape[0]}, {issues_in_progress.shape[0]}, {issues_done.shape[0]}]'
with open('web/content/includes/ggi_data_all_activities.inc', 'w') as f:
    f.write(ggi_data_all_activities)

# Empty (or not) the initialisation banner text in index.
if issues_not_started.shape[0] < 25:
    with open('web/content/includes/initialisation.inc', 'w') as f:
        f.write('')

#
# Replace 
#

# Replace keywords in md files.
def update_keywords(file_in, keywords):
    occurrences = []
    for keyword in keywords:
        for line in FileInput(file_in, inplace=1, backup='.bak'):
            if keyword in line:
                occurrences.append(f'- Changing "{keyword}" to "{keywords[keyword]}" in {file_in}.')
                line = line.replace(keyword, keywords[keyword])
            print(line, end='')
    [ print(o) for o in occurrences ]

current_date = str(date.today())
keywords = {'[GGI_CURRENT_DATE]': current_date}

print("\n# Replacing strings.")
files = glob.glob("web/content/*.md")
files_ = [ f for f in files if os.path.isfile(f) ]
for file in files_:
    update_keywords(file, keywords)

if 'CI_PROJECT_URL' in os.environ:
    print(f"\nWebsite available at the following URL:\n{os.environ['CI_PROJECT_URL']}\n")

print("Done.")
