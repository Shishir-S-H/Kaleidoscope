import subprocess, os

containers = ['image_tagger', 'scene_recognition', 'image_captioning']
for name in containers:
    env_out = subprocess.check_output(['docker', 'exec', name, 'env']).decode()
    env_vars = dict(l.split('=', 1) for l in env_out.strip().splitlines() if '=' in l)
    model = env_vars.get('GOOGLE_GEMINI_MODEL', 'MISSING')
    project = env_vars.get('GOOGLE_CLOUD_PROJECT', 'MISSING')
    region = env_vars.get('GOOGLE_CLOUD_REGION', 'MISSING')
    cred = env_vars.get('GOOGLE_CREDENTIALS_BASE64', '')
    print(f'--- {name} ---')
    print(f'  GOOGLE_GEMINI_MODEL:       {model}')
    print(f'  GOOGLE_CLOUD_PROJECT:      {project}')
    print(f'  GOOGLE_CLOUD_REGION:       {region}')
    print(f'  GOOGLE_CREDENTIALS_BASE64: {"PRESENT (" + str(len(cred)) + " chars)" if len(cred) > 100 else "EMPTY/MISSING"}')
