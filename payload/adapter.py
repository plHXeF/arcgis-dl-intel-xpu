"""Scope-limited ArcGIS U-Net XPU adapter. No global CUDA availability spoofing."""
import os,json,time,functools
from pathlib import Path
LAYOUT=json.loads(Path(__file__).with_name('layout.json').read_text(encoding='utf-8'))
ROOT=Path(LAYOUT['log_dir'])
ROOT.mkdir(parents=True,exist_ok=True)
ADAPTER_REVISION='0.1'
def validation_preflight(model,limit):
    """Inspect sizes only; never iterate a loader or change the user's split."""
    data=getattr(model,'_data',None)
    if data is None:return {}
    def count(name):
        value=getattr(data,name,None)
        return len(value) if value is not None else 0
    result={'training_samples':count('train_ds'),'validation_samples':count('valid_ds'),
        'training_batches':count('train_dl'),'validation_batches':count('valid_dl'),
        'batch_size':getattr(getattr(data,'train_dl',None),'batch_size',None)}
    log('DATA_SPLIT',**result)
    if limit==0 and type(model).__name__=='UnetClassifier':
        if result['validation_samples']==0 or result['validation_batches']==0:
            raise ValueError('Validation set is empty. Increase Validation Percentage in the native tool '
                '(9 chips: use 20% instead of 10%). No training was started; no data split was changed.')
        if result['training_samples']==0 or result['training_batches']==0:
            raise ValueError('Training loader is empty. Reduce Batch Size (try 2) or provide more training chips. '
                'No training was started.')
    return result
def training_limit():
    # Normal ArcGIS launch must honour the epochs entered in its tool.
    # Smoke launchers explicitly set 1; no launch-time setting means no batch cap.
    value=os.environ.get('ARCGIS_INTEL_XPU_MAX_BATCHES','0')
    try:limit=int(value)
    except ValueError as e:
        raise ValueError('ARCGIS_INTEL_XPU_MAX_BATCHES must be an integer; 0=training, 1=smoke') from e
    if limit<0:raise ValueError('ARCGIS_INTEL_XPU_MAX_BATCHES must be >= 0')
    return limit
class BoundedXPUStop(Exception):pass
def log(event,**data):
    record={'event':event,'time':time.time(),'pid':os.getpid(),**data}
    with (ROOT/'xpu-adapter-events.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps(record,default=str)+'\n')
    print('[Arc XPU] '+event+' '+json.dumps(data,default=str),flush=True)
    try:
        import arcpy
        arcpy.AddMessage('[Arc XPU] '+event+' '+json.dumps(data,default=str))
    except Exception:pass
def install(cls):
    if getattr(cls,'_intel_xpu_patched',False):return
    cls._intel_xpu_patched=True
    import torch
    from fastai.callback import Callback
    # Legacy direct .to('cuda')/.cuda() calls in this experimental process only.
    # Devices continue to report xpu, and CUDA availability continues to report false.
    original_to=torch.Tensor.to
    def remap(d):
        if isinstance(d,str) and (d=='cuda' or d.startswith('cuda:')):return d.replace('cuda','xpu',1)
        if isinstance(d,torch.device) and d.type=='cuda':return torch.device('xpu',d.index or 0)
        return d
    @functools.wraps(original_to)
    def tensor_to(t,*args,**kwargs):
        if args:args=(remap(args[0]),)+args[1:]
        if 'device' in kwargs:kwargs['device']=remap(kwargs['device'])
        return original_to(t,*args,**kwargs)
    torch.Tensor.to=tensor_to
    def cuda(t,device=None,non_blocking=False,memory_format=torch.preserve_format):
        index=device.index if isinstance(device,torch.device) else device
        return t.to(torch.device('xpu',index or 0),non_blocking=non_blocking,memory_format=memory_format)
    torch.Tensor.cuda=cuda
    torch.nn.Module.cuda=lambda m,device=None:m.to(torch.device('xpu',device or 0))
    original_fit=cls.fit
    original_save=cls.save
    @functools.wraps(original_fit)
    def fit(self,*args,**kwargs):
        if getattr(self,'_device',torch.device('cpu')).type!='xpu':
            return original_fit(self,*args,**kwargs)
        limit=training_limit()
        self._intel_xpu_bounded_run=False
        validation_preflight(self,limit)
        log('FIT_ENTER',model=type(self).__name__,device=str(self._device),max_batches=limit,
            mode='training' if limit==0 else 'smoke',adapter_revision=ADAPTER_REVISION,
            limit_source='environment' if 'ARCGIS_INTEL_XPU_MAX_BATCHES' in os.environ else 'default',
            requested_epochs=kwargs.get('epochs',args[0] if args else 10),
            torch=torch.__version__,cuda_available=torch.cuda.is_available(),device_name=torch.xpu.get_device_name(0))
        if limit==0:return original_fit(self,*args,**kwargs)
        if limit<0:raise ValueError('ARCGIS_INTEL_XPU_MAX_BATCHES must be >= 0')
        model=self
        class Guard(Callback):
            _order=9999
            def on_train_begin(self,**kw):
                self.params=[p for p in model.learn.model.parameters() if p.requires_grad]
                self.old=[p.detach().clone() for p in self.params]
                self.steps=0;self.backward=False;self.begin=time.perf_counter()
            def on_batch_begin(self,last_input,last_target,train,**kw):
                if train:
                    assert last_input.device.type=='xpu' and last_target.device.type=='xpu'
                    self.shape=list(last_input.shape)
                    self.device=str(last_input.device)
            def on_backward_end(self,**kw):
                self.backward=any(p.grad is not None for p in self.params)
                assert self.backward and all(p.grad is None or torch.isfinite(p.grad).all() for p in self.params)
            def on_batch_end(self,last_loss,train,**kw):
                if not train:return
                self.steps+=1
                if self.steps<limit:return
                torch.xpu.synchronize()
                changed=any(not torch.equal(a,p.detach()) for a,p in zip(self.old,self.params))
                assert changed and self.backward and torch.isfinite(last_loss)
                result=dict(device=self.device,batch_shape=self.shape,loss=float(last_loss.detach().cpu()),
                    optimizer_steps=self.steps,epochs_completed=0,parameters_updated=changed,
                    finite_gradients=True,allocated=torch.xpu.memory_allocated(),reserved=torch.xpu.memory_reserved(),
                    seconds=time.perf_counter()-self.begin,native_fit=True,pid=os.getpid())
                (ROOT/'native-xpu-fit-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                (ROOT/f'native-xpu-fit-result-{os.getpid()}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                log('BOUNDED_TRAINING_PASS',**result)
                raise BoundedXPUStop('Requested bounded smoke stop after optimizer update; no completed epoch')
        kwargs['callbacks']=list(kwargs.get('callbacks',[]))+[Guard()]
        kwargs['checkpoint']=False
        # No learning-rate finder: it would do additional training updates.
        if kwargs.get('lr') is None and len(args)<2:kwargs['lr']=.001
        try:return original_fit(self,*args,**kwargs)
        except BoundedXPUStop:
            self._intel_xpu_bounded_run=True
            return None
    @functools.wraps(original_save)
    def save(self,*args,**kwargs):
        if getattr(self,'_intel_xpu_bounded_run',False):
            kwargs.update(compute_metrics=False,save_html=False)
            log('BOUNDED_SAVE',path=str(args[0]) if args else str(kwargs))
        return original_save(self,*args,**kwargs)
    cls.fit=fit;cls.save=save
    log('ADAPTER_INSTALLED',cuda_redirect=True,default_max_batches=0,adapter_revision=ADAPTER_REVISION)
