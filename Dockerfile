FROM python:3.11
ENV PYTHONUNBUFFERED=1
RUN pip install requests boto3
COPY confluence_backup.py /app/confluence_backup.py
COPY jira_backup.py /app/jira_backup.py
WORKDIR /app