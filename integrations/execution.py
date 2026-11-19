"""Pure, portable execution capability selection; no downloads or credential handling."""
import copy
from pathlib import Path
DEFAULTS={'search':{'enabled':False},'rtk':{'enabled':False,'profile':'safe-output'},'ast_grep':{'enabled':False},
          'worker_skill':False,'rust_skills':[],'serena':{'mode':'off'},'browser':{'mode':'off'}}
def parse_execution(raw):
    if raw is None: return copy.deepcopy(DEFAULTS)
    if not isinstance(raw,dict) or set(raw)-set(DEFAULTS): raise ValueError('Unknown execution capability')
    result=copy.deepcopy(DEFAULTS)
    for key,value in raw.items():
        if key=='worker_skill':
            if type(value) is not bool: raise ValueError('worker_skill must be boolean')
        elif key=='rust_skills':
            if not isinstance(value,list) or any(not isinstance(v,str) for v in value) or len(value)!=len(set(value)) or any(v not in ('ownership','error-handling','concurrency') for v in value):raise ValueError('Invalid Rust modules')
        else:
            if not isinstance(value,dict) or set(value)-set(DEFAULTS[key]):raise ValueError('Invalid '+key+' options')
            value={**DEFAULTS[key],**value}
            if 'enabled' in value and type(value['enabled']) is not bool:raise ValueError('enabled must be boolean')
            allowed={'rtk':('safe-output',),'serena':('off','symbols-readonly'),'browser':('off','playwright-cli')}
            field='profile' if key=='rtk' else 'mode'
            if key in allowed and value[field] not in allowed[key]:raise ValueError('Invalid '+key+' mode')
        result[key]=copy.deepcopy(value)
    return result

def active(options):
    return options!=DEFAULTS

def configure_execution(out,state,previous,spec,templates,root):
    options=parse_execution(spec.get('execution'))
    owned=(previous or {}).get('execution_plugin')
    if owned:
        plugins=out.get('plugins',[])
        for p in plugins:
            if isinstance(p,dict) and p.get('package')==owned['package'] and p!=owned:raise ValueError('Managed execution plugin modified externally')
        out['plugins']=[p for p in plugins if p!=owned]
    if not active(options):return templates
    entry={'package':str(root/'plugins/execution-tools'),'options':options}
    if any((p if isinstance(p,str) else p.get('package'))==entry['package'] for p in out.get('plugins',[])):raise ValueError('Foreign execution plugin collision')
    out.setdefault('plugins',[]).append(entry);state['execution_plugin']=copy.deepcopy(entry)
    result=copy.deepcopy(templates)
    for role,agent in result['agents'].items():
        if options['worker_skill']:
            agent['system']=agent['system'].replace('uses executing-plans','uses local-execution')
            if role in ('local-worker','local-build'):
                agent['system']=agent['system'].replace('Load executing-plans, test-driven-development and verification-before-completion.', 'Load local-execution, test-driven-development and verification-before-completion.')
                agent['system']=agent['system'].replace('Load executing-plans for implementation, plus its test-driven-development and verification dependencies.', 'Load local-execution for implementation, plus test-driven-development and verification-before-completion. Do not reload the heavy executing-plans setup or create a second ledger.')
        if role in ('local-worker','local-build','local-inspect'):
            if options['search']['enabled']:
                agent.setdefault('permissions',[]).extend({'action':name,'resource':'*','effect':'allow'} for name in ('execution_search','execution_status'))
                agent['system']+='\nSEARCH ROUTING: First load local-execution via skill. For file discovery and plain-text code lookup prefer execution_search (mode files/text, narrow paths). Use execution_ast_search for Rust syntax patterns when available. Do not build compound cd/find/grep/head pipelines for source lookup. Shell remains for actual builds/tests and justified tool-unavailable fallbacks. At handoff call execution_status and report actual skills/tools and RTK results; never claim usage from availability.\n'
            if options['ast_grep']['enabled']:agent.setdefault('permissions',[]).append({'action':'execution_ast_search','resource':'*','effect':'allow'})
            if options['worker_skill'] and role!='local-inspect':agent['system']+='\nEXECUTION EFFICIENCY: Use the short approved implementation brief. Keep the approved handoff, use actual compiler/test diagnostics, run the required native checks, and return awaiting_review with original logs. Do not re-plan, re-register, spawn agents or call unavailable context tools.\n'
            if options['ast_grep']['enabled']:agent['system']+='\nSTRUCTURAL SEARCH: Use execution_ast_search only for syntax patterns inside this task worktree; ordinary strings use rg/read. Zero structural matches do not prove absence. No rewrite or cross-worktree search.\n'
            if options['rust_skills']:agent['system']+='\nRUST DIAGNOSTICS: Load rust-diagnostics only for an actual ownership, error-propagation or concurrency problem; follow repository contracts over general advice.\n'
    if options['worker_skill']:
        for command in result.get('commands',{}).values():
            if command.get('agent')=='local-build':command['template']=command['template'].replace('Load executing-plans','Load local-execution')
    return result
