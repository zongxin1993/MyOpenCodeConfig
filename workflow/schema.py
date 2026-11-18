"""Validate the deliberately small JSON Schema vocabulary shipped in this package.

Not a general-purpose JSON Schema implementation. Unsupported keywords fail.
"""
import json
import math
import re
from pathlib import Path

SCHEMAS = Path(__file__).resolve().parents[1] / 'schemas'
KEYS = {'$schema', 'title', 'description', 'type', 'properties', 'required',
        'additionalProperties', 'items', 'enum', 'minLength', 'minItems',
        'minimum', 'maximum', 'exclusiveMinimum', 'pattern'}

def validate(value, schema, path='$'):
    if set(schema) - KEYS:
        return [path + ': unsupported schema keywords']
    errors = []
    types = schema.get('type', [])
    types = [types] if isinstance(types, str) else types
    predicates = {'object': lambda v: type(v) is dict, 'array': lambda v: type(v) is list,
                  'string': lambda v: type(v) is str, 'boolean': lambda v: type(v) is bool,
                  'integer': lambda v: type(v) is int,
                  'number': lambda v: type(v) in (int, float), 'null': lambda v: v is None}
    if types and not any(t in predicates and predicates[t](value) for t in types):
        return [path + ': invalid type']
    if 'enum' in schema and value not in schema['enum']:
        errors.append(path + ': value not allowed')
    if type(value) is dict:
        props = schema.get('properties', {})
        for name in schema.get('required', []):
            if name not in value: errors.append(path + '.' + name + ': required')
        if schema.get('additionalProperties') is False:
            errors += [path + '.' + k + ': unknown field' for k in value if k not in props]
        for name in value.keys() & props.keys():
            errors += validate(value[name], props[name], path + '.' + name)
    if type(value) is list:
        if len(value) < schema.get('minItems', 0): errors.append(path + ': too few items')
        for i, item in enumerate(value):
            errors += validate(item, schema.get('items', {}), path + '[' + str(i) + ']')
    if type(value) is str:
        if len(value.strip()) < schema.get('minLength', 0): errors.append(path + ': empty/short text')
        if 'pattern' in schema and re.fullmatch(schema['pattern'], value) is None:
            errors.append(path + ': invalid format')
    if type(value) in (int, float):
        if not math.isfinite(value): return errors + [path + ': nonfinite number']
        if value < schema.get('minimum', float('-inf')) or value > schema.get('maximum', float('inf')):
            errors.append(path + ': outside bounds')
        if 'exclusiveMinimum' in schema and value <= schema['exclusiveMinimum']:
            errors.append(path + ': must be positive')
    return errors

def check(value, name):
    return validate(value, json.loads((SCHEMAS / (name + '.schema.json')).read_text()))
