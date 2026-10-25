"""Version and source signatures for the single locally validated profile."""
PROFILE={
    'pro_minor':'3.4','python_minor':'3.11','arcgis':'2.4.0',
    'essentials':'deep-learning-essentials=3.4=arcgispro_5',
    'torch':'2.14.1+xpu','torchvision':'0.29.1+xpu','cuda_solver':'11.8',
    'source_sha256':{
        'arcgis/learn/models/_arcgis_model.py':'7e3e680f5a28f09d17a0f6b470358ad1c246f51051fbdf011352201f217b5068',
        'arcgis/learn/models/_vitdet.py':'a982d506a6652d692e698dcab424bb4f9a7926dcc6b18f8313caa1b988e37165',
        'fastai/torch_core.py':'e2b062ccbef93332a2fe16a9aa9f6775b1e12212c19d5154a7340fd787c1ae4c',
        'fastai/basic_train.py':'d9cc1ca8686eb19f11783e0df063ab6525702d57c0aa2c9457fa2954e1eb6d29'
    }
}
def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('Unsupported source layout: '+old[:65])
    return text.replace(old,new,1)
def transform(rel,text):
    if rel.endswith('/_arcgis_model.py'):
        text=replace_once(text,'def _get_device():','''def _get_device():
    if getattr(arcgis.env, "_processorType", "") != "CPU" and torch.xpu.is_available():
        return torch.device("xpu", 0)
''')
        text=replace_once(text,'def _device_check():','''def _device_check():
    if getattr(arcgis.env, "_processorType", "") != "CPU" and torch.xpu.is_available():
        return False
''')
        text=replace_once(text,'self.device = torch.device("cuda")','self.device = _get_device()')
        text=replace_once(text,'torch.device("cuda")\n                if torch.cuda.is_available()',
                          'torch.device("xpu")\n                if torch.xpu.is_available()')
        text+='\nfrom arcgis_intel_xpu_runtime.adapter import install as _intel_xpu_install\n_intel_xpu_install(ArcGISModel)\n'
    elif rel.endswith('/_vitdet.py'):
        text=replace_once(text,'from ._mmlab_utils import load_mmlab_checkpoint','''# Avoid importing optional CUDA-compiled MMCV for the U-Net path.
def load_mmlab_checkpoint(*args, **kwargs):
    from ._mmlab_utils import load_mmlab_checkpoint as impl
    return impl(*args, **kwargs)''')
    elif rel=='fastai/torch_core.py':
        text=replace_once(text,"defaults.device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')",
                           "defaults.device = torch.device('xpu') if torch.xpu.is_available() else torch.device('cpu')")
    elif rel=='fastai/basic_train.py':
        text=replace_once(text,'torch.cuda.amp.GradScaler(enabled=self.mixed_precision)',
                           'torch.amp.GradScaler(self.device, enabled=self.mixed_precision)')
    else:raise ValueError('Unrecognised patch target: '+rel)
    compile(text,rel,'exec')
    return text
