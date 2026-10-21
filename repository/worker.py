"""One JSON call per isolated process. No evaluator assertions or expected answers."""
import importlib
import json
from pathlib import Path
import sys
import types
import typing
sys.dont_write_bytecode = True
sys.pycache_prefix = '/__review_pushback_unused_cache__'


def normalize(value):
    if isinstance(value, bytes):
        return value.decode('utf-8')
    if isinstance(value, (str, int, float, bool, type(None), dict)):
        return value
    return [normalize(item) for item in value]


def invoke(root, request):
    sys.path.insert(0, str(root))
    # The pinned pydash uses only typing_extensions.Protocol. Python 3.11+
    # supplies the same API in typing; keep this compatibility layer explicit.
    if request['call'].get('module') == 'pydash':
        compatibility = types.ModuleType('typing_extensions')
        compatibility.Protocol = typing.Protocol
        sys.modules['typing_extensions'] = compatibility
    args = request['args']
    if request['call']['kind'] == 'call':
        function = getattr(importlib.import_module(request['call']['module']), request['call']['function'])
        return normalize(function(*args))
    from itsdangerous import Signer
    kind = request['call']['kind']
    if kind == 'roundtrip':
        signer = Signer('public-test-key')
        return signer.unsign(signer.sign(args[0])).decode('utf-8')
    if kind == 'newest':
        keys = ['new'] if args[1] == 'single' else ['old', 'new']
        return Signer('new').validate(Signer(keys).sign(args[0]))
    if kind == 'rotation':
        return Signer(['old', 'new']).validate(Signer(args[1]).sign(args[0]))
    if kind == 'tamper':
        signer = Signer('public-test-key')
        token = signer.sign(args[0])
        changed = args[1].encode() + b'.' + token.rsplit(b'.', 1)[1]
        return signer.validate(changed)
    raise ValueError('Unknown call kind')


if __name__ == '__main__':
    request = json.load(sys.stdin)
    try:
        result = {'value': invoke(Path(sys.argv[1]), request)}
    except Exception as error:
        result = {'error': type(error).__name__}
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
