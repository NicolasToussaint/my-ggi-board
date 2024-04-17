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

"""
This script:
- reads the metadata defined in the `conf` directory,
- connects to the GitLab uinstance as configured in the ggi_deployment.json file
- optionally creates the activities on a new (empty) gitlab project,
- optionally creates a board and its lists to display activities.

The script expects your GitLab private key in the environment variable: GGI_GITLAB_TOKEN

usage: ggi_deploy [-h] [-a] [-b] [-d] [-p]

optional arguments:
  -h, --help                  Show this help message and exit
  -a, --activities            Create activities
  -b, --board                 Create board
  -d, --project-description   Update Project Description with pointers to the Board and Dashboard
  -p, --schedule-pipeline     Schedule nightly pipeline to update dashboard
"""

import argparse
import gitlab
import json
import urllib.parse
import os
import random
import re
import tldextract

from collections import OrderedDict

# Define some variables.
conf_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+'/conf'
activities_file = conf_dir + '/ggi_activities_full.json'
conf_file = conf_dir + '/ggi_deployment.json'
init_scorecard_file = conf_dir + '/workflow_init.inc'

# Define some regexps
re_section = re.compile(r"^### (?P<section>.*?)\s*$")

ggi_board_name='GGI Activities/Goals'

def _parse_args():
    """
    Parse arguments from command line.
    """
    desc = "Deploys an instance of the GGI Board on a GitLab or GitHub instance."
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('-gl', '--gitlab',
                        dest='opt_gitlab',
                        action='store_true',
                        help='Use GitLab backend.')
    parser.add_argument('-gh', '--github',
                        dest='opt_github',
                        action='store_true',
                        help='Use GitHub backend.')
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
    parser.add_argument('-p', '--schedule-pipeline', 
                        dest='opt_schedulepipeline', 
                        action='store_true', 
                        help='Schedule nightly pipeline to update dashboard')
    parser.add_argument('-r', '--random-demo', 
                        dest='opt_random', 
                        action='store_true', 
                        help='Random Scorecard objectives and Activities status, for demo purposes')
    args = parser.parse_args()

    return args


