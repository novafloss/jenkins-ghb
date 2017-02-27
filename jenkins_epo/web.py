# This file is part of jenkins-epo
#
# jenkins-epo is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# jenkins-epo is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# jenkins-epo.  If not, see <http://www.gnu.org/licenses/>.

import asyncio
import hmac
import hashlib
import json
import logging
from os.path import realpath as rp, join as j, dirname as dn

from aiohttp import web
from jenkins_yml.job import Job as JobSpec
import yaml

from .github import GITHUB, cached_arequest
from .pipeline import Pipeline
from .procedures import process_url
from .repository import CommitStatus, REPOSITORIES, Repository, WebHook
from .settings import SETTINGS
from .tasks import ProcessUrlTask
from .workers import WORKERS, Task

app = web.Application()
logger = logging.getLogger(__name__)


app.router.add_static(
    '/static/', name='static',
    path=rp(j(dn(__file__), 'static'))
)


@asyncio.coroutine
def simple_webhook(request):
    logger.info("Processing simple webhook event.")
    url = request.GET['head']
    priority = ('10-webhook', url)
    yield from WORKERS.enqueue(
        ProcessUrlTask(priority, url, callable_=process_url)
    )
    return web.json_response({'message': 'Event processing in progress.'})


app.router.add_post('/simple-webhook', simple_webhook, name='simple-webhook')


def compute_signature(payload, secret):
    return "sha1=%s" % (
        hmac.new(key=secret, msg=payload, digestmod=hashlib.sha1)
        .hexdigest()
    )


class DenySignature(Exception):
    pass


class SkipEvent(Exception):
    pass


def validate_signature(headers, payload):
    try:
        key = SETTINGS.GITHUB_SECRET.encode('ascii')
    except Exception as e:
        logger.error("Failed to get GITHUB_SECRET: %s", e)
        raise DenySignature()

    try:
        github_signature = headers['X-Hub-Signature']
        logger.debug("Got signature %r", github_signature)
    except KeyError:
        logger.warn('No Hub signature. Denying.')
        raise DenySignature()

    my_signature = compute_signature(payload, key)
    logger.debug("Wants signature %r", my_signature)
    if github_signature != my_signature:
        logger.warn('Invalid Hub signature. Denying.')
        raise DenySignature()

    return True


_ignored_action = {
    'assigned',
    'unassigned',
    'review_requested',
    'review_requested_removed',
    'labeled',
    'unlabeled',
    'closed',
    'synchronize',
}


def infer_url_from_event(payload):
    if 'pull_request' in payload:
        logger.debug("Detected pull_request event.")
        if payload['action'] in _ignored_action:
            logger.info("Skipping event %s.", payload['action'])
            raise SkipEvent()
        return payload['pull_request']['html_url']
    elif 'ref' in payload:
        logger.debug("Detected branch event.")
        ref = payload['ref'][len('refs/heads/'):]
        return payload['repository']['html_url'] + '/tree/' + ref
    elif 'issue' in payload:
        if 'pull_request' in payload['issue']:
            logger.debug("Detected issue event.")
            return payload['issue']['pull_request']['html_url']
        else:
            logger.debug("Skipping event on literal issue.")
            raise SkipEvent()
    else:
        logger.error("Can't infer HEAD from payload.")
        logger.debug("payload=%r", payload)
        raise SkipEvent()


@asyncio.coroutine
def github_webhook(request):
    logger.info("Processing GitHub webhook event.")
    payload = yield from request.read()
    yield from request.release()

    try:
        validate_signature(request.headers, payload)
    except DenySignature:
        return web.json_response({'message': 'Invalid signature.'}, status=403)

    payload = json.loads(payload.decode('utf-8'))
    if 'hook_id' in payload:
        logger.debug("Ping from GitHub.")
        return web.json_response({'message': 'Hookaïda !'}, status=200)

    try:
        url = infer_url_from_event(payload)
    except SkipEvent:
        return web.json_response({'message': 'Event processed.'})

    priority = ('10-webhook', url)
    logger.info("Queuing %s.", url)
    yield from WORKERS.enqueue(
        ProcessUrlTask(priority, url, callable_=process_url)
    )

    return web.json_response({'message': 'Event processing in progress.'})


app.router.add_post('/github-webhook', github_webhook, name='github-webhook')


