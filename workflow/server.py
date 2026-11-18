"""MCP stdio: inspection plus narrow local registration; no command/project-write tools."""
import argparse
import json
import sys
from .runtime import Runtime, read_json

S = {'type': 'string', 'minLength': 1}
def schema(props):
    return {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}
TOOLS = [
 {'name': 'quality_info', 'description': 'List explicitly registered quality projects; no credentials.', 'inputSchema': schema({})},
 {'name': 'quality_resource', 'description': 'Read a fixed public schema or pinned BMAD bundled resource by its logical name from quality_info. Cannot read arbitrary files or user directories.', 'inputSchema': schema({'name': S})},
 {'name': 'quality_prepare', 'description': 'Read and validate a registered project contract; return exact snapshot and required review kinds. Does not execute commands.', 'inputSchema': schema({'project': S, 'contract': S})},
 {'name': 'quality_gate', 'description': 'Recompute final quality verdict against current bytes, original evidence, and independent review JSON files. Missing/stale/failed checks cannot pass. Read only.', 'inputSchema': schema({'project': S, 'contract': S, 'evidence': S, 'reviews': {'type': 'array', 'items': S}})}]
TOOLS[2]['inputSchema']['properties']['plan_reviews'] = {'type': 'array', 'items': S}
for tool in TOOLS: tool['annotations'] = {'readOnlyHint': True}
TOOLS.append({'name': 'quality_onboard',
              'description': 'Resolve the current absolute project directory and automatically register missing projects in the local registry. Reuses existing policy unchanged. New projects use repository-native rules, no invented commands. Only writes the fixed private registry/backup; never project files or execution evidence. Registration is not acceptance.',
              'inputSchema': schema({'project': S}),
              'annotations': {'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': True}})

def serve(runtime):
    for line in sys.stdin:
        rid = None
        try:
            request = json.loads(line); rid = request.get('id'); method = request.get('method')
            if rid is None: continue
            if method == 'initialize':
                result = {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'opencode-quality', 'version': '1.0.0'}}
            elif method == 'ping': result = {}
            elif method == 'tools/list': result = {'tools': TOOLS}
            elif method == 'tools/call':
                params = request['params']; name = params['name']; args = params.get('arguments', {})
                spec = next(t for t in TOOLS if t['name'] == name)
                from .schema import validate
                if validate(args, spec['inputSchema']): raise ValueError('Invalid tool arguments')
                fn = {'quality_info': runtime.info, 'quality_resource': runtime.resource, 'quality_prepare': runtime.prepare, 'quality_gate': runtime.gate, 'quality_onboard': runtime.onboard}[name]
                try:
                    value = fn(**args)
                    body = value['content'] if name == 'quality_resource' else json.dumps(value, ensure_ascii=False)
                    result = {'content': [{'type': 'text', 'text': body}], 'structuredContent': value}
                except (ValueError, OSError, KeyError, TypeError):
                    result = {'isError': True, 'content': [{'type': 'text', 'text': 'Invalid/unavailable quality artifacts or unregistered project; not a pass.'}]}
            else:
                raise ValueError('Unknown method')
            response = {'jsonrpc': '2.0', 'id': rid, 'result': result}
        except (ValueError, KeyError, TypeError, StopIteration):
            response = {'jsonrpc': '2.0', 'id': rid, 'error': {'code': -32602, 'message': 'Invalid quality protocol request'}}
        print(json.dumps(response, ensure_ascii=False), flush=True)

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--settings', required=True)
    args = parser.parse_args(); serve(Runtime(read_json(args.settings), settings_path=args.settings))
if __name__ == '__main__': main()
