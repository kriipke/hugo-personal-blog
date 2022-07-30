#!/usr/bin/env python3
# coding: utf-8

'''
Check Hugo new releases from Hugo GitHub repo and update image automaticaly

Usage: update.py API_token project_uri
'''

import base64
import requests
import re
import sys
from urllib.parse import quote

GITLAB_URL = "https://gitlab.com/api/v4"
COMMIT_MESSAGE = "Update Hugo to version %s"

def compare_versions(version1, version2):
    def normalize(v):
        return [int(x) for x in re.sub(r'(\.0+)*$','', v).split(".")]
    return normalize(version1) >= normalize(version2)

if len(sys.argv) != 3:
    print('Usage: update.py API_token project_uri')
    exit(1)
https://github.com/gohugoio/hugo/releases/download/v0.101.0/hugo_extended_0.101.0_Linux-64bit.tar.gz
# Get vars from script arguments
GITLAB_TOKEN = sys.argv[1]
GITLAB_PROJECT = quote(sys.argv[2], safe='')

# Get latest release
rrelease = requests.get('https://api.github.com/repos/gohugoio/hugo/releases/latest')
if rrelease.status_code != 200:
    print('Failed to get Hugo latest release from GitHub')
    exit(1)

release = rrelease.json()
print('Last Hugo version is %s'%release['name'])

# Get repository tags
rtags = requests.get('%s/projects/%s/repository/tags'%(GITLAB_URL, GITLAB_PROJECT))
if rtags.status_code != 200:
    print('Failed to get tags from GitLab project')
    exit(1)

# If a higher version is present in the GitLab repository, do nothing
for tag in rtags.json():
    if tag['release'] is None:
        continue
    if compare_versions(tag['release']['tag_name'], release['name'][1:]):
        print('Already up to date, nothing to do')
        exit(0)
print('No tag is higher or equal to Hugo version.\nUpdating...')

# Find release archive checksum from GitHub
for asset in release['assets']:
    if re.search('checksums.txt', asset['name']):
        rchecksums = requests.get(asset['browser_download_url'])
        if rchecksums.status_code != 200:
            print('Failed to get checksums file from GitHub')
            exit(1)
        for line in rchecksums.text.split("\n"):
            if 'hugo_%s_Linux-64bit.tar.gz'%(release['name'][1:]) in line:
                hugo_checksum = line[:64]
            if 'hugo_extended_%s_Linux-64bit.tar.gz'%(release['name'][1:]) in line:
                hugo_extended_checksum = line[:64]

# Get Dockerfile from repository
rdockerfile = requests.get('%s/projects/%s/repository/files/Dockerfile/raw?ref=registry'%(GITLAB_URL, GITLAB_PROJECT))
if rdockerfile.status_code != 200:
    print('Failed to get Dockerfile from %s:'%sys.argv[1])
    print(rdockerfile.text)
    exit(1)
dockerfile = rdockerfile.text.split("\n")

# Replace env variables
for index, line in enumerate(dockerfile):
    if "ARG HUGO_VERSION" in line:
        dockerfile[index] = "ARG HUGO_VERSION=%s"%release['name'][1:]
    if "ARG HUGO_SHA" in line:
        dockerfile[index] = "ARG HUGO_SHA=%s"%hugo_checksum
    if "ARG HUGO_EXTENDED_SHA" in line:
        dockerfile[index] = "ARG HUGO_EXTENDED_SHA=%s"%hugo_extended_checksum

# Update Dockerfile on repository
requestData = {
        'branch': 'registry',
        'content': "\n".join(dockerfile),
        'commit_message': COMMIT_MESSAGE%(release['name'][1:]),
}
rupdate = requests.put('%s/projects/%s/repository/files/Dockerfile'%(
    GITLAB_URL,
    GITLAB_PROJECT,
), data=requestData, headers={'Private-Token': GITLAB_TOKEN})
if rupdate.status_code != 200:
    print("Failed to update Dockerfile:")
    print(rupdate.text)
    exit(1)
print('Dockerfile was updated to version %s'%release['name'][1:])

# Create new tag
requestData = {
        'tag_name': release['name'][1:],
        'ref': 'registry',
        'message': COMMIT_MESSAGE%(release['name'][1:]),
        'release_description': release['body'],
}
rtag = requests.post('%s/projects/%s/repository/tags'%(
    GITLAB_URL,
    GITLAB_PROJECT), data=requestData, headers={'Private-Token': GITLAB_TOKEN})
if rtag.status_code != 201:
    print('Failed to create tag:')
    print(rtag.text)
    exit(0)
print('Tag %s created'%release['name'][1:])
print('Done !')
