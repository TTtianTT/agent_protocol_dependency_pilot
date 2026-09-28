import json
from pathlib import Path
from huggingface_hub import HfApi,snapshot_download
root=Path(__file__).resolve().parents[1]; repo='Qwen/Qwen3.5-4B'
info=HfApi().model_info(repo,files_metadata=True)
files=[s for s in info.siblings if s.rfilename.endswith(('.json','.safetensors','.jinja','.txt')) and '/' not in s.rfilename]
size=sum(s.size or 0 for s in files)
assert size<10*1024**3,(size,'download over budget')
(root/'configs/model_download.json').write_text(json.dumps({'repo':repo,'revision':info.sha,'bytes':size,'files':[(s.rfilename,s.size) for s in files]},indent=2))
print(repo,info.sha,size,flush=True)
snapshot_download(repo,revision=info.sha,allow_patterns=[s.rfilename for s in files],local_dir='/dataset1/zailong/models/Qwen3.5-4B',max_workers=4)
