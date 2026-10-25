"""ArcGIS Pro 3.4 Intel XPU patch manager. Uses Python bundled with ArcGIS.

No training is performed by this program, including after first installation.
"""
import argparse,contextlib,datetime,hashlib,json,os,re,shutil,subprocess,sys,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from profiles import PROFILE,transform
VERSION='0.1'
OVERLAY_PACKAGES=['torch','torchvision','functorch','torchgen','sympy','networkx','filelock','fsspec']
class PatchError(RuntimeError):pass
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
def path_value(value,base):
    p=Path(os.path.expandvars(value)).expanduser()
    return (p if p.is_absolute() else base/p).resolve()
class Manager:
    def __init__(self,config):
        self.config_path=Path(config).resolve()
        self.config=json.loads(self.config_path.read_text(encoding='utf-8-sig'))
        base=self.config_path.parent
        self.pro=path_value(self.config.get('arcgis_pro_dir') or str(Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'ArcGIS/Pro'),base)
        self.base=self.pro/'bin/Python/envs/arcgispro-py3'
        self.conda=self.pro/'bin/Python/Scripts/conda.exe'
        self.source=path_value(self.config['source_environment'],base) if self.config.get('source_environment') else self.base
        name=self.config.get('environment_name','pro-intel-xpu')
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{2,45}',name):raise PatchError('Invalid environment_name')
        if name.lower() in ('arcgispro-py3','pro-classroom','pro-xpu-experiment'):raise PatchError('Choose a NEW environment_name; existing classroom environments are protected.')
        self.root=path_value(self.config.get('runtime_root',r'%LOCALAPPDATA%\ArcGISProIntelXPU'),base)
        self.env=self.root/'envs'/name
        self.xpu=self.root/'envs/intel-xpu'
        self.overlay=self.root/'overlay'
        self.site=self.env/'Lib/site-packages'
        self.state_path=self.root/(name+'-install.json')
        self.alias=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'ESRI/conda/envs'/name
        self.project=path_value(self.config['project_path'],base) if self.config.get('project_path') else None
        self.reuse=path_value(self.config['reuse_environment'],base) if self.config.get('reuse_environment') else None
        # A bundle must never install into its ArcGIS installation or source environment.
        for protected in (self.pro,self.source):
            if self.root==protected or self.root.is_relative_to(protected):raise PatchError('runtime_root must be outside ArcGIS and the source environment')
        if self.root==self.root.parent or self.root==Path.home():raise PatchError('Choose a dedicated runtime_root directory')
        self.logfile=None
    def state(self):
        return json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {}
    def log(self,message):
        print(message,flush=True)
        if self.logfile:
            with self.logfile.open('a',encoding='utf-8') as f:f.write(datetime.datetime.now().isoformat()+' '+message+'\n')
    def run(self,args,env=None,timeout=None):
        args=[str(a) for a in args]
        self.log('RUN '+subprocess.list2cmdline(args))
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        process=subprocess.Popen(args,env=env or self.command_env(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,encoding='utf-8',errors='replace',creationflags=flags)
        for line in process.stdout:self.log(line.rstrip())
        code=process.wait(timeout=timeout)
        if code:raise PatchError('Command failed (exit '+str(code)+'). See installation log.')
    def command_env(self,prefix=None):
        env=os.environ.copy()
        for key in ('PYTHONHOME','PYTHONPATH','CONDA_PREFIX','CONDA_DEFAULT_ENV'):env.pop(key,None)
        env['PYTHONUTF8']='1';env['PIP_DISABLE_PIP_VERSION_CHECK']='1'
        env['CONDA_PKGS_DIRS']=str(self.root/'conda-pkgs')+','+str(self.pro/'bin/Python/pkgs')
        if prefix:
            env['PATH']=';'.join(str(prefix/p) for p in (Path('.'),Path('Library/bin'),Path('Scripts')))+';'+env.get('PATH','')
        return env
    def running_pro(self):
        r=subprocess.run(['powershell','-NoProfile','-Command',
            "@(Get-Process -Name ArcGISPro -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if r.returncode or not r.stdout.strip().isdigit():raise PatchError('Cannot determine whether ArcGIS is running; no changes made.')
        return int(r.stdout.strip())>0
    def require_closed(self):
        if self.running_pro():raise PatchError('Please save and CLOSE ALL ArcGIS Pro windows first. No running process will be stopped.')
    @contextlib.contextmanager
    def operation_lock(self):
        import msvcrt
        self.root.mkdir(parents=True,exist_ok=True)
        with (self.root/'operation.lock').open('a+b') as f:
            if f.tell()==0:f.write(b'0');f.flush()
            f.seek(0)
            try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as e:raise PatchError('Another patch operation is running. Please wait.') from e
            try:yield
            finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
    def version(self):
        records=list((self.base/'conda-meta').glob('arcgispro-*.json'))
        if not records:raise PatchError('ArcGIS Pro Conda metadata not found; check arcgis_pro_dir')
        value=json.loads(records[0].read_text(encoding='utf-8'))['version']
        return '.'.join(str(value).split('.')[:2])
    def gpu_info(self):
        try:
            r=subprocess.run(['powershell','-NoProfile','-Command',
                "[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
                "@(Get-CimInstance Win32_VideoController -ErrorAction Stop | Select-Object Name,DriverVersion,AdapterCompatibility) | ConvertTo-Json -Compress"],
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if r.returncode:return {'available':False,'note':'Driver metadata unavailable; actual support checked during installation'}
            rows=json.loads(r.stdout.strip() or '[]')
            if not rows:return {'available':False,'note':'No display adapter metadata returned; actual support checked during installation'}
            return {'available':True,'adapters':rows if isinstance(rows,list) else [rows]}
        except (OSError,ValueError,subprocess.TimeoutExpired):
            return {'available':False,'note':'Driver metadata unavailable; actual support checked during installation'}
    def preflight(self):
        for p in (self.pro/'bin/ArcGISPro.exe',self.base/'python.exe',self.conda,self.source/'python.exe'):
            if not p.is_file():raise PatchError('Missing: '+str(p))
        v=self.version()
        if v!=PROFILE['pro_minor']:
            raise PatchError('This release supports Pro 3.4 ONLY; detected '+v+'. No packages will be installed or patched.')
        if sys.version_info[:2]!=(3,11):raise PatchError('This profile requires ArcGIS Python 3.11')
        if not (self.source/'conda-meta/pinned').is_file():raise PatchError('Source must be an ArcGIS Conda environment with pinned dependencies')
        if self.project and not self.project.is_file():raise PatchError('project_path does not exist: '+str(self.project))
        if self.source.resolve()==self.env.resolve():raise PatchError('Source and target environments must be different')
        return v
    def check(self):
        v=self.preflight();state=self.state()
        if self.reuse:self.validate_reuse()
        status={'release':VERSION,'pro_minor':v,'arcgis_pro_dir':str(self.pro),
            'project_path':str(self.project) if self.project else None,'source_environment':str(self.source),
            'target_environment':str(self.env),'xpu_environment':str(self.xpu),
            'install_status':state.get('status','not_installed'),'torch_requested':PROFILE['torch'],
            'default_training_batch_limit':0,'check_type':'metadata only; no torch/ArcPy imports, GPU allocation or training',
            'driver_metadata':self.gpu_info()}
        if self.reuse:
            status.update(install_status='ready_external_reuse',target_environment=str(self.reuse),
                xpu_environment=None,
                note='Explicit read-only reuse; no environment modification or installation')
        if state.get('status')=='ready':
            status['missing']=[str(p) for p in (self.env/'python.exe',self.xpu/'Scripts/python.exe',
                self.site/'000_arcgis_intel_xpu.pth',self.site/'arcgis_intel_xpu_runtime/layout.json') if not p.exists()]
        self.log(json.dumps(status,ensure_ascii=False,indent=2))
        return status
    def validate_reuse(self):
        site=self.reuse/'Lib/site-packages'
        if not (self.reuse/'python.exe').is_file() or not (self.reuse/'conda-meta/pinned').is_file():
            raise PatchError('reuse_environment is not an ArcGIS clone')
        if not ((site/'000_classroom_xpu.pth').is_file() or (site/'000_arcgis_intel_xpu.pth').is_file()):
            raise PatchError('reuse_environment lacks this patch family startup marker; clear reuse_environment to install a new clone')
        records=list((self.reuse/'conda-meta').glob('arcgispro-*.json'))
        if not records or '.'.join(str(json.loads(records[0].read_text(encoding='utf-8'))['version']).split('.')[:2])!=PROFILE['pro_minor']:
            raise PatchError('Reused environment version does not match this ArcGIS profile')
    def save_state(self,**data):
        state=self.state();state.update(data)
        state.update(release=VERSION,target=str(self.env),runtime_root=str(self.root),source=str(self.source))
        write_json(self.state_path,state)
    def junction(self,path,target):
        path=Path(path);target=Path(target)
        if path.exists():
            if path.resolve()!=target.resolve():raise PatchError('Existing directory points elsewhere; will not replace: '+str(path))
            return
        if path.is_symlink():raise PatchError('Broken existing link will not be replaced: '+str(path))
        path.parent.mkdir(parents=True,exist_ok=True)
        quote=lambda x:"'"+str(x).replace("'","''")+"'"
        self.run(['powershell','-NoProfile','-Command',
            "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path "+quote(path)+' -Target '+quote(target)+' | Out-Null'])
    def install(self):
        self.preflight();self.require_closed()
        if self.reuse:
            self.validate_reuse();self.log('Using explicitly configured existing patched environment; no installation or source edits.');return
        self.root.mkdir(parents=True,exist_ok=True)
        (self.root/'logs').mkdir(exist_ok=True)
        self.logfile=self.root/'logs/install.log'
        state=self.state()
        if self.env.exists() and not state:raise PatchError('Target exists without this installer ownership record; refusing to modify it')
        if state.get('status')=='ready':
            if self.check().get('missing'):raise PatchError('Installation is incomplete; inspect log or rollback before repair')
            self.log('Already installed. No downloads or package changes.');return
        self.save_state(status=state.get('status','starting'))
        gpu=self.gpu_info()
        if gpu.get('available') and not any('intel' in str(row).lower() for row in gpu.get('adapters',[])):
            raise PatchError('No Intel display adapter detected; no packages downloaded. Check Intel GPU/driver requirements.')
        if not (self.env/'conda-meta/history').exists():
            if self.env.exists() and any(self.env.iterdir()):raise PatchError('Incomplete previous clone; choose a new environment_name. No files deleted.')
            self.log('Creating independent pinned ArcGIS clone...')
            self.run([self.conda,'create','--prefix',self.env,'--clone',self.source,'--pinned','-y'])
            self.save_state(status='cloned')
        if (self.source/'conda-meta/pinned').read_bytes()!=(self.env/'conda-meta/pinned').read_bytes():
            raise PatchError('Clone pinned dependencies differ from source; stop')
        essentials=list((self.env/'conda-meta').glob('deep-learning-essentials-3.4-arcgispro_5.json'))
        if not essentials:
            self.log('Installing official Esri essentials. First install can download several GB.')
            command_env=self.command_env();command_env['CONDA_OVERRIDE_CUDA']=PROFILE['cuda_solver']
            self.run([self.conda,'install','--prefix',self.env,'-c','esri',PROFILE['essentials'],'-y'],env=command_env)
        # Validate ALL original signatures before downloading XPU or editing source.
        self.patch_plan()
        xpu_owner=self.xpu/'arcgis-intel-xpu-owner.json'
        if (self.xpu/'Scripts/python.exe').exists() and not xpu_owner.exists():
            raise PatchError('Existing XPU environment is not owned by this installer; choose a different runtime_root')
        if not (self.xpu/'Scripts/python.exe').exists():
            if self.xpu.exists() and any(self.xpu.iterdir()):raise PatchError('Unmanaged/incomplete XPU directory exists; no deletion attempted')
            self.run([self.base/'python.exe','-I','-m','venv',self.xpu])
            write_json(xpu_owner,{'installer':'ArcGIS-Intel-XPU-Patch','release':VERSION})
        marker=self.xpu/'intel-xpu-packages.json'
        if not marker.exists():
            self.run([self.xpu/'Scripts/python.exe','-I','-m','pip','install',
                'torch=='+PROFILE['torch'],'torchvision=='+PROFILE['torchvision'],
                '--constraint',HERE/'constraints-xpu.txt',
                '--index-url','https://download.pytorch.org/whl/xpu','--cache-dir',self.root/'pip-cache',
                '--report',self.root/'logs/xpu-pip-report.json'])
            write_json(marker,{'torch':PROFILE['torch'],'torchvision':PROFILE['torchvision']})
        src=self.xpu/'Lib/site-packages'
        for name in OVERLAY_PACKAGES:
            if not (src/name).is_dir():raise PatchError('Missing XPU dependency '+name)
            self.junction(self.overlay/name,src/name)
        (self.overlay/'typing_extensions.py').write_bytes((src/'typing_extensions.py').read_bytes())
        self.save_state(status='dependencies_ready')
        self.apply_patch()
        self.junction(self.alias,self.env)
        # One tiny health probe only: no data/model/weights/optimizer/epoch.
        self.log('Checking ArcPy + XPU imports and a one-element XPU tensor (no training)...')
        self.run([self.env/'python.exe','-I','-X','utf8','-u','-c',
            "import arcpy,torch; from arcgis.learn.models import _unet; "
            "assert _unet.HAS_FASTAI; assert torch.xpu.is_available(); "
            "x=torch.ones(1,device='xpu'); torch.xpu.synchronize(); "
            "print('XPU_HEALTH_PASS',arcpy.GetInstallInfo()['Version'],torch.__version__,torch.xpu.get_device_name(0))"],
            env=self.command_env(self.env))
        self.save_state(status='ready',health='tiny_tensor_and_imports_passed')
        self.log('Installation complete. No training or model downloads performed. Use start.cmd.')
    def patch_plan(self):
        state=self.state();saved=state.get('source_changes',{})
        plan=[]
        for rel,expected in PROFILE['source_sha256'].items():
            p=self.site/rel
            if not p.is_file():raise PatchError('Missing framework source: '+rel)
            if rel in saved:
                b=self.root/'backups'/self.env.name/rel
                if not b.is_file() or sha(b)!=expected:raise PatchError('Original backup mismatch: '+rel)
                original=b.read_bytes()
                if sha(p) not in (expected,saved[rel]['patched_sha256']):raise PatchError('Framework modified since installation: '+rel)
            else:
                original=p.read_bytes()
                if hashlib.sha256(original).hexdigest()!=expected:raise PatchError('Unsupported framework source signature: '+rel+'. Target clone left unpatched; a matching profile is needed.')
            text=original.decode('utf-8').replace('\r\n','\n')
            adapted=transform(rel,text).encode('utf-8')
            plan.append((rel,original,adapted))
        return plan
    def apply_patch(self):
        plan=self.patch_plan();changes={}
        # Commit the backup + desired hash manifest before changing source, so retry/rollback can recover a partial apply.
        for rel,original,adapted in plan:
            b=self.root/'backups'/self.env.name/rel;b.parent.mkdir(parents=True,exist_ok=True)
            if not b.exists():b.write_bytes(original)
            changes[rel]={'original_sha256':hashlib.sha256(original).hexdigest(),
                'patched_sha256':hashlib.sha256(adapted).hexdigest()}
        self.save_state(status='patching',source_changes=changes)
        runtime=self.site/'arcgis_intel_xpu_runtime';runtime.mkdir(exist_ok=True)
        for name in ('__init__.py','bootstrap.py','adapter.py'):
            shutil.copy2(HERE/'payload'/name,runtime/name)
        write_json(runtime/'layout.json',{'overlay_path':str(self.overlay),'intel_library_bin':str(self.xpu/'Library/bin'),
            'torch_home':str(self.root/'torch-cache'),'log_dir':str(self.root/'logs')})
        for rel,original,adapted in plan:
            p=self.site/rel;tmp=p.with_name(p.name+'.intel-xpu-tmp')
            tmp.write_bytes(adapted);tmp.replace(p)  # break Conda hardlinks; NEVER write through shared source files
        (self.site/'000_arcgis_intel_xpu.pth').write_text('import arcgis_intel_xpu_runtime.bootstrap\n',encoding='ascii')
        self.save_state(status='patched')
    def start(self,smoke=False):
        self.preflight();self.require_closed()
        if self.reuse:self.validate_reuse()
        elif self.state().get('status')!='ready':
            if not self.config.get('auto_install',True):raise PatchError('Not installed. Run setup.cmd first.')
            self.install()
        status=self.check()
        if status.get('missing'):raise PatchError('Required files missing; startup aborted')
        if not self.reuse:self.patch_plan()
        target=self.reuse or self.env
        alias=(Path(os.environ['LOCALAPPDATA'])/'ESRI/conda/envs'/target.name) if self.reuse else self.alias
        self.junction(alias,target)
        self.run([self.conda,'proswap','-p',alias])
        env=self.command_env();env['ARCGIS_INTEL_XPU_MAX_BATCHES']='1' if smoke else '0'
        env['CLASSROOM_XPU_MAX_BATCHES']='1' if smoke else '0'  # compatibility with the original classroom runtime
        if not self.reuse:env['TORCH_HOME']=str(self.root/'torch-cache')
        args=[str(self.pro/'bin/ArcGISPro.exe')]
        if self.project:args.append(str(self.project))
        subprocess.Popen(args,env=env)
        self.log('Opened ArcGIS. Select '+target.name+' in Package Manager if necessary; native training: GPU / ID 0.')
        self.log('MODE: '+('SMOKE, one batch' if smoke else 'TRAINING, epochs controlled by native tool'))
    def rollback(self):
        self.preflight();self.require_closed();state=self.state()
        if self.reuse:
            self.run([self.conda,'proswap','-p',self.base])
            self.log('Original ArcGIS environment selected. Externally managed reused environment was not modified.');return
        if not state:raise PatchError('No owned installation to roll back')
        # Check all files BEFORE mutation. Never overwrite later user modifications.
        for rel,record in state.get('source_changes',{}).items():
            if sha(self.site/rel) not in (record['original_sha256'],record['patched_sha256']):
                raise PatchError('Refuse to overwrite later modifications: '+rel)
            if sha(self.root/'backups'/self.env.name/rel)!=record['original_sha256']:raise PatchError('Backup corrupted: '+rel)
        self.run([self.conda,'proswap','-p',self.base])
        pth=self.site/'000_arcgis_intel_xpu.pth'
        if pth.exists():pth.replace(pth.with_suffix('.pth.disabled'))
        for rel,record in state.get('source_changes',{}).items():
            p=self.site/rel;tmp=p.with_name(p.name+'.restore-tmp')
            tmp.write_bytes((self.root/'backups'/self.env.name/rel).read_bytes());tmp.replace(p)
        self.save_state(status='rolled_back')
        self.log('Original source restored in owned clone; original ArcGIS environment selected. Environments/logs retained, no data deleted.')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['setup','check','start','smoke','rollback'])
    p.add_argument('--config',default=str(HERE/'config.json'));args=p.parse_args()
    manager=None
    try:
        manager=Manager(args.config)
        action={'setup':manager.install,'check':manager.check,'start':manager.start,
            'smoke':lambda:manager.start(smoke=True),'rollback':manager.rollback}[args.action]
        if args.action=='check':action()
        else:
            manager.preflight();manager.require_closed()
            with manager.operation_lock():action()
        return 0
    except Exception as e:
        print('ERROR: '+str(e),file=sys.stderr,flush=True)
        if manager and manager.logfile:
            with manager.logfile.open('a',encoding='utf-8') as f:f.write(traceback.format_exc())
        return 1
if __name__=='__main__':raise SystemExit(main())
