## Automatic Jira Cloud Backup to s3
[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner2-direct.svg)](https://vshymanskyy.github.io/StandWithUkraine/)

Script for backup Jira and Confluence to s3

Based on https://bitbucket.org/atlassianlabs/automatic-cloud-backup/src/master/

I just added:
* S3 multipart upload instead local store
* ENV support
* Helm chart

Enjoy 🙂

## Usage:

### Helm Install:

`helm install <my-release> oci://registry-1.docker.io/hiload/jira-backup --version 0.1.0 -f values.yaml -f secrets://secret.yaml`


### Docker:

`docker run hiload/jira-backup:1.0 './confluence_backup.py'`

`docker run hiload/jira-backup:1.0 './jira_backup.py'`

### Build your own image:

`docker build . -t your_tag`

Configuration arguments:

| Short | Long                    | env                   | Description                                               |
|-------|-------------------------|-----------------------|-----------------------------------------------------------|
| -s    | --site                  | SITE                  | Your site/account name <account>.atlassian.net            |
| -u    | --user                  | USER                  | Your email address for the jira account with admin rights |
| -t    | --token                 | TOKEN                 | API token for the user account                            |
| -b    | --bucket_name           | BUCKET_NAME           | S3 bucket name                                            |
| -ak   | --aws_access_key_id     | AWS_ACCESS_KEY_ID     | AWS secret access key for s3                              |                                                                                                                                                                |
| -sk   | --aws_secret_access_key | AWS_SECRET_ACCESS_KEY | AWS access key id for s3                                  |
| -ou   | --only_upload_latest    | ONLY_UPLOAD_LATEST    | Just upload latest backup to s3                           |

### License
Copyright (c) 2015 Atlassian US., Inc.\
Copyright (c) 2023 Atlassian Pty Ltd.\
Apache 2.0 licensed, see LICENSE file.