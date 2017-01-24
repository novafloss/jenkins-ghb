import logging
import os.path

from aiohttp import web


logger = logging.getLogger(__name__)


def main_view(request):
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


def pipeline_view(request):
    return web.json_response(dict(
        repository=dict(owner='bersace', name='bacasable'),
        ref='master',
        tree_url='https://github.com/bersace/bacasable/tree/master',
        message_html="Implement OptOut",
        diff=dict(files=7, additions=43, deletions=8),
        stages=[
            dict(
                name='test', state='success',
                time='',
                jobs=[
                    dict(name='ansible', state='success'),
                    dict(name='django', state='success'),
                    dict(name='doc', state='success'),
                    dict(name='lint', state='success'),
                    dict(name='pr', state='success'),
                    dict(name='units', state='success'),
                ],
            ),
            dict(
                name='integration', state='success',
                time='20h',
                jobs=[
                    dict(name='doc', state='success'),
                    dict(name='deploy', state='success'),
                    dict(name='tests', state='success'),
                ],
            ),
            dict(
                name='qualif', state='pending',
                time='3w',
                jobs=[
                    dict(name='perf-short', state='pending'),
                    dict(name='deploy', state='success'),
                    dict(name='perf-valid', state='success'),
                    dict(name='perf-long', state='unknown'),
                ],
            ),
            dict(
                name='live', state='unknown',
                time='',
                jobs=[
                    dict(name='staging-eu', state='unknown'),
                    dict(name='staging-us', state='unknown'),
                    dict(name='prod-eu', state='unknown'),
                    dict(name='prod-us', state='unknown'),
                ],
            ),
        ],
    ))


def repositories_view(request):
    return web.json_response([
        dict(
            owner='bersace',
            name='bacasable' + str(i),
            description_html='Description HTML.',
        )
        for i in range(17)
    ])


def heads_view(request):
    return web.json_response(dict(
        branches=[
            dict(name='master', ref='refs/heads/master', state='pending'),
            dict(name='stable', ref='refs/heads/stable', state='success'),
        ],
        tags=[
            dict(name='16.10.0', ref='refs/tags/16.10.0', state='pending'),
            dict(name='16.9.1', ref='refs/tags/16.9.1', state='success'),
            dict(
                name='16.10.0rc4', ref='refs/tags/16.10.0rc4',
                state='success',
            ),
            dict(
                name='16.10.0rc3', ref='refs/tags/16.10.0rc3',
                state='success',
            ),
        ],
    ))

dashboard = app = web.Application()
app.router.add_get(
    '/',
    handler=main_view)
app.router.add_get(
    '/rest/repositories/',
    handler=repositories_view)
app.router.add_get(
    '/rest/heads/{owner}/{repository}',
    handler=heads_view)
app.router.add_get(
    '/rest/pipeline/{owner}/{repository}/{ref:[^{}]+}',
    handler=pipeline_view)
app.router.add_static(
    '/static/', name='static',
    path=os.path.realpath(os.path.join(os.path.dirname(__file__), 'static'))
)
del app
