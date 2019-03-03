#!/usr/bin/env python2

from __future__ import print_function
import os
import subprocess
import json
import re
import argparse
from collections import namedtuple
import sys
from datetime import datetime
from string import Formatter
from functools import partial
import collections
import traceback
try:
    import yaml
except ImportError:
    yaml = None

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class AttributeDict(dict):
    def __getattr__(self, item):
        return self[item]

def attribute_dict(orig):
    d = dict(orig)
    for k,v in d.iteritems():
        if isinstance(v, collections.Mapping):
            d[k] = attribute_dict(v)
    return AttributeDict(d)

def map_or_single(fn, list_or_single):
    if isinstance(list_or_single, list):
        return map(fn, list_or_single)
    else:
        return fn(list_or_single)

class Context:
    def __init__(self, cmds, vars, verbose):
        self.cmds = cmds
        self.vars = attribute_dict(vars)
        self.verbose = verbose
        self.formatter = Formatter()

    def eval(self, path):
        if isinstance(path, basestring):
            return self.formatter.vformat(path, self.cmds, self.vars)
        else:
            return path.execute(self)

    def verbose_log(self, ast):
        if self.verbose > 0:
            eprint(datetime.now(), self.to_string(ast))

    @staticmethod
    def to_string(x):
        if hasattr(x, 'to_string'):
            return x.to_string()
        else:
            return x

class Ast:
    class True:
        def execute(self, ctx):
            ctx.verbose_log(self)
            return True
        def to_string(self):
            return 'ast.True'

    class False:
        def execute(self, ctx):
            ctx.verbose_log(self)
            return False
        def to_string(self):
            return 'ast.False'

    class Echo:
        def __init__(self, msg):
            self.msg = msg
        def execute(self, ctx):
            ctx.verbose_log(self)
            print(ctx.eval(self.msg))
        def to_string(self):
            return 'echo ({})'.format(Context.to_string(self.msg))

    class ShellExec:
        def __init__(self, cmd):
            self.cmd = cmd
        def execute(self, ctx):
            ctx.verbose_log(self)
            p = subprocess.Popen(self.cmd, shell = True, stdout = subprocess.PIPE)
            stdout, _ = p.communicate()
            p.wait()
            return stdout.strip()
        def to_string(self):
            return 'shellExec ({})'.format(self.cmd)

    class Assign:
        def __init__(self, path, value):
            self.path = path
            self.value = value
        def execute(self, ctx):
            ctx.verbose_log(self)
            evaled = ctx.eval(self.value)
            ctx.vars['usr'][self.path] = evaled
            return evaled
        def to_string(self):
            return 'assign ({} := {})'.format(self.path, Context.to_string(self.value))

    class Match:
        def __init__(self, pattern, expr):
            self.pattern = pattern
            self.expr = expr
        def execute(self, ctx):
            ctx.verbose_log(self)
            return re.search(self.pattern, ctx.eval(self.expr)) is not None
        def to_string(self):
            return '{} match /{}/'.format(ctx.to_string(self.expr), ctx.to_string(self.pattern))

    class Equal:
        def __init__(self, items):
            self.items = items
        def execute(self, ctx):
            ctx.verbose_log(self)
            return reduce(lambda l,r: l == r, map(ctx.eval, self.items))
        def to_string(self):
            return '({})'.format(' == '.join(map(Context.to_string, self.items)))

    class Not:
        def __init__(self, inner):
            self.inner = inner
        def execute(self, ctx):
            ctx.verbose_log(self)
            return not self.inner.execute(ctx) == True
        def to_string(self):
            return 'not ({})'.format(self.inner.to_string())

    class And:
        def __init__(self, items):
            self.items = items
        def execute(self, ctx):
            ctx.verbose_log(self)
            return reduce(lambda l,r: l and r, map(lambda x: x.execute(ctx), self.items))
        def to_string(self):
            return '({})'.format(' and '.join(map(Context.to_string, self.items)))

    class Or:
        def __init__(self, items):
            self.items = items
        def execute(self, ctx):
            ctx.verbose_log(self)
            return reduce(lambda l,r: l or r, map(lambda x: x.execute(ctx), self.items))
        def to_string(self):
            return '({})'.format(' and '.join(map(Context.to_string, self.items)))

    class RequirementNotMet(Exception):
        pass
    class Require:
        def __init__(self, predicate):
            self.predicate = predicate
        def execute(self, ctx):
            ctx.verbose_log(self)
            if not self.predicate.execute(ctx):
                raise Ast.RequirementNotMet(self.to_string())
            return ctx
        def to_string(self):
            return 'require ({})'.format(self.predicate.to_string())

    class If:
        def __init__(self, condition, thens, elses):
            self.condition = condition
            self.thens = thens
            self.elses = elses
        def execute(self, ctx):
            ctx.verbose_log(self)
            if self.condition.execute(ctx):
                return map_or_single(lambda x: ctx.eval(x), self.thens) if self.thens is not None else None
            else:
                return map_or_single(lambda x: ctx.eval(x), self.elses) if self.elses is not None else None
        def to_string(self):
            return 'if ({}) then ({}) else ({})'.format(self.condition.to_string(), [t.to_string() for t in self.thens], [t.to_string() for t in self.elses])

