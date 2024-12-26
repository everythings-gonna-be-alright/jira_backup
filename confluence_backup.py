#!/usr/bin/env python3
# coding=utf-8

# Script created by The Epic Battlebeard 10/08/18
# this script will trigger and download a backup of a CONFLUENCE instance.

# --------- Change log ---------
#
# 2019/11/14 - Script creation

import requests
import time
import re
import argparse
import boto3
from botocore.exceptions import ConnectTimeoutError
import os


def conf_backup(account, username, token, attachments, only_upload_latest):
    # global variables
    global backup_response
    global json
    global file_name

    # Set json data to determine if backup to include attachments.
    if attachments in ('Y', 'y'):
        json = b'{"cbAttachments": "true", "exportToCloud": "true"}'
    elif attachments in ('N', 'n'):
        json = b'{"cbAttachments": "false", "exportToCloud": "true"}'

    # Create the full base url for the JIRA instance using the account name.
    url = 'https://' + account + '.atlassian.net/wiki'

    # Open new session for cookie persistence and auth.
    session = requests.Session()
    session.auth = (username, token)
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    if not only_upload_latest in ('Y', 'y'):
        # Start backup
        backup_start = session.post(url + '/rest/obm/1.0/runbackup', data=json)

        # Catch error response from backup start and exit if error found.
        try:
            backup_response = int(re.search('(?<=<Response \[)(.*?)(?=\])', str(backup_start)).group(1))
        except AttributeError:
            print(backup_start.text)
            exit(1)

        # Check backup startup response is 200 if not print error and exit.
        if backup_response != 200:
            print(backup_start.text)
            exit(1)
        else:
            print('Backup starting...')

    progress_req = session.get(url + '/rest/obm/1.0/getprogress')

    # Check for filename match in response
    file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress_req.text))

    # If no file name match in JSON response keep outputting progress every 10 seconds
    while file_name == 'None':
        progress_req = session.get(url + '/rest/obm/1.0/getprogress')
        # Regex to extract elements of JSON progress response.
        file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress_req.text))
        estimated_percentage = str(re.search('(?<=Estimated progress: )(.*?)(?=\")', progress_req.text))
        error = 'error'
        # While there is an estimated percentage this will be output.
        if estimated_percentage != 'None':
            # Regex for current status.
            current_status = str(
                re.search('(?<=currentStatus\":\")(.*?)(?=\")', progress_req.text).group(1))
            # Regex for percentage progress value
            estimated_percentage_value = str(
                re.search('(?<=Estimated progress: )(.*?)(?=\")', progress_req.text).group(1))
            print('Action: ' + current_status + ' / Overall progress: ' + estimated_percentage_value)
            time.sleep(10)
        # Once no estimated percentage in response the alternative progress is output.
        elif estimated_percentage == 'None':
            # Regex for current status.
            current_status = str(
                re.search('(?<=currentStatus\":\")(.*?)(?=\")', progress_req.text).group(1))
            # Regex for alternative percentage value.
            alt_percentage_value = str(
                re.search('(?<=alternativePercentage\":\")(.*?)(?=\")', progress_req.text).group(1))
            print('Action: ' + current_status + ' / Overall progress: ' + alt_percentage_value)
            time.sleep(10)
        # Catch any instance of the of word 'error' in the response and exit script.
        elif error.casefold() in progress_req.text:
            print(progress_req.text)
            exit(1)

    # Get filename from progress JSON
    file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress_req.text))

    # Check filename is not None
    if file_name != 'None':
        file_name = str(re.search('(?<=fileName\":\")(.*?)(?=\")', progress_req.text).group(1))
        print('Backup file can also be downloaded from ' + url + '/download/' + file_name)
        date = time.strftime("%Y%m%d_%H%M%S")
        filename = account + '_conf_backup_' + date + '.zip'
        url = url + '/download/' + file_name
        return filename, url, session


def upload_to_s3(aws_access_key_id, aws_secret_access_key, bucket_name, s3_object_key, download_url, session):
    # Initialize the S3 client
    timeout_seconds = 30
    s3 = boto3.client('s3', config=boto3.session.Config(connect_timeout=timeout_seconds, read_timeout=timeout_seconds),
                      aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

    # Create an S3 object to write chunks to
    s3_object = s3.create_multipart_upload(Bucket=bucket_name, Key=s3_object_key)

    print('Start upload to s3 bucket ' + bucket_name + "/" + s3_object_key)

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

    except ConnectTimeoutError as e:
        print(f"Connection timed out after {timeout_seconds} seconds. Error:", e)
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
    parser.add_argument('-a', '--attachments', help='[Y/y] to download with attachments or [N/n] to download without')
    parser.add_argument('-b', '--bucket_name', help='S3 bucket name')
    parser.add_argument('-ak', '--aws_access_key_id', help='AWS secret access key for s3')
    parser.add_argument('-sk', '--aws_secret_access_key', help='AWS access key id for s3')
    parser.add_argument('-ou', '--only_upload_latest', help='[Y/y] to just re-upload latest backup to s3')

    args = parser.parse_args()
    site = find_in_envs(args, "site")
    user_name = find_in_envs(args, "user")
    api_token = find_in_envs(args, "token")
    only_upload_latest = find_in_envs(args, "only_upload_latest")
    if not api_token:
        print("API token for the user account is not set")
        exit(1)
    attachments = find_in_envs(args, "attachments")
    # AWS credentials and S3 bucket information
    aws_access_key_id = find_in_envs(args, "aws_access_key_id")
    aws_secret_access_key = find_in_envs(args, "aws_secret_access_key")
    bucket_name = find_in_envs(args, "bucket_name")

    filename, url, session = conf_backup(site, user_name, api_token, attachments, only_upload_latest)
    upload_to_s3(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key,
                 bucket_name=bucket_name, s3_object_key=filename, download_url=url, session=session)


if __name__ == '__main__':
    main()
