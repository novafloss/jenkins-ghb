import datetime
import logging
import re

from github import GitHub, ApiError
import requests
import yaml

from .settings import SETTINGS
from .utils import match, retry


logger = logging.getLogger(__name__)


class LazyGithub(object):
    def __init__(self):
        self._instance = None

    def __getattr__(self, name):
        self.load()
        return getattr(self._instance, name)

    def load(self):
        if not self._instance:
            self._instance = GitHub(access_token=SETTINGS.GITHUB_TOKEN)


GITHUB = LazyGithub()


class PullRequest(object):
    limit_contexts = [p for p in SETTINGS.GHP_LIMIT_JOBS.split(',') if p]

    def __init__(self, data, project):
        self.data = data
        self.project = project
        self._statuses_cache = None

    def __str__(self):
        return self.data['html_url']

    @property
    def ref(self):
        return self.data['head']['ref']

    @retry()
    def comment(self, body):
        if SETTINGS.GHP_DRY_RUN:
            return logger.info("Would comment on %s", self)

        logger.info("Commenting on %s", self)
        (
            GITHUB.repos(self.project.owner)(self.project.repository)
            .issues(self.data['number']).comments.post(body=body)
        )

    def filter_not_built_contexts(self, contexts, rebuild_failed=None):
        not_built = []
        for context in contexts:
            status = self.get_status_for(context)
            state = status.get('state')
            # Skip failed job, unless rebuild asked and old
            if state in {'error', 'failure'}:
                failure_date = datetime.datetime.strptime(
                    status['updated_at'], '%Y-%m-%dT%H:%M:%SZ'
                )
                if rebuild_failed and failure_date > rebuild_failed:
                    continue
            # Skip `Backed`, `New` and `Queued` jobs
            elif state == 'pending':
                # Jenkins deduplicate jobs in the queue. So it's safe to keep
                # triggering the job in case the queue was flushed.
                if status['description'] not in {'Backed', 'New', 'Queued'}:
                    continue
            # Skip other known states
            elif state:
                continue

            not_built.append(context)

        return not_built

    @retry()
    def get_statuses(self):
        if self._statuses_cache is None:
            if SETTINGS.GHP_IGNORE_STATUSES:
                logger.debug("Skip GitHub statuses")
                statuses = {}
            else:
                logger.info(
                    "Fetching statuses for %s", self.data['head']['sha'][:8]
                )
                url = 'https://api.github.com/repos/%s/%s/status/%s?access_token=%s&per_page=100' % (  # noqa
                    self.project.owner, self.project.repository,
                    self.data['head']['sha'], SETTINGS.GITHUB_TOKEN
                )
                statuses = dict([(x['context'], x) for x in (
                    requests.get(url.encode('utf-8'))
                    .json()['statuses']
                ) if match(x['context'], self.limit_contexts)])
                logger.debug("Got status for %r", sorted(statuses.keys()))
            self._statuses_cache = statuses

        return self._statuses_cache

    def get_status_for(self, context):
        return self.get_statuses().get(context, {})

    instruction_re = re.compile(
        '('
        # Case beginning:  jenkins: XXX or `jenkins: XXX`
        '\A`*jenkins:[^\n]*`*' '|'
        # Case one middle line:  jenkins: XXX
        '(?!`)\njenkins:[^\n]*' '|'
        # Case middle line teletype:  `jenkins: XXX`
        '\n`+jenkins:[^\n]*`+' '|'
        # Case block code: ```\njenkins:\n  XXX```
        '```(?:yaml)?\njenkins:[\s\S]*?\n```'
        ')'
    )

    @retry()
    def list_instructions(self):
        logger.info("Queyring comments for instructions")
        issue = (
            GITHUB.repos(self.project.owner)(self.project.repository)
            .issues(self.data['number'])
        )
        comments = [issue.get()] + issue.comments.get()
        for comment in comments:
            body = comment['body'].replace('\r', '')

            for instruction in self.instruction_re.findall(body):
                try:
                    instruction = instruction.strip().strip('`')
                    if instruction.startswith('yaml\n'):
                        instruction = instruction[4:].strip()
                    instruction = yaml.load(instruction)
                except yaml.error.YAMLError as e:
                    logger.warn(
                        "Invalid YAML instruction in %s", comment['html_url']
                    )
                    logger.debug("%s", e)
                    continue

                if not instruction['jenkins']:
                    # Just skip empty or null instructions.
                    continue

                yield (
                    datetime.datetime.strptime(
                        comment['updated_at'],
                        '%Y-%m-%dT%H:%M:%SZ'
                    ),
                    comment['user']['login'],
                    instruction['jenkins'],
                )

    @retry()
    def update_statuses(self, context, state, description, url=None):
        current_statuses = self.get_statuses()

        new_status = dict(
            context=context, description=description,
            state=state, target_url=url,
        )

        if context in current_statuses:
            current_status = {k: current_statuses[context][k] for k in (
                'context', 'description', 'state', 'target_url')}
            if new_status == current_status:
                return

        if SETTINGS.GHP_DRY_RUN:
            return logger.info(
                "Would update status %s to %s/%s", context, state, description,
            )

        try:
            logger.info(
                "Set GitHub status %s to %s/%s", context, state, description,
            )
            new_status = (
                GITHUB.repos(self.project.owner)(self.project.repository)
                .statuses(self.data['head']['sha']).post(**new_status)
            )
            self._statuses_cache[context] = new_status
        except ApiError:
            logger.warn(
                'Hit 1000 status updates on %s', self.data['head']['sha']
            )


class Project(object):
    remote_re = re.compile(
        r'.*github.com[:/](?P<owner>[\w-]+)/(?P<repository>[\w-]+).*'
    )
    pr_limit = [p for p in SETTINGS.GHP_LIMIT_PR.split(',') if p]

    @classmethod
    def from_remote(cls, remote_url):
        match = cls.remote_re.match(remote_url)
        if not match:
            raise ValueError('%r is not github' % (remote_url,))
        return cls(**match.groupdict())

    def __init__(self, owner, repository, jobs=None):
        self.owner = owner
        self.repository = repository
        self.jobs = jobs or []

    def __str__(self):
        return self.url

    @property
    def url(self):
        return 'https://github.com/%s/%s' % (self.owner, self.repository)

    @retry()
    def list_pull_requests(self):
        logger.info(
            "Querying GitHub for %s/%s PR", self.owner, self.repository,
        )

        pulls = (
            GITHUB.repos(self.owner)(self.repository)
            .pulls.get(per_page=b'100')
        )

        for pr in pulls:
            if match(pr['html_url'], self.pr_limit):
                yield PullRequest(pr, project=self)
            else:
                logger.debug("Skipping %s", pr['html_url'])

    def list_contexts(self):
        for job in self.jobs:
            for context in job.list_contexts():
                yield context
