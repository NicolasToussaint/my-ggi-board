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
# - connects to the GitLab uinstance as configured in the ggi_deployment.json file
# - optionally creates the activities on a new (empty) gitlab project,
# - optionally creates a board and its lists to display activities.
#
# The script expects your GitLab private key in the environment variable: GGI_GITLAB_TOKEN

# usage: ggi_deploy [-h] [-a] [-b] [-d]
# 
# optional arguments:
#   -h, --help                  Show this help message and exit
#   -a, --activities            Create activities
#   -b, --board                 Create board
#   -d, --project-description   Update Project Description with pointers to the Board and Dashboard
# 

import gitlab
import json
import re
import argparse
import tldextract
import urllib.parse, glob, os
from fileinput import FileInput
from collections import OrderedDict
import os
import urllib.parse
    

# Define some variables.
conf_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+'/conf'
activities_file = conf_dir + '/ggi_activities_full.json'
conf_file = conf_dir + '/ggi_deployment.json'
init_scorecard_file = conf_dir + '/workflow_init.inc'

# Define some regexps
re_section = re.compile(r"^### (?P<section>.*?)\s*$")

ggi_board_name='GGI Activities/Goals'

#
# Parse arguments from command line.
#
parser = argparse.ArgumentParser(prog='ggi_deploy')
parser.add_argument('-a', '--activities', 
    dest='opt_activities', 
    action='store_true', 
    help='Create activities')
parser.add_argument('-b', '--board', 
    dest='opt_board', 
    action='store_true', 
    help='Create board')
parser.add_argument('-d', '--project-description', 
    dest='opt_projdesc', 
    action='store_true', 
    help='Update Project description')
args = parser.parse_args()

#
# Read metadata for activities and deployment options.
#
print(f"\n# Reading metadata from {activities_file}")
with open(activities_file, 'r', encoding='utf-8') as f:
    metadata = json.load(f)
  
print(f"# Reading deployment options from {conf_file}")
with open(conf_file, 'r', encoding='utf-8') as f:
    conf = json.load(f)

# Read the custom scorecard init file.
print(f"# Reading scorecard init file from {init_scorecard_file}.")
init_scorecard = []
with open(init_scorecard_file, 'r', encoding='utf-8') as f:
    init_scorecard = f.readlines()

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
    print("Use ggi_gitlab_token from environment variable")
else:
    print(" Cannot find env var GGI_GITLAB_TOKEN. Please set it and re-run me.")
    exit(1)


#
# Utility functions
#

def create_label(existing_labels, new_label, label_args):
    if new_label in existing_labels:
        print(f" Ignore label: {new_label}")
    else:
        print(f" Create label: {new_label}")
        project.labels.create(label_args)

def extract_sections(activity):
    paragraphs = activity['content'].split('\n\n')
    content_t = 'Introduction'
    content = OrderedDict()
    content = {content_t: []}
    for p in paragraphs:
        match_section = re.search(re_section, p)
        if (match_section):
            content_t = match_section.group('section')
            content[content_t] = []
        else:
            content[content_t].append(p)
    content_text = content['Introduction'][1] + '\n\n'
    content_text += ''.join(init_scorecard) + '\n\n'
    del content['Introduction']
    for key in content.keys():
        content_text += f"### {key}\n\n"
        content_text += '\n\n'.join(content[key])
    return content_text


#
# Connect to GitLab
#

if (args.opt_activities) or (args.opt_board) or (args.opt_projdesc):
    print(f"\n# Connection to GitLab at {GGI_GITLAB_URL} - {GGI_GITLAB_PROJECT}")
    gl = gitlab.Gitlab(url=GGI_GITLAB_URL, per_page=50, private_token=os.environ['GGI_GITLAB_TOKEN'])
    project = gl.projects.get(GGI_GITLAB_PROJECT)

# Update current project description with Website URL
if (args.opt_projdesc):
    if 'CI_PAGES_URL' in os.environ:
        ggi_activities_url = os.path.join(urllib.parse.urljoin(GGI_GITLAB_URL, GGI_GITLAB_PROJECT), '-/boards')
        ggi_pages_url = os.environ['CI_PAGES_URL']
        desc = (
            'Your own Good Governance Initiative project.\n\n'
            'Here you will find '
            f'[**your dashboard**]({ggi_pages_url})\n'
            f'and the [**GitLab Board**]({ggi_activities_url}) with all activities describing the local GGI deployment.\n\n'
            'For more information please see the official project home page at https://gitlab.ow2.org/ggi/ggi/'
        )
        print(f"\nUpdate Project description with:\n<<<\n{desc}\n>>>\n")

        project.description = desc
        project.save()



#
# Create labels & activities
#
if (args.opt_activities):

    print("\n# Manage labels")
    existing_labels = [i.name for i in project.labels.list()]
    print(f"  - Existing labels: {existing_labels}.")

    # Create role labels if needed
    print("\n Roles labels")
    for label, colour in metadata['roles'].items():
        create_label(existing_labels, label, {'name': label, 'color': colour})

    # Create labels for activity tracking
    print("\n Progress labels")
    for name, label in conf['progress_labels'].items():
        create_label(existing_labels, label, {'name': label, 'color': '#ed9121'})

    # Create goal labels if needed
    print("\n Goal labels")
    for goal in metadata['goals']:
        create_label(existing_labels, goal['name'],
                     {'name': goal['name'], 'color': goal['colour']})

    # Read the custom scorecard init file.
    print(f"# Reading scorecard init file from {init_scorecard_file}.")
    init_scorecard = []
    with open(init_scorecard_file, 'r', encoding='utf-8') as f:
        init_scorecard = f.readlines()
    
    # Create issues with their associated labels.
    print("\n# Create activities.")
    for activity in metadata['activities']:
      print(f"  - Create issue [{activity['name']}]")
      labels = \
        [activity['goal']] + \
        activity['roles'] + \
        [conf['progress_labels']['not_started']]
      print(f"    with labels {labels}")
      ret = project.issues.create({'title': activity['name'],
                                   'description': extract_sections(activity), 
                                   'labels': labels})

#
# Create Goals board
#
if (args.opt_board):
    print(f"\n# Creating Goals board: {ggi_board_name}")
    board = project.boards.create({'name': ggi_board_name})

    print('\n# Creating Goals board lists.')
    # First build an ordered list of goals
    goal_lists = []
    for g in metadata['goals']:
        for l in project.labels.list():
            if l.name == g['name']:
                goal_lists.append(l)
                break
    
    # Then create the lists in gitlab
    for goal_label in goal_lists: 
        print(f"  - Creating list for {goal_label.name}")
        b_list = board.lists.create({'label_id': goal_label.id})
    
print("Done.")
