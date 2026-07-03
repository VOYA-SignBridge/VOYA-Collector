from app.storage.gdrive_client import get_gdrive_client
c = get_gdrive_client()
fid = c.resolve_folder_path('features/vn/bang-chu-cai/class_ahaaa1_c184f3ff')
print('ID:', fid)
if fid:
    files = c.service.files().list(q=f"'{fid}' in parents", spaces='drive', fields='files(id, name)').execute()
    print([f['name'] for f in files.get('files', [])])
