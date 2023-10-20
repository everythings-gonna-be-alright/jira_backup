#!/usr/bin/env python3
# coding=utf-8

# Script created by The Epic Battlebeard 10/08/18
# this script will trigger and download a backup of a JIRA instance.

# --------- Change log ---------
#
# 13/08/18 - NKW - Added help text function, changed string manipulation from substring to regex for consistency.
# 14/08/18 - NKW - Changed to interactive so can still accept input after compilation. (may change to command line args).
# 01/10/18 - NKW - Added argparser to run from command line.
#

import requests
import time
import re
import argparse
import boto3
import os

# Constants (DO NOT CHANGE)
JSON_DATA = b'{"cbAttachments": "true", "exportToCloud": "true"}'

def jira_backup(account, username, token, json, only_upload_latest):

    # Create the full base url for the JIRA instance using the account name.
    url = 'https://' + account + '.atlassian.net'

    # Open new session for cookie persistence and auth.
    session = requests.Session()
    session.auth = (username, token)
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    if not only_upload_latest in ('Y', 'y'):
        # Start backup
        backup_req = session.post(url + '/rest/backup/1/export/runbackup', data=json)

        # Catch error response from backup start and exit if error found.
        if 'error' in backup_req.text:
            print(backup_req.text)
            exit(1)

    # Get task ID of backup.
    task_req = session.get(url + '/rest/backup/1/export/lastTaskId')
    task_id = task_req.text

    # set starting task progress values outside of while loop and if statements.
    task_progress = 0
    last_progress = -1
    global progress_req

    # Get progress and print update until complete
    while task_progress < 100:

        progress_req = session.get(url + '/rest/backup/1/export/getProgress?taskId=' + task_id)

        # Chop just progress update from json response
        try:
            task_progress = int(re.search('(?<=progress":)(.*?)(?=,)', progress_req.text).group(1))
        except AttributeError:
            print(progress_req.text)
            exit(1)

        if (last_progress != task_progress) and 'error' not in progress_req.text:
            print("Progress: "+task_progress+"%")
            last_progress = task_progress
        elif 'error' in progress_req.text:
            print(progress_req.text)
            exit(1)

        if task_progress < 100:
            time.sleep(10)

    if task_progress == 100:

        download = re.search('(?<=result":")(.*?)(?=\",)', progress_req.text).group(1)

        print('Backup complete, downloading files.')
        print('Backup file can also be downloaded from ' + url + '/plugins/servlet/' + download)

        date = time.strftime("%Y%m%d_%H%M%S")
        filename = account + '_backup_' + date + '.zip'
        url = url + '/plugins/servlet/' + download
        return filename, url, session

def upload_to_s3(aws_access_key_id, aws_secret_access_key, bucket_name, s3_object_key, download_url, session):
    # Initialize the S3 client
    s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

    # Create an S3 object to write chunks to
    s3_object = s3.create_multipart_upload(Bucket=bucket_name, Key=s3_object_key)

    print('Start upload to s3 bucket' + bucket_name + "/" + s3_object_key)

    try:
        file = session.get(download_url, stream=True)
        file.raise_for_status()

        # Initialize variables for chunk numbering and upload ID
        part_number = 1
        upload_id = s3_object['UploadId']
        parts = []

        # 50mb chunk
        for chunk in file.iter_content(chunk_size=52428800):
            if chunk:
                # Upload the chunk to S3
                part = s3.upload_part(
                    Bucket=bucket_name,
                    Key=s3_object_key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=chunk
                )
                parts.append({'PartNumber': part_number, 'ETag': part['ETag']})
                part_number += 1

        # Complete the multipart upload
        s3.complete_multipart_upload(
            Bucket=bucket_name,
            Key=s3_object_key,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )

        print(f'Successfully uploaded {s3_object_key} to S3.')

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        # Clean up in case of an error
        s3.abort_multipart_upload(Bucket=bucket_name, Key=s3_object_key, UploadId=upload_id)

def find_in_envs(args, key):
    if os.environ.get(key.upper()):
        value = os.environ.get(key.upper())
    else:
        value = args.__dict__[key]
    return value

def main():

    parser = argparse.ArgumentParser('jira backup')
    parser.add_argument('-s', '--site', help='Your site/account name <account>.atlassian.net')
    parser.add_argument('-u', '--user', help='Your email address for the jira account with admin rights')
    parser.add_argument('-t', '--token', help='API token for the user account')
    parser.add_argument('-b', '--bucket_name', help='S3 bucket name')
    parser.add_argument('-ak', '--aws_access_key_id', help='AWS access key id for s3')
    parser.add_argument('-sk', '--aws_secret_access_key', help='AWS secret access key for s3')
    parser.add_argument('-ou', '--only_upload_latest', help='Just upload latest backup to s3')

    args = parser.parse_args()
    site = find_in_envs(args,"site")
    user_name = find_in_envs(args, "user")
    api_token = find_in_envs(args, "token")
    only_upload_latest = find_in_envs(args, "only_upload_latest")
    if not api_token:
       print("API token for the user account is not set")
       exit(1)
    # AWS credentials and S3 bucket information
    aws_access_key_id = find_in_envs(args, "aws_access_key_id")
    aws_secret_access_key = find_in_envs(args, "aws_secret_access_key")
    bucket_name = find_in_envs(args, "bucket_name")

    filename, url, session = jira_backup(site, user_name, api_token, JSON_DATA, only_upload_latest)
    upload_to_s3(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, bucket_name=bucket_name, s3_object_key=filename, download_url=url, session=session)

if __name__ == '__main__':
    main()