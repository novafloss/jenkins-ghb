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

from collections import OrderedDict
import logging
from string import ascii_letters

from .repository import CommitStatus


logger = logging.getLogger(__name__)


class Pipeline(object):
    def __init__(self, stages=None, trim_prefixes=[]):
        self.stages = stages or OrderedDict()
        self.default_stage = (
            'test'
            if 'test' in self.stages else
            list(self.stages.keys())[0]
        )
        self.trim_prefixes = trim_prefixes

    @classmethod
    def from_yaml(cls, stages=[], trim_prefixes=[]):
        stages = [Stage.factory(s, trim_prefixes) for s in stages]
        return cls(
            stages=OrderedDict([[s.name, s] for s in stages]),
            trim_prefixes=trim_prefixes,
        )

    def add_specs(self, *specs):
        for spec in specs:
            if spec.config.get('periodic') and not spec.config.get('stage'):
                logger.debug("Skipping %s with no explicit stage.", spec)
                continue
            stage = spec.config.get('stage', self.default_stage)
            self.stages[stage].jobs.append(spec)

    def process_statuses(self, *statuses):
        stages_map = {}
        for stage in self.stages.values():
            for context in stage.iter_contextes():
                stages_map[context] = stage
        status_map = {}
        for status in statuses:
            try:
                stage = stages_map.pop(status['context'])
                mapping = stage.statuses
            except KeyError:
                mapping = status_map

            current = mapping.setdefault(
                status['context'], status
            )
            if status.get('updated_at', 0) > current.get('updated_at', 0):
                mapping[status['context']] = status

        missing_statuses = list(stages_map.keys())
        # Assign other status by prefix
        for context, stage in stages_map.items():
            for status in status_map.values():
                if not status['context'].startswith(context):
                    continue
                stage.statuses[status['context']] = status
                if context in missing_statuses:
                    missing_statuses.remove(context)
            if context in missing_statuses:
                stage.statuses[context] = CommitStatus(
                    context=context, state='unknown',
                )

    def to_json(self):
        return [stage.to_json() for stage in self.stages.values()]


class Stage(object):
    @classmethod
    def factory(cls, entry, trim_prefixes):
        if isinstance(entry, str):
            entry = dict(name=entry)
        return cls(trim_prefixes=trim_prefixes, **entry)

    def __init__(self, name, external=None, trim_prefixes=None, **kw):
        self.name = name
        self.jobs = []
        self.external_contextes = external or []
        self.statuses = {}
        self.trim_prefixes = trim_prefixes

    def __bool__(self):
        return bool(self.jobs or self.external_contextes)

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.name)

    def __str__(self):
        return self.name

    @property
    def state(self):
        states = {status['state'] for status in self.statuses.values()}
        if 'error' in states:
            return 'error'
        elif 'failure' in states:
            return 'failure'
        elif 'pending' in states:
            return 'pending'
        elif states == {'success'}:
            return 'success'
        else:
            return 'unknown'

    def iter_contextes(self):
        yield from self.external_contextes
        for job in self.jobs:
            yield job.name

    def trim_context(self, context):
        context = context.strip('-/_')
        prefixes = self.trim_prefixes + [self.name]
        for prefix in prefixes:
            if not context.startswith(prefix):
                continue
            if context[len(prefix):][0] in ascii_letters:
                continue
            return self.trim_context(context[len(prefix):])
        return context

    def to_json(self):
        return dict(
            name=self.name,
            state=self.state,
            statuses=[
                dict(name=self.trim_context(s['context']), state=s['state'])
                for s in sorted(self.statuses.values())
            ]
        )
