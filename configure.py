#!/usr/bin/env python3
"""Generate native OpenCode agents from portable, credential-free role bindings."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
ROLES = ('cloud-workflow','cloud-design','cloud-plan','cloud-review','local-worker','local-build','local-inspect','cloud-plan-review','cloud-structure-review','cloud-test-review')
TITLES = dict(zip(ROLES, ('自动协调','需求澄清与设计','编写计划','独立审计与复审','实施、测试与修复','独立实施入口','只读事实调查','独立计划审查','结构与架构审查','测试有效性审查')))
MAINTENANCE = ('build','general','explore','compaction','title','summary')
BINDING_KEYS = {'provider','model','variant','variants'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_binding(b, partial=False):
    require(isinstance(b,dict) and not set(b)-BINDING_KEYS, 'Unknown binding fields')
    for key in ('provider','model'):
        if key in b:
            require(isinstance(b[key],str) and b[key] and not re.search(r'[\s#]',b[key]), 'Invalid '+key)
        elif not partial:
            raise ValueError('Missing '+key)
    if 'provider' in b:
        require(re.fullmatch(r'[A-Za-z0-9_.-]+',b['provider']), 'Invalid provider ID')
    if 'variant' in b:
        require(b['variant'] is None or isinstance(b['variant'],str) and re.fullmatch(r'[A-Za-z0-9_.-]+',b['variant']), 'Invalid variant')
    require(isinstance(b.get('variants',[]),list), 'variants must be an array')
    seen=set()
    for v in b.get('variants',[]):
        require(isinstance(v,dict) and not set(v)-{'id','settings','body'}, 'Variant accepts id/settings/body only')
        vid=v.get('id','')
        require(isinstance(vid,str) and re.fullmatch(r'workflow-[A-Za-z0-9_.-]+',vid) and vid not in seen, 'Custom variant IDs must be unique and start with workflow-')
        seen.add(vid)
        for field in ('settings','body'):
            require(isinstance(v.get(field,{}),dict), 'Variant '+field+' must be an object')
        def check_keys(node):
            if isinstance(node,dict):
                for key,value in node.items():
                    require(not re.search(r'api.?key|password|secret|authorization|access.?token|refresh.?token|base.?url|endpoint',key,re.I),'Credentials and endpoints belong in private provider config')
                    check_keys(value)
            elif isinstance(node,list):
                for value in node:check_keys(value)
        check_keys(v)
        for key in ('reasoning_budget_tokens','max_tokens'):
            if key in v.get('body',{}):
                value=v['body'][key]
                require(type(value) is int and value>0, key+' must be a positive integer')
        body=v.get('body',{})
        if all(k in body for k in ('reasoning_budget_tokens','max_tokens')):
            require(body['reasoning_budget_tokens']<body['max_tokens'],'Thinking budget must leave output room')


def reference(binding):
    return binding['provider']+'/'+binding['model']+('#'+binding['variant'] if binding.get('variant') else '')


def visibility(role, bindings, session_cloud=False):
    coordinator=role if role in ('cloud-workflow','cloud-design','cloud-plan','local-build') else 'cloud-workflow'
    def identity(name):
        return 'current primary session selection (runtime identity)' if session_cloud and name.startswith('cloud-') else reference(bindings[name])
    identities='\n'.join('- '+name+': '+identity(name) for name in ROLES)
    return '''\n\nMODEL VISIBILITY CONTRACT (generated from models.json):
Actual configured role bindings (provider/model#variant):
'''+identities+'''
At every phase start, before delegation, after real successful dispatch, on each child result return, before approval questions and final delivery, emit this in the MAIN conversation, not reasoning or child-only text:
**【<阶段>｜<状态>】**

- 协调模型：`'''+identity(coordinator)+'''`
- 执行模型：`<actual executor provider/model#variant>`

Use separate Markdown bullet rows with a blank line after the heading. The configured coordinator above is the default for this role; a child must inherit the actual coordinator binding from its parent handoff. In standalone cloud-design/cloud-plan/local-build sessions, the primary role is the coordinator. If the selected session model differs from the configured identity, disclose the actual model; if unavailable, report an identity mismatch and stop, never print a false identity or silently switch providers. A configured variant is not proof of an observed request parameter.
Requirements/design use the current primary role; writing plans in cloud-workflow remains on cloud-workflow. Implementation, interleaved TDD testing, repairs and finalization use local-worker; independent audit/re-audit use cloud-review; fact discovery uses local-inspect. Standalone local-build implements directly with its own binding. Use the exact binding above for the role actually executing that phase. Final delivery must identify the primary reply model as executor, and name the last child's model separately if useful.
Stages: 需求澄清 / 需求设计确认 / 编写计划 / 独立计划审查 / 计划确认 / 实施与测试(TDD) / 独立审计 / 结构审查 / 测试审查 / 门禁核验 / 修复与复验 / 独立复审 / 归档收尾 / 最终交付. Status: 开始 / 等待确认 / 待派发 / 已派发 / 结果已返回 / 需要修复 / 复审通过 / 已完成 / 失败或阻塞.
Before subagent use 待派发. Say 已派发 only after a real successful tool response returns sessionID. In each delegation description prefix [<target role> | <exact target binding>] and the phase. Include all actual role bindings and this visibility rule in the handoff. On child callback, the MAIN coordinator must relay a fresh block identifying the child's executor and whether the report is awaiting independent review. Tests passed does not mean overall completion. Child reports also show coordinator and their own executor. Native child cards/input pickers are not a global model switch; these are workflow messages, not system-attested badges.
'''


def compile_config(base, spec, templates, previous=None):
    require(isinstance(spec,dict) and not set(spec)-{'version','defaults','roles','routing'},'Unknown specification fields')
    require(spec.get('version')==1,'Unsupported version')
    routing=spec.get('routing',{})
    require(isinstance(routing,dict) and not set(routing)-{'cloud_model'},'Unknown routing fields')
    require(routing.get('cloud_model','fixed') in ('fixed','session'),'Invalid cloud_model routing')
    session_cloud=routing.get('cloud_model')=='session'
    defaults=spec.get('defaults',{})
    require(isinstance(defaults,dict) and set(defaults)=={'cloud','local'},'defaults must contain cloud and local')
    for b in defaults.values():validate_binding(b)
    overrides=spec.get('roles',{})
    require(isinstance(overrides,dict) and not set(overrides)-set(ROLES),'Unknown role')
    require(not session_cloud or not any(value for role,value in overrides.items() if role.startswith('cloud-')),
            'Session cloud routing conflicts with fixed cloud role overrides')
    bindings={}
    for role in ROLES:
        override=overrides.get(role,{})
        validate_binding(override,True)
        bindings[role]={**copy.deepcopy(defaults[role.split('-')[0]]),**copy.deepcopy(override)}
        validate_binding(bindings[role])
    out=copy.deepcopy(base)
    generated={}
    for binding in list(defaults.values())+list(bindings.values()):
        for variant in binding.get('variants',[]):
            key=(binding['provider'],binding['model'],variant['id'])
            require(key not in generated or generated[key]==variant,'Conflicting variant definitions for '+str(key))
            generated[key]=variant
    for item in (previous or {}).get('variants',[]):
        model=out.get('providers',{}).get(item['provider'],{}).get('models',{}).get(item['model'],{})
        variants=model.get('variants',[])
        found=[v for v in variants if v.get('id')==item['value']['id']]
        require(not found or found==[item['value']],'Managed variant was modified outside generator: '+item['value']['id'])
        if found:model['variants']=[v for v in variants if v.get('id')!=item['value']['id']]
    state={'version':1,'variants':[],'roles':{role:reference(b) for role,b in bindings.items()},'permissions':{}}
    owned=(previous or {}).get('routing_plugin')
    if owned:
        plugins=out.get('plugins',[])
        require(not any((p if isinstance(p,str) else p.get('package'))==owned['package'] and p!=owned for p in plugins),
                'Managed routing plugin was modified outside generator')
        out['plugins']=[p for p in plugins if p!=owned]
    if session_cloud:
        plugin={'package':str(ROOT/'plugins/cloud-session-router'),'options':{
            'cloudRoles':[r for r in ROLES if r.startswith('cloud-')],
            'localBindings':{r:reference(b) for r,b in bindings.items() if r.startswith('local-')}}}
        require(not any((p if isinstance(p,str) else p.get('package'))==plugin['package'] for p in out.get('plugins',[])),
                'Refusing to overwrite unowned routing plugin')
        out.setdefault('plugins',[]).append(plugin)
        state['routing_plugin']=copy.deepcopy(plugin)
        state['roles'].update({r:'session' for r in ROLES if r.startswith('cloud-')})
    for (pid,mid,vid),value in sorted(generated.items()):
        require(pid in out.get('providers',{}),'Configure custom variant provider privately first: '+pid)
        model=out['providers'][pid].setdefault('models',{}).setdefault(mid,{})
        variants=model.setdefault('variants',[])
        require(not any(v.get('id')==vid for v in variants),'Refusing to overwrite unowned variant: '+vid)
        variants.append(copy.deepcopy(value))
        state['variants'].append({'provider':pid,'model':mid,'value':copy.deepcopy(value)})
    agents=out.setdefault('agents',{})
    old_worker=agents.pop('strata-worker',None)
    require(old_worker is None or 'local-worker' not in agents,
            'Both legacy strata-worker and local-worker exist; reconcile before migration')
    if old_worker is not None:
        agents['local-worker']=old_worker
    for role in ROLES:
        permissions=copy.deepcopy(agents.get(role,{}).get('permissions',templates['agents'][role].get('permissions',[])))
        legacy = templates.get('permission_migrations', {}).get(role)
        managed = (permissions == templates['agents'][role].get('permissions', [])
                   or legacy is not None and permissions == legacy
                   or permissions in templates.get('permission_revisions', {}).get(role, [])
                   or role in (previous or {}).get('permissions', {}) and permissions == previous['permissions'][role])
        if managed:
            permissions = copy.deepcopy(templates['agents'][role].get('permissions', []))
            state['permissions'][role] = copy.deepcopy(permissions)
        for permission in permissions:
            if permission.get('action')=='subagent' and permission.get('resource')=='strata-worker':
                permission['resource']='local-worker'
        agents[role]=copy.deepcopy(templates['agents'][role])
        agents[role]['permissions']=permissions
        dynamic=session_cloud and role.startswith('cloud-')
        if not dynamic:agents[role]['model']=reference(bindings[role])
        else:agents[role].pop('model',None)
        agents[role]['description']='['+role+' | '+('session' if dynamic else reference(bindings[role]))+'] '+TITLES[role]
        agents[role]['system']+=visibility(role,bindings,session_cloud)
    for name in MAINTENANCE:
        agents.setdefault(name,{})['model']=reference(defaults['local'])
    for name,template in templates.get('commands',{}).items():
        command=copy.deepcopy(template)
        dynamic=session_cloud and command['agent'].startswith('cloud-')
        if not dynamic:command['model']=reference(bindings[command['agent']])
        else:command.pop('model',None)
        command['description']='['+command['agent']+' | '+('session' if dynamic else command['model'])+'] '+TITLES[command['agent']]
        out.setdefault('commands',{})[name]=command
    out['model']=reference(defaults['cloud']);out['default_agent']='cloud-workflow'
    # Detect forgotten references in active workflow definitions, not user history/other settings.
    require('strata-worker' not in json.dumps({r:agents[r] for r in ROLES}), 'Old role reference remains')
    return out,state


def atomic_write(path, raw):
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as f:
            os.fchmod(f.fileno(),0o600);f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def install(target,spec,templates,apply=False):
    target=Path(target).expanduser();statepath=target.parent/'.workflow-generated-state.json'
    raw=target.read_bytes();base=json.loads(raw)
    previous=json.loads(statepath.read_text()) if statepath.exists() else None
    out,state=compile_config(base,spec,templates,previous)
    changed=out!=base
    summary={'changed':changed,'applied':False,'roles':state['roles'],'custom_variants':[v['value']['id'] for v in state['variants']],'backup':None}
    if not apply or not changed:return summary
    require(target.read_bytes()==raw,'Target changed during generation; retry')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=target.parent/'backups'/('role-model-config-'+stamp);backup.mkdir(parents=True,mode=0o700)
    for p in (target,statepath):
        if p.exists():shutil.copy2(p,backup/p.name);os.chmod(backup/p.name,0o600)
    previous_state=statepath.read_bytes() if statepath.exists() else None
    newraw=(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode()
    try:
        atomic_write(statepath,(json.dumps(state,ensure_ascii=False,indent=2)+'\n').encode())
        atomic_write(target,newraw)
    except BaseException:
        if previous_state is None:statepath.unlink(missing_ok=True)
        else:atomic_write(statepath,previous_state)
        raise
    summary.update(applied=True,backup=str(backup),sha256=hashlib.sha256(newraw).hexdigest())
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models',type=Path,default=ROOT/'models.json')
    parser.add_argument('--target',type=Path,default=Path.home()/'.config/opencode/opencode.json')
    parser.add_argument('--apply',action='store_true',help='Back up and install (default: dry run)')
    args=parser.parse_args()
    try:
        result=install(args.target,json.loads(args.models.read_text()),json.loads((ROOT/'templates.json').read_text()),args.apply)
    except (ValueError,OSError) as exc:
        parser.exit(1,'Configuration rejected: '+str(exc)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