@asyncio.coroutine
def dashboard(request):
    static = request.app.router['static']
    return web.Response(content_type="text/html", text="""\
<!DOCTYPE html>
<html>
  <head>
    <title>Jenkins EPO Dashboard</title>
    <link rel="stylesheet" type="text/css" href="%(style)s" />
  </head>
  <body>
    <div id="main"></div>
    <script src="%(script)s"></script>
    <script>main();</script>
  </body>
</html>
""".strip() % dict(
        script=static.url(filename='dashboard.js'),
        style=static.url(filename='dashboard.css'),
    ))


app.router.add_get('/dashboard', dashboard, name='dashboard')


class PipelineView(web.View):
    @asyncio.coroutine
    def statuses_task(self):
        self.statuses = yield from cached_arequest(
            GITHUB.repos(self.repository)
            .commits(self.request.match_info['ref'])
            .statuses
        )

    @asyncio.coroutine
    def stages_task(self):
        fullref = self.request.match_info['ref']
        self.payload['ref'] = fullref
        self.jenkins_yml = yield from GITHUB.fetch_file_contents(
            self.repository, 'jenkins.yml', ref=fullref
        )

    @asyncio.coroutine
    def get(self):
        self.payload = dict()
        self.payload['repository'] = r = dict(
            owner=self.request.match_info['owner'],
            name=self.request.match_info['repository'],
        )
        self.repository = '%(owner)s/%(name)s' % self.payload['repository']
        loop = asyncio.get_event_loop()
        tasks = [
            loop.create_task(self.statuses_task()),
            loop.create_task(self.stages_task()),
        ]
        yield from asyncio.gather(*tasks)
        jenkins_yml = yaml.load(self.jenkins_yml)
        settings = jenkins_yml.get('settings', {})
        stages = settings.get('stages', ['build', 'test', 'deploy'])
        pipeline = Pipeline.from_yaml(
            stages, trim_prefixes=[
                r['owner'], r['owner'].lower(),
                r['name'], r['name'].lower(),
            ])
        pipeline.add_specs(*JobSpec.parse_all(self.jenkins_yml))
        statuses = [CommitStatus(s) for s in self.statuses]
        pipeline.process_statuses(*statuses)
        self.payload['stages'] = pipeline.to_json()
        return web.json_response(self.payload)


app.router.add_route(
    '*', '/rest/pipeline/{owner}/{repository}/{ref:[^{}]+}',
    PipelineView, name='pipeline',
)


@asyncio.coroutine
def heads(request):
    payload = dict(branches=[], tags=[])
    repository = yield from Repository.from_name(
        request.match_info['owner'], request.match_info['name'],
    )
    branches = yield from repository.fetch_protected_branches()
    for branch in branches:
        payload['branches'].append(dict(
            name=branch['name'],
            fullref='refs/heads/' + branch['name'],
        ))

    return web.json_response(payload)


app.router.add_get('/rest/heads/{owner}/{name}/', heads, name='heads')


@asyncio.coroutine
def repositories(request):
    payload = []
    for entry in REPOSITORIES:
        owner, name = entry.split('/')
        payload.append(dict(
            owner=owner,
            name=name,
        ))
    payload = sorted(
        payload,
        key=lambda d: (d['owner'], d['name'])
    )
    return web.json_response(payload)


app.router.add_get('/rest/repositories/', repositories, name='repositories')


@asyncio.coroutine
def register_webhook():
    futures = []
    for qualname in REPOSITORIES:
        future = RegisterTask(qualname)
        futures.append(future)
        yield from WORKERS.enqueue(future)
    yield from WORKERS.queue.join()
    return futures


class RegisterTask(Task):
    def __init__(self, qualname):
        super(RegisterTask, self).__init__()
        self.qualname = qualname

    @asyncio.coroutine
    def __call__(self):
        webhook_url = fullurl(route='github-webhook')
        webhook = WebHook({
            "name": "web",
            "active": True,
            "events": [
                "issue_comment",
                "pull_request",
                "push",
            ],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "insecure_ssl": "0",
                "secret": SETTINGS.GITHUB_SECRET,
            }
        })

        owner, name = self.qualname.split('/')
        repository = yield from Repository.from_name(owner, name)
        payload = yield from repository.fetch_hooks()
        hooks = repository.process_hooks(payload, webhook_url)
        hookid = None
        for hook in hooks:
            if hook == webhook:
                logger.info("Webhook for %s uptodate.", repository)
                return
            else:
                hookid = hook['id']
                break
        yield from repository.set_hook(webhook, hookid=hookid)


def fullurl(route='simple-webhook', **query):
    return (
        SETTINGS.SERVER_URL.rstrip('/') +
        str(app.router[route].url_for().with_query(query))
    )