def retrieve_env():
    """
    Read metadata for activities and deployment options.
    
    Determine GitLab server URL and Project name
    * From Environment variable if available, or
    * From configuration file otherwise
    """

    print(f"\n# Reading metadata from {activities_file}")
    with open(activities_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Read the custom scorecard init file.
    print(f"# Reading scorecard init file from {init_scorecard_file}.")
    init_scorecard = []
    with open(init_scorecard_file, 'r', encoding='utf-8') as f:
        init_scorecard = f.readlines()

    print(f"# Reading deployment options from {conf_file}")
    with open(conf_file, 'r', encoding='utf-8') as f:
        params = json.load(f)
        
    if 'CI_SERVER_URL' in os.environ:
        print("- Use GitLab URL from environment variable")
        params['GGI_GITLAB_URL'] = os.environ['CI_SERVER_URL']
    else:
        print("- Use GitLab URL from configuration file")
        params['GGI_GITLAB_URL'] = params['gitlab_url']

    if 'CI_PROJECT_PATH' in os.environ:
        print("- Use GitLab Project from environment variable")
        params['GGI_GITLAB_PROJECT'] = os.environ['CI_PROJECT_PATH']
    else:
        print("- Use GitLab URL from configuration file")
        params['GGI_GITLAB_PROJECT'] = params['gitlab_project']

    if 'CI_PAGES_URL' in os.environ:
        print("- Using GGI_PAGES_URL from environment variable.")
        params['CI_PAGES_URL'] = os.environ['CI_PAGES_URL']
    else:
        print("- Cannot find an env var for GGI_PAGES_URL. Computing it from conf.")
        pieces = tldextract.extract(params['GGI_GITLAB_URL'])
        params['CI_PAGES_URL'] = 'https://' + params['GGI_GITLAB_PROJECT'].split('/')[0] + \
            "." + pieces.domain + ".io/" + params['GGI_GITLAB_PROJECT'].split('/')[-1]

    if 'GGI_GITLAB_TOKEN' in os.environ:
        print("- Using ggi_gitlab_token from env var.")
        params['GGI_GITLAB_TOKEN'] = os.environ['GGI_GITLAB_TOKEN']
    else:
        print("- Cannot find env var GGI_GITLAB_TOKEN. Please set it and re-run me.")
        exit(1)

    params['GGI_URL'] = urllib.parse.urljoin(params['GGI_GITLAB_URL'], params['GGI_GITLAB_PROJECT'])
    params['GGI_ACTIVITIES_URL'] = os.path.join(params['GGI_URL'] + '/', '-/boards')

    return metadata, params


def create_label(existing_labels, new_label, label_args):
    if new_label in existing_labels:
        print(f" Ignore label: {new_label}")
    else:
        print(f" Create label: {new_label}")
        project.labels.create(label_args)

def get_scorecard():
    """
    Build a scorecard with a random number of objectives,
    randomly checked, if required by user.
    Otherwise, simply return the untouched scorecard text
    """

    if (args.opt_random):
        # Create between 4 and 10 objectives per Scorecard
        num_lines = random.randint(4, 10)
        objectives_list = []
        for idx in range(num_lines):
            objectives = "- [ ] objective " + str(idx) + " \n"
            # aim at 25% of objectives done
            if random.randint(1, 4) == 1:
                objectives = objectives.replace("[ ]", "[x]")
            objectives_list.append(objectives)
        return ''.join(init_scorecard).replace("What we aim to achieve in this iteration.", ''.join(objectives_list))
    else:
        return init_scorecard


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
    # Add Activity ID
    content_text = content['Introduction'][1] + '\n\n'
    # Add Scorecard
    content_text += ''.join(get_scorecard())
    del content['Introduction']
    # Add description content.
    for key in content.keys():
        content_text += f"\n\n### {key}\n\n"
        content_text += '\n\n'.join(content[key])
    return content_text


def setup_github(metadata, params: dict, args: dict):
    """
    Executes the following deployment sequence on a GitHub instance:
    * Connect to GitHub
    * Create labels & activities
    * Create Goals board
    * Create schedule for pipeline
    """

    print(f"\n# Connection to GitHub at {params['GGI_GITHUB_URL']} " +
          f"- {params['GGI_GITHUB_PROJECT']}.")
    gh = gitlab.Gitlab(url=params['GGI_GITHUB_URL'],
                       per_page=50,
                       private_token=params['GGI_GITHUB_TOKEN'])
    project = gl.projects.get(params['GGI_GITHUB_PROJECT'])

    


def setup_gitlab(metadata, params: dict, args: dict):
    """
    Executes the following deployment sequence on a GitLab instance:
    * Connect to GitLab
    * Create labels & activities
    * Create Goals board
    * Create schedule for pipeline
    """
    
    print(f"\n# Connection to GitLab at {params['GGI_GITLAB_URL']} " +
          f"- {params['GGI_GITLAB_PROJECT']}.")
    gl = gitlab.Gitlab(url=params['GGI_GITLAB_URL'],
                       per_page=50,
                       private_token=params['GGI_GITLAB_TOKEN'])
    project = gl.projects.get(params['GGI_GITLAB_PROJECT'])

    # Update current project description with Website URL
    if (args.opt_projdesc):
        print("\n# Update Project description")
        if 'CI_PAGES_URL' in params:
            ggi_activities_url = params['GGI_ACTIVITIES_URL']
            ggi_handbook_version = metadata["handbook_version"]
            ggi_pages_url = params['CI_PAGES_URL']
            desc = (
                'Your own Good Governance Initiative project.\n\n'
                'Here you will find '
                f'[**your dashboard**]({ggi_pages_url})\n'
                f'and the [**GitLab Board**]({ggi_activities_url}) with all activities describing the local GGI deployment, based on the version {ggi_handbook_version} of the [GGI handbook](https://ospo-alliance.org/ggi/)\n\n'
                'For more information please see the official project home page at https://ospo-alliance.org/'
            )
            print(f"\nNew description:\n<<<---------\n{desc}\n--------->>>\n")

            project.description = desc
            project.save()
        else:
            print("Cannot find environment variable 'CI_PAGES_URL', skipping.")

    #
    # Create labels & activities
    #
    if (args.opt_activities):

        print("\n# Manage labels")
        existing_labels = [i.name for i in project.labels.list()]

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
        print(f"\n# Reading scorecard init file from {init_scorecard_file}.")
        init_scorecard = []
        with open(init_scorecard_file, 'r', encoding='utf-8') as f:
            init_scorecard = f.readlines()
    
        # Create issues with their associated labels.
        print("\n# Create activities.")
        # First test the existence of Activities Issues:
        #   if at least one Issue is found bearing one Goal label,
        #   consider that all Issues exist and do not add any.
        issues_test = project.issues.list(state='opened')
        if (len(issues_test) > 0):
            print(" Ignore, Issues already exist")
        else:
            for activity in metadata['activities']:
                progress_label = ''
                if (args.opt_random):
                    # randomly choose among valid progress labels
                    # + artificially introduce an extra option for no progress label
                    progress_idx = random.choice(list(conf['progress_labels']) + ['none'])
                    if (progress_idx != 'none' ):
                        progress_label = conf['progress_labels'][progress_idx]
                labels = \
                    [activity['goal']] + \
                    activity['roles'] + \
                    [progress_label]
                print(f"  - Issue: {activity['name']:<60} Labels: {labels}")
                ret = project.issues.create({'title': activity['name'],
                                             'description': extract_sections(activity), 
                                             'labels': labels})

    #
    # Create Goals board
    #
    if (args.opt_board):
        print(f"\n# Create Goals board: {ggi_board_name}")
        boards_list=project.boards.list()
        board_exists=False
        for b in boards_list:
            if b.name == ggi_board_name:
                board_exists=True
                break
        if board_exists:
            print(" Ignore, Board already exists")
        else:
            board = project.boards.create({'name': ggi_board_name})
            print('\n# Create Goals board lists.')
            # First build an ordered list of goals
            goal_lists = []
            for g in metadata['goals']:
                for l in project.labels.list():
                    if l.name == g['name']:
                        goal_lists.append(l)
                        break
        
            # Then create the lists in gitlab
            for goal_label in goal_lists:
                print(f"  - Create list for {goal_label.name}")
                b_list = board.lists.create({'label_id': goal_label.id})

    # Create a scheduled pipeline trigger, if none exist yet.
    if (args.opt_schedulepipeline):
        print(f"\n# Schedule nightly pipeline to refresh the Dashboard")
        nb_pipelines=len(project.pipelineschedules.list())
        if (nb_pipelines > 0):
            print(f" Ignore, already {nb_pipelines} scheduled pipeline(s)")
        else:
            sched = project.pipelineschedules.create({
                'ref': 'main',
                'description': 'Nightly Update',
                'cron': '0 3 * * *'})
            print(f" Pipeline created: '{sched.description}'")


def main():
    """
    Main program. Executes GitLab or GitHub setup functions.
    """
    args = _parse_args()

    if args.opt_gitlab:
        print("* Using GitLab backend.")
        metadata, params = retrieve_env()
        setup_gitlab(metadata, params, args)
    elif args.opt_github:
        print("* Using GitHub backend.")
        metadata, params = retrieve_env()
        setup_github(metadata, params, args)
    elif args.opt_github and args.opt_gitlab:
        print("Cannot use both GitHub and GitLab backends.")
        print("Please select only one. Exiting.")
        exit(2)
    else:
        print("Please select one backend (--gitlab or --github). Exiting.")
        exit(3)
        
    print("\nDone.")


    
if __name__ == '__main__':    

    main()
