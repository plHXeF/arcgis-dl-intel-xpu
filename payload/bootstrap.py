"""Prepare only this environment's loader; no driver, registry or DLL replacement."""
import sys,os,ctypes,importlib.abc,json
from pathlib import Path
LAYOUT=json.loads(Path(__file__).with_name('layout.json').read_text(encoding='utf-8'))
_handles=[ctypes.WinDLL(str(Path(os.environ['SystemRoot'])/'System32'/n))
          for n in ('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll')]
sys.path.insert(0,LAYOUT['overlay_path'])
os.environ.setdefault('TORCH_HOME',LAYOUT['torch_home'])
class _PrepareTorch(importlib.abc.MetaPathFinder):
    busy=False
    def find_spec(self,fullname,path=None,target=None):
        if fullname!='torch' or self.busy:return None
        self.busy=True
        try:
            import arcpy
            dll=Path(LAYOUT['intel_library_bin'])
            _handles.append(os.add_dll_directory(str(dll)))
            os.environ['PATH']=str(dll)+';'+os.environ.get('PATH','')
            os.environ['UR_ADAPTERS_FORCE_LOAD']=str(dll/'ur_adapter_level_zero.dll')
            for name in ('libmmd.dll','libiomp5md.dll','mkl_core.3.dll','sycl9.dll',
                         'mkl_sycl_blas.6.dll','mkl_sycl_dft.6.dll','mkl_sycl_lapack.6.dll'):
                _handles.append(ctypes.WinDLL(str(dll/name)))
        finally:
            sys.meta_path.remove(self)
        return None
sys.meta_path.insert(0,_PrepareTorch())