class AstParser:
    class ParseException(Exception):
        pass

    @staticmethod
    def parse_match(json):
        pattern = json.keys()[0]
        expr = AstParser.parse_or_str(json[pattern], AstParser.parse_pipeline_item)
        return Ast.Match(pattern, expr)

    @staticmethod
    def parse_not(json):
        return Ast.Not(AstParser.parse_predicate(json))

    @staticmethod
    def parse_predicate(json):
        if json == True:
            return Ast.True()
        elif json == False:
            return Ast.False()

        type_name = json.keys()[0]
        definition = json[type_name]

        if type_name == 'and':
            return Ast.And(map(AstParser.parse_predicate, definition))
        elif type_name == 'or':
            return Ast.Or(map(AstParser.parse_predicate, definition))
        elif type_name == 'not':
            return AstParser.parse_not(definition)
        elif type_name == 'match':
            return AstParser.parse_match(definition)
        elif type_name in {'equal', 'eq', '=='}:
            return Ast.Equal(definition)
        elif type_name in {'neq', '!='}:
            return Ast.Not(Ast.Equal(definition))
        else:
            raise AstParser.ParseException('unknown predicate of type "{}"'.format(type_name))

    @staticmethod
    def parse_if(json):
        condition = AstParser.parse_predicate(json['condition'])
        thens = AstParser.parse_or_str(json['then'], lambda x: map_or_single(AstParser.parse_pipeline_item, x)) if 'then' in json else None
        elses = AstParser.parse_or_str(json['else'], lambda x: map_or_single(AstParser.parse_pipeline_item, x)) if 'else' in json else None
        return Ast.If(condition, thens, elses)

    @staticmethod
    def parse_or_str(json, parser):
        if isinstance(json, basestring):
            return json
        else:
            return parser(json)

    @staticmethod
    def parse_pipeline_item(json):
        type_name = json.keys()[0]
        definition = json[type_name]

        if type_name == 'require':
            return Ast.Require(AstParser.parse_predicate(definition))
        elif type_name == 'if':
            return AstParser.parse_if(definition)
        elif type_name == 'echo':
            return Ast.Echo(AstParser.parse_or_str(definition, lambda j: AstParser.parse_pipeline_item(j)))
        elif type_name == 'shell':
            return Ast.ShellExec(json.values()[0])
        elif type_name == 'assign':
            return Ast.Assign(definition.keys()[0], AstParser.parse_or_str(definition.values()[0], lambda j: AstParser.parse_pipeline_item(j)))
        else:
            raise AstParser.ParseException('unknown pipeline step "{}"'.format(type_name))

parser = argparse.ArgumentParser()
def parse_bool(name, v):
    if v == 'true' or v == 'True':
        return True
    elif v == 'false' or v == 'False':
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected for {}, found "{}"'.format(name, v))
config_group = parser.add_mutually_exclusive_group()
config_group.add_argument('--config', required=False, default=None)
config_group.add_argument('--config-file', required=False, default=None)
parser.add_argument('--force', type=partial(parse_bool, 'force'), nargs='?', const=True, required=False, default=False)
parser.add_argument('--verbose', type=partial(parse_bool, 'verbose'), nargs='?', const=True, required=False, default=False)

clictl_args = sys.argv[1:]
other_args = []
if '--' in clictl_args:
    other_args = clictl_args[clictl_args.index('--')+1:]
    clictl_args = clictl_args[:clictl_args.index('--')]
args = parser.parse_args(clictl_args)
cmds = other_args


Config = namedtuple('Config', ['before', 'pipeline', 'after'])

def parse_config(json):

    before = map(AstParser.parse_pipeline_item, json['before']) if 'before' in json else None
    pipeline = map(AstParser.parse_pipeline_item, json['pipeline']) if 'pipeline' in json else None
    after = map(AstParser.parse_pipeline_item, json['after']) if 'after' in json else None

    if ( not before and
         not pipeline and
         not after ):
        if isinstance(json, collections.Mapping) and len(json.keys()) > 0:
            pipeline = [ AstParser.parse_pipeline_item(json) ]
        elif isinstance(json, list):
            pipeline = map(AstParser.parse_pipeline_item, json)

    return Config(before = before or [], pipeline = pipeline or [], after = after or [])

if args.config_file:
    with open(args.config_file) as f:
        config_json = yaml.load(f)
        if config_json is None:
            eprint('Invalid config file')
            sys.exit(2)
elif args.config:
    config_json = yaml.load(args.config)
    if config_json is None:
        eprint('Invalid config')
        sys.exit(2)
else:
    config_json = None

try:
    if config_json is not None:
        config = parse_config(config_json)
    else:
        config = Config([], [])

except AstParser.ParseException as e:
    if args.verbose:
        traceback.print_exc()
    eprint('Invalid configuration:', e.message)
    sys.exit(2)

vars = {
    "args": cmds,
    "env": os.environ,
    "usr": {},
    "config": {
        "force": args.force is True
    }
}

ctx = Context(cmds, vars, 1 if args.verbose else 0)

try:
    for b in config.before:
        b.execute(ctx)

    for p in config.pipeline:
        p.execute(ctx)

    for b in config.after:
        b.execute(ctx)

except Ast.RequirementNotMet as e:
    if args.verbose:
        traceback.print_exc()
    eprint('Requirement not met:', e.message)
    sys.exit(2)
except Exception as e:
    eprint('Error in pipeline:', str(e))
    traceback.print_exc()
    sys.exit(2)


if len(cmds) > 0:
    p = subprocess.Popen(cmds, bufsize=4029, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    p.communicate()
    exitCode = p.wait()
    sys.exit(exitCode)
