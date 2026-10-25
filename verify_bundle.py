"""Fast static checks only. Never imports torch/ArcPy, installs packages or trains."""
from pathlib import Path
import argparse,ast,hashlib,json,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from profiles import PROFILE,transform
def main():
    p=argparse.ArgumentParser();p.add_argument('--pristine-site');args=p.parse_args()
    python_files=list(HERE.glob('*.py'))+list((HERE/'payload').glob('*.py'))
    for path in python_files:ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
    config=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
    assert config['reuse_environment']=='' and config['project_path']==''
    for name in ('setup.cmd','start.cmd','check.cmd','smoke.cmd','rollback.cmd'):
        entry=(HERE/name).read_text(encoding='utf-8')
        assert 'launch.cmd' in entry and 'bootstrap.ps1' not in entry
    launcher=(HERE/'launch.cmd').read_text(encoding='utf-8')
    assert '-File ' not in launcher and '-ExecutionPolicy' not in launcher
    payload=(HERE/'payload/adapter.py').read_text(encoding='utf-8')
    assert "ARCGIS_INTEL_XPU_MAX_BATCHES','0'" in payload
    for path in [HERE/'patch_manager.py',*list((HERE/'payload').glob('*.py'))]:
        content=path.read_text(encoding='utf-8')
        assert not any(part in content.replace(chr(92),'/').lower() for part in ('c:/users/', 'd:/study/')),str(path)
    patched=[]
    if args.pristine_site:
        for rel,expected in PROFILE['source_sha256'].items():
            data=(Path(args.pristine_site)/rel).read_bytes()
            assert hashlib.sha256(data).hexdigest()==expected,rel
            adapted=transform(rel,data.decode('utf-8').replace('\r\n','\n'))
            assert adapted!=data.decode('utf-8')
            ast.parse(adapted,filename=rel);patched.append(rel)
    result={'python_files_parsed':len(python_files),'clean_public_config':True,
        'source_transformations_verified':patched,'training_default_limit':0,
        'installs_performed':0,'gpu_allocations':0,'training_steps':0,
        'clean_machine_install_tested':False}
    print(json.dumps(result,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
