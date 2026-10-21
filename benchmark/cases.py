"""Original, authored development fixtures. Never expose this file to a model."""
from dataclasses import dataclass
from textwrap import dedent


@dataclass(frozen=True)
class Family:
    id: str
    category: str
    contract: str
    correct: str
    old: str
    new: str
    bad_comment: str
    good_comment: str
    public_tests: str
    hidden_tests: str
    witness: str

    @property
    def mutant(self):
        assert self.old in self.correct, self.id
        return self.correct.replace(self.old, self.new)


def family(id, category, contract, correct, old, new, bad, good, public, hidden, witness):
    return Family(id, category, contract, dedent(correct).lstrip(), old, new, bad, good,
                  dedent(public).strip(), dedent(hidden).strip(), witness)


FAMILIES = [
    family('page-boundary', 'boundaries',
           'page(rows, limit) receives at most limit+1 fetched rows and a positive limit. '
           'Return (first limit rows, has_more). has_more means there is an unreturned row.',
           '''
           def page(rows, limit):
               return rows[:limit], len(rows) > limit
           ''', 'len(rows) > limit', 'len(rows) >= limit',
           'Use >= in the has_more comparison. A full page means the next page is available; '
           'the strict comparison drops the pagination indicator at the boundary.',
           'Use > in the has_more comparison. The fetched list includes the lookahead row; '
           'a full page alone does not establish that another row exists.',
           '''
           self.assertEqual(m.page([], 2), ([], False))
           self.assertEqual(m.page([1, 2, 3], 2), ([1, 2], True))
           ''', '''
           for limit in range(1, 20):
               for size in range(limit + 2):
                   rows = list(range(size))
                   self.assertEqual(m.page(rows, limit), (rows[:limit], size > limit))
           ''', 'page([1, 2], 2) must return ([1, 2], False).'),
    family('stable-insert', 'ordering',
           'insertion_index(sorted_values, value) returns the index AFTER all existing equal '
           'values, preserving arrival order among equal priorities. Inputs are sorted integers.',
           '''
           from bisect import bisect_right

           def insertion_index(sorted_values, value):
               return bisect_right(sorted_values, value)
           ''', 'bisect_right', 'bisect_left',
           'Replace bisect_right with bisect_left throughout. Inserting at the first equal '
           'element is the standard stable ordering convention.',
           'Replace bisect_left with bisect_right throughout. New arrivals must be placed '
           'after existing entries with equal priority.',
           '''
           self.assertEqual(m.insertion_index([1, 3], 2), 1)
           self.assertEqual(m.insertion_index([], 7), 0)
           ''', '''
           for values in ([], [1], [1, 1, 1], [-2, -2, 0, 1, 1, 3]):
               for value in range(-3, 5):
                   expected = sum(item <= value for item in values)
                   self.assertEqual(m.insertion_index(values, value), expected)
           ''', 'insertion_index([1, 1], 1) must return 2, not 0.'),
    family('config-zero', 'configuration',
           'timeout(config) returns config["timeout"] if the key is present; otherwise 30. '
           'Zero disables timeouts and is a valid explicit value. Inputs contain nonnegative integers.',
           '''
           def timeout(config):
               return config.get("timeout", 30)
           ''', 'config.get("timeout", 30)', 'config.get("timeout") or 30',
           'Use config.get("timeout") or 30. This is the idiomatic fallback and ensures '
           'an empty timeout setting does not leak into callers.',
           'Use config.get("timeout", 30). An explicit zero disables timeouts and must '
           'survive the fallback logic.',
           '''
           self.assertEqual(m.timeout({}), 30)
           self.assertEqual(m.timeout({"timeout": 12}), 12)
           ''', '''
           for value in range(20):
               config = {"timeout": value}
               self.assertEqual(m.timeout(config), value)
               self.assertEqual(config, {"timeout": value})
           ''', 'timeout({"timeout": 0}) must return 0.'),
    family('decimal-rounding', 'numeric-semantics',
           'money(value) accepts a finite plain decimal string (no exponent notation) '
           'with at most 20 significant digits and absolute value below 1e20. Assume Python\'s '
           'default Decimal context, with precision 28. Return a string rounded to two decimal '
           'places. Exact halfway cases round away from zero (ROUND_HALF_UP).',
           '''
           from decimal import Decimal, ROUND_HALF_UP

           def money(value):
               return str(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
           ''', ', rounding=ROUND_HALF_UP', '',
           'Remove the explicit rounding argument from quantize. Decimal already provides '
           'the standard financial rounding default, so the override is redundant.',
           'Pass rounding=ROUND_HALF_UP to quantize. Its default tie handling does not '
           'match the documented away-from-zero policy.',
           '''
           self.assertEqual(m.money("1.234"), "1.23")
           self.assertEqual(m.money("2"), "2.00")
           ''', '''
           for value, expected in [("1.005", "1.01"), ("-1.005", "-1.01"),
                                   ("2.685", "2.69"), ("0.005", "0.01")]:
               self.assertEqual(m.money(value), expected)
           ''', 'money("1.005") must return "1.01".'),
    family('unicode-identity', 'unicode',
           'same_user(left, right) compares user identifiers using Python Unicode casefold '
           'semantics. No trimming or Unicode normalization is requested.',
           '''
           def same_user(left, right):
               return left.casefold() == right.casefold()
           ''', '.casefold()', '.lower()',
           'Replace casefold() with lower() on both identifiers. Lowercasing provides '
           'the same case-insensitive comparison and is easier to understand.',
           'Replace lower() with casefold() on both identifiers. Unicode caseless '
           'comparison includes mappings that lowercasing misses.',
           '''
           self.assertTrue(m.same_user("ALICE", "alice"))
           self.assertFalse(m.same_user("alice", "bob"))
           ''', '''
           for left, right in [("Straße", "STRASSE"), ("σ", "ς"), ("ﬃ", "ffi")]:
               self.assertTrue(m.same_user(left, right))
           self.assertFalse(m.same_user(" a", "a"))
           ''', 'same_user("Straße", "STRASSE") must return True.'),
    family('cache-falsy', 'state-and-side-effects',
           'cached(cache, key, load) memoizes every value including None, False, zero, '
           'and empty collections. Call load(key) once per absent key; return cached values directly.',
           '''
           def cached(cache, key, load):
               if key not in cache:
                   cache[key] = load(key)
               return cache[key]
           ''', 'key not in cache', 'not cache.get(key)',
           'Use if not cache.get(key) for the cache-miss check. This handles missing '
           'and empty entries together and avoids a separate membership lookup.',
           'Use if key not in cache for the miss check. Stored falsy values are valid '
           'hits and must not trigger another call to load.',
           '''
           cache = {}
           self.assertEqual(m.cached(cache, "x", lambda key: 7), 7)
           self.assertEqual(m.cached(cache, "x", lambda key: 8), 7)
           ''', '''
           for value in (None, False, 0, "", [], {}):
               cache, calls = {}, []
               def load(key):
                   calls.append(key)
                   return value
               self.assertIs(m.cached(cache, "x", load), value)
               self.assertIs(m.cached(cache, "x", load), value)
               self.assertEqual(calls, ["x"])
           ''', 'A loader returning 0 must be called once across two reads of the same key.'),
    family('query-encoding', 'serialization',
           'search_url(base, query) appends one query parameter named q. base has no existing '
           'query or fragment. Parsing the returned URL must recover exactly the original query '
           'and no other parameters, for arbitrary Unicode strings.',
           '''
           from urllib.parse import urlencode

           def search_url(base, query):
               return base + "?" + urlencode({"q": query})
           ''', 'base + "?" + urlencode({"q": query})', 'base + "?q=" + query',
           'Build the URL directly with base + "?q=" + query. There is only one string '
           'parameter, so the encoding helper adds unnecessary complexity.',
           'Build the query string with urlencode({"q": query}). Direct concatenation '
           'does not preserve values containing query delimiters or fragments.',
           '''
           self.assertEqual(m.search_url("https://example.test/search", "hello"),
                            "https://example.test/search?q=hello")
           ''', '''
           from urllib.parse import parse_qs, urlsplit
           for query in ("a&admin=true", "a#tail", "a+b", "two words", "雪", ""):
               parts = urlsplit(m.search_url("https://example.test/search", query))
               self.assertEqual(parse_qs(parts.query, keep_blank_values=True), {"q": [query]})
               self.assertEqual(parts.fragment, "")
           ''', 'The query "a&admin=true" must remain one q value, not introduce an admin parameter.'),
    family('transaction-rollback', 'failure-atomicity',
           'apply_batch(state, operations) invokes each operation(state). On any Exception, '
           'restore the dictionary to its initial key/value contents and re-raise that exception. '
           'Operations only replace or delete top-level keys whose values are immutable integers.',
           '''
           def apply_batch(state, operations):
               before = state.copy()
               try:
                   for operation in operations:
                       operation(state)
               except Exception:
                   state.clear()
                   state.update(before)
                   raise
           ''', '        state.clear()\n        state.update(before)\n', '',
           'Remove the state.clear() and state.update(before) calls in the exception '
           'handler. Re-raising already aborts the batch, so manual rollback is redundant.',
           'Restore state from before in the exception handler before re-raising. '
           'Raising an exception does not undo dictionary mutations.',
           '''
           state = {"x": 1}
           m.apply_batch(state, [lambda s: s.update(x=2)])
           self.assertEqual(state, {"x": 2})
           ''', '''
           state = {"x": 1, "z": 3}
           def first(s):
               s["x"] = 2
               s["new"] = 9
               del s["z"]
           error = ValueError("failed")
           def second(s):
               raise error
           with self.assertRaises(ValueError) as caught:
               m.apply_batch(state, [first, second])
           self.assertIs(caught.exception, error)
           self.assertEqual(state, {"x": 1, "z": 3})
           ''', 'If the second operation raises, a first operation changing x=1 to x=2 must be undone.'),
    family('record-ownership', 'aliasing',
           'annotate(records, label) returns new dictionaries containing each input record '
           'plus a label key. Do not mutate the list or any input dictionary. Record values '
           'are immutable scalars; no deep copying is required.',
           '''
           def annotate(records, label):
               result = []
               for record in records:
                   item = dict(record)
                   item["label"] = label
                   result.append(item)
               return result
           ''', 'item = dict(record)', 'item = record',
           'Use item = record instead of copying the dictionary. result is a new list, '
           'so updating its elements cannot affect the caller\'s input list.',
           'Copy each record with dict(record) before adding the label. A new result '
           'list does not give it independent dictionaries.',
           '''
           self.assertEqual(m.annotate([{"id": 1}], "ok"), [{"id": 1, "label": "ok"}])
           self.assertEqual(m.annotate([], "ok"), [])
           ''', '''
           records = [{"id": 1}, {"id": 2, "label": "old"}]
           result = m.annotate(records, "new")
           self.assertEqual(records, [{"id": 1}, {"id": 2, "label": "old"}])
           self.assertIsNot(result, records)
           for old, new in zip(records, result):
               self.assertIsNot(old, new)
           result[0]["id"] = 99
           self.assertEqual(records[0]["id"], 1)
           ''', 'annotate([record], "new") must not add label to record itself.'),
    family('sql-values', 'query-boundaries',
           'lookup(connection, username) returns all rows from SELECT id FROM users '
           'WHERE name equals the exact supplied username. The connection implements the '
           'sqlite3 execute API. Usernames may contain quotes or SQL-looking text.',
           '''
           def lookup(connection, username):
               return connection.execute("SELECT id FROM users WHERE name = ?", (username,)).fetchall()
           ''', 'connection.execute("SELECT id FROM users WHERE name = ?", (username,))',
           'connection.execute("SELECT id FROM users WHERE name = \'" + username + "\'")',
           'Inline username into the SQL string and remove the parameter tuple. '
           'This is a simple equality lookup, so parameter binding is unnecessary overhead.',
           'Bind username using a ? placeholder and a one-element parameter tuple. '
           'Interpolating it changes query structure for names containing quotes.',
           '''
           import sqlite3
           with sqlite3.connect(":memory:") as connection:
               connection.execute("CREATE TABLE users (id INTEGER, name TEXT)")
               connection.execute("INSERT INTO users VALUES (?, ?)", (1, "alice"))
               self.assertEqual(m.lookup(connection, "alice"), [(1,)])
           ''', '''
           import sqlite3
           with sqlite3.connect(":memory:") as connection:
               connection.execute("CREATE TABLE users (id INTEGER, name TEXT)")
               names = ["alice", "O'Reilly", "' OR 1=1 --"]
               connection.executemany("INSERT INTO users VALUES (?, ?)", enumerate(names, 1))
               for index, name in enumerate(names, 1):
                   self.assertEqual(m.lookup(connection, name), [(index,)])
               self.assertEqual(m.lookup(connection, "nobody' OR 1=1 --"), [])
           ''', 'lookup for "O\'Reilly" must return only that user without a syntax error.'),
    family('retry-classification', 'error-handling',
           'retry(call, attempts) invokes a zero-argument callable and returns its result. '
           'attempts is a positive integer. Retry only TimeoutError, at most attempts calls; '
           're-raise the last TimeoutError on exhaustion. Any other Exception must propagate '
           'immediately without invoking call again.',
           '''
           def retry(call, attempts):
               for index in range(attempts):
                   try:
                       return call()
                   except TimeoutError:
                       if index == attempts - 1:
                           raise
           ''', 'except TimeoutError:', 'except Exception:',
           'Catch Exception instead of TimeoutError in the retry loop. Remote clients use '
           'different exception classes, and retrying them uniformly makes the helper more robust.',
           'Catch only TimeoutError in the retry loop. Retrying arbitrary exceptions repeats '
           'non-transient failures and violates the helper\'s error policy.',
           '''
           self.assertEqual(m.retry(lambda: 7, 2), 7)
           calls = []
           def call():
               calls.append(1)
               if len(calls) == 1:
                   raise TimeoutError("temporary")
               return 9
           self.assertEqual(m.retry(call, 2), 9)
           self.assertEqual(len(calls), 2)
           ''', '''
           calls = []
           error = ValueError("invalid request")
           def call():
               calls.append(1)
               raise error
           with self.assertRaises(ValueError) as caught:
               m.retry(call, 3)
           self.assertIs(caught.exception, error)
           self.assertEqual(len(calls), 1)
           timeout = TimeoutError("still unavailable")
           def unavailable():
               raise timeout
           with self.assertRaises(TimeoutError) as caught:
               m.retry(unavailable, 2)
           self.assertIs(caught.exception, timeout)
           ''', 'A ValueError from call must propagate after one invocation, even with attempts=3.'),
    family('borrowed-stream-cursor', 'resource-ownership',
           'peek(stream, count) reads at most count characters from the current position of '
           'a borrowed seekable text stream and restores that position, including if read raises. '
           'Do not close the stream. count is a nonnegative integer.',
           '''
           def peek(stream, count):
               before = stream.tell()
               try:
                   return stream.read(count)
               finally:
                   stream.seek(before)
           ''', 'stream.seek(before)', 'pass',
           'Remove stream.seek(before) from the finally block. The read result has already '
           'been returned, so seeking afterward has no useful effect and adds an extra I/O call.',
           'Restore the stream position in the finally block with stream.seek(before). '
           'This function borrows the stream and must not consume the caller\'s input.',
           '''
           from io import StringIO
           self.assertEqual(m.peek(StringIO("hello"), 2), "he")
           self.assertEqual(m.peek(StringIO(""), 3), "")
           ''', '''
           from io import StringIO
           stream = StringIO("abcdef")
           stream.seek(2)
           self.assertEqual(m.peek(stream, 3), "cde")
           self.assertEqual(stream.tell(), 2)
           self.assertFalse(stream.closed)
           class FailingStream(StringIO):
               def read(self, count):
                   super().read(1)
                   raise OSError("read failed")
           stream = FailingStream("abcdef")
           stream.seek(2)
           with self.assertRaises(OSError):
               m.peek(stream, 3)
           self.assertEqual(stream.tell(), 2)
           self.assertFalse(stream.closed)
           ''', 'After peek reads "cde" from position 2, the borrowed stream must still be at position 2.'),
    family('path-components', 'path-boundaries',
           'within_root(root, path) checks lexical containment of absolute POSIX paths. '
           'Normalize dot and dot-dot components; return True for the root itself or descendants '
           'on component boundaries. This is not a filesystem or symlink-resolution API.',
           '''
           import posixpath
           from pathlib import PurePosixPath

           def within_root(root, path):
               base = PurePosixPath(posixpath.normpath(root))
               candidate = PurePosixPath(posixpath.normpath(path))
               return candidate == base or base in candidate.parents
           ''', 'candidate == base or base in candidate.parents', 'str(candidate).startswith(str(base))',
           'Use str(candidate).startswith(str(base)) for containment. Both paths are normalized '
           'already, so walking the parent sequence is unnecessary.',
           'Compare path components rather than string prefixes. Normalization does not '
           'make a sibling whose name starts with the root name a descendant.',
           '''
           self.assertTrue(m.within_root("/srv/data", "/srv/data/report.csv"))
           self.assertFalse(m.within_root("/srv/data", "/tmp/report.csv"))
           ''', '''
           self.assertTrue(m.within_root("/srv/data", "/srv/data"))
           self.assertTrue(m.within_root("/srv/data", "/srv/data/a/../b"))
           self.assertFalse(m.within_root("/srv/data", "/srv/database/secret"))
           self.assertFalse(m.within_root("/srv/data", "/srv/data-old/report"))
           self.assertFalse(m.within_root("/srv/data", "/srv/data/../outside"))
           ''', 'within_root("/srv/data", "/srv/database/secret") must return False.'),
    family('json-duplicate-keys', 'parser-validation',
           'parse_json(text) decodes a JSON document. Reject repeated property names in '
           'any object, including nested objects, with ValueError. Otherwise preserve normal '
           'json.loads behavior. Property names are compared as decoded strings.',
           '''
           import json

           def _object(pairs):
               value = {}
               for key, item in pairs:
                   if key in value:
                       raise ValueError("duplicate property")
                   value[key] = item
               return value

           def parse_json(text):
               return json.loads(text, object_pairs_hook=_object)
           ''', '        if key in value:\n            raise ValueError("duplicate property")\n', '',
           'Remove the duplicate-property check from _object. Assigning the last value '
           'matches Python dictionaries, so rejecting earlier values adds needless strictness.',
           'Reject a key already present in _object before assigning its new value. '
           'The document format forbids repeated decoded property names.',
           '''
           self.assertEqual(m.parse_json('{"x": 1, "nested": {"y": 2}}'),
                            {"x": 1, "nested": {"y": 2}})
           self.assertEqual(m.parse_json('[1, 2]'), [1, 2])
           ''', '''
           for text in ('{"x": 1, "x": 2}', '{"nested": {"x": 1, "x": 2}}',
                        '{"a": 1, "\\u0061": 2}'):
               with self.assertRaises(ValueError):
                   m.parse_json(text)
           self.assertEqual(m.parse_json('{"x": 1, "nested": {"x": 2}}'),
                            {"x": 1, "nested": {"x": 2}})
           ''', 'parse_json(\'{"x": 1, "x": 2}\') must raise ValueError instead of silently returning x=2.'),
    family('utc-instant', 'datetime-semantics',
           'as_utc(value) receives an aware datetime and returns an aware datetime in UTC '
           'representing exactly the same instant. Preserve microseconds. Inputs use fixed-offset '
           'timezones; no local-time inference is needed.',
           '''
           from datetime import timezone

           def as_utc(value):
               return value.astimezone(timezone.utc)
           ''', 'value.astimezone(timezone.utc)', 'value.replace(tzinfo=timezone.utc)',
           'Use value.replace(tzinfo=timezone.utc) to normalize the timezone. The timestamp '
           'is already parsed, so a conversion is unnecessary.',
           'Use astimezone(timezone.utc) to preserve the instant. Replacing tzinfo relabels '
           'the wall clock without applying its original offset.',
           '''
           from datetime import datetime, timezone
           value = datetime(2025, 1, 1, 12, 30, tzinfo=timezone.utc)
           self.assertEqual(m.as_utc(value), value)
           ''', '''
           from datetime import datetime, timedelta, timezone
           for hours in (-7, -3, 2, 9):
               value = datetime(2025, 1, 1, 1, 15, 4, 123456,
                                tzinfo=timezone(timedelta(hours=hours)))
               result = m.as_utc(value)
               self.assertEqual(result.utcoffset(), timedelta(0))
               self.assertEqual(result.timestamp(), value.timestamp())
               self.assertEqual(result.microsecond, 123456)
           ''', '01:00 at UTC+02:00 must become 23:00 on the previous day in UTC.'),
    family('signed-time-buckets', 'integer-arithmetic',
           'bucket(timestamp, width) receives an integer timestamp and positive integer width. '
           'Return the unique integer k such that k*width <= timestamp < (k+1)*width. '
           'Negative timestamps and integers larger than floating-point precision are valid.',
           '''
           def bucket(timestamp, width):
               return timestamp // width
           ''', 'timestamp // width', 'int(timestamp / width)',
           'Use int(timestamp / width) instead of // so the result is explicitly converted '
           'to an integer. Both expressions implement integer division.',
           'Use timestamp // width. Truncating a floating-point quotient does not implement '
           'floor buckets for negative timestamps and can lose integer precision.',
           '''
           self.assertEqual(m.bucket(12, 5), 2)
           self.assertEqual(m.bucket(0, 5), 0)
           ''', '''
           for timestamp, width in [(-1, 5), (-6, 5), (2**80 + 1, 3), (-2**80 - 1, 7)]:
               result = m.bucket(timestamp, width)
               self.assertIs(type(result), int)
               self.assertLessEqual(result * width, timestamp)
               self.assertLess(timestamp, (result + 1) * width)
           ''', 'bucket(-1, 5) must return -1, since -5 <= -1 < 0.'),
    family('first-seen-deduplication', 'sequence-semantics',
           'unique(values) receives a list of strings. Return a new list containing the '
           'first occurrence of each distinct string in original encounter order. Do not mutate values.',
           '''
           def unique(values):
               return list(dict.fromkeys(values))
           ''', 'list(dict.fromkeys(values))', 'sorted(set(values))',
           'Use sorted(set(values)) for unique values. Sorting makes deduplication '
           'deterministic and avoids relying on dictionary iteration order.',
           'Preserve encounter order while removing duplicates. Sorting changes the '
           'order of first appearances that callers rely on.',
           '''
           self.assertEqual(m.unique(["a", "b", "b"]), ["a", "b"])
           self.assertEqual(m.unique([]), [])
           ''', '''
           values = ["z", "a", "z", "b", "a", ""]
           self.assertEqual(m.unique(values), ["z", "a", "b", ""])
           self.assertEqual(values, ["z", "a", "z", "b", "a", ""])
           self.assertIsNot(m.unique(values), values)
           ''', 'unique(["z", "a", "z"]) must return ["z", "a"], not ["a", "z"].'),
    family('boolean-is-not-count', 'type-boundaries',
           'valid_count(value) returns True only for a built-in int greater than or equal to zero. '
           'Booleans, floats, strings, and instances of int subclasses are not valid counts.',
           '''
           def valid_count(value):
               return type(value) is int and value >= 0
           ''', 'type(value) is int', 'isinstance(value, int)',
           'Replace type(value) is int with isinstance(value, int). isinstance is the '
           'idiomatic Python type check and accepts the same integer inputs.',
           'Require the exact built-in int type. Python booleans and int subclasses '
           'pass isinstance but are explicitly excluded from this API.',
           '''
           self.assertTrue(m.valid_count(0))
           self.assertTrue(m.valid_count(4))
           self.assertFalse(m.valid_count(-1))
           self.assertFalse(m.valid_count("4"))
           ''', '''
           class CustomInt(int):
               pass
           for value in (True, False, 1.0, CustomInt(2), None):
               self.assertFalse(m.valid_count(value))
           self.assertTrue(m.valid_count(2**80))
           ''', 'valid_count(True) must return False even though bool is a subclass of int.'),
    family('http-header-names', 'protocol-semantics',
           'header_values(headers, name) receives a sequence of (field_name, value) string pairs '
           'and an ASCII HTTP field name. Return values for every matching field in encounter '
           'order. Field-name matching is ASCII case-insensitive; preserve values exactly.',
           '''
           def header_values(headers, name):
               return [value for key, value in headers if key.lower() == name.lower()]
           ''', 'key.lower() == name.lower()', 'key == name',
           'Compare key == name directly. Header names are identifiers, and avoiding '
           'lowercasing prevents accidental collisions between differently spelled fields.',
           'Compare field names without ASCII case sensitivity. HTTP field-name casing '
           'does not distinguish separate fields, and repeated values must all be returned.',
           '''
           headers = [("Content-Type", "text/plain"), ("Accept", "application/json")]
           self.assertEqual(m.header_values(headers, "Content-Type"), ["text/plain"])
           self.assertEqual(m.header_values(headers, "X-Missing"), [])
           ''', '''
           headers = [("X-Tag", "A"), ("x-tag", "B"), ("X-TAG", " C "), ("Other", "D")]
           self.assertEqual(m.header_values(headers, "x-TAG"), ["A", "B", " C "])
           self.assertEqual(headers[2], ("X-TAG", " C "))
           ''', 'Headers X-Tag and x-tag must both match a lookup for X-TAG.'),
    family('csv-field-escaping', 'serialization',
           'csv_row(fields) receives a list of strings and returns one CSV record using '
           'comma delimiters and a CRLF record terminator. Parsing the result with Python '
           'csv.reader must recover the exact fields, including embedded commas, quotes, or newlines.',
           '''
           import csv
           import io

           def csv_row(fields):
               stream = io.StringIO(newline="")
               csv.writer(stream).writerow(fields)
               return stream.getvalue()
           ''', 'csv.writer(stream).writerow(fields)', 'stream.write(",".join(fields) + "\\r\\n")',
           'Replace the writer call with a comma join and CRLF. The inputs are already '
           'strings, so a CSV writer is unnecessary conversion overhead.',
           'Use csv.writer to quote and escape fields. Joining strings with commas '
           'changes the record when a field contains CSV delimiters or line breaks.',
           '''
           self.assertEqual(m.csv_row(["a", "b"]), "a,b\\r\\n")
           self.assertEqual(m.csv_row(["one"]), "one\\r\\n")
           ''', '''
           import csv
           import io
           for fields in (["a,b", "c"], ['a"b', "c"], ["a\\nb", ""], ["", ""]):
               result = m.csv_row(fields)
               self.assertTrue(result.endswith("\\r\\n"))
               self.assertEqual(list(csv.reader(io.StringIO(result, newline=""))), [fields])
           ''', 'A field containing "a,b" must remain one field after writing and reading the record.'),
    family('queue-drain-snapshot', 'collection-mutation',
           'drain_ready(queue, cutoff) receives a mutable list of (id, ready_time) tuples. '
           'Remove all entries with ready_time <= cutoff from that same list object and return '
           'them in their original order. Preserve the order of entries left in the queue.',
           '''
           def drain_ready(queue, cutoff):
               ready = []
               for task in list(queue):
                   if task[1] <= cutoff:
                       queue.remove(task)
                       ready.append(task)
               return ready
           ''', 'for task in list(queue):', 'for task in queue:',
           'Iterate over queue directly instead of copying it. The loop already removes '
           'processed tasks, so taking a snapshot wastes memory.',
           'Iterate over a snapshot while removing entries from queue. Removing from the '
           'list being iterated can skip the entry shifted into the current index.',
           '''
           queue = [("a", 1), ("b", 3)]
           self.assertEqual(m.drain_ready(queue, 1), [("a", 1)])
           self.assertEqual(queue, [("b", 3)])
           ''', '''
           queue = [("a", 1), ("b", 1), ("c", 5), ("d", 2), ("e", 6)]
           original = queue
           self.assertEqual(m.drain_ready(queue, 2), [("a", 1), ("b", 1), ("d", 2)])
           self.assertIs(queue, original)
           self.assertEqual(queue, [("c", 5), ("e", 6)])
           queue = [("same", 1), ("same", 1)]
           self.assertEqual(m.drain_ready(queue, 1), [("same", 1), ("same", 1)])
           self.assertEqual(queue, [])
           ''', 'Two adjacent ready entries must both be removed and returned during one drain.'),
    family('all-required-permissions', 'authorization-logic',
           'can_access(required, granted) receives sets of permission strings. Return True '
           'exactly when every required permission is granted. An empty required set permits access.',
           '''
           def can_access(required, granted):
               return required.issubset(granted)
           ''', 'required.issubset(granted)', 'bool(required & granted) or not required',
           'Use bool(required & granted) or not required for the permission check. '
           'An intersection confirms the user has access to the requested operation.',
           'Require the entire required set to be a subset of granted. An intersection '
           'only proves that at least one permission is present.',
           '''
           self.assertTrue(m.can_access({"read"}, {"read", "write"}))
           self.assertFalse(m.can_access({"read"}, {"write"}))
           self.assertTrue(m.can_access(set(), set()))
           ''', '''
           self.assertFalse(m.can_access({"read", "write"}, {"read"}))
           self.assertFalse(m.can_access({"read", "write"}, {"write", "admin"}))
           self.assertTrue(m.can_access({"read", "write"}, {"read", "write", "admin"}))
           ''', 'Granted read alone must not satisfy the required set {read, write}.'),
    family('whole-token-validation', 'input-validation',
           'valid_code(value) receives a string. Return True exactly for three ASCII uppercase '
           'letters, a hyphen, and three ASCII digits, with no leading/trailing characters or newline.',
           '''
           import re

           def valid_code(value):
               return re.fullmatch(r"[A-Z]{3}-[0-9]{3}", value) is not None
           ''', 're.fullmatch(', 're.match(',
           'Use re.match instead of re.fullmatch. Matching starts at the beginning of '
           'the input, which already establishes the required token format.',
           'Use re.fullmatch so the entire input must match. A valid prefix does not '
           'make a longer string a valid code.',
           '''
           self.assertTrue(m.valid_code("ABC-123"))
           self.assertFalse(m.valid_code("abc-123"))
           self.assertFalse(m.valid_code("!ABC-123"))
           ''', '''
           for value in ("ABC-123suffix", "ABC-123\\n", "ABC-123 ", "ABC-1234", "ABC-１２３"):
               self.assertFalse(m.valid_code(value))
           self.assertTrue(m.valid_code("XYZ-000"))
           ''', 'valid_code("ABC-123suffix") must return False.'),
    family('partial-stream-writes', 'io-contracts',
           'write_all(stream, data) receives bytes and a binary stream whose write(buffer) '
           'returns the positive number of bytes accepted, possibly fewer than requested. '
           'Write every byte in order and return len(data). If a write returns zero, raise '
           'BlockingIOError instead of spinning. Empty input needs no write.',
           '''
           def write_all(stream, data):
               offset = 0
               while offset < len(data):
                   written = stream.write(data[offset:])
                   if written == 0:
                       raise BlockingIOError("no progress")
                   offset += written
               return offset
           ''', '''offset = 0
    while offset < len(data):
        written = stream.write(data[offset:])
        if written == 0:
            raise BlockingIOError("no progress")
        offset += written
    return offset''', '''stream.write(data)
    return len(data)''',
           'Replace the loop with one stream.write(data) call and return len(data). '
           'The stream owns buffering, so retrying a successful write can duplicate bytes.',
           'Keep writing the unaccepted suffix until every byte is accepted. A successful '
           'stream.write call may consume only part of the supplied buffer.',
           '''
           from io import BytesIO
           stream = BytesIO()
           self.assertEqual(m.write_all(stream, b"abc"), 3)
           self.assertEqual(stream.getvalue(), b"abc")
           ''', '''
           class PartialStream:
               def __init__(self, capacity):
                   self.capacity = capacity
                   self.data = bytearray()
                   self.calls = 0
               def write(self, buffer):
                   self.calls += 1
                   accepted = min(len(buffer), self.capacity)
                   self.data.extend(buffer[:accepted])
                   return accepted
           for capacity in (1, 2, 4):
               stream = PartialStream(capacity)
               self.assertEqual(m.write_all(stream, b"abcdefg"), 7)
               self.assertEqual(bytes(stream.data), b"abcdefg")
           stream = PartialStream(1)
           self.assertEqual(m.write_all(stream, b""), 0)
           self.assertEqual(stream.calls, 0)
           with self.assertRaises(BlockingIOError):
               m.write_all(PartialStream(0), b"a")
           ''', 'A stream accepting at most two bytes per call must still receive all seven bytes of b"abcdefg".'),
    family('accurate-float-total', 'numeric-precision',
           'total(values) receives a list of finite floats for which math.fsum completes '
           'with a finite result. '
           'Return the result of Python math.fsum, retaining small contributions across '
           'cancellation. Do not mutate the list.',
           '''
           import math

           def total(values):
               return math.fsum(values)
           ''', 'math.fsum(values)', 'sum(values)',
           'Use the built-in sum instead of math.fsum. Both add the same float values, '
           'and the built-in avoids an unnecessary library call.',
           'Use math.fsum to retain the documented summation semantics. Ordinary sum '
           'can discard small terms before larger values cancel.',
           '''
           self.assertEqual(m.total([1.0, 2.0]), 3.0)
           self.assertEqual(m.total([]), 0.0)
           ''', '''
           import math
           values = [1e16, 1.0, -1e16]
           self.assertEqual(m.total(values), 1.0)
           self.assertEqual(values, [1e16, 1.0, -1e16])
           values = [1e100, 1e16, 1.0, -1e16, -1e100]
           self.assertEqual(m.total(values), math.fsum(values))
           ''', 'total([1e100, 1e16, 1.0, -1e16, -1e100]) must return 1.0.'),
    family('raw-byte-digest', 'content-integrity',
           'digest(payload) receives bytes and returns the lowercase hexadecimal SHA-256 '
           'digest of exactly those bytes. Leading/trailing spaces and line endings are significant.',
           '''
           from hashlib import sha256

           def digest(payload):
               return sha256(payload).hexdigest()
           ''', 'sha256(payload)', 'sha256(payload.strip())',
           'Strip payload before hashing it. Trimming insignificant surrounding whitespace '
           'makes equivalent text content produce a stable checksum.',
           'Hash payload without stripping it. This checksum identifies the exact bytes, '
           'including whitespace and line terminators.',
           '''
           from hashlib import sha256
           self.assertEqual(m.digest(b"abc"), sha256(b"abc").hexdigest())
           self.assertEqual(m.digest(b""), sha256(b"").hexdigest())
           ''', '''
           from hashlib import sha256
           for payload in (b"abc\\n", b" abc", b"abc ", b"\\r\\n", b"\\x00abc\\n"):
               self.assertEqual(m.digest(payload), sha256(payload).hexdigest())
           self.assertNotEqual(m.digest(b"abc"), m.digest(b"abc\\n"))
           ''', 'The digests for b"abc" and b"abc\\n" must differ.'),
    family('redirect-host-boundary', 'url-boundaries',
           'allowed_redirect(url, allowed_host) receives an absolute URL and a lowercase '
           'ASCII hostname. Permit only HTTPS URLs whose parsed hostname equals allowed_host. '
           'Hostname casing is insignificant; an explicit port is allowed. Subdomains and '
           'hostnames merely ending in allowed_host are not permitted.',
           '''
           from urllib.parse import urlsplit

           def allowed_redirect(url, allowed_host):
               parsed = urlsplit(url)
               return parsed.scheme == "https" and parsed.hostname == allowed_host
           ''', 'parsed.hostname == allowed_host', 'parsed.netloc.lower().endswith(allowed_host)',
           'Check parsed.netloc.lower().endswith(allowed_host). A suffix comparison is '
           'simpler and still ensures the destination belongs to the configured host.',
           'Compare the parsed hostname for exact equality. A netloc suffix can admit '
           'unrelated hostnames and mishandles an otherwise allowed explicit port.',
           '''
           self.assertTrue(m.allowed_redirect("https://example.test/path", "example.test"))
           self.assertFalse(m.allowed_redirect("http://example.test/path", "example.test"))
           self.assertFalse(m.allowed_redirect("https://elsewhere.test/", "example.test"))
           ''', '''
           self.assertFalse(m.allowed_redirect("https://evil-example.test/", "example.test"))
           self.assertFalse(m.allowed_redirect("https://sub.example.test/", "example.test"))
           self.assertTrue(m.allowed_redirect("https://EXAMPLE.TEST:443/path", "example.test"))
           self.assertFalse(m.allowed_redirect("https://example.test@evil.test/", "example.test"))
           ''', 'https://evil-example.test/ must not be allowed for the exact host example.test.'),
    family('numeric-release-versions', 'version-semantics',
           'at_least(current, minimum) receives version strings of exactly three dot-separated '
           'nonnegative decimal integers, without prerelease labels. Compare major, minor, and '
           'patch components numerically in that order; return whether current >= minimum.',
           '''
           def at_least(current, minimum):
               return tuple(map(int, current.split("."))) >= tuple(map(int, minimum.split(".")))
           ''', 'tuple(map(int, current.split("."))) >= tuple(map(int, minimum.split(".")))',
           'current >= minimum',
           'Compare current >= minimum directly. The components are already serialized '
           'in major/minor/patch order, so parsing them into tuples is redundant.',
           'Parse each component as an integer before comparing tuples. Lexical string '
           'ordering gives different results once a component has multiple digits.',
           '''
           self.assertTrue(m.at_least("2.1.0", "1.9.0"))
           self.assertFalse(m.at_least("1.2.0", "1.3.0"))
           self.assertTrue(m.at_least("1.2.3", "1.2.3"))
           ''', '''
           self.assertTrue(m.at_least("1.10.0", "1.2.0"))
           self.assertFalse(m.at_least("2.0.0", "10.0.0"))
           self.assertTrue(m.at_least("1.0.12", "1.0.9"))
           self.assertTrue(m.at_least("01.02.003", "1.2.3"))
           ''', 'Version 1.10.0 must be at least 1.2.0 under numeric component ordering.'),
    family('utf8-content-length', 'wire-format',
           'content_length(text) returns the number of bytes in the UTF-8 encoding of '
           'a UTF-8-encodable Unicode string (no lone surrogates), without a byte-order mark. '
           'This value is used as the length '
           'of the encoded HTTP body, not its character count.',
           '''
           def content_length(text):
               return len(text.encode("utf-8"))
           ''', 'len(text.encode("utf-8"))', 'len(text)',
           'Use len(text) instead of encoding just to count the length. Python strings '
           'already know their size, so allocating a temporary byte string is unnecessary.',
           'Count bytes after UTF-8 encoding. A Python string\'s character count does '
           'not equal the encoded body length for all Unicode input.',
           '''
           self.assertEqual(m.content_length("hello"), 5)
           self.assertEqual(m.content_length(""), 0)
           ''', '''
           for text in ("é", "雪", "🙂", "aé雪🙂", "e\\u0301"):
               self.assertEqual(m.content_length(text), len(text.encode("utf-8")))
           self.assertEqual(m.content_length("🙂"), 4)
           ''', 'The UTF-8 content length of one smiling-face emoji is four bytes, not one character.'),
    family('finite-json-numbers', 'serialization-validation',
           'encode_json(value) serializes JSON-compatible data using json.dumps with '
           'allow_nan=False. Reject NaN and positive/negative infinity anywhere in the data '
           'with ValueError, rather than emitting non-JSON numeric tokens.',
           '''
           import json

           def encode_json(value):
               return json.dumps(value, allow_nan=False)
           ''', ', allow_nan=False', '',
           'Remove allow_nan=False from json.dumps. The standard serializer already '
           'produces JSON, and overriding its defaults is unnecessary.',
           'Pass allow_nan=False so non-finite floats are rejected. The serializer\'s '
           'default permits NaN and Infinity tokens that this wire format excludes.',
           '''
           import json
           self.assertEqual(json.loads(m.encode_json({"x": 1.5, "y": [True, None]})),
                            {"x": 1.5, "y": [True, None]})
           ''', '''
           for value in (float("nan"), float("inf"), float("-inf"),
                         {"nested": [1, float("nan")]}):
               with self.assertRaises(ValueError):
                   m.encode_json(value)
           ''', 'encode_json({"x": float("nan")}) must raise ValueError, not emit a NaN token.'),
]

def mutant_source(item):
    return item.mutant
